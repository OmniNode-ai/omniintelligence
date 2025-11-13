"""
Unit Tests for TreeStampingPublisher

Tests publisher methods for tree stamping event publishing.

Created: 2025-10-24
Purpose: Test event publishing with correlation ID tracking
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from kafka.tree_stamping_publisher import TreeStampingPublisher


@pytest.fixture
def mock_kafka_publisher():
    """Mock KafkaEventPublisher."""
    mock = AsyncMock()
    mock.initialize = AsyncMock()
    mock.publish = AsyncMock()
    mock.shutdown = AsyncMock()
    return mock


@pytest.fixture
def mock_kafka_config():
    """Mock Kafka configuration."""
    config = MagicMock()
    config.topics = MagicMock()
    # Set up topic names
    config.topics.tree_index_project_completed = (
        "dev.archon-intelligence.tree.index-project-completed.v1"
    )
    config.topics.tree_index_project_failed = (
        "dev.archon-intelligence.tree.index-project-failed.v1"
    )
    config.topics.tree_search_files_completed = (
        "dev.archon-intelligence.tree.search-files-completed.v1"
    )
    config.topics.tree_search_files_failed = (
        "dev.archon-intelligence.tree.search-files-failed.v1"
    )
    config.topics.tree_get_status_completed = (
        "dev.archon-intelligence.tree.get-status-completed.v1"
    )
    config.topics.tree_get_status_failed = (
        "dev.archon-intelligence.tree.get-status-failed.v1"
    )
    return config


@pytest.fixture
async def publisher(mock_kafka_publisher, mock_kafka_config):
    """Create TreeStampingPublisher with mocked dependencies."""
    with patch(
        "kafka.tree_stamping_publisher.KafkaEventPublisher",
        return_value=mock_kafka_publisher,
    ):
        with patch(
            "kafka.tree_stamping_publisher.get_kafka_config",
            return_value=mock_kafka_config,
        ):
            publisher = TreeStampingPublisher()
            await publisher.initialize()
            return publisher


@pytest.mark.asyncio
async def test_publish_index_project_completed(publisher, mock_kafka_publisher):
    """Test publishing index project completed event."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())

    await publisher.publish_index_project_completed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        project_name="test-project",
        files_discovered=100,
        files_indexed=95,
        vector_indexed=95,
        graph_indexed=95,
        cache_warmed=True,
        duration_ms=5000,
        errors=["error1"],
        warnings=["warning1"],
    )

    # Verify publish was called
    mock_kafka_publisher.publish.assert_called_once()

    # Extract published event
    call_args = mock_kafka_publisher.publish.call_args
    assert call_args.kwargs["topic"] == (
        "dev.archon-intelligence.tree.index-project-completed.v1"
    )
    assert call_args.kwargs["key"] == correlation_id

    event = call_args.kwargs["event"]
    assert event["correlation_id"] == correlation_id
    assert event["causation_id"] == causation_id
    assert (
        event["event_type"] == "dev.archon-intelligence.tree.index-project-completed.v1"
    )
    assert event["payload"]["project_name"] == "test-project"
    assert event["payload"]["files_discovered"] == 100
    assert event["payload"]["files_indexed"] == 95
    assert event["payload"]["vector_indexed"] == 95
    assert event["payload"]["graph_indexed"] == 95
    assert event["payload"]["cache_warmed"] is True
    assert event["payload"]["duration_ms"] == 5000
    assert event["payload"]["errors"] == ["error1"]
    assert event["payload"]["warnings"] == ["warning1"]


@pytest.mark.asyncio
async def test_publish_index_project_failed(publisher, mock_kafka_publisher):
    """Test publishing index project failed event."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())

    await publisher.publish_index_project_failed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        project_name="test-project",
        error_code="TREE_DISCOVERY_FAILED",
        error_message="OnexTree service unavailable",
        duration_ms=2000,
        retry_recommended=True,
        retry_after_seconds=60,
    )

    # Verify publish was called
    mock_kafka_publisher.publish.assert_called_once()

    # Extract published event
    call_args = mock_kafka_publisher.publish.call_args
    assert call_args.kwargs["topic"] == (
        "dev.archon-intelligence.tree.index-project-failed.v1"
    )
    assert call_args.kwargs["key"] == correlation_id

    event = call_args.kwargs["event"]
    assert event["correlation_id"] == correlation_id
    assert event["causation_id"] == causation_id
    assert event["event_type"] == "dev.archon-intelligence.tree.index-project-failed.v1"
    assert event["payload"]["project_name"] == "test-project"
    assert event["payload"]["error_code"] == "TREE_DISCOVERY_FAILED"
    assert event["payload"]["error_message"] == "OnexTree service unavailable"
    assert event["payload"]["duration_ms"] == 2000
    assert event["payload"]["retry_recommended"] is True
    assert event["payload"]["retry_after_seconds"] == 60


@pytest.mark.asyncio
async def test_publish_search_files_completed(publisher, mock_kafka_publisher):
    """Test publishing search files completed event."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())

    results = [
        {"file_path": "/path/to/file1.py", "score": 0.95},
        {"file_path": "/path/to/file2.py", "score": 0.85},
    ]

    await publisher.publish_search_files_completed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        query="authentication",
        results=results,
        total_results=2,
        duration_ms=150,
    )

    # Verify publish was called
    mock_kafka_publisher.publish.assert_called_once()

    # Extract published event
    call_args = mock_kafka_publisher.publish.call_args
    assert call_args.kwargs["topic"] == (
        "dev.archon-intelligence.tree.search-files-completed.v1"
    )
    assert call_args.kwargs["key"] == correlation_id

    event = call_args.kwargs["event"]
    assert event["correlation_id"] == correlation_id
    assert event["causation_id"] == causation_id
    assert (
        event["event_type"] == "dev.archon-intelligence.tree.search-files-completed.v1"
    )
    assert event["payload"]["query"] == "authentication"
    assert event["payload"]["results"] == results
    assert event["payload"]["total_results"] == 2
    assert event["payload"]["duration_ms"] == 150


@pytest.mark.asyncio
async def test_publish_search_files_failed(publisher, mock_kafka_publisher):
    """Test publishing search files failed event."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())

    await publisher.publish_search_files_failed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        query="test query",
        error_code="INDEX_NOT_FOUND",
        error_message="Project not indexed",
        duration_ms=50,
    )

    # Verify publish was called
    mock_kafka_publisher.publish.assert_called_once()

    # Extract published event
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]
    assert event["correlation_id"] == correlation_id
    assert event["payload"]["error_code"] == "INDEX_NOT_FOUND"
    assert event["payload"]["error_message"] == "Project not indexed"


@pytest.mark.asyncio
async def test_publish_get_status_completed(publisher, mock_kafka_publisher):
    """Test publishing get status completed event."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())
    last_indexed = datetime.now(timezone.utc).isoformat()

    await publisher.publish_get_status_completed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        project_name="test-project",
        is_indexed=True,
        last_indexed_at=last_indexed,
        file_count=100,
        index_health="healthy",
        duration_ms=100,
    )

    # Verify publish was called
    mock_kafka_publisher.publish.assert_called_once()

    # Extract published event
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]
    assert event["correlation_id"] == correlation_id
    assert event["payload"]["project_name"] == "test-project"
    assert event["payload"]["is_indexed"] is True
    assert event["payload"]["last_indexed_at"] == last_indexed
    assert event["payload"]["file_count"] == 100
    assert event["payload"]["index_health"] == "healthy"


@pytest.mark.asyncio
async def test_publish_get_status_failed(publisher, mock_kafka_publisher):
    """Test publishing get status failed event."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())

    await publisher.publish_get_status_failed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        project_name="test-project",
        error_code="SERVICE_UNAVAILABLE",
        error_message="Qdrant service unavailable",
        duration_ms=1000,
    )

    # Verify publish was called
    mock_kafka_publisher.publish.assert_called_once()

    # Extract published event
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]
    assert event["correlation_id"] == correlation_id
    assert event["payload"]["error_code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_correlation_id_propagation(publisher, mock_kafka_publisher):
    """Test correlation ID is propagated through all events."""
    correlation_id = str(uuid4())
    causation_id = str(uuid4())

    # Test with index completed
    await publisher.publish_index_project_completed(
        correlation_id=correlation_id,
        causation_id=causation_id,
        project_name="test",
        files_discovered=10,
        files_indexed=10,
        vector_indexed=10,
        graph_indexed=10,
        cache_warmed=True,
        duration_ms=1000,
    )

    # Verify correlation_id is in event and used as key
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]
    key = call_args.kwargs["key"]

    assert event["correlation_id"] == correlation_id
    assert event["causation_id"] == causation_id
    assert key == correlation_id


@pytest.mark.asyncio
async def test_event_envelope_structure(publisher, mock_kafka_publisher):
    """Test event envelope has all required fields."""
    correlation_id = str(uuid4())

    await publisher.publish_index_project_completed(
        correlation_id=correlation_id,
        causation_id=None,
        project_name="test",
        files_discovered=10,
        files_indexed=10,
        vector_indexed=10,
        graph_indexed=10,
        cache_warmed=True,
        duration_ms=1000,
    )

    # Extract event
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]

    # Verify envelope structure
    assert "event_id" in event
    assert "event_type" in event
    assert "correlation_id" in event
    assert "timestamp" in event
    assert "source" in event
    assert "payload" in event

    # Verify source metadata
    assert event["source"]["service"] == "archon-intelligence"
    assert "instance_id" in event["source"]

    # Verify timestamp format (ISO 8601)
    datetime.fromisoformat(event["timestamp"])


@pytest.mark.asyncio
async def test_causation_id_optional(publisher, mock_kafka_publisher):
    """Test causation_id is optional and omitted if None."""
    correlation_id = str(uuid4())

    await publisher.publish_index_project_completed(
        correlation_id=correlation_id,
        causation_id=None,  # No causation_id
        project_name="test",
        files_discovered=10,
        files_indexed=10,
        vector_indexed=10,
        graph_indexed=10,
        cache_warmed=True,
        duration_ms=1000,
    )

    # Extract event
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]

    # Verify causation_id is present when provided
    assert "causation_id" not in event or event.get("causation_id") is None


@pytest.mark.asyncio
async def test_shutdown(publisher, mock_kafka_publisher):
    """Test publisher shutdown."""
    await publisher.shutdown()

    # Verify kafka publisher shutdown was called
    mock_kafka_publisher.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_default_error_lists(publisher, mock_kafka_publisher):
    """Test default empty lists for errors and warnings."""
    correlation_id = str(uuid4())

    # Don't provide errors/warnings
    await publisher.publish_index_project_completed(
        correlation_id=correlation_id,
        causation_id=None,
        project_name="test",
        files_discovered=10,
        files_indexed=10,
        vector_indexed=10,
        graph_indexed=10,
        cache_warmed=True,
        duration_ms=1000,
    )

    # Extract event
    call_args = mock_kafka_publisher.publish.call_args
    event = call_args.kwargs["event"]

    # Verify default empty lists
    assert event["payload"]["errors"] == []
    assert event["payload"]["warnings"] == []
