"""
Integration Tests - Freshness Analyses HTTP Operation

Tests the FRESHNESS_ANALYSES operation end-to-end with HTTP calls to the intelligence service.

Wave: 3
Operation: Freshness - Analyses
HTTP Endpoint: GET /freshness/analyses
"""

from uuid import uuid4

import httpx
import pytest
import respx
from events.models.freshness_events import (
    FreshnessEventHelpers,
    ModelFreshnessAnalysesRequestPayload,
)
from handlers.freshness_handler import FreshnessHandler


class TestFreshnessAnalysesIntegration:
    """Integration tests for Freshness Analyses operation."""

    @pytest.fixture
    async def handler(self):
        """Create FreshnessHandler instance."""
        handler = FreshnessHandler()
        yield handler
        await handler._close_http_client()

    @pytest.fixture
    def correlation_id(self):
        """Generate correlation ID for test."""
        return str(uuid4())

    @respx.mock
    @pytest.mark.asyncio
    async def test_analyses_successful_http_call(self, handler, correlation_id):
        """Test successful analyses HTTP call with real service integration."""
        # Arrange: Mock HTTP response
        mock_response = {
            "analyses": [
                {
                    "id": "analysis_1",
                    "document_path": "/docs/test.md",
                    "freshness_score": 0.85,
                    "analyzed_at": "2025-10-22T12:00:00Z",
                },
                {
                    "id": "analysis_2",
                    "document_path": "/docs/example.md",
                    "freshness_score": 0.92,
                    "analyzed_at": "2025-10-22T11:30:00Z",
                },
            ],
            "total_count": 2,
        }

        respx.get("http://localhost:8053/freshness/analyses").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        # Create request payload
        payload = ModelFreshnessAnalysesRequestPayload(limit=10)

        # Create event
        event = FreshnessEventHelpers.create_event_envelope(
            event_type="freshness_analyses_requested",
            payload=payload,
            correlation_id=correlation_id,
        )

        # Act: Handle event
        import time

        start_time = time.perf_counter()
        result = await handler._handle_analyses(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert
        assert result is True
        assert handler.metrics["events_handled"] == 1
        assert handler.metrics["events_failed"] == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_analyses_http_error_handling(self, handler, correlation_id):
        """Test analyses operation handles HTTP errors correctly."""
        # Arrange: Mock 500 error
        respx.get("http://localhost:8053/freshness/analyses").mock(
            return_value=httpx.Response(500, json={"error": "Internal server error"})
        )

        payload = ModelFreshnessAnalysesRequestPayload(limit=5)

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_analyses(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert: Should handle error gracefully
        assert result is False
        assert handler.metrics["events_failed"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_analyses_with_limit_parameter(self, handler, correlation_id):
        """Test analyses operation respects limit parameter."""
        # Arrange
        mock_response = {
            "analyses": [{"id": f"analysis_{i}"} for i in range(3)],
            "total_count": 3,
        }

        # Capture request to verify params
        route = respx.get("http://localhost:8053/freshness/analyses").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelFreshnessAnalysesRequestPayload(limit=3)

        # Act
        import time

        start_time = time.perf_counter()
        await handler._handle_analyses(correlation_id, payload.model_dump(), start_time)

        # Assert: Verify request was made with correct params
        assert route.called
        assert route.calls.last.request.url.params["limit"] == "3"

    @respx.mock
    @pytest.mark.asyncio
    async def test_analyses_empty_results(self, handler, correlation_id):
        """Test analyses operation with empty results."""
        # Arrange
        mock_response = {"analyses": [], "total_count": 0}

        respx.get("http://localhost:8053/freshness/analyses").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelFreshnessAnalysesRequestPayload()

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_analyses(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert
        assert result is True
        assert handler.metrics["events_handled"] == 1
