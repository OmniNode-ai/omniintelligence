"""
Comprehensive test configuration for Archon intelligence testing system.

Includes fixtures for intelligence document testing, correlation algorithms,
performance testing, and comprehensive API endpoint testing.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load test environment variables from .env.test
env_test_path = Path(__file__).parent.parent / ".env.test"
if env_test_path.exists():
    load_dotenv(env_test_path)

# Set test environment
os.environ["TEST_MODE"] = "true"
os.environ["TESTING"] = "true"

# Only set fake credentials if NOT running real integration tests
if os.getenv("REAL_INTEGRATION_TESTS") != "true":
    # Set fake database credentials to prevent connection attempts
    os.environ["SUPABASE_URL"] = "https://test.supabase.co"
    os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
else:
    # Load real credentials from .env for integration tests
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

# Set required port environment variables for ServiceDiscovery
os.environ.setdefault("ARCHON_SERVER_PORT", "8181")
os.environ.setdefault("ARCHON_AGENTS_PORT", "8052")

# Import centralized configuration
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.kafka_helper import KAFKA_HOST_SERVERS

# Import fixture modules (pytest discovers fixtures automatically)
from tests.fixtures import (
    correlation_test_data,
    file_location_fixtures,
    intelligence_documents,
)

# Register fixture modules with pytest
pytest_plugins = [
    "tests.fixtures.correlation_test_data",
    "tests.fixtures.intelligence_documents",
    "tests.fixtures.file_location_fixtures",
]


def pytest_addoption(parser):
    """Add custom command line options for test configuration."""
    parser.addoption(
        "--real-integration",
        action="store_true",
        default=False,
        help="Run real integration tests against live services (Kafka, Qdrant, Memgraph)",
    )


def pytest_configure(config):
    """Configure pytest with custom behavior based on command line options."""
    # Set environment variable if --real-integration flag is used
    if config.getoption("--real-integration"):
        os.environ["REAL_INTEGRATION_TESTS"] = "true"
        config.addinivalue_line(
            "markers",
            "real_integration: marks tests requiring real service connections",
        )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to skip real_integration tests unless explicitly requested.

    Tests marked with @pytest.mark.real_integration will be skipped unless
    --real-integration flag is provided on command line.
    """
    if config.getoption("--real-integration"):
        # Running with --real-integration flag, don't skip
        return

    skip_real_integration = pytest.mark.skip(
        reason="Real integration test - requires --real-integration flag and live services"
    )

    for item in items:
        if "real_integration" in item.keywords:
            item.add_marker(skip_real_integration)


@pytest.fixture(autouse=True)
def prevent_real_db_calls(request):
    """Automatically prevent any real database calls in all tests.

    Skip this protection for integration tests when REAL_INTEGRATION_TESTS=true.
    """
    # Check if this is a real integration test that should use real services
    if os.getenv("REAL_INTEGRATION_TESTS") == "true":
        # Allow real database calls for real integration tests
        yield
        return

    # Check if test has real_integration marker
    if hasattr(request, "node") and request.node.get_closest_marker("real_integration"):
        # Skip for tests marked with @pytest.mark.real_integration
        pytest.skip(
            "Real integration test skipped - requires real services (use --real-integration flag)"
        )
        return

    # Check if test has marker to skip database protection
    if hasattr(request, "node") and request.node.get_closest_marker("integration"):
        # Skip for tests marked with @pytest.mark.integration
        pytest.skip(
            "Integration test skipped - requires real services (set REAL_INTEGRATION_TESTS=true)"
        )
        return

    with patch("supabase.create_client") as mock_create:
        # Make create_client raise an error if called without our mock
        mock_create.side_effect = Exception(
            "Real database calls are not allowed in tests!"
        )
        yield


@pytest.fixture(autouse=True, scope="session")
def reset_prometheus_registry_once():
    """Clear Prometheus metrics registry once at test session start.

    This fixture ensures a clean Prometheus registry at the start of the test session.
    Individual test isolation is handled by idempotent metric registration in the
    source modules (e.g., container_health_monitor.py uses _get_or_create_metric).

    This is more efficient than clearing between every test and works well with
    idempotent metric registration.
    """
    try:
        from prometheus_client import REGISTRY

        # Clear registry once at session start
        collectors = list(REGISTRY._collector_to_names.keys())
        for collector in collectors:
            try:
                REGISTRY.unregister(collector)
            except (KeyError, ValueError):
                # Already unregistered or default collector
                pass

        yield

        # No cleanup needed - let metrics persist for reporting

    except ImportError:
        # If prometheus_client is not installed, just skip
        yield


@pytest.fixture
def mock_database_client():
    """Mock Supabase client for testing."""
    mock_client = MagicMock()

    # Mock table operations with chaining support
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_insert = MagicMock()
    mock_update = MagicMock()
    mock_delete = MagicMock()

    # Setup method chaining for select
    mock_select.execute.return_value.data = []
    mock_select.eq.return_value = mock_select
    mock_select.neq.return_value = mock_select
    mock_select.order.return_value = mock_select
    mock_select.limit.return_value = mock_select
    mock_table.select.return_value = mock_select

    # Setup method chaining for insert
    mock_insert.execute.return_value.data = [{"id": "test-id"}]
    mock_table.insert.return_value = mock_insert

    # Setup method chaining for update
    mock_update.execute.return_value.data = [{"id": "test-id"}]
    mock_update.eq.return_value = mock_update
    mock_table.update.return_value = mock_update

    # Setup method chaining for delete
    mock_delete.execute.return_value.data = []
    mock_delete.eq.return_value = mock_delete
    mock_table.delete.return_value = mock_delete

    # Make table() return the mock table
    mock_client.table.return_value = mock_table

    # Mock auth operations
    mock_client.auth = MagicMock()
    mock_client.auth.get_user.return_value = None

    # Mock storage operations
    mock_client.storage = MagicMock()

    return mock_client


@pytest.fixture
def client(mock_database_client):
    """FastAPI test client with mocked database."""
    # Patch all the ways Supabase client can be created
    # NOTE: Use 'server.' paths (not 'src.server.') to match actual import paths
    with patch(
        "server.services.client_manager.create_client",
        return_value=mock_database_client,
    ):
        with patch(
            "server.services.credential_service.create_client",
            return_value=mock_database_client,
        ):
            with patch(
                "server.services.client_manager.get_database_client",
                return_value=mock_database_client,
            ):
                with patch("supabase.create_client", return_value=mock_database_client):
                    # Import app after patching to ensure mocks are used
                    from src.server.main import app

                    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """Alias for client fixture - provides FastAPI test client for auth testing."""
    return client


@pytest.fixture
def test_project():
    """Simple test project data."""
    return {
        "title": "Test Project",
        "description": "A test project for essential tests",
    }


@pytest.fixture
def test_task():
    """Simple test task data."""
    return {
        "title": "Test Task",
        "description": "A test task for essential tests",
        "status": "todo",
        "assignee": "User",
    }


@pytest.fixture
def test_knowledge_item():
    """Simple test knowledge item data."""
    return {
        "url": "https://example.com/test",
        "title": "Test Knowledge Item",
        "content": "This is test content for knowledge base",
        "source_id": "test-source",
    }


@pytest.fixture(scope="session")
def test_timeouts() -> dict[str, int]:
    """
    Load configurable test timeout values from environment variables.

    Returns dict with timeout values in milliseconds for various test scenarios.
    Defaults can be overridden via environment variables or .env.test file.

    Usage in tests:
        def test_something(test_timeouts):
            timeout = test_timeouts["cold_cache"]
            assert duration_ms < timeout

    Environment variables (all in milliseconds):
        - COLD_CACHE_TIMEOUT_MS: Cold cache performance (default: 9000)
        - WARM_CACHE_TIMEOUT_MS: Warm cache performance (default: 1000)
        - PARALLEL_QUERY_TIMEOUT_MS: Parallel queries (default: 5000)
        - RETRY_TIMEOUT_MS: Retry logic tests (default: 15000)
        - CONNECTION_POOL_TIMEOUT_MS: Connection pooling (default: 5000)
        - FULL_BENCHMARK_TIMEOUT_MS: Full benchmark suite (default: 30000)
        - CACHE_GET_TIMEOUT_MS: Cache get operations (default: 1000)
        - CACHE_SET_TIMEOUT_MS: Cache set operations (default: 1000)
        - CACHE_CLEAR_TIMEOUT_MS: Cache clear operations (default: 5000)
        - LARGE_RESULT_TIMEOUT_MS: Large result caching (default: 10000)
        - CONCURRENT_WRITE_TIMEOUT_MS: Concurrent writes (default: 5000)
        - CACHE_EVICTION_TIMEOUT_MS: Cache eviction tests (default: 10000)
        - NETWORK_PARTITION_TIMEOUT_MS: Network partition (default: 5000)
    """
    return {
        # Core performance timeouts
        "cold_cache": int(os.getenv("COLD_CACHE_TIMEOUT_MS", "9000")),
        "warm_cache": int(os.getenv("WARM_CACHE_TIMEOUT_MS", "1000")),
        "parallel_query": int(os.getenv("PARALLEL_QUERY_TIMEOUT_MS", "5000")),
        "retry": int(os.getenv("RETRY_TIMEOUT_MS", "15000")),
        "connection_pool": int(os.getenv("CONNECTION_POOL_TIMEOUT_MS", "5000")),
        "full_benchmark": int(os.getenv("FULL_BENCHMARK_TIMEOUT_MS", "30000")),
        # Cache operation timeouts
        "cache_get": int(os.getenv("CACHE_GET_TIMEOUT_MS", "1000")),
        "cache_set": int(os.getenv("CACHE_SET_TIMEOUT_MS", "1000")),
        "cache_clear": int(os.getenv("CACHE_CLEAR_TIMEOUT_MS", "5000")),
        # Edge case test timeouts
        "large_result": int(os.getenv("LARGE_RESULT_TIMEOUT_MS", "10000")),
        "concurrent_write": int(os.getenv("CONCURRENT_WRITE_TIMEOUT_MS", "5000")),
        "cache_eviction": int(os.getenv("CACHE_EVICTION_TIMEOUT_MS", "10000")),
        "network_partition": int(os.getenv("NETWORK_PARTITION_TIMEOUT_MS", "5000")),
    }


# Fixtures for Supabase fallback and Consul integration tests


@pytest.fixture
def mock_consul_client():
    """Mock Consul client for testing."""
    mock_client = MagicMock()

    # Mock agent API
    mock_client.agent = MagicMock()
    mock_client.agent.service = MagicMock()
    mock_client.agent.service.register = MagicMock()
    mock_client.agent.service.deregister = MagicMock()

    # Mock health API
    mock_client.health = MagicMock()
    mock_client.health.service = MagicMock(return_value=(0, []))

    return mock_client


@pytest.fixture
def mock_credential_service():
    """Mock CredentialService for testing."""
    from src.server.services.credential_service import CredentialService

    service = CredentialService()

    # Mock database client to return empty results
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.execute.return_value.data = []

    with patch.object(service, "_get_database_client", return_value=mock_db):
        yield service


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for event testing."""
    from unittest.mock import AsyncMock

    mock_producer = AsyncMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    return mock_producer


@pytest.fixture
def mock_kafka_consumer():
    """Mock Kafka consumer for event testing."""
    from unittest.mock import AsyncMock

    mock_consumer = AsyncMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.__aiter__ = AsyncMock(return_value=iter([]))

    return mock_consumer


@pytest.fixture
def test_env_credentials():
    """Test environment credentials for fallback testing."""
    return {
        "OPENAI_API_KEY": "test-openai-key",
        "LLM_PROVIDER": "openai",
        "MODEL_CHOICE": "gpt-4",
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "HOST": "0.0.0.0",
        "PORT": "8181",
        "CONSUL_HOST": "192.168.86.200",
        "CONSUL_PORT": "8500",
        "KAFKA_BOOTSTRAP_SERVERS": KAFKA_HOST_SERVERS,  # Use centralized config
    }
