"""
Integration Tests for End-to-End Pattern Learning Flow
AI-Generated with agent-testing methodology
Coverage Target: 95%+

Tests complete flow:
1. Pattern extraction from execution trace
2. Storage in PostgreSQL
3. Vector embedding generation
4. Indexing in Qdrant
5. Pattern retrieval and matching
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from asyncpg import Pool
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct


class TestEndToEndPatternFlow:
    """Integration tests for complete pattern learning workflow."""

    @pytest.mark.asyncio
    async def test_complete_pattern_lifecycle(
        self,
        integration_environment: Dict[str, Any],
        sample_pattern: Dict[str, Any],
        sample_embedding: List[float],
        performance_timer,
    ):
        """
        Test complete pattern lifecycle:
        - Store pattern in PostgreSQL
        - Index vector in Qdrant
        - Search and retrieve pattern
        - Update pattern metadata
        - Delete pattern from both systems
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        pattern = sample_pattern
        embedding = sample_embedding

        # Act & Assert - Full lifecycle
        performance_timer.start()

        # Step 1: Store in PostgreSQL
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(pattern["pattern_id"]),
                pattern["pattern_type"],
                pattern["intent_keywords"],
                pattern["execution_sequence"],
                pattern["success_criteria"],
                pattern["metadata"],
            )

            # Verify PostgreSQL storage
            pg_result = await conn.fetchrow(
                """
                SELECT pattern_id, pattern_type
                FROM success_patterns
                WHERE pattern_id = $1
                """,
                uuid.UUID(pattern["pattern_id"]),
            )
            assert pg_result is not None

        # Step 2: Index in Qdrant
        point = PointStruct(
            id=pattern["pattern_id"],
            vector=embedding,
            payload={
                "pattern_type": pattern["pattern_type"],
                "intent_keywords": pattern["intent_keywords"],
            },
        )

        await qdrant_client.upsert(
            collection_name=collection_name,
            points=[point],
        )

        # Step 3: Search and retrieve
        search_results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=1,
        )

        assert len(search_results) == 1
        assert search_results[0].id == pattern["pattern_id"]

        # Step 4: Update pattern metadata
        async with db_pool.acquire() as conn:
            updated_metadata = {
                **pattern["metadata"],
                "success_count": 10,
            }

            await conn.execute(
                """
                UPDATE success_patterns
                SET metadata = $1, updated_at = NOW()
                WHERE pattern_id = $2
                """,
                updated_metadata,
                uuid.UUID(pattern["pattern_id"]),
            )

            # Verify update
            updated_result = await conn.fetchrow(
                """
                SELECT metadata
                FROM success_patterns
                WHERE pattern_id = $1
                """,
                uuid.UUID(pattern["pattern_id"]),
            )
            assert updated_result["metadata"]["success_count"] == 10

        # Step 5: Delete from both systems
        await qdrant_client.delete(
            collection_name=collection_name,
            points_selector=[pattern["pattern_id"]],
        )

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM success_patterns
                WHERE pattern_id = $1
                """,
                uuid.UUID(pattern["pattern_id"]),
            )

        performance_timer.stop()

        # Verify deletion
        retrieved_qdrant = await qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[pattern["pattern_id"]],
        )
        assert len(retrieved_qdrant) == 0

        async with db_pool.acquire() as conn:
            retrieved_pg = await conn.fetchrow(
                """
                SELECT pattern_id
                FROM success_patterns
                WHERE pattern_id = $1
                """,
                uuid.UUID(pattern["pattern_id"]),
            )
            assert retrieved_pg is None

        # Performance: E2E flow should complete in <1000ms
        assert performance_timer.elapsed_ms < 1000, (
            f"E2E flow took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds 1000ms threshold"
        )

    @pytest.mark.asyncio
    async def test_pattern_matching_flow(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        performance_timer,
    ):
        """
        Test pattern matching flow:
        - Store multiple patterns
        - Index all vectors
        - Search for similar patterns
        - Verify ranking by confidence score
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch

        # Act - Store and index all patterns
        performance_timer.start()

        async with db_pool.acquire() as conn:
            for pattern in patterns:
                await conn.execute(
                    """
                    INSERT INTO success_patterns (
                        pattern_id, pattern_type, intent_keywords,
                        execution_sequence, success_criteria, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.UUID(pattern["pattern_id"]),
                    pattern["pattern_type"],
                    pattern["intent_keywords"],
                    pattern["execution_sequence"],
                    pattern["success_criteria"],
                    pattern["metadata"],
                )

        # Index in Qdrant
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

        # Search for top 3 similar patterns
        query_vector = embeddings[0]
        search_results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3,
        )

        performance_timer.stop()

        # Assert
        assert len(search_results) == 3

        # Verify results are ranked by similarity
        for i in range(len(search_results) - 1):
            assert search_results[i].score >= search_results[i + 1].score

        # Performance: Pattern matching should complete in <500ms
        assert performance_timer.elapsed_ms < 500, (
            f"Pattern matching took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds 500ms threshold"
        )

    @pytest.mark.asyncio
    async def test_pattern_usage_tracking(
        self,
        integration_environment: Dict[str, Any],
        sample_pattern: Dict[str, Any],
        mock_correlation_id: str,
    ):
        """
        Test pattern usage tracking flow:
        - Store pattern
        - Log pattern usage
        - Update usage statistics
        - Query usage history
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        pattern = sample_pattern

        # Act - Store pattern and log usage
        async with db_pool.acquire() as conn:
            # Store pattern
            await conn.execute(
                """
                INSERT INTO success_patterns (
                    pattern_id, pattern_type, intent_keywords,
                    execution_sequence, success_criteria, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid.UUID(pattern["pattern_id"]),
                pattern["pattern_type"],
                pattern["intent_keywords"],
                pattern["execution_sequence"],
                pattern["success_criteria"],
                pattern["metadata"],
            )

            # Log pattern usage
            for i in range(3):
                await conn.execute(
                    """
                    INSERT INTO pattern_usage_log (
                        pattern_id, correlation_id, matched_at,
                        similarity_score, applied, outcome
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.UUID(pattern["pattern_id"]),
                    uuid.UUID(mock_correlation_id),
                    datetime.now(timezone.utc),
                    0.85 + (i * 0.05),
                    True,
                    "success",
                )

            # Query usage history
            usage_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM pattern_usage_log
                WHERE pattern_id = $1
                """,
                uuid.UUID(pattern["pattern_id"]),
            )

            # Query success rate
            success_rate = await conn.fetchval(
                """
                SELECT CAST(COUNT(*) FILTER (WHERE outcome = 'success') AS FLOAT) /
                       NULLIF(COUNT(*), 0)
                FROM pattern_usage_log
                WHERE pattern_id = $1
                """,
                uuid.UUID(pattern["pattern_id"]),
            )

        # Assert
        assert usage_count == 3
        assert success_rate == 1.0  # All successful

    @pytest.mark.asyncio
    async def test_concurrent_pattern_operations(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
    ):
        """
        Test concurrent pattern operations:
        - Multiple simultaneous inserts
        - Concurrent searches
        - Data consistency verification
        """
        import asyncio

        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        patterns = sample_patterns_batch[:5]  # Use 5 patterns
        embeddings = sample_embeddings_batch[:5]

        # Act - Concurrent inserts
        async def insert_pattern(pattern: Dict[str, Any], embedding: List[float]):
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO success_patterns (
                        pattern_id, pattern_type, intent_keywords,
                        execution_sequence, success_criteria, metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.UUID(pattern["pattern_id"]),
                    pattern["pattern_type"],
                    pattern["intent_keywords"],
                    pattern["execution_sequence"],
                    pattern["success_criteria"],
                    pattern["metadata"],
                )

            # Index in Qdrant
            point = PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={"pattern_type": pattern["pattern_type"]},
            )

            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[point],
            )

        # Execute concurrent inserts
        await asyncio.gather(
            *[
                insert_pattern(pattern, embedding)
                for pattern, embedding in zip(patterns, embeddings)
            ]
        )

        # Assert - Verify all patterns stored
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM success_patterns
                WHERE pattern_id = ANY($1)
                """,
                [uuid.UUID(p["pattern_id"]) for p in patterns],
            )

        assert count == len(patterns)

        # Verify all vectors indexed
        collection_info = await qdrant_client.get_collection(
            collection_name=collection_name
        )
        assert collection_info.points_count >= len(patterns)
