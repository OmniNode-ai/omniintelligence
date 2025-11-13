"""
Integration Test - System Utilities: Metrics Operation

Tests complete HTTP flow for GET /metrics:
1. Handler receives METRICS_REQUESTED event
2. Handler calls Intelligence service HTTP endpoint
3. Handler publishes METRICS_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.system_utilities_events import EnumSystemUtilitiesEventType
from handlers.system_utilities_handler import SystemUtilitiesHandler


@pytest.fixture
def mock_metrics_response():
    """Mock successful metrics response."""
    return {
        "system_metrics": {
            "cpu_usage_percent": 45.2,
            "memory_usage_mb": 1024.5,
            "disk_usage_percent": 62.1,
        },
        "service_metrics": {
            "intelligence": {"requests_per_second": 12.5, "avg_latency_ms": 45.2},
            "search": {"requests_per_second": 8.3, "avg_latency_ms": 78.1},
        },
        "kafka_metrics": {
            "messages_per_second": 150.5,
            "consumer_lag": 42,
        },
        "cache_metrics": {
            "hit_rate": 0.85,
            "memory_usage_mb": 256.0,
        },
    }


@pytest.fixture
def sample_metrics_request():
    """Create sample metrics request."""
    correlation_id = uuid4()
    payload = {
        "include_detailed_metrics": True,
        "time_window_seconds": 300,
        "metric_types": ["cpu", "memory", "kafka"],
    }

    return {
        "event_type": EnumSystemUtilitiesEventType.METRICS_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestSystemMetricsIntegration:
    """Integration tests for System Metrics operation."""

    async def test_metrics_collection_success(
        self,
        sample_metrics_request,
        mock_metrics_response,
    ):
        """Test successful metrics collection via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_metrics_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", return_value=mock_response
        ) as mock_get:
            handler = SystemUtilitiesHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_metrics_request)

            assert result is True

            # Verify HTTP call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/metrics" in call_args[0][0]

            # Verify response published
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "metrics-completed" in topic

            event = publish_call[1]["event"]
            payload = event["payload"]
            assert "cpu_usage_percent" in payload["system_metrics"]
            assert payload["system_metrics"]["cpu_usage_percent"] == 45.2

    async def test_metrics_http_error(
        self,
        sample_metrics_request,
    ):
        """Test metrics collection with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=AsyncMock(), response=mock_response
        )

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = SystemUtilitiesHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_metrics_request)

            assert result is False

            # Verify error response
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "metrics-failed" in topic
