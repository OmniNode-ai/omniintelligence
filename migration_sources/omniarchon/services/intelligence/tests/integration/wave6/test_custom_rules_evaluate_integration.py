"""
Integration Test: Custom Quality Rules - Evaluate
Tests complete flow: Event → Handler → HTTP → Response

Wave 6 - HTTP Implementation
Operation: POST /api/custom-rules/evaluate
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.integration
@pytest.mark.wave6
@pytest.mark.custom_rules
class TestCustomRulesEvaluateIntegration:
    """Integration tests for Custom Rules Evaluate operation."""

    @pytest.mark.asyncio
    async def test_evaluate_success_flow(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test complete evaluate flow with successful HTTP response."""
        from handlers.custom_quality_rules_handler import CustomQualityRulesHandler

        # Create handler
        handler = CustomQualityRulesHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {
            "project_id": "test_project_001",
            "code": "def hello():\\n    pass",
            "rules": ["naming_convention", "docstring_required"],
        }
        event = mock_event_envelope(
            correlation_id, payload, event_type="EVALUATE_REQUESTED"
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "custom_score": 0.85,
            "violations": ["Missing docstring for function 'hello'"],
            "warnings": ["Consider adding type hints"],
            "suggestions": ["Add comprehensive docstring"],
            "rules_evaluated": 2,
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
                "http://localhost:8053/api/custom-rules/evaluate", json=payload
            )

            # Verify response was published
            mock_router.publish.assert_called_once()
            publish_call = mock_router.publish.call_args

            # Verify event structure
            published_event = publish_call[0][1]  # 2nd positional argument is the event
            assert str(published_event["correlation_id"]) == correlation_id

            # Verify payload structure
            result_payload = published_event["payload"]
            assert "custom_score" in result_payload
            assert result_payload["custom_score"] == 0.85
            assert "violations" in result_payload
            assert len(result_payload["violations"]) == 1
            assert "rules_evaluated" in result_payload
            assert result_payload["rules_evaluated"] == 2

    @pytest.mark.asyncio
    async def test_evaluate_http_error_handling(
        self,
        mock_event_envelope,
        mock_router,
    ):
        """Test evaluate flow when HTTP service returns error."""
        import httpx
        from handlers.custom_quality_rules_handler import CustomQualityRulesHandler

        # Create handler
        handler = CustomQualityRulesHandler()
        handler._router = mock_router
        handler._router_initialized = True

        # Create request event
        correlation_id = str(uuid4())
        payload = {
            "project_id": "test_project_001",
            "code": "invalid code",
            "rules": [],
        }
        event = mock_event_envelope(
            correlation_id, payload, event_type="EVALUATE_REQUESTED"
        )

        # Mock HTTP error
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "400 Bad Request", request=AsyncMock(), response=AsyncMock()
                )
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
            assert "project_id" in payload
            assert payload["project_id"] == "test_project_001"
