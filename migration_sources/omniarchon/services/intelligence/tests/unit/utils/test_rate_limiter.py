"""
Unit tests for EmbeddingRateLimiter

Tests semaphore-based rate limiting to ensure concurrent requests are properly throttled.
"""

import asyncio
import time

import pytest
from utils.rate_limiter import EmbeddingRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_basic():
    """Test basic rate limiter initialization and usage."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=3)

    assert rate_limiter.max_concurrent == 3
    assert rate_limiter.get_available_slots() == 3
    assert not rate_limiter.is_at_capacity()


@pytest.mark.asyncio
async def test_rate_limiter_acquire_release():
    """Test acquire and release operations."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=2)

    # Initial state
    assert rate_limiter.get_available_slots() == 2

    # Acquire first slot
    await rate_limiter.acquire()
    assert rate_limiter.get_available_slots() == 1

    # Acquire second slot
    await rate_limiter.acquire()
    assert rate_limiter.get_available_slots() == 0
    assert rate_limiter.is_at_capacity()

    # Release first slot
    rate_limiter.release()
    assert rate_limiter.get_available_slots() == 1
    assert not rate_limiter.is_at_capacity()

    # Release second slot
    rate_limiter.release()
    assert rate_limiter.get_available_slots() == 2


@pytest.mark.asyncio
async def test_rate_limiter_context_manager():
    """Test rate limiter as async context manager."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=2)

    assert rate_limiter.get_available_slots() == 2

    async with rate_limiter:
        # Inside context, one slot should be used
        assert rate_limiter.get_available_slots() == 1

    # After context, slot should be released
    assert rate_limiter.get_available_slots() == 2


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_operations():
    """Test rate limiter with concurrent operations."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=3)

    concurrent_count = []
    max_concurrent_observed = 0

    async def mock_embedding_call(delay: float):
        """Mock embedding call with rate limiting."""
        nonlocal max_concurrent_observed

        async with rate_limiter:
            # Track concurrent operations
            concurrent_count.append(1)
            current_concurrent = len(concurrent_count)
            max_concurrent_observed = max(max_concurrent_observed, current_concurrent)

            # Simulate embedding generation
            await asyncio.sleep(delay)

            # Remove from tracking
            concurrent_count.pop()

    # Launch 10 concurrent tasks
    tasks = [mock_embedding_call(0.1) for _ in range(10)]
    await asyncio.gather(*tasks)

    # Verify max concurrent never exceeded limit
    assert max_concurrent_observed <= 3


@pytest.mark.asyncio
async def test_rate_limiter_blocking():
    """Test that rate limiter blocks when at capacity."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=1)

    # Acquire the only slot
    await rate_limiter.acquire()
    assert rate_limiter.is_at_capacity()

    # Try to acquire again (should block)
    acquire_completed = False

    async def try_acquire():
        nonlocal acquire_completed
        await rate_limiter.acquire()
        acquire_completed = True
        rate_limiter.release()

    # Start acquire task (will block)
    task = asyncio.create_task(try_acquire())

    # Give it a moment to block
    await asyncio.sleep(0.1)
    assert not acquire_completed  # Should still be blocked

    # Release the slot
    rate_limiter.release()

    # Wait for task to complete
    await asyncio.wait_for(task, timeout=1.0)
    assert acquire_completed  # Should now be completed


@pytest.mark.asyncio
async def test_rate_limiter_invalid_max_concurrent():
    """Test rate limiter with invalid max_concurrent value."""
    # Should default to 3 if invalid value provided
    rate_limiter = EmbeddingRateLimiter(max_concurrent=0)
    assert rate_limiter.max_concurrent == 3

    rate_limiter = EmbeddingRateLimiter(max_concurrent=-5)
    assert rate_limiter.max_concurrent == 3


@pytest.mark.asyncio
async def test_rate_limiter_exception_handling():
    """Test that rate limiter releases slot even when exception occurs."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=2)

    assert rate_limiter.get_available_slots() == 2

    try:
        async with rate_limiter:
            assert rate_limiter.get_available_slots() == 1
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Slot should be released even after exception
    assert rate_limiter.get_available_slots() == 2


@pytest.mark.asyncio
async def test_rate_limiter_performance():
    """Test rate limiter performance with realistic workload."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=3)

    start_time = time.time()

    async def mock_embedding_call():
        """Mock embedding call (~100ms simulated processing)."""
        async with rate_limiter:
            await asyncio.sleep(0.1)  # 100ms simulated processing

    # Launch 9 concurrent tasks (3 batches of 3)
    # With max_concurrent=3, this should take ~300ms (3 batches × 100ms)
    tasks = [mock_embedding_call() for _ in range(9)]
    await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    # Should take approximately 300ms (allow some overhead)
    # With no rate limiting, would take ~100ms (all parallel)
    # With rate limiting (3 concurrent), takes ~300ms (3 batches)
    assert 0.25 < elapsed < 0.5, f"Expected ~300ms, got {elapsed*1000:.0f}ms"


@pytest.mark.asyncio
async def test_rate_limiter_repr():
    """Test rate limiter string representation."""
    rate_limiter = EmbeddingRateLimiter(max_concurrent=5)

    repr_str = repr(rate_limiter)
    assert "EmbeddingRateLimiter" in repr_str
    assert "max=5" in repr_str
    assert "in_use=0" in repr_str
    assert "available=5" in repr_str

    # Acquire slot and check repr updates
    await rate_limiter.acquire()
    repr_str = repr(rate_limiter)
    assert "in_use=1" in repr_str
    assert "available=4" in repr_str

    rate_limiter.release()
