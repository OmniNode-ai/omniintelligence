"""
Integration Test: Pattern Traceability - Analytics Compute
Wave 4 - HTTP Implementation Test

Author: Archon Intelligence Team
Date: 2025-10-22
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from handlers import PatternTraceabilityHandler


@pytest.fixture
def sample_analytics_compute_request():
    return {
        "correlation_id": str(uuid4()),
        "payload": {"correlation_field": "agent_name"},
        "event_type": "analytics_compute_requested",
    }


@pytest.fixture
def mock_api_response():
    return {
        "correlation_field": "agent_name",
        "results": {
            "agent-1": {"count": 500, "avg_duration_ms": 1200.0},
            "agent-2": {"count": 300, "avg_duration_ms": 950.0},
        },
        "total_records": 800,
    }


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestPatternTraceabilityAnalyticsComputeIntegration:
    @pytest.mark.asyncio
    async def test_analytics_compute_success_flow(
        self, sample_analytics_compute_request, mock_api_response
    ):
        handler = PatternTraceabilityHandler()

        with patch.object(
            handler.http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_analytics_compute_request)
            assert result is True

            mock_post.assert_called_once()
            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert payload["correlation_field"] == "agent_name"
            assert payload["total_records"] == 800
