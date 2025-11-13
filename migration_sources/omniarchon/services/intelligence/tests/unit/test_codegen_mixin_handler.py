"""
Unit tests for Codegen Mixin Handler

Tests event handling for mixin recommendation requests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from handlers import CodegenMixinHandler

# Add src directory to path for imports


class TestCodegenMixinHandler:
    """Test suite for Codegen Mixin Handler."""

    @pytest.fixture
    def mock_pattern_service(self):
        """Create mock pattern service."""
        mock = AsyncMock()
        mock.recommend_mixins.return_value = [
            {
                "mixin_name": "CachingMixin",
                "confidence": 0.85,
                "reason": "Matches requirements: caching needed",
                "required_config": {"cache_ttl_seconds": 300},
            },
            {
                "mixin_name": "MetricsMixin",
                "confidence": 0.65,
                "reason": "Commonly used for this node type",
                "required_config": {},
            },
        ]
        return mock

    @pytest.fixture
    def handler(self, mock_pattern_service):
        """Create handler instance with mocked service."""
        return CodegenMixinHandler(pattern_service=mock_pattern_service)

    def test_can_handle_mixin_request(self, handler):
        """Test that handler accepts mixin request events."""
        assert handler.can_handle("codegen.request.mixin") is True
        assert handler.can_handle("mixin.recommend") is True

    def test_can_handle_other_events(self, handler):
        """Test that handler rejects other event types."""
        assert handler.can_handle("codegen.request.validate") is False
        assert handler.can_handle("codegen.request.pattern") is False
        assert handler.can_handle("unknown.event") is False

    @pytest.mark.asyncio
    async def test_handle_event_success(self, handler, mock_pattern_service):
        """Test successful event handling."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": ["caching needed", "metrics tracking"],
                "node_type": "effect",
            },
        }

        result = await handler.handle_event(event)

        assert result is True
        mock_pattern_service.recommend_mixins.assert_called_once_with(
            requirements=["caching needed", "metrics tracking"],
            node_type="effect",
        )

    @pytest.mark.asyncio
    async def test_handle_event_missing_requirements(
        self, handler, mock_pattern_service
    ):
        """Test handling of event with missing requirements."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "node_type": "effect",
            },
        }

        result = await handler.handle_event(event)

        assert result is False
        mock_pattern_service.recommend_mixins.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_string_requirement(self, handler, mock_pattern_service):
        """Test that single string requirement is converted to list."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": "caching needed",
                "node_type": "effect",
            },
        }

        result = await handler.handle_event(event)

        assert result is True
        mock_pattern_service.recommend_mixins.assert_called_once()
        call_kwargs = mock_pattern_service.recommend_mixins.call_args.kwargs
        assert isinstance(call_kwargs["requirements"], list)
        assert call_kwargs["requirements"] == ["caching needed"]

    @pytest.mark.asyncio
    async def test_handle_event_default_node_type(self, handler, mock_pattern_service):
        """Test that handler uses default node type when not provided."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": ["some requirement"],
            },
        }

        result = await handler.handle_event(event)

        assert result is True
        mock_pattern_service.recommend_mixins.assert_called_once()
        call_kwargs = mock_pattern_service.recommend_mixins.call_args.kwargs
        assert call_kwargs["node_type"] == "effect"  # Default

    @pytest.mark.asyncio
    async def test_handle_event_with_object_format(self, handler, mock_pattern_service):
        """Test handling of event in object format."""
        event = MagicMock()
        event.correlation_id = "test-456"
        event.payload = {
            "requirements": ["retry logic"],
            "node_type": "compute",
        }

        result = await handler.handle_event(event)

        assert result is True
        assert mock_pattern_service.recommend_mixins.called

    @pytest.mark.asyncio
    async def test_handle_event_service_error(self, handler, mock_pattern_service):
        """Test error handling when service fails."""
        mock_pattern_service.recommend_mixins.side_effect = Exception("Service error")

        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": ["some requirement"],
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
                "requirements": ["some requirement"],
            },
        }

        initial_handled = handler.metrics["events_handled"]
        await handler.handle_event(event)

        assert handler.metrics["events_handled"] == initial_handled + 1
        assert handler.metrics["events_failed"] == 0

    @pytest.mark.asyncio
    async def test_metrics_tracking_failure(self, handler, mock_pattern_service):
        """Test that metrics are tracked on failure."""
        mock_pattern_service.recommend_mixins.side_effect = Exception("Error")

        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": ["some requirement"],
            },
        }

        initial_failed = handler.metrics["events_failed"]
        await handler.handle_event(event)

        assert handler.metrics["events_failed"] == initial_failed + 1

    def test_get_handler_name(self, handler):
        """Test handler name retrieval."""
        assert handler.get_handler_name() == "CodegenMixinHandler"

    def test_get_metrics(self, handler):
        """Test metrics retrieval."""
        handler.metrics["events_handled"] = 8
        handler.metrics["events_failed"] = 2

        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 8
        assert metrics["events_failed"] == 2
        assert metrics["success_rate"] == 8 / 10
        assert metrics["handler_name"] == "CodegenMixinHandler"

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

    @pytest.mark.asyncio
    async def test_empty_requirements_list(self, handler, mock_pattern_service):
        """Test handling of empty requirements list."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": [],
                "node_type": "effect",
            },
        }

        result = await handler.handle_event(event)

        # Should fail because requirements list is empty
        assert result is False
        mock_pattern_service.recommend_mixins.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_requirements(self, handler, mock_pattern_service):
        """Test handling of multiple requirements."""
        event = {
            "correlation_id": "test-123",
            "payload": {
                "requirements": ["caching", "metrics", "health check", "retry logic"],
                "node_type": "effect",
            },
        }

        result = await handler.handle_event(event)

        assert result is True
        mock_pattern_service.recommend_mixins.assert_called_once()
        call_kwargs = mock_pattern_service.recommend_mixins.call_args.kwargs
        assert len(call_kwargs["requirements"]) == 4
