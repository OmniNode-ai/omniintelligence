"""
Integration Test - Performance Analytics: Health Operation

Tests complete HTTP flow for GET /api/performance-analytics/health:
1. Handler receives HEALTH_REQUESTED event
2. Handler calls Intelligence service HTTP endpoint
3. Handler publishes HEALTH_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.performance_analytics_events import (
    EnumPerformanceAnalyticsEventType,
)
from handlers.performance_analytics_handler import PerformanceAnalyticsHandler


@pytest.fixture
def mock_health_response():
    """Mock successful health response from Intelligence service."""
    return {
        "status": "healthy",
        "baseline_service": "active",
        "optimization_analyzer": "active",
        "total_operations_tracked": 15,
        "total_measurements": 250,
        "uptime_seconds": 3600,
    }


@pytest.fixture
def sample_health_request():
    """Create sample health request event."""
    correlation_id = str(uuid4())
    payload = {}

    return {
        "event_type": EnumPerformanceAnalyticsEventType.HEALTH_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestPerformanceAnalyticsHealthIntegration:
    """Integration tests for Performance Analytics Health operation."""

    async def test_health_success_http_call(
        self,
        sample_health_request,
        mock_health_response,
    ):
        """Test successful health check via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_health_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", return_value=mock_response
        ) as mock_get:
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_health_request)

            assert result is True

            # Verify HTTP call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/api/performance-analytics/health" in call_args[0][0]

            # Verify response published
            handler._router.publish.assert_called_once()
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "health-completed" in topic

            # Verify payload
            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["status"] == "healthy"
            assert payload["baseline_service"] == "active"
            assert payload["optimization_analyzer"] == "active"
            assert payload["total_operations_tracked"] == 15
            assert payload["total_measurements"] == 250
            assert payload["uptime_seconds"] == 3600

    async def test_health_unhealthy_status(
        self,
        sample_health_request,
    ):
        """Test health check with unhealthy status."""
        unhealthy_response = {
            "status": "unhealthy",
            "baseline_service": "inactive",
            "optimization_analyzer": "inactive",
            "total_operations_tracked": 0,
            "total_measurements": 0,
            "uptime_seconds": 0,
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = unhealthy_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_health_request)

            # Should still succeed (service responded)
            assert result is True

            publish_call = handler._router.publish.call_args
            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["status"] == "unhealthy"

    async def test_health_http_error(
        self,
        sample_health_request,
    ):
        """Test health check with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service unavailable"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable", request=Mock(), response=mock_response
        )

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_health_request)

            assert result is False

            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "health-failed" in topic

    async def test_health_correlation_id_preserved(
        self,
        sample_health_request,
        mock_health_response,
    ):
        """Test correlation ID preservation in health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_health_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            await handler.handle_event(sample_health_request)

            publish_call = handler._router.publish.call_args
            event = publish_call[1]["event"]
            assert (
                str(event["correlation_id"]) == sample_health_request["correlation_id"]
            )
