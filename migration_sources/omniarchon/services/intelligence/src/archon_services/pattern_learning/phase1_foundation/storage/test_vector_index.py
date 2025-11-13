"""
Unit Tests for Qdrant Vector Index Effect Node

Tests real Qdrant integration with performance validation.
Target: >85% code coverage, <100ms search performance for 1000+ patterns.

Uses Ollama nomic-embed-text for local embedding generation.
"""

import os
from typing import List
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from .model_contract_vector_index import (
    ModelContractBatchIndexEffect,
    ModelContractVectorDeleteEffect,
    ModelContractVectorIndexEffect,
    ModelContractVectorSearchEffect,
    ModelVectorIndexPoint,
)
from .node_qdrant_vector_index_effect import NodeQdrantVectorIndexEffect

# Test Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.86.200:11434")
TEST_COLLECTION = "test_execution_patterns"


@pytest_asyncio.fixture(scope="module")
# NOTE: correlation_id support enabled for tracing
async def vector_index_node():
    """Create and cleanup vector index node for tests."""
    node = NodeQdrantVectorIndexEffect(
        qdrant_url=QDRANT_URL, ollama_base_url=OLLAMA_BASE_URL
    )

    yield node

    # Cleanup: delete test collection
    try:
        await node.qdrant_client.delete_collection(collection_name=TEST_COLLECTION)
    except Exception:
        pass

    await node.close()


@pytest.fixture
def sample_pattern_points() -> List[ModelVectorIndexPoint]:
    """Generate sample pattern points for testing."""
    return [
        ModelVectorIndexPoint(
            id=uuid4(),
            payload={
                "text": "Database query optimization using indexes for faster retrieval",
                "pattern_type": "performance_optimization",
                "complexity": "medium",
            },
        ),
        ModelVectorIndexPoint(
            id=uuid4(),
            payload={
                "text": "Implement caching layer with Redis for reduced database load",
                "pattern_type": "performance_optimization",
                "complexity": "high",
            },
        ),
        ModelVectorIndexPoint(
            id=uuid4(),
            payload={
                "text": "API rate limiting implementation using token bucket algorithm",
                "pattern_type": "api_design",
                "complexity": "medium",
            },
        ),
        ModelVectorIndexPoint(
            id=uuid4(),
            payload={
                "text": "Error handling pattern with retry logic and exponential backoff",
                "pattern_type": "error_handling",
                "complexity": "medium",
            },
        ),
        ModelVectorIndexPoint(
            id=uuid4(),
            payload={
                "text": "Async task processing with message queue for background jobs",
                "pattern_type": "async_processing",
                "complexity": "high",
            },
        ),
    ]


# =============================================================================
# Contract Validation Tests
# =============================================================================


class TestContractValidation:
    """Test contract validation and error handling."""

    def test_vector_index_point_requires_text(self):
        """Test that ModelVectorIndexPoint validates text field."""
        with pytest.raises(ValueError, match="text"):
            ModelVectorIndexPoint(payload={"pattern_type": "test"})  # Missing 'text'

    def test_vector_index_point_rejects_empty_text(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValueError, match="text"):
            ModelVectorIndexPoint(payload={"text": "   "})  # Empty/whitespace only

    def test_index_contract_requires_points(self):
        """Test that index contract requires at least one point."""
        with pytest.raises(ValueError):
            ModelContractVectorIndexEffect(
                collection_name=TEST_COLLECTION, points=[]  # Empty list
            )

    def test_index_contract_limits_batch_size(self):
        """Test that batch size is limited to 100 points."""
        points = [
            ModelVectorIndexPoint(payload={"text": f"Pattern {i}"}) for i in range(101)
        ]

        with pytest.raises(ValueError):
            ModelContractVectorIndexEffect(
                collection_name=TEST_COLLECTION, points=points
            )

    def test_batch_contract_validates_batch_sizes(self):
        """Test that batch contract validates individual batch sizes."""
        # Create one valid batch and one oversized batch
        valid_batch = [
            ModelVectorIndexPoint(payload={"text": f"Pattern {i}"}) for i in range(50)
        ]
        oversized_batch = [
            ModelVectorIndexPoint(payload={"text": f"Pattern {i}"}) for i in range(101)
        ]

        with pytest.raises(ValueError, match="Maximum is 100"):
            ModelContractBatchIndexEffect(
                collection_name=TEST_COLLECTION,
                batch_points=[valid_batch, oversized_batch],
            )


# =============================================================================
# Vector Indexing Tests
# =============================================================================


class TestVectorIndexing:
    """Test vector indexing operations."""

    @pytest.mark.asyncio
    async def test_index_single_batch(self, vector_index_node, sample_pattern_points):
        """Test indexing a single batch of patterns."""
        contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=sample_pattern_points
        )

        result = await vector_index_node.execute_effect(contract)

        assert result.status == "success"
        assert result.indexed_count == len(sample_pattern_points)
        assert len(result.point_ids) == len(sample_pattern_points)
        assert result.collection_name == TEST_COLLECTION
        assert result.duration_ms > 0

        # Verify performance metrics were recorded
        metrics = vector_index_node.get_metrics()
        assert "total_duration_ms" in metrics
        assert "embedding_generation_ms" in metrics
        assert "upsert_duration_ms" in metrics

    @pytest.mark.asyncio
    async def test_index_creates_collection_automatically(self, vector_index_node):
        """Test that indexing creates collection if it doesn't exist."""
        new_collection = f"{TEST_COLLECTION}_autocreate"

        point = ModelVectorIndexPoint(payload={"text": "Test pattern for autocreate"})

        contract = ModelContractVectorIndexEffect(
            collection_name=new_collection, points=[point]
        )

        result = await vector_index_node.execute_effect(contract)

        assert result.status == "success"
        assert result.indexed_count == 1

        # Verify collection exists
        collection_info = await vector_index_node.qdrant_client.get_collection(
            collection_name=new_collection
        )
        assert collection_info is not None

        # Cleanup
        await vector_index_node.qdrant_client.delete_collection(
            collection_name=new_collection
        )

    @pytest.mark.asyncio
    async def test_index_performance_target(self, vector_index_node):
        """Test that indexing 100 patterns completes in <2s."""
        # Generate 100 test patterns
        large_batch = [
            ModelVectorIndexPoint(
                payload={
                    "text": f"Performance test pattern {i} with sufficient text content",
                    "index": i,
                }
            )
            for i in range(100)
        ]

        contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=large_batch
        )

        result = await vector_index_node.execute_effect(contract)

        assert result.status == "success"
        assert result.indexed_count == 100
        assert (
            result.duration_ms < 2000
        ), f"Indexing took {result.duration_ms}ms, target is <2000ms"

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_points(self, vector_index_node):
        """Test that upserting with same ID updates the point."""
        point_id = uuid4()

        # Initial index
        point_v1 = ModelVectorIndexPoint(
            id=point_id, payload={"text": "Original pattern text", "version": 1}
        )

        contract_v1 = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=[point_v1]
        )

        result_v1 = await vector_index_node.execute_effect(contract_v1)
        assert result_v1.indexed_count == 1

        # Update with same ID
        point_v2 = ModelVectorIndexPoint(
            id=point_id, payload={"text": "Updated pattern text", "version": 2}
        )

        contract_v2 = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=[point_v2]
        )

        result_v2 = await vector_index_node.execute_effect(contract_v2)
        assert result_v2.indexed_count == 1

        # Verify only one point exists
        points = await vector_index_node.qdrant_client.scroll(
            collection_name=TEST_COLLECTION,
            limit=100,
        )
        matching_points = [p for p in points[0] if str(p.id) == str(point_id)]
        assert len(matching_points) == 1
        assert matching_points[0].payload["version"] == 2


# =============================================================================
# Vector Search Tests
# =============================================================================


class TestVectorSearch:
    """Test vector similarity search operations."""

    @pytest.mark.asyncio
    async def test_search_similar_patterns(
        self, vector_index_node, sample_pattern_points
    ):
        """Test searching for similar patterns."""
        # First, index the patterns
        index_contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=sample_pattern_points
        )
        await vector_index_node.execute_effect(index_contract)

        # Search for performance optimization patterns
        search_contract = ModelContractVectorSearchEffect(
            collection_name=TEST_COLLECTION,
            query_text="How to optimize database performance with caching",
            limit=3,
            score_threshold=0.5,
        )

        result = await vector_index_node.search_similar(search_contract)

        assert result.total_results > 0
        assert len(result.hits) <= 3
        assert result.search_time_ms > 0
        assert result.collection_name == TEST_COLLECTION

        # Verify hits are sorted by score (descending)
        scores = [hit.score for hit in result.hits]
        assert scores == sorted(scores, reverse=True)

        # Verify all scores are above threshold
        for hit in result.hits:
            assert hit.score >= 0.5

    @pytest.mark.asyncio
    async def test_search_performance_under_100ms(self, vector_index_node):
        """Test that search completes in <100ms for 1000+ patterns."""
        # Index 1000+ patterns for performance test
        large_dataset = []
        for i in range(1000):
            point = ModelVectorIndexPoint(
                payload={
                    "text": f"Pattern {i}: Database query optimization technique number {i}",
                    "index": i,
                }
            )
            large_dataset.append(point)

        # Index in batches of 100
        for batch_start in range(0, len(large_dataset), 100):
            batch = large_dataset[batch_start : batch_start + 100]
            contract = ModelContractVectorIndexEffect(
                collection_name=TEST_COLLECTION, points=batch
            )
            await vector_index_node.execute_effect(contract)

        # Perform search
        search_contract = ModelContractVectorSearchEffect(
            collection_name=TEST_COLLECTION,
            query_text="Database optimization strategies",
            limit=10,
            score_threshold=0.6,
        )

        result = await vector_index_node.search_similar(search_contract)

        assert (
            result.search_time_ms < 100
        ), f"Search took {result.search_time_ms}ms, target is <100ms"
        assert result.total_results > 0

    @pytest.mark.asyncio
    async def test_search_empty_collection_returns_no_results(self, vector_index_node):
        """Test searching an empty collection returns no results."""
        empty_collection = f"{TEST_COLLECTION}_empty"

        # Ensure collection exists but is empty
        await vector_index_node._ensure_collection_exists(empty_collection)

        search_contract = ModelContractVectorSearchEffect(
            collection_name=empty_collection,
            query_text="Find patterns in empty collection",
            limit=10,
        )

        result = await vector_index_node.search_similar(search_contract)

        assert result.total_results == 0
        assert len(result.hits) == 0

        # Cleanup
        await vector_index_node.qdrant_client.delete_collection(
            collection_name=empty_collection
        )


# =============================================================================
# Delete Operation Tests
# =============================================================================


class TestDeleteOperations:
    """Test pattern deletion operations."""

    @pytest.mark.asyncio
    async def test_delete_single_pattern(self, vector_index_node):
        """Test deleting a single pattern point."""
        # Index a pattern
        point = ModelVectorIndexPoint(payload={"text": "Pattern to be deleted"})

        index_contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=[point]
        )
        await vector_index_node.execute_effect(index_contract)

        # Delete the pattern
        delete_contract = ModelContractVectorDeleteEffect(
            collection_name=TEST_COLLECTION, point_ids=[point.id]
        )

        result = await vector_index_node.delete_pattern(delete_contract)

        assert result.status == "success"
        assert result.deleted_count == 1
        assert result.collection_name == TEST_COLLECTION
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_delete_multiple_patterns(
        self, vector_index_node, sample_pattern_points
    ):
        """Test deleting multiple pattern points."""
        # Index patterns
        index_contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=sample_pattern_points
        )
        await vector_index_node.execute_effect(index_contract)

        # Delete first 3 patterns
        ids_to_delete = [p.id for p in sample_pattern_points[:3]]

        delete_contract = ModelContractVectorDeleteEffect(
            collection_name=TEST_COLLECTION, point_ids=ids_to_delete
        )

        result = await vector_index_node.delete_pattern(delete_contract)

        assert result.status == "success"
        assert result.deleted_count == 3


# =============================================================================
# Batch Operation Tests
# =============================================================================


class TestBatchOperations:
    """Test batch indexing operations."""

    @pytest.mark.asyncio
    async def test_batch_index_multiple_batches(self, vector_index_node):
        """Test batch indexing of multiple pattern batches."""
        # Create 3 batches of 10 patterns each
        batch1 = [
            ModelVectorIndexPoint(payload={"text": f"Batch 1 Pattern {i}"})
            for i in range(10)
        ]
        batch2 = [
            ModelVectorIndexPoint(payload={"text": f"Batch 2 Pattern {i}"})
            for i in range(10)
        ]
        batch3 = [
            ModelVectorIndexPoint(payload={"text": f"Batch 3 Pattern {i}"})
            for i in range(10)
        ]

        contract = ModelContractBatchIndexEffect(
            collection_name=TEST_COLLECTION, batch_points=[batch1, batch2, batch3]
        )

        result = await vector_index_node.batch_index(contract)

        assert result.status == "success"
        assert result.total_indexed == 30
        assert result.batches_processed == 3
        assert result.failed_batches == 0
        assert result.total_duration_ms > 0

    @pytest.mark.asyncio
    async def test_batch_index_handles_partial_failures(self, vector_index_node):
        """Test that batch indexing continues despite individual batch failures."""
        # This is a simulation test - in real scenario, a batch might fail
        # For now, we just verify the mechanism works with valid data

        batch1 = [
            ModelVectorIndexPoint(payload={"text": f"Valid Pattern {i}"})
            for i in range(10)
        ]

        contract = ModelContractBatchIndexEffect(
            collection_name=TEST_COLLECTION, batch_points=[batch1]
        )

        result = await vector_index_node.batch_index(contract)

        # Should succeed with all batches valid
        assert result.status == "success"
        assert result.batches_processed == 1
        assert result.failed_batches == 0


# =============================================================================
# Resource Management Tests
# =============================================================================


class TestResourceManagement:
    """Test resource management and cleanup."""

    @pytest.mark.asyncio
    async def test_node_cleanup_closes_connections(self):
        """Test that node cleanup closes connections properly."""
        node = NodeQdrantVectorIndexEffect(
            qdrant_url=QDRANT_URL, ollama_base_url=OLLAMA_BASE_URL
        )

        # Use the node
        point = ModelVectorIndexPoint(payload={"text": "Cleanup test pattern"})
        contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=[point]
        )
        await node.execute_effect(contract)

        # Cleanup
        await node.close()

        # Verify connections are closed (attempting operations should fail)
        with pytest.raises(Exception):
            await node.qdrant_client.get_collections()


# =============================================================================
# Performance Metrics Tests
# =============================================================================


class TestPerformanceMetrics:
    """Test performance metrics tracking."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_indexing(
        self, vector_index_node, sample_pattern_points
    ):
        """Test that performance metrics are recorded during indexing."""
        contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=sample_pattern_points
        )

        await vector_index_node.execute_effect(contract)

        metrics = vector_index_node.get_metrics()

        # Verify all expected metrics are present
        assert "total_duration_ms" in metrics
        assert "embedding_generation_ms" in metrics
        assert "upsert_duration_ms" in metrics
        assert "embeddings_per_second" in metrics
        assert "points_per_second" in metrics

        # Verify metrics have reasonable values
        assert metrics["total_duration_ms"] > 0
        assert metrics["embeddings_per_second"] > 0
        assert metrics["points_per_second"] > 0

    @pytest.mark.asyncio
    async def test_metrics_recorded_for_search(
        self, vector_index_node, sample_pattern_points
    ):
        """Test that search metrics are recorded."""
        # Index patterns first
        index_contract = ModelContractVectorIndexEffect(
            collection_name=TEST_COLLECTION, points=sample_pattern_points
        )
        await vector_index_node.execute_effect(index_contract)

        # Perform search
        search_contract = ModelContractVectorSearchEffect(
            collection_name=TEST_COLLECTION, query_text="Test search query", limit=5
        )

        await vector_index_node.search_similar(search_contract)

        metrics = vector_index_node.get_metrics()

        assert "search_duration_ms" in metrics
        assert metrics["search_duration_ms"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
