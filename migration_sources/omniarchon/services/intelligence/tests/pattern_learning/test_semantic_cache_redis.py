"""
Additional Tests for Redis Backend and Edge Cases

Tests to achieve >90% coverage:
- Redis backend integration
- Redis error handling
- Content hash auto-population
- Additional edge cases
"""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from archon_services.pattern_learning.phase2_matching.reducer_semantic_cache import (
    CacheMetrics,
    SemanticAnalysisResult,
    SemanticCacheReducer,
)

# ============================================================================
# Redis Backend Tests
# ============================================================================


@pytest.mark.asyncio
async def test_redis_enabled_initialization():
    """Test cache initialization with Redis enabled."""
    mock_redis = AsyncMock()
    cache = SemanticCacheReducer(
        max_size=100, default_ttl=3600, redis_client=mock_redis, redis_enabled=True
    )

    assert cache.redis_enabled is True
    assert cache.redis_client is mock_redis


@pytest.mark.asyncio
async def test_redis_disabled_with_client():
    """Test that Redis is disabled even when client provided but flag is False."""
    mock_redis = AsyncMock()
    cache = SemanticCacheReducer(
        max_size=100, default_ttl=3600, redis_client=mock_redis, redis_enabled=False
    )

    assert cache.redis_enabled is False
    assert cache.redis_client is None


@pytest.mark.asyncio
async def test_redis_cache_hit():
    """Test cache hit from Redis backend."""
    import json

    mock_redis = AsyncMock()
    cache = SemanticCacheReducer(
        max_size=100, redis_enabled=True, redis_client=mock_redis
    )

    content = "test content for redis"
    cache_key = cache.get_cache_key(content)

    # Mock Redis response
    result_data = {
        "pattern_id": str(uuid4()),
        "content_hash": cache_key,
        "keywords": ["redis", "test"],
        "intent": "testing",
        "confidence": 0.95,
        "execution_patterns": {},
        "metadata": {},
        "timestamp": "2025-10-02T12:00:00Z",
    }

    mock_redis.get.return_value = json.dumps(result_data)

    # Get from cache (should hit Redis)
    result = await cache.get(content)

    assert result is not None
    assert result.keywords == ["redis", "test"]
    assert cache.metrics.redis_hits == 1
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_redis_cache_miss():
    """Test cache miss from Redis backend."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    cache = SemanticCacheReducer(
        max_size=100, redis_enabled=True, redis_client=mock_redis
    )

    content = "non-existent content"
    result = await cache.get(content)

    assert result is None
    assert cache.metrics.redis_misses == 1


@pytest.mark.asyncio
async def test_redis_set():
    """Test storing entry in Redis backend."""
    mock_redis = AsyncMock()
    cache = SemanticCacheReducer(
        max_size=100, redis_enabled=True, redis_client=mock_redis
    )

    content = "content to store in redis"
    result = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["store", "redis"],
        intent="testing",
        confidence=0.9,
    )

    await cache.set(content, result, ttl=1800)

    # Verify Redis setex was called
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == f"semantic_cache:{cache.get_cache_key(content)}"
    assert call_args[0][1] == 1800  # TTL


@pytest.mark.asyncio
async def test_redis_get_error_handling():
    """Test graceful handling of Redis GET errors."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis connection failed")

    cache = SemanticCacheReducer(
        max_size=100, redis_enabled=True, redis_client=mock_redis
    )

    content = "content with redis error"
    result = await cache.get(content)

    # Should return None and not crash
    assert result is None
    assert cache.metrics.redis_misses == 1


@pytest.mark.asyncio
async def test_redis_set_error_handling():
    """Test graceful handling of Redis SET errors."""
    mock_redis = AsyncMock()
    mock_redis.setex.side_effect = Exception("Redis write failed")

    cache = SemanticCacheReducer(
        max_size=100, redis_enabled=True, redis_client=mock_redis
    )

    content = "content with redis write error"
    result = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["error", "test"],
        intent="testing",
        confidence=0.8,
    )

    # Should not crash, entry still in memory cache
    await cache.set(content, result)

    # Verify in-memory cache has the entry
    cached = await cache.get(content)
    assert cached is not None


# ============================================================================
# Content Hash Auto-Population Tests
# ============================================================================


@pytest.mark.asyncio
async def test_auto_populate_content_hash():
    """Test automatic content hash population when missing."""
    cache = SemanticCacheReducer(max_size=100)

    content = "test content without hash"
    result = SemanticAnalysisResult(
        content_hash="",  # Empty hash
        keywords=["test"],
        intent="testing",
        confidence=0.9,
    )

    await cache.set(content, result)

    # Verify hash was auto-populated
    cached = await cache.get(content)
    assert cached is not None
    assert cached.content_hash == cache.get_cache_key(content)


@pytest.mark.asyncio
async def test_preserve_existing_content_hash():
    """Test that existing content hash is preserved."""
    cache = SemanticCacheReducer(max_size=100)

    content = "test content with hash"
    existing_hash = cache.get_cache_key(content)

    result = SemanticAnalysisResult(
        content_hash=existing_hash, keywords=["test"], intent="testing", confidence=0.9
    )

    await cache.set(content, result)

    cached = await cache.get(content)
    assert cached.content_hash == existing_hash


# ============================================================================
# Cache Warming with Errors
# ============================================================================


@pytest.mark.asyncio
async def test_cache_warming_with_failures():
    """Test cache warming handles individual failures gracefully."""
    cache = SemanticCacheReducer(max_size=100)

    contents = ["content1", "content2", "content3"]
    call_count = 0

    async def mock_analysis_with_failure(content: str) -> SemanticAnalysisResult:
        nonlocal call_count
        call_count += 1

        # Fail on second item
        if content == "content2":
            raise ValueError("Analysis failed")

        return SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[content],
            intent="testing",
            confidence=0.9,
        )

    warmed_count = await cache.warm_cache(contents, mock_analysis_with_failure)

    # Should have warmed 2 out of 3 (skipping the failed one)
    assert warmed_count == 2
    assert call_count == 3  # All were attempted


# ============================================================================
# Execute Reduction Additional Operations
# ============================================================================


@pytest.mark.asyncio
async def test_execute_reduction_evict_expired():
    """Test ONEX reducer evict_expired operation."""
    cache = SemanticCacheReducer(max_size=100, default_ttl=1)

    # Add some entries
    for i in range(3):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[f"key_{i}"],
            intent="test",
            confidence=0.9,
        )
        await cache.set(content, result)

    # Wait for expiration
    await asyncio.sleep(1.1)

    # Execute evict_expired operation
    result = await cache.execute_reduction("evict_expired", {})

    assert result["success"] is True
    assert result["evicted_count"] == 3


@pytest.mark.asyncio
async def test_execute_reduction_warm():
    """Test ONEX reducer warm operation."""
    cache = SemanticCacheReducer(max_size=100)

    async def mock_analysis(content: str) -> SemanticAnalysisResult:
        return SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=content.split(),
            intent="test",
            confidence=0.9,
        )

    result = await cache.execute_reduction(
        "warm",
        {"content_samples": ["sample1", "sample2"], "analysis_function": mock_analysis},
    )

    assert result["success"] is True
    assert result["warmed_count"] == 2


# ============================================================================
# Get Status Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_status():
    """Test get_status returns comprehensive cache information."""
    cache = SemanticCacheReducer(max_size=100)

    # Add some entries with varying access counts
    for i in range(5):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[f"key_{i}"],
            intent="test",
            confidence=0.9,
        )
        await cache.set(content, result)

        # Access some entries multiple times
        for _ in range(i + 1):
            await cache.get(content)

    status = cache.get_status()

    assert status["status"] == "healthy"
    assert "metrics" in status
    assert status["total_access_count"] > 0
    assert status["avg_access_per_entry"] > 0


@pytest.mark.asyncio
async def test_get_status_empty_cache():
    """Test get_status with empty cache."""
    cache = SemanticCacheReducer(max_size=100)

    status = cache.get_status()

    assert status["status"] == "healthy"
    assert status["total_access_count"] == 0
    assert status["avg_access_per_entry"] == 0


# ============================================================================
# Redis Metrics Tests
# ============================================================================


def test_cache_metrics_redis_hit_rate():
    """Test Redis-specific hit rate calculation."""
    metrics = CacheMetrics(redis_hits=80, redis_misses=20)

    assert metrics.redis_hit_rate == 0.8


def test_cache_metrics_redis_no_requests():
    """Test Redis hit rate with no requests."""
    metrics = CacheMetrics()

    assert metrics.redis_hit_rate == 0.0


# ============================================================================
# Additional Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_multiple_sets_same_key():
    """Test multiple sets to same key updates entry."""
    cache = SemanticCacheReducer(max_size=100)

    content = "same content"

    # First set
    result1 = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["first"],
        intent="testing",
        confidence=0.8,
    )
    await cache.set(content, result1)

    # Second set (update)
    result2 = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["second", "updated"],
        intent="testing",
        confidence=0.95,
    )
    await cache.set(content, result2)

    # Should have updated entry
    cached = await cache.get(content)
    assert cached.keywords == ["second", "updated"]
    assert cached.confidence == 0.95


@pytest.mark.asyncio
async def test_concurrent_access():
    """Test concurrent cache access is safe."""
    cache = SemanticCacheReducer(max_size=100)

    content = "concurrent content"
    result = SemanticAnalysisResult(
        content_hash=cache.get_cache_key(content),
        keywords=["concurrent"],
        intent="testing",
        confidence=0.9,
    )
    await cache.set(content, result)

    # Concurrent gets
    tasks = [cache.get(content) for _ in range(50)]
    results = await asyncio.gather(*tasks)

    # All should succeed
    assert all(r is not None for r in results)
    assert cache.metrics.hits == 50


@pytest.mark.asyncio
async def test_eviction_updates_metrics():
    """Test that eviction properly updates metrics."""
    cache = SemanticCacheReducer(max_size=5)

    # Fill cache
    for i in range(5):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[f"key_{i}"],
            intent="test",
            confidence=0.9,
        )
        await cache.set(content, result)

    initial_evictions = cache.metrics.evictions

    # Add more to trigger eviction
    for i in range(5, 10):
        content = f"content_{i}"
        result = SemanticAnalysisResult(
            content_hash=cache.get_cache_key(content),
            keywords=[f"key_{i}"],
            intent="test",
            confidence=0.9,
        )
        await cache.set(content, result)

    # Evictions should have increased
    assert cache.metrics.evictions == initial_evictions + 5
    assert len(cache._cache) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
