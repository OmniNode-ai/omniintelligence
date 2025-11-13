"""
Performance Trends Integration Tests

Tests actual HTTP calls to Intelligence service for performance trends operations.

Validates:
- GET /performance/trends HTTP call
- Proper parameter passing (timeframe, operation)
- Success and failure response handling
- Event publishing
- Error handling

Created: 2025-10-22
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.performance_events import (
    EnumPerformanceEventType,
    ModelTrendsRequestPayload,
)
from handlers.performance_handler import PerformanceHandler


@pytest.mark.asyncio
class TestPerformanceTrendsIntegration:
    """Integration tests for Performance Trends HTTP implementation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = PerformanceHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def trends_event(self):
        """Create test trends event."""
        return {
            "event_type": EnumPerformanceEventType.TRENDS_REQUESTED.value,
            "correlation_id": str(uuid4()),
            "payload": {
                "time_window_hours": 720,
                "operation_name": "api_endpoint",
            },
        }

    async def test_trends_success(self, handler, trends_event):
        """Test successful trends HTTP call."""
        mock_response = {
            "operations_count": 15,
            "trends_count": 4,
            "time_window_hours": 720,
            "trends_summary": {
                "improving_operations": 8,
                "degrading_operations": 2,
                "stable_operations": 5,
            },
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(trends_event)

            assert result is True
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "http://test-service:8053/performance/trends" in str(call_args)
            assert call_args.kwargs["params"]["timeframe"] == 720
            assert call_args.kwargs["params"]["operation"] == "api_endpoint"
            handler._router.publish.assert_called_once()

    async def test_trends_http_error(self, handler, trends_event):
        """Test trends HTTP error handling."""
        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 503
            mock_resp.text = "Service Unavailable"
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "503 Error", request=Mock(), response=mock_resp
            )
            mock_get.return_value = mock_resp

            result = await handler.handle_event(trends_event)

            assert result is False
            handler._router.publish.assert_called_once()
            call_args = handler._router.publish.call_args
            assert "trends-failed" in call_args.kwargs["topic"]

    async def test_trends_minimal_params(self, handler):
        """Test trends with minimal parameters."""
        event = {
            "event_type": EnumPerformanceEventType.TRENDS_REQUESTED.value,
            "correlation_id": str(uuid4()),
            "payload": {},
        }
        mock_response = {
            "operations_count": 5,
            "trends_count": 2,
            "time_window_hours": 24,
            "trends_summary": {},
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(event)

            assert result is True
            mock_get.assert_called_once()

    async def test_trends_metrics_updated(self, handler, trends_event):
        """Test that handler metrics are updated after trends query."""
        initial_events_handled = handler.metrics["events_handled"]
        mock_response = {
            "operations_count": 1,
            "trends_count": 1,
            "time_window_hours": 24,
            "trends_summary": {},
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(trends_event)

            assert result is True
            assert handler.metrics["events_handled"] == initial_events_handled + 1
            assert "trends" in handler.metrics["operations_by_type"]
            assert handler.metrics["operations_by_type"]["trends"] > 0
