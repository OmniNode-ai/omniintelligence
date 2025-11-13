"""
Comprehensive Unit Tests for IntelligenceKafkaConsumer

Tests coverage for:
- DLQ routing and error categorization
- Event type extraction (codegen + archon-intelligence topics)
- Factory functions with environment variables
- Service client initialization
- Consumer loop error handling
- Graceful shutdown and cleanup

Created: 2025-11-03
Purpose: Increase kafka_consumer.py coverage from 43% to 90%+
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from confluent_kafka import KafkaError, Message
from kafka_consumer import (
    IntelligenceKafkaConsumer,
    create_intelligence_kafka_consumer,
    get_kafka_consumer,
)


class TestDLQRouting:
    """Test Dead Letter Queue routing functionality"""

    @pytest.fixture
    def consumer_with_dlq(self):
        """Create consumer with DLQ publisher mock"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="dlq-test",
        )
        # Mock DLQ publisher
        consumer._dlq_publisher = AsyncMock()
        consumer._dlq_publisher.publish = AsyncMock()
        return consumer

    @pytest.mark.asyncio
    async def test_route_to_dlq_deserialization_error(self, consumer_with_dlq):
        """Test DLQ routing for JSON deserialization errors"""
        # Create mock message
        mock_message = MagicMock()
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100
        mock_message.timestamp.return_value = (0, 1699000000000)
        mock_message.value.return_value = b'{"test": "data"}'
        mock_message.key.return_value = b"test-key"

        error_msg = "JSONDecodeError: invalid JSON format"

        await consumer_with_dlq._route_to_dlq(mock_message, error_msg)

        # Verify DLQ metrics updated
        assert consumer_with_dlq.metrics["dlq_routed"] == 1

        # Verify DLQ publisher was called
        consumer_with_dlq._dlq_publisher.publish.assert_called_once()
        call_args = consumer_with_dlq._dlq_publisher.publish.call_args

        # Verify DLQ topic name
        assert call_args.kwargs["topic"] == "test.topic.v1.dlq"

        # Verify payload structure
        payload = call_args.kwargs["event"]
        assert payload["original_topic"] == "test.topic.v1"
        assert payload["original_partition"] == 0
        assert payload["original_offset"] == 100
        assert payload["error"] == error_msg
        assert payload["error_type"] == "deserialization_error"
        assert "error_timestamp" in payload

    @pytest.mark.asyncio
    async def test_route_to_dlq_timeout_error(self, consumer_with_dlq):
        """Test DLQ routing categorizes timeout errors correctly"""
        mock_message = MagicMock()
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100
        mock_message.timestamp.return_value = (0, 1699000000000)
        mock_message.value.return_value = b'{"test": "data"}'
        mock_message.key.return_value = None

        error_msg = "Request timeout after 30s"

        await consumer_with_dlq._route_to_dlq(mock_message, error_msg)

        # Verify error type categorization
        call_args = consumer_with_dlq._dlq_publisher.publish.call_args
        payload = call_args.kwargs["event"]
        assert payload["error_type"] == "timeout_error"

    @pytest.mark.asyncio
    async def test_route_to_dlq_handler_error(self, consumer_with_dlq):
        """Test DLQ routing categorizes handler errors correctly"""
        mock_message = MagicMock()
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100
        mock_message.timestamp.return_value = (0, 1699000000000)
        mock_message.value.return_value = b'{"test": "data"}'
        mock_message.key.return_value = None

        error_msg = "Handler failed to process event"

        await consumer_with_dlq._route_to_dlq(mock_message, error_msg)

        # Verify error type categorization
        call_args = consumer_with_dlq._dlq_publisher.publish.call_args
        payload = call_args.kwargs["event"]
        assert payload["error_type"] == "handler_error"

    @pytest.mark.asyncio
    async def test_route_to_dlq_validation_error(self, consumer_with_dlq):
        """Test DLQ routing categorizes validation errors correctly"""
        mock_message = MagicMock()
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100
        mock_message.timestamp.return_value = (0, 1699000000000)
        mock_message.value.return_value = b'{"test": "data"}'
        mock_message.key.return_value = None

        error_msg = "ValidationError: invalid payload"

        await consumer_with_dlq._route_to_dlq(mock_message, error_msg)

        # Verify error type categorization
        call_args = consumer_with_dlq._dlq_publisher.publish.call_args
        payload = call_args.kwargs["event"]
        assert payload["error_type"] == "validation_error"

    @pytest.mark.asyncio
    async def test_route_to_dlq_binary_data(self, consumer_with_dlq):
        """Test DLQ routing handles binary data gracefully"""
        mock_message = MagicMock()
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100
        mock_message.timestamp.return_value = (-1, None)  # No timestamp
        # Binary data that can't be decoded
        mock_message.value.return_value = b"\x80\x81\x82"
        mock_message.key.return_value = None

        error_msg = "Binary decode error"

        await consumer_with_dlq._route_to_dlq(mock_message, error_msg)

        # Verify DLQ publisher was called
        call_args = consumer_with_dlq._dlq_publisher.publish.call_args
        payload = call_args.kwargs["event"]

        # Verify binary data is represented as size
        assert "<binary data, size=3 bytes>" in payload["original_value"]
        assert payload["original_timestamp"] is None

    @pytest.mark.asyncio
    async def test_route_to_dlq_no_publisher(self):
        """Test DLQ routing handles missing publisher gracefully"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="dlq-test",
        )
        # No DLQ publisher initialized
        consumer._dlq_publisher = None

        mock_message = MagicMock()
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100
        mock_message.timestamp.return_value = (0, 1699000000000)
        mock_message.value.return_value = b'{"test": "data"}'
        mock_message.key.return_value = None

        # Should not raise exception even without publisher
        await consumer._route_to_dlq(mock_message, "Test error")

        # Metrics should still be updated
        assert consumer.metrics["dlq_routed"] == 1


class TestEventTypeExtraction:
    """Test event type extraction from topics and payloads"""

    @pytest.fixture
    def consumer(self):
        return IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

    def test_extract_event_type_from_data(self, consumer):
        """Test extracting event type from event data"""
        event_data = {
            "event_type": "codegen.request.validate",
            "payload": {},
        }

        event_type = consumer._extract_event_type(
            event_data, "omninode.codegen.request.validate.v1"
        )

        assert event_type == "codegen.request.validate"

    def test_extract_event_type_codegen_topic(self, consumer):
        """Test inferring event type from codegen topic"""
        event_data = {"payload": {}}

        # Codegen validate
        event_type = consumer._extract_event_type(
            event_data, "omninode.codegen.request.validate.v1"
        )
        assert event_type == "codegen.request.validate"

        # Codegen analyze
        event_type = consumer._extract_event_type(
            event_data, "omninode.codegen.request.analyze.v1"
        )
        assert event_type == "codegen.request.analyze"

        # Codegen pattern
        event_type = consumer._extract_event_type(
            event_data, "omninode.codegen.request.pattern.v1"
        )
        assert event_type == "codegen.request.pattern"

        # Codegen mixin
        event_type = consumer._extract_event_type(
            event_data, "omninode.codegen.request.mixin.v1"
        )
        assert event_type == "codegen.request.mixin"

    def test_extract_event_type_archon_intelligence_topic(self, consumer):
        """Test inferring event type from archon-intelligence topic"""
        event_data = {"payload": {}}

        # Tree indexing
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.tree.index-project-requested.v1"
        )
        assert event_type == "tree.index-project"

        # Quality assessment
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.quality.assess-code-requested.v1"
        )
        assert event_type == "quality.assess-code"

        # Entity extraction
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.entity.extract-code-requested.v1"
        )
        assert event_type == "entity.extract-code"

        # Performance baseline
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.performance.baseline-requested.v1"
        )
        assert event_type == "performance.baseline"

        # Freshness analyze
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.freshness.analyze-requested.v1"
        )
        assert event_type == "freshness.analyze"

        # Pattern learning
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.pattern-learning.match-requested.v1"
        )
        assert event_type == "pattern-learning.match"

        # Traceability
        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.traceability.track-requested.v1"
        )
        assert event_type == "traceability.track"

    def test_extract_event_type_completed_suffix(self, consumer):
        """Test event type extraction strips -completed suffix"""
        event_data = {"payload": {}}

        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.tree.index-project-completed.v1"
        )
        assert event_type == "tree.index-project"

    def test_extract_event_type_failed_suffix(self, consumer):
        """Test event type extraction strips -failed suffix"""
        event_data = {"payload": {}}

        event_type = consumer._extract_event_type(
            event_data, "dev.archon-intelligence.tree.index-project-failed.v1"
        )
        assert event_type == "tree.index-project"

    def test_extract_event_type_unknown_topic(self, consumer):
        """Test event type extraction returns None for unknown topic format"""
        event_data = {"payload": {}}

        event_type = consumer._extract_event_type(event_data, "unknown.topic.format")
        assert event_type is None


class TestFactoryFunctions:
    """Test factory functions with environment variables"""

    @patch.dict(
        os.environ,
        {
            "KAFKA_BOOTSTRAP_SERVERS": "test-server:9092",
            "KAFKA_CONSUMER_GROUP": "test-group",
            "KAFKA_AUTO_OFFSET_RESET": "latest",
            "KAFKA_ENABLE_AUTO_COMMIT": "false",
            "KAFKA_MAX_POLL_RECORDS": "1000",
            "KAFKA_SESSION_TIMEOUT_MS": "45000",
            "KAFKA_MAX_IN_FLIGHT": "200",
            "KAFKA_CODEGEN_VALIDATE_REQUEST": "custom.validate.v1",
            "KAFKA_CODEGEN_ANALYZE_REQUEST": "custom.analyze.v1",
            "KAFKA_CODEGEN_PATTERN_REQUEST": "custom.pattern.v1",
            "KAFKA_CODEGEN_MIXIN_REQUEST": "custom.mixin.v1",
        },
        clear=True,
    )
    def test_create_intelligence_kafka_consumer_custom_env(self):
        """Test consumer creation with custom environment variables"""
        consumer = create_intelligence_kafka_consumer()

        assert consumer.bootstrap_servers == "test-server:9092"
        assert consumer.consumer_group == "test-group"
        assert consumer.auto_offset_reset == "latest"
        assert consumer.enable_auto_commit == False
        assert consumer.max_poll_records == 1000
        assert consumer.session_timeout_ms == 45000
        assert consumer.max_in_flight == 200

        # Verify custom topic names are used
        assert "custom.validate.v1" in consumer.topics
        assert "custom.analyze.v1" in consumer.topics
        assert "custom.pattern.v1" in consumer.topics
        assert "custom.mixin.v1" in consumer.topics

    @patch.dict(os.environ, {}, clear=True)
    def test_create_intelligence_kafka_consumer_defaults(self):
        """Test consumer creation with default values"""
        consumer = create_intelligence_kafka_consumer()

        assert consumer.bootstrap_servers == "omninode-bridge-redpanda:9092"
        assert consumer.consumer_group == "archon-intelligence"
        assert consumer.auto_offset_reset == "earliest"
        assert consumer.enable_auto_commit == True
        assert consumer.max_poll_records == 500
        assert consumer.session_timeout_ms == 30000
        assert consumer.max_in_flight == 100

    def test_get_kafka_consumer_singleton_pattern(self):
        """Test singleton pattern returns same instance"""
        # Reset singleton
        import kafka_consumer

        kafka_consumer._consumer_instance = None

        consumer1 = get_kafka_consumer()
        consumer2 = get_kafka_consumer()

        assert consumer1 is consumer2
        assert id(consumer1) == id(consumer2)


class TestServiceInitialization:
    """Test service client initialization"""

    @pytest.mark.asyncio
    async def test_initialize_service_clients_success(self):
        """Test successful service client initialization"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        with (
            patch("kafka_consumer.ComprehensiveONEXScorer") as mock_scorer,
            patch("kafka_consumer.CodegenLangExtractService") as mock_langextract,
            patch("kafka_consumer.CodegenPatternService") as mock_pattern,
        ):

            await consumer._initialize_service_clients()

            # Verify all services initialized
            assert consumer.quality_scorer is not None
            assert consumer.langextract_service is not None
            assert consumer.pattern_service is not None

    @pytest.mark.asyncio
    async def test_initialize_service_clients_failure(self):
        """Test service client initialization handles errors"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        with patch(
            "kafka_consumer.ComprehensiveONEXScorer",
            side_effect=Exception("Init failed"),
        ):
            with pytest.raises(Exception, match="Init failed"):
                await consumer._initialize_service_clients()


class TestConsumerLoopErrorHandling:
    """Test consumer loop error handling paths"""

    @pytest.mark.asyncio
    async def test_consumer_loop_partition_eof(self):
        """Test consumer loop handles end of partition"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Mock consumer
        mock_consumer = MagicMock()
        consumer.consumer = mock_consumer

        # Create mock message with partition EOF error
        mock_message = MagicMock()
        mock_error = MagicMock()
        mock_error.code.return_value = KafkaError._PARTITION_EOF
        mock_message.error.return_value = mock_error

        # Configure poll to return EOF message then None (to exit loop)
        poll_results = [mock_message, None]
        poll_index = [0]

        async def mock_poll(*args):
            result = poll_results[poll_index[0]]
            poll_index[0] += 1
            if poll_index[0] >= len(poll_results):
                consumer.running = False  # Stop loop
            return result

        # Start consumer loop
        consumer.running = True
        with patch("asyncio.to_thread", side_effect=mock_poll):
            await consumer._consumer_loop()

        # Loop should handle EOF gracefully and continue
        assert not consumer.running

    @pytest.mark.asyncio
    async def test_consumer_loop_fatal_error(self):
        """Test consumer loop stops on fatal Kafka error"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Mock consumer
        mock_consumer = MagicMock()
        consumer.consumer = mock_consumer

        # Create mock message with fatal error
        mock_message = MagicMock()
        mock_error = MagicMock()
        mock_error.code.return_value = KafkaError.UNKNOWN
        mock_error.fatal.return_value = True
        mock_message.error.return_value = mock_error

        # Configure poll to return fatal error
        async def mock_poll(*args):
            return mock_message

        # Start consumer loop
        consumer.running = True
        with patch("asyncio.to_thread", side_effect=mock_poll):
            await consumer._consumer_loop()

        # Loop should stop on fatal error
        assert not consumer.running

    @pytest.mark.asyncio
    async def test_consumer_loop_message_processing_error(self):
        """Test consumer loop routes failed messages to DLQ"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Mock consumer and DLQ
        mock_consumer = MagicMock()
        consumer.consumer = mock_consumer
        consumer._dlq_publisher = AsyncMock()
        consumer._route_to_dlq = AsyncMock()

        # Create mock message
        mock_message = MagicMock()
        mock_message.error.return_value = None
        mock_message.value.return_value = b'{"test": "data"}'
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100

        # Mock process_message to raise exception
        consumer._process_message = AsyncMock(
            side_effect=Exception("Processing failed")
        )

        poll_count = [0]

        async def mock_poll(*args):
            poll_count[0] += 1
            if poll_count[0] == 1:
                return mock_message
            consumer.running = False
            return None

        # Start consumer loop
        consumer.running = True
        with patch("asyncio.to_thread", side_effect=mock_poll):
            await consumer._consumer_loop()

        # Verify DLQ routing was called
        consumer._route_to_dlq.assert_called_once()
        assert consumer.metrics["events_failed"] == 1


class TestGracefulShutdown:
    """Test graceful shutdown and cleanup"""

    @pytest.mark.asyncio
    async def test_stop_with_auto_commit_disabled(self):
        """Test stop commits offsets when auto-commit is disabled"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
            enable_auto_commit=False,
        )

        # Mock consumer
        mock_consumer = MagicMock()
        consumer.consumer = mock_consumer

        # Mock DLQ publisher
        consumer._dlq_publisher = AsyncMock()
        consumer._dlq_publisher.shutdown = AsyncMock()

        # Mock consumer task
        consumer.running = True
        consumer._consumer_task = AsyncMock()
        consumer._consumer_task.done.return_value = True

        # Mock handlers
        mock_handler = MagicMock()
        mock_handler._shutdown_publisher = AsyncMock()
        consumer.handlers = [mock_handler]

        await consumer.stop()

        # Verify offset commit was called
        mock_consumer.commit.assert_called_once_with(asynchronous=False)
        mock_consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_with_task_timeout(self):
        """Test stop cancels task if it doesn't finish in time"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Mock consumer
        mock_consumer = MagicMock()
        consumer.consumer = mock_consumer

        # Mock DLQ publisher
        consumer._dlq_publisher = AsyncMock()
        consumer._dlq_publisher.shutdown = AsyncMock()

        # Mock consumer task that takes too long
        consumer.running = True

        # Create a mock task that behaves like an asyncio.Task
        class MockTask:
            def __init__(self):
                self.cancel_called = False

            def done(self):
                return False

            def cancel(self):
                self.cancel_called = True

            def __await__(self):
                # Raise CancelledError when awaited
                async def _cancelled():
                    raise asyncio.CancelledError()

                return _cancelled().__await__()

        mock_task = MockTask()
        consumer._consumer_task = mock_task

        # Mock handlers
        consumer.handlers = []

        # Mock asyncio.wait_for to timeout
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            await consumer.stop()

        # Verify task was cancelled
        assert mock_task.cancel_called

    @pytest.mark.asyncio
    async def test_shutdown_handlers(self):
        """Test shutdown calls shutdown on all handlers"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Create mock handlers
        handler1 = MagicMock()
        handler1._shutdown_publisher = AsyncMock()
        handler1.get_handler_name = MagicMock(return_value="Handler1")

        handler2 = MagicMock()
        handler2._shutdown_publisher = AsyncMock()
        handler2.get_handler_name = MagicMock(return_value="Handler2")

        handler3 = MagicMock()  # No shutdown method
        handler3.get_handler_name = MagicMock(return_value="Handler3")

        consumer.handlers = [handler1, handler2, handler3]

        await consumer._shutdown_handlers()

        # Verify shutdown called on handlers that support it
        handler1._shutdown_publisher.assert_called_once()
        handler2._shutdown_publisher.assert_called_once()
        # handler3 has no shutdown method, so no call expected


class TestMessageProcessing:
    """Test message processing internal logic"""

    @pytest.mark.asyncio
    async def test_process_message_internal_empty_message(self):
        """Test processing empty message"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Create mock message with no value
        mock_message = MagicMock()
        mock_message.value.return_value = None
        mock_message.topic.return_value = "test.topic.v1"

        # Should return early without raising exception
        await consumer._process_message_internal(mock_message)

        # No events processed
        assert consumer.metrics["events_processed"] == 0

    @pytest.mark.asyncio
    async def test_process_message_internal_no_event_type(self):
        """Test processing message with no extractable event type"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Create mock message with data but no event type
        mock_message = MagicMock()
        event_data = {"payload": {}}
        mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
        mock_message.topic.return_value = "unknown.topic.format"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100

        # Should return early without raising exception
        await consumer._process_message_internal(mock_message)

        # No events processed
        assert consumer.metrics["events_processed"] == 0

    @pytest.mark.asyncio
    async def test_process_message_internal_json_decode_error(self):
        """Test processing message with invalid JSON"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
        )

        # Create mock message with invalid JSON
        mock_message = MagicMock()
        mock_message.value.return_value = b"not valid json"
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100

        # Should handle error gracefully without raising
        await consumer._process_message_internal(mock_message)

        # Failed event metric incremented
        assert consumer.metrics["events_failed"] == 1

    @pytest.mark.asyncio
    async def test_process_message_internal_manual_commit(self):
        """Test message processing commits offset when auto-commit disabled"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="test",
            enable_auto_commit=False,
        )

        # Mock consumer
        mock_consumer = MagicMock()
        consumer.consumer = mock_consumer

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)
        mock_handler.handle_event = AsyncMock(return_value=True)
        consumer.handlers = [mock_handler]

        # Create mock message
        mock_message = MagicMock()
        event_data = {
            "event_type": "test.event",
            "correlation_id": "test-123",
            "payload": {},
        }
        mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100

        await consumer._process_message_internal(mock_message)

        # Verify manual commit was called
        mock_consumer.commit.assert_called_once_with(
            message=mock_message, asynchronous=True
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
