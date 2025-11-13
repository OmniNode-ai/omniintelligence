"""
Valkey Cache Schemas

Defines cache key patterns, TTL configurations, and serialization helpers
for file location search caching.

ONEX Pattern: Compute (Configuration and data transformation)
Performance: Key generation <1ms, serialization <5ms
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class CacheSchemas:
    """
    Valkey cache key patterns and operations for file location search.

    Cache Strategy:
    - Search results: 5 minute TTL (frequent updates)
    - Project status: 1 hour TTL (infrequent changes)
    - File metadata: 30 minute TTL (moderate updates)

    Key Patterns:
    - file_location:query:{hash} - Search results
    - file_location:project:{name}:status - Project status
    - file_location:project:{name}:invalidate - Invalidation marker
    - file_location:metadata:{path_hash} - File metadata
    """

    # ==========================================================================
    # TTL Configuration (in seconds)
    # ==========================================================================

    SEARCH_RESULT_TTL = 300  # 5 minutes
    PROJECT_STATUS_TTL = 3600  # 1 hour
    FILE_METADATA_TTL = 1800  # 30 minutes
    INVALIDATION_TTL = 60  # 1 minute (short-lived marker)

    # ==========================================================================
    # Key Pattern Prefixes
    # ==========================================================================

    PREFIX = "file_location"
    QUERY_PREFIX = f"{PREFIX}:query"
    PROJECT_PREFIX = f"{PREFIX}:project"
    METADATA_PREFIX = f"{PREFIX}:metadata"
    INVALIDATION_SUFFIX = "invalidate"

    # ==========================================================================
    # Key Generation Methods
    # ==========================================================================

    @staticmethod
    def search_result_key(query: str, projects: Optional[list] = None) -> str:
        """
        Generate cache key for search result.

        Includes query text and optional project filters in hash to ensure
        different queries/filters produce different cache keys.

        Args:
            query: Search query text
            projects: Optional list of project name filters

        Returns:
            Cache key string

        Example:
            >>> key = CacheSchemas.search_result_key("authentication module")
            >>> # Returns: "file_location:query:sha256_abc123..."
        """
        # Include projects in hash to differentiate filtered queries
        cache_input = query
        if projects:
            cache_input = f"{query}|projects:{','.join(sorted(projects))}"

        query_hash = hashlib.sha256(cache_input.encode()).hexdigest()
        return f"{CacheSchemas.QUERY_PREFIX}:{query_hash}"

    @staticmethod
    def project_status_key(project_name: str) -> str:
        """
        Generate cache key for project status.

        Args:
            project_name: Project identifier

        Returns:
            Cache key string

        Example:
            >>> key = CacheSchemas.project_status_key("omniarchon")
            >>> # Returns: "file_location:project:omniarchon:status"
        """
        return f"{CacheSchemas.PROJECT_PREFIX}:{project_name}:status"

    @staticmethod
    def project_invalidation_key(project_name: str) -> str:
        """
        Generate invalidation marker key for project.

        Args:
            project_name: Project identifier

        Returns:
            Invalidation key string

        Example:
            >>> key = CacheSchemas.project_invalidation_key("omniarchon")
            >>> # Returns: "file_location:project:omniarchon:invalidate"
        """
        return f"{CacheSchemas.PROJECT_PREFIX}:{project_name}:{CacheSchemas.INVALIDATION_SUFFIX}"

    @staticmethod
    def file_metadata_key(file_path: str) -> str:
        """
        Generate cache key for file metadata.

        Uses hash of file path to ensure consistent key length.

        Args:
            file_path: Absolute file path

        Returns:
            Cache key string

        Example:
            >>> key = CacheSchemas.file_metadata_key("/path/to/file.py")
            >>> # Returns: "file_location:metadata:sha256_abc123..."
        """
        path_hash = hashlib.sha256(file_path.encode()).hexdigest()
        return f"{CacheSchemas.METADATA_PREFIX}:{path_hash}"

    @staticmethod
    def global_invalidation_key() -> str:
        """
        Generate global cache invalidation key.

        Returns:
            Global invalidation key

        Example:
            >>> key = CacheSchemas.global_invalidation_key()
            >>> # Returns: "file_location:invalidate_all"
        """
        return f"{CacheSchemas.PREFIX}:invalidate_all"

    # ==========================================================================
    # Pattern Matching
    # ==========================================================================

    @staticmethod
    def project_query_pattern(project_name: str) -> str:
        """
        Generate pattern to match all queries for a specific project.

        Used for cache invalidation when project is reindexed.

        Args:
            project_name: Project identifier

        Returns:
            Pattern string for Redis SCAN

        Example:
            >>> pattern = CacheSchemas.project_query_pattern("omniarchon")
            >>> # Use with: SCAN 0 MATCH pattern
        """
        return f"{CacheSchemas.QUERY_PREFIX}:*{project_name}*"

    @staticmethod
    def all_queries_pattern() -> str:
        """
        Generate pattern to match all search queries.

        Returns:
            Pattern string for Redis SCAN

        Example:
            >>> pattern = CacheSchemas.all_queries_pattern()
            >>> # Returns: "file_location:query:*"
        """
        return f"{CacheSchemas.QUERY_PREFIX}:*"

    @staticmethod
    def all_project_status_pattern() -> str:
        """
        Generate pattern to match all project status entries.

        Returns:
            Pattern string for Redis SCAN

        Example:
            >>> pattern = CacheSchemas.all_project_status_pattern()
            >>> # Returns: "file_location:project:*:status"
        """
        return f"{CacheSchemas.PROJECT_PREFIX}:*:status"

    # ==========================================================================
    # Serialization Methods
    # ==========================================================================

    @staticmethod
    def serialize_search_result(result: Dict[str, Any]) -> str:
        """
        Serialize search result for caching.

        Adds cached_at timestamp and converts to JSON.

        Args:
            result: Search result dictionary

        Returns:
            JSON string for cache storage

        Example:
            >>> result = {"success": True, "results": [...]}
            >>> serialized = CacheSchemas.serialize_search_result(result)
        """
        # Add caching metadata
        cache_entry = {
            **result,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "cache_source": "valkey",
        }
        return json.dumps(cache_entry)

    @staticmethod
    def deserialize_search_result(cached: str) -> Dict[str, Any]:
        """
        Deserialize cached search result.

        Args:
            cached: JSON string from cache

        Returns:
            Search result dictionary

        Example:
            >>> cached_str = cache.get(key)
            >>> result = CacheSchemas.deserialize_search_result(cached_str)
        """
        return json.loads(cached)

    @staticmethod
    def serialize_project_status(status: Dict[str, Any]) -> str:
        """
        Serialize project status for caching.

        Args:
            status: Project status dictionary

        Returns:
            JSON string for cache storage

        Example:
            >>> status = {"indexed": True, "file_count": 1247, ...}
            >>> serialized = CacheSchemas.serialize_project_status(status)
        """
        cache_entry = {
            **status,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(cache_entry)

    @staticmethod
    def deserialize_project_status(cached: str) -> Dict[str, Any]:
        """
        Deserialize cached project status.

        Args:
            cached: JSON string from cache

        Returns:
            Project status dictionary

        Example:
            >>> cached_str = cache.get(key)
            >>> status = CacheSchemas.deserialize_project_status(cached_str)
        """
        return json.loads(cached)

    # ==========================================================================
    # Cache Statistics
    # ==========================================================================

    @staticmethod
    def get_cache_stats_keys() -> Dict[str, str]:
        """
        Get cache statistics key names.

        Returns:
            Dictionary of statistic keys

        Example:
            >>> stats_keys = CacheSchemas.get_cache_stats_keys()
            >>> hit_count = cache.get(stats_keys["hits"])
        """
        return {
            "hits": f"{CacheSchemas.PREFIX}:stats:hits",
            "misses": f"{CacheSchemas.PREFIX}:stats:misses",
            "invalidations": f"{CacheSchemas.PREFIX}:stats:invalidations",
            "queries_cached": f"{CacheSchemas.PREFIX}:stats:queries_cached",
        }

    # ==========================================================================
    # Validation
    # ==========================================================================

    @staticmethod
    def validate_ttl(ttl: int) -> bool:
        """
        Validate TTL value is within acceptable range.

        Args:
            ttl: TTL in seconds

        Returns:
            True if valid, False otherwise

        Example:
            >>> is_valid = CacheSchemas.validate_ttl(300)
        """
        # TTL should be between 1 minute and 24 hours
        MIN_TTL = 60
        MAX_TTL = 86400
        return MIN_TTL <= ttl <= MAX_TTL

    @staticmethod
    def get_ttl_for_key_type(key: str) -> int:
        """
        Get recommended TTL based on key type.

        Args:
            key: Cache key

        Returns:
            Recommended TTL in seconds

        Example:
            >>> key = CacheSchemas.search_result_key("test")
            >>> ttl = CacheSchemas.get_ttl_for_key_type(key)
            >>> # Returns: 300 (SEARCH_RESULT_TTL)
        """
        if CacheSchemas.QUERY_PREFIX in key:
            return CacheSchemas.SEARCH_RESULT_TTL
        elif ":status" in key:
            return CacheSchemas.PROJECT_STATUS_TTL
        elif CacheSchemas.METADATA_PREFIX in key:
            return CacheSchemas.FILE_METADATA_TTL
        elif CacheSchemas.INVALIDATION_SUFFIX in key:
            return CacheSchemas.INVALIDATION_TTL
        else:
            # Default TTL
            return CacheSchemas.SEARCH_RESULT_TTL


__all__ = ["CacheSchemas"]
