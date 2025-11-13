"""
Unit tests for KafkaConsumerService including MVP Day 2 codegen handler registration.

Tests:
- Service initialization
- Handler registration (base handlers + codegen intelligence handlers)
- Intelligence service client creation
- Graceful degradation when handlers not available
- Status reporting

Created: 2025-10-14 (MVP Day 2)
Updated: 2025-10-14 - Added codegen handler tests
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import system under test
from src.server.services.kafka_consumer_service import (
    KafkaConsumerService,
    get_kafka_consumer_service,
)


@pytest.fixture
def consumer_service():
    """Create fresh KafkaConsumerService instance for testing."""
    return KafkaConsumerService()


@pytest.fixture
def mock_consumer():
    """Create mock consumer with registry."""
    consumer = Mock()
    consumer.registry = Mock()
    consumer.registry.register = Mock()
    consumer.registry.handlers = {}
    consumer.consumer_state = Mock()
    consumer.consumer_state.value = "running"
    consumer.metrics = {"messages_processed": 10}
    consumer.circuit_breaker = Mock()
    consumer.circuit_breaker.state = Mock()
    consumer.circuit_breaker.state.value = "closed"
    return consumer


@pytest.fixture
def mock_http_client():
    """Create mock HTTP client for intelligence services."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


class TestKafkaConsumerServiceInitialization:
    """Test service initialization and lifecycle."""

    def test_service_initializes_with_defaults(self, consumer_service):
        """Test that service initializes with correct default state."""
        assert consumer_service.consumer is None
        assert consumer_service._is_running is False
        assert consumer_service._http_client_manager is None
        assert consumer_service._langextract_client is None
        assert consumer_service._quality_scorer is None
        assert consumer_service._pattern_client is None

    def test_singleton_pattern(self):
        """Test that get_kafka_consumer_service returns same instance."""
        service1 = get_kafka_consumer_service()
        service2 = get_kafka_consumer_service()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_service_starts_successfully(self, consumer_service):
        """Test that service starts with proper configuration."""
        with (
            patch.object(consumer_service, "_load_consumer_config") as mock_load_config,
            patch.object(
                consumer_service, "_create_container"
            ) as mock_create_container,
            patch.object(
                consumer_service, "_register_default_handlers"
            ) as mock_register,
            patch(
                "src.server.services.kafka_consumer_service.NodeArchonKafkaConsumerEffect"
            ) as mock_consumer_class,
        ):

            # Setup mocks
            mock_config = Mock()
            mock_config.consumer_group = "test-group"
            mock_config.topic_patterns = ["test.topic.*"]
            mock_load_config.return_value = mock_config

            mock_container = Mock()
            mock_create_container.return_value = mock_container

            mock_consumer = AsyncMock()
            mock_consumer.start_consuming = AsyncMock()
            mock_consumer_class.return_value = mock_consumer

            # Start service
            await consumer_service.start()

            # Verify initialization sequence
            mock_load_config.assert_called_once()
            mock_create_container.assert_called_once()
            mock_consumer_class.assert_called_once_with(mock_container, mock_config)
            mock_register.assert_called_once()
            mock_consumer.start_consuming.assert_called_once()
            assert consumer_service._is_running is True

    @pytest.mark.asyncio
    async def test_service_stops_gracefully(self, consumer_service):
        """Test that service stops with proper cleanup."""
        # Setup running service
        mock_consumer = AsyncMock()
        mock_consumer.stop_consuming = AsyncMock()
        consumer_service.consumer = mock_consumer
        consumer_service._is_running = True

        # Stop service
        await consumer_service.stop()

        # Verify cleanup
        mock_consumer.stop_consuming.assert_called_once()
        assert consumer_service._is_running is False

    def test_get_status_when_stopped(self, consumer_service):
        """Test status reporting when service is stopped."""
        status = consumer_service.get_status()

        assert status["status"] == "stopped"
        assert status["is_running"] is False

    def test_get_status_when_running(self, consumer_service, mock_consumer):
        """Test status reporting when service is running."""
        consumer_service.consumer = mock_consumer
        consumer_service._is_running = True

        status = consumer_service.get_status()

        assert status["status"] == "running"
        assert status["is_running"] is True
        assert "metrics" in status
        assert "circuit_breaker_state" in status
        assert "handlers_registered" in status


class TestHandlerRegistration:
    """Test handler registration including codegen intelligence handlers."""

    @pytest.mark.asyncio
    async def test_register_base_handlers_only(self, consumer_service, mock_consumer):
        """Test that base handlers are registered when codegen handlers unavailable."""
        consumer_service.consumer = mock_consumer

        with patch(
            "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
            False,
        ):
            await consumer_service._register_default_handlers()

        # Verify base handlers registered (3 base handlers)
        assert mock_consumer.registry.register.call_count >= 3

    @pytest.mark.asyncio
    async def test_register_all_handlers_when_available(
        self, consumer_service, mock_consumer
    ):
        """Test that all 7 handlers are registered when codegen handlers available."""
        consumer_service.consumer = mock_consumer

        with (
            patch(
                "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
                True,
            ),
            patch.object(
                consumer_service, "_get_langextract_client", new_callable=AsyncMock
            ) as mock_langextract,
            patch.object(
                consumer_service, "_get_quality_scorer", new_callable=AsyncMock
            ) as mock_quality,
            patch.object(
                consumer_service, "_get_pattern_client", new_callable=AsyncMock
            ) as mock_pattern,
        ):

            # Setup mock clients
            mock_langextract.return_value = Mock()
            mock_quality.return_value = Mock()
            mock_pattern.return_value = Mock()

            await consumer_service._register_default_handlers()

        # Verify all handlers registered (3 base + 4 codegen = 7 total)
        assert mock_consumer.registry.register.call_count == 7

    @pytest.mark.asyncio
    async def test_handler_registration_fails_gracefully(
        self, consumer_service, mock_consumer
    ):
        """Test that handler registration continues even if codegen handlers fail."""
        consumer_service.consumer = mock_consumer

        with (
            patch(
                "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
                True,
            ),
            patch.object(
                consumer_service, "_get_langextract_client", new_callable=AsyncMock
            ) as mock_langextract,
        ):

            # Simulate failure in codegen handler registration
            mock_langextract.side_effect = Exception("Client creation failed")

            # Should not raise exception
            await consumer_service._register_default_handlers()

        # Base handlers should still be registered (3)
        assert mock_consumer.registry.register.call_count >= 3


class TestIntelligenceServiceClients:
    """Test intelligence service client creation and management."""

    @pytest.mark.asyncio
    async def test_get_http_client_manager_creates_once(self, consumer_service):
        """Test that HTTP client manager is created and cached."""
        with patch(
            "src.server.services.centralized_http_client_manager.get_http_client_manager",
            new_callable=AsyncMock,
        ) as mock_get_manager:
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager

            # First call creates
            manager1 = await consumer_service._get_http_client_manager()
            assert manager1 is mock_manager
            assert mock_get_manager.call_count == 1

            # Second call uses cache
            manager2 = await consumer_service._get_http_client_manager()
            assert manager2 is mock_manager
            assert mock_get_manager.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_get_langextract_client_creates_once(self, consumer_service):
        """Test that LangExtract client is created and cached."""
        with patch.object(
            consumer_service, "_get_http_client_manager", new_callable=AsyncMock
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_client = Mock()
            mock_manager.get_client = AsyncMock(return_value=mock_client)
            mock_get_manager.return_value = mock_manager

            # First call creates
            client1 = await consumer_service._get_langextract_client()
            assert client1 is mock_client
            assert mock_manager.get_client.call_count == 1

            # Second call uses cache
            client2 = await consumer_service._get_langextract_client()
            assert client2 is mock_client
            assert mock_manager.get_client.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_get_quality_scorer_creates_once(self, consumer_service):
        """Test that quality scorer is created and cached."""
        with (
            patch(
                "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
                True,
            ),
            patch(
                "src.server.services.kafka_consumer_service.ComprehensiveONEXScorer"
            ) as mock_scorer_class,
        ):
            mock_scorer = Mock()
            mock_scorer_class.return_value = mock_scorer

            # First call creates
            scorer1 = await consumer_service._get_quality_scorer()
            assert scorer1 is mock_scorer
            assert mock_scorer_class.call_count == 1

            # Second call uses cache
            scorer2 = await consumer_service._get_quality_scorer()
            assert scorer2 is mock_scorer
            assert mock_scorer_class.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_get_quality_scorer_returns_none_when_unavailable(
        self, consumer_service
    ):
        """Test that quality scorer returns None when handlers unavailable."""
        with patch(
            "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
            False,
        ):
            scorer = await consumer_service._get_quality_scorer()
            assert scorer is None

    @pytest.mark.asyncio
    async def test_get_pattern_client_creates_once(self, consumer_service):
        """Test that pattern learning client is created and cached."""
        with patch.object(
            consumer_service, "_get_http_client_manager", new_callable=AsyncMock
        ) as mock_get_manager:
            mock_manager = AsyncMock()
            mock_client = Mock()
            mock_manager.get_client = AsyncMock(return_value=mock_client)
            mock_get_manager.return_value = mock_manager

            # First call creates
            client1 = await consumer_service._get_pattern_client()
            assert client1 is mock_client
            assert mock_manager.get_client.call_count == 1

            # Second call uses cache
            client2 = await consumer_service._get_pattern_client()
            assert client2 is mock_client
            assert mock_manager.get_client.call_count == 1  # Not called again


class TestConfigurationLoading:
    """Test consumer configuration loading from contract YAML."""

    def test_load_config_from_contract_file(self, consumer_service):
        """Test that configuration is loaded from contract YAML."""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", create=True),
            patch("yaml.safe_load") as mock_yaml_load,
        ):

            # Mock contract YAML content
            mock_yaml_load.return_value = {
                "consumer_config": {
                    "bootstrap_servers": "kafka:9092",
                    "consumer_group": "test-consumer",
                    "topic_patterns": ["test.events.*"],
                    "auto_offset_reset": "earliest",
                    "enable_auto_commit": True,
                    "max_poll_records": 50,
                    "session_timeout_ms": 45000,
                    "max_concurrent_events": 10,
                    "circuit_breaker_enabled": True,
                    "failure_threshold": 3,
                    "timeout_seconds": 30,
                }
            }

            config = consumer_service._load_consumer_config()

            assert config.bootstrap_servers == "kafka:9092"
            assert config.consumer_group == "test-consumer"
            assert config.topic_patterns == ["test.events.*"]
            assert config.max_poll_records == 50

    def test_load_config_falls_back_to_defaults(self, consumer_service):
        """Test that configuration falls back to defaults when file missing."""
        with patch("pathlib.Path.exists", return_value=False):
            # Mock environment to clear KAFKA_BOOTSTRAP_SERVERS so we test the hardcoded default
            with patch.dict("os.environ", {}, clear=False):
                # Remove KAFKA_BOOTSTRAP_SERVERS if it exists
                if "KAFKA_BOOTSTRAP_SERVERS" in os.environ:
                    del os.environ["KAFKA_BOOTSTRAP_SERVERS"]

                config = consumer_service._load_consumer_config()

                # Should use defaults from ModelConsumerConfig (omninode-bridge-redpanda:9092 is the hardcoded default)
                assert config.bootstrap_servers == "omninode-bridge-redpanda:9092"
                assert config.consumer_group == "archon-consumer-group"


class TestContainerCreation:
    """Test ONEX container creation with Kafka client."""

    def test_create_container_with_kafka_client(self, consumer_service):
        """Test that container is created with registered Kafka client."""
        with (
            patch(
                "src.server.services.kafka_consumer_service.ONEXContainer"
            ) as mock_container_class,
            patch(
                "src.server.services.kafka_consumer_service.KafkaClient"
            ) as mock_kafka_client_class,
        ):

            mock_container = Mock()
            mock_container.register_service = Mock()
            mock_container_class.return_value = mock_container

            mock_kafka_client = Mock()
            mock_kafka_client_class.return_value = mock_kafka_client

            container = consumer_service._create_container()

            # Verify container created and Kafka client registered
            mock_container_class.assert_called_once()
            mock_kafka_client_class.assert_called_once()
            mock_container.register_service.assert_called_once_with(
                "kafka_client", mock_kafka_client
            )
            assert container is mock_container


@pytest.mark.integration
class TestKafkaConsumerServiceIntegration:
    """Integration tests for full consumer service lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_without_codegen_handlers(self, consumer_service):
        """Test complete start -> register -> stop lifecycle without codegen handlers."""
        with (
            patch(
                "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
                False,
            ),
            patch.object(consumer_service, "_load_consumer_config") as mock_load_config,
            patch.object(
                consumer_service, "_create_container"
            ) as mock_create_container,
            patch(
                "src.server.services.kafka_consumer_service.NodeArchonKafkaConsumerEffect"
            ) as mock_consumer_class,
        ):

            # Setup mocks
            mock_config = Mock()
            mock_config.consumer_group = "test-group"
            mock_config.topic_patterns = ["test.*"]
            mock_load_config.return_value = mock_config

            mock_container = Mock()
            mock_create_container.return_value = mock_container

            mock_consumer = AsyncMock()
            mock_consumer.start_consuming = AsyncMock()
            mock_consumer.stop_consuming = AsyncMock()
            mock_consumer.registry = Mock()
            mock_consumer.registry.register = Mock()
            mock_consumer.registry.handlers = []
            mock_consumer_class.return_value = mock_consumer

            # Start
            await consumer_service.start()
            assert consumer_service._is_running is True
            assert mock_consumer.registry.register.call_count == 3  # 3 base handlers

            # Stop
            await consumer_service.stop()
            assert consumer_service._is_running is False
            mock_consumer.stop_consuming.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_codegen_handlers(self, consumer_service):
        """Test complete start -> register -> stop lifecycle with codegen handlers."""
        with (
            patch(
                "src.server.services.kafka_consumer_service.CODEGEN_HANDLERS_AVAILABLE",
                True,
            ),
            patch.object(consumer_service, "_load_consumer_config") as mock_load_config,
            patch.object(
                consumer_service, "_create_container"
            ) as mock_create_container,
            patch.object(
                consumer_service, "_get_langextract_client", new_callable=AsyncMock
            ) as mock_langextract,
            patch.object(
                consumer_service, "_get_quality_scorer", new_callable=AsyncMock
            ) as mock_quality,
            patch.object(
                consumer_service, "_get_pattern_client", new_callable=AsyncMock
            ) as mock_pattern,
            patch(
                "src.server.services.kafka_consumer_service.NodeArchonKafkaConsumerEffect"
            ) as mock_consumer_class,
        ):

            # Setup mocks
            mock_config = Mock()
            mock_config.consumer_group = "test-group"
            mock_config.topic_patterns = ["test.*"]
            mock_load_config.return_value = mock_config

            mock_container = Mock()
            mock_create_container.return_value = mock_container

            mock_langextract.return_value = Mock()
            mock_quality.return_value = Mock()
            mock_pattern.return_value = Mock()

            mock_consumer = AsyncMock()
            mock_consumer.start_consuming = AsyncMock()
            mock_consumer.stop_consuming = AsyncMock()
            mock_consumer.registry = Mock()
            mock_consumer.registry.register = Mock()
            mock_consumer.registry.handlers = []
            mock_consumer_class.return_value = mock_consumer

            # Start
            await consumer_service.start()
            assert consumer_service._is_running is True
            assert mock_consumer.registry.register.call_count == 7  # 3 base + 4 codegen

            # Stop
            await consumer_service.stop()
            assert consumer_service._is_running is False
