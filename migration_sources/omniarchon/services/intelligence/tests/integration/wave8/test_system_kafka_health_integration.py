"""
Integration Test - System Utilities: Kafka Health Operation

Tests complete HTTP flow for GET /kafka/health:
1. Handler receives KAFKA_HEALTH_REQUESTED event
2. Handler calls Intelligence service HTTP endpoint
3. Handler publishes KAFKA_HEALTH_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.system_utilities_events import EnumSystemUtilitiesEventType
from handlers.system_utilities_handler import SystemUtilitiesHandler


@pytest.fixture
def mock_kafka_health_response():
    """Mock successful Kafka health response."""
    return {
        "status": "healthy",
        "producer_healthy": True,
        "consumer_healthy": True,
        "topics_available": 25,
        "broker_count": 3,
        "health_details": {
            "bootstrap_servers": "localhost:9092",
            "cluster_id": "test-cluster",
        },
    }


@pytest.fixture
def sample_kafka_health_request():
    """Create sample Kafka health request."""
    correlation_id = uuid4()
    payload = {
        "check_producer": True,
        "check_consumer": True,
        "check_topics": True,
        "timeout_ms": 5000,
    }

    return {
        "event_type": EnumSystemUtilitiesEventType.KAFKA_HEALTH_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestSystemKafkaHealthIntegration:
    """Integration tests for System Kafka Health operation."""

    async def test_kafka_health_success(
        self,
        sample_kafka_health_request,
        mock_kafka_health_response,
    ):
        """Test successful Kafka health check via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_kafka_health_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", return_value=mock_response
        ) as mock_get:
            handler = SystemUtilitiesHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_kafka_health_request)

            assert result is True

            # Verify HTTP call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/kafka/health" in call_args[0][0]

            # Verify query params
            params = call_args[1]["params"]
            assert params["check_producer"] is True
            assert params["check_consumer"] is True

            # Verify response published
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "kafka-health-completed" in topic

            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["status"] == "healthy"
            assert payload["producer_healthy"] is True
            assert payload["broker_count"] == 3

    async def test_kafka_health_unhealthy(
        self,
        sample_kafka_health_request,
    ):
        """Test Kafka health check with unhealthy status."""
        unhealthy_response = {
            "status": "unhealthy",
            "producer_healthy": False,
            "consumer_healthy": True,
            "topics_available": 0,
            "broker_count": 0,
            "health_details": {},
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = unhealthy_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = SystemUtilitiesHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_kafka_health_request)

            # Should succeed (service responded)
            assert result is True

            publish_call = handler._router.publish.call_args
            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["status"] == "unhealthy"
            assert payload["producer_healthy"] is False

    async def test_kafka_health_connection_error(
        self,
        sample_kafka_health_request,
    ):
        """Test Kafka health check with connection error."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Kafka unavailable"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Kafka unavailable", request=AsyncMock(), response=mock_response
        )

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = SystemUtilitiesHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_kafka_health_request)

            assert result is False

            # Verify error response
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "kafka-health-failed" in topic
