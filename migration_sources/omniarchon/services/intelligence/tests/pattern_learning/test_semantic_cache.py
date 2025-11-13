"""
Comprehensive Test Suite for Semantic Cache Reducer

Tests cover:
- Cache key generation
- Cache hits and misses
- TTL expiration
- LRU eviction
- Metrics tracking
- Redis backend integration
- Cache warming
- Edge cases
"""

import asyncio
import hashlib
import time
from uuid import uuid4

import pytest
from archon_services.pattern_learning.phase2_matching.reducer_semantic_cache import (
    CacheEntry,
    CacheMetrics,
    SemanticAnalysisResult,
    SemanticCacheReducer,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def cache_reducer():
    """Create a fresh cache reducer for testing."""
    return SemanticCacheReducer(max_size=10, default_ttl=3600)


@pytest.fixture
def sample_result():
    """Create a sample semantic analysis result."""
    return SemanticAnalysisResult(
        pattern_id=uuid4(),
        content_hash="a" * 64,
        keywords=["test", "sample", "fixture"],
        intent="testing",
        confidence=0.95,
        execution_patterns={"test_pattern": "value"},
        metadata={"source": "test_fixture"},
    )


@pytest.fixture
def sample_content():
    """Sample content for cache testing."""
    return "This is a sample task description for testing semantic caching."


# ============================================================================
# Cache Key Generation Tests
# ============================================================================


def test_cache_key_generation(cache_reducer: SemanticCacheReducer):
    """Test SHA256 cache key generation."""
    content = "test content"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    cache_key = cache_reducer.get_cache_key(content)

    assert cache_key == expected_hash
    assert len(cache_key) == 64
    assert all(c in "0123456789abcdef" for c in cache_key)


def test_cache_key_uniqueness(cache_reducer: SemanticCacheReducer):
    """Test that different content produces different keys."""
    content1 = "first content"
    content2 = "second content"

    key1 = cache_reducer.get_cache_key(content1)
    key2 = cache_reducer.get_cache_key(content2)

    assert key1 != key2


def test_cache_key_consistency(cache_reducer: SemanticCacheReducer):
    """Test that same content produces same key."""
    content = "consistent content"

    key1 = cache_reducer.get_cache_key(content)
    key2 = cache_reducer.get_cache_key(content)

    assert key1 == key2


# ============================================================================
# Cache Hit/Miss Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cache_miss(cache_reducer: SemanticCacheReducer, sample_content: str):
    """Test cache miss on empty cache."""
    result = await cache_reducer.get(sample_content)

    assert result is None
    assert cache_reducer.metrics.misses == 1
    assert cache_reducer.metrics.hits == 0
    assert cache_reducer.metrics.total_requests == 1


@pytest.mark.asyncio
async def test_cache_hit(
    cache_reducer: SemanticCacheReducer,
    sample_content: str,
    sample_result: SemanticAnalysisResult,
):
    """Test cache hit after storing entry."""
    # Store result
    await cache_reducer.set(sample_content, sample_result)

    # Retrieve result
    cached_result = await cache_reducer.get(sample_content)

    assert cached_result is not None
    assert cached_result.pattern_id == sample_result.pattern_id
    assert cached_result.keywords == sample_result.keywords
    assert cache_reducer.metrics.hits == 1
    assert cache_reducer.metrics.misses == 0


@pytest.mark.asyncio
async def test_multiple_cache_operations(cache_reducer: SemanticCacheReducer):
    """Test multiple cache hits and misses."""
    contents = ["content one", "content two", "content three"]

    # Store entries
    for i, content in enumerate(contents):
        result = SemanticAnalysisResult(
            content_hash=cache_reducer.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        await cache_reducer.set(content, result)

    # Test hits
    for content in contents:
        cached = await cache_reducer.get(content)
        assert cached is not None

    # Test miss
    miss_result = await cache_reducer.get("non-existent content")
    assert miss_result is None

    # Verify metrics
    assert cache_reducer.metrics.hits == 3
    assert cache_reducer.metrics.misses == 1
    assert cache_reducer.metrics.total_requests == 4
    assert cache_reducer.metrics.hit_rate == 0.75


# ============================================================================
# TTL Expiration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cache_expiration(
    cache_reducer: SemanticCacheReducer,
    sample_content: str,
    sample_result: SemanticAnalysisResult,
):
    """Test that expired entries are not returned."""
    # Create cache with short TTL
    short_ttl_cache = SemanticCacheReducer(max_size=10, default_ttl=1)

    # Store entry
    await short_ttl_cache.set(sample_content, sample_result)

    # Verify it's cached
    cached = await short_ttl_cache.get(sample_content)
    assert cached is not None

    # Wait for expiration
    await asyncio.sleep(1.1)

    # Verify it's expired
    expired_result = await short_ttl_cache.get(sample_content)
    assert expired_result is None
    assert short_ttl_cache.metrics.misses == 1  # Expired = miss


@pytest.mark.asyncio
async def test_custom_ttl(cache_reducer: SemanticCacheReducer):
    """Test custom TTL per entry."""
    content = "custom ttl content"
    result = SemanticAnalysisResult(
        content_hash=cache_reducer.get_cache_key(content),
        keywords=["custom"],
        intent="testing",
        confidence=0.8,
    )

    # Store with custom 2-second TTL
    await cache_reducer.set(content, result, ttl=2)

    # Verify entry exists
    entry_key = cache_reducer.get_cache_key(content)
    assert entry_key in cache_reducer._cache
    assert cache_reducer._cache[entry_key].ttl_seconds == 2


def test_entry_is_expired():
    """Test CacheEntry expiration checking."""
    current_time = time.time()

    # Fresh entry
    fresh_entry = CacheEntry(
        result=SemanticAnalysisResult(
            content_hash="test", keywords=[], intent="test", confidence=0.5
        ),
        created_at=current_time,
        last_accessed=current_time,
        ttl_seconds=3600,
    )
    assert not fresh_entry.is_expired(current_time)

    # Expired entry
    expired_entry = CacheEntry(
        result=SemanticAnalysisResult(
            content_hash="test", keywords=[], intent="test", confidence=0.5
        ),
        created_at=current_time - 7200,  # 2 hours ago
        last_accessed=current_time,
        ttl_seconds=3600,  # 1 hour TTL
    )
    assert expired_entry.is_expired(current_time)


# ============================================================================
# LRU Eviction Tests
# ============================================================================


@pytest.mark.asyncio
async def test_lru_eviction(cache_reducer: SemanticCacheReducer):
    """Test LRU eviction when max_size reached."""
    # Fill cache to max_size (10)
    for i in range(10):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache_reducer.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        await cache_reducer.set(content, result)

    # Verify cache is full
    assert len(cache_reducer._cache) == 10

    # Add one more entry - should evict LRU
    new_content = "content_new"
    new_result = SemanticAnalysisResult(
        content_hash=cache_reducer.get_cache_key(new_content),
        keywords=["new"],
        intent="new",
        confidence=0.95,
    )
    await cache_reducer.set(new_content, new_result)

    # Verify cache size maintained
    assert len(cache_reducer._cache) == 10

    # Verify oldest entry evicted (content_0)
    oldest_cached = await cache_reducer.get("content_0")
    assert oldest_cached is None

    # Verify newest entry exists
    newest_cached = await cache_reducer.get(new_content)
    assert newest_cached is not None

    # Verify eviction metric
    assert cache_reducer.metrics.evictions >= 1


@pytest.mark.asyncio
async def test_lru_ordering(cache_reducer: SemanticCacheReducer):
    """Test that accessing entries updates LRU order."""
    # Add 5 entries
    for i in range(5):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache_reducer.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        await cache_reducer.set(content, result)

    # Access content_0 to move it to end of LRU
    await cache_reducer.get("content_0")

    # Fill cache to trigger eviction
    for i in range(5, 11):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache_reducer.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        await cache_reducer.set(content, result)

    # content_0 should still exist (was accessed)
    assert await cache_reducer.get("content_0") is not None

    # content_1 should be evicted (was LRU)
    assert await cache_reducer.get("content_1") is None


# ============================================================================
# Metrics Tracking Tests
# ============================================================================


def test_cache_metrics_initialization():
    """Test CacheMetrics initialization."""
    metrics = CacheMetrics()

    assert metrics.hits == 0
    assert metrics.misses == 0
    assert metrics.evictions == 0
    assert metrics.total_requests == 0
    assert metrics.hit_rate == 0.0


def test_cache_metrics_hit_rate():
    """Test hit rate calculation."""
    metrics = CacheMetrics(hits=80, misses=20, total_requests=100)

    assert metrics.hit_rate == 0.8


def test_cache_metrics_to_dict():
    """Test metrics export to dictionary."""
    metrics = CacheMetrics(hits=10, misses=5, evictions=2, total_requests=15)

    metrics_dict = metrics.to_dict()

    assert metrics_dict["hits"] == 10
    assert metrics_dict["misses"] == 5
    assert metrics_dict["evictions"] == 2
    assert metrics_dict["total_requests"] == 15
    assert metrics_dict["hit_rate"] == pytest.approx(0.6667, rel=0.01)


@pytest.mark.asyncio
async def test_get_metrics(cache_reducer: SemanticCacheReducer):
    """Test cache metrics retrieval."""
    # Perform some operations
    content = "test content"
    result = SemanticAnalysisResult(
        content_hash=cache_reducer.get_cache_key(content),
        keywords=["test"],
        intent="testing",
        confidence=0.9,
    )

    await cache_reducer.set(content, result)
    await cache_reducer.get(content)  # Hit
    await cache_reducer.get("non-existent")  # Miss

    metrics = cache_reducer.get_metrics()

    assert metrics["hits"] == 1
    assert metrics["misses"] == 1
    assert metrics["total_requests"] == 2
    assert metrics["hit_rate"] == 0.5
    assert metrics["cache_size"] == 1
    assert metrics["max_size"] == 10
    assert metrics["utilization"] == 0.1


# ============================================================================
# Cache Entry Tests
# ============================================================================


def test_cache_entry_touch():
    """Test CacheEntry touch functionality."""
    entry = CacheEntry(
        result=SemanticAnalysisResult(
            content_hash="test", keywords=[], intent="test", confidence=0.5
        ),
        created_at=time.time(),
        last_accessed=time.time(),
    )

    initial_access_count = entry.access_count
    initial_last_accessed = entry.last_accessed

    # Wait a bit
    time.sleep(0.1)

    # Touch entry
    entry.touch()

    assert entry.access_count == initial_access_count + 1
    assert entry.last_accessed > initial_last_accessed


# ============================================================================
# Cache Management Tests
# ============================================================================


@pytest.mark.asyncio
async def test_clear_cache(cache_reducer: SemanticCacheReducer):
    """Test cache clearing."""
    # Add some entries
    for i in range(5):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache_reducer.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        await cache_reducer.set(content, result)

    # Verify entries exist
    assert len(cache_reducer._cache) == 5

    # Clear cache
    cache_reducer.clear()

    # Verify cache is empty
    assert len(cache_reducer._cache) == 0
    assert cache_reducer.metrics.hits == 0
    assert cache_reducer.metrics.misses == 0


@pytest.mark.asyncio
async def test_evict_expired_entries(cache_reducer: SemanticCacheReducer):
    """Test manual eviction of expired entries."""
    # Create cache with short TTL
    short_ttl_cache = SemanticCacheReducer(max_size=10, default_ttl=1)

    # Add entries
    for i in range(5):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=short_ttl_cache.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        await short_ttl_cache.set(content, result)

    # Wait for expiration
    await asyncio.sleep(1.1)

    # Manually evict expired
    evicted_count = short_ttl_cache.evict_expired()

    assert evicted_count == 5
    assert len(short_ttl_cache._cache) == 0


@pytest.mark.asyncio
async def test_cache_warming():
    """Test cache warming functionality."""
    cache = SemanticCacheReducer(max_size=100, default_ttl=3600)

    # Sample content to warm
    content_samples = ["sample task 1", "sample task 2", "sample task 3"]

    # Mock analysis function
    async def mock_analysis(content: str) -> SemanticAnalysisResult:
        return SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=content.split(),
            intent="testing",
            confidence=0.9,
        )

    # Warm cache
    warmed_count = await cache.warm_cache(content_samples, mock_analysis)

    assert warmed_count == 3
    assert len(cache._cache) == 3

    # Verify entries are cached
    for content in content_samples:
        cached = await cache.get(content)
        assert cached is not None


@pytest.mark.asyncio
async def test_cache_warming_skip_existing():
    """Test that cache warming skips existing entries."""
    cache = SemanticCacheReducer(max_size=100, default_ttl=3600)

    content = "existing content"
    result = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["existing"],
        intent="test",
        confidence=0.9,
    )

    # Add entry manually
    await cache.set(content, result)

    # Try to warm with same content
    async def mock_analysis(content: str) -> SemanticAnalysisResult:
        raise ValueError("Should not be called for existing entries")

    warmed_count = await cache.warm_cache([content], mock_analysis)

    assert warmed_count == 0  # Should skip existing


# ============================================================================
# ONEX Reducer Interface Tests
# ============================================================================


@pytest.mark.asyncio
async def test_execute_reduction_get(
    cache_reducer: SemanticCacheReducer,
    sample_content: str,
    sample_result: SemanticAnalysisResult,
):
    """Test ONEX reducer get operation."""
    # Store entry
    await cache_reducer.set(sample_content, sample_result)

    # Execute get operation
    result = await cache_reducer.execute_reduction("get", {"content": sample_content})

    assert result["success"] is True
    assert result["cache_hit"] is True
    assert result["result"] is not None


@pytest.mark.asyncio
async def test_execute_reduction_set(cache_reducer: SemanticCacheReducer):
    """Test ONEX reducer set operation."""
    content = "test content"
    result_data = {
        "content_hash": cache_reducer.get_cache_key(content),
        "keywords": ["test"],
        "intent": "testing",
        "confidence": 0.9,
    }

    # Execute set operation
    result = await cache_reducer.execute_reduction(
        "set", {"content": content, "result": result_data}
    )

    assert result["success"] is True

    # Verify entry was stored
    cached = await cache_reducer.get(content)
    assert cached is not None


@pytest.mark.asyncio
async def test_execute_reduction_metrics(cache_reducer: SemanticCacheReducer):
    """Test ONEX reducer metrics operation."""
    result = await cache_reducer.execute_reduction("metrics", {})

    assert result["success"] is True
    assert "metrics" in result
    assert "hits" in result["metrics"]
    assert "misses" in result["metrics"]


@pytest.mark.asyncio
async def test_execute_reduction_clear(cache_reducer: SemanticCacheReducer):
    """Test ONEX reducer clear operation."""
    # Add some entries
    content = "test content"
    result_obj = SemanticAnalysisResult(
        content_hash=cache_reducer.get_cache_key(content),
        keywords=["test"],
        intent="testing",
        confidence=0.9,
    )
    await cache_reducer.set(content, result_obj)

    # Execute clear
    result = await cache_reducer.execute_reduction("clear", {})

    assert result["success"] is True
    assert len(cache_reducer._cache) == 0


@pytest.mark.asyncio
async def test_execute_reduction_unknown_operation(cache_reducer: SemanticCacheReducer):
    """Test ONEX reducer with unknown operation."""
    result = await cache_reducer.execute_reduction("unknown_op", {})

    assert result["success"] is False
    assert "error" in result


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_empty_content(cache_reducer: SemanticCacheReducer):
    """Test handling of empty content."""
    result = SemanticAnalysisResult(
        content_hash=cache_reducer.get_cache_key(""),
        keywords=[],
        intent="empty",
        confidence=0.0,
    )

    await cache_reducer.set("", result)
    cached = await cache_reducer.get("")

    assert cached is not None


@pytest.mark.asyncio
async def test_very_large_content(cache_reducer: SemanticCacheReducer):
    """Test handling of very large content."""
    large_content = "x" * 10000  # 10KB content

    result = SemanticAnalysisResult(
        content_hash=cache_reducer.get_cache_key(large_content),
        keywords=["large"],
        intent="testing",
        confidence=0.9,
    )

    await cache_reducer.set(large_content, result)
    cached = await cache_reducer.get(large_content)

    assert cached is not None


def test_semantic_analysis_result_serialization(sample_result: SemanticAnalysisResult):
    """Test SemanticAnalysisResult JSON serialization."""
    result_dict = sample_result.model_dump()

    assert "pattern_id" in result_dict
    assert "content_hash" in result_dict
    assert "keywords" in result_dict
    assert "confidence" in result_dict


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cache_performance():
    """Test cache performance meets <1ms target for cached results."""
    cache = SemanticCacheReducer(max_size=1000, default_ttl=3600)

    content = "performance test content"
    result = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["performance"],
        intent="testing",
        confidence=0.95,
    )

    # Store entry
    await cache.set(content, result)

    # Measure retrieval time
    start_time = time.perf_counter()
    for _ in range(100):
        await cache.get(content)
    end_time = time.perf_counter()

    avg_time_ms = ((end_time - start_time) / 100) * 1000

    # Should be well under 1ms for cached results
    assert avg_time_ms < 1.0, f"Cache retrieval too slow: {avg_time_ms:.3f}ms"


@pytest.mark.asyncio
async def test_high_throughput():
    """Test cache handles high throughput scenarios."""
    cache = SemanticCacheReducer(max_size=1000, default_ttl=3600)

    # Create many unique entries
    tasks = []
    for i in range(100):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[f"keyword_{i}"],
            intent=f"intent_{i}",
            confidence=0.9,
        )
        tasks.append(cache.set(content, result))

    # Execute concurrently
    await asyncio.gather(*tasks)

    # Verify all entries stored
    assert len(cache._cache) == 100


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=reducer_semantic_cache", "--cov-report=term-missing"]
    )
