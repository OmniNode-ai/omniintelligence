#!/usr/bin/env python3
"""
Shared fixtures for integration tests.

Provides common fixtures used across all handler integration tests
to reduce code duplication and maintain consistency.

Author: Archon Intelligence Team
Date: 2025-10-15
Updated: 2025-10-16 (Phase 5 Enhancement)
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

# ============================================================================
# Event & Router Fixtures
# ============================================================================


@pytest.fixture
def mock_event_envelope():
    """
    Create mock event envelope for testing.

    Returns a class that can be instantiated with correlation_id, payload, and optionally event_type.
    Used to simulate Kafka event envelopes in integration tests.

    Example:
        envelope = mock_event_envelope(correlation_id="123", payload={"key": "value"}, event_type="HEALTH_REQUESTED")
        assert envelope.correlation_id == "123"
        assert envelope.payload["key"] == "value"
        assert envelope.event_type == "HEALTH_REQUESTED"
    """

    class MockEventEnvelope:
        def __init__(
            self, correlation_id: str, payload: Dict[str, Any], event_type: str = ""
        ):
            self.correlation_id = correlation_id
            self.payload = payload
            self.event_type = event_type

        def get(self, key: str, default=None):
            """Support dict-like access for compatibility."""
            return getattr(self, key, default)

    return MockEventEnvelope


@pytest.fixture
def mock_router():
    """
    Mock HybridEventRouter for testing.

    Returns an AsyncMock with all router methods mocked:
    - initialize() - Router initialization
    - publish() - Event publishing
    - shutdown() - Router cleanup

    Example:
        handler._router = mock_router
        await handler.handle_event(event)
        mock_router.publish.assert_called_once()
    """
    router = AsyncMock()
    router.initialize = AsyncMock()
    router.publish = AsyncMock()
    router.shutdown = AsyncMock()
    return router


# ============================================================================
# FastAPI Test Client Fixture
# ============================================================================


@pytest.fixture(scope="function")
async def test_client():
    """
    Async FastAPI test client for integration tests.

    Returns an AsyncClient instance configured with the intelligence service app.
    Function-scoped to ensure proper async context management and lifespan events.

    This fixture properly triggers FastAPI lifespan events, which initializes:
    - Database connection pools (for intelligence metrics API)
    - Memgraph adapter
    - Background services (freshness monitor, etc.)

    Example:
        response = await test_client.get("/health")
        assert response.status_code == 200
    """
    # Lazy import to avoid circular dependencies
    from httpx import ASGITransport, AsyncClient

    try:
        from app import app

        # Create async client with ASGI transport
        # Using async context manager properly triggers lifespan events
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            timeout=30.0,  # Increase timeout for tests that initialize services
        ) as client:
            yield client
    except ImportError:
        pytest.skip("FastAPI app not available for integration tests")


@pytest.fixture(scope="function")
async def client(test_client):
    """
    Alias for test_client fixture for backward compatibility.

    Many tests use 'client' as the fixture name, so this provides
    the same AsyncClient instance but with a different name.

    Example:
        response = await client.get("/health")
        assert response.status_code == 200
    """
    return test_client


@pytest.fixture(scope="session")
def sync_test_client():
    """
    Synchronous FastAPI test client for legacy integration tests.

    Returns a TestClient instance configured with the intelligence service app.
    Session-scoped to reuse across all tests for better performance.

    Use this for tests that don't need async/await syntax.

    Example:
        response = sync_test_client.get("/health")
        assert response.status_code == 200
    """
    # Lazy import to avoid circular dependencies
    from fastapi.testclient import TestClient

    try:
        from app import app

        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI app not available for integration tests")


@pytest.fixture(scope="function")
def test_client_with_lifespan():
    """
    Synchronous FastAPI test client with lifespan event support.

    Returns a TestClient instance that properly triggers FastAPI lifespan events,
    ensuring services like freshness_monitor are initialized. Function-scoped
    to ensure proper initialization for each test.

    This fixture patches FreshnessDatabase and DocumentFreshnessMonitor to avoid
    requiring PostgreSQL during tests. The mocks provide realistic test responses
    for all freshness API endpoints.

    Use this for tests that require lifespan-dependent services (e.g., freshness API).

    Example:
        def test_freshness(test_client_with_lifespan):
            response = test_client_with_lifespan.get("/freshness/stats")
            assert response.status_code == 200
    """
    # Lazy import to avoid circular dependencies
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi.testclient import TestClient

    try:
        from app import app
        from freshness.models import (
            DocumentFreshness,
            FreshnessAnalysis,
            FreshnessLevel,
            FreshnessScore,
        )

        # Create mock instances
        mock_monitor_instance = MagicMock()
        mock_database_instance = MagicMock()

        # Configure mock analyze_document method
        async def mock_analyze_document(file_path, **kwargs):
            import hashlib

            from freshness.models import DocumentClassification, DocumentType

            # Generate consistent document_id from path
            doc_id = hashlib.md5(file_path.encode()).hexdigest()

            return DocumentFreshness(
                document_id=doc_id,
                file_path=file_path,
                file_size_bytes=1024,
                last_modified=datetime.now(timezone.utc),
                classification=DocumentClassification(
                    document_type=DocumentType.GUIDE, confidence=0.9
                ),
                freshness_score=FreshnessScore(
                    overall_score=0.85,
                    time_decay_score=0.9,
                    dependency_score=0.8,
                    content_relevance_score=0.85,
                    usage_frequency_score=0.85,
                ),
                freshness_level=FreshnessLevel.FRESH,
                dependencies=[],
                broken_dependencies_count=0,
            )

        # Configure mock analyze_directory method
        async def mock_analyze_directory(directory_path, **kwargs):
            return FreshnessAnalysis(
                analysis_id=f"test_analysis_{int(datetime.now(timezone.utc).timestamp())}",
                base_path=directory_path,
                total_documents=5,
                analyzed_documents=5,
                skipped_documents=0,
                documents=[],
                average_freshness_score=0.85,
                stale_documents_count=1,
                critical_documents_count=0,
            )

        mock_monitor_instance.analyze_document = AsyncMock(
            side_effect=mock_analyze_document
        )
        mock_monitor_instance.analyze_directory = AsyncMock(
            side_effect=mock_analyze_directory
        )

        # Configure database mock methods
        mock_database_instance.initialize = AsyncMock()
        mock_database_instance.store_analysis = AsyncMock(return_value=True)
        mock_database_instance.get_stale_documents = AsyncMock(return_value=[])
        mock_database_instance.get_freshness_stats = AsyncMock(
            return_value={
                "total_documents": 100,
                "fresh_count": 80,
                "stale_count": 15,
                "outdated_count": 4,
                "critical_count": 1,
                "average_age_days": 15.5,
                "average_freshness_score": 0.82,
            }
        )
        mock_database_instance.get_recent_analyses = AsyncMock(return_value=[])
        mock_database_instance.get_document_by_path = AsyncMock(return_value=None)
        mock_database_instance.cleanup_old_data = AsyncMock(return_value=10)

        # Patch the classes at the point where app.py imports them
        # This ensures the lifespan event creates our mocks instead of real instances
        with (
            patch("app.FreshnessDatabase", return_value=mock_database_instance),
            patch("app.DocumentFreshnessMonitor", return_value=mock_monitor_instance),
            patch("app.DataRefreshWorker", return_value=MagicMock()),
            patch("app.FreshnessEventCoordinator", return_value=MagicMock()),
        ):

            with TestClient(app) as client:
                yield client

    except ImportError:
        pytest.skip("FastAPI app not available for integration tests")


# ============================================================================
# Pattern Learning Fixtures
# ============================================================================


@pytest.fixture
def sample_patterns() -> List[Dict[str, Any]]:
    """
    Sample pattern data for testing (100 patterns).

    Returns list of pattern dicts with:
    - pattern_id: Unique pattern identifier
    - pattern_type: Type of pattern (code_generation, debugging, etc.)
    - context: Pattern context metadata
    - execution_trace: Execution details
    - success: Whether pattern execution succeeded

    Example:
        patterns = sample_patterns
        assert len(patterns) == 100
        assert patterns[0]["pattern_id"] == "pattern_000"
    """
    return [
        {
            "pattern_id": f"pattern_{i:03d}",
            "pattern_type": "code_generation" if i % 2 == 0 else "debugging",
            "context": {
                "language": "python" if i % 3 == 0 else "typescript",
                "complexity": "high" if i % 5 == 0 else "medium",
            },
            "execution_trace": f"trace_data_{i}",
            "success": i % 2 == 0,
            "confidence_score": 0.5 + (i * 0.005),  # Range 0.5-0.995
        }
        for i in range(100)
    ]


@pytest.fixture
def sample_pattern_single() -> Dict[str, Any]:
    """
    Single sample pattern for focused testing.

    Example:
        pattern = sample_pattern_single
        result = await service.analyze_pattern(pattern)
    """
    return {
        "pattern_id": "test_pattern_001",
        "pattern_type": "code_generation",
        "context": {"language": "python", "complexity": "medium"},
        "execution_trace": "test_trace_data",
        "success": True,
        "confidence_score": 0.85,
        "metadata": {"created_at": datetime.now(timezone.utc).isoformat()},
    }


# ============================================================================
# Quality Intelligence Fixtures
# ============================================================================


@pytest.fixture
def quality_history_fixture() -> List[Dict[str, Any]]:
    """
    Sample quality history data (30 days of improving trend).

    Returns list of quality snapshots with:
    - timestamp: When measurement was taken
    - quality_score: Overall quality score (0.7 to 0.76)
    - project_id: Project identifier

    Example:
        history = quality_history_fixture
        assert len(history) == 30
        assert history[0]["quality_score"] > history[-1]["quality_score"]  # Improving
    """
    return [
        {
            "timestamp": datetime.now(timezone.utc) - timedelta(days=i),
            "quality_score": 0.7 + (i * 0.002),  # Improving trend
            "compliance_score": 0.75 + (i * 0.0015),
            "project_id": "test_project",
            "file_path": f"src/test_{i}.py",
            "violations": max(0, 10 - i),  # Decreasing violations
        }
        for i in range(30)
    ]


@pytest.fixture
def quality_snapshot_fixture() -> Dict[str, Any]:
    """
    Single quality snapshot for focused testing.

    Example:
        snapshot = quality_snapshot_fixture
        result = await service.validate_quality(snapshot)
    """
    return {
        "timestamp": datetime.now(timezone.utc),
        "project_id": "test_project",
        "file_path": "src/test.py",
        "quality_score": 0.85,
        "compliance_score": 0.90,
        "violations": [],
        "warnings": ["Missing docstring"],
        "correlation_id": str(uuid.uuid4()),
    }


# ============================================================================
# Performance Intelligence Fixtures
# ============================================================================


@pytest.fixture
def baseline_fixture() -> Dict[str, Any]:
    """
    Performance baseline data for testing.

    Returns baseline statistics with:
    - operation_name: Operation being measured
    - measurements: Raw measurement data
    - p50, p95, p99: Percentile values
    - mean, std_dev: Statistical metrics

    Example:
        baseline = baseline_fixture
        assert baseline["p50"] == 150
        assert len(baseline["measurements"]) == 100
    """
    measurements = [100 + i for i in range(100)]
    return {
        "operation_name": "test_operation",
        "measurements": measurements,
        "p50": 150,
        "p95": 195,
        "p99": 199,
        "mean": 149.5,
        "std_dev": 29.0,
        "sample_size": 100,
        "timestamp": datetime.now(timezone.utc),
    }


@pytest.fixture
def performance_measurements_fixture() -> List[Dict[str, Any]]:
    """
    Sample performance measurements (10 measurements).

    Example:
        measurements = performance_measurements_fixture
        avg = sum(m["duration_ms"] for m in measurements) / len(measurements)
    """
    return [
        {
            "operation": "test_operation",
            "duration_ms": 100.0 + (i * 5.0),
            "timestamp": datetime.now(timezone.utc) - timedelta(seconds=i),
            "success": True,
        }
        for i in range(10)
    ]


# ============================================================================
# Pattern Traceability Fixtures
# ============================================================================


@pytest.fixture
def pattern_lineage_fixture() -> Dict[str, Any]:
    """
    Sample pattern lineage data for traceability testing.

    Example:
        lineage = pattern_lineage_fixture
        assert lineage["pattern_id"] == "pattern_001"
        assert len(lineage["ancestors"]) == 3
    """
    return {
        "pattern_id": "pattern_001",
        "parent_pattern_id": "pattern_000",
        "ancestors": ["pattern_000", "pattern_base_1", "pattern_root"],
        "evolution_count": 3,
        "first_seen": datetime.now(timezone.utc) - timedelta(days=30),
        "last_seen": datetime.now(timezone.utc),
        "execution_count": 42,
        "success_rate": 0.88,
    }


@pytest.fixture
def execution_logs_fixture() -> List[Dict[str, Any]]:
    """
    Sample agent execution logs for traceability testing.

    Example:
        logs = execution_logs_fixture
        assert len(logs) == 10
        assert logs[0]["agent_name"] == "agent_001"
    """
    return [
        {
            "execution_id": str(uuid.uuid4()),
            "agent_name": f"agent_{i:03d}",
            "pattern_id": f"pattern_{i:03d}",
            "timestamp": datetime.now(timezone.utc) - timedelta(hours=i),
            "duration_ms": 100.0 + (i * 10.0),
            "success": i % 2 == 0,
            "error_message": None if i % 2 == 0 else f"Error {i}",
        }
        for i in range(10)
    ]


# ============================================================================
# Database & Cleanup Fixtures
# ============================================================================


@pytest.fixture(scope="function")
async def clean_database():
    """
    Clean test data after each test.

    Yields control to the test, then cleans up afterwards.
    Function-scoped to ensure isolation between tests.

    Example:
        async def test_something(clean_database):
            # Test code here
            pass
            # Database cleaned up automatically after test
    """
    # Setup: Nothing needed before test
    yield

    # Teardown: Clean up test data after test
    # Note: Actual cleanup logic should be implemented based on database structure
    # For now, this is a placeholder that can be extended
    pass


# ============================================================================
# Authentication & Headers Fixtures
# ============================================================================


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """
    Authentication headers for API integration tests.

    Returns dict with Authorization header for test authentication.

    Example:
        response = test_client.get("/api/protected", headers=auth_headers)
        assert response.status_code == 200
    """
    return {
        "Authorization": "Bearer test_token_integration",
        "Content-Type": "application/json",
    }


# ============================================================================
# Common Test Data Fixtures
# ============================================================================


@pytest.fixture
def correlation_id_fixture() -> str:
    """
    Generate unique correlation ID for testing.

    Example:
        correlation_id = correlation_id_fixture
        response = await service.process(correlation_id=correlation_id)
    """
    return str(uuid.uuid4())


@pytest.fixture
def project_id_fixture() -> str:
    """
    Test project ID fixture.

    Example:
        project_id = project_id_fixture
        response = await service.get_project(project_id)
    """
    return "test_project_integration"


# ============================================================================
# Pattern Analytics & Feedback Fixtures
# ============================================================================


@pytest.fixture
async def sample_feedback_data():
    """
    Sample feedback data for pattern analytics testing.

    Creates sample pattern feedback entries that can be used for testing
    usage stats and analytics endpoints.

    Example:
        async def test_usage_stats(test_client, sample_feedback_data):
            # sample_feedback_data is already populated
            response = await test_client.get("/api/pattern-analytics/usage-stats")
    """
    from archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
        FeedbackSentiment,
        ModelPatternFeedback,
    )

    # Create sample feedback data
    feedback_items = []
    for i in range(10):
        feedback = ModelPatternFeedback(
            pattern_id=uuid.uuid4(),
            pattern_name=f"test_pattern_{i}",
            sentiment=(
                FeedbackSentiment.POSITIVE if i % 2 == 0 else FeedbackSentiment.NEGATIVE
            ),
            success=i % 2 == 0,
            quality_score=0.7 + (i * 0.02),
            created_at=datetime.now(timezone.utc) - timedelta(hours=i),
            context={"test": True, "index": i},
        )
        feedback_items.append(feedback)

    # Return the feedback data (tests can inject into services as needed)
    return feedback_items


@pytest.fixture
def benchmark():
    """
    Benchmark fixture for performance testing.

    Provides a simple benchmark function that can be used to time operations.

    Example:
        def test_performance(benchmark):
            result = benchmark(lambda: expensive_operation())
            assert result < 1.0  # Assert operation takes less than 1 second
    """

    class SimpleBenchmark:
        def __call__(self, func, *args, **kwargs):
            """Call the function and return elapsed time in seconds."""
            import time

            start = time.time()
            func(*args, **kwargs)
            elapsed = time.time() - start
            return elapsed

    return SimpleBenchmark()


@pytest.fixture
async def pattern_analytics_service():
    """
    Pattern analytics service for testing.

    Creates a mock pattern analytics service with feedback store.

    Example:
        async def test_analytics(pattern_analytics_service):
            service = pattern_analytics_service
            result = await service.get_usage_stats()
    """
    from unittest.mock import AsyncMock

    class MockPatternAnalyticsService:
        def __init__(self):
            self.orchestrator = AsyncMock()
            self.orchestrator.feedback_store = []

        async def get_usage_stats(self, *args, **kwargs):
            """Mock get_usage_stats method."""
            return {
                "total_patterns": len(self.orchestrator.feedback_store),
                "patterns": [],
                "time_range": kwargs.get("time_range", "7d"),
                "granularity": kwargs.get("group_by", "day"),
            }

    return MockPatternAnalyticsService()
