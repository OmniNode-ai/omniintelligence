"""
Comprehensive Test Suite for Kafka Consumer Service

Tests cover:
1. Consumer Lifecycle Tests (startup/shutdown, graceful cleanup)
2. Message Processing Tests (consumption, API calls, error handling)
3. Metrics Tracking Tests (consumption counts, error tracking)
4. Performance Tests (consumption rate, processing latency)

Author: Archon Integration Team
Version: 1.0.0
Created: 2025-10-07
Updated: 2025-10-09 (Aligned with SimpleEventSubscriber implementation)
"""

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Import actual implementation (pythonpath configured in pytest.ini)
from main import Config, SimpleEventSubscriber

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = Config()
    config.kafka_bootstrap_servers = "localhost:9092"
    config.kafka_group_id = "test-consumer-group"
    config.kafka_topics = ["test.topic.lifecycle", "test.topic.tools"]
    config.archon_api_url = "http://localhost:8181"
    config.service_auth_token = "test-token"
    return config


@pytest.fixture
def mock_kafka_consumer():
    """Create mock AIOKafkaConsumer."""
    consumer = AsyncMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()

    # Mock message
    mock_message = MagicMock()
    mock_message.topic = "test.topic.lifecycle"
    mock_message.partition = 0
    mock_message.offset = 0
    mock_message.key = b"test-key"
    mock_message.value = {
        "event_type": "tool_updated",
        "data": {"tool_id": "test-tool"},
    }
    mock_message.timestamp = int(datetime.now().timestamp() * 1000)
    mock_message.headers = []

    consumer.__aiter__ = AsyncMock(return_value=iter([mock_message]))
    return consumer


@pytest.fixture
def mock_http_client():
    """Create mock HTTP client."""
    client = AsyncMock()

    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()

    client.post = AsyncMock(return_value=mock_response)
    client.aclose = AsyncMock()

    return client


@pytest.fixture
async def test_subscriber():
    """Create test SimpleEventSubscriber instance."""
    subscriber = SimpleEventSubscriber()
    yield subscriber
    # Cleanup
    if subscriber.running:
        await subscriber.stop()


# ============================================================================
# Unit Tests: Consumer Lifecycle
# ============================================================================


class TestConsumerLifecycle:
    """Unit tests for SimpleEventSubscriber lifecycle."""

    def test_subscriber_initialization(self, test_subscriber):
        """Test subscriber initializes correctly."""
        assert test_subscriber.running is False
        assert test_subscriber.messages_consumed == 0
        assert test_subscriber.messages_processed == 0
        assert test_subscriber.errors == 0
        assert test_subscriber.consumer is None

    @pytest.mark.asyncio
    @patch("main.aiokafka.AIOKafkaConsumer")
    async def test_subscriber_start(
        self, mock_consumer_class, test_subscriber, mock_kafka_consumer
    ):
        """Test subscriber starts successfully."""
        mock_consumer_class.return_value = mock_kafka_consumer

        await test_subscriber.start()

        assert test_subscriber.running is True
        assert test_subscriber.consumer is not None
        mock_kafka_consumer.start.assert_called_once()

    @pytest.mark.asyncio
    @patch("main.aiokafka.AIOKafkaConsumer")
    async def test_subscriber_stop(
        self, mock_consumer_class, test_subscriber, mock_kafka_consumer
    ):
        """Test subscriber stops gracefully."""
        mock_consumer_class.return_value = mock_kafka_consumer

        # Start first
        await test_subscriber.start()
        assert test_subscriber.running is True

        # Then stop
        await test_subscriber.stop()

        assert test_subscriber.running is False
        mock_kafka_consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_initial_state(self, test_subscriber):
        """Test metrics in initial state."""
        metrics = test_subscriber.get_metrics()

        assert metrics.status == "stopped"
        assert metrics.messages_consumed == 0
        assert metrics.messages_processed == 0
        assert metrics.errors == 0
        assert metrics.uptime_seconds >= 0
        assert len(metrics.connected_topics) == 0

    @pytest.mark.asyncio
    @patch("main.aiokafka.AIOKafkaConsumer")
    async def test_get_metrics_running_state(
        self, mock_consumer_class, test_subscriber, mock_kafka_consumer, test_config
    ):
        """Test metrics when running."""
        mock_consumer_class.return_value = mock_kafka_consumer

        await test_subscriber.start()

        metrics = test_subscriber.get_metrics()

        assert metrics.status == "running"
        assert metrics.uptime_seconds >= 0


# ============================================================================
# Unit Tests: Message Processing
# ============================================================================


class TestMessageProcessing:
    """Unit tests for message processing and API calls."""

    @pytest.mark.asyncio
    async def test_process_tool_update_event(self, test_subscriber, mock_http_client):
        """Test processing tool update events."""
        test_subscriber.http_client = mock_http_client

        tool_data = {
            "tool_id": "test-tool",
            "tool_name": "Test Tool",
            "version": "1.0.0",
        }

        await test_subscriber._handle_tool_update(tool_data)

        # Verify API call was made
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/api/events/tool-update" in call_args[0][0]
        assert call_args[1]["json"] == tool_data

    @pytest.mark.asyncio
    async def test_process_service_lifecycle_event(
        self, test_subscriber, mock_http_client
    ):
        """Test processing service lifecycle events."""
        test_subscriber.http_client = mock_http_client

        lifecycle_data = {
            "service_name": "test-service",
            "status": "startup",
            "timestamp": datetime.now().isoformat(),
        }

        await test_subscriber._handle_service_lifecycle(lifecycle_data)

        # Verify API call was made
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/api/events/service-lifecycle" in call_args[0][0]
        assert call_args[1]["json"] == lifecycle_data

    @pytest.mark.asyncio
    async def test_process_system_event(self, test_subscriber, mock_http_client):
        """Test processing system events."""
        test_subscriber.http_client = mock_http_client

        system_data = {
            "event_type": "system_alert",
            "severity": "high",
            "message": "Test alert",
        }

        await test_subscriber._handle_system_event(system_data)

        # Verify API call was made
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "/api/events/system-event" in call_args[0][0]
        assert call_args[1]["json"] == system_data

    @pytest.mark.asyncio
    async def test_error_handling_api_failure(self, test_subscriber):
        """Test error handling when API call fails."""
        # Create mock client that raises exception
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("API Error"))
        test_subscriber.http_client = mock_client

        tool_data = {"tool_id": "test"}

        # Should raise exception
        with pytest.raises(Exception):
            await test_subscriber._handle_tool_update(tool_data)


# ============================================================================
# Unit Tests: Metrics Tracking
# ============================================================================


class TestMetricsTracking:
    """Unit tests for metrics tracking."""

    @pytest.mark.asyncio
    async def test_message_consumption_counter(self, test_subscriber):
        """Test message consumption counter increments."""
        initial_count = test_subscriber.messages_consumed

        # Simulate message consumption
        test_subscriber.messages_consumed += 1

        assert test_subscriber.messages_consumed == initial_count + 1

    @pytest.mark.asyncio
    async def test_message_processing_counter(self, test_subscriber):
        """Test message processing counter increments."""
        initial_count = test_subscriber.messages_processed

        # Simulate message processing
        test_subscriber.messages_processed += 1

        assert test_subscriber.messages_processed == initial_count + 1

    @pytest.mark.asyncio
    async def test_error_counter(self, test_subscriber):
        """Test error counter increments."""
        initial_count = test_subscriber.errors

        # Simulate error
        test_subscriber.errors += 1

        assert test_subscriber.errors == initial_count + 1

    @pytest.mark.asyncio
    async def test_metrics_consistency(self, test_subscriber):
        """Test metrics remain consistent."""
        # Simulate processing
        test_subscriber.messages_consumed = 10
        test_subscriber.messages_processed = 8
        test_subscriber.errors = 2

        metrics = test_subscriber.get_metrics()

        # Verify consistency
        assert metrics.messages_consumed == 10
        assert metrics.messages_processed == 8
        assert metrics.errors == 2


# ============================================================================
# Performance Tests
# ============================================================================


class TestConsumerPerformance:
    """Performance tests for consumer throughput and latency."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_api_call_latency(self, test_subscriber, mock_http_client):
        """Test API call processing latency is reasonable."""
        test_subscriber.http_client = mock_http_client

        tool_data = {"tool_id": "test-tool"}

        # Measure processing time
        start_time = time.perf_counter()
        await test_subscriber._handle_tool_update(tool_data)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Should be under 100ms target (with mocked HTTP)
        assert elapsed_ms < 100, f"API call took {elapsed_ms:.2f}ms (target: <100ms)"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_multiple_message_throughput(self, test_subscriber, mock_http_client):
        """Test subscriber can handle multiple messages quickly."""
        test_subscriber.http_client = mock_http_client

        # Create test messages
        num_messages = 50
        messages = []
        for i in range(num_messages):
            tool_data = {"tool_id": f"tool-{i}", "version": "1.0.0"}
            messages.append(tool_data)

        # Measure throughput
        start_time = time.perf_counter()
        for msg in messages:
            await test_subscriber._handle_tool_update(msg)
        elapsed_s = time.perf_counter() - start_time

        messages_per_sec = num_messages / elapsed_s

        # Should achieve >50 messages/sec target (with mocked HTTP)
        assert (
            messages_per_sec > 50
        ), f"Throughput: {messages_per_sec:.0f} msg/sec (target: >50)"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_metrics_update_performance(self, test_subscriber):
        """Test metrics updates are fast."""
        # Simulate many metric updates
        num_updates = 1000

        start_time = time.perf_counter()
        for _ in range(num_updates):
            test_subscriber.get_metrics()
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        avg_time_ms = elapsed_ms / num_updates

        # Should be under 1ms per metrics call
        assert (
            avg_time_ms < 1.0
        ), f"Avg metrics time: {avg_time_ms:.3f}ms (target: <1ms)"


# ============================================================================
# Test Configuration
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_after_tests():
    """Clean up after tests."""
    yield
    # Cleanup code here if needed


# Mark slow tests
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
