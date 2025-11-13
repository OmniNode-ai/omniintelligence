"""
Comprehensive tests for intelligence-consumer main service orchestrator.

Tests:
- IntelligenceConsumerService initialization
- Service lifecycle (start, stop, run)
- Event processing (enrichment, code-analysis, batch)
- Event validation and invalid event handling
- Error handling and DLQ routing
- Health checks and metrics
- Circuit breaker integration
- Graceful shutdown

Coverage Target: 50%+ of main.py (289 lines)
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from src.main import IntelligenceConsumerService, main


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock()
    config.instance_id = "test-instance-123"
    config.kafka_bootstrap_servers = "localhost:9092"
    config.enrichment_topic = "test.enrichment"
    config.intelligence_service_url = "http://localhost:8053"
    config.intelligence_timeout = 60
    config.circuit_breaker_threshold = 5
    config.circuit_breaker_timeout = 30
    config.circuit_breaker_success_threshold = 3
    config.shutdown_timeout = 10
    config.retry_backoff_base = 2
    config.retry_backoff_max = 60
    config.log_level = "INFO"
    config.log_format = "json"
    return config


@pytest.fixture
def mock_intelligence_client():
    """Mock intelligence service client."""
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.process_document = AsyncMock(
        return_value={
            "entities": [{"entity_type": "function", "name": "test_func"}],
            "patterns": ["pattern1"],
            "quality_score": 0.85,
        }
    )
    client.assess_code = AsyncMock(
        return_value={
            "quality_score": 0.80,
            "issues": [],
            "recommendations": [],
        }
    )
    client.health_check = AsyncMock(return_value=True)
    client.circuit_state = "closed"
    return client


@pytest.fixture
def mock_consumer():
    """Mock enrichment consumer."""
    consumer = AsyncMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer.consume_loop = AsyncMock()
    consumer.publish_completion_event = AsyncMock()
    consumer.publish_code_analysis_completion = AsyncMock()
    consumer.publish_code_analysis_failure = AsyncMock()
    consumer.publish_dlq_event = AsyncMock()
    consumer.get_consumer_lag = AsyncMock(return_value={"partition-0": 10})
    consumer.running = True
    return consumer


@pytest.fixture
def mock_error_handler():
    """Mock error handler."""
    handler = Mock()
    handler.handle_error = AsyncMock()
    handler.get_stats = Mock(return_value={"total_errors": 5, "retries_attempted": 2})
    return handler


@pytest.fixture
def service(mock_config):
    """Create service instance with mocked config."""
    with patch("src.main.get_config", return_value=mock_config):
        return IntelligenceConsumerService()


class TestIntelligenceConsumerServiceInitialization:
    """Test service initialization."""

    def test_service_initializes_with_correct_state(self, service, mock_config):
        """Test that service initializes with correct default state."""
        assert service.config == mock_config
        assert service.intelligence_client is None
        assert service.error_handler is None
        assert service.consumer is None
        assert service.health_server is None
        assert not service.shutdown_event.is_set()
        assert service.invalid_events_skipped == 0
        assert service.invalid_events_by_reason == {}

    def test_service_binds_logger_with_instance_id(self, service, mock_config):
        """Test that logger is bound with instance ID."""
        assert service.logger is not None
        # Logger should have bound context
        assert hasattr(service.logger, "_context")


class TestServiceLifecycle:
    """Test service lifecycle management."""

    @pytest.mark.asyncio
    async def test_service_starts_successfully(
        self,
        service,
        mock_intelligence_client,
        mock_consumer,
        mock_error_handler,
    ):
        """Test that service starts all components."""
        with (
            patch(
                "src.main.IntelligenceServiceClient",
                return_value=mock_intelligence_client,
            ),
            patch("src.main.EnrichmentConsumer", return_value=mock_consumer),
            patch("src.main.ErrorHandler", return_value=mock_error_handler),
            patch("src.main.run_health_server", new_callable=AsyncMock) as mock_health,
        ):
            mock_health_server = Mock()
            mock_health.return_value = mock_health_server

            await service.start()

            # Verify components started
            mock_intelligence_client.start.assert_called_once()
            assert service.intelligence_client == mock_intelligence_client
            assert service.error_handler == mock_error_handler
            assert service.consumer == mock_consumer
            assert service.health_server == mock_health_server
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_stops_gracefully(
        self,
        service,
        mock_intelligence_client,
        mock_consumer,
    ):
        """Test that service stops all components gracefully."""
        # Setup running service
        service.consumer = mock_consumer
        service.intelligence_client = mock_intelligence_client
        health_server = AsyncMock()
        service.health_server = health_server

        await service.stop()

        # Verify cleanup sequence
        mock_consumer.stop.assert_called_once()
        mock_intelligence_client.stop.assert_called_once()
        health_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_run_waits_for_consumer_startup(self, service, mock_consumer):
        """Test that run() waits for consumer to be ready."""
        service.consumer = mock_consumer
        service.consumer.running = False

        async def set_running_after_delay():
            await asyncio.sleep(0.1)
            service.consumer.running = True

        # Start background task to set running flag
        asyncio.create_task(set_running_after_delay())

        # Start run in background
        run_task = asyncio.create_task(service.run())

        # Wait briefly and then trigger shutdown
        await asyncio.sleep(0.2)
        service.shutdown_event.set()

        # Wait for run to complete
        try:
            await asyncio.wait_for(run_task, timeout=2.0)
        except asyncio.TimeoutError:
            run_task.cancel()
            pytest.fail("run() did not complete in time")

        mock_consumer.consume_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_run_raises_if_consumer_fails_to_start(
        self, service, mock_consumer
    ):
        """Test that run() raises if consumer doesn't start within timeout."""
        service.consumer = mock_consumer
        service.consumer.running = False  # Never becomes ready

        # Mock time.time() to simulate timeout without actually waiting
        with patch("src.main.time.time") as mock_time:
            # Return sequence: start (0), check 1 (301 - past timeout)
            mock_time.side_effect = [
                0,
                301,
                301,
                301,
                301,
            ]  # Multiple values in case of extra calls

            with pytest.raises(RuntimeError, match="Consumer failed to start"):
                await service.run()


class TestEventValidation:
    """Test event schema validation."""

    def test_is_valid_event_schema_rejects_non_dict(self, service):
        """Test validation rejects non-dictionary events."""
        is_valid, error = service._is_valid_event_schema("not a dict", "test.topic")
        assert not is_valid
        assert "not a dictionary" in error

    def test_is_valid_event_schema_rejects_missing_payload(self, service):
        """Test validation rejects events without payload."""
        event_data = {"event_type": "test"}
        is_valid, error = service._is_valid_event_schema(event_data, "test.topic")
        assert not is_valid
        assert "payload" in error.lower() or "missing" in error.lower()

    def test_is_valid_event_schema_accepts_valid_enrichment_event_individual(
        self, service
    ):
        """Test validation accepts valid individual enrichment event."""
        event_data = {
            "payload": {
                "file_path": "/path/to/file.py",
                "content": "print('hello')",
                "project_name": "test-project",
            }
        }
        is_valid, error = service._is_valid_event_schema(event_data, "test.enrichment")
        assert is_valid
        assert error == ""

    def test_is_valid_event_schema_accepts_valid_enrichment_event_batch(self, service):
        """Test validation accepts valid batch enrichment event."""
        event_data = {
            "payload": {
                "files": [
                    {"file_path": "/path/to/file.py", "content": "print('hello')"}
                ],
                "project_name": "test-project",
            }
        }
        is_valid, error = service._is_valid_event_schema(event_data, "test.enrichment")
        assert is_valid
        assert error == ""

    def test_is_valid_event_schema_accepts_valid_code_analysis_event(self, service):
        """Test validation accepts valid code-analysis event."""
        event_data = {
            "event_type": "code_analysis_requested",
            "payload": {
                "source_path": "/path/to/file.py",
                "content": "print('hello')",
            },
        }
        is_valid, error = service._is_valid_event_schema(
            event_data, "test.code-analysis-requested"
        )
        assert is_valid
        assert error == ""

    def test_is_valid_event_schema_rejects_enrichment_missing_fields(self, service):
        """Test validation rejects enrichment event missing required fields."""
        event_data = {
            "payload": {
                "file_path": "/path/to/file.py",
                # Missing content and project_name
            }
        }
        is_valid, error = service._is_valid_event_schema(event_data, "test.enrichment")
        assert not is_valid
        assert "missing required fields" in error.lower()

    def test_is_valid_event_schema_rejects_code_analysis_missing_fields(self, service):
        """Test validation rejects code-analysis event missing required fields."""
        event_data = {
            "event_type": "code_analysis_requested",
            "payload": {
                "source_path": "/path/to/file.py",
                # Missing content
            },
        }
        is_valid, error = service._is_valid_event_schema(
            event_data, "test.code-analysis-requested"
        )
        assert not is_valid
        assert "missing required fields" in error.lower()


class TestMessageProcessing:
    """Test message routing and processing."""

    @pytest.mark.asyncio
    async def test_process_message_skips_invalid_events(self, service):
        """Test that invalid events are skipped and tracked."""
        event_data = {"payload": {}}  # Invalid: missing required fields
        topic = "test.enrichment"

        await service._process_message(event_data, topic)

        assert service.invalid_events_skipped == 1
        assert len(service.invalid_events_by_reason) > 0

    @pytest.mark.asyncio
    async def test_process_message_routes_to_enrichment_handler(self, service):
        """Test that enrichment events are routed correctly."""
        event_data = {
            "correlation_id": "test-123",
            "event_type": "enrichment",
            "payload": {
                "file_path": "/path/to/file.py",
                "content": "print('hello')",
                "project_name": "test-project",
            },
        }
        topic = "test.enrichment"

        with patch.object(
            service, "_process_enrichment_event", new_callable=AsyncMock
        ) as mock_process:
            await service._process_message(event_data, topic)
            mock_process.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_process_message_routes_to_code_analysis_handler(self, service):
        """Test that code-analysis events are routed correctly."""
        event_data = {
            "correlation_id": "test-123",
            "event_type": "code_analysis_requested",
            "payload": {
                "source_path": "/path/to/file.py",
                "content": "print('hello')",
            },
        }
        topic = "test.code-analysis-requested"

        with patch.object(
            service, "_process_code_analysis_event", new_callable=AsyncMock
        ) as mock_process:
            await service._process_message(event_data, topic)
            mock_process.assert_called_once_with(event_data)


class TestEnrichmentEventProcessing:
    """Test enrichment event processing."""

    @pytest.mark.asyncio
    async def test_process_individual_file_event_succeeds(
        self, service, mock_intelligence_client, mock_consumer
    ):
        """Test processing individual file event."""
        service.intelligence_client = mock_intelligence_client
        service.consumer = mock_consumer

        event_data = {
            "correlation_id": "test-123",
            "event_type": "enrichment",
            "payload": {
                "file_path": "/path/to/file.py",
                "content": "print('hello')",
                "project_name": "test-project",
            },
        }

        await service._process_enrichment_event(event_data)

        mock_intelligence_client.process_document.assert_called_once()
        mock_consumer.publish_completion_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_batch_event_succeeds(
        self, service, mock_intelligence_client, mock_consumer
    ):
        """Test processing batch enrichment event."""
        service.intelligence_client = mock_intelligence_client
        service.consumer = mock_consumer

        event_data = {
            "correlation_id": "test-123",
            "event_type": "batch_enrichment",
            "payload": {
                "project_name": "test-project",
                "files": [
                    {"file_path": "/file1.py", "content": "print('1')"},
                    {"file_path": "/file2.py", "content": "print('2')"},
                ],
            },
        }

        await service._process_enrichment_event(event_data)

        # Should process both files
        assert mock_intelligence_client.process_document.call_count == 2
        assert mock_consumer.publish_completion_event.call_count == 2

    @pytest.mark.asyncio
    async def test_process_batch_event_partial_failure(
        self, service, mock_intelligence_client, mock_consumer
    ):
        """Test batch processing with partial failures."""
        service.intelligence_client = mock_intelligence_client
        service.consumer = mock_consumer

        # First call succeeds, second fails
        mock_intelligence_client.process_document.side_effect = [
            {"entities": [], "patterns": []},
            Exception("Processing failed"),
        ]

        event_data = {
            "correlation_id": "test-123",
            "payload": {
                "project_name": "test-project",
                "files": [
                    {"file_path": "/file1.py", "content": "print('1')"},
                    {"file_path": "/file2.py", "content": "print('2')"},
                ],
            },
        }

        # Should not raise exception (partial success)
        await service._process_enrichment_event(event_data)

        assert mock_intelligence_client.process_document.call_count == 2


class TestCodeAnalysisEventProcessing:
    """Test code-analysis event processing."""

    @pytest.mark.asyncio
    async def test_process_code_analysis_event_succeeds(
        self, service, mock_intelligence_client, mock_consumer
    ):
        """Test processing code-analysis event."""
        service.intelligence_client = mock_intelligence_client
        service.consumer = mock_consumer

        event_data = {
            "correlation_id": "test-123",
            "event_type": "code_analysis_requested",
            "payload": {
                "source_path": "/path/to/file.py",
                "content": "print('hello')",
                "language": "python",
            },
        }

        await service._process_code_analysis_event(event_data)

        mock_intelligence_client.assess_code.assert_called_once()
        mock_consumer.publish_code_analysis_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_code_analysis_event_handles_failure(
        self, service, mock_intelligence_client, mock_consumer
    ):
        """Test code-analysis event failure handling."""
        service.intelligence_client = mock_intelligence_client
        service.consumer = mock_consumer

        mock_intelligence_client.assess_code.side_effect = Exception("Analysis failed")

        event_data = {
            "correlation_id": "test-123",
            "event_type": "code_analysis_requested",
            "payload": {
                "source_path": "/path/to/file.py",
                "content": "print('hello')",
            },
        }

        with pytest.raises(Exception, match="Analysis failed"):
            await service._process_code_analysis_event(event_data)

        mock_consumer.publish_code_analysis_failure.assert_called_once()


class TestErrorHandling:
    """Test error handling and DLQ routing."""

    @pytest.mark.asyncio
    async def test_handle_processing_error_delegates_to_error_handler(
        self, service, mock_error_handler
    ):
        """Test error handling delegates to error handler."""
        service.error_handler = mock_error_handler

        error = Exception("Processing failed")
        event_data = {"correlation_id": "test-123"}

        await service._handle_processing_error(error, event_data)

        mock_error_handler.handle_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_to_dlq(self, service, mock_consumer):
        """Test DLQ event publishing."""
        service.consumer = mock_consumer

        error = Exception("Test error")
        event_data = {"correlation_id": "test-123"}

        await service._publish_to_dlq(
            original_event=event_data,
            error=error,
            retry_count=3,
            error_details={"reason": "timeout"},
        )

        mock_consumer.publish_dlq_event.assert_called_once()


class TestHealthChecks:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_check_consumer_health_when_running(self, service, mock_consumer):
        """Test consumer health check when running."""
        service.consumer = mock_consumer
        service.consumer.running = True

        is_healthy = await service._check_consumer_health()
        assert is_healthy

    @pytest.mark.asyncio
    async def test_check_consumer_health_when_not_running(self, service):
        """Test consumer health check when not running."""
        service.consumer = None

        is_healthy = await service._check_consumer_health()
        assert not is_healthy

    @pytest.mark.asyncio
    async def test_get_consumer_lag_safe_returns_empty_when_no_consumer(self, service):
        """Test consumer lag returns empty dict when consumer not initialized."""
        service.consumer = None

        lag = await service._get_consumer_lag_safe()
        assert lag == {}

    @pytest.mark.asyncio
    async def test_get_consumer_lag_safe_returns_lag_when_available(
        self, service, mock_consumer
    ):
        """Test consumer lag returns actual lag when available."""
        service.consumer = mock_consumer
        mock_consumer.get_consumer_lag.return_value = {"partition-0": 10}

        lag = await service._get_consumer_lag_safe()
        assert lag == {"partition-0": 10}

    def test_get_invalid_event_stats(self, service):
        """Test invalid event statistics."""
        service.invalid_events_skipped = 5
        service.invalid_events_by_reason = {
            "Missing file_path": 3,
            "Missing content": 2,
        }

        stats = service._get_invalid_event_stats()

        assert stats["total_skipped"] == 5
        assert len(stats["by_reason"]) == 2


class TestGracefulShutdown:
    """Test graceful shutdown handling."""

    def test_handle_shutdown_signal(self, service):
        """Test shutdown signal sets shutdown event."""
        import signal

        assert not service.shutdown_event.is_set()

        service.handle_shutdown_signal(signal.SIGTERM)

        assert service.shutdown_event.is_set()


class TestMainEntryPoint:
    """Test main entry point."""

    @pytest.mark.asyncio
    async def test_main_starts_and_stops_service(self, mock_config):
        """Test main() starts service and handles lifecycle."""
        with (
            patch("src.main.get_config", return_value=mock_config),
            patch("src.main.IntelligenceConsumerService") as mock_service_class,
            patch("src.main.asyncio.get_running_loop") as mock_loop,
        ):
            mock_service = AsyncMock()
            mock_service.start = AsyncMock()
            mock_service.stop = AsyncMock()
            mock_service.run = AsyncMock()
            mock_service.handle_shutdown_signal = Mock()
            mock_service_class.return_value = mock_service

            mock_event_loop = Mock()
            mock_loop.return_value = mock_event_loop

            # Run main (will start then immediately stop due to mocks)
            try:
                await asyncio.wait_for(main(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

            mock_service.start.assert_called_once()
