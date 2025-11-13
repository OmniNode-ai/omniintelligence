"""
Integration Test - Performance Analytics: Trends Operation

Tests complete HTTP flow for GET /api/performance-analytics/trends:
1. Handler receives TRENDS_REQUESTED event
2. Handler calls Intelligence service HTTP endpoint
3. Handler publishes TRENDS_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.performance_analytics_events import (
    EnumPerformanceAnalyticsEventType,
    PerformanceAnalyticsEventHelpers,
)
from handlers.performance_analytics_handler import PerformanceAnalyticsHandler


@pytest.fixture
def mock_trends_response():
    """Mock successful trends response from Intelligence service."""
    return {
        "time_window": "24h",
        "operations": {
            "api_call": {
                "trend": "improving",
                "change_percent": -5.2,
                "avg_duration_ms": 45.0,
            },
            "database_query": {
                "trend": "degrading",
                "change_percent": 12.3,
                "avg_duration_ms": 120.0,
            },
        },
        "overall_health": "good",
    }


@pytest.fixture
def sample_trends_request():
    """Create sample trends request event."""
    correlation_id = str(uuid4())
    payload = {
        "time_window_hours": 24,
    }

    return {
        "event_type": EnumPerformanceAnalyticsEventType.TRENDS_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestPerformanceAnalyticsTrendsIntegration:
    """Integration tests for Performance Analytics Trends operation."""

    async def test_trends_success_http_call(
        self,
        sample_trends_request,
        mock_trends_response,
    ):
        """Test successful trends retrieval via HTTP."""
        # Mock HTTP client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_trends_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "get", return_value=mock_response
        ) as mock_get:
            # Create handler with mock router
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.initialize = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            # Handle event
            result = await handler.handle_event(sample_trends_request)

            # Verify success
            assert result is True

            # Verify HTTP call was made
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/api/performance-analytics/trends" in call_args[0][0]

            # Verify response was published
            handler._router.publish.assert_called_once()
            publish_call = handler._router.publish.call_args

            # Verify topic
            topic = publish_call[1]["topic"]
            assert "trends-completed" in topic

            # Verify payload
            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["time_window"] == "24h"
            assert len(payload["operations"]) == 2
            assert "api_call" in payload["operations"]
            assert "database_query" in payload["operations"]
            assert payload["overall_health"] == "good"

            # Verify metrics updated
            metrics = handler.get_metrics()
            assert metrics["events_handled"] == 1
            assert metrics["operations_by_type"]["trends"] == 1

    async def test_trends_http_error_handling(
        self,
        sample_trends_request,
    ):
        """Test trends operation with HTTP error."""
        # Mock HTTP client to raise error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=Mock(), response=mock_response
        )

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            # Create handler
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.initialize = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            # Handle event
            result = await handler.handle_event(sample_trends_request)

            # Verify failure
            assert result is False

            # Verify error response was published
            handler._router.publish.assert_called_once()
            publish_call = handler._router.publish.call_args

            # Verify topic
            topic = publish_call[1]["topic"]
            assert "trends-failed" in topic

            # Verify error payload
            event = publish_call[1]["event"]
            payload = event["payload"]
            assert "Service error" in payload["error_message"]

            # Verify metrics updated
            metrics = handler.get_metrics()
            assert metrics["events_failed"] == 1

    async def test_trends_correlation_id_preserved(
        self,
        sample_trends_request,
        mock_trends_response,
    ):
        """Test that correlation ID is preserved through trends operation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_trends_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            await handler.handle_event(sample_trends_request)

            # Verify correlation ID preserved
            publish_call = handler._router.publish.call_args
            event = publish_call[1]["event"]
            assert (
                str(event["correlation_id"]) == sample_trends_request["correlation_id"]
            )

            # Verify used as routing key
            key = publish_call[1]["key"]
            assert key == sample_trends_request["correlation_id"]

    async def test_trends_timeout_handling(
        self,
        sample_trends_request,
    ):
        """Test trends operation with timeout."""
        with patch.object(
            httpx.AsyncClient,
            "get",
            side_effect=httpx.TimeoutException("Request timeout"),
        ):
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_trends_request)

            # Verify graceful failure
            assert result is False

            # Verify error response published
            handler._router.publish.assert_called_once()
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "trends-failed" in topic

    async def test_trends_empty_response(
        self,
        sample_trends_request,
    ):
        """Test trends operation with empty trends list."""
        empty_response = {
            "time_window": "24h",
            "operations": {},
            "overall_health": "unknown",
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_response.raise_for_status = Mock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            handler = PerformanceAnalyticsHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_trends_request)

            # Verify success with empty data
            assert result is True

            publish_call = handler._router.publish.call_args
            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["time_window"] == "24h"
            assert len(payload["operations"]) == 0
            assert payload["overall_health"] == "unknown"
