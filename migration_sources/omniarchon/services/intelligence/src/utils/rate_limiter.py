"""
Rate Limiter for Embedding Requests

Semaphore-based rate limiting to prevent queue buildup at vLLM service during bulk operations.
Throttles concurrent embedding requests to maintain ~200ms latency instead of 15-30s queue waits.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingRateLimiter:
    """
    Semaphore-based rate limiter for embedding requests.

    Prevents queue buildup at vLLM service by limiting concurrent requests.
    During bulk ingestion, unthrottled requests can queue up:
      - vLLM base latency: ~91ms per request
      - With queue: 91ms + 15-30s queue wait = timeout

    With rate limiting:
      - Max concurrent requests controlled (default: 3)
      - Expected latency: ~200ms (base + minimal queue)
      - No timeout errors

    Usage:
        rate_limiter = EmbeddingRateLimiter(max_concurrent=3)

        async with rate_limiter:
            embedding = await generate_embedding(text)

    Configuration:
        max_concurrent: Maximum concurrent embedding requests
                       - Default: 3 (conservative)
                       - Can increase to 5-10 based on vLLM capacity
                       - Formula: N consumers × max_concurrent = total concurrent
    """

    def __init__(self, max_concurrent: int = 3):
        """
        Initialize rate limiter with maximum concurrent requests.

        Args:
            max_concurrent: Maximum number of concurrent embedding requests.
                          Default is 3 (conservative for stability).
                          Can be increased to 5-10 based on vLLM service capacity.
        """
        if max_concurrent < 1:
            logger.warning(f"Invalid max_concurrent={max_concurrent}, using default=3")
            max_concurrent = 3

        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

        logger.info(
            f"✅ EmbeddingRateLimiter initialized: max_concurrent={max_concurrent}"
        )

    async def acquire(self):
        """Acquire semaphore slot (blocks if at max concurrent)."""
        await self.semaphore.acquire()

    def release(self):
        """Release semaphore slot."""
        self.semaphore.release()

    async def __aenter__(self):
        """Context manager entry - acquire slot."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release slot."""
        self.release()
        return False  # Don't suppress exceptions

    def get_available_slots(self) -> int:
        """
        Get number of available semaphore slots.

        Returns:
            Number of slots available (0 = at max concurrent)
        """
        # Semaphore._value is the number of available permits
        return self.semaphore._value

    def is_at_capacity(self) -> bool:
        """
        Check if rate limiter is at capacity.

        Returns:
            True if all slots are in use, False otherwise
        """
        return self.get_available_slots() == 0

    def __repr__(self) -> str:
        """String representation for debugging."""
        available = self.get_available_slots()
        in_use = self.max_concurrent - available
        return (
            f"EmbeddingRateLimiter(max={self.max_concurrent}, "
            f"in_use={in_use}, available={available})"
        )
