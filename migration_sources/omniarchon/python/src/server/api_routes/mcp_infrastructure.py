"""
MCP API Infrastructure Components

Handles:
- HTTP client connection pooling
- Valkey cache management for tool definitions
- Request coalescing for cache stampede protection
- Lifespan management
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

import httpx
from cachetools import TTLCache
from redis import asyncio as aioredis
from server.config.logfire_config import api_logger

# ============================================
# HTTP CLIENT CONNECTION POOLING
# ============================================

# Module-level HTTP client with connection pooling
_HTTP_CLIENT: httpx.AsyncClient | None = None
_CLIENT_LOCK = asyncio.Lock()


async def get_http_client() -> httpx.AsyncClient:
    """
    Get or create shared HTTP client with connection pooling.

    Performance characteristics:
    - Connection pool: 100 max connections, 20 keepalive connections
    - Timeouts: Configurable via environment variables (defaults: 5s/25s/10s/60s)
    - Thread-safe initialization with async lock
    - Reused across all tool calls for reduced latency

    Environment variables:
    - HTTP_CONNECT_TIMEOUT: Connection timeout in seconds (default: 5.0)
    - HTTP_READ_TIMEOUT: Read timeout in seconds (default: 25.0)
    - HTTP_WRITE_TIMEOUT: Write timeout in seconds (default: 10.0)
    - HTTP_POOL_TIMEOUT: Pool timeout in seconds (default: 60.0)

    Returns:
        httpx.AsyncClient: Shared async HTTP client instance
    """
    global _HTTP_CLIENT

    async with _CLIENT_LOCK:
        if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
            # Get timeouts from environment with sensible defaults
            connect_timeout = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5.0"))
            read_timeout = float(os.getenv("HTTP_READ_TIMEOUT", "25.0"))
            write_timeout = float(os.getenv("HTTP_WRITE_TIMEOUT", "10.0"))
            pool_timeout = float(os.getenv("HTTP_POOL_TIMEOUT", "60.0"))

            _HTTP_CLIENT = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=connect_timeout,
                    read=read_timeout,
                    write=write_timeout,
                    pool=pool_timeout,
                ),
                limits=httpx.Limits(
                    max_connections=100,  # Total connections
                    max_keepalive_connections=20,  # Persistent connections
                ),
            )
            api_logger.info(
                f"Initialized HTTP client with connection pooling - "
                f"max_connections=100, keepalive=20, timeouts=({connect_timeout}s/{read_timeout}s/{write_timeout}s)"
            )

    return _HTTP_CLIENT


async def close_http_client():
    """Close the shared HTTP client and cleanup resources."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT and not _HTTP_CLIENT.is_closed:
        await _HTTP_CLIENT.aclose()
        _HTTP_CLIENT = None
        api_logger.info("Closed HTTP client connection pool")


# ============================================
# LIFESPAN MANAGEMENT
# ============================================


@asynccontextmanager
async def router_lifespan(app):
    """Lifespan context manager for router resources."""
    # Startup
    yield
    # Shutdown
    await close_http_client()
    api_logger.info("Server shutdown: Resources cleaned up")


# ============================================
# VALKEY CACHE FOR TOOL DEFINITIONS
# ============================================

# Module-level Redis client for tool definition caching
_redis_client: aioredis.Redis | None = None
_redis_lock = asyncio.Lock()

# Request coalescing locks to prevent cache stampede
# TTL-based cache to prevent memory leaks (max 100 keys, 5 minute TTL)
# Keyed by cache key to ensure only one backend call per resource
_request_locks: TTLCache = TTLCache(maxsize=100, ttl=300)


async def get_redis_client() -> aioredis.Redis | None:
    """
    Get or create Redis client for tool definition caching.

    Returns:
        Redis client instance or None if connection fails
    """
    global _redis_client

    async with _redis_lock:
        if _redis_client is None:
            try:
                redis_url = os.getenv("VALKEY_URL", "redis://archon-valkey:6379/0")
                enable_cache = os.getenv("ENABLE_CACHE", "true").lower() == "true"

                if not enable_cache:
                    api_logger.info(
                        "Tool definition cache disabled via ENABLE_CACHE=false"
                    )
                    return None

                _redis_client = await aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )

                # Test connection
                await _redis_client.ping()
                api_logger.info(f"✅ Tool definition cache initialized: {redis_url}")

            except Exception as e:
                api_logger.warning(
                    f"⚠️  Tool definition cache unavailable: {e}. Continuing without cache."
                )
                _redis_client = None

    return _redis_client


async def get_cached_tools(client_id: str) -> list[dict] | None:
    """
    Get cached tool definitions for a client.

    Args:
        client_id: MCP client identifier

    Returns:
        List of tool definitions or None if not cached
    """
    try:
        redis = await get_redis_client()
        if not redis:
            return None

        cache_key = f"mcp:tools:{client_id}"
        cached = await redis.get(cache_key)

        if cached:
            api_logger.debug(f"✅ Cache HIT: {cache_key}")
            return json.loads(cached)

        api_logger.debug(f"❌ Cache MISS: {cache_key}")
        return None

    except Exception as e:
        api_logger.warning(f"Cache read failed for {client_id}: {e}")
        return None


async def cache_tools(client_id: str, tools: list[dict], ttl: int = 3600):
    """
    Cache tool definitions for a client.

    Args:
        client_id: MCP client identifier
        tools: List of tool definitions to cache
        ttl: Time-to-live in seconds (default: 3600 = 1 hour)

    Returns:
        True if cached successfully, False otherwise
    """
    try:
        redis = await get_redis_client()
        if not redis:
            return False

        cache_key = f"mcp:tools:{client_id}"
        await redis.setex(cache_key, ttl, json.dumps(tools))

        api_logger.info(f"✅ Cache SET: {cache_key} ({len(tools)} tools, ttl={ttl}s)")
        return True

    except Exception as e:
        api_logger.warning(f"Cache write failed for {client_id}: {e}")
        return False


async def invalidate_tools_cache(
    client_id: str | None = None, batch_size: int = 100
) -> int:
    """
    Invalidate cached tool definitions.

    Args:
        client_id: Specific client to invalidate, or None for all clients
        batch_size: Number of keys to delete per batch operation (default: 100).
                   Prevents OOM on large key sets by using batched deletion.
                   Higher values = faster but more memory, lower = slower but safer.

    Returns:
        Number of cache keys invalidated

    Implementation Notes:
        Uses Redis SCAN (non-blocking) instead of KEYS (blocking) for production safety.
        Batched deletion ensures O(batch_size) memory vs O(n) for naive approach.
    """
    try:
        redis = await get_redis_client()
        if not redis:
            return 0

        if client_id:
            # Invalidate specific client
            cache_key = f"mcp:tools:{client_id}"
            deleted = await redis.delete(cache_key)
            api_logger.info(f"✅ Cache INVALIDATE: {cache_key}")
            return deleted
        else:
            # Invalidate all tool caches (batch delete for efficiency)
            pattern = "mcp:tools:*"
            deleted = 0
            batch = []

            async for key in redis.scan_iter(match=pattern):
                batch.append(key)
                if len(batch) >= batch_size:
                    await redis.delete(*batch)
                    deleted += len(batch)
                    batch = []

            # Delete remaining keys in batch
            if batch:
                await redis.delete(*batch)
                deleted += len(batch)

            api_logger.info(
                f"✅ Cache INVALIDATE: {deleted} keys matching '{pattern}' (batch_size={batch_size})"
            )
            return deleted

    except Exception as e:
        api_logger.warning(f"Cache invalidation failed: {e}")
        return 0


async def get_tools_with_coalescing(client_id: str) -> list[dict]:
    """
    Get tools from cache with stampede protection using request coalescing.

    Implements double-check locking pattern:
    1. Check cache (fast path for cache hits)
    2. Acquire per-key lock (only on cache miss)
    3. Double-check cache (might be populated by concurrent request)
    4. Load from backend if still missing

    This prevents thundering herd problem where multiple concurrent requests
    on cache miss would all hit the backend simultaneously.

    Args:
        client_id: MCP client identifier

    Returns:
        List of tool definitions

    Raises:
        Exception: If tool loading fails after cache miss
    """
    from ..utils.mcp_tools_loader import load_mcp_tools

    # First check: Try cache without lock (fast path)
    cached_tools = await get_cached_tools(client_id)
    if cached_tools is not None:
        api_logger.info(f"Returning {len(cached_tools)} cached tools (fast path)")
        return cached_tools

    # Cache miss - use per-key lock for request coalescing
    cache_key = f"mcp:tools:{client_id}"
    if cache_key not in _request_locks:
        _request_locks[cache_key] = asyncio.Lock()

    lock = _request_locks[cache_key]
    successfully_cached = False

    try:
        async with lock:
            # Second check: Cache might be populated by concurrent request
            cached_tools = await get_cached_tools(client_id)
            if cached_tools is not None:
                api_logger.info(
                    f"Returning {len(cached_tools)} cached tools (double-check hit)"
                )
                return cached_tools

            # Still cache miss - load from backend (only one request does this)
            api_logger.info(
                "Loading task management tools from configuration (cache miss, coalescing)"
            )

            try:
                task_tools = load_mcp_tools()

                # Only cache if we successfully loaded tools
                if task_tools:
                    await cache_tools(client_id, task_tools)
                    successfully_cached = True
                    api_logger.info(
                        f"Returning {len(task_tools)} task management tools (backend load)"
                    )
                else:
                    # Empty result - cache with short TTL (30s) to prevent stampede on transient issues
                    await cache_tools(client_id, [], ttl=30)
                    successfully_cached = True
                    api_logger.warning(
                        "load_mcp_tools() returned empty list - cached with 30s TTL for stampede protection"
                    )

            except Exception as e:
                api_logger.error(f"Failed to load MCP tools from config: {e}")
                # Cache empty result with very short TTL (5s) to prevent stampede during failures
                await cache_tools(client_id, [], ttl=5)
                successfully_cached = True
                task_tools = []

            return task_tools
    finally:
        # Only cleanup lock if we successfully cached the result
        # Keep lock for transient failures to prevent stampede
        if successfully_cached:
            _request_locks.pop(cache_key, None)
