"""
Comprehensive unit tests for EventPublisher.

Tests cover:
- Successful event publishing with mock Kafka producer
- Event serialization and JSON encoding
- Correlation ID propagation
- Error handling and retry logic with exponential backoff
- Circuit breaker behavior
- Dead Letter Queue (DLQ) routing
- Secret sanitization in event payloads
- Metrics tracking
- Factory functions

All tests use mocked Kafka producer - NO real Kafka connection.
"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch, call
from uuid import UUID, uuid4

import pytest

from omniintelligence.events.publisher.event_publisher import (
    EventPublisher,
    create_event_publisher,
)
from omniintelligence.models import (
    ModelEventEnvelope,
    ModelEventMetadata,
    ModelEventSource,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_producer():
    """
    Create a mock confluent_kafka.Producer.

    This simulates the synchronous Kafka producer behavior with delivery callbacks.
    """
    producer = MagicMock()

    # Default: successful produce with callback invocation
    def successful_produce(topic, value, key=None, callback=None):
        # Simulate async delivery callback
        if callback:
            # Create mock message
            mock_msg = MagicMock()
            mock_msg.topic.return_value = topic
            mock_msg.partition.return_value = 0
            mock_msg.offset.return_value = 100
            # Call callback with no error
            callback(None, mock_msg)

    producer.produce.side_effect = successful_produce
    producer.poll.return_value = 0
    producer.flush.return_value = 0

    return producer


@pytest.fixture
def mock_producer_with_failure():
    """
    Create a mock producer that fails on first N attempts then succeeds.

    Used for testing retry logic with exponential backoff.
    """
    producer = MagicMock()

    # Track call count
    call_count = {"count": 0, "fail_count": 2}

    def produce_with_failures(topic, value, key=None, callback=None):
        call_count["count"] += 1
        if callback:
            if call_count["count"] <= call_count["fail_count"]:
                # Fail with error
                callback(Exception("Kafka broker unavailable"), None)
            else:
                # Succeed
                mock_msg = MagicMock()
                mock_msg.topic.return_value = topic
                callback(None, mock_msg)

    producer.produce.side_effect = produce_with_failures
    producer.poll.return_value = 0
    producer.flush.return_value = 0

    return producer, call_count


@pytest.fixture
def mock_producer_permanent_failure():
    """
    Create a mock producer that always fails.

    Used for testing DLQ routing and circuit breaker.
    """
    producer = MagicMock()

    def always_fail(topic, value, key=None, callback=None):
        if callback:
            callback(Exception("Permanent failure"), None)

    producer.produce.side_effect = always_fail
    producer.poll.return_value = 0
    producer.flush.return_value = 0

    return producer


@pytest.fixture
def publisher(mock_producer):
    """Create an EventPublisher with mocked Kafka producer."""
    with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
        MockProducer.return_value = mock_producer
        pub = EventPublisher(
            bootstrap_servers="localhost:9092",
            service_name="test-service",
            instance_id="test-instance-001",
            hostname="test-host",
            max_retries=3,
            retry_backoff_ms=10,  # Short backoff for tests
            circuit_breaker_threshold=5,
            circuit_breaker_timeout_s=60,
            enable_dlq=True,
            enable_sanitization=True,
        )
        # Replace the producer with our mock
        pub.producer = mock_producer
        yield pub


@pytest.fixture
def publisher_no_dlq(mock_producer):
    """Create an EventPublisher with DLQ disabled."""
    with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
        MockProducer.return_value = mock_producer
        pub = EventPublisher(
            bootstrap_servers="localhost:9092",
            service_name="test-service",
            instance_id="test-instance-001",
            enable_dlq=False,
        )
        pub.producer = mock_producer
        yield pub


@pytest.fixture
def publisher_no_sanitization(mock_producer):
    """Create an EventPublisher with sanitization disabled."""
    with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
        MockProducer.return_value = mock_producer
        pub = EventPublisher(
            bootstrap_servers="localhost:9092",
            service_name="test-service",
            instance_id="test-instance-001",
            enable_sanitization=False,
        )
        pub.producer = mock_producer
        yield pub


@pytest.fixture
def sample_payload():
    """Sample event payload for testing."""
    return {
        "code_content": "def hello(): pass",
        "language": "python",
        "file_path": "src/test.py",
    }


@pytest.fixture
def sample_correlation_id():
    """Sample correlation ID for testing."""
    return UUID("550e8400-e29b-41d4-a716-446655440000")


# ============================================================================
# Test: Initialization
# ============================================================================


class TestEventPublisherInitialization:
    """Tests for EventPublisher initialization."""

    def test_initialization_with_defaults(self):
        """Test publisher initializes with default configuration."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer"):
            publisher = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
            )

            assert publisher.bootstrap_servers == "localhost:9092"
            assert publisher.service_name == "test-service"
            assert publisher.instance_id == "test-001"
            assert publisher.max_retries == 3
            assert publisher.retry_backoff_ms == 1000
            assert publisher.circuit_breaker_threshold == 5
            assert publisher.circuit_breaker_timeout_s == 60
            assert publisher.enable_dlq is True
            assert publisher.enable_sanitization is True

    def test_initialization_with_custom_config(self):
        """Test publisher initializes with custom configuration."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer"):
            publisher = EventPublisher(
                bootstrap_servers="kafka.example.com:29092",
                service_name="custom-service",
                instance_id="custom-001",
                hostname="custom-host",
                max_retries=5,
                retry_backoff_ms=500,
                circuit_breaker_threshold=10,
                circuit_breaker_timeout_s=120,
                enable_dlq=False,
                enable_sanitization=False,
            )

            assert publisher.bootstrap_servers == "kafka.example.com:29092"
            assert publisher.hostname == "custom-host"
            assert publisher.max_retries == 5
            assert publisher.retry_backoff_ms == 500
            assert publisher.circuit_breaker_threshold == 10
            assert publisher.circuit_breaker_timeout_s == 120
            assert publisher.enable_dlq is False
            assert publisher.enable_sanitization is False

    def test_metrics_initialized_to_zero(self):
        """Test metrics are initialized to zero."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer"):
            publisher = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
            )

            assert publisher.metrics["events_published"] == 0
            assert publisher.metrics["events_failed"] == 0
            assert publisher.metrics["events_sent_to_dlq"] == 0
            assert publisher.metrics["total_publish_time_ms"] == 0.0
            assert publisher.metrics["circuit_breaker_opens"] == 0
            assert publisher.metrics["retries_attempted"] == 0


# ============================================================================
# Test: Successful Publishing
# ============================================================================


class TestSuccessfulPublishing:
    """Tests for successful event publishing."""

    @pytest.mark.asyncio
    async def test_publish_success(self, publisher, mock_producer, sample_payload, sample_correlation_id):
        """Test successful event publishing."""
        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=sample_correlation_id,
        )

        assert result is True
        assert mock_producer.produce.called
        assert publisher.metrics["events_published"] == 1
        assert publisher.metrics["events_failed"] == 0

    @pytest.mark.asyncio
    async def test_publish_with_explicit_correlation_id(self, publisher, mock_producer, sample_payload):
        """Test publishing with explicit correlation ID."""
        correlation_id = uuid4()
        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=correlation_id,
        )

        assert result is True
        # Verify produce was called
        produce_call = mock_producer.produce.call_args
        assert produce_call is not None

        # Parse the serialized event to verify correlation_id exists and matches
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))
        assert "correlation_id" in event_data
        assert event_data["correlation_id"] == str(correlation_id)

    @pytest.mark.asyncio
    async def test_publish_with_custom_topic(self, publisher, mock_producer, sample_payload):
        """Test publishing to custom topic override."""
        custom_topic = "custom.topic.name"

        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=uuid4(),
            topic=custom_topic,
        )

        assert result is True
        # Verify produce was called with custom topic
        produce_call = mock_producer.produce.call_args
        topic = produce_call.kwargs.get("topic") or produce_call.args[0]
        assert topic == custom_topic

    @pytest.mark.asyncio
    async def test_publish_with_partition_key(self, publisher, mock_producer, sample_payload):
        """Test publishing with partition key for ordering."""
        partition_key = "user-123"

        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=uuid4(),
            partition_key=partition_key,
        )

        assert result is True
        produce_call = mock_producer.produce.call_args
        key = produce_call.kwargs.get("key")
        assert key == partition_key.encode()

    @pytest.mark.asyncio
    async def test_publish_with_causation_id(self, publisher, mock_producer, sample_payload, sample_correlation_id):
        """Test publishing with causation ID for event sourcing."""
        causation_id = uuid4()

        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=sample_correlation_id,
            causation_id=causation_id,
        )

        assert result is True
        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))
        assert event_data["causation_id"] == str(causation_id)

    @pytest.mark.asyncio
    async def test_publish_with_metadata(self, publisher, mock_producer, sample_payload):
        """Test publishing with custom metadata."""
        metadata = ModelEventMetadata(
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            span_id="00f067aa0ba902b7",
            user_id="user-456",
            tenant_id="tenant-acme",
        )

        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=uuid4(),
            metadata=metadata,
        )

        assert result is True
        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))
        assert event_data["metadata"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert event_data["metadata"]["user_id"] == "user-456"

    @pytest.mark.asyncio
    async def test_publish_updates_metrics(self, publisher, mock_producer, sample_payload):
        """Test that publishing updates metrics correctly."""
        # Publish multiple events
        for _ in range(3):
            await publisher.publish(
                event_type="omninode.test.event.created.v1",
                payload=sample_payload,
                correlation_id=uuid4(),
            )

        assert publisher.metrics["events_published"] == 3
        assert publisher.metrics["events_failed"] == 0
        assert publisher.metrics["total_publish_time_ms"] > 0


# ============================================================================
# Test: Event Serialization
# ============================================================================


class TestEventSerialization:
    """Tests for event serialization and encoding."""

    @pytest.mark.asyncio
    async def test_event_envelope_structure(self, publisher, mock_producer, sample_payload, sample_correlation_id):
        """Test serialized event has correct envelope structure."""
        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=sample_correlation_id,
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))

        # Verify envelope structure
        assert "event_id" in event_data
        assert "event_type" in event_data
        assert "correlation_id" in event_data
        assert "timestamp" in event_data
        assert "version" in event_data
        assert "source" in event_data
        assert "payload" in event_data

        # Verify source metadata
        assert event_data["source"]["service"] == "test-service"
        assert event_data["source"]["instance_id"] == "test-instance-001"
        assert event_data["source"]["hostname"] == "test-host"

        # Verify payload
        assert event_data["payload"] == sample_payload

    @pytest.mark.asyncio
    async def test_uuid_serialization(self, publisher, mock_producer, sample_payload, sample_correlation_id):
        """Test UUIDs are serialized as strings."""
        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=sample_correlation_id,
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))

        # UUIDs should be strings
        assert isinstance(event_data["event_id"], str)
        assert isinstance(event_data["correlation_id"], str)

        # Verify correlation_id matches input
        assert event_data["correlation_id"] == str(sample_correlation_id)

    @pytest.mark.asyncio
    async def test_payload_with_pydantic_model(self, publisher, mock_producer):
        """Test payload serialization with Pydantic model."""
        from pydantic import BaseModel

        class TestPayload(BaseModel):
            name: str
            value: int

        payload = TestPayload(name="test", value=42)

        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=payload,
            correlation_id=uuid4(),
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))

        assert event_data["payload"]["name"] == "test"
        assert event_data["payload"]["value"] == 42


# ============================================================================
# Test: Secret Sanitization
# ============================================================================


class TestSecretSanitization:
    """Tests for secret sanitization in event payloads."""

    @pytest.mark.asyncio
    async def test_sanitizes_openai_api_key(self, publisher, mock_producer):
        """Test OpenAI API keys are sanitized from payloads."""
        payload = {
            "config": {
                "api_key": "sk-abcdefghijklmnopqrstuvwxyz123456789012"
            }
        }

        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=payload,
            correlation_id=uuid4(),
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_str = event_bytes.decode("utf-8")

        # Should NOT contain the original API key
        assert "sk-abcdefghijklmnopqrstuvwxyz123456789012" not in event_str
        # Should contain sanitized placeholder
        assert "[OPENAI_API_KEY]" in event_str

    @pytest.mark.asyncio
    async def test_sanitizes_github_token(self, publisher, mock_producer):
        """Test GitHub tokens are sanitized from payloads."""
        payload = {
            "token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        }

        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=payload,
            correlation_id=uuid4(),
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_str = event_bytes.decode("utf-8")

        assert "ghp_abcdefghijklmnopqrstuvwxyz1234567890" not in event_str
        assert "[GITHUB_TOKEN]" in event_str

    @pytest.mark.asyncio
    async def test_sanitizes_jwt_token(self, publisher, mock_producer):
        """Test JWT tokens are sanitized from payloads."""
        # Simple mock JWT (header.payload.signature format)
        # Using a field name that won't match auth_token pattern
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        payload = {"jwt_value": jwt}

        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=payload,
            correlation_id=uuid4(),
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_str = event_bytes.decode("utf-8")

        assert jwt not in event_str
        assert "[JWT_TOKEN]" in event_str

    @pytest.mark.asyncio
    async def test_sanitization_disabled(self, publisher_no_sanitization, mock_producer):
        """Test sanitization can be disabled."""
        payload = {
            "api_key": "sk-abcdefghijklmnopqrstuvwxyz123456789012"
        }

        await publisher_no_sanitization.publish(
            event_type="omninode.test.event.created.v1",
            payload=payload,
            correlation_id=uuid4(),
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_str = event_bytes.decode("utf-8")

        # With sanitization disabled, the key should remain
        assert "sk-abcdefghijklmnopqrstuvwxyz123456789012" in event_str


# ============================================================================
# Test: Retry Logic
# ============================================================================


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self, mock_producer_with_failure):
        """Test retries on transient failures then succeeds."""
        producer, call_count = mock_producer_with_failure

        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = producer
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=3,
                retry_backoff_ms=1,  # Very short for test
            )
            pub.producer = producer

            result = await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            assert result is True
            # Should have attempted 3 times (2 failures + 1 success)
            assert call_count["count"] == 3
            assert pub.metrics["retries_attempted"] == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_producer_permanent_failure):
        """Test behavior when max retries exceeded."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer_permanent_failure
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=2,
                retry_backoff_ms=1,
                enable_dlq=False,  # Disable DLQ for this test
            )
            pub.producer = mock_producer_permanent_failure

            result = await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            assert result is False
            assert pub.metrics["events_failed"] == 1
            # Should have attempted max_retries + 1 times
            assert mock_producer_permanent_failure.produce.call_count >= 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Test exponential backoff increases delay correctly."""
        producer = MagicMock()
        attempts = []

        def track_produce(topic, value, key=None, callback=None):
            attempts.append(time.perf_counter())
            if callback:
                if len(attempts) < 3:
                    callback(Exception("Failure"), None)
                else:
                    callback(None, MagicMock())

        producer.produce.side_effect = track_produce
        producer.poll.return_value = 0

        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = producer
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=3,
                retry_backoff_ms=50,  # 50ms base backoff
            )
            pub.producer = producer

            await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            # Verify delays increase exponentially
            # First retry: 50ms, second retry: 100ms
            if len(attempts) >= 3:
                delay1 = (attempts[1] - attempts[0]) * 1000  # ms
                delay2 = (attempts[2] - attempts[1]) * 1000  # ms
                # Allow some tolerance for async execution
                assert delay1 >= 40  # ~50ms expected
                assert delay2 >= 80  # ~100ms expected (2x first)


# ============================================================================
# Test: Dead Letter Queue (DLQ)
# ============================================================================


class TestDeadLetterQueue:
    """Tests for Dead Letter Queue routing."""

    @pytest.mark.asyncio
    async def test_dlq_routing_on_failure(self, mock_producer_permanent_failure):
        """Test failed events are sent to DLQ."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer_permanent_failure
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=1,
                retry_backoff_ms=1,
                enable_dlq=True,
            )
            pub.producer = mock_producer_permanent_failure

            result = await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            assert result is False
            assert pub.metrics["events_sent_to_dlq"] == 1

            # Verify DLQ produce was called with .dlq suffix
            produce_calls = mock_producer_permanent_failure.produce.call_args_list
            dlq_calls = [c for c in produce_calls if ".dlq" in str(c)]
            assert len(dlq_calls) >= 1

    @pytest.mark.asyncio
    async def test_dlq_payload_structure(self, mock_producer_permanent_failure):
        """Test DLQ payload contains error metadata."""
        dlq_payloads = []

        original_produce = mock_producer_permanent_failure.produce.side_effect

        def capture_dlq(topic, value, key=None, callback=None):
            if ".dlq" in topic:
                dlq_payloads.append(json.loads(value.decode("utf-8")))
            else:
                # For non-DLQ topics, fail
                if callback:
                    callback(Exception("Failure"), None)

        mock_producer_permanent_failure.produce.side_effect = capture_dlq

        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer_permanent_failure
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=1,
                retry_backoff_ms=1,
                enable_dlq=True,
            )
            pub.producer = mock_producer_permanent_failure

            await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            # Verify DLQ payload structure
            assert len(dlq_payloads) == 1
            dlq_data = dlq_payloads[0]

            assert "original_topic" in dlq_data
            assert "original_envelope" in dlq_data
            assert "error_message" in dlq_data
            assert "error_timestamp" in dlq_data
            assert "service" in dlq_data
            assert "instance_id" in dlq_data
            assert "retry_count" in dlq_data

            assert dlq_data["service"] == "test-service"
            assert dlq_data["error_message"] == "Failed after max retries"

    @pytest.mark.asyncio
    async def test_dlq_disabled(self, mock_producer_permanent_failure):
        """Test DLQ routing disabled when enable_dlq=False."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer_permanent_failure
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=1,
                retry_backoff_ms=1,
                enable_dlq=False,
            )
            pub.producer = mock_producer_permanent_failure

            await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            assert pub.metrics["events_sent_to_dlq"] == 0


# ============================================================================
# Test: Circuit Breaker
# ============================================================================


class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_threshold(self, mock_producer_permanent_failure):
        """Test circuit breaker opens after threshold failures."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer_permanent_failure
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=0,  # No retries for faster test
                circuit_breaker_threshold=3,
                enable_dlq=False,
            )
            pub.producer = mock_producer_permanent_failure

            # Cause failures to open circuit breaker
            for _ in range(3):
                await pub.publish(
                    event_type="omninode.test.event.created.v1",
                    payload={"test": "data"},
                    correlation_id=uuid4(),
                )

            assert pub._circuit_breaker_open is True
            assert pub.metrics["circuit_breaker_opens"] == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_requests(self, mock_producer_permanent_failure):
        """Test circuit breaker rejects requests when open."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer_permanent_failure
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=0,
                circuit_breaker_threshold=2,
                enable_dlq=False,
            )
            pub.producer = mock_producer_permanent_failure

            # Cause failures to open circuit breaker
            for _ in range(2):
                await pub.publish(
                    event_type="omninode.test.event.created.v1",
                    payload={"test": "data"},
                    correlation_id=uuid4(),
                )

            # Next request should raise RuntimeError
            with pytest.raises(RuntimeError, match="Circuit breaker is open"):
                await pub.publish(
                    event_type="omninode.test.event.created.v1",
                    payload={"test": "data"},
                    correlation_id=uuid4(),
                )

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(self, publisher, mock_producer, sample_payload):
        """Test circuit breaker resets after successful publish."""
        # Manually set some failures
        publisher._circuit_breaker_failures = 3

        # Successful publish should reset
        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=sample_payload,
            correlation_id=uuid4(),
        )

        assert publisher._circuit_breaker_failures == 0
        assert publisher._circuit_breaker_open is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_timeout_reset(self):
        """Test circuit breaker resets after timeout."""
        producer = MagicMock()

        call_count = {"count": 0}

        def produce_behavior(topic, value, key=None, callback=None):
            call_count["count"] += 1
            if callback:
                if call_count["count"] <= 2:
                    callback(Exception("Failure"), None)
                else:
                    callback(None, MagicMock())

        producer.produce.side_effect = produce_behavior
        producer.poll.return_value = 0
        producer.flush.return_value = 0

        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = producer
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
                max_retries=0,
                circuit_breaker_threshold=2,
                circuit_breaker_timeout_s=0.1,  # 100ms timeout for test
                enable_dlq=False,
            )
            pub.producer = producer

            # Cause failures to open circuit
            await pub.publish("omninode.test.event.created.v1", {"test": 1}, correlation_id=uuid4())
            await pub.publish("omninode.test.event.created.v1", {"test": 2}, correlation_id=uuid4())

            assert pub._circuit_breaker_open is True

            # Wait for timeout
            await asyncio.sleep(0.15)

            # Should allow request after timeout (circuit half-open)
            result = await pub.publish("omninode.test.event.created.v1", {"test": 3}, correlation_id=uuid4())

            # This should succeed and close the circuit
            assert result is True
            assert pub._circuit_breaker_open is False


# ============================================================================
# Test: Metrics
# ============================================================================


class TestMetrics:
    """Tests for metrics tracking."""

    def test_get_metrics(self, publisher):
        """Test get_metrics returns correct structure."""
        metrics = publisher.get_metrics()

        assert "events_published" in metrics
        assert "events_failed" in metrics
        assert "events_sent_to_dlq" in metrics
        assert "total_publish_time_ms" in metrics
        assert "avg_publish_time_ms" in metrics
        assert "circuit_breaker_opens" in metrics
        assert "retries_attempted" in metrics
        assert "circuit_breaker_status" in metrics
        assert "current_failures" in metrics
        assert "total_events" in metrics

    def test_avg_publish_time_calculation(self, publisher):
        """Test average publish time calculation."""
        # Simulate some published events
        publisher.metrics["events_published"] = 5
        publisher.metrics["total_publish_time_ms"] = 100.0

        metrics = publisher.get_metrics()

        assert metrics["avg_publish_time_ms"] == 20.0

    def test_avg_publish_time_zero_events(self, publisher):
        """Test average publish time with zero events."""
        metrics = publisher.get_metrics()

        assert metrics["avg_publish_time_ms"] == 0.0

    def test_circuit_breaker_status_in_metrics(self, publisher):
        """Test circuit breaker status appears in metrics."""
        # Closed by default
        metrics = publisher.get_metrics()
        assert metrics["circuit_breaker_status"] == "closed"

        # Open the circuit
        publisher._circuit_breaker_open = True
        metrics = publisher.get_metrics()
        assert metrics["circuit_breaker_status"] == "open"


# ============================================================================
# Test: Close
# ============================================================================


class TestClose:
    """Tests for publisher close/shutdown."""

    @pytest.mark.asyncio
    async def test_close_flushes_producer(self, publisher, mock_producer):
        """Test close flushes pending messages."""
        await publisher.close()

        mock_producer.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_flush_timeout(self, mock_producer):
        """Test close handles flush timeout gracefully."""
        mock_producer.flush.return_value = 5  # 5 messages remaining

        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
            )
            pub.producer = mock_producer

            # Should not raise, just log warning
            await pub.close()
            mock_producer.flush.assert_called()

    @pytest.mark.asyncio
    async def test_close_handles_flush_exception(self, mock_producer):
        """Test close handles flush exception gracefully."""
        mock_producer.flush.side_effect = Exception("Flush error")

        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = mock_producer
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
            )
            pub.producer = mock_producer

            # Should not raise
            await pub.close()


# ============================================================================
# Test: Factory Function
# ============================================================================


class TestFactoryFunction:
    """Tests for create_event_publisher factory function."""

    def test_create_event_publisher(self):
        """Test factory creates configured publisher."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer"):
            publisher = create_event_publisher(
                bootstrap_servers="kafka:9092",
                service_name="factory-test",
                instance_id="factory-001",
            )

            assert isinstance(publisher, EventPublisher)
            assert publisher.bootstrap_servers == "kafka:9092"
            assert publisher.service_name == "factory-test"
            assert publisher.instance_id == "factory-001"

    def test_create_event_publisher_with_kwargs(self):
        """Test factory passes through kwargs."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer"):
            publisher = create_event_publisher(
                bootstrap_servers="kafka:9092",
                service_name="factory-test",
                instance_id="factory-001",
                max_retries=10,
                enable_dlq=False,
            )

            assert publisher.max_retries == 10
            assert publisher.enable_dlq is False


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_publish_with_none_producer(self):
        """Test publish raises when producer is None."""
        with patch("omniintelligence.events.publisher.event_publisher.Producer") as MockProducer:
            MockProducer.return_value = None
            pub = EventPublisher(
                bootstrap_servers="localhost:9092",
                service_name="test-service",
                instance_id="test-001",
            )
            pub.producer = None

            # Should return False (handled gracefully)
            result = await pub.publish(
                event_type="omninode.test.event.created.v1",
                payload={"test": "data"},
                correlation_id=uuid4(),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_publish_with_empty_payload(self, publisher, mock_producer):
        """Test publish with empty payload."""
        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload={},
            correlation_id=uuid4(),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_with_complex_payload(self, publisher, mock_producer):
        """Test publish with complex nested payload."""
        payload = {
            "level1": {
                "level2": {
                    "level3": [1, 2, {"nested": "value"}]
                },
                "array": [{"a": 1}, {"b": 2}],
            },
            "unicode": "Hello 日本語 emoji 🎉",
            "numbers": [1, 2.5, -3, 1e10],
            "booleans": [True, False, None],
        }

        result = await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload=payload,
            correlation_id=uuid4(),
        )

        assert result is True

        # Verify payload is preserved
        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))

        assert event_data["payload"]["unicode"] == "Hello 日本語 emoji 🎉"
        assert event_data["payload"]["level1"]["level2"]["level3"][2]["nested"] == "value"

    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self, publisher, mock_producer):
        """Test correlation ID is correctly propagated through envelope."""
        correlation_id = UUID("12345678-1234-5678-1234-567812345678")

        await publisher.publish(
            event_type="omninode.test.event.created.v1",
            payload={"test": "data"},
            correlation_id=correlation_id,
        )

        produce_call = mock_producer.produce.call_args
        event_bytes = produce_call.kwargs.get("value") or produce_call.args[1]
        event_data = json.loads(event_bytes.decode("utf-8"))

        assert event_data["correlation_id"] == "12345678-1234-5678-1234-567812345678"


# ============================================================================
# Test: Event Envelope Creation (Unit)
# ============================================================================


class TestEventEnvelopeCreation:
    """Unit tests for _create_event_envelope method."""

    def test_create_event_envelope_basic(self, publisher):
        """Test basic envelope creation with correlation ID."""
        correlation_id = uuid4()
        envelope = publisher._create_event_envelope(
            event_type="omninode.test.event.created.v1",
            payload={"test": "data"},
            correlation_id=correlation_id,
        )

        assert isinstance(envelope, ModelEventEnvelope)
        assert envelope.event_type == "omninode.test.event.created.v1"
        assert envelope.payload == {"test": "data"}
        assert envelope.source.service == "test-service"
        assert envelope.source.instance_id == "test-instance-001"
        assert envelope.source.hostname == "test-host"
        assert envelope.correlation_id == correlation_id

    def test_create_event_envelope_with_explicit_correlation_id(self, publisher):
        """Test envelope creation with explicit correlation ID."""
        correlation_id = UUID("550e8400-e29b-41d4-a716-446655440000")

        envelope = publisher._create_event_envelope(
            event_type="omninode.test.event.created.v1",
            payload={"test": "data"},
            correlation_id=correlation_id,
        )

        assert envelope.correlation_id == correlation_id

    def test_create_event_envelope_with_uuid_string(self, publisher):
        """Test envelope creation with UUID (various formats)."""
        # Test with UUID object
        correlation_id = UUID("12345678-1234-5678-1234-567812345678")

        envelope = publisher._create_event_envelope(
            event_type="omninode.test.event.created.v1",
            payload={"test": "data"},
            correlation_id=correlation_id,
        )

        assert envelope.correlation_id == correlation_id
        assert isinstance(envelope.correlation_id, UUID)


# ============================================================================
# Test: Serialization (Unit)
# ============================================================================


class TestSerializationUnit:
    """Unit tests for _serialize_event method."""

    def test_serialize_event_returns_bytes(self, publisher):
        """Test serialization returns bytes."""
        envelope = publisher._create_event_envelope(
            event_type="omninode.test.event.created.v1",
            payload={"test": "data"},
            correlation_id=uuid4(),
        )

        result = publisher._serialize_event(envelope)

        assert isinstance(result, bytes)

    def test_serialize_event_valid_json(self, publisher):
        """Test serialization produces valid JSON."""
        envelope = publisher._create_event_envelope(
            event_type="omninode.test.event.created.v1",
            payload={"test": "data"},
            correlation_id=uuid4(),
        )

        result = publisher._serialize_event(envelope)

        # Should parse without error
        data = json.loads(result.decode("utf-8"))
        assert data["event_type"] == "omninode.test.event.created.v1"
        assert data["payload"] == {"test": "data"}

    def test_serialize_event_utf8_encoded(self, publisher):
        """Test serialization is UTF-8 encoded."""
        envelope = publisher._create_event_envelope(
            event_type="omninode.test.event.created.v1",
            payload={"unicode": "日本語 🎉"},
            correlation_id=uuid4(),
        )

        result = publisher._serialize_event(envelope)

        data = json.loads(result.decode("utf-8"))
        assert data["payload"]["unicode"] == "日本語 🎉"
