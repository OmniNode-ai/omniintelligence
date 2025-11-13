"""
Unit tests for search service query processing.

Tests the search query processing functionality including:
- Hybrid search orchestration
- Query parsing and optimization
- Multi-source search coordination
- Result ranking and merging
- Search analytics and caching
- Error handling and fallback strategies
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from engines.graph_search import GraphSearchEngine
from engines.search_cache import SearchCache
from engines.vector_search import VectorSearchEngine
from models.search_models import (
    EntityType,
    RelationshipSearchRequest,
    RelationshipSearchResponse,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from orchestration.hybrid_search import HybridSearchOrchestrator


class TestHybridSearchOrchestrator:
    """Test cases for hybrid search orchestration functionality."""

    @pytest.fixture
    def mock_vector_engine(self):
        """Mock vector search engine for testing."""
        engine = AsyncMock(spec=VectorSearchEngine)
        engine.semantic_search.return_value = AsyncMock()
        engine.quality_weighted_search.return_value = AsyncMock()
        return engine

    @pytest.fixture
    def mock_graph_engine(self):
        """Mock graph search engine for testing."""
        engine = AsyncMock(spec=GraphSearchEngine)
        engine.relationship_search.return_value = AsyncMock()
        engine.structural_search.return_value = AsyncMock()
        return engine

    @pytest.fixture
    def mock_search_cache(self):
        """Mock search cache for testing."""
        cache = AsyncMock(spec=SearchCache)
        cache.get.return_value = None  # Cache miss by default
        cache.set.return_value = True
        return cache

    @pytest.fixture
    def hybrid_orchestrator(
        self, mock_vector_engine, mock_graph_engine, mock_search_cache
    ):
        """Create HybridSearchOrchestrator instance for testing."""
        orchestrator = HybridSearchOrchestrator(
            supabase_url="http://test-supabase",
            supabase_key="test-key",
            memgraph_uri="bolt://test-memgraph:7687",
            ollama_base_url="http://test-ollama:11434",
        )
        orchestrator.vector_engine = mock_vector_engine
        orchestrator.graph_engine = mock_graph_engine
        orchestrator.search_cache = mock_search_cache
        orchestrator._initialized = True
        return orchestrator

    @pytest.fixture
    def sample_search_request(self):
        """Sample search request for testing."""
        return SearchRequest(
            query="user authentication and authorization patterns",
            mode=SearchMode.HYBRID,
            limit=10,
            entity_types=[EntityType.DOCUMENT, EntityType.API_ENDPOINT],
            include_content=True,
            quality_weight=0.3,
            score_threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_hybrid_search_orchestration(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test hybrid search orchestration combining multiple engines."""
        # Mock vector search results
        vector_results = [
            SearchResult(
                id="vector-1",
                title="Authentication Guide",
                content="Complete guide to user authentication",
                score=0.92,
                entity_type=EntityType.DOCUMENT,
                source="vector_search",
            ),
            SearchResult(
                id="vector-2",
                title="/api/login",
                content="User login endpoint",
                score=0.85,
                entity_type=EntityType.API_ENDPOINT,
                source="vector_search",
            ),
        ]

        # Mock graph search results
        graph_results = [
            SearchResult(
                id="graph-1",
                title="OAuth Implementation",
                content="OAuth authentication implementation",
                score=0.88,
                entity_type=EntityType.CONCEPT,
                source="graph_search",
            )
        ]

        # Setup mock returns
        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = (
            vector_results
        )
        hybrid_orchestrator.graph_engine.structural_search.return_value.results = (
            graph_results
        )

        # Execute hybrid search
        response = await hybrid_orchestrator.hybrid_search(sample_search_request)

        assert isinstance(response, SearchResponse)
        assert len(response.results) > 0
        assert response.total_results >= len(vector_results) + len(graph_results)

        # Verify both engines were called
        hybrid_orchestrator.vector_engine.semantic_search.assert_called_once()
        hybrid_orchestrator.graph_engine.structural_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_optimization(self, hybrid_orchestrator):
        """Test query optimization for better search performance."""
        original_query = "how to implement user authentication and authorization using JWT tokens and OAuth"

        optimized_query = await hybrid_orchestrator.optimize_query(original_query)

        assert isinstance(optimized_query, str)
        assert len(optimized_query) <= len(original_query)
        # Should contain key terms
        assert any(
            term in optimized_query.lower()
            for term in ["authentication", "authorization", "jwt", "oauth"]
        )

    @pytest.mark.asyncio
    async def test_result_ranking_and_merging(self, hybrid_orchestrator):
        """Test result ranking and merging from multiple sources."""
        # Mock results from different sources with different scores
        vector_results = [
            {"id": "v1", "score": 0.9, "source": "vector", "relevance": 0.85},
            {"id": "v2", "score": 0.8, "source": "vector", "relevance": 0.75},
        ]

        graph_results = [
            {"id": "g1", "score": 0.85, "source": "graph", "relevance": 0.9},
            {"id": "g2", "score": 0.75, "source": "graph", "relevance": 0.8},
        ]

        # Test result merging with intelligent ranking
        merged_results = hybrid_orchestrator.merge_and_rank_results(
            vector_results=vector_results,
            graph_results=graph_results,
            ranking_strategy="weighted_score",
        )

        assert len(merged_results) == 4
        # Verify results are ranked by composite score
        for i in range(len(merged_results) - 1):
            assert (
                merged_results[i]["composite_score"]
                >= merged_results[i + 1]["composite_score"]
            )

    @pytest.mark.asyncio
    async def test_semantic_search_mode(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test pure semantic search mode."""
        sample_search_request.mode = SearchMode.SEMANTIC

        # Mock vector search results
        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = [
            SearchResult(
                id="semantic-1",
                title="Semantic Result",
                score=0.9,
                entity_type=EntityType.DOCUMENT,
            )
        ]

        response = await hybrid_orchestrator.semantic_search(sample_search_request)

        assert response.search_mode == SearchMode.SEMANTIC
        assert len(response.results) > 0

        # Verify only vector engine was used
        hybrid_orchestrator.vector_engine.semantic_search.assert_called_once()
        hybrid_orchestrator.graph_engine.structural_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_structural_search_mode(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test pure structural search mode."""
        sample_search_request.mode = SearchMode.STRUCTURAL

        # Mock graph search results
        hybrid_orchestrator.graph_engine.structural_search.return_value.results = [
            SearchResult(
                id="structural-1",
                title="Structural Result",
                score=0.85,
                entity_type=EntityType.CONCEPT,
            )
        ]

        response = await hybrid_orchestrator.structural_search(sample_search_request)

        assert response.search_mode == SearchMode.STRUCTURAL
        assert len(response.results) > 0

        # Verify only graph engine was used
        hybrid_orchestrator.graph_engine.structural_search.assert_called_once()
        hybrid_orchestrator.vector_engine.semantic_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test search with entity type and metadata filters."""
        sample_search_request.filters = {
            "document_type": "tutorial",
            "language": "python",
            "quality_score": {"gte": 0.8},
        }

        # Mock filtered search results
        filtered_results = [
            SearchResult(
                id="filtered-1",
                title="Python Authentication Tutorial",
                score=0.9,
                entity_type=EntityType.DOCUMENT,
                metadata={
                    "document_type": "tutorial",
                    "language": "python",
                    "quality_score": 0.85,
                },
            )
        ]

        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = (
            filtered_results
        )

        response = await hybrid_orchestrator.search_with_filters(sample_search_request)

        # Verify filters were applied
        for result in response.results:
            if hasattr(result, "metadata") and result.metadata:
                if "document_type" in result.metadata:
                    assert result.metadata["document_type"] == "tutorial"
                if "language" in result.metadata:
                    assert result.metadata["language"] == "python"

    @pytest.mark.asyncio
    async def test_search_caching(self, hybrid_orchestrator, sample_search_request):
        """Test search result caching mechanism."""
        # First search (cache miss)
        cached_results = None
        hybrid_orchestrator.search_cache.get.return_value = cached_results

        mock_results = [SearchResult(id="cached-1", title="Cached Result", score=0.9)]
        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = (
            mock_results
        )

        response1 = await hybrid_orchestrator.cached_search(sample_search_request)

        # Verify cache was checked and set
        hybrid_orchestrator.search_cache.get.assert_called_once()
        hybrid_orchestrator.search_cache.set.assert_called_once()

        # Second search (cache hit)
        hybrid_orchestrator.search_cache.get.return_value = mock_results
        hybrid_orchestrator.search_cache.reset_mock()

        response2 = await hybrid_orchestrator.cached_search(sample_search_request)

        # Verify cache was used
        hybrid_orchestrator.search_cache.get.assert_called_once()
        assert response1.results == response2.results

    @pytest.mark.asyncio
    async def test_search_analytics_tracking(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test search analytics and performance tracking."""
        time.time()

        # Mock search execution
        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = [
            SearchResult(id="analytics-1", title="Analytics Result", score=0.9)
        ]

        response = await hybrid_orchestrator.search_with_analytics(
            sample_search_request
        )

        # Verify analytics data
        assert hasattr(response, "analytics")
        assert response.analytics.query == sample_search_request.query
        assert response.analytics.search_mode == sample_search_request.mode
        assert response.analytics.total_results > 0
        assert response.analytics.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_error_handling_vector_engine_failure(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test error handling when vector engine fails."""
        # Mock vector engine failure
        hybrid_orchestrator.vector_engine.semantic_search.side_effect = Exception(
            "Vector engine failed"
        )

        # Mock graph engine success
        hybrid_orchestrator.graph_engine.structural_search.return_value.results = [
            SearchResult(id="fallback-1", title="Fallback Result", score=0.8)
        ]

        # Should fall back to graph search
        response = await hybrid_orchestrator.search_with_fallback(sample_search_request)

        assert len(response.results) > 0
        assert response.fallback_used is True
        assert "vector_engine_error" in response.error_details

    @pytest.mark.asyncio
    async def test_error_handling_both_engines_failure(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test error handling when both engines fail."""
        # Mock both engines failing
        hybrid_orchestrator.vector_engine.semantic_search.side_effect = Exception(
            "Vector engine failed"
        )
        hybrid_orchestrator.graph_engine.structural_search.side_effect = Exception(
            "Graph engine failed"
        )

        with pytest.raises(Exception) as exc_info:
            await hybrid_orchestrator.search_with_fallback(sample_search_request)

        assert "All search engines failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_concurrent_search_requests(self, hybrid_orchestrator):
        """Test handling of concurrent search requests."""
        requests = [
            SearchRequest(query=f"query {i}", mode=SearchMode.HYBRID, limit=5)
            for i in range(5)
        ]

        # Mock search results
        for i, request in enumerate(requests):
            hybrid_orchestrator.vector_engine.semantic_search.return_value.results = [
                SearchResult(id=f"concurrent-{i}", title=f"Result {i}", score=0.8)
            ]

        # Execute concurrent searches
        tasks = [hybrid_orchestrator.hybrid_search(request) for request in requests]

        responses = await asyncio.gather(*tasks)

        # Verify all searches completed
        assert len(responses) == 5
        for response in responses:
            assert isinstance(response, SearchResponse)
            assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_search_result_deduplication(self, hybrid_orchestrator):
        """Test deduplication of search results from multiple sources."""
        # Mock overlapping results from different sources
        vector_results = [
            {"id": "duplicate-1", "score": 0.9, "source": "vector"},
            {"id": "unique-vector", "score": 0.8, "source": "vector"},
        ]

        graph_results = [
            {
                "id": "duplicate-1",
                "score": 0.85,
                "source": "graph",
            },  # Same ID as vector result
            {"id": "unique-graph", "score": 0.75, "source": "graph"},
        ]

        deduplicated_results = hybrid_orchestrator.deduplicate_results(
            vector_results, graph_results
        )

        # Should have 3 unique results (duplicate-1, unique-vector, unique-graph)
        assert len(deduplicated_results) == 3

        # Duplicate should have higher score from vector source
        duplicate_result = next(
            r for r in deduplicated_results if r["id"] == "duplicate-1"
        )
        assert duplicate_result["score"] == 0.9

    @pytest.mark.asyncio
    async def test_search_performance_optimization(
        self, hybrid_orchestrator, sample_search_request
    ):
        """Test search performance optimization techniques."""
        # Test query optimization
        optimized_request = await hybrid_orchestrator.optimize_search_request(
            sample_search_request
        )

        # Should have optimized parameters
        assert optimized_request.limit <= sample_search_request.limit
        assert len(optimized_request.query) <= len(sample_search_request.query)

        # Test parallel execution
        start_time = time.time()

        # Mock both engines
        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = [
            SearchResult(id="parallel-v", score=0.9)
        ]
        hybrid_orchestrator.graph_engine.structural_search.return_value.results = [
            SearchResult(id="parallel-g", score=0.8)
        ]

        response = await hybrid_orchestrator.parallel_search(optimized_request)

        execution_time = time.time() - start_time

        # Should execute faster than sequential search
        assert execution_time < 1.0  # Should be fast with mocked engines
        assert len(response.results) >= 2


class TestRelationshipSearch:
    """Test cases for relationship search functionality."""

    @pytest.fixture
    def relationship_search_request(self):
        """Sample relationship search request."""
        return RelationshipSearchRequest(
            entity_id="auth-concept",
            relationship_types=["IMPLEMENTS", "USES", "RELATES_TO"],
            max_depth=3,
            include_metadata=True,
        )

    @pytest.mark.asyncio
    async def test_relationship_discovery(
        self, hybrid_orchestrator, relationship_search_request
    ):
        """Test relationship discovery from graph database."""
        # Mock relationship results
        mock_relationships = [
            {
                "from_entity": "auth-concept",
                "to_entity": "login-endpoint",
                "relationship_type": "IMPLEMENTS",
                "properties": {"confidence": 0.9},
            },
            {
                "from_entity": "auth-concept",
                "to_entity": "jwt-token",
                "relationship_type": "USES",
                "properties": {"confidence": 0.85},
            },
        ]

        hybrid_orchestrator.graph_engine.find_relationships.return_value = (
            mock_relationships
        )

        response = await hybrid_orchestrator.relationship_search(
            relationship_search_request
        )

        assert isinstance(response, RelationshipSearchResponse)
        assert len(response.relationships) == 2
        assert response.source_entity_id == "auth-concept"

    @pytest.mark.asyncio
    async def test_multi_hop_relationship_search(
        self, hybrid_orchestrator, relationship_search_request
    ):
        """Test multi-hop relationship search with depth limits."""
        relationship_search_request.max_depth = 2

        # Mock multi-hop relationships
        mock_paths = [
            {
                "path": ["auth-concept", "login-endpoint", "user-session"],
                "path_length": 2,
                "total_confidence": 0.8,
            }
        ]

        hybrid_orchestrator.graph_engine.find_paths.return_value = mock_paths

        response = await hybrid_orchestrator.multi_hop_search(
            relationship_search_request
        )

        assert len(response.paths) == 1
        assert response.paths[0]["path_length"] <= relationship_search_request.max_depth


class TestSearchAnalytics:
    """Test cases for search analytics functionality."""

    @pytest.mark.asyncio
    async def test_search_performance_metrics(self, hybrid_orchestrator):
        """Test collection of search performance metrics."""
        # Execute multiple searches to generate metrics
        search_requests = [
            SearchRequest(query="test query 1", mode=SearchMode.HYBRID),
            SearchRequest(query="test query 2", mode=SearchMode.SEMANTIC),
            SearchRequest(query="test query 3", mode=SearchMode.STRUCTURAL),
        ]

        for request in search_requests:
            await hybrid_orchestrator.search_with_analytics(request)

        # Get analytics summary
        analytics = await hybrid_orchestrator.get_search_analytics()

        assert analytics.total_searches >= 3
        assert analytics.average_response_time > 0
        assert len(analytics.search_modes_used) > 0

    @pytest.mark.asyncio
    async def test_query_pattern_analysis(self, hybrid_orchestrator):
        """Test analysis of query patterns and optimization opportunities."""
        # Simulate repeated similar queries
        similar_queries = [
            "user authentication",
            "authentication for users",
            "how to authenticate users",
            "user auth implementation",
        ]

        for query in similar_queries:
            request = SearchRequest(query=query, mode=SearchMode.HYBRID)
            await hybrid_orchestrator.search_with_analytics(request)

        # Analyze query patterns
        patterns = await hybrid_orchestrator.analyze_query_patterns()

        assert "authentication" in patterns.frequent_terms
        assert patterns.similar_query_groups > 0

    @pytest.mark.asyncio
    async def test_search_result_quality_metrics(self, hybrid_orchestrator):
        """Test collection of search result quality metrics."""
        # Mock search with quality metrics
        mock_results = [
            SearchResult(
                id="quality-1",
                title="High Quality Result",
                score=0.95,
                quality_indicators={"relevance": 0.9, "freshness": 0.85},
            ),
            SearchResult(
                id="quality-2",
                title="Medium Quality Result",
                score=0.75,
                quality_indicators={"relevance": 0.7, "freshness": 0.8},
            ),
        ]

        request = SearchRequest(query="quality test", mode=SearchMode.HYBRID)
        hybrid_orchestrator.vector_engine.semantic_search.return_value.results = (
            mock_results
        )

        response = await hybrid_orchestrator.search_with_quality_metrics(request)

        assert response.quality_metrics.average_relevance > 0
        assert response.quality_metrics.average_freshness > 0
        assert response.quality_metrics.high_quality_results_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
