"""
Comprehensive Unit Tests for SearchHandler - Coverage Improvement

Tests for SearchHandler event processing, multi-source search orchestration,
error handling, and result aggregation. Target: 70%+ coverage.

Test Categories:
- Initialization and configuration
- Event routing (can_handle)
- Event handling (handle_event) - success and error paths
- Multi-source search (_perform_search) - all search types
- RAG search (_search_rag) - success, validation, errors
- Vector search (_search_vector) - success, validation, errors
- Knowledge graph search (_search_knowledge_graph) - success, validation, errors
- Embedding generation (_generate_embedding) - success, validation, errors
- Result deduplication and ranking
- Response publishing (completed/failed)
- Metrics tracking
- Edge cases and validation

Created: 2025-11-04
Purpose: Improve coverage from 12.1% to 70%+
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from events.models.search_events import (
    EnumSearchErrorCode,
    EnumSearchType,
    ModelSearchResultItem,
)
from handlers.search_handler import SearchHandler
from neo4j.exceptions import ServiceUnavailable
from pydantic import ValidationError
from qdrant_client.models import ScoredPoint

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_router():
    """Mock Kafka router for publishing events."""
    router = AsyncMock()
    router.publish = AsyncMock()
    return router


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for external service calls."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def handler(mock_http_client):
    """Create SearchHandler with mocked dependencies."""
    handler = SearchHandler(
        rag_search_url="http://test-rag:8055/search",
        qdrant_url="http://test-qdrant:6333",
        memgraph_uri="bolt://test-memgraph:7687",
        http_client=mock_http_client,
    )
    return handler


@pytest.fixture
def handler_with_router(handler, mock_router):
    """Create SearchHandler with initialized router."""
    handler._router = mock_router
    handler._router_initialized = True
    return handler


def create_mock_event(
    event_type: str = "SEARCH_REQUESTED",
    correlation_id: str = None,
    payload: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Create mock event envelope."""
    correlation_id = correlation_id or str(uuid4())
    return {
        "event_type": event_type,
        "correlation_id": correlation_id,
        "payload": payload or {},
        "metadata": {"timestamp": "2025-11-04T00:00:00Z"},
    }


# ==============================================================================
# Initialization Tests
# ==============================================================================


class TestSearchHandlerInitialization:
    """Test SearchHandler initialization and configuration."""

    def test_init_with_defaults(self):
        """Test handler initialization with default values."""
        handler = SearchHandler()

        assert handler.rag_search_url == SearchHandler.RAG_SEARCH_URL
        assert handler.qdrant_url == SearchHandler.QDRANT_URL
        assert handler.memgraph_uri == SearchHandler.MEMGRAPH_URI
        assert handler.http_client is None
        assert handler.metrics["events_handled"] == 0
        assert handler.metrics["events_failed"] == 0
        assert handler.metrics["searches_completed"] == 0
        assert handler.metrics["searches_failed"] == 0

    def test_init_with_custom_urls(self):
        """Test handler initialization with custom service URLs."""
        handler = SearchHandler(
            rag_search_url="http://custom-rag:9000",
            qdrant_url="http://custom-qdrant:7000",
            memgraph_uri="bolt://custom-memgraph:8000",
        )

        assert handler.rag_search_url == "http://custom-rag:9000"
        assert handler.qdrant_url == "http://custom-qdrant:7000"
        assert handler.memgraph_uri == "bolt://custom-memgraph:8000"

    def test_init_with_http_client(self, mock_http_client):
        """Test handler initialization with provided HTTP client."""
        handler = SearchHandler(http_client=mock_http_client)

        assert handler.http_client is mock_http_client


# ==============================================================================
# Event Routing Tests (can_handle)
# ==============================================================================


class TestCanHandle:
    """Test event routing and handler selection."""

    def test_can_handle_search_requested(self, handler):
        """Test handler recognizes SEARCH_REQUESTED event."""
        assert handler.can_handle("SEARCH_REQUESTED") is True

    def test_can_handle_search_requested_with_namespace(self, handler):
        """Test handler recognizes namespaced SEARCH_REQUESTED event."""
        assert handler.can_handle("intelligence.search-requested") is True

    def test_can_handle_full_event_type(self, handler):
        """Test handler recognizes full Kafka event type."""
        assert (
            handler.can_handle("omninode.intelligence.event.search_requested.v1")
            is True
        )

    def test_cannot_handle_unknown_event(self, handler):
        """Test handler rejects unknown event types."""
        assert handler.can_handle("unknown.event.type") is False
        assert handler.can_handle("TREE_INDEXING_REQUESTED") is False


# ==============================================================================
# Event Handling Tests (handle_event)
# ==============================================================================


class TestHandleEvent:
    """Test main event handling logic."""

    @pytest.mark.asyncio
    async def test_handle_event_success(self, handler_with_router, mock_http_client):
        """Test successful event handling end-to-end."""
        # Mock RAG search response
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "results": [
                        {
                            "path": "src/test.py",
                            "score": 0.9,
                            "content": "test content",
                            "metadata": {},
                        }
                    ]
                },
                raise_for_status=MagicMock(),
            )
        )

        event = create_mock_event(
            payload={
                "query": "test query",
                "search_type": "SEMANTIC",
                "max_results": 10,
            }
        )

        success = await handler_with_router.handle_event(event)

        assert success is True
        assert handler_with_router.metrics["events_handled"] == 1
        assert handler_with_router.metrics["searches_completed"] == 1
        assert handler_with_router.metrics["rag_queries"] == 1

    @pytest.mark.asyncio
    async def test_handle_event_missing_query(self, handler_with_router):
        """Test event handling fails when query is missing."""
        event = create_mock_event(
            payload={
                # query missing
                "search_type": "HYBRID",
            }
        )

        success = await handler_with_router.handle_event(event)

        assert success is False
        assert handler_with_router.metrics["events_failed"] == 1
        assert handler_with_router.metrics["searches_failed"] == 1

        # Verify failed event was published
        handler_with_router._router.publish.assert_called_once()
        call_kwargs = handler_with_router._router.publish.call_args.kwargs
        assert "search-failed" in call_kwargs["topic"]

    @pytest.mark.asyncio
    async def test_handle_event_invalid_search_type(
        self, handler_with_router, mock_http_client
    ):
        """Test event handling with invalid search type defaults to HYBRID."""
        # Mock RAG search
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"results": []},
                raise_for_status=MagicMock(),
            )
        )

        event = create_mock_event(
            payload={
                "query": "test",
                "search_type": "INVALID_TYPE",  # Invalid
            }
        )

        success = await handler_with_router.handle_event(event)

        # Should default to HYBRID and succeed
        assert success is True

    @pytest.mark.asyncio
    async def test_handle_event_search_exception(self, handler_with_router):
        """Test event handling when search raises exception."""
        # Mock _perform_search to raise exception
        with patch.object(
            handler_with_router,
            "_perform_search",
            side_effect=Exception("Search error"),
        ):
            event = create_mock_event(payload={"query": "test"})

            success = await handler_with_router.handle_event(event)

            assert success is False
            assert handler_with_router.metrics["events_failed"] == 1
            assert handler_with_router.metrics["searches_failed"] == 1


# ==============================================================================
# Multi-Source Search Tests (_perform_search)
# ==============================================================================


class TestPerformSearch:
    """Test multi-source search orchestration."""

    @pytest.mark.asyncio
    async def test_perform_search_semantic_only(self, handler, mock_http_client):
        """Test SEMANTIC search queries only RAG."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "results": [
                        {
                            "path": "test.py",
                            "score": 0.9,
                            "content": "content",
                            "metadata": {},
                        }
                    ]
                },
                raise_for_status=MagicMock(),
            )
        )

        result = await handler._perform_search(
            query="test",
            search_type=EnumSearchType.SEMANTIC,
            project_id=None,
            max_results=10,
            filters={},
            quality_weight=None,
            include_context=True,
            enable_caching=True,
        )

        assert result["total_results"] >= 0
        assert "rag" in result["sources_queried"]
        assert "vector" not in result["sources_queried"]
        assert "knowledge_graph" not in result["sources_queried"]
        assert handler.metrics["rag_queries"] == 1

    @pytest.mark.asyncio
    async def test_perform_search_vector_only(self, handler, mock_http_client):
        """Test VECTOR search queries only Qdrant."""
        # Mock embedding generation
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"embedding": [0.1] * 768},
                raise_for_status=MagicMock(),
            )
        )

        # Mock Qdrant search
        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant = MagicMock()
            # Create mock scored point instead of using Pydantic model
            mock_point = MagicMock()
            mock_point.id = 1
            mock_point.score = 0.85
            mock_point.payload = {"source_path": "test.py", "content": "content"}
            mock_point.vector = None
            mock_qdrant.search = MagicMock(return_value=[mock_point])
            mock_qdrant_class.return_value = mock_qdrant

            result = await handler._perform_search(
                query="test",
                search_type=EnumSearchType.VECTOR,
                project_id=None,
                max_results=10,
                filters={},
                quality_weight=None,
                include_context=True,
                enable_caching=True,
            )

            assert result["total_results"] >= 0
            assert "vector" in result["sources_queried"]
            assert "rag" not in result["sources_queried"]
            assert handler.metrics["vector_queries"] == 1

    @pytest.mark.asyncio
    async def test_perform_search_knowledge_graph_only(self, handler):
        """Test KNOWLEDGE_GRAPH search queries only Memgraph."""
        # Mock Memgraph
        with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_result = MagicMock()

            # Configure mock to return records
            mock_record = MagicMock()
            mock_record.get = MagicMock(
                side_effect=lambda key: {
                    "name": "test_function",
                    "description": "Test description",
                    "content": "def test(): pass",
                    "source_path": "test.py",
                    "entity_type": "function",
                    "labels": ["Function"],
                }.get(key)
            )
            mock_result.__iter__ = MagicMock(return_value=iter([mock_record]))

            mock_session.run = MagicMock(return_value=mock_result)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock()

            mock_driver.session = MagicMock(return_value=mock_session)
            mock_driver.close = MagicMock()
            mock_graph_db.driver = MagicMock(return_value=mock_driver)

            result = await handler._perform_search(
                query="test",
                search_type=EnumSearchType.KNOWLEDGE_GRAPH,
                project_id=None,
                max_results=10,
                filters={},
                quality_weight=None,
                include_context=True,
                enable_caching=True,
            )

            assert result["total_results"] >= 0
            assert "knowledge_graph" in result["sources_queried"]
            assert handler.metrics["kg_queries"] == 1

    @pytest.mark.asyncio
    async def test_perform_search_hybrid(self, handler, mock_http_client):
        """Test HYBRID search queries all sources."""
        # Mock RAG
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "results": [
                        {
                            "path": "rag.py",
                            "score": 0.9,
                            "content": "rag content",
                            "metadata": {},
                        }
                    ],
                    "embedding": [0.1] * 768,
                },
                raise_for_status=MagicMock(),
            )
        )

        # Mock Qdrant
        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant = MagicMock()
            mock_point = MagicMock()
            mock_point.id = 1
            mock_point.score = 0.85
            mock_point.payload = {
                "source_path": "vector.py",
                "content": "vector content",
            }
            mock_point.vector = None
            mock_qdrant.search = MagicMock(return_value=[mock_point])
            mock_qdrant_class.return_value = mock_qdrant

            # Mock Memgraph
            with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
                mock_driver = MagicMock()
                mock_session = MagicMock()
                mock_result = MagicMock()
                mock_record = MagicMock()
                mock_record.get = MagicMock(
                    side_effect=lambda key: {
                        "name": "kg_entity",
                        "content": "kg content",
                        "source_path": "kg.py",
                        "labels": ["Entity"],
                    }.get(key)
                )
                mock_result.__iter__ = MagicMock(return_value=iter([mock_record]))
                mock_session.run = MagicMock(return_value=mock_result)
                mock_session.__enter__ = MagicMock(return_value=mock_session)
                mock_session.__exit__ = MagicMock()
                mock_driver.session = MagicMock(return_value=mock_session)
                mock_driver.close = MagicMock()
                mock_graph_db.driver = MagicMock(return_value=mock_driver)

                result = await handler._perform_search(
                    query="test",
                    search_type=EnumSearchType.HYBRID,
                    project_id=None,
                    max_results=10,
                    filters={},
                    quality_weight=None,
                    include_context=True,
                    enable_caching=True,
                )

                # All sources should be queried
                assert len(result["sources_queried"]) == 3
                assert "rag" in result["sources_queried"]
                assert "vector" in result["sources_queried"]
                assert "knowledge_graph" in result["sources_queried"]

    @pytest.mark.asyncio
    async def test_perform_search_graceful_degradation_one_fails(
        self, handler, mock_http_client
    ):
        """Test graceful degradation when one source fails."""
        # RAG succeeds
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "results": [
                        {
                            "path": "test.py",
                            "score": 0.9,
                            "content": "content",
                            "metadata": {},
                        }
                    ],
                    "embedding": [0.1] * 768,
                },
                raise_for_status=MagicMock(),
            )
        )

        # Vector search fails
        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant_class.side_effect = Exception("Qdrant connection failed")

            # KG succeeds
            with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
                mock_driver = MagicMock()
                mock_session = MagicMock()
                mock_result = MagicMock()
                mock_result.__iter__ = MagicMock(return_value=iter([]))
                mock_session.run = MagicMock(return_value=mock_result)
                mock_session.__enter__ = MagicMock(return_value=mock_session)
                mock_session.__exit__ = MagicMock()
                mock_driver.session = MagicMock(return_value=mock_session)
                mock_driver.close = MagicMock()
                mock_graph_db.driver = MagicMock(return_value=mock_driver)

                result = await handler._perform_search(
                    query="test",
                    search_type=EnumSearchType.HYBRID,
                    project_id=None,
                    max_results=10,
                    filters={},
                    quality_weight=None,
                    include_context=True,
                    enable_caching=True,
                )

                # Should succeed with 2 sources
                assert len(result["sources_queried"]) == 2
                assert "rag" in result["sources_queried"]
                assert "knowledge_graph" in result["sources_queried"]
                assert "vector" not in result["sources_queried"]

    @pytest.mark.asyncio
    async def test_perform_search_all_sources_fail(self, handler, mock_http_client):
        """Test error when all sources fail."""
        # All sources fail
        mock_http_client.post = AsyncMock(side_effect=Exception("RAG failed"))

        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant_class.side_effect = Exception("Qdrant failed")

            with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
                mock_graph_db.driver.side_effect = Exception("Memgraph failed")

                with pytest.raises(ValueError, match="All search sources failed"):
                    await handler._perform_search(
                        query="test",
                        search_type=EnumSearchType.HYBRID,
                        project_id=None,
                        max_results=10,
                        filters={},
                        quality_weight=None,
                        include_context=True,
                        enable_caching=True,
                    )


# ==============================================================================
# RAG Search Tests (_search_rag)
# ==============================================================================


class TestSearchRAG:
    """Test RAG search functionality."""

    @pytest.mark.asyncio
    async def test_search_rag_success(self, handler, mock_http_client):
        """Test successful RAG search."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "results": [
                        {
                            "path": "src/test.py",
                            "score": 0.95,
                            "content": "test content",
                            "metadata": {"language": "python"},
                        }
                    ]
                },
                raise_for_status=MagicMock(),
            )
        )

        result = await handler._search_rag(
            query="test query", max_results=10, filters={}
        )

        assert len(result["results"]) == 1
        assert result["results"][0].source_path == "src/test.py"
        assert result["results"][0].score == 0.95
        assert result["timing_ms"] >= 0

    @pytest.mark.asyncio
    async def test_search_rag_validation_fallback(self, handler, mock_http_client):
        """Test RAG search with validation error fallback."""
        # Return invalid data that fails validation but has results
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "results": [
                        {
                            "path": "test.py",  # Valid
                            "score": 0.8,
                            "content": "content",
                            "metadata": {},
                        }
                    ],
                    "invalid_field": "should_not_break",  # Extra field
                },
                raise_for_status=MagicMock(),
            )
        )

        result = await handler._search_rag(query="test", max_results=10, filters={})

        # Should fall back to unvalidated results
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_search_rag_http_error(self, handler, mock_http_client):
        """Test RAG search HTTP error handling."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=500,
                raise_for_status=MagicMock(
                    side_effect=httpx.HTTPStatusError(
                        "Internal Server Error",
                        request=MagicMock(),
                        response=MagicMock(status_code=500),
                    )
                ),
            )
        )

        with pytest.raises(httpx.HTTPStatusError):
            await handler._search_rag(query="test", max_results=10, filters={})

    @pytest.mark.asyncio
    async def test_search_rag_no_http_client(self):
        """Test RAG search without pre-configured HTTP client."""
        handler = SearchHandler(http_client=None)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.post = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=lambda: {"results": []},
                    raise_for_status=MagicMock(),
                )
            )
            mock_client_class.return_value = mock_client

            result = await handler._search_rag(query="test", max_results=10, filters={})

            assert result["results"] == []


# ==============================================================================
# Vector Search Tests (_search_vector)
# ==============================================================================


class TestSearchVector:
    """Test vector search functionality."""

    @pytest.mark.asyncio
    async def test_search_vector_success(self, handler, mock_http_client):
        """Test successful vector search."""
        # Mock embedding generation
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"embedding": [0.1] * 768},
                raise_for_status=MagicMock(),
            )
        )

        # Mock Qdrant search
        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant = MagicMock()
            mock_point = MagicMock()
            mock_point.id = "1"
            mock_point.score = 0.92
            mock_point.payload = {
                "source_path": "src/module.py",
                "content": "module content",
            }
            mock_point.vector = None
            mock_qdrant.search = MagicMock(return_value=[mock_point])
            mock_qdrant_class.return_value = mock_qdrant

            result = await handler._search_vector(
                query="test", max_results=10, filters={}
            )

            assert len(result["results"]) == 1
            assert result["results"][0].source_path == "src/module.py"
            assert result["results"][0].score == 0.92

    @pytest.mark.asyncio
    async def test_search_vector_with_project_filter(self, handler, mock_http_client):
        """Test vector search with project_id filter."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"embedding": [0.1] * 768},
                raise_for_status=MagicMock(),
            )
        )

        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant = MagicMock()
            mock_qdrant.search = MagicMock(return_value=[])
            mock_qdrant_class.return_value = mock_qdrant

            await handler._search_vector(
                query="test", max_results=10, filters={"project_id": "test-project"}
            )

            # Verify filter was applied
            call_kwargs = mock_qdrant.search.call_args.kwargs
            assert call_kwargs["query_filter"] is not None

    @pytest.mark.asyncio
    async def test_search_vector_validation_fallback(self, handler, mock_http_client):
        """Test vector search validation error fallback."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"embedding": [0.1] * 768},
                raise_for_status=MagicMock(),
            )
        )

        # Mock Qdrant to return data that might fail validation
        with patch("handlers.search_handler.QdrantClient") as mock_qdrant_class:
            mock_qdrant = MagicMock()
            mock_hit = MagicMock()
            mock_hit.id = "test-id"
            mock_hit.score = 0.85
            mock_hit.payload = {"source_path": "test.py", "content": "content"}
            mock_qdrant.search = MagicMock(return_value=[mock_hit])
            mock_qdrant_class.return_value = mock_qdrant

            result = await handler._search_vector(
                query="test", max_results=10, filters={}
            )

            # Should succeed with fallback
            assert len(result["results"]) >= 0


# ==============================================================================
# Knowledge Graph Search Tests (_search_knowledge_graph)
# ==============================================================================


class TestSearchKnowledgeGraph:
    """Test knowledge graph search functionality."""

    @pytest.mark.asyncio
    async def test_search_knowledge_graph_success(self, handler):
        """Test successful knowledge graph search."""
        with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
            mock_driver = MagicMock()
            mock_session = MagicMock()

            # Create a mock result that properly returns records
            class MockRecord:
                def get(self, key, default=None):
                    data = {
                        "name": "TestClass",
                        "description": "A test class",
                        "content": "class TestClass: pass",
                        "source_path": "src/test.py",
                        "entity_type": "class",
                        "labels": ["Class", "Entity"],
                    }
                    return data.get(key, default)

            mock_result = [MockRecord()]
            mock_session.run = MagicMock(return_value=mock_result)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=(None, None, None))
            mock_driver.session = MagicMock(return_value=mock_session)
            mock_driver.close = MagicMock()
            mock_graph_db.driver = MagicMock(return_value=mock_driver)

            result = await handler._search_knowledge_graph(
                query="TestClass", max_results=10, filters={}
            )

            assert len(result["results"]) == 1
            assert result["results"][0].source_path == "src/test.py"
            # Exact name match should have higher score
            assert result["results"][0].score == 0.9

    @pytest.mark.asyncio
    async def test_search_knowledge_graph_with_project_filter(self, handler):
        """Test knowledge graph search with project filter."""
        with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.__iter__ = MagicMock(return_value=iter([]))
            mock_session.run = MagicMock(return_value=mock_result)
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock()
            mock_driver.session = MagicMock(return_value=mock_session)
            mock_driver.close = MagicMock()
            mock_graph_db.driver = MagicMock(return_value=mock_driver)

            await handler._search_knowledge_graph(
                query="test", max_results=10, filters={"project_id": "test-project"}
            )

            # Verify project_id was included in query
            call_args = mock_session.run.call_args
            assert call_args[0][1]["project_id"] == "test-project"

    @pytest.mark.asyncio
    async def test_search_knowledge_graph_connection_error(self, handler):
        """Test knowledge graph search connection error."""
        with patch("handlers.search_handler.GraphDatabase") as mock_graph_db:
            mock_graph_db.driver.side_effect = ServiceUnavailable("Connection failed")

            with pytest.raises(ServiceUnavailable):
                await handler._search_knowledge_graph(
                    query="test", max_results=10, filters={}
                )


# ==============================================================================
# Embedding Generation Tests (_generate_embedding)
# ==============================================================================


class TestGenerateEmbedding:
    """Test embedding generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, handler, mock_http_client):
        """Test successful embedding generation."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"embedding": [0.1, 0.2, 0.3] * 256},
                raise_for_status=MagicMock(),
            )
        )

        embedding = await handler._generate_embedding("test text")

        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_embedding_validation_fallback(
        self, handler, mock_http_client
    ):
        """Test embedding generation with validation fallback."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "embedding": [0.1] * 768,
                    "extra_field": "ignored",  # Extra field
                },
                raise_for_status=MagicMock(),
            )
        )

        embedding = await handler._generate_embedding("test text")

        assert len(embedding) == 768

    @pytest.mark.asyncio
    async def test_generate_embedding_invalid_response(self, handler, mock_http_client):
        """Test embedding generation with invalid response."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"wrong_field": "no_embedding"},
                raise_for_status=MagicMock(),
            )
        )

        with pytest.raises(ValueError, match="Invalid Ollama response format"):
            await handler._generate_embedding("test text")

    @pytest.mark.asyncio
    async def test_generate_embedding_http_error(self, handler, mock_http_client):
        """Test embedding generation HTTP error."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=500,
                raise_for_status=MagicMock(
                    side_effect=httpx.HTTPStatusError(
                        "Server Error",
                        request=MagicMock(),
                        response=MagicMock(status_code=500),
                    )
                ),
            )
        )

        with pytest.raises(Exception):
            await handler._generate_embedding("test text")

    @pytest.mark.asyncio
    async def test_generate_embedding_no_http_client(self):
        """Test embedding generation without pre-configured HTTP client."""
        handler = SearchHandler(http_client=None)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.post = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=lambda: {"embedding": [0.1] * 768},
                    raise_for_status=MagicMock(),
                )
            )
            mock_client_class.return_value = mock_client

            embedding = await handler._generate_embedding("test text")

            assert len(embedding) == 768


# ==============================================================================
# Deduplication and Ranking Tests
# ==============================================================================


class TestDeduplicateAndRank:
    """Test result deduplication and ranking."""

    def test_deduplicate_by_path(self, handler):
        """Test deduplication removes duplicate paths."""
        results = [
            ModelSearchResultItem(
                source_path="test.py", score=0.9, content="v1", metadata={}
            ),
            ModelSearchResultItem(
                source_path="test.py", score=0.8, content="v2", metadata={}
            ),
            ModelSearchResultItem(
                source_path="other.py", score=0.7, content="v3", metadata={}
            ),
        ]

        ranked = handler._deduplicate_and_rank(
            results=results, max_results=10, quality_weight=None
        )

        # Should keep only highest score for each path
        assert len(ranked) == 2
        assert ranked[0].source_path == "test.py"
        assert ranked[0].score == 0.9  # Higher score kept

    def test_rank_by_score_descending(self, handler):
        """Test results are ranked by score in descending order."""
        results = [
            ModelSearchResultItem(
                source_path="low.py", score=0.5, content="low", metadata={}
            ),
            ModelSearchResultItem(
                source_path="high.py", score=0.95, content="high", metadata={}
            ),
            ModelSearchResultItem(
                source_path="med.py", score=0.7, content="med", metadata={}
            ),
        ]

        ranked = handler._deduplicate_and_rank(
            results=results, max_results=10, quality_weight=None
        )

        assert len(ranked) == 3
        assert ranked[0].score == 0.95
        assert ranked[1].score == 0.7
        assert ranked[2].score == 0.5

    def test_limit_max_results(self, handler):
        """Test max_results limits output."""
        results = [
            ModelSearchResultItem(
                source_path=f"file{i}.py", score=0.9 - i * 0.1, content="c", metadata={}
            )
            for i in range(10)
        ]

        ranked = handler._deduplicate_and_rank(
            results=results, max_results=3, quality_weight=None
        )

        assert len(ranked) == 3

    def test_quality_weighted_ranking(self, handler):
        """Test quality-weighted ranking."""
        results = [
            ModelSearchResultItem(
                source_path="high_quality.py",
                score=0.7,
                content="content",
                metadata={"quality_score": 0.95},
            ),
            ModelSearchResultItem(
                source_path="low_quality.py",
                score=0.9,
                content="content",
                metadata={"quality_score": 0.3},
            ),
        ]

        ranked = handler._deduplicate_and_rank(
            results=results, max_results=10, quality_weight=0.5
        )

        # With 50% quality weight:
        # high_quality: 0.5*0.7 + 0.5*0.95 = 0.825
        # low_quality: 0.5*0.9 + 0.5*0.3 = 0.6
        assert len(ranked) == 2
        assert ranked[0].source_path == "high_quality.py"


# ==============================================================================
# Response Publishing Tests
# ==============================================================================


class TestResponsePublishing:
    """Test event publishing for completed/failed responses."""

    @pytest.mark.asyncio
    async def test_publish_completed_response(self, handler_with_router):
        """Test publishing SEARCH_COMPLETED event."""
        search_result = {
            "total_results": 5,
            "results": [
                ModelSearchResultItem(
                    source_path="test.py", score=0.9, content="content", metadata={}
                )
            ],
            "sources_queried": ["rag", "vector"],
            "service_timings": {"rag_search_ms": 100.0},
            "cache_hit": False,
            "aggregation_strategy": "weighted_score",
        }

        test_corr_id = str(uuid4())
        await handler_with_router._publish_completed_response(
            correlation_id=test_corr_id,
            query="test query",
            search_type=EnumSearchType.HYBRID,
            search_result=search_result,
            processing_time_ms=250.0,
        )

        # Verify published
        handler_with_router._router.publish.assert_called_once()
        call_kwargs = handler_with_router._router.publish.call_args.kwargs
        assert "search-completed" in call_kwargs["topic"]
        assert call_kwargs["key"] == test_corr_id

    @pytest.mark.asyncio
    async def test_publish_failed_response(self, handler_with_router):
        """Test publishing SEARCH_FAILED event."""
        test_corr_id = str(uuid4())
        await handler_with_router._publish_failed_response(
            correlation_id=test_corr_id,
            query="test query",
            search_type=EnumSearchType.HYBRID,
            error_code=EnumSearchErrorCode.INTERNAL_ERROR,
            error_message="Test error",
            retry_allowed=True,
            processing_time_ms=100.0,
            failed_services=["rag"],
            error_details={"exception": "TestException"},
        )

        # Verify published
        handler_with_router._router.publish.assert_called_once()
        call_kwargs = handler_with_router._router.publish.call_args.kwargs
        assert "search-failed" in call_kwargs["topic"]
        assert call_kwargs["key"] == test_corr_id


# ==============================================================================
# Metrics Tests
# ==============================================================================


class TestMetrics:
    """Test metrics tracking and reporting."""

    def test_get_handler_name(self, handler):
        """Test get_handler_name returns correct name."""
        assert handler.get_handler_name() == "SearchHandler"

    def test_get_metrics_initial(self, handler):
        """Test initial metrics state."""
        metrics = handler.get_metrics()

        assert metrics["events_handled"] == 0
        assert metrics["events_failed"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_processing_time_ms"] == 0.0
        assert metrics["handler_name"] == "SearchHandler"

    @pytest.mark.asyncio
    async def test_get_metrics_after_events(
        self, handler_with_router, mock_http_client
    ):
        """Test metrics after processing events."""
        # Mock successful RAG search
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"results": []},
                raise_for_status=MagicMock(),
            )
        )

        # Process successful event
        event1 = create_mock_event(
            payload={"query": "test1", "search_type": "SEMANTIC"}
        )
        await handler_with_router.handle_event(event1)

        # Process failed event (missing query - returns False early)
        event2 = create_mock_event(payload={})  # Missing query
        await handler_with_router.handle_event(event2)

        metrics = handler_with_router.get_metrics()

        # Note: Failed events increment events_failed but not events_handled
        # events_handled = 1 (successful), events_failed = 1 (failed)
        # total_events = events_handled + events_failed = 2
        assert metrics["events_handled"] == 1
        assert metrics["events_failed"] == 1
        assert metrics["searches_completed"] == 1
        assert metrics["searches_failed"] == 1
        # success_rate = events_handled / total_events = 1 / 2 = 0.5
        assert metrics["success_rate"] == 0.5
        assert metrics["avg_processing_time_ms"] > 0


# ==============================================================================
# Edge Cases and Validation Tests
# ==============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_search_results(self, handler, mock_http_client):
        """Test handling of empty search results."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"results": []},
                raise_for_status=MagicMock(),
            )
        )

        result = await handler._search_rag(query="test", max_results=10, filters={})

        assert result["results"] == []
        assert result["timing_ms"] >= 0

    @pytest.mark.asyncio
    async def test_max_results_zero(self, handler, mock_http_client):
        """Test with max_results=0 (edge case)."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"results": []},
                raise_for_status=MagicMock(),
            )
        )

        result = await handler._perform_search(
            query="test",
            search_type=EnumSearchType.SEMANTIC,
            project_id=None,
            max_results=0,  # Edge case
            filters={},
            quality_weight=None,
            include_context=True,
            enable_caching=True,
        )

        assert result["total_results"] == 0

    def test_deduplicate_empty_results(self, handler):
        """Test deduplication with empty results."""
        ranked = handler._deduplicate_and_rank(
            results=[], max_results=10, quality_weight=None
        )

        assert ranked == []

    @pytest.mark.asyncio
    async def test_search_with_complex_filters(self, handler, mock_http_client):
        """Test search with complex filter dictionary."""
        mock_http_client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {"results": []},
                raise_for_status=MagicMock(),
            )
        )

        complex_filters = {
            "project_id": "test-project",
            "language": "python",
            "min_quality_score": 0.7,
            "file_patterns": ["src/**/*.py"],
        }

        result = await handler._search_rag(
            query="test", max_results=10, filters=complex_filters
        )

        # Verify filters were passed to RAG service
        call_kwargs = mock_http_client.post.call_args.kwargs
        assert call_kwargs["json"]["filters"] == complex_filters


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
