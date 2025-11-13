"""
Integration Test: Pattern Traceability - Execution Logs
Wave 4 - HTTP Implementation Test

Tests complete flow for execution logs retrieval.

Author: Archon Intelligence Team
Date: 2025-10-22
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from handlers import PatternTraceabilityHandler


@pytest.fixture
def sample_execution_logs_request():
    """Create sample execution logs request event."""
    return {
        "correlation_id": str(uuid4()),
        "payload": {
            "limit": 50,
            "time_window_hours": 24,
        },
        "event_type": "execution_logs_requested",
    }


@pytest.fixture
def mock_api_response():
    """Mock API response for execution logs endpoint."""
    return {
        "logs": [
            {
                "execution_id": "exec-001",
                "pattern_id": "pattern-abc",
                "status": "success",
            },
            {
                "execution_id": "exec-002",
                "pattern_id": "pattern-def",
                "status": "success",
            },
        ],
        "total_count": 2,
    }


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestPatternTraceabilityExecLogsIntegration:
    """Integration tests for Pattern Traceability Execution Logs operation."""

    @pytest.mark.asyncio
    async def test_execution_logs_success_flow(
        self,
        sample_execution_logs_request,
        mock_api_response,
    ):
        """Test complete execution logs flow with HTTP call."""
        handler = PatternTraceabilityHandler()

        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_execution_logs_request)

            assert result is True
            mock_get.assert_called_once()

            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert payload["total_count"] == 2
            assert len(payload["logs"]) == 2

    @pytest.mark.asyncio
    async def test_execution_logs_with_query_params(
        self,
        sample_execution_logs_request,
        mock_api_response,
    ):
        """Test that query parameters are passed correctly."""
        handler = PatternTraceabilityHandler()

        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_execution_logs_request)

            assert result is True
            # Verify params were passed
            call_kwargs = mock_get.call_args.kwargs
            assert "params" in call_kwargs

    @pytest.mark.asyncio
    async def test_execution_logs_error_handling(self, sample_execution_logs_request):
        """Test error handling when HTTP call fails."""
        handler = PatternTraceabilityHandler()

        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = Exception("HTTP error")

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_execution_logs_request)

            assert result is False
