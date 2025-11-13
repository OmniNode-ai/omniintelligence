#!/usr/bin/env python3
"""
Standalone test for tree integration

Tests the tree info retrieval, caching, and error handling without full service dependencies.
Run with: python3 test_tree_integration_standalone.py
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add src to path for imports and import directly from module file
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import directly from the tree_integration module file to avoid __init__.py imports
import importlib.util

spec = importlib.util.spec_from_file_location(
    "tree_integration",
    Path(__file__).parent / "src" / "api" / "pattern_learning" / "tree_integration.py",
)
tree_integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tree_integration)

# Extract what we need
OnexTreeClient = tree_integration.OnexTreeClient
TreeInfo = tree_integration.TreeInfo
TreeInfoCache = tree_integration.TreeInfoCache
TreeMetadata = tree_integration.TreeMetadata
RelevantFile = tree_integration.RelevantFile
get_tree_cache_metrics = tree_integration.get_tree_cache_metrics
clear_tree_cache = tree_integration.clear_tree_cache


def test_cache_initialization():
    """Test cache initializes with correct parameters"""
    print("Testing cache initialization...")
    cache = TreeInfoCache(max_size=100, ttl_seconds=600)

    assert cache.max_size == 100, "Cache max_size incorrect"
    assert cache.ttl_seconds == 600, "Cache ttl_seconds incorrect"
    assert len(cache._cache) == 0, "Cache should be empty on init"
    assert cache.metrics.total_requests == 0, "Metrics should be zero"
    print("✅ Cache initialization test passed")


def test_cache_key_generation():
    """Test cache key generation from pattern parameters"""
    print("\nTesting cache key generation...")
    cache = TreeInfoCache()

    key1 = cache._get_cache_key("pattern1", "onex", "EFFECT")
    key2 = cache._get_cache_key("pattern1", "onex", "EFFECT")
    key3 = cache._get_cache_key("pattern2", "onex", "EFFECT")

    # Same parameters = same key
    assert key1 == key2, "Same params should generate same key"

    # Different parameters = different key
    assert key1 != key3, "Different params should generate different key"

    # Keys should be 16 characters (truncated SHA256)
    assert len(key1) == 16, f"Key length should be 16, got {len(key1)}"
    print("✅ Cache key generation test passed")


def test_cache_miss():
    """Test cache miss behavior"""
    print("\nTesting cache miss...")
    cache = TreeInfoCache()

    result = cache.get("pattern1", "onex", "EFFECT")

    assert result is None, "Should return None on cache miss"
    assert cache.metrics.misses == 1, "Should increment miss counter"
    assert cache.metrics.hits == 0, "Hits should be zero"
    assert cache.metrics.total_requests == 1, "Total requests should be 1"
    print("✅ Cache miss test passed")


def test_cache_hit():
    """Test cache hit behavior"""
    print("\nTesting cache hit...")
    cache = TreeInfoCache()

    tree_info = TreeInfo(
        relevant_files=[RelevantFile(path="test.py", file_type="model", relevance=0.9)],
        tree_metadata=TreeMetadata(total_files=1),
    )

    # Store in cache
    cache.set("pattern1", "onex", tree_info, "EFFECT")

    # Retrieve from cache
    result = cache.get("pattern1", "onex", "EFFECT")

    assert result is not None, "Should return cached value"
    assert result.from_cache is True, "Should mark as from_cache"
    assert len(result.relevant_files) == 1, "Should have 1 file"
    assert cache.metrics.hits == 1, "Should increment hit counter"
    assert cache.metrics.misses == 0, "Misses should be zero"
    print("✅ Cache hit test passed")


def test_lru_eviction():
    """Test LRU eviction when cache is full"""
    print("\nTesting LRU eviction...")
    cache = TreeInfoCache(max_size=2)

    tree_info = TreeInfo(
        relevant_files=[],
        tree_metadata=TreeMetadata(total_files=0),
    )

    # Fill cache to max size
    cache.set("pattern1", "onex", tree_info)
    cache.set("pattern2", "onex", tree_info)

    assert len(cache._cache) == 2, "Cache should be at max size"

    # Add one more - should evict LRU (pattern1)
    cache.set("pattern3", "onex", tree_info)

    assert len(cache._cache) == 2, "Cache should still be at max size"
    assert cache.metrics.evictions == 1, "Should have 1 eviction"

    # pattern1 should be evicted
    result1 = cache.get("pattern1", "onex")
    assert result1 is None, "pattern1 should be evicted"

    # pattern2 and pattern3 should still be cached
    result2 = cache.get("pattern2", "onex")
    result3 = cache.get("pattern3", "onex")
    assert result2 is not None, "pattern2 should still be cached"
    assert result3 is not None, "pattern3 should still be cached"
    print("✅ LRU eviction test passed")


def test_cache_clear():
    """Test cache clear operation"""
    print("\nTesting cache clear...")
    cache = TreeInfoCache()

    tree_info = TreeInfo(
        relevant_files=[],
        tree_metadata=TreeMetadata(total_files=0),
    )

    cache.set("pattern1", "onex", tree_info)
    cache.set("pattern2", "onex", tree_info)

    assert len(cache._cache) == 2, "Should have 2 entries"

    # Clear cache
    cache.clear()

    assert len(cache._cache) == 0, "Cache should be empty after clear"
    assert cache.metrics.total_requests == 0, "Metrics should be reset"
    assert cache.metrics.hits == 0, "Hits should be reset"
    print("✅ Cache clear test passed")


def test_cache_metrics():
    """Test cache metrics reporting"""
    print("\nTesting cache metrics...")
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

    assert metrics["cache_size"] == 2, "Should have 2 entries"
    assert metrics["max_size"] == 100, "Max size should be 100"
    assert metrics["hits"] == 1, "Should have 1 hit"
    assert metrics["misses"] == 1, "Should have 1 miss"
    assert metrics["total_requests"] == 2, "Should have 2 total requests"
    assert metrics["hit_rate"] == 0.5, "Hit rate should be 50%"
    assert metrics["utilization"] == 0.02, "Utilization should be 2% (2/100)"
    print("✅ Cache metrics test passed")


async def test_onextree_client_initialization():
    """Test client initializes with correct base URL"""
    print("\nTesting OnexTree client initialization...")
    client = OnexTreeClient(
        base_url="http://test-server:8058",
        timeout=5.0,
        max_retries=3,
    )

    assert client.base_url == "http://test-server:8058", "Base URL incorrect"
    assert client.timeout == 5.0, "Timeout incorrect"
    assert client.max_retries == 3, "Max retries incorrect"
    print("✅ OnexTree client initialization test passed")


async def test_successful_tree_info_retrieval():
    """Test successful tree info retrieval from OnexTree service"""
    print("\nTesting successful tree info retrieval...")
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

        # Mock the response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        # json() is a regular method, not async
        mock_response.json = lambda: mock_response_data
        mock_client.get = AsyncMock(return_value=mock_response)

        # Execute search
        tree_info = await client.search_pattern_files(
            pattern_name="pattern_learning",
            pattern_type="onex",
            node_type="EFFECT",
        )

        # Verify results
        assert len(tree_info.relevant_files) == 2, "Should have 2 files"
        assert tree_info.relevant_files[0].path.endswith(
            "node_pattern_query_effect.py"
        ), "First file path incorrect"
        assert (
            tree_info.relevant_files[0].relevance == 0.95
        ), "Relevance score incorrect"
        assert tree_info.relevant_files[0].node_type == "EFFECT", "Node type incorrect"
        assert tree_info.tree_metadata.total_files == 2, "Total files incorrect"
        assert tree_info.tree_metadata.tree_depth == 3, "Tree depth incorrect"
        assert tree_info.from_cache is False, "Should not be from cache"
        assert tree_info.query_time_ms > 0, "Query time should be > 0"
        print("✅ Successful tree info retrieval test passed")


async def test_pattern_not_found_handling():
    """Test handling when pattern is not found in OnexTree"""
    print("\nTesting pattern not found handling...")
    client = OnexTreeClient()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock 404 response
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_response)

        # Execute search
        tree_info = await client.search_pattern_files(
            pattern_name="nonexistent_pattern",
            pattern_type="onex",
        )

        # Should return empty results, not raise error
        assert len(tree_info.relevant_files) == 0, "Should have no files for 404"
        assert tree_info.tree_metadata.total_files == 0, "Total files should be 0"
        print("✅ Pattern not found handling test passed")


def test_cache_performance():
    """Benchmark: Cache hit should be <1ms"""
    print("\nTesting cache performance...")
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

    print(f"  Cache hit average time: {avg_time_ms:.4f}ms")
    assert avg_time_ms < 1.0, f"Cache hit took {avg_time_ms:.4f}ms (target: <1ms)"
    print("✅ Cache performance test passed")


async def run_async_tests():
    """Run all async tests"""
    await test_onextree_client_initialization()
    await test_successful_tree_info_retrieval()
    await test_pattern_not_found_handling()


def main():
    """Run all tests"""
    print("=" * 60)
    print("Tree Integration Standalone Tests")
    print("=" * 60)

    # Run sync tests
    test_cache_initialization()
    test_cache_key_generation()
    test_cache_miss()
    test_cache_hit()
    test_lru_eviction()
    test_cache_clear()
    test_cache_metrics()
    test_cache_performance()

    # Run async tests
    asyncio.run(run_async_tests())

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
