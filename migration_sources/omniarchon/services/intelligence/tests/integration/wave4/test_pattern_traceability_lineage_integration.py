"""
Integration Test: Pattern Traceability - Lineage
Wave 4 - HTTP Implementation Test

Tests complete flow:
1. Consume Kafka event
2. Handler processes lineage request
3. HTTP call to GET /api/pattern-traceability/lineage/{pattern_id}
4. Response published via HybridEventRouter
5. Verify response reaches correct topic with correct structure

Author: Archon Intelligence Team
Date: 2025-10-22
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from events.models.pattern_traceability_events import (
    EnumTraceabilityErrorCode,
    ModelLineageCompletedPayload,
    ModelLineageRequestPayload,
)
from handlers import PatternTraceabilityHandler

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_lineage_request():
    """Create sample lineage request event."""
    correlation_id = str(uuid4())
    pattern_id = "pattern-abc123"

    return {
        "correlation_id": correlation_id,
        "payload": {
            "pattern_id": pattern_id,
        },
        "event_type": "lineage_requested",
    }


@pytest.fixture
def mock_api_response():
    """Mock API response for lineage endpoint."""
    return {
        "pattern_id": "pattern-abc123",
        "lineage_chain": [
            {"pattern_id": "pattern-abc123", "depth": 0},
            {"pattern_id": "pattern-def456", "depth": 1},
            {"pattern_id": "pattern-ghi789", "depth": 2},
        ],
        "depth": 2,
        "total_ancestors": 2,
    }


# ============================================================================
# Integration Test Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.handler_tests
@pytest.mark.wave4
class TestPatternTraceabilityLineageIntegration:
    """Integration tests for Pattern Traceability Lineage operation."""

    @pytest.mark.asyncio
    async def test_lineage_success_flow(
        self,
        sample_lineage_request,
        mock_api_response,
    ):
        """
        Test complete lineage flow:
        1. Receive lineage request
        2. HTTP call to Intelligence Service
        3. Publish response via HybridEventRouter
        """
        # Create handler
        handler = PatternTraceabilityHandler()

        # Mock HTTP client response
        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Mock event router
            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            # Handle event
            result = await handler.handle_event(sample_lineage_request)

            # Verify handler processed successfully
            assert result is True

            # Verify HTTP call was made
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert (
                f"/api/pattern-traceability/lineage/{sample_lineage_request['payload']['pattern_id']}"
                in str(call_args)
            )

            # Verify publish was called
            handler._router.publish.assert_called_once()

            # Verify published payload structure
            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]

            # Extract payload from envelope
            payload = (
                published_event["payload"]
                if hasattr(published_event, "payload")
                else published_event.get("payload")
            )

            assert (
                payload["pattern_id"] == sample_lineage_request["payload"]["pattern_id"]
            )
            assert payload["depth"] == 2
            assert payload["total_ancestors"] == 2
            assert len(payload["lineage_chain"]) == 3

    @pytest.mark.asyncio
    async def test_lineage_http_error_handling(
        self,
        sample_lineage_request,
    ):
        """Test error handling when HTTP call fails."""
        handler = PatternTraceabilityHandler()

        # Mock HTTP client to raise error
        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = Exception("HTTP connection failed")

            # Mock event router
            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            # Handle event
            result = await handler.handle_event(sample_lineage_request)

            # Verify handler caught error
            assert result is False

            # Verify failed event was published
            handler._router.publish.assert_called_once()
            publish_call_args = handler._router.publish.call_args
            published_event = publish_call_args.kwargs["event"]

            # Verify it's a failed event
            # Extract event_type from metadata (omnibase_core pattern)
            if isinstance(published_event, dict):
                metadata = published_event.get("metadata", {})
                event_type = metadata.get(
                    "event_type", published_event.get("event_type", "")
                )
            else:
                metadata = getattr(published_event, "metadata", {})
                event_type = (
                    metadata.get("event_type", "")
                    if isinstance(metadata, dict)
                    else getattr(published_event, "event_type", "")
                )
            assert "failed" in event_type.lower()

    @pytest.mark.asyncio
    async def test_lineage_pattern_not_found(
        self,
        sample_lineage_request,
    ):
        """Test handling when pattern is not found."""
        handler = PatternTraceabilityHandler()

        # Mock HTTP client to return 404
        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = Exception("404 Not Found")
            mock_get.return_value = mock_response

            # Mock event router
            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            # Handle event
            result = await handler.handle_event(sample_lineage_request)

            # Verify handler caught error
            assert result is False

            # Verify failed event was published
            handler._router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_lineage_metrics_tracking(
        self,
        sample_lineage_request,
        mock_api_response,
    ):
        """Test that metrics are properly tracked."""
        handler = PatternTraceabilityHandler()

        # Mock HTTP client response
        with patch.object(
            handler.http_client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Mock event router
            handler._router = AsyncMock()
            handler._router_initialized = True
            handler._router.publish = AsyncMock()

            # Handle event
            await handler.handle_event(sample_lineage_request)

            # Verify metrics
            metrics = handler.get_metrics()
            assert metrics["events_handled"] == 1
            assert metrics["events_failed"] == 0
            assert "lineage" in metrics["operations_by_type"]
            assert metrics["operations_by_type"]["lineage"] == 1
