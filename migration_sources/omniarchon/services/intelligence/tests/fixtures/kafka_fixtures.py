"""
Kafka Test Fixtures for Tree Stamping Integration Tests

Provides mock Kafka infrastructure for testing event-driven adapter:
- Mock producers with event tracking
- Mock consumers with correlation ID tracking
- Topic management helpers
- Event verification utilities

Created: 2025-10-24
Purpose: Stream E - Testing Infrastructure
"""

import asyncio
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ==============================================================================
# Mock Event Envelope
# ==============================================================================


class MockEventEnvelope:
    """Mock event envelope for testing without real Kafka."""

    def __init__(
        self,
        event_id: Optional[str] = None,
        event_type: str = "tree.index-project-requested",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        source_service: str = "test-service",
    ):
        self.event_id = event_id or str(uuid4())
        self.event_type = event_type
        self.correlation_id = correlation_id or str(uuid4())
        self.causation_id = causation_id
        self.payload = payload or {}
        self.timestamp = timestamp or datetime.now(UTC)
        self.source_service = source_service

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_service": self.source_service,
        }


# ==============================================================================
# Mock Kafka Producer
# ==============================================================================


class MockKafkaProducer:
    """
    Mock Kafka producer that tracks published events.

    Features:
    - Event tracking by correlation ID
    - Topic tracking
    - Error simulation
    - Metrics tracking
    """

    def __init__(self):
        self.published_events: List[Dict[str, Any]] = []
        self.published_by_correlation: Dict[str, List[Dict[str, Any]]] = {}
        self.published_by_topic: Dict[str, List[Dict[str, Any]]] = {}
        self.metrics = {
            "total_published": 0,
            "publish_errors": 0,
        }
        self._should_fail = False
        self._failure_message = "Mock publish failure"
        self.initialized = False

    async def initialize(self) -> None:
        """
        Initialize the Kafka producer (mock implementation).

        This method matches the real KafkaEventPublisher API for testing.
        Marks the producer as initialized and returns None.
        """
        self.initialized = True

    async def publish(
        self,
        topic: str,
        event: Any,
        key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Publish event to mock Kafka."""
        if self._should_fail:
            self.metrics["publish_errors"] += 1
            raise Exception(self._failure_message)

        # Convert event to dict
        if hasattr(event, "to_dict"):
            # MockEventEnvelope has to_dict()
            event_dict = event.to_dict()
        elif hasattr(event, "model_dump"):
            # Pydantic v2 models (ModelEventEnvelope, etc.)
            event_dict = event.model_dump()
        elif hasattr(event, "dict"):
            # Pydantic v1 models
            event_dict = event.dict()
        elif isinstance(event, dict):
            # Already a dict
            event_dict = event
        else:
            # Fallback: try to use event as-is
            event_dict = event

        # Extract correlation_id safely
        if correlation_id:
            corr_id = correlation_id
        elif isinstance(event_dict, dict):
            corr_id = event_dict.get("correlation_id")
        elif hasattr(event_dict, "correlation_id"):
            corr_id = getattr(event_dict, "correlation_id", None)
        else:
            corr_id = None

        # Normalize correlation_id to string for consistent tracking
        if corr_id is not None:
            corr_id = str(corr_id)

        # Track event
        published_event = {
            "topic": topic,
            "event": event_dict,
            "key": key,
            "correlation_id": corr_id,
            "timestamp": datetime.now(UTC),
        }

        self.published_events.append(published_event)
        self.metrics["total_published"] += 1

        # Track by correlation ID
        if corr_id:
            if corr_id not in self.published_by_correlation:
                self.published_by_correlation[corr_id] = []
            self.published_by_correlation[corr_id].append(published_event)

        # Track by topic
        if topic not in self.published_by_topic:
            self.published_by_topic[topic] = []
        self.published_by_topic[topic].append(published_event)

    def simulate_failure(self, should_fail: bool = True, message: str = None):
        """Simulate publish failures for error testing."""
        self._should_fail = should_fail
        if message:
            self._failure_message = message

    def get_events_for_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get all events published with a specific correlation ID."""
        return self.published_by_correlation.get(correlation_id, [])

    def get_events_for_topic(self, topic: str) -> List[Dict[str, Any]]:
        """Get all events published to a specific topic."""
        return self.published_by_topic.get(topic, [])

    def reset(self):
        """Reset all tracked events and metrics."""
        self.published_events.clear()
        self.published_by_correlation.clear()
        self.published_by_topic.clear()
        self.metrics = {
            "total_published": 0,
            "publish_errors": 0,
        }
        self._should_fail = False
        self.initialized = False


# ==============================================================================
# Mock Kafka Consumer
# ==============================================================================


class MockKafkaConsumer:
    """
    Mock Kafka consumer for testing event consumption.

    Features:
    - Simulates event delivery
    - Tracks consumed events
    - Supports correlation ID filtering
    - Simulates consumer errors
    """

    def __init__(self, topics: List[str] = None):
        self.topics = topics or []
        self.consumed_events: List[Dict[str, Any]] = []
        self.handlers: List[Any] = []
        self._pending_events: asyncio.Queue = asyncio.Queue()
        self._should_fail = False
        self._failure_message = "Mock consume failure"

    async def subscribe(self, topics: List[str]):
        """Subscribe to topics."""
        self.topics.extend(topics)

    async def consume(self) -> Optional[Any]:
        """Consume next event from queue."""
        if self._should_fail:
            raise Exception(self._failure_message)

        try:
            event = await asyncio.wait_for(self._pending_events.get(), timeout=0.1)
            self.consumed_events.append(event)
            return event
        except asyncio.TimeoutError:
            return None

    async def inject_event(self, event: Any):
        """Inject an event for testing (simulates Kafka delivery)."""
        await self._pending_events.put(event)

    def simulate_failure(self, should_fail: bool = True, message: str = None):
        """Simulate consume failures for error testing."""
        self._should_fail = should_fail
        if message:
            self._failure_message = message

    def register_handler(self, handler: Any):
        """Register an event handler."""
        self.handlers.append(handler)

    def reset(self):
        """Reset consumer state."""
        self.consumed_events.clear()
        self.handlers.clear()
        self._pending_events = asyncio.Queue()
        self._should_fail = False


# ==============================================================================
# Pytest Fixtures
# ==============================================================================


@pytest.fixture
def mock_kafka_producer():
    """Create a mock Kafka producer."""
    return MockKafkaProducer()


@pytest.fixture
def mock_kafka_consumer():
    """Create a mock Kafka consumer."""
    return MockKafkaConsumer()


@pytest.fixture
def sample_index_project_request():
    """Sample index project request event."""
    return MockEventEnvelope(
        event_type="tree.index-project-requested",
        payload={
            "project_path": "/tmp/test-project",
            "project_name": "test-project",
            "include_tests": True,
            "force_reindex": False,
        },
    )


@pytest.fixture
def sample_search_files_request():
    """Sample search files request event."""
    return MockEventEnvelope(
        event_type="tree.search-files-requested",
        payload={
            "query": "authentication module",
            "projects": ["test-project"],
            "file_types": [".py"],
            "min_quality_score": 0.7,
            "limit": 10,
        },
    )


@pytest.fixture
def sample_get_status_request():
    """Sample get status request event."""
    return MockEventEnvelope(
        event_type="tree.get-status-requested",
        payload={
            "project_name": "test-project",
        },
    )


@pytest.fixture
def mock_bridge_success_result():
    """Mock successful TreeStampingBridge result."""
    from models.file_location import ProjectIndexResult

    return ProjectIndexResult(
        success=True,
        project_name="test-project",
        files_discovered=100,
        files_indexed=98,
        vector_indexed=98,
        graph_indexed=98,
        cache_warmed=True,
        duration_ms=5000,
        errors=[],
        warnings=["2 files failed intelligence generation"],
    )


@pytest.fixture
def mock_bridge_failure_result():
    """Mock failed TreeStampingBridge result."""
    from models.file_location import ProjectIndexResult

    return ProjectIndexResult(
        success=False,
        project_name="test-project",
        files_discovered=0,
        files_indexed=0,
        vector_indexed=0,
        graph_indexed=0,
        cache_warmed=False,
        duration_ms=100,
        errors=["OnexTree service unavailable"],
        warnings=[],
    )


@pytest.fixture
def correlation_tracker():
    """
    Correlation ID tracker for end-to-end event flow testing.

    Tracks request → response event chains.
    """

    class CorrelationTracker:
        def __init__(self):
            self.requests: Dict[str, Dict[str, Any]] = {}
            self.responses: Dict[str, List[Dict[str, Any]]] = {}

        def track_request(self, correlation_id: str, event: Dict[str, Any]):
            """Track a request event."""
            self.requests[correlation_id] = {
                "event": event,
                "timestamp": datetime.now(UTC),
            }

        def track_response(self, correlation_id: str, event: Dict[str, Any]):
            """Track a response event."""
            if correlation_id not in self.responses:
                self.responses[correlation_id] = []
            self.responses[correlation_id].append(
                {
                    "event": event,
                    "timestamp": datetime.now(UTC),
                }
            )

        def get_request(self, correlation_id: str) -> Optional[Dict[str, Any]]:
            """Get request for correlation ID."""
            return self.requests.get(correlation_id)

        def get_responses(self, correlation_id: str) -> List[Dict[str, Any]]:
            """Get all responses for correlation ID."""
            return self.responses.get(correlation_id, [])

        def has_response(self, correlation_id: str) -> bool:
            """Check if response exists for correlation ID."""
            return (
                correlation_id in self.responses
                and len(self.responses[correlation_id]) > 0
            )

        def verify_flow(self, correlation_id: str) -> bool:
            """Verify complete request → response flow."""
            has_request = correlation_id in self.requests
            has_response = self.has_response(correlation_id)
            return has_request and has_response

    return CorrelationTracker()


@pytest.fixture
def event_factory():
    """
    Factory for creating test events.

    Simplifies test event creation with sensible defaults.
    """

    class EventFactory:
        @staticmethod
        def create_index_request(
            project_path: str = "/tmp/test-project",
            project_name: str = "test-project",
            include_tests: bool = True,
            force_reindex: bool = False,
            correlation_id: Optional[str] = None,
        ) -> MockEventEnvelope:
            """Create index project request event."""
            return MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=correlation_id,
                payload={
                    "project_path": project_path,
                    "project_name": project_name,
                    "include_tests": include_tests,
                    "force_reindex": force_reindex,
                },
            )

        @staticmethod
        def create_search_request(
            query: str = "authentication",
            projects: Optional[List[str]] = None,
            correlation_id: Optional[str] = None,
        ) -> MockEventEnvelope:
            """Create search files request event."""
            return MockEventEnvelope(
                event_type="tree.search-files-requested",
                correlation_id=correlation_id,
                payload={
                    "query": query,
                    "projects": projects or ["test-project"],
                    "file_types": [".py"],
                    "min_quality_score": 0.7,
                    "limit": 10,
                },
            )

        @staticmethod
        def create_status_request(
            project_name: str = "test-project",
            correlation_id: Optional[str] = None,
        ) -> MockEventEnvelope:
            """Create get status request event."""
            return MockEventEnvelope(
                event_type="tree.get-status-requested",
                correlation_id=correlation_id,
                payload={
                    "project_name": project_name,
                },
            )

    return EventFactory()


__all__ = [
    "MockEventEnvelope",
    "MockKafkaProducer",
    "MockKafkaConsumer",
    "mock_kafka_producer",
    "mock_kafka_consumer",
    "sample_index_project_request",
    "sample_search_files_request",
    "sample_get_status_request",
    "mock_bridge_success_result",
    "mock_bridge_failure_result",
    "correlation_tracker",
    "event_factory",
]
