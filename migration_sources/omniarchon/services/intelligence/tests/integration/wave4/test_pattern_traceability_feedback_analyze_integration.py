"""
Integration Test: Pattern Traceability - Feedback Analyze
Wave 4 - HTTP Implementation Test

Author: Archon Intelligence Team
Date: 2025-10-22
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from handlers import PatternTraceabilityHandler


@pytest.fixture
def sample_feedback_analyze_request():
    return {
        "correlation_id": str(uuid4()),
        "payload": {
            "pattern_id": "pattern-abc123",
            "feedback_data": {"rating": 5, "comments": "Excellent pattern"},
        },
        "event_type": "feedback_analyze_requested",
    }


@pytest.fixture
def mock_api_response():
    return {
        "pattern_id": "pattern-abc123",
        "analysis_results": {
            "sentiment": "positive",
            "themes": ["performance", "usability"],
        },
        "recommendations": ["Consider adding more examples", "Update documentation"],
        "confidence": 0.88,
    }


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestPatternTraceabilityFeedbackAnalyzeIntegration:
    @pytest.mark.asyncio
    async def test_feedback_analyze_success_flow(
        self, sample_feedback_analyze_request, mock_api_response
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

            result = await handler.handle_event(sample_feedback_analyze_request)
            assert result is True

            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert payload["pattern_id"] == "pattern-abc123"
            assert payload["confidence"] == 0.88
            assert len(payload["recommendations"]) == 2
