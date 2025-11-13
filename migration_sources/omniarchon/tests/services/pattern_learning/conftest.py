"""
Pytest Configuration and Fixtures for Pattern Learning Tests
AI-Generated Test Infrastructure with agent-testing methodology
Coverage Target: 95%+
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Generator, List
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from asyncpg import Connection, Pool, create_pool
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

# Test database configuration
TEST_DB_CONFIG = {
    "host": os.getenv("TEST_POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("TEST_POSTGRES_PORT", "5455")),
    "database": os.getenv("TEST_POSTGRES_DB", "intelligence_test_db"),
    "user": os.getenv("TEST_POSTGRES_USER", "intelligence_user"),
    "password": os.getenv("TEST_POSTGRES_PASSWORD", ""),
}

# Test Qdrant configuration
TEST_QDRANT_CONFIG = {
    "url": os.getenv("TEST_QDRANT_URL", "http://localhost:6333"),
    "collection_name": "test_patterns",
    "vector_size": 1536,  # OpenAI ada-002 embedding size
}


# ==========================================
# Event Loop Configuration
# ==========================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==========================================
# Database Fixtures
# ==========================================


@pytest_asyncio.fixture(scope="session")
async def db_pool() -> AsyncGenerator[Pool, None]:
    """Create PostgreSQL connection pool for testing."""
    pool = await create_pool(**TEST_DB_CONFIG, min_size=2, max_size=10)

    # Initialize test schema
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    yield pool

    await pool.close()


@pytest_asyncio.fixture
async def db_conn(db_pool: Pool) -> AsyncGenerator[Connection, None]:
    """Get database connection for a test."""
    async with db_pool.acquire() as conn:
        # Start transaction
        tr = conn.transaction()
        await tr.start()

        yield conn

        # Rollback transaction to maintain test isolation
        await tr.rollback()


@pytest_asyncio.fixture
async def clean_database(db_conn: Connection) -> None:
    """Clean all pattern-related tables before test."""
    tables = [
        "pattern_usage_log",
        "success_patterns",
        "error_patterns",
        "agent_chaining_patterns",
    ]

    for table in tables:
        await db_conn.execute(f"TRUNCATE TABLE {table} CASCADE;")


# ==========================================
# Qdrant Fixtures
# ==========================================


@pytest_asyncio.fixture(scope="session")
async def qdrant_client() -> AsyncGenerator[AsyncQdrantClient, None]:
    """Create Qdrant client for testing."""
    client = AsyncQdrantClient(url=TEST_QDRANT_CONFIG["url"])

    # Create test collection
    try:
        await client.create_collection(
            collection_name=TEST_QDRANT_CONFIG["collection_name"],
            vectors_config=VectorParams(
                size=TEST_QDRANT_CONFIG["vector_size"],
                distance=Distance.COSINE,
            ),
        )
    except Exception:
        # Collection already exists
        pass

    yield client

    await client.close()


@pytest_asyncio.fixture
async def clean_qdrant(qdrant_client: AsyncQdrantClient) -> None:
    """Clean Qdrant collection before test."""
    collection_name = TEST_QDRANT_CONFIG["collection_name"]

    # Delete and recreate collection for clean state
    try:
        await qdrant_client.delete_collection(collection_name=collection_name)
    except Exception:
        pass

    await qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=TEST_QDRANT_CONFIG["vector_size"],
            distance=Distance.COSINE,
        ),
    )


# ==========================================
# Pattern Test Fixtures
# ==========================================


@pytest.fixture
def sample_pattern() -> Dict[str, Any]:
    """Generate a sample success pattern for testing."""
    return {
        "pattern_id": str(uuid.uuid4()),
        "pattern_type": "agent_sequence",
        "intent_keywords": ["authentication", "JWT", "user login"],
        "execution_sequence": [
            {
                "agent": "agent-api-architect",
                "tool": "create_endpoint",
                "parameters": {"endpoint": "/auth/login", "method": "POST"},
            },
            {
                "agent": "agent-security-audit",
                "tool": "validate_security",
                "parameters": {"check_type": "input_validation"},
            },
        ],
        "success_criteria": {
            "status_code": 200,
            "execution_time_ms": 150,
            "error_count": 0,
        },
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "success_count": 5,
            "total_attempts": 5,
            "confidence_score": 0.95,
        },
    }


@pytest.fixture
def sample_patterns_batch() -> List[Dict[str, Any]]:
    """Generate 10 sample patterns for batch testing."""
    patterns = []

    pattern_types = [
        "agent_sequence",
        "tool_chain",
        "error_recovery",
        "optimization",
    ]

    for i in range(10):
        patterns.append(
            {
                "pattern_id": str(uuid.uuid4()),
                "pattern_type": pattern_types[i % len(pattern_types)],
                "intent_keywords": [f"keyword_{i}", f"feature_{i}"],
                "execution_sequence": [
                    {
                        "agent": f"agent-test-{i}",
                        "tool": f"tool_{i}",
                        "parameters": {"index": i},
                    }
                ],
                "success_criteria": {
                    "status_code": 200,
                    "execution_time_ms": 100 + i * 10,
                    "error_count": 0,
                },
                "metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "success_count": i + 1,
                    "total_attempts": i + 2,
                    "confidence_score": 0.8 + (i * 0.01),
                },
            }
        )

    return patterns


@pytest.fixture
def sample_embedding() -> List[float]:
    """Generate a sample embedding vector."""
    import random

    random.seed(42)
    return [random.random() for _ in range(TEST_QDRANT_CONFIG["vector_size"])]


@pytest.fixture
def sample_embeddings_batch(sample_patterns_batch) -> List[List[float]]:
    """Generate embeddings for batch of patterns."""
    import random

    random.seed(42)

    return [
        [random.random() for _ in range(TEST_QDRANT_CONFIG["vector_size"])]
        for _ in range(len(sample_patterns_batch))
    ]


# ==========================================
# Mock Fixtures
# ==========================================


@pytest.fixture
def mock_openai_client() -> MagicMock:
    """Mock OpenAI client for embedding generation."""
    client = MagicMock()

    # Mock embeddings.create response
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
    client.embeddings.create.return_value = mock_response

    return client


@pytest.fixture
def mock_correlation_id() -> str:
    """Generate mock correlation ID for tracing."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_execution_trace() -> Dict[str, Any]:
    """Generate mock execution trace data."""
    correlation_id = str(uuid.uuid4())

    return {
        "correlation_id": correlation_id,
        "execution_id": str(uuid.uuid4()),
        "parent_id": None,
        "root_id": correlation_id,
        "event_type": "agent_execution",
        "event_data": {
            "agent": "agent-test",
            "tool": "test_tool",
            "status": "success",
        },
        "execution_time_ms": 150,
        "timestamp": datetime.now(timezone.utc),
    }


# ==========================================
# Performance Benchmark Fixtures
# ==========================================


@pytest.fixture
def performance_timer():
    """Utility for timing test operations."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()

        @property
        def elapsed_ms(self) -> float:
            if self.start_time is None or self.end_time is None:
                raise ValueError("Timer not properly started/stopped")
            return (self.end_time - self.start_time) * 1000

    return Timer()


@pytest.fixture
def benchmark_config() -> Dict[str, Any]:
    """Configuration for performance benchmarks."""
    return {
        "pattern_lookup_max_ms": 100,
        "pattern_storage_max_ms": 200,
        "batch_index_max_ms": 500,
        "vector_search_max_ms": 100,
        "e2e_flow_max_ms": 1000,
    }


# ==========================================
# Edge Case Fixtures
# ==========================================


@pytest.fixture
def malformed_patterns() -> List[Dict[str, Any]]:
    """Generate malformed patterns for edge case testing."""
    return [
        {},  # Empty pattern
        {"pattern_id": "invalid-uuid"},  # Invalid UUID
        {"pattern_type": None},  # Null type
        {"intent_keywords": "not_a_list"},  # Invalid keywords type
        {"execution_sequence": []},  # Empty sequence
        {"success_criteria": "invalid"},  # Invalid criteria
        {
            "pattern_id": str(uuid.uuid4()),
            # Missing required fields
        },
        {
            "pattern_id": str(uuid.uuid4()),
            "pattern_type": "unknown_type",  # Invalid type value
            "intent_keywords": ["test"],
            "execution_sequence": "invalid",  # Wrong type
        },
    ]


@pytest.fixture
def connection_failure_scenarios() -> List[Dict[str, str]]:
    """Connection failure scenarios for testing."""
    return [
        {"type": "database_timeout", "message": "Connection timeout"},
        {"type": "database_connection_refused", "message": "Connection refused"},
        {"type": "qdrant_timeout", "message": "Qdrant timeout"},
        {"type": "qdrant_connection_refused", "message": "Qdrant connection refused"},
        {"type": "database_query_error", "message": "Query execution error"},
        {"type": "qdrant_insert_error", "message": "Vector insert error"},
    ]


# ==========================================
# Integration Test Fixtures
# ==========================================


@pytest_asyncio.fixture
async def integration_environment(
    db_pool: Pool,
    qdrant_client: AsyncQdrantClient,
    clean_database,
    clean_qdrant,
) -> Dict[str, Any]:
    """Set up complete integration testing environment."""
    return {
        "db_pool": db_pool,
        "qdrant_client": qdrant_client,
        "collection_name": TEST_QDRANT_CONFIG["collection_name"],
        "vector_size": TEST_QDRANT_CONFIG["vector_size"],
    }


# ==========================================
# Utility Functions
# ==========================================


def assert_pattern_valid(pattern: Dict[str, Any]) -> None:
    """Assert that a pattern has all required fields."""
    required_fields = [
        "pattern_id",
        "pattern_type",
        "intent_keywords",
        "execution_sequence",
        "success_criteria",
        "metadata",
    ]

    for field in required_fields:
        assert field in pattern, f"Pattern missing required field: {field}"

    # Validate types
    assert isinstance(pattern["pattern_id"], str)
    assert isinstance(pattern["pattern_type"], str)
    assert isinstance(pattern["intent_keywords"], list)
    assert isinstance(pattern["execution_sequence"], list)
    assert isinstance(pattern["success_criteria"], dict)
    assert isinstance(pattern["metadata"], dict)


def assert_performance_within_threshold(
    elapsed_ms: float, max_ms: float, operation: str
) -> None:
    """Assert that operation completed within performance threshold."""
    assert (
        elapsed_ms <= max_ms
    ), f"{operation} took {elapsed_ms:.2f}ms, exceeds threshold of {max_ms}ms"
