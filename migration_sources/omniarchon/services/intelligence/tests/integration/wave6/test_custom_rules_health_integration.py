"""
Integration Test: Custom Quality Rules - Health
Tests complete flow: Event → Handler → HTTP → Response

Wave 6 - HTTP Implementation
Operation: GET /api/custom-rules/health
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.wave6
@pytest.mark.custom_rules
class TestCustomRulesHealthIntegration:
    """Integration tests for Custom Rules Health operation."""

    @pytest.mark.asyncio
    async def test_health_success_flow(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test complete health check flow with successful HTTP response."""
        from handlers.custom_quality_rules_handler import CustomQualityRulesHandler

        # Create handler
        handler = CustomQualityRulesHandler()
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
            "total_projects": 5,
            "total_rules": 42,
        }
        mock_response.raise_for_status = lambda: None

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
                "http://localhost:8053/api/custom-rules/health"
            )

            # Verify response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify event structure (publish is called with positional args: topic, event, key)
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            assert str(published_event["correlation_id"]) == correlation_id

            # Verify payload structure
            result_payload = published_event["payload"]
            assert "status" in result_payload
            assert result_payload["status"] == "healthy"
            assert "total_projects" in result_payload
            assert result_payload["total_projects"] == 5
            assert "total_rules" in result_payload
            assert result_payload["total_rules"] == 42
            assert "processing_time_ms" in result_payload
            assert result_payload["processing_time_ms"] > 0
