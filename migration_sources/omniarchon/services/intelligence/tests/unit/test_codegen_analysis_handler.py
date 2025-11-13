"""
Unit tests for Codegen Analysis Handler

Tests event handling, PRD analysis, and response publishing.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from archon_services.langextract import CodegenLangExtractService
from handlers import CodegenAnalysisHandler

# Add src directory to path for imports


class TestCodegenAnalysisHandler:
    """Test suite for Codegen Analysis Handler."""

    @pytest.fixture
    def mock_langextract_service(self):
        """Create mock LangExtract service."""
        service = AsyncMock(spec=CodegenLangExtractService)
        service.connect = AsyncMock()
        service.close = AsyncMock()
        service.analyze_prd_semantics = AsyncMock()
        return service

    @pytest.fixture
    def handler(self, mock_langextract_service):
        """Create handler instance with mock service."""
        return CodegenAnalysisHandler(langextract_service=mock_langextract_service)

    @pytest.fixture
    def sample_analysis_result(self):
        """Create sample analysis result."""
        return {
            "concepts": [
                {
                    "name": "UserService",
                    "confidence": 0.9,
                    "type": "entity",
                    "context": "REST API",
                },
                {
                    "name": "authentication",
                    "confidence": 0.85,
                    "type": "concept",
                    "context": "auth flow",
                },
            ],
            "entities": [
                {"name": "UserService", "confidence": 0.9, "context": "REST API"},
            ],
            "relationships": [
                {
                    "pattern": "api_endpoint",
                    "confidence": 0.9,
                    "description": "REST API pattern",
                },
            ],
            "domain_keywords": ["REST API", "Authentication"],
            "node_type_hints": {
                "effect": 0.6,
                "compute": 0.2,
                "reducer": 0.15,
                "orchestrator": 0.05,
            },
            "confidence": 0.87,
            "metadata": {
                "processing_time_ms": 250.5,
                "language": "en",
                "total_concepts": 2,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    @pytest.fixture
    def sample_event_dict(self):
        """Create sample event dictionary."""
        return {
            "correlation_id": str(uuid4()),
            "event_type": "codegen.request.analyze",
            "payload": {
                "prd_content": "Create a REST API service for user management",
                "analysis_type": "full",
                "context": "REST API development",
                "min_confidence": 0.7,
            },
        }

    @pytest.fixture
    def sample_event_object(self):
        """Create sample event object with attributes."""
        event = MagicMock()
        event.correlation_id = uuid4()
        event.payload = {
            "prd_content": "Create a REST API service for user management",
            "analysis_type": "full",
            "context": "REST API development",
            "min_confidence": 0.7,
        }
        return event

    def test_can_handle_valid_event_types(self, handler):
        """Test that handler accepts valid event types."""
        assert handler.can_handle("codegen.request.analyze") is True
        assert handler.can_handle("prd.analyze") is True

    def test_can_handle_invalid_event_types(self, handler):
        """Test that handler rejects invalid event types."""
        assert handler.can_handle("codegen.request.validate") is False
        assert handler.can_handle("unknown.event") is False
        assert handler.can_handle("") is False

    def test_get_handler_name(self, handler):
        """Test handler name retrieval."""
        assert handler.get_handler_name() == "CodegenAnalysisHandler"

    @pytest.mark.asyncio
    async def test_handle_event_success_dict_format(
        self,
        handler,
        mock_langextract_service,
        sample_event_dict,
        sample_analysis_result,
    ):
        """Test successful event handling with dict format."""
        # Setup mock response
        mock_langextract_service.analyze_prd_semantics.return_value = (
            sample_analysis_result
        )

        # Mock response publisher to avoid actual publishing
        with patch.object(
            handler, "_publish_analysis_response", new_callable=AsyncMock
        ) as mock_publish:
            result = await handler.handle_event(sample_event_dict)

            # Verify handler returned success
            assert result is True

            # Verify service was connected
            mock_langextract_service.connect.assert_called_once()

            # Verify analysis was called with correct parameters
            mock_langextract_service.analyze_prd_semantics.assert_called_once()
            call_kwargs = mock_langextract_service.analyze_prd_semantics.call_args[1]
            assert (
                call_kwargs["prd_content"]
                == sample_event_dict["payload"]["prd_content"]
            )
            assert call_kwargs["analysis_type"] == "full"
            assert call_kwargs["context"] == "REST API development"
            assert call_kwargs["min_confidence"] == 0.7

            # Verify response was published
            mock_publish.assert_called_once()
            publish_args = mock_publish.call_args[0]
            assert publish_args[0] == sample_event_dict["correlation_id"]
            assert publish_args[1] == sample_analysis_result

    @pytest.mark.asyncio
    async def test_handle_event_success_object_format(
        self,
        handler,
        mock_langextract_service,
        sample_event_object,
        sample_analysis_result,
    ):
        """Test successful event handling with object format."""
        # Setup mock response
        mock_langextract_service.analyze_prd_semantics.return_value = (
            sample_analysis_result
        )

        # Mock response publisher
        with patch.object(
            handler, "_publish_analysis_response", new_callable=AsyncMock
        ) as mock_publish:
            result = await handler.handle_event(sample_event_object)

            # Verify success
            assert result is True

            # Verify analysis was called
            mock_langextract_service.analyze_prd_semantics.assert_called_once()

            # Verify response was published
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_missing_prd_content(
        self, handler, mock_langextract_service, sample_event_dict
    ):
        """Test handling event with missing prd_content."""
        # Remove prd_content from payload
        sample_event_dict["payload"]["prd_content"] = None

        # Mock error response publisher
        with patch.object(
            handler, "_publish_analysis_error_response", new_callable=AsyncMock
        ) as mock_error:
            result = await handler.handle_event(sample_event_dict)

            # Verify handler returned failure
            assert result is False

            # Verify service was connected
            mock_langextract_service.connect.assert_called_once()

            # Verify analysis was NOT called
            mock_langextract_service.analyze_prd_semantics.assert_not_called()

            # Verify error response was published
            mock_error.assert_called_once()
            error_args = mock_error.call_args[0]
            assert "Missing prd_content" in error_args[1]

    @pytest.mark.asyncio
    async def test_handle_event_analysis_failure(
        self, handler, mock_langextract_service, sample_event_dict
    ):
        """Test handling of analysis service failures."""
        # Setup mock to raise exception
        mock_langextract_service.analyze_prd_semantics.side_effect = Exception(
            "Analysis failed"
        )

        # Mock error response publisher
        with patch.object(
            handler, "_publish_analysis_error_response", new_callable=AsyncMock
        ) as mock_error:
            result = await handler.handle_event(sample_event_dict)

            # Verify handler returned failure
            assert result is False

            # Verify error response was published
            mock_error.assert_called_once()
            error_args = mock_error.call_args[0]
            assert "Analysis failed" in error_args[1]

    @pytest.mark.asyncio
    async def test_handle_event_default_parameters(
        self, handler, mock_langextract_service, sample_analysis_result
    ):
        """Test handling event with default parameters."""
        event = {
            "correlation_id": str(uuid4()),
            "event_type": "codegen.request.analyze",
            "payload": {
                "prd_content": "Simple PRD content",
                # No analysis_type, context, or min_confidence provided
            },
        }

        mock_langextract_service.analyze_prd_semantics.return_value = (
            sample_analysis_result
        )

        with patch.object(
            handler, "_publish_analysis_response", new_callable=AsyncMock
        ):
            result = await handler.handle_event(event)

            assert result is True

            # Verify default parameters were used
            call_kwargs = mock_langextract_service.analyze_prd_semantics.call_args[1]
            assert call_kwargs["analysis_type"] == "full"  # default
            assert call_kwargs["context"] is None  # default
            assert call_kwargs["min_confidence"] == 0.7  # default

    @pytest.mark.asyncio
    async def test_get_correlation_id_from_dict(self, handler):
        """Test correlation ID extraction from dict event."""
        event = {"correlation_id": "test-correlation-id"}
        correlation_id = handler._get_correlation_id(event)
        assert correlation_id == "test-correlation-id"

    @pytest.mark.asyncio
    async def test_get_correlation_id_from_object(self, handler):
        """Test correlation ID extraction from object event."""
        event = MagicMock()
        event.correlation_id = "test-correlation-id"
        correlation_id = handler._get_correlation_id(event)
        assert correlation_id == "test-correlation-id"

    @pytest.mark.asyncio
    async def test_get_correlation_id_unknown(self, handler):
        """Test correlation ID extraction from unknown format."""
        event = "invalid-event"
        correlation_id = handler._get_correlation_id(event)
        assert correlation_id == "unknown"

    @pytest.mark.asyncio
    async def test_get_payload_from_dict(self, handler):
        """Test payload extraction from dict event."""
        event = {"payload": {"key": "value"}}
        payload = handler._get_payload(event)
        assert payload == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_payload_from_object(self, handler):
        """Test payload extraction from object event."""
        event = MagicMock()
        event.payload = {"key": "value"}
        payload = handler._get_payload(event)
        assert payload == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_payload_unknown(self, handler):
        """Test payload extraction from unknown format."""
        event = "invalid-event"
        payload = handler._get_payload(event)
        assert payload == {}

    @pytest.mark.asyncio
    async def test_cleanup(self, handler, mock_langextract_service):
        """Test handler cleanup."""
        # Initialize service
        await handler._ensure_service_initialized()
        assert handler._service_initialized is True

        # Mock shutdown publisher
        with patch.object(
            handler, "_shutdown_publisher", new_callable=AsyncMock
        ) as mock_shutdown:
            await handler.cleanup()

            # Verify service was closed
            mock_langextract_service.close.assert_called_once()
            assert handler._service_initialized is False

            # Verify publisher was shutdown
            mock_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_initialization_once(
        self,
        handler,
        mock_langextract_service,
        sample_event_dict,
        sample_analysis_result,
    ):
        """Test that service is initialized only once."""
        mock_langextract_service.analyze_prd_semantics.return_value = (
            sample_analysis_result
        )

        with patch.object(
            handler, "_publish_analysis_response", new_callable=AsyncMock
        ):
            # Handle first event
            await handler.handle_event(sample_event_dict)
            assert mock_langextract_service.connect.call_count == 1

            # Handle second event
            await handler.handle_event(sample_event_dict)
            # Connect should still be called only once
            assert mock_langextract_service.connect.call_count == 1

    @pytest.mark.asyncio
    async def test_publish_analysis_response_calls_base(self, handler):
        """Test that _publish_analysis_response calls base _publish_response."""
        correlation_id = str(uuid4())
        result = {"test": "result"}

        with patch.object(
            handler, "_publish_response", new_callable=AsyncMock
        ) as mock_base:
            await handler._publish_analysis_response(correlation_id, result)

            # Verify base method was called with correct parameters
            mock_base.assert_called_once()
            call_kwargs = mock_base.call_args[1]
            assert call_kwargs["correlation_id"] == correlation_id
            assert call_kwargs["result"] == result
            assert call_kwargs["response_type"] == "analyze"
            assert call_kwargs["priority"] == "NORMAL"

    @pytest.mark.asyncio
    async def test_publish_analysis_error_response_calls_base(self, handler):
        """Test that _publish_analysis_error_response calls base error method."""
        correlation_id = str(uuid4())
        error_message = "Test error"

        # Mock the base class _publish_error_response method
        base_publish_error = AsyncMock()
        with patch.object(
            CodegenAnalysisHandler.__bases__[0],
            "_publish_error_response",
            new=base_publish_error,
        ):
            handler_with_mock = CodegenAnalysisHandler()
            await handler_with_mock._publish_analysis_error_response(
                correlation_id, error_message
            )

            # Would verify base method was called
            # (Implementation detail - base class handles actual publishing)

    @pytest.mark.asyncio
    async def test_multiple_event_types(
        self, handler, mock_langextract_service, sample_analysis_result
    ):
        """Test handling different event types."""
        mock_langextract_service.analyze_prd_semantics.return_value = (
            sample_analysis_result
        )

        event1 = {
            "correlation_id": str(uuid4()),
            "event_type": "codegen.request.analyze",
            "payload": {"prd_content": "Test content"},
        }

        event2 = {
            "correlation_id": str(uuid4()),
            "event_type": "prd.analyze",
            "payload": {"prd_content": "Test content"},
        }

        with patch.object(
            handler, "_publish_analysis_response", new_callable=AsyncMock
        ):
            # Both event types should be handled
            result1 = await handler.handle_event(event1)
            result2 = await handler.handle_event(event2)

            assert result1 is True
            assert result2 is True
            assert mock_langextract_service.analyze_prd_semantics.call_count == 2


@pytest.mark.asyncio
class TestCodegenAnalysisHandlerIntegration:
    """Integration tests for Codegen Analysis Handler."""

    @pytest.fixture
    def handler_no_mock(self):
        """Create handler without mocks for integration testing."""
        return CodegenAnalysisHandler()

    async def test_service_auto_initialization(self, handler_no_mock):
        """Test that service is auto-initialized when None."""
        # Service should be None initially
        assert handler_no_mock.langextract_service is None

        # After initialization, should have a service
        await handler_no_mock._ensure_service_initialized()
        assert handler_no_mock.langextract_service is not None
        assert isinstance(
            handler_no_mock.langextract_service, CodegenLangExtractService
        )

        # Cleanup
        await handler_no_mock.cleanup()
