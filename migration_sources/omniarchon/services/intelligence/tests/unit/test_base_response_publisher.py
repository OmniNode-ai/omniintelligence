"""
Unit tests for BaseResponsePublisher

Tests response publishing functionality, error handling, and HybridEventRouter integration.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from src.events.models.model_routing_context import ModelRoutingContext
from src.handlers import BaseResponsePublisher

# Add src directory to path for imports


class MockHandler(BaseResponsePublisher):
    """Mock handler for testing BaseResponsePublisher mixin."""

    def __init__(self):
        super().__init__()
        self.handler_name = "MockHandler"


class TestBaseResponsePublisher:
    """Test suite for BaseResponsePublisher mixin."""

    @pytest.fixture
    def handler(self):
        """Create handler instance with mocked router."""
        handler = MockHandler()
        # Mock the router to avoid real Kafka connections
        handler._router = AsyncMock()
        handler._router_initialized = True
        handler._router.publish = AsyncMock()
        return handler

    @pytest.mark.asyncio
    async def test_publish_response_success(self, handler):
        """Test successful response publishing."""
        correlation_id = str(uuid4())
        result = {
            "quality_score": 0.85,
            "onex_compliance_score": 0.90,
            "is_valid": True,
            "violations": [],
            "warnings": [],
            "suggestions": ["Good job!"],
        }

        await handler._publish_response(
            correlation_id=correlation_id,
            result=result,
            response_type="validate",
            priority="NORMAL",
        )

        # Verify router.publish was called
        handler._router.publish.assert_called_once()
        call_args = handler._router.publish.call_args

        # Verify topic
        assert call_args[1]["topic"] == "omninode.codegen.response.validate.v1"

        # Verify event structure
        event = call_args[1]["event"]
        assert (
            event.correlation_id == correlation_id
            or str(event.correlation_id) == correlation_id
        )
        assert event.payload == result
        assert event.source_service == "archon-intelligence"

        # Verify routing context
        context = call_args[1]["context"]
        assert isinstance(context, ModelRoutingContext)
        assert context.requires_persistence is True
        assert context.is_cross_service is True

        # Verify key
        assert call_args[1]["key"] == correlation_id

    @pytest.mark.asyncio
    async def test_publish_response_all_types(self, handler):
        """Test publishing for all response types."""
        correlation_id = str(uuid4())
        result = {"test": "data"}
        response_types = ["analyze", "validate", "pattern", "mixin"]

        for response_type in response_types:
            handler._router.publish.reset_mock()

            await handler._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type=response_type,
            )

            call_args = handler._router.publish.call_args
            expected_topic = f"omninode.codegen.response.{response_type}.v1"
            assert call_args[1]["topic"] == expected_topic

    @pytest.mark.asyncio
    async def test_publish_response_with_priority(self, handler):
        """Test response publishing with different priority levels."""
        correlation_id = str(uuid4())
        result = {"test": "data"}
        priorities = ["CRITICAL", "HIGH", "NORMAL", "LOW"]

        for priority in priorities:
            handler._router.publish.reset_mock()

            await handler._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="validate",
                priority=priority,
            )

            call_args = handler._router.publish.call_args
            event = call_args[1]["event"]
            assert event.priority == priority

            context = call_args[1]["context"]
            assert context.priority_level == priority

    @pytest.mark.asyncio
    async def test_publish_error_response_success(self, handler):
        """Test successful error response publishing."""
        correlation_id = str(uuid4())
        error_message = "Test error message"

        await handler._publish_error_response(
            correlation_id=correlation_id,
            error_message=error_message,
            response_type="validate",
            error_code="TEST_ERROR",
        )

        # Verify publish was called
        handler._router.publish.assert_called_once()
        call_args = handler._router.publish.call_args

        # Verify error payload structure
        event = call_args[1]["event"]
        payload = event.payload
        assert payload["is_valid"] is False
        assert payload["quality_score"] == 0.0
        assert payload["onex_compliance_score"] == 0.0
        assert len(payload["violations"]) > 0
        assert "Handler error" in payload["violations"][0]
        assert error_message in payload["violations"][0]
        assert payload["details"]["error"] == error_message
        assert payload["details"]["error_code"] == "TEST_ERROR"

    @pytest.mark.asyncio
    async def test_ensure_router_initialized_success(self, handler):
        """Test router initialization."""
        # Reset initialization
        handler._router_initialized = False
        handler._router = None

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router_class.return_value = mock_router

            await handler._ensure_router_initialized()

            assert handler._router_initialized is True
            assert handler._router is not None
            mock_router.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_router_initialized_idempotent(self, handler):
        """Test that router initialization is idempotent."""
        # Already initialized
        assert handler._router_initialized is True
        initial_router = handler._router

        await handler._ensure_router_initialized()

        # Should not create new router
        assert handler._router is initial_router

    @pytest.mark.asyncio
    async def test_publish_response_router_not_initialized(self):
        """Test publishing when router is not initialized."""
        handler = MockHandler()
        handler._router_initialized = False

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.publish = AsyncMock()
            mock_router_class.return_value = mock_router

            correlation_id = str(uuid4())
            result = {"test": "data"}

            await handler._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="validate",
            )

            # Verify initialization was called
            mock_router.initialize.assert_called_once()
            # Verify publish was called
            mock_router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_response_handles_publish_failure(self, handler, caplog):
        """Test that publish failures are logged but don't crash."""
        handler._router.publish.side_effect = Exception("Publish failed")

        correlation_id = str(uuid4())
        result = {"test": "data"}

        # Should not raise exception
        await handler._publish_response(
            correlation_id=correlation_id,
            result=result,
            response_type="validate",
        )

        # Verify error was logged
        assert any(
            "Failed to publish response" in record.message for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_publish_response_initialization_failure_raises(self, handler):
        """Test that initialization failures raise RuntimeError."""
        handler._router_initialized = False
        handler._router = None

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize.side_effect = Exception("Init failed")
            mock_router_class.return_value = mock_router

            correlation_id = str(uuid4())
            result = {"test": "data"}

            # Should raise RuntimeError for initialization failure
            with pytest.raises(RuntimeError) as exc_info:
                await handler._publish_response(
                    correlation_id=correlation_id,
                    result=result,
                    response_type="validate",
                )

            assert "initialize" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_publish_error_response_with_default_error_code(self, handler):
        """Test error response with default error code."""
        correlation_id = str(uuid4())
        error_message = "Something went wrong"

        await handler._publish_error_response(
            correlation_id=correlation_id,
            error_message=error_message,
            response_type="analyze",
            error_code=None,  # Use default
        )

        call_args = handler._router.publish.call_args
        event = call_args[1]["event"]
        payload = event.payload
        assert payload["details"]["error_code"] == "HANDLER_ERROR"

    @pytest.mark.asyncio
    async def test_publish_error_response_handles_failure(self, handler, caplog):
        """Test that error response publishing failures are logged."""
        handler._router.publish.side_effect = Exception("Critical failure")

        correlation_id = str(uuid4())
        error_message = "Original error"

        # Should not crash
        await handler._publish_error_response(
            correlation_id=correlation_id,
            error_message=error_message,
            response_type="validate",
        )

        # Verify critical error was logged (both publish failure and error response)
        assert any(
            "Failed to publish response" in record.message for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_shutdown_publisher_success(self, handler):
        """Test publisher shutdown."""
        await handler._shutdown_publisher()

        handler._router.shutdown.assert_called_once()
        assert handler._router_initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_publisher_handles_error(self, handler, caplog):
        """Test that shutdown errors are logged."""
        handler._router.shutdown.side_effect = Exception("Shutdown failed")

        await handler._shutdown_publisher()

        # Should not crash
        assert handler._router_initialized is False
        assert any("Error shutting down" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_shutdown_publisher_not_initialized(self):
        """Test shutdown when publisher was never initialized."""
        handler = MockHandler()
        handler._router = None
        handler._router_initialized = False

        # Should not crash
        await handler._shutdown_publisher()

        assert handler._router_initialized is False

    @pytest.mark.asyncio
    async def test_correlation_id_uuid_handling(self, handler):
        """Test that both string and UUID correlation IDs are handled."""
        result = {"test": "data"}

        # Test with string correlation ID
        str_correlation_id = str(uuid4())
        await handler._publish_response(
            correlation_id=str_correlation_id,
            result=result,
            response_type="validate",
        )

        call_args = handler._router.publish.call_args
        event = call_args[1]["event"]
        # Should convert to UUID
        assert str(event.correlation_id) == str_correlation_id

    @pytest.mark.asyncio
    async def test_routing_context_fields(self, handler):
        """Test that routing context has correct fields."""
        correlation_id = str(uuid4())
        result = {"test": "data"}

        await handler._publish_response(
            correlation_id=correlation_id,
            result=result,
            response_type="validate",
            priority="HIGH",
        )

        call_args = handler._router.publish.call_args
        context = call_args[1]["context"]

        assert context.requires_persistence is True
        assert context.is_cross_service is True
        assert context.is_test_environment is False
        assert context.is_local_tool is False
        assert context.priority_level == "HIGH"
        assert context.service_name == "archon-intelligence"

    @pytest.mark.asyncio
    async def test_event_metadata_fields(self, handler):
        """Test that event has all required metadata fields."""
        correlation_id = str(uuid4())
        result = {"test": "data"}

        await handler._publish_response(
            correlation_id=correlation_id,
            result=result,
            response_type="analyze",
        )

        call_args = handler._router.publish.call_args
        event = call_args[1]["event"]

        # Verify metadata fields
        assert event.source_service == "archon-intelligence"
        assert event.source_version == "1.0.0"
        assert event.payload_type == "CodegenAnalyzeResponse"
        assert event.payload == result
        assert isinstance(event.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_multiple_responses_different_handlers(self):
        """Test multiple handlers can publish independently."""
        handler1 = MockHandler()
        handler1._router = AsyncMock()
        handler1._router_initialized = True
        handler1._router.publish = AsyncMock()

        handler2 = MockHandler()
        handler2._router = AsyncMock()
        handler2._router_initialized = True
        handler2._router.publish = AsyncMock()

        correlation_id1 = str(uuid4())
        correlation_id2 = str(uuid4())

        await handler1._publish_response(
            correlation_id=correlation_id1,
            result={"data": "handler1"},
            response_type="validate",
        )

        await handler2._publish_response(
            correlation_id=correlation_id2,
            result={"data": "handler2"},
            response_type="analyze",
        )

        # Verify both published independently
        handler1._router.publish.assert_called_once()
        handler2._router.publish.assert_called_once()


@pytest.mark.asyncio
class TestBaseResponsePublisherIntegration:
    """Integration tests for BaseResponsePublisher with real components."""

    async def test_full_response_lifecycle(self):
        """Test full response publishing lifecycle."""
        handler = MockHandler()

        with patch(
            "src.handlers.base_response_publisher.HybridEventRouter"
        ) as mock_router_class:
            mock_router = AsyncMock()
            mock_router.initialize = AsyncMock()
            mock_router.publish = AsyncMock()
            mock_router.shutdown = AsyncMock()
            mock_router_class.return_value = mock_router

            # Initialize
            await handler._ensure_router_initialized()
            assert handler._router_initialized is True

            # Publish response
            correlation_id = str(uuid4())
            result = {"quality_score": 0.9}
            await handler._publish_response(
                correlation_id=correlation_id,
                result=result,
                response_type="validate",
            )

            # Verify publish called
            mock_router.publish.assert_called_once()

            # Shutdown
            await handler._shutdown_publisher()
            mock_router.shutdown.assert_called_once()
            assert handler._router_initialized is False
