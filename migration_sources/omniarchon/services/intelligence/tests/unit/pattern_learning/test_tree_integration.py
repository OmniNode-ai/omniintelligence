"""
Unit tests for OnexTree integration

Tests the tree info retrieval, caching, and error handling for pattern learning.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from api.pattern_learning.tree_integration import (
    TREE_INFO_CACHE_MAX_SIZE,
    TREE_INFO_CACHE_TTL,
    OnexTreeClient,
    RelevantFile,
    TreeInfo,
    TreeInfoCache,
    TreeMetadata,
    clear_tree_cache,
    get_tree_cache_metrics,
    get_tree_info_for_pattern,
)


class TestTreeInfoCache:
    """Test tree info caching functionality"""

    def test_cache_initialization(self):
        """Test cache initializes with correct parameters"""
        cache = TreeInfoCache(max_size=100, ttl_seconds=600)

        assert cache.max_size == 100
        assert cache.ttl_seconds == 600
        assert len(cache._cache) == 0
        assert cache.metrics.total_requests == 0

    def test_cache_key_generation(self):
        """Test cache key generation from pattern parameters"""
        cache = TreeInfoCache()

        key1 = cache._get_cache_key("pattern1", "onex", "EFFECT")
        key2 = cache._get_cache_key("pattern1", "onex", "EFFECT")
        key3 = cache._get_cache_key("pattern2", "onex", "EFFECT")

        # Same parameters = same key
        assert key1 == key2

        # Different parameters = different key
        assert key1 != key3

        # Keys should be 16 characters (truncated SHA256)
        assert len(key1) == 16

    def test_cache_miss(self):
        """Test cache miss behavior"""
        cache = TreeInfoCache()

        result = cache.get("pattern1", "onex", "EFFECT")

        assert result is None
        assert cache.metrics.misses == 1
        assert cache.metrics.hits == 0
        assert cache.metrics.total_requests == 1

    def test_cache_hit(self):
        """Test cache hit behavior"""
        cache = TreeInfoCache()

        tree_info = TreeInfo(
            relevant_files=[
                RelevantFile(path="test.py", file_type="model", relevance=0.9)
            ],
            tree_metadata=TreeMetadata(total_files=1),
        )

        # Store in cache
        cache.set("pattern1", "onex", tree_info, "EFFECT")

        # Retrieve from cache
        result = cache.get("pattern1", "onex", "EFFECT")

        assert result is not None
        assert result.from_cache is True
        assert len(result.relevant_files) == 1
        assert cache.metrics.hits == 1
        assert cache.metrics.misses == 0
        assert cache.metrics.total_requests == 1

    def test_cache_expiration(self):
        """Test cache entry expiration"""
        cache = TreeInfoCache(ttl_seconds=1)  # 1 second TTL

        tree_info = TreeInfo(
            relevant_files=[
                RelevantFile(path="test.py", file_type="model", relevance=0.9)
            ],
            tree_metadata=TreeMetadata(total_files=1),
        )

        # Store in cache
        cache.set("pattern1", "onex", tree_info, "EFFECT")

        # Manually expire entry
        cache_key = cache._get_cache_key("pattern1", "onex", "EFFECT")
        cache._cache[cache_key].created_at = 0  # Set to epoch

        # Try to retrieve - should be expired
        result = cache.get("pattern1", "onex", "EFFECT")

        assert result is None
        assert cache.metrics.misses == 1
        assert cache.metrics.evictions == 1

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = TreeInfoCache(max_size=2)

        tree_info = TreeInfo(
            relevant_files=[],
            tree_metadata=TreeMetadata(total_files=0),
        )

        # Fill cache to max size
        cache.set("pattern1", "onex", tree_info)
        cache.set("pattern2", "onex", tree_info)

        assert len(cache._cache) == 2

        # Add one more - should evict LRU (pattern1)
        cache.set("pattern3", "onex", tree_info)

        assert len(cache._cache) == 2
        assert cache.metrics.evictions == 1

        # pattern1 should be evicted
        result1 = cache.get("pattern1", "onex")
        assert result1 is None

        # pattern2 and pattern3 should still be cached
        result2 = cache.get("pattern2", "onex")
        result3 = cache.get("pattern3", "onex")
        assert result2 is not None
        assert result3 is not None

    def test_cache_clear(self):
        """Test cache clear operation"""
        cache = TreeInfoCache()

        tree_info = TreeInfo(
            relevant_files=[],
            tree_metadata=TreeMetadata(total_files=0),
        )

        cache.set("pattern1", "onex", tree_info)
        cache.set("pattern2", "onex", tree_info)

        assert len(cache._cache) == 2

        # Clear cache
        cache.clear()

        assert len(cache._cache) == 0
        assert cache.metrics.total_requests == 0
        assert cache.metrics.hits == 0

    def test_cache_metrics(self):
        """Test cache metrics reporting"""
        cache = TreeInfoCache(max_size=100)

        tree_info = TreeInfo(
            relevant_files=[],
            tree_metadata=TreeMetadata(total_files=0),
        )

        # Add some entries
        cache.set("pattern1", "onex", tree_info)
        cache.set("pattern2", "onex", tree_info)

        # Generate some hits and misses
        cache.get("pattern1", "onex")  # Hit
        cache.get("pattern3", "onex")  # Miss

        metrics = cache.get_metrics()

        assert metrics["cache_size"] == 2
        assert metrics["max_size"] == 100
        assert metrics["hits"] == 1
        assert metrics["misses"] == 1
        assert metrics["total_requests"] == 2
        assert metrics["hit_rate"] == 0.5
        assert metrics["utilization"] == 0.02  # 2/100


class TestOnexTreeClient:
    """Test OnexTree HTTP client"""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initializes with correct base URL"""
        client = OnexTreeClient(
            base_url="http://test-server:8058",
            timeout=5.0,
            max_retries=3,
        )

        assert client.base_url == "http://test-server:8058"
        assert client.timeout == 5.0
        assert client.max_retries == 3

    @pytest.mark.asyncio
    async def test_successful_tree_info_retrieval(self):
        """Test successful tree info retrieval from OnexTree service"""
        client = OnexTreeClient()

        # Mock response data
        mock_response_data = {
            "files": [
                {
                    "path": "services/intelligence/src/pattern_learning/node_pattern_query_effect.py",
                    "file_type": "implementation",
                    "relevance": 0.95,
                    "node_type": "EFFECT",
                    "size_bytes": 5432,
                },
                {
                    "path": "services/intelligence/src/models/pattern_models.py",
                    "file_type": "model",
                    "relevance": 0.85,
                    "node_type": None,
                    "size_bytes": 2341,
                },
            ],
            "metadata": {
                "total_files": 2,
                "node_types": ["EFFECT"],
                "pattern_locations": ["services/intelligence/src/pattern_learning"],
                "tree_depth": 3,
                "last_indexed": "2025-11-03T10:00:00Z",
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock the async context manager
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock the response - use MagicMock for synchronous methods
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.get.return_value = mock_response

            # Execute search
            tree_info = await client.search_pattern_files(
                pattern_name="pattern_learning",
                pattern_type="onex",
                node_type="EFFECT",
                correlation_id=uuid4(),
            )

            # Verify results
            assert len(tree_info.relevant_files) == 2
            assert tree_info.relevant_files[0].path.endswith(
                "node_pattern_query_effect.py"
            )
            assert tree_info.relevant_files[0].relevance == 0.95
            assert tree_info.relevant_files[0].node_type == "EFFECT"
            assert tree_info.tree_metadata.total_files == 2
            assert tree_info.tree_metadata.tree_depth == 3
            assert tree_info.from_cache is False
            assert tree_info.query_time_ms > 0

    @pytest.mark.asyncio
    async def test_pattern_not_found_handling(self):
        """Test handling when pattern is not found in OnexTree"""
        client = OnexTreeClient()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 404 response - use MagicMock for synchronous methods
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.get.return_value = mock_response

            # Execute search
            tree_info = await client.search_pattern_files(
                pattern_name="nonexistent_pattern",
                pattern_type="onex",
            )

            # Should return empty results, not raise error
            assert len(tree_info.relevant_files) == 0
            assert tree_info.tree_metadata.total_files == 0

    @pytest.mark.asyncio
    async def test_service_timeout_handling(self):
        """Test handling of OnexTree service timeouts"""
        client = OnexTreeClient(max_retries=1)  # Only 1 retry for faster test

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock timeout exception
            import httpx

            mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

            # Execute search - should return empty results after retries
            tree_info = await client.search_pattern_files(
                pattern_name="pattern1",
                pattern_type="onex",
            )

            # Should return empty results on error
            assert len(tree_info.relevant_files) == 0
            assert tree_info.tree_metadata.total_files == 0

    @pytest.mark.asyncio
    async def test_response_parsing(self):
        """Test parsing of OnexTree API response"""
        client = OnexTreeClient()

        response_data = {
            "files": [
                {
                    "path": "test/path.py",
                    "file_type": "model",
                    "relevance": 0.8,
                }
            ],
            "metadata": {
                "total_files": 1,
                "node_types": ["EFFECT"],
                "pattern_locations": ["test"],
            },
        }

        tree_info = client._parse_onextree_response(response_data)

        assert len(tree_info.relevant_files) == 1
        assert tree_info.relevant_files[0].path == "test/path.py"
        assert tree_info.tree_metadata.total_files == 1
        assert tree_info.tree_metadata.node_types == ["EFFECT"]


@pytest.mark.asyncio
async def test_get_tree_info_for_pattern_with_caching():
    """Test the main public API with caching"""
    # Clear cache first
    clear_tree_cache()

    mock_response_data = {
        "files": [
            {
                "path": "test.py",
                "file_type": "model",
                "relevance": 0.9,
            }
        ],
        "metadata": {
            "total_files": 1,
            "node_types": [],
            "pattern_locations": [],
        },
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock the response - use MagicMock for synchronous methods
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response

        # First call - should hit OnexTree service
        tree_info1 = await get_tree_info_for_pattern(
            pattern_name="test_pattern",
            pattern_type="onex",
        )

        assert tree_info1.from_cache is False
        assert len(tree_info1.relevant_files) == 1

        # Second call - should hit cache
        tree_info2 = await get_tree_info_for_pattern(
            pattern_name="test_pattern",
            pattern_type="onex",
        )

        assert tree_info2.from_cache is True
        assert len(tree_info2.relevant_files) == 1

        # Verify cache metrics
        metrics = get_tree_cache_metrics()
        assert metrics["total_requests"] == 2  # One miss + one hit
        assert metrics["hits"] == 1
        assert metrics["misses"] == 1
        assert metrics["hit_rate"] == 0.5  # 1 hit out of 2 requests


def test_cache_metrics_api():
    """Test cache metrics API"""
    clear_tree_cache()

    metrics = get_tree_cache_metrics()

    assert "hits" in metrics
    assert "misses" in metrics
    assert "total_requests" in metrics
    assert "cache_size" in metrics
    assert "hit_rate" in metrics
    assert "utilization" in metrics


def test_clear_cache_api():
    """Test cache clear API"""
    clear_tree_cache()

    metrics = get_tree_cache_metrics()
    assert metrics["cache_size"] == 0
    assert metrics["total_requests"] == 0


# Performance benchmarks
@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_cache_performance():
    """Benchmark: Cache hit should be <1ms"""
    import time

    cache = TreeInfoCache()
    tree_info = TreeInfo(
        relevant_files=[RelevantFile(path="test.py", file_type="model", relevance=0.9)],
        tree_metadata=TreeMetadata(total_files=1),
    )

    cache.set("pattern1", "onex", tree_info)

    # Warm up
    for _ in range(10):
        cache.get("pattern1", "onex")

    # Benchmark
    iterations = 1000
    start = time.perf_counter()

    for _ in range(iterations):
        cache.get("pattern1", "onex")

    end = time.perf_counter()
    avg_time_ms = ((end - start) / iterations) * 1000

    print(f"\nCache hit average time: {avg_time_ms:.4f}ms")
    assert avg_time_ms < 1.0, f"Cache hit took {avg_time_ms:.4f}ms (target: <1ms)"
