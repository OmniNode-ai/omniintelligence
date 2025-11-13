"""
Integration Test: Pattern Traceability - Execution Summary
Wave 4 - HTTP Implementation Test

Tests complete flow for execution summary retrieval.

Author: Archon Intelligence Team
Date: 2025-10-22
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from handlers import PatternTraceabilityHandler


@pytest.fixture
def sample_execution_summary_request():
    """Create sample execution summary request event."""
    return {
        "correlation_id": str(uuid4()),
        "payload": {},
        "event_type": "execution_summary_requested",
    }


@pytest.fixture
def mock_api_response():
    """Mock API response for execution summary endpoint."""
    return {
        "total_executions": 1000,
        "success_count": 920,
        "failure_count": 80,
        "average_duration_ms": 1250.5,
        "breakdown": {
            "by_status": {"success": 920, "failure": 80},
            "by_agent": {"agent-1": 500, "agent-2": 500},
        },
    }


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestPatternTraceabilityExecSummaryIntegration:
    """Integration tests for Pattern Traceability Execution Summary operation."""

    @pytest.mark.asyncio
    async def test_execution_summary_success_flow(
        self,
        sample_execution_summary_request,
        mock_api_response,
    ):
        """Test complete execution summary flow with HTTP call."""
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

            result = await handler.handle_event(sample_execution_summary_request)

            assert result is True
            mock_get.assert_called_once()

            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert payload["total_executions"] == 1000
            assert payload["success_count"] == 920
            assert payload["failure_count"] == 80
            assert payload["average_duration_ms"] == 1250.5

    @pytest.mark.asyncio
    async def test_execution_summary_error_handling(
        self, sample_execution_summary_request
    ):
        """Test error handling when HTTP call fails."""
        handler = PatternTraceabilityHandler()

        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = Exception("Connection timeout")

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_execution_summary_request)

            assert result is False

    @pytest.mark.asyncio
    async def test_execution_summary_metrics(
        self,
        sample_execution_summary_request,
        mock_api_response,
    ):
        """Test that metrics are properly tracked."""
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

            await handler.handle_event(sample_execution_summary_request)

            metrics = handler.get_metrics()
            assert metrics["events_handled"] == 1
            assert "execution_summary" in metrics["operations_by_type"]
