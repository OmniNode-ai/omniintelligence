"""
Integration Test - Document Processing: Batch Index Operation

Tests complete HTTP flow for POST /batch-index:
1. Handler receives BATCH_INDEX_REQUESTED event
2. Handler calls Intelligence service HTTP endpoint
3. Handler publishes BATCH_INDEX_COMPLETED/FAILED event

Part of Wave 8 - HTTP Implementation + Integration Tests
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from events.models.document_processing_events import EnumDocumentProcessingEventType
from handlers.document_processing_handler import DocumentProcessingHandler


@pytest.fixture
def mock_batch_response():
    """Mock successful batch indexing response."""
    return {
        "documents_indexed": 45,
        "documents_skipped": 3,
        "documents_failed": 2,
        "batch_results": {
            "total_entities": 500,
            "total_embeddings": 450,
        },
        "failed_documents": [
            {
                "path": "doc1.md",
                "error": "Parsing error",
                "error_code": "PARSING_ERROR",
            },
            {
                "path": "doc2.md",
                "error": "Invalid format",
                "error_code": "INVALID_FORMAT",
            },
        ],
    }


@pytest.fixture
def sample_batch_request():
    """Create sample batch index request."""
    correlation_id = str(uuid4())
    payload = {
        "document_paths": [f"docs/doc{i}.md" for i in range(50)],
        "batch_options": {},
        "skip_existing": True,
        "parallel_workers": 4,
    }

    return {
        "event_type": EnumDocumentProcessingEventType.BATCH_INDEX_REQUESTED.value,
        "correlation_id": correlation_id,
        "payload": payload,
    }


@pytest.mark.integration
@pytest.mark.wave8
@pytest.mark.asyncio
class TestDocumentBatchIndexIntegration:
    """Integration tests for Document Batch Index operation."""

    async def test_batch_index_success(
        self,
        sample_batch_request,
        mock_batch_response,
    ):
        """Test successful batch indexing via HTTP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_batch_response
        mock_response.raise_for_status = Mock()

        with patch.object(
            httpx.AsyncClient, "post", return_value=mock_response
        ) as mock_post:
            handler = DocumentProcessingHandler()
            handler._router = AsyncMock()
            handler._router.publish = AsyncMock()
            handler._router_initialized = True

            result = await handler.handle_event(sample_batch_request)

            assert result is True

            # Verify HTTP call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/batch-index" in call_args[0][0]

            # Verify response published
            publish_call = handler._router.publish.call_args
            topic = publish_call[1]["topic"]
            assert "batch-index-completed" in topic

            event = publish_call[1]["event"]
            payload = event["payload"]
            assert payload["documents_indexed"] == 45
            assert payload["documents_failed"] == 2

    async def test_batch_too_large(self):
        """Test batch index with too many documents."""
        correlation_id = str(uuid4())
        large_batch = {
            "document_paths": [f"docs/doc{i}.md" for i in range(1500)],  # Over limit
            "batch_options": {},
        }

        event = {
            "event_type": EnumDocumentProcessingEventType.BATCH_INDEX_REQUESTED.value,
            "correlation_id": correlation_id,
            "payload": large_batch,
        }

        handler = DocumentProcessingHandler()
        handler._router = AsyncMock()
        handler._router.publish = AsyncMock()
        handler._router_initialized = True

        result = await handler.handle_event(event)

        assert result is False

        # Verify failure response
        publish_call = handler._router.publish.call_args
        topic = publish_call[1]["topic"]
        assert "batch-index-failed" in topic
