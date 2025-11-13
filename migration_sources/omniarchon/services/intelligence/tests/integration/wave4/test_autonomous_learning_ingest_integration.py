"""
Integration Test: Autonomous Learning - Patterns Ingest
Wave 4 - HTTP Implementation Test

Tests complete flow for pattern ingestion.

Author: Archon Intelligence Team
Date: 2025-10-22
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from handlers import AutonomousLearningHandler


@pytest.fixture
def sample_pattern_ingest_request():
    return {
        "correlation_id": str(uuid4()),
        "payload": {
            "execution_pattern": {
                "execution_id": "exec-test-001",
                "task_characteristics": {
                    "task_type": "api_generation",
                    "complexity": "medium",
                },
                "execution_details": {
                    "agent_used": "agent-api-architect",
                    "patterns_applied": ["api_generation", "data_validation"],
                },
                "outcome": {
                    "success": True,
                    "duration_ms": 285000,
                    "quality_score": 0.87,
                },
            },
            "project_id": "project-test-001",
        },
        "event_type": "pattern_ingest_requested",
    }


@pytest.fixture
def mock_api_response():
    return {
        "pattern_id": "pattern-new-001",
        "pattern_name": "api_generation",
        "is_new_pattern": True,
        "success_rate": 0.87,
        "total_executions": 42,
        "confidence_score": 0.92,
    }


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestAutonomousLearningIngestIntegration:
    @pytest.mark.asyncio
    async def test_pattern_ingest_success_flow(
        self, sample_pattern_ingest_request, mock_api_response
    ):
        handler = AutonomousLearningHandler()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_pattern_ingest_request)
            assert result is True

            mock_post.assert_called_once()
            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert payload["pattern_id"] == "pattern-new-001"
            assert payload["is_new_pattern"] is True
            assert payload["confidence_score"] == 0.92

    @pytest.mark.asyncio
    async def test_pattern_ingest_error_handling(self, sample_pattern_ingest_request):
        handler = AutonomousLearningHandler()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Ingestion failed")

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_pattern_ingest_request)
            assert result is False

    @pytest.mark.asyncio
    async def test_pattern_ingest_metrics(
        self, sample_pattern_ingest_request, mock_api_response
    ):
        handler = AutonomousLearningHandler()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            await handler.handle_event(sample_pattern_ingest_request)

            metrics = handler.get_metrics()
            assert metrics["events_handled"] == 1
            assert "pattern_ingest" in metrics["operations_by_type"]
