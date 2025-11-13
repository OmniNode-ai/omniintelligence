"""
Unit Tests for IntelligenceKafkaConsumer

Tests the Kafka consumer service including:
- Consumer initialization and configuration
- Handler registration
- Event routing and processing
- Lifecycle management (start/stop)
- Metrics and health checks
- Error handling

Created: 2025-10-15
Purpose: Comprehensive testing of Kafka consumer integration
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the consumer class
from kafka_consumer import (
    IntelligenceKafkaConsumer,
    create_intelligence_kafka_consumer,
    get_kafka_consumer,
)


class TestIntelligenceKafkaConsumer:
    """Test suite for IntelligenceKafkaConsumer"""

    @pytest.fixture
    def mock_consumer_config(self):
        """Provide mock consumer configuration"""
        return {
            "bootstrap_servers": "localhost:19092",
            "topics": [
                "omninode.codegen.request.validate.v1",
                "omninode.codegen.request.analyze.v1",
            ],
            "consumer_group": "test-intelligence",
            "auto_offset_reset": "earliest",
        }

    @pytest.fixture
    def consumer_instance(self, mock_consumer_config):
        """Create consumer instance for testing"""
        return IntelligenceKafkaConsumer(**mock_consumer_config)

    def test_consumer_initialization(self, mock_consumer_config):
        """Test consumer initializes with correct configuration"""
        consumer = IntelligenceKafkaConsumer(**mock_consumer_config)

        assert consumer.bootstrap_servers == mock_consumer_config["bootstrap_servers"]
        assert consumer.topics == mock_consumer_config["topics"]
        assert consumer.consumer_group == mock_consumer_config["consumer_group"]
        assert consumer.running == False
        assert consumer.handlers == []
        assert consumer.consumer is None

    @pytest.mark.asyncio
    async def test_consumer_initialize_success(self, consumer_instance):
        """Test successful consumer initialization"""
        with patch("src.kafka_consumer.Consumer") as mock_kafka_consumer:
            mock_consumer = MagicMock()
            mock_kafka_consumer.return_value = mock_consumer

            await consumer_instance.initialize()

            # Verify consumer was created
            mock_kafka_consumer.assert_called_once()

            # Verify subscription
            mock_consumer.subscribe.assert_called_once_with(consumer_instance.topics)

            # Verify handlers were registered
            assert len(consumer_instance.handlers) == 4  # 4 codegen handlers

    @pytest.mark.asyncio
    async def test_consumer_initialize_failure(self, consumer_instance):
        """Test consumer initialization failure handling"""
        with patch("src.kafka_consumer.Consumer") as mock_kafka_consumer:
            mock_kafka_consumer.side_effect = Exception("Connection failed")

            with pytest.raises(Exception):
                await consumer_instance.initialize()

    @pytest.mark.asyncio
    async def test_handler_registration(self, consumer_instance):
        """Test handler registration during initialization"""
        with patch("src.kafka_consumer.Consumer"):
            await consumer_instance.initialize()

            # Verify all 4 handlers registered
            assert len(consumer_instance.handlers) == 4

            handler_names = [h.get_handler_name() for h in consumer_instance.handlers]

            assert "CodegenValidationHandler" in handler_names
            assert "CodegenAnalysisHandler" in handler_names
            assert "CodegenPatternHandler" in handler_names
            assert "CodegenMixinHandler" in handler_names

    @pytest.mark.asyncio
    async def test_event_routing_to_handler(self, consumer_instance):
        """Test event routing to appropriate handler"""
        # Setup mock handler
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)
        mock_handler.handle_event = AsyncMock(return_value=True)

        consumer_instance.handlers = [mock_handler]

        # Test routing
        event_data = {
            "event_type": "codegen.request.validate",
            "correlation_id": "test-123",
            "payload": {"code_content": "def test(): pass"},
        }

        result = await consumer_instance._route_to_handler(
            "codegen.request.validate", event_data
        )

        assert result == True
        mock_handler.can_handle.assert_called_once_with("codegen.request.validate")
        mock_handler.handle_event.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_event_routing_no_handler(self, consumer_instance):
        """Test event routing when no handler found"""
        # Setup mock handler that doesn't handle event
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=False)

        consumer_instance.handlers = [mock_handler]

        # Test routing
        result = await consumer_instance._route_to_handler(
            "unknown.event.type", {"test": "data"}
        )

        assert result == False

    def test_extract_event_type_from_data(self, consumer_instance):
        """Test extracting event type from event data"""
        event_data = {
            "event_type": "codegen.request.validate",
            "payload": {},
        }

        event_type = consumer_instance._extract_event_type(
            event_data, "omninode.codegen.request.validate.v1"
        )

        assert event_type == "codegen.request.validate"

    def test_extract_event_type_from_topic(self, consumer_instance):
        """Test inferring event type from topic when not in data"""
        event_data = {"payload": {}}  # No event_type field

        event_type = consumer_instance._extract_event_type(
            event_data, "omninode.codegen.request.analyze.v1"
        )

        assert event_type == "codegen.request.analyze"

    @pytest.mark.asyncio
    async def test_process_message_success(self, consumer_instance):
        """Test successful message processing"""
        # Setup
        consumer_instance.handlers = []

        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)
        mock_handler.handle_event = AsyncMock(return_value=True)
        consumer_instance.handlers.append(mock_handler)

        # Create mock Kafka message
        mock_message = MagicMock()
        event_data = {
            "event_type": "codegen.request.validate",
            "correlation_id": "test-123",
            "payload": {"code_content": "test"},
        }
        mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
        mock_message.topic.return_value = "omninode.codegen.request.validate.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100

        # Process message
        await consumer_instance._process_message(mock_message)

        # Verify handler was called
        mock_handler.handle_event.assert_called_once()
        assert consumer_instance.metrics["events_processed"] == 1
        assert consumer_instance.metrics["events_failed"] == 0

    @pytest.mark.asyncio
    async def test_process_message_failure(self, consumer_instance):
        """Test message processing failure handling"""
        # Setup mock handler that fails
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)
        mock_handler.handle_event = AsyncMock(side_effect=Exception("Handler failed"))
        consumer_instance.handlers = [mock_handler]

        # Create mock message
        mock_message = MagicMock()
        event_data = {"event_type": "codegen.request.validate", "payload": {}}
        mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
        mock_message.topic.return_value = "omninode.codegen.request.validate.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 100

        # Process message (should not raise exception)
        with pytest.raises(Exception):
            await consumer_instance._process_message(mock_message)

        # Verify metrics
        assert consumer_instance.metrics["events_failed"] == 1

    def test_metrics_calculation(self, consumer_instance):
        """Test metrics calculation"""
        # Set some test metrics
        consumer_instance.metrics["events_processed"] = 100
        consumer_instance.metrics["events_failed"] = 10
        consumer_instance.metrics["total_processing_time_ms"] = 5000.0
        consumer_instance.metrics["consumer_started_at"] = 0  # Use fixed timestamp
        consumer_instance.handlers = [MagicMock(), MagicMock()]

        with patch("time.time", return_value=10):  # 10 seconds uptime
            metrics = consumer_instance.get_metrics()

            assert metrics["events_processed"] == 100
            assert metrics["events_failed"] == 10
            assert metrics["total_events"] == 110
            assert metrics["avg_processing_time_ms"] == 50.0  # 5000 / 100
            assert metrics["events_per_second"] == 10.0  # 100 / 10
            assert metrics["uptime_seconds"] == 10
            assert metrics["handlers_registered"] == 2

    def test_health_status_healthy(self, consumer_instance):
        """Test health status when consumer is healthy"""
        consumer_instance.running = True
        consumer_instance.metrics["events_processed"] = 100
        consumer_instance.metrics["events_failed"] = 5
        consumer_instance.metrics["last_event_timestamp"] = 100
        consumer_instance.metrics["consumer_started_at"] = 0

        with patch("time.time", return_value=120):  # Recent activity
            health = consumer_instance.get_health()

            assert health["status"] == "healthy"
            assert health["is_running"] == True
            assert health["error_rate_percent"] < 10

    def test_health_status_degraded_high_error_rate(self, consumer_instance):
        """Test health status with high error rate"""
        consumer_instance.running = True
        consumer_instance.metrics["events_processed"] = 40
        consumer_instance.metrics["events_failed"] = 60  # 60% error rate

        health = consumer_instance.get_health()

        assert health["status"] == "degraded"
        assert health["error_rate_percent"] > 50

    def test_health_status_unhealthy_not_running(self, consumer_instance):
        """Test health status when consumer is not running"""
        consumer_instance.running = False

        health = consumer_instance.get_health()

        assert health["status"] == "unhealthy"
        assert health["is_running"] == False

    @pytest.mark.asyncio
    async def test_consumer_start(self, consumer_instance):
        """Test consumer start creates background task"""
        with patch("src.kafka_consumer.Consumer"):
            await consumer_instance.initialize()

        # Mock consumer loop to prevent blocking
        consumer_instance._consumer_loop = AsyncMock()

        await consumer_instance.start()

        assert consumer_instance.running == True
        assert consumer_instance._consumer_task is not None

    @pytest.mark.asyncio
    async def test_consumer_stop(self, consumer_instance):
        """Test consumer stop gracefully shuts down"""
        with patch("src.kafka_consumer.Consumer"):
            await consumer_instance.initialize()
            consumer_instance.consumer = MagicMock()

        consumer_instance.running = True
        consumer_instance._consumer_task = AsyncMock()
        consumer_instance._consumer_task.done.return_value = False
        consumer_instance._consumer_task.cancel = MagicMock()

        # Mock handler shutdown
        for handler in consumer_instance.handlers:
            handler._shutdown_publisher = AsyncMock()

        await consumer_instance.stop()

        assert consumer_instance.running == False
        consumer_instance.consumer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handlers(self, consumer_instance):
        """Test handler shutdown is called"""
        # Create mock handlers with shutdown method
        mock_handler1 = MagicMock()
        mock_handler1._shutdown_publisher = AsyncMock()
        mock_handler1.get_handler_name = MagicMock(return_value="Handler1")

        mock_handler2 = MagicMock()
        mock_handler2._shutdown_publisher = AsyncMock()
        mock_handler2.get_handler_name = MagicMock(return_value="Handler2")

        consumer_instance.handlers = [mock_handler1, mock_handler2]

        await consumer_instance._shutdown_handlers()

        mock_handler1._shutdown_publisher.assert_called_once()
        mock_handler2._shutdown_publisher.assert_called_once()


class TestFactoryFunctions:
    """Test factory functions for consumer creation"""

    @patch.dict(
        "os.environ",
        {
            "KAFKA_BOOTSTRAP_SERVERS": "test-server:9092",
            "KAFKA_CONSUMER_GROUP": "test-group",
            "KAFKA_CODEGEN_VALIDATE_REQUEST": "test.validate.v1",
            "KAFKA_CODEGEN_ANALYZE_REQUEST": "test.analyze.v1",
            "KAFKA_CODEGEN_PATTERN_REQUEST": "test.pattern.v1",
            "KAFKA_CODEGEN_MIXIN_REQUEST": "test.mixin.v1",
        },
    )
    def test_create_intelligence_kafka_consumer_from_env(self):
        """Test consumer creation from environment variables"""
        consumer = create_intelligence_kafka_consumer()

        assert consumer.bootstrap_servers == "test-server:9092"
        assert consumer.consumer_group == "test-group"
        assert len(consumer.topics) == 4
        assert "test.validate.v1" in consumer.topics

    def test_get_kafka_consumer_singleton(self):
        """Test singleton pattern for consumer"""
        # Reset singleton
        import src.kafka_consumer

        src.kafka_consumer._consumer_instance = None

        consumer1 = get_kafka_consumer()
        consumer2 = get_kafka_consumer()

        assert consumer1 is consumer2


class TestBackpressureHandling:
    """Test suite for backpressure mechanism"""

    @pytest.fixture
    def consumer_with_backpressure(self):
        """Create consumer instance with low max_in_flight for testing"""
        return IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="backpressure-test",
            max_in_flight=3,  # Low limit to trigger backpressure easily
        )

    def test_semaphore_initialization(self, consumer_with_backpressure):
        """Test semaphore is initialized with correct max_in_flight"""
        assert consumer_with_backpressure.max_in_flight == 3
        assert consumer_with_backpressure._semaphore._value == 3
        assert consumer_with_backpressure._current_in_flight == 0

    def test_backpressure_metrics_initialization(self, consumer_with_backpressure):
        """Test backpressure metrics are initialized"""
        metrics = consumer_with_backpressure.metrics
        assert "max_in_flight_reached" in metrics
        assert "total_backpressure_wait_time_ms" in metrics
        assert "current_in_flight" in metrics
        assert "max_concurrent_events" in metrics
        assert metrics["max_in_flight_reached"] == 0
        assert metrics["total_backpressure_wait_time_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_processing(
        self, consumer_with_backpressure
    ):
        """Test semaphore limits concurrent event processing"""
        # Setup mock handler with slow processing
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)

        # Create a handler that takes time to process
        processing_started = []
        processing_finished = []

        async def slow_handler(event_data):
            processing_started.append(event_data["correlation_id"])
            await asyncio.sleep(0.1)  # Simulate processing time
            processing_finished.append(event_data["correlation_id"])
            return True

        mock_handler.handle_event = slow_handler
        consumer_with_backpressure.handlers = [mock_handler]

        # Create multiple mock messages
        messages = []
        for i in range(5):  # More than max_in_flight (3)
            mock_message = MagicMock()
            event_data = {
                "event_type": "codegen.request.validate",
                "correlation_id": f"test-{i}",
                "payload": {"code_content": "test"},
            }
            mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
            mock_message.topic.return_value = "test.topic.v1"
            mock_message.partition.return_value = 0
            mock_message.offset.return_value = i
            messages.append(mock_message)

        # Process all messages concurrently
        tasks = [consumer_with_backpressure._process_message(msg) for msg in messages]
        await asyncio.gather(*tasks)

        # Verify backpressure was applied (more events than max_in_flight)
        assert consumer_with_backpressure.metrics["max_in_flight_reached"] > 0
        assert (
            consumer_with_backpressure.metrics["max_concurrent_events"] <= 3
        )  # Should not exceed limit

    @pytest.mark.asyncio
    async def test_backpressure_wait_time_tracking(self, consumer_with_backpressure):
        """Test backpressure wait time is tracked"""
        # Setup mock handler with slow processing
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)

        async def slow_handler(event_data):
            await asyncio.sleep(0.05)
            return True

        mock_handler.handle_event = slow_handler
        consumer_with_backpressure.handlers = [mock_handler]

        # Create messages that will trigger backpressure
        messages = []
        for i in range(5):
            mock_message = MagicMock()
            event_data = {
                "event_type": "codegen.request.validate",
                "correlation_id": f"test-{i}",
                "payload": {},
            }
            mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
            mock_message.topic.return_value = "test.topic.v1"
            mock_message.partition.return_value = 0
            mock_message.offset.return_value = i
            messages.append(mock_message)

        # Process messages
        tasks = [consumer_with_backpressure._process_message(msg) for msg in messages]
        await asyncio.gather(*tasks)

        # Verify wait time was tracked
        if consumer_with_backpressure.metrics["max_in_flight_reached"] > 0:
            assert (
                consumer_with_backpressure.metrics["total_backpressure_wait_time_ms"]
                > 0
            )

    @pytest.mark.asyncio
    async def test_current_in_flight_tracking(self, consumer_with_backpressure):
        """Test current in-flight count is tracked correctly"""
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)

        # Track in-flight counts during processing
        observed_in_flight_counts = []

        async def tracking_handler(event_data):
            observed_in_flight_counts.append(
                consumer_with_backpressure.metrics["current_in_flight"]
            )
            await asyncio.sleep(0.02)
            return True

        mock_handler.handle_event = tracking_handler
        consumer_with_backpressure.handlers = [mock_handler]

        # Process multiple messages
        messages = []
        for i in range(3):
            mock_message = MagicMock()
            event_data = {
                "event_type": "codegen.request.validate",
                "correlation_id": f"test-{i}",
                "payload": {},
            }
            mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
            mock_message.topic.return_value = "test.topic.v1"
            mock_message.partition.return_value = 0
            mock_message.offset.return_value = i
            messages.append(mock_message)

        # Process concurrently
        tasks = [consumer_with_backpressure._process_message(msg) for msg in messages]
        await asyncio.gather(*tasks)

        # After processing, in-flight should be 0
        assert consumer_with_backpressure.metrics["current_in_flight"] == 0

        # Max concurrent should have been tracked
        assert consumer_with_backpressure.metrics["max_concurrent_events"] > 0

    def test_backpressure_metrics_in_get_metrics(self, consumer_with_backpressure):
        """Test backpressure metrics are included in get_metrics()"""
        # Set some test data
        consumer_with_backpressure.metrics["events_processed"] = 10
        consumer_with_backpressure.metrics["max_in_flight_reached"] = 5
        consumer_with_backpressure.metrics["total_backpressure_wait_time_ms"] = 250.0
        consumer_with_backpressure.metrics["consumer_started_at"] = 0

        with patch("time.time", return_value=10):
            metrics = consumer_with_backpressure.get_metrics()

            # Verify backpressure metrics are present
            assert "max_in_flight_reached" in metrics
            assert "total_backpressure_wait_time_ms" in metrics
            assert "current_in_flight" in metrics
            assert "max_concurrent_events" in metrics
            assert "avg_backpressure_wait_ms" in metrics
            assert "backpressure_percentage" in metrics
            assert "max_in_flight_limit" in metrics

            # Verify calculations
            assert metrics["avg_backpressure_wait_ms"] == 50.0  # 250 / 5
            assert metrics["backpressure_percentage"] == 50.0  # 5 / 10 * 100
            assert metrics["max_in_flight_limit"] == 3

    @patch.dict(
        "os.environ",
        {
            "KAFKA_BOOTSTRAP_SERVERS": "test-server:9092",
            "KAFKA_CONSUMER_GROUP": "test-group",
            "KAFKA_MAX_IN_FLIGHT": "50",  # Custom backpressure limit
        },
    )
    def test_max_in_flight_from_environment(self):
        """Test max_in_flight configuration from environment variable"""
        consumer = create_intelligence_kafka_consumer()

        assert consumer.max_in_flight == 50
        assert consumer._semaphore._value == 50

    @pytest.mark.asyncio
    async def test_backpressure_with_handler_failure(self, consumer_with_backpressure):
        """Test backpressure tracking continues even when handler fails"""
        mock_handler = MagicMock()
        mock_handler.can_handle = MagicMock(return_value=True)
        mock_handler.handle_event = AsyncMock(side_effect=Exception("Handler failed"))
        consumer_with_backpressure.handlers = [mock_handler]

        # Create mock message
        mock_message = MagicMock()
        event_data = {"event_type": "codegen.request.validate", "payload": {}}
        mock_message.value.return_value = json.dumps(event_data).encode("utf-8")
        mock_message.topic.return_value = "test.topic.v1"
        mock_message.partition.return_value = 0
        mock_message.offset.return_value = 0

        # Process message (should fail but not crash)
        with pytest.raises(Exception):
            await consumer_with_backpressure._process_message(mock_message)

        # Verify in-flight count was decremented even after failure
        assert consumer_with_backpressure.metrics["current_in_flight"] == 0


class TestIntegrationScenarios:
    """Integration test scenarios"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_consumer_lifecycle(self):
        """Test complete consumer lifecycle"""
        consumer = IntelligenceKafkaConsumer(
            bootstrap_servers="localhost:19092",
            topics=["test.topic.v1"],
            consumer_group="integration-test",
        )

        try:
            # Initialize
            with patch("src.kafka_consumer.Consumer"):
                await consumer.initialize()

            assert len(consumer.handlers) == 4

            # Start (mock the loop)
            consumer._consumer_loop = AsyncMock()
            await consumer.start()
            assert consumer.running == True

            # Get metrics
            metrics = consumer.get_metrics()
            assert "events_processed" in metrics

            # Get health
            health = consumer.get_health()
            assert "status" in health

            # Stop
            consumer.consumer = MagicMock()
            for handler in consumer.handlers:
                handler._shutdown_publisher = AsyncMock()
            await consumer.stop()
            assert consumer.running == False

        except Exception as e:
            pytest.fail(f"Integration test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
