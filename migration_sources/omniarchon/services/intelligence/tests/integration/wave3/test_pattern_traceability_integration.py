"""
Integration Tests - Pattern Traceability HTTP Operations

Tests the following Pattern Traceability operations end-to-end:
1. Track - Track single pattern lineage
2. Track Batch - Track multiple patterns

Wave: 3
Module: Pattern Traceability
HTTP Endpoints: POST /api/pattern-traceability/lineage/*
"""

from uuid import uuid4

import httpx
import pytest
import respx
from events.models.pattern_traceability_events import (
    ModelTrackBatchRequestPayload,
    ModelTrackRequestPayload,
)
from handlers.pattern_traceability_handler import PatternTraceabilityHandler


class TestTrackIntegration:
    """Integration tests for Track operation."""

    @pytest.fixture
    def handler(self):
        """Create PatternTraceabilityHandler instance."""
        return PatternTraceabilityHandler()

    @pytest.fixture
    def correlation_id(self):
        """Generate correlation ID for test."""
        return uuid4()

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_successful_http_call(self, handler, correlation_id):
        """Test successful pattern tracking HTTP call."""
        # Arrange: Mock HTTP response
        mock_response = {
            "tracked": True,
            "lineage_id": "lineage_abc123",
            "pattern_id": "pattern_123",
        }

        respx.post("http://localhost:8053/api/pattern-traceability/lineage/track").mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        payload = ModelTrackRequestPayload(
            pattern_id="pattern_123",
            pattern_type="test_handler",
            metadata={"origin": "test", "version": "1.0"},
        )

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert
        assert result is True
        assert handler.metrics["events_handled"] == 1
        assert handler.metrics["events_failed"] == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_http_error_handling(self, handler, correlation_id):
        """Test track operation handles HTTP errors correctly."""
        # Arrange: Mock 404 error (pattern not found)
        respx.post("http://localhost:8053/api/pattern-traceability/lineage/track").mock(
            return_value=httpx.Response(404, json={"error": "Pattern not found"})
        )

        payload = ModelTrackRequestPayload(
            pattern_id="nonexistent_pattern", pattern_type="test", metadata={}
        )

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert: Should handle error gracefully
        assert result is False
        assert handler.metrics["events_failed"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_with_metadata(self, handler, correlation_id):
        """Test track operation passes metadata correctly."""
        # Arrange
        mock_response = {
            "tracked": True,
            "lineage_id": "lineage_xyz",
            "pattern_id": "pattern_456",
        }

        # Capture request to verify payload
        route = respx.post(
            "http://localhost:8053/api/pattern-traceability/lineage/track"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        metadata = {"user": "test_user", "timestamp": "2025-10-22T12:00:00Z"}
        payload = ModelTrackRequestPayload(
            pattern_id="pattern_456", pattern_type="api", metadata=metadata
        )

        # Act
        import time

        start_time = time.perf_counter()
        await handler._handle_track(correlation_id, payload.model_dump(), start_time)

        # Assert: Verify request was made with correct metadata
        assert route.called
        request_body = route.calls.last.request.content
        assert b"test_user" in request_body
        assert b"pattern_456" in request_body


class TestTrackBatchIntegration:
    """Integration tests for Track Batch operation."""

    @pytest.fixture
    def handler(self):
        """Create PatternTraceabilityHandler instance."""
        return PatternTraceabilityHandler()

    @pytest.fixture
    def correlation_id(self):
        """Generate correlation ID for test."""
        return uuid4()

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_batch_successful(self, handler, correlation_id):
        """Test successful batch tracking."""
        # Arrange: Mock HTTP response
        mock_response = {
            "tracked_count": 3,
            "failed_count": 0,
            "lineage_ids": ["lineage_1", "lineage_2", "lineage_3"],
        }

        respx.post(
            "http://localhost:8053/api/pattern-traceability/lineage/track/batch"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        patterns = [
            {"pattern_id": "p1", "source": "test", "metadata": {}},
            {"pattern_id": "p2", "source": "test", "metadata": {}},
            {"pattern_id": "p3", "source": "test", "metadata": {}},
        ]
        payload = ModelTrackBatchRequestPayload(patterns=patterns)

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track_batch(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert
        assert result is True
        assert handler.metrics["events_handled"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_batch_partial_failure(self, handler, correlation_id):
        """Test batch tracking with partial failures."""
        # Arrange: Mock response with some failures
        mock_response = {
            "tracked_count": 2,
            "failed_count": 1,
            "lineage_ids": ["lineage_1", "lineage_2"],
            "failures": [{"pattern_id": "p3", "error": "Invalid pattern"}],
        }

        respx.post(
            "http://localhost:8053/api/pattern-traceability/lineage/track/batch"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        patterns = [
            {"pattern_id": "p1", "source": "test", "metadata": {}},
            {"pattern_id": "p2", "source": "test", "metadata": {}},
            {"pattern_id": "p3", "source": "test", "metadata": {}},
        ]
        payload = ModelTrackBatchRequestPayload(patterns=patterns)

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track_batch(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert: Should still succeed (HTTP 200)
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_batch_empty_patterns(self, handler, correlation_id):
        """Test batch tracking with minimal pattern (validation now requires at least 1)."""
        # Arrange: Model validation now requires at least 1 pattern
        mock_response = {
            "tracked_count": 1,
            "failed_count": 0,
            "lineage_ids": ["lineage_minimal"],
        }

        respx.post(
            "http://localhost:8053/api/pattern-traceability/lineage/track/batch"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        # Use minimal valid pattern (model now requires min_length=1)
        payload = ModelTrackBatchRequestPayload(
            patterns=[{"pattern_id": "minimal", "pattern_type": "test", "metadata": {}}]
        )

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track_batch(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_batch_http_error(self, handler, correlation_id):
        """Test batch tracking handles HTTP errors."""
        # Arrange: Mock 500 error
        respx.post(
            "http://localhost:8053/api/pattern-traceability/lineage/track/batch"
        ).mock(return_value=httpx.Response(500, json={"error": "Server error"}))

        patterns = [
            {"pattern_id": "p1", "source": "test", "metadata": {}},
        ]
        payload = ModelTrackBatchRequestPayload(patterns=patterns)

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track_batch(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert: Should handle error gracefully
        assert result is False
        assert handler.metrics["events_failed"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_track_batch_large_payload(self, handler, correlation_id):
        """Test batch tracking with large number of patterns."""
        # Arrange
        pattern_count = 100
        mock_response = {
            "tracked_count": pattern_count,
            "failed_count": 0,
            "lineage_ids": [f"lineage_{i}" for i in range(pattern_count)],
        }

        respx.post(
            "http://localhost:8053/api/pattern-traceability/lineage/track/batch"
        ).mock(return_value=httpx.Response(200, json=mock_response))

        patterns = [
            {"pattern_id": f"pattern_{i}", "source": "test", "metadata": {}}
            for i in range(pattern_count)
        ]
        payload = ModelTrackBatchRequestPayload(patterns=patterns)

        # Act
        import time

        start_time = time.perf_counter()
        result = await handler._handle_track_batch(
            correlation_id, payload.model_dump(), start_time
        )

        # Assert
        assert result is True
        assert handler.metrics["events_handled"] == 1
