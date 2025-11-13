"""
Integration Test: Pattern Traceability - Evolution
Wave 4 - HTTP Implementation Test

Tests complete flow:
1. Consume Kafka event
2. Handler processes evolution request
3. HTTP call to GET /api/pattern-traceability/lineage/{pattern_id}/evolution
4. Response published via HybridEventRouter
5. Verify response reaches correct topic with correct structure

Author: Archon Intelligence Team
Date: 2025-10-22
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from handlers import PatternTraceabilityHandler


@pytest.fixture
def sample_evolution_request():
    """Create sample evolution request event."""
    correlation_id = str(uuid4())
    pattern_id = "pattern-abc123"

    return {
        "correlation_id": correlation_id,
        "payload": {
            "pattern_id": pattern_id,
        },
        "event_type": "evolution_requested",
    }


@pytest.fixture
def mock_api_response():
    """Mock API response for evolution endpoint."""
    return {
        "pattern_id": "pattern-abc123",
        "evolution_stages": [
            {"version": "1.0.0", "timestamp": "2025-01-01T00:00:00Z"},
            {"version": "1.1.0", "timestamp": "2025-02-01T00:00:00Z"},
            {"version": "2.0.0", "timestamp": "2025-03-01T00:00:00Z"},
        ],
        "total_versions": 3,
        "time_span_hours": 1440.0,
        "metrics": {
            "quality_trend": "improving",
            "usage_trend": "increasing",
        },
    }


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestPatternTraceabilityEvolutionIntegration:
    """Integration tests for Pattern Traceability Evolution operation."""

    @pytest.mark.asyncio
    async def test_evolution_success_flow(
        self,
        sample_evolution_request,
        mock_api_response,
    ):
        """Test complete evolution flow with HTTP call."""
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

            result = await handler.handle_event(sample_evolution_request)

            assert result is True
            mock_get.assert_called_once()

            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert (
                payload["pattern_id"]
                == sample_evolution_request["payload"]["pattern_id"]
            )
            assert payload["total_versions"] == 3
            assert payload["time_span_hours"] == 1440.0
            assert len(payload["evolution_stages"]) == 3

    @pytest.mark.asyncio
    async def test_evolution_http_error_handling(self, sample_evolution_request):
        """Test error handling when HTTP call fails."""
        handler = PatternTraceabilityHandler()

        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = Exception("HTTP connection failed")

            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            result = await handler.handle_event(sample_evolution_request)

            assert result is False
            handler._router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_evolution_metrics_tracking(
        self,
        sample_evolution_request,
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

            await handler.handle_event(sample_evolution_request)

            metrics = handler.get_metrics()
            assert metrics["events_handled"] == 1
            assert "evolution" in metrics["operations_by_type"]
