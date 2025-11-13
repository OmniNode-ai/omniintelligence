"""
Integration Test - Document Processing: Process Document Operation

Tests complete HTTP flow for POST /process/document:
1. Handler receives PROCESS_DOCUMENT_REQUESTED event
2. Handler calls Intelligence service HTTP endpoint
3. Handler publishes PROCESS_DOCUMENT_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.document_processing_events import EnumDocumentProcessingEventType
from handlers.document_processing_handler import DocumentProcessingHandler


@pytest.fixture
def mock_process_response():
    """Mock successful document processing response."""
    return {
        "entities_extracted": 15,
        "embeddings_generated": 10,
        "processing_results": {
            "status": "success",
            "quality_score": 0.85,
        },
        "cache_hit": False,
    }


@pytest.fixture
def sample_process_request():
    """Create sample process document request."""
    correlation_id = str(uuid4())
    payload = {
        "document_path": "docs/architecture.md",
        "content": "# Architecture\n\nThis is a test document.",
        "document_type": "markdown",
        "processing_options": {},
        "extract_entities": True,
        "generate_embeddings": True,
    }

    return {
        "event_type": EnumDocumentProcessingEventType.PROCESS_DOCUMENT_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestDocumentProcessIntegration:
    """Integration tests for Document Process operation."""

    async def test_process_document_success(
        self,
        sample_process_request,
        mock_process_response,
    ):
        """Test successful document processing via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_process_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", return_value=mock_response
        ) as mock_post:
            handler = DocumentProcessingHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_process_request)

            assert result is True

            # Verify HTTP call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/process/document" in call_args[0][0]

            # Verify response published
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "process-document-completed" in topic

            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["entities_extracted"] == 15
            assert payload["embeddings_generated"] == 10
