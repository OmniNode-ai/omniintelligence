"""
Pytest configuration and fixtures for omniintelligence tests.

Shared test fixtures for all tests including intelligence nodes and pattern extraction.
"""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# =========================================================================
# Core Pytest Configuration
# =========================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =========================================================================
# Basic Sample Data Fixtures
# =========================================================================


@pytest.fixture
def correlation_id() -> str:
    """Provide a valid UUID test correlation ID for distributed tracing."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def sample_code() -> str:
    """Sample code for testing."""
    return """
def calculate_fibonacci(n: int) -> int:
    \"\"\"Calculate nth Fibonacci number.\"\"\"
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)
"""


@pytest.fixture
def sample_code_snippet() -> str:
    """Provide a sample code snippet for analysis tests."""
    return '''
def calculate_sum(numbers: list[int]) -> int:
    """Calculate the sum of a list of numbers."""
    return sum(numbers)
'''


@pytest.fixture
def sample_metadata() -> dict[str, str]:
    """Sample metadata for testing."""
    return {
        "file_path": "src/utils/math.py",
        "language": "python",
        "project_name": "test_project",
        "author": "test_user",
    }


@pytest.fixture
def sample_pattern_context() -> dict[str, str]:
    """Provide sample context for pattern extraction tests."""
    return {
        "file_path": "/test/example.py",
        "language": "python",
        "framework": "none",
    }


# =========================================================================
# Mock Container Fixtures
# =========================================================================


@pytest.fixture
def mock_onex_container():
    """Create a mock ONEX container for testing."""
    try:
        from omnibase_core.models.container.model_onex_container import (
            ModelONEXContainer,
        )
        return ModelONEXContainer()
    except ImportError:
        # Fallback to mock if omnibase_core not available
        container = MagicMock()
        container.correlation_id = str(uuid4())
        return container


# =========================================================================
# Mock Intelligence Service Fixtures
# =========================================================================


@pytest.fixture
def mock_intelligence_client():
    """Create a mock intelligence service client."""
    client = AsyncMock()
    client.check_health = AsyncMock(
        return_value=MagicMock(
            status="healthy",
            service_version="1.0.0",
            uptime_seconds=12345,
        )
    )
    client.get_metrics = MagicMock(
        return_value={
            "total_requests": 100,
            "successful_requests": 95,
            "failed_requests": 5,
            "circuit_breaker_state": "closed",
        }
    )
    client.close = AsyncMock()
    client.connect = AsyncMock()
    return client


@pytest.fixture
def mock_quality_response():
    """Create a mock quality assessment response."""
    response = MagicMock()
    response.quality_score = 0.85
    response.onex_compliance = MagicMock(
        score=0.80,
        violations=[],
        recommendations=["Add type hints"],
    )
    response.maintainability = MagicMock(complexity_score=0.75)
    response.architectural_era = "advanced_archon"
    response.temporal_relevance = 0.90
    response.architectural_compliance = None
    return response


# =========================================================================
# Mock Kafka/Event Fixtures
# =========================================================================


@pytest.fixture
def mock_kafka_consumer():
    """Create a mock Kafka consumer for testing event-driven components."""
    consumer = AsyncMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer.getmany = AsyncMock(return_value={})
    return consumer


@pytest.fixture
def mock_kafka_producer():
    """Create a mock Kafka producer for testing event publishing."""
    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send_and_wait = AsyncMock()
    return producer


# =========================================================================
# Sample Intelligence Input Fixtures
# =========================================================================


@pytest.fixture
def sample_intelligence_input_dict() -> dict[str, Any]:
    """Provide a sample intelligence input dictionary."""
    return {
        "operation_type": "assess_code_quality",
        "content": "def hello(): pass",
        "source_path": "test.py",
        "language": "python",
        "options": {"include_recommendations": True},
    }


@pytest.fixture
def sample_execution_trace() -> str:
    """Provide a sample execution trace for pattern extraction tests."""
    return json.dumps({
        "events": [
            {
                "type": "function_call",
                "function": "analyze_code",
                "duration_ms": 15.3,
            },
            {
                "type": "function_call",
                "function": "generate_output",
                "duration_ms": 25.2,
            },
            {
                "type": "status",
                "status": "completed",
                "duration_ms": 5.1,
            },
        ]
    })
