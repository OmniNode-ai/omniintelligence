"""
Integration Test: Pattern Analytics Health
Tests complete flow: Event → Handler → HTTP → Response

Wave 6 - HTTP Implementation
Operation: GET /api/pattern-analytics/health
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.wave6
@pytest.mark.pattern_analytics
class TestPatternAnalyticsHealthIntegration:
    """Integration tests for Pattern Analytics Health operation."""

    @pytest.mark.asyncio
    async def test_health_success_flow(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test complete health check flow with successful HTTP response."""
        from handlers.pattern_analytics_handler import PatternAnalyticsHandler

        # Create handler
        handler = PatternAnalyticsHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {}
        event = mock_event_envelope(
            correlation_id, payload, event_type="HEALTH_REQUESTED"
        )

        # Mock HTTP response
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "healthy",
            "service": "pattern-analytics",
            "endpoints": [
                "/api/pattern-analytics/success-rates",
                "/api/pattern-analytics/top-patterns",
                "/api/pattern-analytics/emerging-patterns",
                "/api/pattern-analytics/pattern/{pattern_id}/history",
                "/api/pattern-analytics/health",
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Handle event
            result = await handler.handle_event(event)

            # Verify handler processed successfully
            assert result is True

            # Verify HTTP call was made
            mock_client.get.assert_called_once_with(
                "http://localhost:8053/api/pattern-analytics/health"
            )

            # Verify response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Extract event from call args (positional or keyword)
            if len(publish_call.args) >= 2:
                published_event = publish_call.args[1]
            else:
                published_event = publish_call.kwargs.get("event")

            # Verify event structure
            assert published_event is not None

            # Extract correlation_id and payload (event can be dict or object)
            if isinstance(published_event, dict):
                event_correlation_id = str(published_event.get("correlation_id"))
                payload = published_event.get("payload")
            else:
                event_correlation_id = str(published_event["correlation_id"])
                payload = published_event["payload"]

            assert event_correlation_id == correlation_id

            # Verify payload structure
            assert "status" in payload
            assert payload["status"] == "healthy"
            assert "service" in payload
            assert payload["service"] == "pattern-analytics"
            assert "endpoints" in payload
            assert len(payload["endpoints"]) == 5

    @pytest.mark.asyncio
    async def test_health_http_error_handling(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test health check flow when HTTP service is unavailable."""
        import httpx
        from handlers.pattern_analytics_handler import PatternAnalyticsHandler

        # Create handler
        handler = PatternAnalyticsHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {}
        event = mock_event_envelope(
            correlation_id, payload, event_type="HEALTH_REQUESTED"
        )

        # Mock HTTP error
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Service unavailable")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Handle event
            result = await handler.handle_event(event)

            # Verify handler failed gracefully
            assert result is False

            # Verify error response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify error payload
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            payload = published_event["payload"]
            assert "error_message" in payload
            assert "Service unavailable" in payload["error_message"]

    @pytest.mark.asyncio
    async def test_health_metrics_tracking(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test that health check tracks metrics correctly."""
        from handlers.pattern_analytics_handler import PatternAnalyticsHandler

        # Create handler
        handler = PatternAnalyticsHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {}
        event = mock_event_envelope(
            correlation_id, payload, event_type="HEALTH_REQUESTED"
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "healthy",
            "service": "pattern-analytics",
            "endpoints": [],
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Process event
            await handler.handle_event(event)

            # Verify metrics
            metrics = handler.get_metrics()
            assert metrics["events_handled"] == 1
            assert metrics["events_failed"] == 0
            assert "health" in metrics["operations_by_type"]
            assert metrics["operations_by_type"]["health"] == 1
