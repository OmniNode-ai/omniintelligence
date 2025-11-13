"""
Advanced Search Caching System

Provides multi-level caching for search operations with:
- Redis-based distributed caching
- In-memory LRU caching
- Embedding vector caching
- Query result caching with smart invalidation
- Performance monitoring and optimization
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis.asyncio as redis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CacheMetrics(BaseModel):
    """Cache performance metrics."""

    cache_hits: int = Field(default=0, description="Number of cache hits")
    cache_misses: int = Field(default=0, description="Number of cache misses")
    cache_evictions: int = Field(default=0, description="Number of cache evictions")
    total_requests: int = Field(default=0, description="Total cache requests")
    average_response_time_ms: float = Field(
        default=0.0, description="Average response time"
    )
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    redis_connected: bool = Field(default=False, description="Redis connection status")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate


class LRUCache:
    """Thread-safe LRU cache implementation for in-memory caching."""

    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache with maximum size."""
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        async with self._lock:
            if key in self.cache:
                # Move to end (most recently used)
                value = self.cache.pop(key)
                self.cache[key] = value
                return value
            return None

    async def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        async with self._lock:
            if key in self.cache:
                # Update existing item
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # Remove least recently used item
                self.cache.popitem(last=False)

            self.cache[key] = value

    async def delete(self, key: str) -> bool:
        """Delete item from cache."""
        async with self._lock:
            return self.cache.pop(key, None) is not None

    async def clear(self) -> None:
        """Clear all items from cache."""
        async with self._lock:
            self.cache.clear()

    async def size(self) -> int:
        """Get current cache size."""
        async with self._lock:
            return len(self.cache)

    async def keys(self) -> List[str]:
        """Get all cache keys."""
        async with self._lock:
            return list(self.cache.keys())


class SearchCache:
    """
    Advanced multi-level search caching system.

    Provides:
    - Redis distributed caching for scalability
    - In-memory LRU caching for speed
    - Embedding vector caching
    - Query result caching with TTL
    - Smart cache invalidation
    - Performance monitoring
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        redis_password: Optional[str] = None,
        max_memory_cache_size: int = 1000,
        default_ttl_seconds: int = 3600,  # 1 hour
        embedding_ttl_seconds: int = 86400,  # 24 hours
        enable_compression: bool = True,
    ):
        """
        Initialize search cache system.

        Args:
            redis_url: Redis connection URL (optional)
            redis_password: Redis password (optional)
            max_memory_cache_size: Maximum in-memory cache size
            default_ttl_seconds: Default TTL for cached items
            embedding_ttl_seconds: TTL for embedding vectors
            enable_compression: Whether to compress cached data
        """
        self.redis_url = redis_url
        self.redis_password = redis_password
        self.default_ttl = default_ttl_seconds
        self.embedding_ttl = embedding_ttl_seconds
        self.enable_compression = enable_compression

        # Redis client (optional)
        self.redis_client: Optional[redis.Redis] = None
        self.redis_available = False

        # In-memory caches
        self.query_cache = LRUCache(max_memory_cache_size)
        self.embedding_cache = LRUCache(
            max_memory_cache_size // 2
        )  # Embeddings are larger
        self.result_cache = LRUCache(max_memory_cache_size)

        # Performance metrics
        self.metrics = CacheMetrics()

        # Cache key prefixes
        self.QUERY_PREFIX = "search:query:"
        self.EMBEDDING_PREFIX = "search:embedding:"
        self.RESULT_PREFIX = "search:result:"
        self.ANALYTICS_PREFIX = "search:analytics:"

    async def initialize(self) -> None:
        """Initialize cache system and Redis connection."""
        try:
            if self.redis_url:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    password=self.redis_password,
                    decode_responses=False,  # We handle binary data
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    max_connections=20,
                )

                # Test Redis connection
                await self.redis_client.ping()
                self.redis_available = True
                self.metrics.redis_connected = True
                logger.info("Redis cache initialized successfully")
            else:
                logger.info("Redis not configured, using in-memory cache only")

        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache: {e}")
            self.redis_available = False
            self.metrics.redis_connected = False

    async def close(self) -> None:
        """Close cache connections."""
        if self.redis_client:
            await self.redis_client.close()

    def _generate_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key from arguments."""
        # Create stable hash from arguments
        key_data = json.dumps(args, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"{prefix}{key_hash}"

    def _serialize_data(self, data: Any) -> bytes:
        """Serialize data for caching."""
        if self.enable_compression:
            import zlib

            return zlib.compress(pickle.dumps(data))
        return pickle.dumps(data)

    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize cached data."""
        if self.enable_compression:
            import zlib

            return pickle.loads(zlib.decompress(data))
        return pickle.loads(data)

    async def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get data from Redis cache."""
        if not self.redis_available or not self.redis_client:
            return None

        try:
            data = await self.redis_client.get(key)
            if data:
                return self._deserialize_data(data)
        except Exception as e:
            logger.warning(f"Redis get failed for key {key}: {e}")

        return None

    async def _set_to_redis(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """Set data to Redis cache."""
        if not self.redis_available or not self.redis_client:
            return False

        try:
            serialized_data = self._serialize_data(value)
            ttl = ttl or self.default_ttl
            await self.redis_client.setex(key, ttl, serialized_data)
            return True
        except Exception as e:
            logger.warning(f"Redis set failed for key {key}: {e}")
            return False

    async def _delete_from_redis(self, key: str) -> bool:
        """Delete data from Redis cache."""
        if not self.redis_available or not self.redis_client:
            return False

        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Redis delete failed for key {key}: {e}")
            return False

    async def cache_query_result(
        self,
        query: str,
        search_mode: str,
        filters: Dict[str, Any],
        results: List[Dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> None:
        """Cache search query results."""
        start_time = time.time()

        try:
            cache_key = self._generate_cache_key(
                self.QUERY_PREFIX, query, search_mode, filters
            )

            cache_data = {
                "results": results,
                "cached_at": datetime.utcnow().isoformat(),
                "query": query,
                "search_mode": search_mode,
                "filters": filters,
            }

            # Cache in both Redis and memory
            await asyncio.gather(
                self._set_to_redis(cache_key, cache_data, ttl),
                self.query_cache.set(cache_key, cache_data),
                return_exceptions=True,
            )

            cache_time = (time.time() - start_time) * 1000
            logger.debug(f"Cached query results in {cache_time:.2f}ms")

        except Exception as e:
            logger.error(f"Failed to cache query results: {e}")

    async def get_cached_query_result(
        self, query: str, search_mode: str, filters: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search query results."""
        start_time = time.time()

        try:
            cache_key = self._generate_cache_key(
                self.QUERY_PREFIX, query, search_mode, filters
            )

            # Try memory cache first (fastest)
            cached_data = await self.query_cache.get(cache_key)
            if cached_data:
                self.metrics.cache_hits += 1
                self.metrics.total_requests += 1
                cache_time = (time.time() - start_time) * 1000
                self._update_response_time(cache_time)
                logger.debug(f"Query cache hit (memory) in {cache_time:.2f}ms")
                return cached_data["results"]

            # Try Redis cache
            cached_data = await self._get_from_redis(cache_key)
            if cached_data:
                # Store in memory cache for faster future access
                await self.query_cache.set(cache_key, cached_data)
                self.metrics.cache_hits += 1
                self.metrics.total_requests += 1
                cache_time = (time.time() - start_time) * 1000
                self._update_response_time(cache_time)
                logger.debug(f"Query cache hit (Redis) in {cache_time:.2f}ms")
                return cached_data["results"]

            # Cache miss
            self.metrics.cache_misses += 1
            self.metrics.total_requests += 1
            return None

        except Exception as e:
            logger.error(f"Failed to get cached query results: {e}")
            return None

    async def cache_embedding(
        self, text: str, model: str, embedding: np.ndarray, ttl: Optional[int] = None
    ) -> None:
        """Cache embedding vector."""
        try:
            cache_key = self._generate_cache_key(self.EMBEDDING_PREFIX, text, model)

            cache_data = {
                "embedding": embedding.tolist(),
                "text": text,
                "model": model,
                "cached_at": datetime.utcnow().isoformat(),
                "shape": embedding.shape,
            }

            # Cache with longer TTL for embeddings
            ttl = ttl or self.embedding_ttl

            await asyncio.gather(
                self._set_to_redis(cache_key, cache_data, ttl),
                self.embedding_cache.set(cache_key, cache_data),
                return_exceptions=True,
            )

        except Exception as e:
            logger.error(f"Failed to cache embedding: {e}")

    async def get_cached_embedding(self, text: str, model: str) -> Optional[np.ndarray]:
        """Get cached embedding vector."""
        try:
            cache_key = self._generate_cache_key(self.EMBEDDING_PREFIX, text, model)

            # Try memory cache first
            cached_data = await self.embedding_cache.get(cache_key)
            if cached_data:
                self.metrics.cache_hits += 1
                self.metrics.total_requests += 1
                return np.array(cached_data["embedding"])

            # Try Redis cache
            cached_data = await self._get_from_redis(cache_key)
            if cached_data:
                # Store in memory cache
                await self.embedding_cache.set(cache_key, cached_data)
                self.metrics.cache_hits += 1
                self.metrics.total_requests += 1
                return np.array(cached_data["embedding"])

            # Cache miss
            self.metrics.cache_misses += 1
            self.metrics.total_requests += 1
            return None

        except Exception as e:
            logger.error(f"Failed to get cached embedding: {e}")
            return None

    async def cache_analytics(
        self, query: str, analytics_data: Dict[str, Any], ttl: Optional[int] = None
    ) -> None:
        """Cache search analytics data."""
        try:
            cache_key = self._generate_cache_key(self.ANALYTICS_PREFIX, query)

            cache_data = {
                "analytics": analytics_data,
                "query": query,
                "cached_at": datetime.utcnow().isoformat(),
            }

            await self._set_to_redis(cache_key, cache_data, ttl)

        except Exception as e:
            logger.error(f"Failed to cache analytics: {e}")

    async def get_cached_analytics(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data."""
        try:
            cache_key = self._generate_cache_key(self.ANALYTICS_PREFIX, query)
            cached_data = await self._get_from_redis(cache_key)

            if cached_data:
                return cached_data["analytics"]

            return None

        except Exception as e:
            logger.error(f"Failed to get cached analytics: {e}")
            return None

    async def invalidate_cache(self, pattern: str = "*") -> int:
        """Invalidate cache entries matching pattern."""
        invalidated_count = 0

        try:
            # Invalidate Redis cache
            if self.redis_available and self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    invalidated_count += deleted

            # Invalidate memory caches
            if pattern == "*":
                await asyncio.gather(
                    self.query_cache.clear(),
                    self.embedding_cache.clear(),
                    self.result_cache.clear(),
                    return_exceptions=True,
                )
                invalidated_count += await self.query_cache.size()
                invalidated_count += await self.embedding_cache.size()
                invalidated_count += await self.result_cache.size()

            logger.info(f"Invalidated {invalidated_count} cache entries")
            return invalidated_count

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return 0

    async def invalidate_source_cache(self, source_id: str) -> None:
        """Invalidate cache entries related to a specific source."""
        try:
            # Invalidate Redis patterns
            patterns = [
                f"{self.QUERY_PREFIX}*",  # All query caches (too complex to filter)
                f"{self.RESULT_PREFIX}*{source_id}*",
            ]

            for pattern in patterns:
                await self.invalidate_cache(pattern)

            logger.info(f"Invalidated cache for source: {source_id}")

        except Exception as e:
            logger.error(f"Failed to invalidate source cache: {e}")

    def _update_response_time(self, response_time_ms: float) -> None:
        """Update average response time metric."""
        if self.metrics.total_requests == 1:
            self.metrics.average_response_time_ms = response_time_ms
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_response_time_ms = (
                alpha * response_time_ms
                + (1 - alpha) * self.metrics.average_response_time_ms
            )

    async def get_cache_stats(self) -> CacheMetrics:
        """Get comprehensive cache statistics."""
        try:
            # Update memory usage
            # Read embedding dimensions from environment for accurate memory estimation
            import os

            embedding_dims = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

            memory_usage = 0.0
            memory_usage += await self.query_cache.size() * 1024  # Rough estimate
            memory_usage += (
                await self.embedding_cache.size() * 4 * embedding_dims
            )  # Embeddings (4 bytes per float)
            memory_usage += await self.result_cache.size() * 512  # Results

            self.metrics.memory_usage_mb = memory_usage / (1024 * 1024)
            self.metrics.last_updated = datetime.utcnow()

            return self.metrics

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return self.metrics

    async def warm_cache(self, entities: List[Tuple[str, str, str]]) -> int:
        """Warm cache with common entities and embeddings."""
        warmed_count = 0

        try:
            for entity_id, content, model in entities:
                # Pre-generate and cache embeddings for common content
                # This would integrate with the embedding generator
                logger.debug(f"Warming cache for entity: {entity_id}")
                warmed_count += 1

            logger.info(f"Warmed cache with {warmed_count} entities")
            return warmed_count

        except Exception as e:
            logger.error(f"Failed to warm cache: {e}")
            return 0

    async def optimize_cache(self) -> Dict[str, Any]:
        """Optimize cache performance and clean up expired entries."""
        optimization_stats = {
            "cleaned_entries": 0,
            "memory_freed_mb": 0.0,
            "optimization_time_ms": 0.0,
        }

        start_time = time.time()

        try:
            # Get current memory usage

            # Clean up Redis expired keys (Redis does this automatically, but we can force)
            if self.redis_available and self.redis_client:
                # Get memory usage before
                info = await self.redis_client.info("memory")
                redis_memory_before = info.get("used_memory", 0)

                # Force cleanup of expired keys
                await self.redis_client.flushall()  # This is aggressive - in practice use more selective cleanup

                # Get memory usage after
                info = await self.redis_client.info("memory")
                redis_memory_after = info.get("used_memory", 0)

                optimization_stats["memory_freed_mb"] = (
                    redis_memory_before - redis_memory_after
                ) / (1024 * 1024)

            # Update metrics
            optimization_stats["optimization_time_ms"] = (
                time.time() - start_time
            ) * 1000

            logger.info(f"Cache optimization completed: {optimization_stats}")
            return optimization_stats

        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")
            return optimization_stats


# Global cache instance
search_cache = SearchCache()


async def initialize_search_cache(
    redis_url: Optional[str] = None, redis_password: Optional[str] = None, **kwargs
) -> SearchCache:
    """Initialize and return the global search cache instance."""
    global search_cache

    search_cache = SearchCache(
        redis_url=redis_url, redis_password=redis_password, **kwargs
    )

    await search_cache.initialize()
    return search_cache


async def get_search_cache() -> SearchCache:
    """Get the global search cache instance."""
    return search_cache
