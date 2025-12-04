"""
Tests for Kafka Event Effect Node.

Tests cover:
- Initialization and configuration
- Event publishing with delivery confirmation
- Retry logic with exponential backoff
- Circuit breaker behavior
- Dead-letter queue routing
- Error handling
- Metrics tracking
"""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from omniintelligence.nodes.kafka_event_effect import (
    ModelKafkaEventConfig,
    ModelKafkaEventInput,
    NodeKafkaEventEffect,
)


@pytest.fixture
def mock_producer():
    """Create mock Kafka producer."""
    producer = MagicMock()
    producer.produce = MagicMock()
    producer.poll = MagicMock()
    producer.flush = MagicMock(return_value=0)
    return producer


@pytest.fixture
def kafka_config():
    """Create test Kafka configuration."""
    return ModelKafkaEventConfig(
        bootstrap_servers="localhost:9092",
        topic_prefix="test",
        enable_idempotence=True,
        acks="all",
        max_retries=2,
        retry_backoff_ms=100,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_s=5,
        enable_dlq=True,
    )


@pytest.fixture
async def kafka_effect_node(kafka_config, mock_producer):
    """Create test Kafka effect node."""
    node = NodeKafkaEventEffect(container=None, config=kafka_config)

    # Mock producer initialization
    with patch(
        "omniintelligence.nodes.kafka_event_effect.v1_0_0.effect.Producer",
        return_value=mock_producer,
    ):
        await node.initialize()

    yield node

    await node.shutdown()


class TestKafkaEventEffectInitialization:
    """Test Kafka event effect node initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, kafka_config):
        """Test successful initialization."""
        node = NodeKafkaEventEffect(container=None, config=kafka_config)

        with patch(
            "omniintelligence.nodes.kafka_event_effect.v1_0_0.effect.Producer"
        ) as mock_producer_class:
            mock_producer = MagicMock()
            mock_producer_class.return_value = mock_producer

            await node.initialize()

            assert node.producer is not None
            assert node.producer == mock_producer
            mock_producer_class.assert_called_once()

        await node.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_failure(self, kafka_config):
        """Test initialization failure."""
        node = NodeKafkaEventEffect(container=None, config=kafka_config)

        with patch(
            "omniintelligence.nodes.kafka_event_effect.v1_0_0.effect.Producer",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(
                RuntimeError, match="Kafka producer initialization failed"
            ):
                await node.initialize()

    def test_default_config(self):
        """Test default configuration values."""
        node = NodeKafkaEventEffect(container=None)

        assert node.config.bootstrap_servers == "omninode-bridge-redpanda:9092"
        assert node.config.topic_prefix == "dev.archon-intelligence"
        assert node.config.enable_idempotence is True
        assert node.config.acks == "all"
        assert node.config.max_retries == 3


class TestKafkaEventEffectPublishing:
    """Test event publishing operations."""

    @pytest.mark.asyncio
    async def test_publish_event_success(self, kafka_effect_node):
        """Test successful event publishing."""
        correlation_id = uuid4()
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87, "entity_id": "abc-123"},
            correlation_id=correlation_id,
        )

        # Mock successful delivery
        def mock_produce(topic, value, key, callback):
            # Simulate successful delivery
            msg = MagicMock()
            msg.partition.return_value = 0
            msg.offset.return_value = 42
            callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        output = await kafka_effect_node.execute_effect(input_data)

        assert output.success is True
        assert output.topic == "test.quality.assessed.v1"
        assert output.partition == 0
        assert output.offset == 42
        assert output.correlation_id == correlation_id
        assert output.error is None

    @pytest.mark.asyncio
    async def test_publish_event_with_custom_key(self, kafka_effect_node):
        """Test publishing with custom partition key."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
            key="custom-key-123",
        )

        # Mock successful delivery
        def mock_produce(topic, value, key, callback):
            assert key == b"custom-key-123"
            msg = MagicMock()
            msg.partition.return_value = 0
            msg.offset.return_value = 42
            callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        output = await kafka_effect_node.execute_effect(input_data)

        assert output.success is True

    @pytest.mark.asyncio
    async def test_publish_event_serialization(self, kafka_effect_node):
        """Test event serialization."""
        correlation_id = uuid4()
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87, "nested": {"key": "value"}},
            correlation_id=correlation_id,
        )

        # Capture serialized data
        captured_value = None

        def mock_produce(topic, value, key, callback):
            nonlocal captured_value
            captured_value = value
            msg = MagicMock()
            msg.partition.return_value = 0
            msg.offset.return_value = 42
            callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        await kafka_effect_node.execute_effect(input_data)

        # Verify serialization
        assert captured_value is not None
        envelope = json.loads(captured_value.decode("utf-8"))
        assert envelope["event_type"] == "QUALITY_ASSESSED"
        assert envelope["correlation_id"] == str(correlation_id)
        assert envelope["payload"]["quality_score"] == 0.87
        assert "event_id" in envelope
        assert "timestamp" in envelope
        assert "source" in envelope


class TestKafkaEventEffectRetry:
    """Test retry logic and error handling."""

    @pytest.mark.asyncio
    async def test_publish_with_retry_success(self, kafka_effect_node):
        """Test successful publish after retry."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Mock failure then success
        attempt = 0

        def mock_produce(topic, value, key, callback):
            nonlocal attempt
            attempt += 1

            if attempt == 1:
                # First attempt fails
                callback(Exception("Temporary failure"), None)
            else:
                # Second attempt succeeds
                msg = MagicMock()
                msg.partition.return_value = 0
                msg.offset.return_value = 42
                callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        output = await kafka_effect_node.execute_effect(input_data)

        assert output.success is True
        assert kafka_effect_node.metrics["retries_attempted"] == 1

    @pytest.mark.asyncio
    async def test_publish_max_retries_exceeded(self, kafka_effect_node):
        """Test max retries exceeded."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Mock all attempts failing
        def mock_produce(topic, value, key, callback):
            callback(Exception("Persistent failure"), None)

        kafka_effect_node.producer.produce = mock_produce

        output = await kafka_effect_node.execute_effect(input_data)

        assert output.success is False
        assert output.error is not None
        assert "Persistent failure" in output.error
        assert kafka_effect_node.metrics["events_failed"] == 1
        assert kafka_effect_node.metrics["retries_attempted"] == 2  # max_retries=2


class TestKafkaEventEffectCircuitBreaker:
    """Test circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self, kafka_effect_node):
        """Test circuit breaker opens after threshold failures."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Mock all attempts failing
        def mock_produce(topic, value, key, callback):
            callback(Exception("Failure"), None)

        kafka_effect_node.producer.produce = mock_produce

        # Trigger multiple failures (threshold = 3)
        for _ in range(3):
            output = await kafka_effect_node.execute_effect(input_data)
            assert output.success is False

        # Circuit breaker should be open
        assert kafka_effect_node._circuit_breaker_open is True
        assert kafka_effect_node.metrics["circuit_breaker_opens"] == 1

        # Next attempt should fail immediately
        with pytest.raises(RuntimeError, match="Circuit breaker is open"):
            await kafka_effect_node.execute_effect(input_data)

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(self, kafka_effect_node):
        """Test circuit breaker resets after successful publish."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Mock one failure then success
        attempt = 0

        def mock_produce(topic, value, key, callback):
            nonlocal attempt
            attempt += 1

            if attempt == 1:
                callback(Exception("Failure"), None)
            else:
                msg = MagicMock()
                msg.partition.return_value = 0
                msg.offset.return_value = 42
                callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        # First attempt fails
        kafka_effect_node._circuit_breaker_failures = 2

        # Second attempt succeeds
        output = await kafka_effect_node.execute_effect(input_data)
        assert output.success is True

        # Circuit breaker should be reset
        assert kafka_effect_node._circuit_breaker_failures == 0
        assert kafka_effect_node._circuit_breaker_open is False


class TestKafkaEventEffectDLQ:
    """Test dead-letter queue routing."""

    @pytest.mark.asyncio
    async def test_dlq_routing_on_failure(self, kafka_effect_node):
        """Test DLQ routing on max retries exceeded."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Track DLQ publish
        dlq_published = False
        dlq_topic = None

        def mock_produce(topic, value, key=None, callback=None):
            nonlocal dlq_published, dlq_topic

            if ".dlq" in topic:
                dlq_published = True
                dlq_topic = topic
            elif callback:
                callback(Exception("Failure"), None)

        kafka_effect_node.producer.produce = mock_produce

        output = await kafka_effect_node.execute_effect(input_data)

        assert output.success is False
        assert dlq_published is True
        assert dlq_topic == "test.quality.assessed.v1.dlq"
        assert kafka_effect_node.metrics["events_sent_to_dlq"] == 1


class TestKafkaEventEffectMetrics:
    """Test metrics tracking."""

    @pytest.mark.asyncio
    async def test_metrics_update_on_success(self, kafka_effect_node):
        """Test metrics update on successful publish."""
        initial_metrics = kafka_effect_node.metrics.copy()

        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Mock successful delivery
        def mock_produce(topic, value, key, callback):
            msg = MagicMock()
            msg.partition.return_value = 0
            msg.offset.return_value = 42
            callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        await kafka_effect_node.execute_effect(input_data)

        metrics = kafka_effect_node.get_metrics()
        assert metrics["events_published"] == initial_metrics["events_published"] + 1
        assert (
            metrics["total_publish_time_ms"] > initial_metrics["total_publish_time_ms"]
        )
        assert metrics["avg_publish_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_metrics_update_on_failure(self, kafka_effect_node):
        """Test metrics update on failed publish."""
        initial_metrics = kafka_effect_node.metrics.copy()

        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        # Mock failure
        def mock_produce(topic, value, key, callback):
            if ".dlq" not in topic:
                callback(Exception("Failure"), None)

        kafka_effect_node.producer.produce = mock_produce

        await kafka_effect_node.execute_effect(input_data)

        metrics = kafka_effect_node.get_metrics()
        assert metrics["events_failed"] == initial_metrics["events_failed"] + 1
        assert metrics["retries_attempted"] > initial_metrics["retries_attempted"]


class TestKafkaEventEffectEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_execute_without_initialization(self):
        """Test execute without initialization."""
        node = NodeKafkaEventEffect(container=None)

        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={"quality_score": 0.87},
            correlation_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Kafka producer not initialized"):
            await node.execute_effect(input_data)

    @pytest.mark.asyncio
    async def test_shutdown_with_pending_messages(self, kafka_config):
        """Test shutdown with pending messages."""
        node = NodeKafkaEventEffect(container=None, config=kafka_config)

        with patch(
            "omniintelligence.nodes.kafka_event_effect.v1_0_0.effect.Producer"
        ) as mock_producer_class:
            mock_producer = MagicMock()
            mock_producer.flush.return_value = 2  # 2 pending messages
            mock_producer_class.return_value = mock_producer

            await node.initialize()
            await node.shutdown()

            mock_producer.flush.assert_called_once_with(timeout=10.0)

    @pytest.mark.asyncio
    async def test_empty_payload(self, kafka_effect_node):
        """Test publishing with empty payload."""
        input_data = ModelKafkaEventInput(
            topic="quality.assessed.v1",
            event_type="QUALITY_ASSESSED",
            payload={},
            correlation_id=uuid4(),
        )

        # Mock successful delivery
        def mock_produce(topic, value, key, callback):
            msg = MagicMock()
            msg.partition.return_value = 0
            msg.offset.return_value = 42
            callback(None, msg)

        kafka_effect_node.producer.produce = mock_produce

        output = await kafka_effect_node.execute_effect(input_data)

        assert output.success is True
