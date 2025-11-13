"""
Unit Tests for Pattern Vector Indexing (Qdrant)
AI-Generated with agent-testing methodology
Coverage Target: 95%+

Tests:
- Vector indexing operations
- Similarity search
- Batch operations
- Search performance
- Error handling
"""

import uuid
from typing import Any, Dict, List

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
)


class TestPatternIndexingQdrant:
    """Unit tests for Qdrant vector indexing operations."""

    # ==========================================
    # Indexing Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_index_single_pattern_vector(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_pattern: Dict[str, Any],
        sample_embedding: List[float],
        clean_qdrant,
    ):
        """Test indexing a single pattern vector."""
        # Arrange
        pattern = sample_pattern
        embedding = sample_embedding
        collection_name = "test_patterns"

        point = PointStruct(
            id=pattern["pattern_id"],
            vector=embedding,
            payload={
                "pattern_type": pattern["pattern_type"],
                "intent_keywords": pattern["intent_keywords"],
                "confidence_score": pattern["metadata"]["confidence_score"],
            },
        )

        # Act
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[point],
        )

        # Assert - Retrieve the point to verify
        retrieved = await qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[pattern["pattern_id"]],
        )

        assert len(retrieved) == 1
        assert retrieved[0].id == pattern["pattern_id"]
        assert retrieved[0].payload["pattern_type"] == pattern["pattern_type"]

    @pytest.mark.asyncio
    async def test_batch_index_pattern_vectors(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        clean_qdrant,
        performance_timer,
    ):
        """Test batch indexing of 10 pattern vectors."""
        # Arrange
        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        collection_name = "test_patterns"

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={
                    "pattern_type": pattern["pattern_type"],
                    "intent_keywords": pattern["intent_keywords"],
                    "confidence_score": pattern["metadata"]["confidence_score"],
                },
            )
            for pattern, embedding in zip(patterns, embeddings)
        ]

        # Act
        performance_timer.start()
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )
        performance_timer.stop()

        # Assert
        collection_info = await qdrant_client.get_collection(
            collection_name=collection_name
        )
        assert collection_info.points_count == len(patterns)

        # Performance: Batch indexing should complete in <500ms
        assert performance_timer.elapsed_ms < 500, (
            f"Batch indexing took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds 500ms threshold"
        )

    @pytest.mark.asyncio
    async def test_update_existing_pattern_vector(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_pattern: Dict[str, Any],
        sample_embedding: List[float],
        clean_qdrant,
    ):
        """Test updating an existing pattern vector (upsert)."""
        # Arrange - Index initial vector
        pattern = sample_pattern
        embedding = sample_embedding
        collection_name = "test_patterns"

        initial_point = PointStruct(
            id=pattern["pattern_id"],
            vector=embedding,
            payload={"confidence_score": 0.8},
        )

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[initial_point],
        )

        # Act - Update with new confidence score
        updated_point = PointStruct(
            id=pattern["pattern_id"],
            vector=embedding,
            payload={"confidence_score": 0.95},
        )

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[updated_point],
        )

        # Assert
        retrieved = await qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[pattern["pattern_id"]],
        )

        assert retrieved[0].payload["confidence_score"] == 0.95

    # ==========================================
    # Similarity Search Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_similarity_search_single_result(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        clean_qdrant,
        performance_timer,
    ):
        """Test similarity search returning top 1 result."""
        # Arrange - Index batch
        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        collection_name = "test_patterns"

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={
                    "pattern_type": pattern["pattern_type"],
                    "confidence_score": pattern["metadata"]["confidence_score"],
                },
            )
            for pattern, embedding in zip(patterns, embeddings)
        ]

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        # Act - Search using first embedding as query
        query_vector = embeddings[0]

        performance_timer.start()
        results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=1,
        )
        performance_timer.stop()

        # Assert
        assert len(results) == 1
        assert results[0].id == patterns[0]["pattern_id"]
        assert results[0].score > 0.9  # Should be very similar to itself

        # Performance: Search should complete in <100ms
        assert performance_timer.elapsed_ms < 100, (
            f"Similarity search took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds 100ms threshold"
        )

    @pytest.mark.asyncio
    async def test_similarity_search_with_limit(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        clean_qdrant,
    ):
        """Test similarity search with custom limit."""
        # Arrange
        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        collection_name = "test_patterns"

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={"pattern_type": pattern["pattern_type"]},
            )
            for pattern, embedding in zip(patterns, embeddings)
        ]

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        # Act - Search with limit=5
        query_vector = embeddings[0]
        results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=5,
        )

        # Assert
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_similarity_search_with_score_threshold(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        clean_qdrant,
    ):
        """Test similarity search with minimum score threshold."""
        # Arrange
        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        collection_name = "test_patterns"

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={"pattern_type": pattern["pattern_type"]},
            )
            for pattern, embedding in zip(patterns, embeddings)
        ]

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        # Act - Search with score threshold
        query_vector = embeddings[0]
        results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            score_threshold=0.7,
            limit=10,
        )

        # Assert
        assert len(results) > 0
        for result in results:
            assert result.score >= 0.7

    @pytest.mark.asyncio
    async def test_similarity_search_with_filter(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        clean_qdrant,
    ):
        """Test similarity search with payload filter."""
        # Arrange
        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        collection_name = "test_patterns"

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={
                    "pattern_type": pattern["pattern_type"],
                    "confidence_score": pattern["metadata"]["confidence_score"],
                },
            )
            for pattern, embedding in zip(patterns, embeddings)
        ]

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        # Act - Search filtered by pattern_type
        query_vector = embeddings[0]
        results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="pattern_type",
                        match=MatchValue(value="agent_sequence"),
                    )
                ]
            ),
            limit=10,
        )

        # Assert
        assert len(results) > 0
        for result in results:
            assert result.payload["pattern_type"] == "agent_sequence"

    # ==========================================
    # Delete Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_delete_pattern_vector_by_id(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_pattern: Dict[str, Any],
        sample_embedding: List[float],
        clean_qdrant,
    ):
        """Test deleting a pattern vector by ID."""
        # Arrange - Index pattern first
        pattern = sample_pattern
        embedding = sample_embedding
        collection_name = "test_patterns"

        point = PointStruct(
            id=pattern["pattern_id"],
            vector=embedding,
            payload={"pattern_type": pattern["pattern_type"]},
        )

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[point],
        )

        # Act - Delete the point
        await qdrant_client.delete(
            collection_name=collection_name,
            points_selector=[pattern["pattern_id"]],
        )

        # Assert
        retrieved = await qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[pattern["pattern_id"]],
        )

        assert len(retrieved) == 0

    # ==========================================
    # Retrieval Operations
    # ==========================================

    @pytest.mark.asyncio
    async def test_retrieve_pattern_vector_by_id(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_pattern: Dict[str, Any],
        sample_embedding: List[float],
        clean_qdrant,
    ):
        """Test retrieving a pattern vector by ID."""
        # Arrange
        pattern = sample_pattern
        embedding = sample_embedding
        collection_name = "test_patterns"

        point = PointStruct(
            id=pattern["pattern_id"],
            vector=embedding,
            payload={
                "pattern_type": pattern["pattern_type"],
                "confidence_score": pattern["metadata"]["confidence_score"],
            },
        )

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[point],
        )

        # Act
        retrieved = await qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[pattern["pattern_id"]],
            with_vectors=True,
        )

        # Assert
        assert len(retrieved) == 1
        assert retrieved[0].id == pattern["pattern_id"]
        assert retrieved[0].vector == embedding
        assert retrieved[0].payload["pattern_type"] == pattern["pattern_type"]

    # ==========================================
    # Collection Management
    # ==========================================

    @pytest.mark.asyncio
    async def test_collection_stats(
        self,
        qdrant_client: AsyncQdrantClient,
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        clean_qdrant,
    ):
        """Test retrieving collection statistics."""
        # Arrange - Index batch
        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        collection_name = "test_patterns"

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={"pattern_type": pattern["pattern_type"]},
            )
            for pattern, embedding in zip(patterns, embeddings)
        ]

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        # Act
        collection_info = await qdrant_client.get_collection(
            collection_name=collection_name
        )

        # Assert
        assert collection_info.points_count == len(patterns)
        assert collection_info.config.params.vectors.size == 1536
        assert collection_info.config.params.vectors.distance == Distance.COSINE

    # ==========================================
    # Error Handling
    # ==========================================

    @pytest.mark.asyncio
    async def test_search_nonexistent_collection_fails(
        self, qdrant_client: AsyncQdrantClient, sample_embedding: List[float]
    ):
        """Test that searching nonexistent collection raises error."""
        # Act & Assert
        with pytest.raises(Exception):  # Should raise collection not found error
            await qdrant_client.search(
                collection_name="nonexistent_collection",
                query_vector=sample_embedding,
                limit=5,
            )

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_pattern_returns_empty(
        self, qdrant_client: AsyncQdrantClient, clean_qdrant
    ):
        """Test that retrieving nonexistent pattern returns empty list."""
        # Act
        retrieved = await qdrant_client.retrieve(
            collection_name="test_patterns",
            ids=[str(uuid.uuid4())],  # Random ID that doesn't exist
        )

        # Assert
        assert len(retrieved) == 0
