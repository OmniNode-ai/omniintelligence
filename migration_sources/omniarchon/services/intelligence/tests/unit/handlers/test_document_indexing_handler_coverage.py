"""
Unit Tests for DocumentIndexingHandler - Comprehensive Coverage (V2)

Simplified and focused on coverage improvement from 17.9% to 70%+

Created: 2025-11-04
"""

from typing import Dict
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from events.models.document_indexing_events import (
    EnumDocumentIndexEventType,
    EnumIndexingErrorCode,
)
from fixtures.kafka_fixtures import MockEventEnvelope
from handlers.document_indexing_handler import DocumentIndexingHandler


# Helper function to create mock HTTP response
def create_mock_response(json_data: Dict) -> MagicMock:
    """Create a mock HTTP response."""
    response = MagicMock()
    response.json = MagicMock(return_value=json_data)
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def handler():
    """Create handler with test configuration."""
    return DocumentIndexingHandler(
        bridge_url="http://test-bridge:8057",
        langextract_url="http://test-langextract:8156",
        qdrant_url="http://test-qdrant:6333",
        memgraph_uri="bolt://test-memgraph:7687",
        intelligence_url="http://test-intelligence:8053",
    )


@pytest.fixture
def handler_with_router(handler):
    """Create handler with mocked router."""
    handler._router = AsyncMock()
    handler._router.publish = AsyncMock()
    handler._router_initialized = True
    return handler


@pytest.fixture
def sample_content():
    """Sample Python code."""
    return """
def test_func():
    pass

class TestClass:
    def method(self):
        pass
"""


# ==============================================================================
# Event Routing Tests (7 tests)
# ==============================================================================


class TestEventRouting:
    def test_can_handle_requested(self, handler):
        assert handler.can_handle("DOCUMENT_INDEX_REQUESTED") is True

    def test_can_handle_enum(self, handler):
        assert (
            handler.can_handle(
                EnumDocumentIndexEventType.DOCUMENT_INDEX_REQUESTED.value
            )
            is True
        )

    def test_can_handle_dotted(self, handler):
        assert handler.can_handle("intelligence.document-index-requested") is True

    def test_can_handle_full_qualified(self, handler):
        assert (
            handler.can_handle(
                "omninode.intelligence.event.document_index_requested.v1"
            )
            is True
        )

    def test_cannot_handle_unknown(self, handler):
        assert handler.can_handle("unknown.event") is False

    def test_cannot_handle_completed(self, handler):
        assert handler.can_handle("DOCUMENT_INDEX_COMPLETED") is False

    def test_cannot_handle_failed(self, handler):
        assert handler.can_handle("DOCUMENT_INDEX_FAILED") is False


# ==============================================================================
# Initialization Tests (5 tests)
# ==============================================================================


class TestInitialization:
    def test_default_urls(self):
        h = DocumentIndexingHandler()
        assert h.bridge_url == "http://localhost:8057"
        assert h.langextract_url == "http://localhost:8156"
        assert h.qdrant_url == "http://localhost:6333"
        assert h.memgraph_uri == "bolt://localhost:7687"
        assert h.intelligence_url == "http://localhost:8053"

    def test_custom_urls(self):
        h = DocumentIndexingHandler(
            bridge_url="http://custom:9000",
            langextract_url="http://custom:9001",
        )
        assert h.bridge_url == "http://custom:9000"
        assert h.langextract_url == "http://custom:9001"

    def test_metrics_initialized(self, handler):
        assert handler.metrics["events_handled"] == 0
        assert handler.metrics["events_failed"] == 0
        assert "service_failures" in handler.metrics

    def test_http_client_none(self, handler):
        assert handler.http_client is None

    def test_handler_name(self, handler):
        assert handler.get_handler_name() == "DocumentIndexingHandler"


# ==============================================================================
# HTTP Client Management Tests (5 tests)
# ==============================================================================


class TestHttpClient:
    @pytest.mark.asyncio
    async def test_ensure_creates_client(self, handler):
        await handler._ensure_http_client()
        assert handler.http_client is not None
        await handler._close_http_client()

    @pytest.mark.asyncio
    async def test_ensure_idempotent(self, handler):
        await handler._ensure_http_client()
        client1 = handler.http_client
        await handler._ensure_http_client()
        assert handler.http_client is client1
        await handler._close_http_client()

    @pytest.mark.asyncio
    async def test_close_client(self, handler):
        await handler._ensure_http_client()
        await handler._close_http_client()
        assert handler.http_client is None

    @pytest.mark.asyncio
    async def test_close_when_none(self, handler):
        await handler._close_http_client()
        assert handler.http_client is None

    @pytest.mark.asyncio
    async def test_shutdown_closes_client(self, handler_with_router):
        await handler_with_router._ensure_http_client()
        await handler_with_router.shutdown()
        assert handler_with_router.http_client is None


# ==============================================================================
# Validation Tests (2 tests)
# ==============================================================================


class TestValidation:
    @pytest.mark.asyncio
    async def test_missing_source_path(self, handler_with_router):
        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"content": "test"},
        )
        success = await handler_with_router.handle_event(event)
        assert success is False
        assert handler_with_router.metrics["indexing_failures"] == 1

    @pytest.mark.asyncio
    async def test_missing_content(self, handler_with_router):
        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py"},
        )
        success = await handler_with_router.handle_event(event)
        assert success is False
        assert handler_with_router.metrics["indexing_failures"] == 1


# ==============================================================================
# Document Indexing Pipeline Tests (3 tests)
# ==============================================================================


class TestPipeline:
    @pytest.mark.asyncio
    async def test_successful_indexing(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()

        async def mock_post(url, **kwargs):
            if "stamp-metadata" in url:
                return create_mock_response(
                    {"hash": "blake3:abc", "dedupe_status": "new"}
                )
            elif "extract/code" in url:
                return create_mock_response({"entities": [], "relationships": []})
            elif "assess/code" in url:
                return create_mock_response({"quality_score": 0.8})
            return MagicMock()

        handler_with_router.http_client.post = mock_post

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={
                "source_path": "test.py",
                "content": sample_content,
                "language": "python",
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True
        assert handler_with_router.metrics["indexing_successes"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        handler_with_router.http_client.post = AsyncMock(
            return_value=create_mock_response(
                {"hash": "blake3:cached", "dedupe_status": "duplicate"}
            )
        )

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py", "content": sample_content},
        )

        success = await handler_with_router.handle_event(event)
        assert success is True
        assert handler_with_router.metrics["cache_hits"] == 1

    @pytest.mark.asyncio
    async def test_metadata_failure(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()

        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        handler_with_router.http_client.post = AsyncMock(return_value=response)

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py", "content": sample_content},
        )

        success = await handler_with_router.handle_event(event)
        assert success is False
        assert handler_with_router.metrics["service_failures"]["metadata_stamping"] == 1


# ==============================================================================
# Service Options Tests (4 tests)
# ==============================================================================


class TestOptions:
    @pytest.mark.asyncio
    async def test_skip_entity_extraction(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        handler_with_router.http_client.post = AsyncMock(
            return_value=create_mock_response(
                {"hash": "blake3:abc", "dedupe_status": "new"}
            )
        )

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={
                "source_path": "test.py",
                "content": sample_content,
                "indexing_options": {"skip_entity_extraction": True},
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True

    @pytest.mark.asyncio
    async def test_skip_quality_assessment(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        handler_with_router.http_client.post = AsyncMock(
            return_value=create_mock_response(
                {"hash": "blake3:abc", "dedupe_status": "new"}
            )
        )

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={
                "source_path": "test.py",
                "content": sample_content,
                "indexing_options": {"skip_quality_assessment": True},
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True

    @pytest.mark.asyncio
    async def test_skip_vector_indexing(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()

        async def mock_post(url, **kwargs):
            if "stamp-metadata" in url:
                return create_mock_response(
                    {"hash": "blake3:abc", "dedupe_status": "new"}
                )
            elif "extract/code" in url:
                return create_mock_response({"entities": [], "relationships": []})
            return MagicMock()

        handler_with_router.http_client.post = mock_post

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={
                "source_path": "test.py",
                "content": sample_content,
                "indexing_options": {"skip_vector_indexing": True},
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True

    @pytest.mark.asyncio
    async def test_skip_knowledge_graph(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()

        async def mock_post(url, **kwargs):
            if "stamp-metadata" in url:
                return create_mock_response(
                    {"hash": "blake3:abc", "dedupe_status": "new"}
                )
            elif "extract/code" in url:
                return create_mock_response(
                    {"entities": [{"name": "test"}], "relationships": []}
                )
            return MagicMock()

        handler_with_router.http_client.post = mock_post

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={
                "source_path": "test.py",
                "content": sample_content,
                "indexing_options": {"skip_knowledge_graph": True},
            },
        )

        success = await handler_with_router.handle_event(event)
        assert success is True


# ==============================================================================
# Content Chunking Tests (3 tests)
# ==============================================================================


class TestChunking:
    def test_basic_chunking(self, handler):
        content = "a" * 1000
        chunks = handler._chunk_content(content, 100, 20)
        assert len(chunks) > 0
        assert len(chunks[0]) == 100

    def test_small_content(self, handler):
        content = "small"
        chunks = handler._chunk_content(content, 1000, 200)
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_chunking_overlap(self, handler):
        content = "abcdefghij" * 20
        chunks = handler._chunk_content(content, 50, 10)
        assert len(chunks) >= 2


# ==============================================================================
# Vector/KG Indexing Tests (2 tests)
# ==============================================================================


class TestIndexing:
    @pytest.mark.asyncio
    async def test_vector_indexing(self, handler):
        result = await handler._index_vectors(
            chunks=["chunk1", "chunk2"],
            source_path="test.py",
            metadata={},
        )
        assert len(result["vector_ids"]) == 2

    @pytest.mark.asyncio
    async def test_kg_indexing(self, handler):
        result = await handler._index_knowledge_graph(
            entities=[{"name": "func1"}],
            relationships=[{"source": "a", "target": "b"}],
            source_path="test.py",
        )
        assert len(result["entity_ids"]) == 1
        assert result["relationships_created"] == 1


# ==============================================================================
# Error Handling Tests (2 tests)
# ==============================================================================


class TestErrors:
    @pytest.mark.asyncio
    async def test_exception_handling(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        handler_with_router.http_client.post = AsyncMock(side_effect=Exception("Error"))

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py", "content": sample_content},
        )

        success = await handler_with_router.handle_event(event)
        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1

    @pytest.mark.asyncio
    async def test_publish_failure_handling(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        handler_with_router.http_client.post = AsyncMock(side_effect=Exception("Error"))
        handler_with_router._router.publish = AsyncMock(
            side_effect=Exception("Publish error")
        )

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py", "content": sample_content},
        )

        success = await handler_with_router.handle_event(event)
        assert success is False


# ==============================================================================
# Metrics Tests (4 tests)
# ==============================================================================


class TestMetrics:
    @pytest.mark.asyncio
    async def test_events_handled_increments(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        handler_with_router.http_client.post = AsyncMock(
            return_value=create_mock_response(
                {"hash": "blake3:abc", "dedupe_status": "new"}
            )
        )

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py", "content": sample_content},
        )

        await handler_with_router.handle_event(event)
        assert handler_with_router.metrics["events_handled"] == 1

    def test_get_metrics_calculates_rates(self, handler):
        handler.metrics["events_handled"] = 8
        handler.metrics["events_failed"] = 2
        handler.metrics["total_processing_time_ms"] = 8000.0
        handler.metrics["cache_hits"] = 3

        metrics = handler.get_metrics()
        assert metrics["success_rate"] == 0.8
        assert metrics["avg_processing_time_ms"] == 1000.0
        assert metrics["cache_hit_rate"] == 0.375

    def test_get_metrics_zero_events(self, handler):
        metrics = handler.get_metrics()
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_service_failure_tracked(self, handler_with_router, sample_content):
        handler_with_router.http_client = AsyncMock()
        response = MagicMock()
        response.raise_for_status.side_effect = Exception("Error")
        handler_with_router.http_client.post = AsyncMock(return_value=response)

        event = MockEventEnvelope(
            event_type="DOCUMENT_INDEX_REQUESTED",
            payload={"source_path": "test.py", "content": sample_content},
        )

        await handler_with_router.handle_event(event)
        assert handler_with_router.metrics["service_failures"]["metadata_stamping"] == 1


# ==============================================================================
# Response Publishing Tests (2 tests)
# ==============================================================================


class TestPublishing:
    @pytest.mark.asyncio
    async def test_publish_completed(self, handler_with_router):
        result = {
            "document_hash": "blake3:abc",
            "entity_ids": [],
            "vector_ids": [],
            "quality_score": 0.8,
            "onex_compliance": 0.9,
            "entities_extracted": 0,
            "relationships_created": 0,
            "chunks_indexed": 0,
            "service_timings": {},
            "cache_hit": False,
            "reindex_required": False,
        }

        await handler_with_router._publish_completed_response(
            correlation_id=str(uuid4()),
            indexing_result=result,
            source_path="test.py",
            processing_time_ms=100.0,
        )

        handler_with_router._router.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_failed(self, handler_with_router):
        await handler_with_router._publish_failed_response(
            correlation_id=str(uuid4()),
            source_path="test.py",
            error_code=EnumIndexingErrorCode.PARSING_ERROR,
            error_message="Error",
            retry_allowed=True,
            processing_time_ms=50.0,
        )

        handler_with_router._router.publish.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
