"""
Performance Report Integration Tests

Tests actual HTTP calls to Intelligence service for performance report operations.

Validates:
- GET /performance/report HTTP call
- Proper parameter passing (time_window_hours, operation)
- Success and failure response handling
- Event publishing
- Error handling (HTTP errors, timeouts, service unavailable)

Created: 2025-10-22
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.performance_events import (
    EnumPerformanceEventType,
    ModelReportRequestPayload,
)
from handlers.performance_handler import PerformanceHandler


@pytest.mark.asyncio
class TestPerformanceReportIntegration:
    """Integration tests for Performance Report HTTP implementation."""

    @pytest.fixture
    async def handler(self):
        """Create handler instance with mocked router."""
        handler = PerformanceHandler(intelligence_url="http://test-service:8053")
        handler._router = AsyncMock()
        handler._router_initialized = True
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def report_event(self):
        """Create test report event."""
        return {
            "event_type": EnumPerformanceEventType.REPORT_REQUESTED.value,
            "correlation_id": str(uuid4()),
            "payload": {
                "time_window_hours": 168,
                "operation_name": "test_operation",
            },
        }

    async def test_report_success(self, handler, report_event):
        """Test successful report HTTP call."""
        correlation_id = report_event["correlation_id"]
        mock_response = {
            "operations_count": 12,
            "total_measurements": 2450,
            "time_window_hours": 168,
            "report_summary": {
                "avg_response_time_ms": 185.2,
                "slowest_operation": "database_query",
                "fastest_operation": "cache_lookup",
            },
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(report_event)

            assert result is True
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "http://test-service:8053/performance/report" in str(call_args)
            assert call_args.kwargs["params"]["time_window_hours"] == 168
            assert call_args.kwargs["params"]["operation"] == "test_operation"
            handler._router.publish.assert_called_once()

    async def test_report_http_error(self, handler, report_event):
        """Test report HTTP error handling."""
        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Error", request=Mock(), response=mock_resp
            )
            mock_get.return_value = mock_resp

            result = await handler.handle_event(report_event)

            assert result is False
            handler._router.publish.assert_called_once()
            # Verify FAILED event was published
            call_args = handler._router.publish.call_args
            assert "report-failed" in call_args.kwargs["topic"]

    async def test_report_timeout(self, handler, report_event):
        """Test report timeout handling."""
        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            result = await handler.handle_event(report_event)

            assert result is False
            handler._router.publish.assert_called_once()

    async def test_report_connection_error(self, handler, report_event):
        """Test report connection error handling."""
        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await handler.handle_event(report_event)

            assert result is False
            handler._router.publish.assert_called_once()

    async def test_report_minimal_params(self, handler):
        """Test report with minimal parameters."""
        event = {
            "event_type": EnumPerformanceEventType.REPORT_REQUESTED.value,
            "correlation_id": str(uuid4()),
            "payload": {},
        }
        mock_response = {
            "operations_count": 5,
            "total_measurements": 100,
            "time_window_hours": 24,
            "report_summary": {},
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(event)

            assert result is True
            mock_get.assert_called_once()

    async def test_report_metrics_updated(self, handler, report_event):
        """Test that handler metrics are updated after report."""
        initial_events_handled = handler.metrics["events_handled"]
        mock_response = {
            "operations_count": 1,
            "total_measurements": 10,
            "time_window_hours": 24,
            "report_summary": {},
        }

        with patch.object(httpx.AsyncClient, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            result = await handler.handle_event(report_event)

            assert result is True
            assert handler.metrics["events_handled"] == initial_events_handled + 1
            assert "report" in handler.metrics["operations_by_type"]
            assert handler.metrics["operations_by_type"]["report"] > 0
