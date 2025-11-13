"""
OnexTree Integration for Pattern Learning

Retrieves tree information for patterns from OnexTree service at 192.168.86.200:8058.
Returns file paths to relevant models, protocols, implementations.

ONEX Pattern: Effect Node (external service integration)
Performance Target: <100ms with caching
Cache TTL: 5 minutes (300s)
"""

import hashlib
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# OnexTree service URL from environment
ONEX_TREE_SERVICE_URL = os.getenv("ONEX_TREE_SERVICE_URL", "http://192.168.86.200:8058")

# Cache configuration
TREE_INFO_CACHE_TTL = 300  # 5 minutes
TREE_INFO_CACHE_MAX_SIZE = 500  # Max cache entries

# HTTP client configuration
HTTP_TIMEOUT = 10.0  # 10 second timeout
HTTP_MAX_RETRIES = 2


# ============================================================================
# Models
# ============================================================================


class RelevantFile(BaseModel):
    """File relevant to a pattern."""

    path: str = Field(..., description="File path relative to repository root")
    file_type: str = Field(
        ..., description="File type (model, protocol, implementation, test)"
    )
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    node_type: Optional[str] = Field(None, description="ONEX node type if applicable")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")


class TreeMetadata(BaseModel):
    """Tree metadata for pattern."""

    total_files: int = Field(default=0, description="Total files found")
    node_types: List[str] = Field(
        default_factory=list, description="ONEX node types found"
    )
    pattern_locations: List[str] = Field(
        default_factory=list, description="Directories containing pattern"
    )
    tree_depth: Optional[int] = Field(None, description="Maximum tree depth")
    last_indexed: Optional[str] = Field(None, description="Last indexing timestamp")


class TreeInfo(BaseModel):
    """Complete tree information for a pattern."""

    relevant_files: List[RelevantFile] = Field(default_factory=list)
    tree_metadata: TreeMetadata = Field(default_factory=TreeMetadata)
    from_cache: bool = Field(default=False, description="Retrieved from cache")
    query_time_ms: float = Field(default=0.0, description="Query execution time")


@dataclass
class CacheEntry:
    """Cache entry with TTL tracking."""

    tree_info: TreeInfo
    created_at: float
    cache_key: str
    access_count: int = 0

    def is_expired(self) -> bool:
        """Check if entry has exceeded TTL."""
        return (time.time() - self.created_at) > TREE_INFO_CACHE_TTL

    def touch(self) -> None:
        """Update access count."""
        self.access_count += 1


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_requests: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        return self.hits / self.total_requests if self.total_requests > 0 else 0.0


# ============================================================================
# Tree Info Cache
# ============================================================================


class TreeInfoCache:
    """
    LRU cache for tree information with TTL expiration.

    Performance Target: <1ms for cached results
    """

    def __init__(
        self,
        max_size: int = TREE_INFO_CACHE_MAX_SIZE,
        ttl_seconds: int = TREE_INFO_CACHE_TTL,
    ):
        """Initialize cache."""
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.metrics = CacheMetrics()

        logger.info(
            f"TreeInfoCache initialized: max_size={max_size}, ttl={ttl_seconds}s"
        )

    def _get_cache_key(
        self, pattern_name: str, pattern_type: str, node_type: Optional[str]
    ) -> str:
        """Generate cache key from pattern parameters."""
        key_str = f"{pattern_name}:{pattern_type}:{node_type or 'any'}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]

    def get(
        self, pattern_name: str, pattern_type: str, node_type: Optional[str] = None
    ) -> Optional[TreeInfo]:
        """Retrieve cached tree info."""
        cache_key = self._get_cache_key(pattern_name, pattern_type, node_type)
        self.metrics.total_requests += 1

        if cache_key in self._cache:
            entry = self._cache[cache_key]

            # Check expiration
            if entry.is_expired():
                logger.debug(f"Cache entry expired: {cache_key}")
                self._evict_entry(cache_key)
                self.metrics.misses += 1
                return None

            # Cache hit - move to end (LRU)
            self._cache.move_to_end(cache_key)
            entry.touch()
            self.metrics.hits += 1

            logger.debug(f"Cache HIT: {cache_key} (access_count={entry.access_count})")

            # Mark as from cache
            tree_info = entry.tree_info.model_copy(deep=True)
            tree_info.from_cache = True
            return tree_info

        # Cache miss
        self.metrics.misses += 1
        logger.debug(f"Cache MISS: {cache_key}")
        return None

    def set(
        self,
        pattern_name: str,
        pattern_type: str,
        tree_info: TreeInfo,
        node_type: Optional[str] = None,
    ) -> None:
        """Store tree info in cache."""
        cache_key = self._get_cache_key(pattern_name, pattern_type, node_type)

        # Check if we need to evict
        if cache_key not in self._cache and len(self._cache) >= self.max_size:
            # Evict LRU entry (first item)
            evicted_key = next(iter(self._cache))
            self._evict_entry(evicted_key)

        # Store entry
        entry = CacheEntry(
            tree_info=tree_info, created_at=time.time(), cache_key=cache_key
        )
        self._cache[cache_key] = entry
        self._cache.move_to_end(cache_key)

        logger.debug(f"Cache SET: {cache_key} (cache_size={len(self._cache)})")

    def _evict_entry(self, cache_key: str) -> None:
        """Evict entry from cache."""
        if cache_key in self._cache:
            del self._cache[cache_key]
            self.metrics.evictions += 1
            logger.debug(f"Evicted cache entry: {cache_key}")

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self.metrics = CacheMetrics()
        logger.info("Tree info cache cleared")

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics."""
        return {
            "hits": self.metrics.hits,
            "misses": self.metrics.misses,
            "evictions": self.metrics.evictions,
            "total_requests": self.metrics.total_requests,
            "hit_rate": self.metrics.hit_rate,
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "utilization": (
                len(self._cache) / self.max_size if self.max_size > 0 else 0.0
            ),
        }


# ============================================================================
# Global Cache Instance
# ============================================================================

_tree_info_cache = TreeInfoCache()


# ============================================================================
# OnexTree Client
# ============================================================================


class OnexTreeClient:
    """
    HTTP client for OnexTree service.

    Performance Target: <100ms for tree lookups
    """

    def __init__(
        self,
        base_url: str = ONEX_TREE_SERVICE_URL,
        timeout: float = HTTP_TIMEOUT,
        max_retries: int = HTTP_MAX_RETRIES,
    ):
        """Initialize OnexTree client."""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        logger.info(f"OnexTreeClient initialized: base_url={self.base_url}")

    async def search_pattern_files(
        self,
        pattern_name: str,
        pattern_type: str,
        node_type: Optional[str] = None,
        correlation_id: Optional[UUID] = None,
    ) -> TreeInfo:
        """
        Search OnexTree for files related to a pattern.

        Args:
            pattern_name: Pattern name to search for
            pattern_type: Pattern type (e.g., "onex", "design_pattern")
            node_type: Optional ONEX node type filter
            correlation_id: Request correlation ID

        Returns:
            TreeInfo with relevant files and metadata
        """
        start_time = time.time()

        # Check cache first
        cached = _tree_info_cache.get(pattern_name, pattern_type, node_type)
        if cached:
            logger.info(
                f"Tree info retrieved from cache: pattern={pattern_name}, "
                f"type={pattern_type}, node_type={node_type}"
            )
            return cached

        # Query OnexTree service
        try:
            tree_info = await self._query_onextree(
                pattern_name, pattern_type, node_type, correlation_id
            )

            # Calculate query time
            query_time_ms = (time.time() - start_time) * 1000
            tree_info.query_time_ms = query_time_ms

            # Cache result
            _tree_info_cache.set(pattern_name, pattern_type, tree_info, node_type)

            logger.info(
                f"Tree info retrieved from OnexTree: pattern={pattern_name}, "
                f"files={len(tree_info.relevant_files)}, time={query_time_ms:.2f}ms"
            )

            return tree_info

        except Exception as e:
            logger.error(f"Failed to retrieve tree info: {e}", exc_info=True)
            # Return empty tree info on error
            return TreeInfo(
                relevant_files=[],
                tree_metadata=TreeMetadata(),
                from_cache=False,
                query_time_ms=(time.time() - start_time) * 1000,
            )

    async def _query_onextree(
        self,
        pattern_name: str,
        pattern_type: str,
        node_type: Optional[str],
        correlation_id: Optional[UUID],
    ) -> TreeInfo:
        """
        Query OnexTree service with retry logic.

        OnexTree API endpoints (expected):
        - GET /api/search/pattern?name={pattern_name}&type={pattern_type}&node_type={node_type}
        - GET /api/files/by-pattern?pattern={pattern_name}
        """
        headers = {}
        if correlation_id:
            headers["X-Correlation-ID"] = str(correlation_id)

        # Build query parameters
        params = {
            "pattern_name": pattern_name,
            "pattern_type": pattern_type,
        }
        if node_type:
            params["node_type"] = node_type

        # Try with retries
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    # Try pattern search endpoint
                    response = await client.get(
                        f"{self.base_url}/api/search/pattern",
                        params=params,
                        headers=headers,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_onextree_response(data)
                    elif response.status_code == 404:
                        # Pattern not found - return empty result
                        logger.warning(f"Pattern not found in OnexTree: {pattern_name}")
                        return TreeInfo(
                            relevant_files=[],
                            tree_metadata=TreeMetadata(),
                        )
                    else:
                        logger.warning(
                            f"OnexTree returned status {response.status_code}: {response.text}"
                        )

            except httpx.TimeoutException:
                last_exception = TimeoutError(
                    f"OnexTree request timed out after {self.timeout}s"
                )
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} timed out")
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {e}")

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                await self._async_sleep(2**attempt)

        # All retries failed
        raise Exception(
            f"Failed to query OnexTree after {self.max_retries} attempts: {last_exception}"
        )

    @staticmethod
    async def _async_sleep(seconds: float) -> None:
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(seconds)

    def _parse_onextree_response(self, data: Dict[str, Any]) -> TreeInfo:
        """
        Parse OnexTree API response into TreeInfo model.

        Expected response format:
        {
            "files": [
                {
                    "path": "services/...",
                    "type": "model",
                    "relevance": 0.95,
                    "node_type": "EFFECT",
                    "size_bytes": 1234
                }
            ],
            "metadata": {
                "total_files": 5,
                "node_types": ["EFFECT", "COMPUTE"],
                "pattern_locations": ["services/intelligence/src"],
                "tree_depth": 3,
                "last_indexed": "2025-11-03T..."
            }
        }
        """
        relevant_files = []
        for file_data in data.get("files", []):
            try:
                relevant_files.append(RelevantFile(**file_data))
            except Exception as e:
                logger.warning(f"Failed to parse file data: {e}")

        tree_metadata = TreeMetadata()
        if "metadata" in data:
            try:
                tree_metadata = TreeMetadata(**data["metadata"])
            except Exception as e:
                logger.warning(f"Failed to parse tree metadata: {e}")

        return TreeInfo(
            relevant_files=relevant_files,
            tree_metadata=tree_metadata,
            from_cache=False,
        )


# ============================================================================
# Public API
# ============================================================================

# Global client instance
_onextree_client: Optional[OnexTreeClient] = None


def get_onextree_client() -> OnexTreeClient:
    """Get or create OnexTree client instance."""
    global _onextree_client
    if _onextree_client is None:
        _onextree_client = OnexTreeClient()
    return _onextree_client


async def get_tree_info_for_pattern(
    pattern_name: str,
    pattern_type: str,
    node_type: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> TreeInfo:
    """
    Get tree information for a pattern.

    This is the main public API for retrieving tree information.
    Results are cached for 5 minutes with <100ms overhead.

    Args:
        pattern_name: Pattern name to search for
        pattern_type: Pattern type (e.g., "onex", "design_pattern")
        node_type: Optional ONEX node type filter (EFFECT, COMPUTE, REDUCER, ORCHESTRATOR)
        correlation_id: Request correlation ID

    Returns:
        TreeInfo containing:
        - relevant_files: List of files with paths, types, and relevance scores
        - tree_metadata: Metadata about the pattern's location in the tree
        - from_cache: Whether result was retrieved from cache
        - query_time_ms: Time taken to retrieve information

    Performance:
    - Cache hit: <1ms
    - Cache miss: <100ms (target)

    Example:
        >>> tree_info = await get_tree_info_for_pattern(
        ...     "pattern_learning",
        ...     "onex",
        ...     node_type="EFFECT"
        ... )
        >>> print(tree_info.relevant_files[0].path)
        'services/intelligence/src/services/pattern_learning/node_pattern_query_effect.py'
    """
    client = get_onextree_client()
    return await client.search_pattern_files(
        pattern_name, pattern_type, node_type, correlation_id
    )


def get_tree_cache_metrics() -> Dict[str, Any]:
    """
    Get tree info cache metrics.

    Returns cache statistics including hit rate, size, and utilization.
    """
    return _tree_info_cache.get_metrics()


def clear_tree_cache() -> None:
    """Clear the tree info cache (admin operation)."""
    _tree_info_cache.clear()
