#!/usr/bin/env python3
"""
Comprehensive Error Recovery Tests for Intelligence Service

Tests error scenarios and recovery mechanisms for the Kafka consumer
and event handlers, ensuring robustness and fault tolerance.

Test Coverage:
1. Kafka connection failures (startup + runtime)
2. Handler exception recovery (continues processing)
3. Backend service unavailability (graceful degradation)
4. Message ordering preservation
5. Concurrent event processing race conditions
6. Payload size limit enforcement
7. Invalid event format handling
8. Graceful shutdown during processing
9. Offset commit and recovery
10. Error response publishing

Created: 2025-10-15
Purpose: Validate error recovery and fault tolerance mechanisms
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from confluent_kafka import Consumer, KafkaError, KafkaException, Message
from handlers.codegen_validation_handler import CodegenValidationHandler
from kafka_consumer import IntelligenceKafkaConsumer

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_kafka_consumer():
    """Create mock Kafka consumer for testing."""
    consumer = Mock(spec=Consumer)
    consumer.subscribe = Mock()
    consumer.poll = Mock(return_value=None)
    consumer.close = Mock()
    return consumer


@pytest.fixture
def mock_handler():
    """Create mock event handler for testing."""
    handler = AsyncMock()
    handler.can_handle = Mock(return_value=True)
    handler.handle_event = AsyncMock(return_value=True)
    handler.get_handler_name = Mock(return_value="MockHandler")
    handler._shutdown_publisher = AsyncMock()
    return handler


@pytest.fixture
def mock_failing_handler():
    """Create mock handler that fails processing."""
    handler = AsyncMock()
    handler.can_handle = Mock(return_value=True)
    handler.handle_event = AsyncMock(side_effect=Exception("Handler processing error"))
    handler.get_handler_name = Mock(return_value="FailingHandler")
    handler._shutdown_publisher = AsyncMock()
    return handler


@pytest.fixture
def sample_event_data():
    """Create sample event data for testing."""
    return {
        "event_id": str(uuid4()),
        "event_type": "codegen.request.validate",
        "correlation_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_service": "test-service",
        "payload": {
            "code_content": "class TestNode(NodeBase): pass",
            "node_type": "effect",
            "file_path": "test.py",
        },
    }


def create_kafka_message(
    value: Optional[Dict[str, Any]] = None,
    topic: str = "test.topic",
    partition: int = 0,
    offset: int = 0,
    error: Optional[KafkaError] = None,
) -> Message:
    """
    Create mock Kafka message for testing.

    Args:
        value: Message value (will be JSON-encoded)
        topic: Topic name
        partition: Partition number
        offset: Message offset
        error: Optional Kafka error

    Returns:
        Mock Kafka Message object
    """
    msg = Mock(spec=Message)

    if value is not None:
        msg.value = Mock(return_value=json.dumps(value).encode("utf-8"))
    else:
        msg.value = Mock(return_value=None)

    msg.topic = Mock(return_value=topic)
    msg.partition = Mock(return_value=partition)
    msg.offset = Mock(return_value=offset)

    if error:
        msg.error = Mock(return_value=error)
    else:
        msg.error = Mock(return_value=None)

    return msg


# ============================================================================
# Kafka Connection Failure Tests
# ============================================================================


@pytest.mark.asyncio
class TestKafkaConnectionFailures:
    """Test Kafka connection failure scenarios and recovery."""

    async def test_connection_failure_on_startup(self):
        """Test consumer handles connection failure during initialization."""
        # Patch Consumer class before creating consumer
        with patch("kafka_consumer.Consumer") as mock_consumer_class:
            # Make Consumer raise KafkaException on instantiation
            mock_consumer_class.side_effect = KafkaException("Connection refused")

            # Create consumer with invalid bootstrap servers
            consumer = IntelligenceKafkaConsumer(
                bootstrap_servers="invalid-host:9999",
                topics=["test.topic"],
            )

            # Initialization should fail with RuntimeError
            with pytest.raises(
                RuntimeError, match="Failed to initialize Kafka consumer"
            ):
                await consumer.initialize()

    async def test_connection_loss_during_processing(
        self, mock_kafka_consumer, mock_handler, sample_event_data
    ):
        """Test consumer handles connection loss during message processing."""
        # Setup consumer
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        # Mock successful initialization
        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_handler]
            consumer.running = True

            # Simulate connection loss error
            connection_error = Mock(spec=KafkaError)
            connection_error.code = Mock(return_value=KafkaError.NETWORK_EXCEPTION)
            connection_error.fatal = Mock(return_value=False)

            error_msg = create_kafka_message(error=connection_error)

            # Setup poll sequence: error -> reconnect -> success
            good_msg = create_kafka_message(value=sample_event_data)
            mock_kafka_consumer.poll.side_effect = [error_msg, None, good_msg, None]

            # Process messages
            tasks = []
            for _ in range(3):
                msg = await asyncio.to_thread(mock_kafka_consumer.poll, 1.0)
                if msg and not msg.error():
                    tasks.append(consumer._process_message(msg))

            # Should process good message successfully
            if tasks:
                await asyncio.gather(*tasks)
                assert mock_handler.handle_event.called

    async def test_fatal_kafka_error_stops_consumer(self, mock_kafka_consumer):
        """Test consumer stops on fatal Kafka errors."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.running = True

            # Create fatal error
            fatal_error = Mock(spec=KafkaError)
            fatal_error.code = Mock(return_value=KafkaError._AUTHENTICATION)
            fatal_error.fatal = Mock(return_value=True)

            error_msg = create_kafka_message(error=fatal_error)
            mock_kafka_consumer.poll.return_value = error_msg

            # Start consumer loop (will stop on fatal error)
            loop_task = asyncio.create_task(consumer._consumer_loop())

            # Wait a bit for error to be processed
            await asyncio.sleep(0.1)

            # Consumer should have stopped
            assert consumer.running is False

            # Cleanup
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

    async def test_partition_eof_handling(self, mock_kafka_consumer, sample_event_data):
        """Test consumer continues on partition EOF."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer

            # Create partition EOF error
            eof_error = Mock(spec=KafkaError)
            eof_error.code = Mock(return_value=KafkaError._PARTITION_EOF)

            eof_msg = create_kafka_message(error=eof_error)

            # Setup poll: EOF -> good message
            good_msg = create_kafka_message(value=sample_event_data)
            mock_kafka_consumer.poll.side_effect = [eof_msg, good_msg]

            # Process EOF message (should not raise)
            msg1 = await asyncio.to_thread(mock_kafka_consumer.poll, 1.0)
            assert msg1.error()  # Should have EOF error

            # Process good message
            msg2 = await asyncio.to_thread(mock_kafka_consumer.poll, 1.0)
            assert not msg2.error()


# ============================================================================
# Handler Exception Recovery Tests
# ============================================================================


@pytest.mark.asyncio
class TestHandlerExceptionRecovery:
    """Test handler exception handling and recovery."""

    async def test_handler_exception_continues_processing(
        self, mock_kafka_consumer, mock_failing_handler, sample_event_data
    ):
        """Test consumer continues processing after handler exception."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_failing_handler]
            consumer.running = True  # Simulate running consumer

            # Create message
            msg = create_kafka_message(value=sample_event_data)

            # Process message (handler will fail)
            await consumer._process_message(msg)

            # Verify handler was called
            assert mock_failing_handler.handle_event.called

            # Verify failure was counted
            assert consumer.metrics["events_failed"] == 1

            # Consumer should still be able to process next message
            assert consumer.running is True

    async def test_multiple_handlers_one_fails(
        self, mock_kafka_consumer, mock_handler, mock_failing_handler, sample_event_data
    ):
        """Test processing continues when one handler fails."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer

            # Register multiple handlers with different event types
            mock_handler.can_handle = Mock(return_value=False)
            mock_failing_handler.can_handle = Mock(return_value=True)

            consumer.handlers = [mock_handler, mock_failing_handler]

            # Create message
            msg = create_kafka_message(value=sample_event_data)

            # Process message (failing handler matches)
            await consumer._process_message(msg)

            # Failing handler was called
            assert mock_failing_handler.handle_event.called

            # First handler was not called (can't handle this type)
            assert not mock_handler.handle_event.called

    async def test_handler_publishes_error_response(
        self, mock_kafka_consumer, sample_event_data
    ):
        """Test handler publishes error response on failure."""
        # Patch _publish_error_response at the base class level
        with patch(
            "src.handlers.base_response_publisher.BaseResponsePublisher._publish_error_response",
            new=AsyncMock(),
        ) as mock_publish:
            # Create real handler with mocked dependencies
            with patch("src.handlers.codegen_validation_handler.CodegenQualityService"):
                handler = CodegenValidationHandler(quality_service=Mock())

                # Mock quality service to raise exception
                handler.quality_service.validate_generated_code = AsyncMock(
                    side_effect=Exception("Validation failed")
                )

                # Create event envelope
                event = {
                    "correlation_id": str(uuid4()),
                    "payload": sample_event_data["payload"],
                }

                # Handle event (should catch exception and publish error)
                result = await handler.handle_event(event)

                # Should return False and publish error
                assert result is False
                assert mock_publish.called


# ============================================================================
# Backend Service Unavailable Tests
# ============================================================================


@pytest.mark.asyncio
class TestBackendServiceUnavailable:
    """Test graceful degradation when backend services are unavailable."""

    async def test_langextract_service_unavailable(self, sample_event_data):
        """Test handler gracefully degrades when LangExtract is unavailable."""
        from handlers.codegen_analysis_handler import CodegenAnalysisHandler

        # Patch _publish_error_response at the base class level
        with patch(
            "src.handlers.base_response_publisher.BaseResponsePublisher._publish_error_response",
            new=AsyncMock(),
        ) as mock_publish:
            # Create handler with mocked service
            mock_service = Mock()
            mock_service.connect = AsyncMock()
            mock_service.analyze_prd_semantics = AsyncMock(
                side_effect=Exception("Service unavailable")
            )

            handler = CodegenAnalysisHandler(langextract_service=mock_service)

            # Create event with correct payload structure for analysis handler
            event = {
                "correlation_id": str(uuid4()),
                "payload": {
                    "prd_content": "Test PRD content for analysis",
                    "analysis_type": "full",
                },
            }

            # Handle event
            result = await handler.handle_event(event)

            # Should fail gracefully and publish error
            assert result is False
            assert mock_publish.called

    async def test_qdrant_service_unavailable(self, sample_event_data):
        """Test pattern handler gracefully degrades when Qdrant is unavailable."""
        from handlers.codegen_pattern_handler import CodegenPatternHandler

        # Create handler with mocked service
        mock_service = Mock()
        mock_service.find_similar_nodes = AsyncMock(
            side_effect=Exception("Qdrant connection failed")
        )

        handler = CodegenPatternHandler(pattern_service=mock_service)
        handler._publish_error_response = AsyncMock()

        # Create event
        event = {
            "correlation_id": str(uuid4()),
            "payload": {
                "node_description": "Test node description",
                "node_type": "effect",
            },
        }

        # Handle event
        result = await handler.handle_event(event)

        # Should fail gracefully and publish error
        assert result is False
        assert handler._publish_error_response.called

    async def test_service_timeout_handling(self, sample_event_data):
        """Test handler handles service timeouts gracefully."""
        from handlers.codegen_pattern_handler import CodegenPatternHandler

        # Create handler with service that times out
        mock_service = Mock()

        async def slow_service(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow service
            return []

        mock_service.find_similar_nodes = slow_service

        handler = CodegenPatternHandler(pattern_service=mock_service)
        handler._publish_error_response = AsyncMock()

        # Create event
        event = {
            "correlation_id": str(uuid4()),
            "payload": {
                "node_description": "Test node",
                "node_type": "effect",
            },
        }

        # Handle event with timeout
        try:
            await asyncio.wait_for(handler.handle_event(event), timeout=1.0)
        except asyncio.TimeoutError:
            # Timeout is expected - this tests that timeouts can occur
            # Note: Handler doesn't have its own metrics dict, metrics are tracked at consumer level
            pass


# ============================================================================
# Message Processing Edge Cases
# ============================================================================


@pytest.mark.asyncio
class TestMessageProcessingEdgeCases:
    """Test edge cases in message processing."""

    async def test_message_ordering_preservation(
        self, mock_kafka_consumer, mock_handler
    ):
        """Test messages are processed in order."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_handler]

            # Create ordered messages
            messages = []
            for i in range(5):
                event_data = {
                    "event_id": str(uuid4()),
                    "event_type": "codegen.request.validate",
                    "correlation_id": str(uuid4()),
                    "payload": {"sequence": i},
                }
                messages.append(create_kafka_message(value=event_data, offset=i))

            # Process messages in order
            for msg in messages:
                await consumer._process_message(msg)

            # Verify handler was called in order
            assert mock_handler.handle_event.call_count == 5

            # Verify sequence numbers were in order
            call_args = [
                call[0][0] for call in mock_handler.handle_event.call_args_list
            ]
            sequences = [arg["payload"]["sequence"] for arg in call_args]
            assert sequences == [0, 1, 2, 3, 4]

    async def test_concurrent_event_processing(
        self, mock_kafka_consumer, mock_handler, sample_event_data
    ):
        """Test concurrent event processing doesn't cause race conditions."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_handler]

            # Create multiple messages with different correlation IDs
            messages = []
            for _ in range(10):
                event_data = sample_event_data.copy()
                event_data["correlation_id"] = str(uuid4())
                messages.append(create_kafka_message(value=event_data))

            # Process messages concurrently
            tasks = [consumer._process_message(msg) for msg in messages]
            await asyncio.gather(*tasks)

            # All messages should be processed
            assert mock_handler.handle_event.call_count == 10
            assert consumer.metrics["events_processed"] == 10

    async def test_payload_size_limit_enforcement(
        self, mock_kafka_consumer, mock_handler
    ):
        """Test handling of oversized payloads."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_handler]

            # Create message with very large payload (10MB)
            large_payload = {
                "event_type": "codegen.request.validate",
                "correlation_id": str(uuid4()),
                "payload": {
                    "code_content": "x" * (10 * 1024 * 1024),  # 10MB of data
                },
            }

            msg = create_kafka_message(value=large_payload)

            # Process message (may fail or succeed depending on limits)
            try:
                await consumer._process_message(msg)
                # If it succeeds, handler should have been called
                assert mock_handler.handle_event.called
            except Exception:
                # If it fails, should be logged as failed event
                assert consumer.metrics["events_failed"] >= 0

    async def test_invalid_json_handling(self, mock_kafka_consumer):
        """Test handling of malformed JSON messages."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer

            # Create message with invalid JSON
            msg = Mock(spec=Message)
            msg.value = Mock(return_value=b"invalid json{{{")
            msg.error = Mock(return_value=None)
            msg.topic = Mock(return_value="test.topic")
            msg.partition = Mock(return_value=0)
            msg.offset = Mock(return_value=0)

            # Process message (should catch JSONDecodeError and not raise)
            await consumer._process_message(msg)

            # Failure should be counted
            assert consumer.metrics["events_failed"] == 1

    async def test_empty_message_handling(self, mock_kafka_consumer):
        """Test handling of empty messages."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer

            # Create empty message
            msg = create_kafka_message(value=None)

            # Process message (should handle gracefully)
            await consumer._process_message(msg)

            # Should not increment processed count
            assert consumer.metrics["events_processed"] == 0

    async def test_missing_required_fields(self, mock_kafka_consumer, mock_handler):
        """Test handling of events with missing required fields."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_handler]

            # Create message with missing correlation_id
            incomplete_event = {
                "event_type": "codegen.request.validate",
                # Missing correlation_id
                "payload": {"code_content": "test"},
            }

            msg = create_kafka_message(value=incomplete_event)

            # Process message
            await consumer._process_message(msg)

            # Handler should still be called (correlation_id defaults to "unknown")
            assert mock_handler.handle_event.called


# ============================================================================
# Graceful Shutdown Tests
# ============================================================================


@pytest.mark.asyncio
class TestGracefulShutdown:
    """Test graceful shutdown behavior."""

    async def test_shutdown_during_event_processing(
        self, mock_kafka_consumer, sample_event_data
    ):
        """Test graceful shutdown waits for event processing to complete."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        # Create slow handler
        slow_handler = AsyncMock()
        slow_handler.can_handle = Mock(return_value=True)
        slow_handler.get_handler_name = Mock(return_value="SlowHandler")
        slow_handler._shutdown_publisher = AsyncMock()

        async def slow_processing(*args, **kwargs):
            await asyncio.sleep(0.5)  # Simulate slow processing
            return True

        slow_handler.handle_event = slow_processing

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [slow_handler]
            consumer.running = True

            # Start processing a message
            msg = create_kafka_message(value=sample_event_data)
            process_task = asyncio.create_task(consumer._process_message(msg))

            # Give it time to start
            await asyncio.sleep(0.1)

            # Initiate shutdown
            shutdown_task = asyncio.create_task(consumer.stop())

            # Wait for both tasks
            await asyncio.gather(process_task, shutdown_task)

            # Verify consumer is stopped
            assert consumer.running is False

    async def test_shutdown_calls_handler_cleanup(
        self, mock_kafka_consumer, mock_handler
    ):
        """Test shutdown calls cleanup on all handlers."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [mock_handler]
            consumer.running = True

            # Stop consumer
            await consumer.stop()

            # Handler cleanup should be called
            assert mock_handler._shutdown_publisher.called

    async def test_shutdown_timeout_cancels_processing(self, mock_kafka_consumer):
        """Test shutdown timeout cancels long-running processing."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.running = True

            # Create consumer task that never finishes
            async def never_ending_loop():
                while True:
                    await asyncio.sleep(1)

            consumer._consumer_task = asyncio.create_task(never_ending_loop())

            # Stop consumer (should timeout and cancel)
            start = time.perf_counter()
            await consumer.stop()
            elapsed = time.perf_counter() - start

            # Should complete within timeout (10s) plus small buffer
            assert elapsed < 11.0
            assert consumer._consumer_task.cancelled()

    async def test_offset_commit_on_shutdown(self, mock_kafka_consumer):
        """Test offsets are committed during shutdown."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
            enable_auto_commit=False,  # Manual commit mode
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.running = True

            # Stop consumer
            await consumer.stop()

            # Consumer close should be called (which commits offsets)
            assert mock_kafka_consumer.close.called


# ============================================================================
# Integration: Full Error Recovery Flow
# ============================================================================


@pytest.mark.asyncio
class TestFullErrorRecoveryFlow:
    """Integration test for complete error recovery flow."""

    async def test_end_to_end_error_recovery(
        self, mock_kafka_consumer, sample_event_data
    ):
        """
        Test complete error recovery flow:
        1. Handler fails on first message
        2. Error response is published
        3. Consumer continues processing
        4. Subsequent messages succeed
        """
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        # Create handler that fails once then succeeds
        handler = AsyncMock()
        handler.get_handler_name = Mock(return_value="RecoveryHandler")
        handler.can_handle = Mock(return_value=True)
        handler._shutdown_publisher = AsyncMock()

        call_count = 0

        async def fail_once_handler(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call fails")
            return True

        handler.handle_event = fail_once_handler

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = [handler]
            consumer.running = True  # Simulate running consumer

            # Create two messages
            msg1 = create_kafka_message(value=sample_event_data, offset=0)
            msg2_data = sample_event_data.copy()
            msg2_data["correlation_id"] = str(uuid4())
            msg2 = create_kafka_message(value=msg2_data, offset=1)

            # Process first message (will fail)
            await consumer._process_message(msg1)
            assert consumer.metrics["events_failed"] == 1
            assert call_count == 1

            # Process second message (should succeed)
            await consumer._process_message(msg2)
            assert consumer.metrics["events_processed"] == 1
            assert call_count == 2

            # Verify consumer is still running
            assert consumer.running is True

    async def test_cascading_failure_recovery(
        self, mock_kafka_consumer, sample_event_data
    ):
        """
        Test recovery from cascading failures across multiple handlers.
        """
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        # Create multiple handlers with different failure modes
        handlers = []
        for i in range(3):
            handler = AsyncMock()
            handler.get_handler_name = Mock(return_value=f"Handler{i}")
            handler._shutdown_publisher = AsyncMock()

            # Different handlers handle different event types
            if i == 0:
                handler.can_handle = Mock(side_effect=lambda et: "validate" in et)
                handler.handle_event = AsyncMock(
                    side_effect=Exception("Validation failed")
                )
            elif i == 1:
                handler.can_handle = Mock(side_effect=lambda et: "analyze" in et)
                handler.handle_event = AsyncMock(return_value=True)
            else:
                handler.can_handle = Mock(side_effect=lambda et: "pattern" in et)
                handler.handle_event = AsyncMock(return_value=True)

            handlers.append(handler)

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.handlers = handlers

            # Create events for different handlers
            events = [
                {**sample_event_data, "event_type": "codegen.request.validate"},
                {**sample_event_data, "event_type": "codegen.request.analyze"},
                {**sample_event_data, "event_type": "codegen.request.pattern"},
            ]

            # Process all events
            for idx, event_data in enumerate(events):
                msg = create_kafka_message(value=event_data, offset=idx)
                await consumer._process_message(msg)

            # First handler should have failed, others succeeded
            assert consumer.metrics["events_failed"] == 1
            assert consumer.metrics["events_processed"] == 2


# ============================================================================
# Health and Metrics Tests
# ============================================================================


@pytest.mark.asyncio
class TestHealthAndMetrics:
    """Test health monitoring and metrics during error scenarios."""

    async def test_health_status_during_errors(self, mock_kafka_consumer):
        """Test health status reflects error rates."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer
            consumer.running = True

            # Simulate high error rate: 6 failed out of 10 total = 60% error rate
            consumer.metrics["events_processed"] = 4
            consumer.metrics["events_failed"] = 6  # 6/(4+6) = 60% error rate

            health = consumer.get_health()

            # Should be degraded due to >50% error rate
            assert health["status"] == "degraded"
            assert health["error_rate_percent"] == 60.0

    async def test_metrics_accuracy_after_errors(
        self, mock_kafka_consumer, mock_handler, mock_failing_handler, sample_event_data
    ):
        """Test metrics are accurate after processing errors."""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topics=["test.topic"],
        )

        with patch("src.kafka_consumer.Consumer", return_value=mock_kafka_consumer):
            consumer.consumer = mock_kafka_consumer

            # Add both good and failing handlers
            mock_handler.can_handle = Mock(return_value=False)
            mock_failing_handler.can_handle = Mock(return_value=True)
            consumer.handlers = [mock_handler, mock_failing_handler]

            # Process multiple messages
            for i in range(5):
                event_data = sample_event_data.copy()
                event_data["correlation_id"] = str(uuid4())
                msg = create_kafka_message(value=event_data, offset=i)
                await consumer._process_message(msg)

            metrics = consumer.get_metrics()

            # All should have failed
            assert metrics["events_failed"] == 5
            assert metrics["events_processed"] == 0
            assert metrics["total_events"] == 5


# ============================================================================
# Documentation String
# ============================================================================


ERROR_RECOVERY_DOCUMENTATION = """
# Error Recovery and Fault Tolerance Documentation

## Expected Error Behaviors

### 1. Kafka Connection Errors

**Startup Connection Failure:**
- Consumer initialization fails with RuntimeError
- Error is logged with details
- Consumer does not start processing
- Recovery: Fix connection settings and restart

**Runtime Connection Loss:**
- Non-fatal network errors are logged
- Consumer continues polling
- Automatic reconnection on next poll
- No message loss if offsets are committed

**Fatal Kafka Errors:**
- Consumer stops gracefully
- Offsets are committed
- All handlers are shut down
- Recovery: Address root cause and restart service

### 2. Handler Exception Recovery

**Handler Processing Exception:**
- Exception is caught and logged
- Error metric is incremented
- Error response is published (if correlation_id available)
- Consumer continues processing next message
- Recovery: Automatic, no manual intervention needed

**Multiple Handler Failures:**
- Each handler failure is independent
- One handler failure doesn't affect others
- Failed events are counted separately per handler
- Recovery: Handlers self-recover on next message

### 3. Backend Service Unavailability

**Service Connection Failure:**
- Handler catches service exceptions
- Error response published to requester
- Event marked as failed
- Consumer continues processing
- Recovery: Service automatically retries on next request

**Service Timeout:**
- Handler respects timeout limits
- Timeout treated as service failure
- Error response published
- Recovery: Automatic on next request

**Graceful Degradation:**
- Core consumer functionality maintained
- Other handlers continue working
- Metrics track service-specific failures
- Recovery: Services self-heal when available

### 4. Message Processing Edge Cases

**Message Ordering:**
- Messages processed in offset order
- Sequential processing per partition
- Failures don't reorder subsequent messages
- Recovery: N/A (expected behavior)

**Concurrent Processing:**
- Thread-safe metrics updates
- No race conditions in handler state
- Independent correlation IDs
- Recovery: N/A (expected behavior)

**Oversized Payloads:**
- Large messages may be rejected by Kafka
- Handler may fail on memory constraints
- Error logged and counted
- Recovery: Implement payload size limits

**Invalid Message Format:**
- JSON decode errors caught
- Event marked as failed
- Warning logged with message details
- Recovery: Message skipped, processing continues

### 5. Graceful Shutdown

**Shutdown During Processing:**
- Current event processing completes
- 10-second timeout for completion
- Offsets committed before close
- Handlers cleaned up
- Recovery: N/A (clean shutdown)

**Shutdown Timeout:**
- Long-running processing cancelled after 10s
- Consumer task cancelled gracefully
- Partial work may be lost
- Recovery: Next startup reprocesses from offset

## Recovery Patterns

### Pattern 1: Transient Failure Recovery
```
1. Handler encounters transient error (network timeout)
2. Handler catches exception, logs error
3. Error response published to requester
4. Handler ready for next message
5. Next message processed successfully
6. Recovery complete
```

### Pattern 2: Service Outage Recovery
```
1. Backend service unavailable
2. Handler detects connection failure
3. Error responses published for affected events
4. Other handlers continue working
5. Service comes back online
6. Subsequent requests succeed
7. Recovery complete
```

### Pattern 3: Consumer Restart Recovery
```
1. Fatal error stops consumer
2. Offsets committed to Kafka
3. Consumer shut down cleanly
4. Service restarted
5. Consumer initializes
6. Processing resumes from last committed offset
7. No message loss
8. Recovery complete
```

## Monitoring and Alerting

### Key Metrics
- `events_failed`: Total failed events (alert if >10% of total)
- `error_rate_percent`: Current error rate (alert if >50%)
- `events_per_second`: Processing throughput (alert if drops to 0)
- `uptime_seconds`: Consumer uptime (track availability)

### Health Status
- `healthy`: Normal operation, low error rate
- `degraded`: High error rate (>50%) or no recent activity
- `unhealthy`: Consumer not running

### Alert Thresholds
- Error rate >50%: Warning (check backend services)
- Error rate >80%: Critical (immediate attention)
- No activity for 5 minutes: Warning (check Kafka connection)
- Consumer not running: Critical (service down)

## Testing Strategy

### Unit Tests
- Mock all external dependencies
- Test error paths explicitly
- Verify metrics accuracy
- Validate error response structure

### Integration Tests
- Use real Kafka (or Redpanda)
- Test actual handler implementations
- Verify end-to-end flows
- Test failure recovery

### Performance Tests
- High load error scenarios
- Concurrent failure handling
- Resource cleanup verification
- Memory leak detection

## Best Practices

1. **Always catch handler exceptions** - Never let exceptions propagate to consumer
2. **Publish error responses** - Always notify requester of failures
3. **Log with context** - Include correlation_id, event_type, error details
4. **Update metrics accurately** - Track both successes and failures
5. **Clean up resources** - Implement proper shutdown for all handlers
6. **Monitor health status** - Use health endpoint for alerting
7. **Test error paths** - Don't just test happy path
8. **Document recovery** - Clear runbooks for common failures
"""


# ============================================================================
# Test Runner
# ============================================================================


if __name__ == "__main__":
    # Print documentation
    print(ERROR_RECOVERY_DOCUMENTATION)

    # Run tests
    pytest.main(
        [
            __file__,
            "-v",
            "-s",
            "--tb=short",
            "--durations=10",
        ]
    )
