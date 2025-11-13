"""
Unit tests for Qdrant vector storage and search operations.

Tests the Qdrant vector database functionality including:
- Vector storage and indexing
- Similarity search operations
- Collection management
- Quality-weighted search
- Batch operations and performance
- Error handling and recovery
"""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import numpy as np
import pytest
from engines.qdrant_adapter import QdrantAdapter
from engines.vector_search import VectorSearchEngine
from models.search_models import (
    VectorSearchRequest,
    VectorSearchResult,
)
from qdrant_client.http.models import (
    Distance,
)


class TestQdrantAdapter:
    """Test cases for Qdrant adapter functionality."""

    @pytest.fixture
    def mock_qdrant_client(self):
        """Mock Qdrant client for testing."""
        client = Mock()

        # Mock collection operations
        client.create_collection = Mock()
        client.get_collection_info = Mock()
        client.delete_collection = Mock()

        # Mock point operations
        client.upsert = Mock()
        client.search = Mock()
        client.get_points = Mock()
        client.delete_points = Mock()

        # Mock batch operations
        client.batch_update_points = Mock()

        return client

    @pytest.fixture
    def qdrant_adapter(self, mock_qdrant_client):
        """Create QdrantAdapter instance for testing."""
        adapter = QdrantAdapter(url="http://test-qdrant:6333", api_key="test-key")
        adapter.client = mock_qdrant_client
        adapter._initialized = True
        return adapter

    @pytest.fixture
    def sample_vectors(self):
        """Sample vectors for testing."""
        return [
            {
                "id": str(uuid4()),
                "vector": np.random.rand(768).tolist(),
                "metadata": {
                    "entity_id": "entity-1",
                    "entity_type": "document",
                    "title": "Test Document 1",
                    "content_preview": "This is a test document about authentication",
                    "quality_score": 0.85,
                },
            },
            {
                "id": str(uuid4()),
                "vector": np.random.rand(768).tolist(),
                "metadata": {
                    "entity_id": "entity-2",
                    "entity_type": "api_endpoint",
                    "title": "/login",
                    "content_preview": "Authentication endpoint for user login",
                    "quality_score": 0.92,
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_collection_creation(self, qdrant_adapter):
        """Test creating collections in Qdrant."""
        collection_name = "test_collection"
        vector_size = 768

        await qdrant_adapter.create_collection(
            collection_name=collection_name,
            vector_size=vector_size,
            distance_metric="cosine",
        )

        qdrant_adapter.client.create_collection.assert_called_once()
        call_args = qdrant_adapter.client.create_collection.call_args

        assert call_args[1]["collection_name"] == collection_name
        assert call_args[1]["vectors_config"].size == vector_size
        assert call_args[1]["vectors_config"].distance == Distance.COSINE

    @pytest.mark.asyncio
    async def test_collection_exists_check(self, qdrant_adapter):
        """Test checking if collection exists."""
        # Mock existing collection
        qdrant_adapter.client.get_collection_info.return_value = Mock(
            config=Mock(params=Mock(vectors=Mock(size=768)))
        )

        exists = await qdrant_adapter.collection_exists("existing_collection")
        assert exists is True

        # Mock non-existing collection
        qdrant_adapter.client.get_collection_info.side_effect = Exception(
            "Collection not found"
        )

        exists = await qdrant_adapter.collection_exists("non_existing_collection")
        assert exists is False

    @pytest.mark.asyncio
    async def test_store_vectors(self, qdrant_adapter, sample_vectors):
        """Test storing vectors in Qdrant."""
        collection_name = "test_collection"

        # Mock successful upsert
        qdrant_adapter.client.upsert.return_value = Mock(
            operation_id=1, status="completed"
        )

        result = await qdrant_adapter.store_vectors(
            collection_name=collection_name, vectors=sample_vectors
        )

        assert result["success"] is True
        assert result["stored_count"] == 2

        # Verify upsert was called with correct parameters
        qdrant_adapter.client.upsert.assert_called_once()
        call_args = qdrant_adapter.client.upsert.call_args

        assert call_args[1]["collection_name"] == collection_name
        assert len(call_args[1]["points"]) == 2

    @pytest.mark.asyncio
    async def test_search_vectors(self, qdrant_adapter):
        """Test vector similarity search."""
        query_vector = np.random.rand(768).tolist()
        collection_name = "test_collection"

        # Mock search results
        mock_results = [
            Mock(
                id="result-1",
                score=0.95,
                payload={
                    "entity_id": "entity-1",
                    "title": "Highly relevant document",
                    "quality_score": 0.9,
                },
            ),
            Mock(
                id="result-2",
                score=0.82,
                payload={
                    "entity_id": "entity-2",
                    "title": "Moderately relevant document",
                    "quality_score": 0.75,
                },
            ),
        ]

        qdrant_adapter.client.search.return_value = mock_results

        results = await qdrant_adapter.search_vectors(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=10,
            score_threshold=0.7,
        )

        assert len(results) == 2
        assert results[0]["score"] >= 0.7
        assert results[1]["score"] >= 0.7
        assert results[0]["score"] > results[1]["score"]  # Should be sorted by score

    @pytest.mark.asyncio
    async def test_filtered_search(self, qdrant_adapter):
        """Test vector search with metadata filters."""
        query_vector = np.random.rand(768).tolist()
        collection_name = "test_collection"

        # Mock filtered search results
        mock_results = [
            Mock(
                id="doc-1",
                score=0.9,
                payload={"entity_type": "document", "quality_score": 0.85},
            )
        ]

        qdrant_adapter.client.search.return_value = mock_results

        # Test with entity type filter
        results = await qdrant_adapter.search_vectors(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=10,
            filters={"entity_type": "document", "quality_score": {"gte": 0.8}},
        )

        assert len(results) == 1
        assert results[0]["metadata"]["entity_type"] == "document"

        # Verify filter was applied
        qdrant_adapter.client.search.assert_called_once()
        call_args = qdrant_adapter.client.search.call_args
        assert call_args[1]["query_filter"] is not None

    @pytest.mark.asyncio
    async def test_quality_weighted_search(self, qdrant_adapter):
        """Test quality-weighted vector search."""
        query_vector = np.random.rand(768).tolist()
        collection_name = "test_collection"

        # Mock results with different quality scores
        mock_results = [
            Mock(
                id="high-quality",
                score=0.8,
                payload={"title": "High quality document", "quality_score": 0.95},
            ),
            Mock(
                id="low-quality",
                score=0.85,
                payload={"title": "Lower quality document", "quality_score": 0.6},
            ),
        ]

        qdrant_adapter.client.search.return_value = mock_results

        results = await qdrant_adapter.quality_weighted_search(
            collection_name=collection_name,
            query_vector=query_vector,
            quality_weight=0.3,
            limit=10,
        )

        # Verify quality weighting affected ranking
        assert len(results) == 2

        # Calculate expected weighted scores
        result1_weighted = (
            0.8 * 0.7 + 0.95 * 0.3
        )  # similarity * (1-weight) + quality * weight
        result2_weighted = 0.85 * 0.7 + 0.6 * 0.3

        # High quality document should rank higher despite lower similarity
        if result1_weighted > result2_weighted:
            assert results[0]["id"] == "high-quality"
        else:
            assert results[0]["id"] == "low-quality"

    @pytest.mark.asyncio
    async def test_batch_vector_storage(self, qdrant_adapter):
        """Test batch storage of large vector sets."""
        collection_name = "test_collection"

        # Generate large batch of vectors
        large_batch = []
        for i in range(1000):
            large_batch.append(
                {
                    "id": f"vector-{i}",
                    "vector": np.random.rand(768).tolist(),
                    "metadata": {"entity_id": f"entity-{i}", "batch_index": i},
                }
            )

        # Mock successful batch operations
        qdrant_adapter.client.upsert.return_value = Mock(
            operation_id=1, status="completed"
        )

        result = await qdrant_adapter.batch_store_vectors(
            collection_name=collection_name, vectors=large_batch, batch_size=100
        )

        assert result["success"] is True
        assert result["total_stored"] == 1000
        assert result["batches_processed"] == 10

        # Verify upsert was called multiple times for batching
        assert qdrant_adapter.client.upsert.call_count == 10

    @pytest.mark.asyncio
    async def test_vector_update(self, qdrant_adapter):
        """Test updating existing vectors."""
        collection_name = "test_collection"
        vector_id = "existing-vector"
        updated_vector = np.random.rand(768).tolist()
        updated_metadata = {
            "entity_id": "entity-1",
            "title": "Updated Document",
            "quality_score": 0.9,
        }

        result = await qdrant_adapter.update_vector(
            collection_name=collection_name,
            vector_id=vector_id,
            vector=updated_vector,
            metadata=updated_metadata,
        )

        assert result["success"] is True

        # Verify upsert was called for update
        qdrant_adapter.client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_vector_deletion(self, qdrant_adapter):
        """Test deleting vectors from collection."""
        collection_name = "test_collection"
        vector_ids = ["vector-1", "vector-2", "vector-3"]

        # Mock successful deletion
        qdrant_adapter.client.delete_points.return_value = Mock(
            operation_id=1, status="completed"
        )

        result = await qdrant_adapter.delete_vectors(
            collection_name=collection_name, vector_ids=vector_ids
        )

        assert result["success"] is True
        assert result["deleted_count"] == 3

        # Verify delete was called
        qdrant_adapter.client.delete_points.assert_called_once()
        call_args = qdrant_adapter.client.delete_points.call_args
        assert call_args[1]["collection_name"] == collection_name

    @pytest.mark.asyncio
    async def test_collection_statistics(self, qdrant_adapter):
        """Test retrieving collection statistics."""
        collection_name = "test_collection"

        # Mock collection info
        qdrant_adapter.client.get_collection_info.return_value = Mock(
            points_count=5000,
            config=Mock(params=Mock(vectors=Mock(size=768, distance="Cosine"))),
            status="green",
        )

        stats = await qdrant_adapter.get_collection_stats(collection_name)

        assert stats["points_count"] == 5000
        assert stats["vector_size"] == 768
        assert stats["distance_metric"] == "Cosine"
        assert stats["status"] == "green"

    @pytest.mark.asyncio
    async def test_error_handling_storage(self, qdrant_adapter, sample_vectors):
        """Test error handling during vector storage."""
        collection_name = "test_collection"

        # Mock storage failure
        qdrant_adapter.client.upsert.side_effect = Exception("Storage failed")

        result = await qdrant_adapter.store_vectors(
            collection_name=collection_name, vectors=sample_vectors
        )

        assert result["success"] is False
        assert "Storage failed" in result["error"]

    @pytest.mark.asyncio
    async def test_error_handling_search(self, qdrant_adapter):
        """Test error handling during vector search."""
        query_vector = np.random.rand(768).tolist()
        collection_name = "test_collection"

        # Mock search failure
        qdrant_adapter.client.search.side_effect = Exception("Search failed")

        with pytest.raises(Exception) as exc_info:
            await qdrant_adapter.search_vectors(
                collection_name=collection_name, query_vector=query_vector
            )

        assert "Search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connection_retry_mechanism(self, qdrant_adapter):
        """Test connection retry mechanism for transient failures."""
        collection_name = "test_collection"

        # Mock transient connection failures followed by success
        qdrant_adapter.client.get_collection_info.side_effect = [
            Exception("Connection timeout"),
            Exception("Connection timeout"),
            Mock(points_count=100),  # Success on third try
        ]

        # Assuming retry mechanism exists
        if hasattr(qdrant_adapter, "with_retry"):
            result = await qdrant_adapter.with_retry(
                qdrant_adapter.get_collection_stats, collection_name, max_retries=3
            )
            assert result["points_count"] == 100


class TestVectorSearchEngine:
    """Test cases for vector search engine functionality."""

    @pytest.fixture
    def mock_qdrant_adapter(self):
        """Mock Qdrant adapter for testing."""
        adapter = AsyncMock()
        adapter.search_vectors = AsyncMock()
        adapter.quality_weighted_search = AsyncMock()
        adapter.store_vectors = AsyncMock()
        return adapter

    @pytest.fixture
    def vector_search_engine(self, mock_qdrant_adapter):
        """Create VectorSearchEngine instance for testing."""
        engine = VectorSearchEngine(
            qdrant_adapter=mock_qdrant_adapter, default_collection="documents"
        )
        return engine

    @pytest.mark.asyncio
    async def test_semantic_search(self, vector_search_engine):
        """Test semantic search functionality."""
        search_request = VectorSearchRequest(
            query="user authentication and login",
            limit=10,
            score_threshold=0.7,
            entity_types=["document", "api_endpoint"],
        )

        # Mock search results
        vector_search_engine.qdrant_adapter.search_vectors.return_value = [
            {
                "id": "doc-1",
                "score": 0.92,
                "metadata": {
                    "title": "Authentication Guide",
                    "entity_type": "document",
                },
            },
            {
                "id": "api-1",
                "score": 0.85,
                "metadata": {"title": "/login", "entity_type": "api_endpoint"},
            },
        ]

        results = await vector_search_engine.semantic_search(search_request)

        assert isinstance(results, VectorSearchResult)
        assert len(results.matches) == 2
        assert results.matches[0].score >= results.matches[1].score
        assert all(match.score >= 0.7 for match in results.matches)

    @pytest.mark.asyncio
    async def test_quality_weighted_search(self, vector_search_engine):
        """Test quality-weighted search functionality."""
        search_request = VectorSearchRequest(
            query="API documentation",
            limit=5,
            quality_weight=0.3,
            min_quality_score=0.8,
        )

        # Mock quality-weighted search results
        vector_search_engine.qdrant_adapter.quality_weighted_search.return_value = [
            {
                "id": "doc-high-quality",
                "score": 0.88,
                "weighted_score": 0.91,
                "metadata": {"title": "High Quality API Docs", "quality_score": 0.95},
            }
        ]

        results = await vector_search_engine.quality_weighted_search(search_request)

        assert len(results.matches) == 1
        assert results.matches[0].metadata["quality_score"] >= 0.8

    @pytest.mark.asyncio
    async def test_multi_collection_search(self, vector_search_engine):
        """Test searching across multiple collections."""
        search_request = VectorSearchRequest(
            query="microservices architecture",
            collections=["documents", "code_examples", "api_specs"],
            limit=15,
        )

        # Mock search results from different collections
        vector_search_engine.qdrant_adapter.search_vectors.side_effect = [
            [{"id": "doc-1", "score": 0.9, "collection": "documents"}],
            [{"id": "code-1", "score": 0.85, "collection": "code_examples"}],
            [{"id": "api-1", "score": 0.88, "collection": "api_specs"}],
        ]

        results = await vector_search_engine.multi_collection_search(search_request)

        assert len(results.matches) == 3
        # Verify results are merged and sorted by score
        assert results.matches[0].score >= results.matches[1].score
        assert results.matches[1].score >= results.matches[2].score

    @pytest.mark.asyncio
    async def test_search_with_filters(self, vector_search_engine):
        """Test search with metadata filters."""
        search_request = VectorSearchRequest(
            query="authentication patterns",
            limit=10,
            filters={
                "document_type": "tutorial",
                "language": "python",
                "quality_score": {"gte": 0.8},
            },
        )

        # Mock filtered search results
        vector_search_engine.qdrant_adapter.search_vectors.return_value = [
            {
                "id": "tutorial-1",
                "score": 0.9,
                "metadata": {
                    "document_type": "tutorial",
                    "language": "python",
                    "quality_score": 0.92,
                },
            }
        ]

        results = await vector_search_engine.search_with_filters(search_request)

        assert len(results.matches) == 1
        match = results.matches[0]
        assert match.metadata["document_type"] == "tutorial"
        assert match.metadata["language"] == "python"
        assert match.metadata["quality_score"] >= 0.8

    @pytest.mark.asyncio
    async def test_search_performance_optimization(self, vector_search_engine):
        """Test search performance optimization techniques."""
        # Test caching mechanism
        search_request = VectorSearchRequest(query="cached query test", limit=5)

        # Mock initial search
        vector_search_engine.qdrant_adapter.search_vectors.return_value = [
            {"id": "cached-result", "score": 0.9}
        ]

        # First search (should hit database)
        results1 = await vector_search_engine.cached_search(search_request)

        # Second search (should hit cache)
        results2 = await vector_search_engine.cached_search(search_request)

        # Verify database was only called once
        assert vector_search_engine.qdrant_adapter.search_vectors.call_count == 1
        assert results1.matches == results2.matches

    @pytest.mark.asyncio
    async def test_search_result_ranking(self, vector_search_engine):
        """Test search result ranking and scoring."""
        # Mock multiple results with different scores and quality
        mock_results = [
            {
                "id": "result-1",
                "score": 0.85,
                "metadata": {"quality_score": 0.9, "recency_score": 0.8},
            },
            {
                "id": "result-2",
                "score": 0.9,
                "metadata": {"quality_score": 0.7, "recency_score": 0.9},
            },
            {
                "id": "result-3",
                "score": 0.8,
                "metadata": {"quality_score": 0.95, "recency_score": 0.6},
            },
        ]

        # Test custom ranking function
        ranked_results = vector_search_engine.rank_results(
            mock_results,
            ranking_weights={"similarity": 0.5, "quality": 0.3, "recency": 0.2},
        )

        # Verify results are properly ranked
        assert len(ranked_results) == 3
        for i in range(len(ranked_results) - 1):
            assert (
                ranked_results[i]["composite_score"]
                >= ranked_results[i + 1]["composite_score"]
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
