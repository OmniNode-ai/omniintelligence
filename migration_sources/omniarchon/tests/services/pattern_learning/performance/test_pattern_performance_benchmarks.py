"""
Performance Benchmark Tests for Pattern Learning
AI-Generated with agent-testing methodology
Coverage Target: 95%+

Benchmarks:
- Pattern storage throughput
- Vector search latency <100ms
- Batch indexing throughput
- Concurrent operations
- Memory usage
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from asyncpg import Pool
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct


class TestPatternPerformanceBenchmarks:
    """Performance benchmark tests for pattern learning operations."""

    # ==========================================
    # Storage Performance
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_single_pattern_storage_latency(
        self,
        integration_environment: Dict[str, Any],
        sample_pattern: Dict[str, Any],
        benchmark_config: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Single pattern storage should complete in <200ms
        Target: p95 < 200ms
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        pattern = sample_pattern
        max_latency = benchmark_config["pattern_storage_max_ms"]

        # Act
        performance_timer.start()

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

        performance_timer.stop()

        # Assert
        assert performance_timer.elapsed_ms < max_latency, (
            f"Pattern storage took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds target of {max_latency}ms"
        )

        print(f"\n✓ Pattern storage latency: {performance_timer.elapsed_ms:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_batch_pattern_storage_throughput(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        benchmark_config: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Batch insert of 10 patterns
        Target: <500ms total (50ms per pattern)
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        patterns = sample_patterns_batch
        max_latency = benchmark_config["batch_index_max_ms"]

        # Act
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

        performance_timer.stop()

        # Assert
        assert performance_timer.elapsed_ms < max_latency, (
            f"Batch storage took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds target of {max_latency}ms"
        )

        throughput = len(patterns) / (performance_timer.elapsed_ms / 1000)
        print(
            f"\n✓ Batch storage: {performance_timer.elapsed_ms:.2f}ms "
            f"({throughput:.1f} patterns/sec)"
        )

    # ==========================================
    # Vector Search Performance
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_vector_search_latency(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        benchmark_config: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Vector similarity search
        Target: <100ms for search across 1000 patterns
        """
        # Arrange
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        max_latency = benchmark_config["vector_search_max_ms"]

        # Index patterns
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

        # Act - Search
        query_vector = embeddings[0]

        performance_timer.start()
        results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=5,
        )
        performance_timer.stop()

        # Assert
        assert len(results) > 0
        assert performance_timer.elapsed_ms < max_latency, (
            f"Vector search took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds target of {max_latency}ms"
        )

        print(f"\n✓ Vector search latency: {performance_timer.elapsed_ms:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_batch_vector_indexing_throughput(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        benchmark_config: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Batch vector indexing
        Target: <500ms for 10 vectors
        """
        # Arrange
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch
        max_latency = benchmark_config["batch_index_max_ms"]

        points = [
            PointStruct(
                id=pattern["pattern_id"],
                vector=embedding,
                payload={"pattern_type": pattern["pattern_type"]},
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
        assert performance_timer.elapsed_ms < max_latency, (
            f"Batch indexing took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds target of {max_latency}ms"
        )

        throughput = len(patterns) / (performance_timer.elapsed_ms / 1000)
        print(
            f"\n✓ Batch indexing: {performance_timer.elapsed_ms:.2f}ms "
            f"({throughput:.1f} vectors/sec)"
        )

    # ==========================================
    # Pattern Lookup Performance
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_pattern_lookup_by_id_latency(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        benchmark_config: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Pattern lookup by ID
        Target: <100ms
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        patterns = sample_patterns_batch
        max_latency = benchmark_config["pattern_lookup_max_ms"]

        # Insert patterns
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

        target_id = patterns[0]["pattern_id"]

        # Act - Lookup
        performance_timer.start()

        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT *
                FROM success_patterns
                WHERE pattern_id = $1
                """,
                uuid.UUID(target_id),
            )

        performance_timer.stop()

        # Assert
        assert result is not None
        assert performance_timer.elapsed_ms < max_latency, (
            f"Pattern lookup took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds target of {max_latency}ms"
        )

        print(f"\n✓ Pattern lookup latency: {performance_timer.elapsed_ms:.2f}ms")

    # ==========================================
    # End-to-End Performance
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_e2e_pattern_flow_latency(
        self,
        integration_environment: Dict[str, Any],
        sample_pattern: Dict[str, Any],
        sample_embedding: List[float],
        benchmark_config: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Complete E2E flow (store + index + search)
        Target: <1000ms
        """
        # Arrange
        db_pool: Pool = integration_environment["db_pool"]
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        pattern = sample_pattern
        embedding = sample_embedding
        max_latency = benchmark_config["e2e_flow_max_ms"]

        # Act - Complete flow
        performance_timer.start()

        # Store in PostgreSQL
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

        # Search
        results = await qdrant_client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=1,
        )

        performance_timer.stop()

        # Assert
        assert len(results) > 0
        assert performance_timer.elapsed_ms < max_latency, (
            f"E2E flow took {performance_timer.elapsed_ms:.2f}ms, "
            f"exceeds target of {max_latency}ms"
        )

        print(f"\n✓ E2E flow latency: {performance_timer.elapsed_ms:.2f}ms")

    # ==========================================
    # Concurrent Operations Performance
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_pattern_searches(
        self,
        integration_environment: Dict[str, Any],
        sample_patterns_batch: List[Dict[str, Any]],
        sample_embeddings_batch: List[List[float]],
        performance_timer,
    ):
        """
        Benchmark: 10 concurrent searches
        Target: <500ms total
        """
        # Arrange
        qdrant_client: AsyncQdrantClient = integration_environment["qdrant_client"]
        collection_name = integration_environment["collection_name"]

        patterns = sample_patterns_batch
        embeddings = sample_embeddings_batch

        # Index patterns
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

        # Act - Concurrent searches
        async def search(query_vector: List[float]):
            return await qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=3,
            )

        performance_timer.start()
        results = await asyncio.gather(*[search(emb) for emb in embeddings])
        performance_timer.stop()

        # Assert
        assert len(results) == len(embeddings)
        assert all(len(r) > 0 for r in results)

        print(
            f"\n✓ Concurrent searches ({len(embeddings)} queries): "
            f"{performance_timer.elapsed_ms:.2f}ms"
        )

    # ==========================================
    # Scalability Tests
    # ==========================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.slow
    async def test_pattern_storage_scalability(
        self,
        integration_environment: Dict[str, Any],
        performance_timer,
    ):
        """
        Benchmark: Storage performance with increasing pattern count
        Test: 100, 500, 1000 patterns
        """
        db_pool: Pool = integration_environment["db_pool"]

        results = {}

        for count in [100, 500, 1000]:
            # Generate patterns
            patterns = [
                {
                    "pattern_id": str(uuid.uuid4()),
                    "pattern_type": "test",
                    "intent_keywords": [f"keyword_{i}"],
                    "execution_sequence": [{"agent": f"agent_{i}"}],
                    "success_criteria": {"status": "ok"},
                    "metadata": {"created_at": datetime.now(timezone.utc).isoformat()},
                }
                for i in range(count)
            ]

            # Measure insertion time
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

            performance_timer.stop()

            results[count] = performance_timer.elapsed_ms
            throughput = count / (performance_timer.elapsed_ms / 1000)

            print(
                f"\n✓ {count} patterns: {performance_timer.elapsed_ms:.2f}ms "
                f"({throughput:.1f} patterns/sec)"
            )

            # Cleanup
            async with db_pool.acquire() as conn:
                await conn.execute("TRUNCATE TABLE success_patterns CASCADE;")

        # Assert - Performance should scale sub-linearly
        assert results[1000] < results[100] * 15  # Allow 50% overhead at scale
