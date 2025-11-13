"""
Unit tests for Codegen Pattern Handler

Tests event handling for pattern matching requests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from handlers import CodegenPatternHandler

# Add src directory to path for imports


class TestCodegenPatternHandler:
    """Test suite for Codegen Pattern Handler."""

    @pytest.fixture
    def mock_pattern_service(self):
        """Create mock pattern service."""
        mock = AsyncMock()
        mock.find_similar_nodes.return_value = [
            {
                "node_id": "node-123",
                "similarity_score": 0.95,
                "description": "Database writer node",
                "mixins_used": ["CachingMixin", "RetryMixin"],
                "contracts": [],
                "code_snippets": [],
                "metadata": {"node_type": "effect"},
            }
        ]
        return mock

    @pytest.fixture
    def handler(self, mock_pattern_service):
        """Create handler instance with mocked service."""
        return CodegenPatternHandler(pattern_service=mock_pattern_service)

    def test_can_handle_pattern_request(self, handler):
        """Test that handler accepts pattern request events."""
        assert handler.can_handle("codegen.request.pattern") is True
        assert handler.can_handle("pattern.match") is True

    def test_can_handle_other_events(self, handler):
        """Test that handler rejects other event types."""
        assert handler.can_handle("codegen.request.validate") is False
        assert handler.can_handle("codegen.request.mixin") is False
        assert handler.can_handle("unknown.event") is False

    @pytest.mark.asyncio
    async def test_handle_event_success(self, handler, mock_pattern_service):
        """Test successful event handling."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_description": "Write data to database",
                "node_type": "effect",
                "limit": 5,
                "score_threshold": 0.7,
            },
        }

        result = await handler.handle_event(event)

        assert result is True
        mock_pattern_service.find_similar_nodes.assert_called_once_with(
            node_description="Write data to database",
            node_type="effect",
            limit=5,
            score_threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_handle_event_missing_description(
        self, handler, mock_pattern_service
    ):
        """Test handling of event with missing node_description."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_type": "effect",
            },
        }

        result = await handler.handle_event(event)

        assert result is False
        mock_pattern_service.find_similar_nodes.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_default_parameters(self, handler, mock_pattern_service):
        """Test that handler uses default parameters when not provided."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_description": "Some description",
            },
        }

        result = await handler.handle_event(event)

        assert result is True
        mock_pattern_service.find_similar_nodes.assert_called_once()
        call_kwargs = mock_pattern_service.find_similar_nodes.call_args.kwargs
        assert call_kwargs["node_type"] == "effect"  # Default
        assert call_kwargs["limit"] == 5  # Default
        assert call_kwargs["score_threshold"] == 0.7  # Default

    @pytest.mark.asyncio
    async def test_handle_event_with_object_format(self, handler, mock_pattern_service):
        """Test handling of event in object format."""
        event = MagicMock()
        event.correlation_id = "test-456"
        event.payload = {
            "node_description": "Process data",
            "node_type": "compute",
        }

        result = await handler.handle_event(event)

        assert result is True
        assert mock_pattern_service.find_similar_nodes.called

    @pytest.mark.asyncio
    async def test_handle_event_service_error(self, handler, mock_pattern_service):
        """Test error handling when service fails."""
        mock_pattern_service.find_similar_nodes.side_effect = Exception("Service error")

        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_description": "Some description",
            },
        }

        result = await handler.handle_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_metrics_tracking_success(self, handler, mock_pattern_service):
        """Test that metrics are tracked on success."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_description": "Some description",
            },
        }

        initial_handled = handler.metrics["events_handled"]
        await handler.handle_event(event)

        assert handler.metrics["events_handled"] == initial_handled + 1
        assert handler.metrics["events_failed"] == 0

    @pytest.mark.asyncio
    async def test_metrics_tracking_failure(self, handler, mock_pattern_service):
        """Test that metrics are tracked on failure."""
        mock_pattern_service.find_similar_nodes.side_effect = Exception("Error")

        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_description": "Some description",
            },
        }

        initial_failed = handler.metrics["events_failed"]
        await handler.handle_event(event)

        assert handler.metrics["events_failed"] == initial_failed + 1

    def test_get_handler_name(self, handler):
        """Test handler name retrieval."""
        assert handler.get_handler_name() == "CodegenPatternHandler"

    def test_get_metrics(self, handler):
        """Test metrics retrieval."""
        handler.metrics["events_handled"] = 10
        handler.metrics["events_failed"] = 2

        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 10
        assert metrics["events_failed"] == 2
        assert metrics["success_rate"] == 10 / 12
        assert metrics["handler_name"] == "CodegenPatternHandler"

    def test_get_metrics_no_events(self, handler):
        """Test metrics when no events processed."""
        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["success_rate"] == 1.0  # Default when no events

    @pytest.mark.asyncio
    async def test_correlation_id_extraction_dict(self, handler):
        """Test correlation ID extraction from dict event."""
        event = {"correlation_id": "dict-123", "payload": {}}

        correlation_id = handler._get_correlation_id(event)
        assert correlation_id == "dict-123"

    @pytest.mark.asyncio
    async def test_correlation_id_extraction_object(self, handler):
        """Test correlation ID extraction from object event."""
        event = MagicMock()
        event.correlation_id = "object-456"

        correlation_id = handler._get_correlation_id(event)
        assert correlation_id == "object-456"

    @pytest.mark.asyncio
    async def test_correlation_id_extraction_unknown(self, handler):
        """Test correlation ID extraction from unknown format."""
        event = "invalid"

        correlation_id = handler._get_correlation_id(event)
        assert correlation_id == "unknown"

    @pytest.mark.asyncio
    async def test_payload_extraction_dict(self, handler):
        """Test payload extraction from dict event."""
        event = {
            "correlation_id": "test",
            "payload": {"key": "value"},
        }

        payload = handler._get_payload(event)
        assert payload == {"key": "value"}

    @pytest.mark.asyncio
    async def test_payload_extraction_object(self, handler):
        """Test payload extraction from object event."""
        event = MagicMock()
        event.payload = {"key": "value"}

        payload = handler._get_payload(event)
        assert payload == {"key": "value"}

    @pytest.mark.asyncio
    async def test_payload_extraction_missing(self, handler):
        """Test payload extraction when missing."""
        event = {"correlation_id": "test"}

        payload = handler._get_payload(event)
        assert payload == {}
