"""
Integration Test: Custom Quality Rules - Load Config
Tests complete flow: Event → Handler → HTTP → Response

Wave 6 - HTTP Implementation
Operation: POST /api/custom-rules/project/{project_id}/load-config
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.wave6
@pytest.mark.custom_rules
class TestCustomRulesLoadConfigIntegration:
    """Integration tests for Custom Rules Load Config operation."""

    @pytest.mark.asyncio
    async def test_load_config_success_flow(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test complete load config flow with successful HTTP response."""
        from handlers.custom_quality_rules_handler import CustomQualityRulesHandler

        # Create handler
        handler = CustomQualityRulesHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {
            "project_id": "test_project_001",
            "config_path": "/path/to/quality_rules.yaml",
            "config_yaml": "rules:\\n  - naming_convention\\n  - docstring_required",
        }
        event = mock_event_envelope(
            correlation_id, payload, event_type="LOAD_CONFIG_REQUESTED"
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "project_id": "test_project_001",
            "rules_loaded": 2,
            "rule_ids": ["naming_convention", "docstring_required"],
            "config_path": "/path/to/quality_rules.yaml",
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Handle event
            result = await handler.handle_event(event)

            # Verify handler processed successfully
            assert result is True

            # Verify HTTP call was made
            mock_client.post.assert_called_once_with(
                "http://localhost:8053/api/custom-rules/project/test_project_001/load-config",
                json=payload,
            )

            # Verify response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify payload structure
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            result_payload = published_event["payload"]
            assert "project_id" in result_payload
            assert result_payload["project_id"] == "test_project_001"
            assert "rules_loaded" in result_payload
            assert result_payload["rules_loaded"] == 2
            assert "rule_ids" in result_payload
            assert len(result_payload["rule_ids"]) == 2
