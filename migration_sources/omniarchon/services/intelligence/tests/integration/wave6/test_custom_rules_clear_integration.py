"""
Integration Test: Custom Quality Rules - Clear
Tests complete flow: Event → Handler → HTTP → Response

Wave 6 - HTTP Implementation
Operation: DELETE /api/custom-rules/project/{project_id}/rules
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.wave6
@pytest.mark.custom_rules
class TestCustomRulesClearIntegration:
    """Integration tests for Custom Rules Clear operation."""

    @pytest.mark.asyncio
    async def test_clear_success_flow(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test complete clear flow with successful HTTP response."""
        from handlers.custom_quality_rules_handler import CustomQualityRulesHandler

        # Create handler
        handler = CustomQualityRulesHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {"project_id": "test_project_001"}
        event = mock_event_envelope(
            correlation_id, payload, event_type="CLEAR_REQUESTED"
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "project_id": "test_project_001",
            "rules_cleared": 5,
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Handle event
            result = await handler.handle_event(event)

            # Verify handler processed successfully
            assert result is True

            # Verify HTTP call was made
            mock_client.delete.assert_called_once_with(
                "http://localhost:8053/api/custom-rules/project/test_project_001/rules"
            )

            # Verify response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify payload structure
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            result_payload = published_event["payload"]
            assert "project_id" in result_payload
            assert result_payload["project_id"] == "test_project_001"
            assert "rules_cleared" in result_payload
            assert result_payload["rules_cleared"] == 5
