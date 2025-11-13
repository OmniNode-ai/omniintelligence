"""
Semantic Pattern Caching Layer - ONEX Reducer Node

Multi-tier LRU cache with TTL expiration for semantic analysis results.
Provides fast lookup with optional distributed Redis backend.

ONEX Pattern: Reducer (caching/memoization)
Performance Target: <1ms for cached results, >80% hit rate
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    import redis.asyncio

logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================


@dataclass
class CacheMetrics:
    """Cache performance metrics tracking."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_requests: int = 0
    redis_hits: int = 0
    redis_misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        return self.hits / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def redis_hit_rate(self) -> float:
        """Calculate Redis-specific hit rate."""
        redis_total = self.redis_hits + self.redis_misses
        return self.redis_hits / redis_total if redis_total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate,
            "redis_hits": self.redis_hits,
            "redis_misses": self.redis_misses,
            "redis_hit_rate": self.redis_hit_rate,
        }


class SemanticAnalysisResult(BaseModel):
    """Result from semantic pattern analysis (cached value)."""

    pattern_id: UUID = Field(default_factory=uuid4)
    content_hash: str = Field(..., description="SHA256 hash of analyzed content")
    keywords: List[str] = Field(default_factory=list)
    intent: str = Field(default="unknown")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    execution_patterns: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CacheEntry:
    """Individual cache entry with TTL tracking."""

    result: SemanticAnalysisResult
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl_seconds: int = 3600  # 1 hour default

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if entry has exceeded TTL."""
        current = current_time or time.time()
        return (current - self.created_at) > self.ttl_seconds

    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


# ============================================================================
# ONEX Reducer Node Implementation
# ============================================================================


class SemanticCacheReducer:
    """
    Multi-tier LRU cache with TTL for semantic analysis results.

    ONEX Node Type: Reducer (caching/memoization pattern)

    Features:
    - LRU eviction when max_size reached
    - TTL-based expiration (configurable per entry)
    - SHA256-based cache keys
    - Optional Redis backend for distributed caching
    - Comprehensive metrics tracking
    - Cache warming support

    Architecture:
    - Primary: In-memory LRU cache (fast, local)
    - Secondary: Redis backend (optional, distributed)
    - Automatic eviction and expiration management

    Performance:
    - Target: <1ms for cached results
    - Target: >80% hit rate in production
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        redis_client: Optional["redis.asyncio.Redis[bytes]"] = None,
        redis_enabled: bool = False,
    ):
        """
        Initialize semantic cache reducer.

        Args:
            max_size: Maximum number of entries in LRU cache
            default_ttl: Default TTL in seconds (1 hour default)
            redis_client: Optional Redis client for distributed caching
            redis_enabled: Enable Redis backend if client provided
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.redis_client = redis_client if redis_enabled else None
        self.redis_enabled = redis_enabled and redis_client is not None

        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Metrics tracking
        self.metrics = CacheMetrics()

        logger.info(
            f"SemanticCacheReducer initialized: max_size={max_size}, "
            f"ttl={default_ttl}s, redis_enabled={self.redis_enabled}"
        )

    # ========================================================================
    # Core Cache Operations
    # ========================================================================

    def get_cache_key(self, content: str) -> str:
        """
        Generate SHA256 cache key from content.

        Args:
            content: Content to hash

        Returns:
            64-character hex digest
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get(
        self, content: str, correlation_id: Optional[UUID] = None
    ) -> Optional[SemanticAnalysisResult]:
        """
        Retrieve cached semantic analysis result.

        Checks:
        1. In-memory cache (fast path)
        2. Redis cache if enabled (distributed path)
        3. Returns None on miss

        Args:
            content: Content to look up

        Returns:
            Cached result if found and not expired, None otherwise
        """
        cache_key = self.get_cache_key(content)
        self.metrics.total_requests += 1

        # Check in-memory cache first
        if cache_key in self._cache:
            entry = self._cache[cache_key]

            # Check expiration
            if entry.is_expired():
                logger.debug(f"Cache entry expired: {cache_key[:16]}...")
                self._evict_entry(cache_key)
                self.metrics.misses += 1
                return None

            # Cache hit - move to end (LRU)
            self._cache.move_to_end(cache_key)
            entry.touch()
            self.metrics.hits += 1

            logger.debug(
                f"Cache HIT (memory): {cache_key[:16]}... "
                f"(access_count={entry.access_count})"
            )
            return entry.result

        # Check Redis if enabled
        if self.redis_enabled:
            redis_result = await self._get_from_redis(cache_key)
            if redis_result:
                # Populate in-memory cache
                await self._set_in_memory(cache_key, redis_result)
                self.metrics.hits += 1
                self.metrics.redis_hits += 1
                logger.debug(f"Cache HIT (redis): {cache_key[:16]}...")
                return redis_result
            else:
                self.metrics.redis_misses += 1

        # Cache miss
        self.metrics.misses += 1
        logger.debug(f"Cache MISS: {cache_key[:16]}...")
        return None

    async def set(
        self, content: str, result: SemanticAnalysisResult, ttl: Optional[int] = None
    ) -> None:
        """
        Store semantic analysis result in cache.

        Args:
            content: Content that was analyzed
            result: Analysis result to cache
            ttl: Optional custom TTL (uses default if not specified)
        """
        cache_key = self.get_cache_key(content)
        ttl_seconds = ttl or self.default_ttl

        # Ensure result has matching content hash
        if not result.content_hash:
            result.content_hash = cache_key

        # Store in memory
        await self._set_in_memory(cache_key, result, ttl_seconds)

        # Store in Redis if enabled
        if self.redis_enabled:
            await self._set_in_redis(cache_key, result, ttl_seconds)

        logger.debug(
            f"Cache SET: {cache_key[:16]}... (ttl={ttl_seconds}s, "
            f"cache_size={len(self._cache)})"
        )

    async def _set_in_memory(
        self, cache_key: str, result: SemanticAnalysisResult, ttl: Optional[int] = None
    ) -> None:
        """Store entry in in-memory LRU cache."""
        ttl_seconds = ttl or self.default_ttl
        current_time = time.time()

        # Create cache entry
        entry = CacheEntry(
            result=result,
            created_at=current_time,
            last_accessed=current_time,
            ttl_seconds=ttl_seconds,
        )

        # Check if we need to evict
        if cache_key not in self._cache and len(self._cache) >= self.max_size:
            # Evict LRU entry (first item in OrderedDict)
            evicted_key = next(iter(self._cache))
            self._evict_entry(evicted_key)

        # Store entry
        self._cache[cache_key] = entry
        self._cache.move_to_end(cache_key)

    async def _get_from_redis(
        self, cache_key: str, correlation_id: Optional[UUID] = None
    ) -> Optional[SemanticAnalysisResult]:
        """Retrieve entry from Redis backend."""
        if not self.redis_client:
            return None

        try:
            import json

            value = await self.redis_client.get(f"semantic_cache:{cache_key}")
            if value:
                data = json.loads(value)
                return SemanticAnalysisResult(**data)
            return None
        except Exception as e:
            logger.warning(f"Redis GET failed: {e}")
            return None

    async def _set_in_redis(
        self, cache_key: str, result: SemanticAnalysisResult, ttl: int
    ) -> None:
        """Store entry in Redis backend with TTL."""
        if not self.redis_client:
            return

        try:
            import json

            value = json.dumps(result.model_dump(), default=str)
            await self.redis_client.setex(f"semantic_cache:{cache_key}", ttl, value)
        except Exception as e:
            logger.warning(f"Redis SET failed: {e}")

    def _evict_entry(self, cache_key: str) -> None:
        """Evict entry from cache and update metrics."""
        if cache_key in self._cache:
            del self._cache[cache_key]
            self.metrics.evictions += 1
            logger.debug(f"Evicted cache entry: {cache_key[:16]}...")

    # ========================================================================
    # Cache Management
    # ========================================================================

    async def warm_cache(
        self,
        content_samples: List[str],
        analysis_function: Optional[
            "Callable[[str], Awaitable[SemanticAnalysisResult]]"
        ] = None,
    ) -> int:
        """
        Warm cache with historical patterns.

        Args:
            content_samples: List of content to pre-analyze and cache
            analysis_function: Optional async function to generate results

        Returns:
            Number of entries successfully warmed
        """
        warmed_count = 0

        for content in content_samples:
            # Check if already cached
            cache_key = self.get_cache_key(content)
            if cache_key in self._cache:
                continue

            # Generate result if function provided
            if analysis_function:
                try:
                    result = await analysis_function(content)
                    await self.set(content, result)
                    warmed_count += 1
                except Exception as e:
                    logger.warning(f"Cache warming failed for entry: {e}")
                    continue

        logger.info(f"Cache warming complete: {warmed_count} entries added")
        return warmed_count

    def clear(self) -> None:
        """Clear all cache entries and reset metrics."""
        self._cache.clear()
        self.metrics = CacheMetrics()
        logger.info("Cache cleared")

    def evict_expired(self) -> int:
        """
        Manually evict all expired entries.

        Returns:
            Number of entries evicted
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items() if entry.is_expired(current_time)
        ]

        for key in expired_keys:
            self._evict_entry(key)

        if expired_keys:
            logger.info(f"Evicted {len(expired_keys)} expired entries")

        return len(expired_keys)

    # ========================================================================
    # Metrics and Monitoring
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache metrics.

        Returns:
            Dictionary with cache statistics and performance data
        """
        return {
            **self.metrics.to_dict(),
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "utilization": len(self._cache) / self.max_size,
            "redis_enabled": self.redis_enabled,
            "default_ttl": self.default_ttl,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get detailed cache status information."""
        total_access_count = sum(entry.access_count for entry in self._cache.values())

        return {
            "status": "healthy",
            "metrics": self.get_metrics(),
            "total_access_count": total_access_count,
            "avg_access_per_entry": (
                total_access_count / len(self._cache) if self._cache else 0
            ),
        }

    # ========================================================================
    # ONEX Reducer Interface
    # ========================================================================

    async def execute_reduction(
        self, operation: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        ONEX Reducer execution interface.

        Operations:
        - get: Retrieve cached result
        - set: Store result in cache
        - warm: Warm cache with samples
        - clear: Clear all entries
        - evict_expired: Remove expired entries
        - metrics: Get cache metrics

        Args:
            operation: Operation to execute
            data: Operation parameters

        Returns:
            Operation result
        """
        if operation == "get":
            result = await self.get(data["content"])
            return {
                "success": True,
                "result": result.model_dump() if result else None,
                "cache_hit": result is not None,
            }

        elif operation == "set":
            await self.set(
                data["content"],
                SemanticAnalysisResult(**data["result"]),
                data.get("ttl"),
            )
            return {"success": True}

        elif operation == "warm":
            count = await self.warm_cache(
                data["content_samples"], data.get("analysis_function")
            )
            return {"success": True, "warmed_count": count}

        elif operation == "clear":
            self.clear()
            return {"success": True}

        elif operation == "evict_expired":
            count = self.evict_expired()
            return {"success": True, "evicted_count": count}

        elif operation == "metrics":
            return {"success": True, "metrics": self.get_metrics()}

        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
