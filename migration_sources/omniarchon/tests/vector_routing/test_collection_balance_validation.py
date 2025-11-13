"""
Collection Balance Validation Tests

Tests to validate collection balance, performance parity, and search consistency
across quality_vectors and archon_vectors collections.
"""

import asyncio
import os
import sys
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

# Add the search service to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/search"))
sys.path.append(
    os.path.join(os.path.dirname(__file__), "../../services/search/engines")
)

from engines.qdrant_adapter import QdrantAdapter
from models.search_models import EntityType, SearchRequest, SearchResult


class TestCollectionBalanceValidation:
    """Test suite for collection balance validation"""

    @pytest.fixture
    def mock_qdrant_adapter(self):
        """Mock Qdrant adapter with collection statistics"""
        adapter = Mock(spec=QdrantAdapter)

        # Mock collection statistics
        def mock_get_collection_stats(collection_name=None):
            stats = {
                "quality_vectors": {
                    "collection_name": "quality_vectors",
                    "vectors_count": 2500,
                    "indexed_vectors_count": 2500,
                    "points_count": 2500,
                    "segments_count": 2,
                    "disk_data_size": 50000000,  # 50MB
                    "ram_data_size": 25000000,  # 25MB
                },
                "archon_vectors": {
                    "collection_name": "archon_vectors",
                    "vectors_count": 7500,
                    "indexed_vectors_count": 7500,
                    "points_count": 7500,
                    "segments_count": 3,
                    "disk_data_size": 150000000,  # 150MB
                    "ram_data_size": 75000000,  # 75MB
                },
            }
            return asyncio.create_task(
                asyncio.coroutine(
                    lambda: stats.get(collection_name, stats["archon_vectors"])
                )()
            )

        adapter.get_collection_stats.side_effect = mock_get_collection_stats

        # Mock similarity search with performance timing
        async def mock_similarity_search(query_vector, request, collection_name=None):
            # Simulate different performance characteristics
            if collection_name == "quality_vectors":
                await asyncio.sleep(0.05)  # 50ms
                return [
                    SearchResult(
                        entity_id=f"quality_entity_{i}",
                        entity_type=EntityType.DOCUMENT,
                        title=f"Quality Document {i}",
                        relevance_score=0.9 - (i * 0.1),
                        semantic_score=0.9 - (i * 0.1),
                    )
                    for i in range(min(request.limit, 5))
                ]
            else:
                await asyncio.sleep(0.08)  # 80ms
                return [
                    SearchResult(
                        entity_id=f"general_entity_{i}",
                        entity_type=EntityType.DOCUMENT,
                        title=f"General Document {i}",
                        relevance_score=0.85 - (i * 0.1),
                        semantic_score=0.85 - (i * 0.1),
                    )
                    for i in range(min(request.limit, 8))
                ]

        adapter.similarity_search.side_effect = mock_similarity_search

        # Mock health check
        adapter.health_check = AsyncMock(return_value=True)

        return adapter

    @pytest.fixture
    def mock_vector_engine(self, mock_qdrant_adapter):
        """Mock vector search engine with Qdrant adapter"""
        engine = Mock()
        engine.qdrant_adapter = mock_qdrant_adapter
        engine.generate_embeddings = AsyncMock(return_value=[np.random.rand(1536)])
        return engine

    @pytest.fixture
    def mock_search_orchestrator(self, mock_vector_engine):
        """Mock search orchestrator with vector engine"""
        orchestrator = Mock()
        orchestrator.vector_engine = mock_vector_engine
        return orchestrator

    @pytest.mark.asyncio
    async def test_collection_size_monitoring(self, mock_qdrant_adapter):
        """Test monitoring of collection sizes and balance"""

        # Get statistics for both collections
        quality_stats = await mock_qdrant_adapter.get_collection_stats(
            "quality_vectors"
        )
        archon_stats = await mock_qdrant_adapter.get_collection_stats("archon_vectors")

        # Verify basic stats structure
        assert "vectors_count" in quality_stats
        assert "vectors_count" in archon_stats

        # Calculate balance metrics
        total_vectors = quality_stats["vectors_count"] + archon_stats["vectors_count"]
        quality_percentage = (quality_stats["vectors_count"] / total_vectors) * 100
        archon_percentage = (archon_stats["vectors_count"] / total_vectors) * 100

        # Verify reasonable distribution (quality should be smaller subset)
        assert (
            quality_percentage < 50
        ), "Quality collection should be smaller than general collection"
        assert (
            archon_percentage > 50
        ), "General collection should contain majority of documents"

        # Verify minimum thresholds
        assert (
            quality_stats["vectors_count"] > 0
        ), "Quality collection should not be empty"
        assert (
            archon_stats["vectors_count"] > 0
        ), "General collection should not be empty"

        # Log balance information for monitoring
        print("Collection Balance:")
        print(
            f"  Quality vectors: {quality_stats['vectors_count']} ({quality_percentage:.1f}%)"
        )
        print(
            f"  Archon vectors: {archon_stats['vectors_count']} ({archon_percentage:.1f}%)"
        )

    @pytest.mark.asyncio
    async def test_collection_performance_parity(self, mock_qdrant_adapter):
        """Test that both collections maintain similar performance characteristics"""

        # Create test search request
        search_request = SearchRequest(
            query="test query", limit=10, semantic_threshold=0.7
        )

        query_vector = np.random.rand(1536)

        # Measure search performance for quality_vectors
        start_time = time.time()
        quality_results = await mock_qdrant_adapter.similarity_search(
            query_vector, search_request, "quality_vectors"
        )
        quality_time = (time.time() - start_time) * 1000

        # Measure search performance for archon_vectors
        start_time = time.time()
        archon_results = await mock_qdrant_adapter.similarity_search(
            query_vector, search_request, "archon_vectors"
        )
        archon_time = (time.time() - start_time) * 1000

        # Verify both collections return results
        assert len(quality_results) > 0, "Quality collection should return results"
        assert len(archon_results) > 0, "General collection should return results"

        # Verify performance is within acceptable range (both under 100ms)
        assert (
            quality_time < 100
        ), f"Quality collection search took {quality_time:.2f}ms (should be <100ms)"
        assert (
            archon_time < 100
        ), f"General collection search took {archon_time:.2f}ms (should be <100ms)"

        # Performance should be comparable (within 50ms difference)
        time_difference = abs(quality_time - archon_time)
        assert (
            time_difference < 50
        ), f"Performance difference of {time_difference:.2f}ms is too large"

        print("Performance comparison:")
        print(
            f"  Quality vectors: {quality_time:.2f}ms ({len(quality_results)} results)"
        )
        print(f"  Archon vectors: {archon_time:.2f}ms ({len(archon_results)} results)")

    @pytest.mark.asyncio
    async def test_search_result_quality_consistency(self, mock_qdrant_adapter):
        """Test that search results maintain quality consistency across collections"""

        search_request = SearchRequest(
            query="technical analysis", limit=5, semantic_threshold=0.5
        )

        query_vector = np.random.rand(1536)

        # Get results from both collections
        quality_results = await mock_qdrant_adapter.similarity_search(
            query_vector, search_request, "quality_vectors"
        )
        archon_results = await mock_qdrant_adapter.similarity_search(
            query_vector, search_request, "archon_vectors"
        )

        # Verify result structure consistency
        for result in quality_results:
            assert hasattr(result, "entity_id"), "Quality results should have entity_id"
            assert hasattr(
                result, "relevance_score"
            ), "Quality results should have relevance_score"
            assert hasattr(
                result, "semantic_score"
            ), "Quality results should have semantic_score"
            assert (
                0 <= result.relevance_score <= 1
            ), "Relevance score should be between 0 and 1"

        for result in archon_results:
            assert hasattr(result, "entity_id"), "Archon results should have entity_id"
            assert hasattr(
                result, "relevance_score"
            ), "Archon results should have relevance_score"
            assert hasattr(
                result, "semantic_score"
            ), "Archon results should have semantic_score"
            assert (
                0 <= result.relevance_score <= 1
            ), "Relevance score should be between 0 and 1"

        # Verify results are ordered by relevance (descending)
        if len(quality_results) > 1:
            for i in range(len(quality_results) - 1):
                assert (
                    quality_results[i].relevance_score
                    >= quality_results[i + 1].relevance_score
                ), "Quality results should be ordered by relevance score"

        if len(archon_results) > 1:
            for i in range(len(archon_results) - 1):
                assert (
                    archon_results[i].relevance_score
                    >= archon_results[i + 1].relevance_score
                ), "Archon results should be ordered by relevance score"

    @pytest.mark.asyncio
    async def test_collection_resource_utilization(self, mock_qdrant_adapter):
        """Test resource utilization patterns across collections"""

        # Get resource statistics
        quality_stats = await mock_qdrant_adapter.get_collection_stats(
            "quality_vectors"
        )
        archon_stats = await mock_qdrant_adapter.get_collection_stats("archon_vectors")

        # Calculate resource efficiency metrics
        quality_disk_per_vector = (
            quality_stats["disk_data_size"] / quality_stats["vectors_count"]
        )
        archon_disk_per_vector = (
            archon_stats["disk_data_size"] / archon_stats["vectors_count"]
        )

        quality_ram_per_vector = (
            quality_stats["ram_data_size"] / quality_stats["vectors_count"]
        )
        archon_ram_per_vector = (
            archon_stats["ram_data_size"] / archon_stats["vectors_count"]
        )

        # Verify reasonable resource utilization
        assert quality_disk_per_vector > 0, "Quality collection should use disk space"
        assert archon_disk_per_vector > 0, "Archon collection should use disk space"

        # Resource usage per vector should be comparable
        disk_ratio = quality_disk_per_vector / archon_disk_per_vector
        ram_ratio = quality_ram_per_vector / archon_ram_per_vector

        assert (
            0.5 < disk_ratio < 2.0
        ), f"Disk usage per vector ratio ({disk_ratio:.2f}) seems unusual"
        assert (
            0.5 < ram_ratio < 2.0
        ), f"RAM usage per vector ratio ({ram_ratio:.2f}) seems unusual"

        print("Resource utilization per vector:")
        print(
            f"  Quality - Disk: {quality_disk_per_vector:.0f} bytes, RAM: {quality_ram_per_vector:.0f} bytes"
        )
        print(
            f"  Archon - Disk: {archon_disk_per_vector:.0f} bytes, RAM: {archon_ram_per_vector:.0f} bytes"
        )

    @pytest.mark.asyncio
    async def test_concurrent_collection_access(self, mock_qdrant_adapter):
        """Test concurrent access to both collections"""

        search_request = SearchRequest(
            query="concurrent test", limit=3, semantic_threshold=0.6
        )

        query_vector = np.random.rand(1536)

        # Create concurrent search tasks
        tasks = []
        for i in range(5):
            # Alternate between collections
            collection = "quality_vectors" if i % 2 == 0 else "archon_vectors"
            task = mock_qdrant_adapter.similarity_search(
                query_vector, search_request, collection
            )
            tasks.append(task)

        # Execute all searches concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = (time.time() - start_time) * 1000

        # Verify all searches completed successfully
        assert len(results) == 5, "All concurrent searches should complete"
        for result_list in results:
            assert isinstance(result_list, list), "Each search should return a list"
            assert len(result_list) > 0, "Each search should return results"

        # Verify concurrent performance is reasonable
        average_time_per_search = total_time / 5
        assert (
            average_time_per_search < 200
        ), f"Average concurrent search time {average_time_per_search:.2f}ms is too high"

        print("Concurrent access test:")
        print(f"  Total time: {total_time:.2f}ms")
        print(f"  Average per search: {average_time_per_search:.2f}ms")

    @pytest.mark.asyncio
    async def test_collection_scaling_characteristics(self, mock_qdrant_adapter):
        """Test scaling characteristics as collections grow"""

        # Simulate collection growth by increasing vector counts
        await mock_qdrant_adapter.get_collection_stats("archon_vectors")

        # Simulate different collection sizes
        test_sizes = [1000, 5000, 10000, 25000]
        performance_data = []

        for size in test_sizes:
            # Mock updated stats for this size
            mock_qdrant_adapter.get_collection_stats = AsyncMock(
                return_value={
                    "collection_name": "archon_vectors",
                    "vectors_count": size,
                    "indexed_vectors_count": size,
                    "points_count": size,
                    "segments_count": max(1, size // 5000),
                    "disk_data_size": size * 20000,  # 20KB per vector
                    "ram_data_size": size * 10000,  # 10KB per vector
                }
            )

            # Measure simulated search performance
            search_request = SearchRequest(query="scaling test", limit=10)
            query_vector = np.random.rand(1536)

            start_time = time.time()
            await mock_qdrant_adapter.similarity_search(query_vector, search_request)
            search_time = (time.time() - start_time) * 1000

            performance_data.append(
                {
                    "size": size,
                    "search_time": search_time,
                    "segments": max(1, size // 5000),
                }
            )

        # Verify scaling is sub-linear (search time shouldn't grow linearly with size)
        for i in range(1, len(performance_data)):
            size_ratio = performance_data[i]["size"] / performance_data[0]["size"]
            time_ratio = (
                performance_data[i]["search_time"] / performance_data[0]["search_time"]
            )

            # Time ratio should be less than size ratio (sub-linear scaling)
            assert (
                time_ratio < size_ratio
            ), f"Search time scaling ({time_ratio:.2f}) should be better than linear ({size_ratio:.2f})"

        print("Scaling characteristics:")
        for data in performance_data:
            print(
                f"  Size: {data['size']:,} vectors, Time: {data['search_time']:.2f}ms, Segments: {data['segments']}"
            )

    @pytest.mark.asyncio
    async def test_collection_health_monitoring(self, mock_qdrant_adapter):
        """Test health monitoring across both collections"""

        # Test health check for both collections
        quality_health = await mock_qdrant_adapter.health_check()
        archon_health = await mock_qdrant_adapter.health_check()

        assert quality_health is True, "Quality collection should be healthy"
        assert archon_health is True, "Archon collection should be healthy"

        # Get detailed stats for health assessment
        quality_stats = await mock_qdrant_adapter.get_collection_stats(
            "quality_vectors"
        )
        archon_stats = await mock_qdrant_adapter.get_collection_stats("archon_vectors")

        # Health indicators
        quality_health_score = self._calculate_collection_health_score(quality_stats)
        archon_health_score = self._calculate_collection_health_score(archon_stats)

        assert (
            quality_health_score > 0.8
        ), f"Quality collection health score ({quality_health_score:.2f}) is too low"
        assert (
            archon_health_score > 0.8
        ), f"Archon collection health score ({archon_health_score:.2f}) is too low"

        print("Collection health scores:")
        print(f"  Quality collection: {quality_health_score:.2f}")
        print(f"  Archon collection: {archon_health_score:.2f}")

    def _calculate_collection_health_score(self, stats: Dict[str, Any]) -> float:
        """Calculate a health score for a collection based on its statistics"""
        score = 1.0

        # Check if all vectors are indexed
        if stats["vectors_count"] > 0:
            index_ratio = stats["indexed_vectors_count"] / stats["vectors_count"]
            score *= index_ratio

        # Check reasonable segment count (not too fragmented)
        if stats["vectors_count"] > 0:
            vectors_per_segment = stats["vectors_count"] / max(
                1, stats["segments_count"]
            )
            if vectors_per_segment < 100:  # Too fragmented
                score *= 0.8
            elif vectors_per_segment > 50000:  # Segments too large
                score *= 0.9

        # Check reasonable memory usage
        if stats["vectors_count"] > 0:
            ram_per_vector = stats["ram_data_size"] / stats["vectors_count"]
            if ram_per_vector > 50000:  # More than 50KB per vector seems high
                score *= 0.9

        return score

    @pytest.mark.asyncio
    async def test_load_distribution_analysis(self, mock_qdrant_adapter):
        """Test load distribution patterns across collections"""

        # Simulate different query patterns
        query_patterns = [
            ("quality analysis", "quality_vectors"),
            ("technical report", "quality_vectors"),
            ("API documentation", "archon_vectors"),
            ("user guide", "archon_vectors"),
            ("performance metrics", "quality_vectors"),
            ("design specification", "archon_vectors"),
        ]

        collection_load = {"quality_vectors": 0, "archon_vectors": 0}
        total_time = {"quality_vectors": 0, "archon_vectors": 0}

        # Execute queries and measure load
        for query, expected_collection in query_patterns:
            search_request = SearchRequest(query=query, limit=5)
            query_vector = np.random.rand(1536)

            start_time = time.time()
            await mock_qdrant_adapter.similarity_search(
                query_vector, search_request, expected_collection
            )
            elapsed_time = (time.time() - start_time) * 1000

            collection_load[expected_collection] += 1
            total_time[expected_collection] += elapsed_time

        # Analyze load distribution
        total_queries = sum(collection_load.values())
        quality_load_percentage = (
            collection_load["quality_vectors"] / total_queries
        ) * 100
        archon_load_percentage = (
            collection_load["archon_vectors"] / total_queries
        ) * 100

        avg_quality_time = total_time["quality_vectors"] / max(
            1, collection_load["quality_vectors"]
        )
        avg_archon_time = total_time["archon_vectors"] / max(
            1, collection_load["archon_vectors"]
        )

        # Verify reasonable load distribution
        assert (
            20 <= quality_load_percentage <= 80
        ), f"Quality collection load ({quality_load_percentage:.1f}%) seems imbalanced"
        assert (
            20 <= archon_load_percentage <= 80
        ), f"Archon collection load ({archon_load_percentage:.1f}%) seems imbalanced"

        # Verify performance consistency
        performance_diff = abs(avg_quality_time - avg_archon_time)
        assert (
            performance_diff < 30
        ), f"Performance difference ({performance_diff:.2f}ms) between collections is too large"

        print("Load distribution analysis:")
        print(
            f"  Quality collection: {quality_load_percentage:.1f}% load, {avg_quality_time:.2f}ms avg"
        )
        print(
            f"  Archon collection: {archon_load_percentage:.1f}% load, {avg_archon_time:.2f}ms avg"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
