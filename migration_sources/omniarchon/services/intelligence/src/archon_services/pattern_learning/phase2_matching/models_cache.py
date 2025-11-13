"""
ONEX Models: Cache System Data Models

Purpose: Define data models for cache access tracking and metrics
Pattern: ONEX 4-Node Architecture - Data Models
File: models_cache.py

Track: Track 3 Phase 2 - Pattern Matching & Caching
ONEX Compliant: Model naming convention (models_*)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ============================================================================
# Cache Access Tracking Models
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class CacheAccessType(str, Enum):
    """Type of cache access operation"""

    HIT = "hit"
    MISS = "miss"
    SET = "set"
    EVICTION = "eviction"
    EXPIRATION = "expiration"


@dataclass
class CacheAccessEvent:
    """
    Record of a cache access operation.

    Tracks individual cache operations for analysis and optimization.

    Attributes:
        event_id: Unique identifier for this access event
        access_type: Type of cache access (hit, miss, set, eviction)
        cache_key: The cache key accessed
        timestamp: When the access occurred
        content_hash: SHA256 hash of the content (for privacy)
        hit_latency_ms: Latency for hit operations (None for misses)
        metadata: Additional contextual information
    """

    event_id: UUID = field(default_factory=uuid4)
    access_type: CacheAccessType = CacheAccessType.MISS
    cache_key: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    content_hash: str = ""
    hit_latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "event_id": str(self.event_id),
            "access_type": self.access_type.value,
            "cache_key": self.cache_key,
            "timestamp": self.timestamp.isoformat(),
            "content_hash": self.content_hash,
            "hit_latency_ms": self.hit_latency_ms,
            "metadata": self.metadata,
        }


@dataclass
class CacheMetrics:
    """
    Cache performance metrics.

    Tracks aggregate cache performance statistics.

    Attributes:
        hits: Total number of cache hits
        misses: Total number of cache misses
        evictions: Total number of evictions (LRU)
        expirations: Total number of TTL expirations
        total_requests: Total cache access requests
        total_latency_ms: Cumulative latency for all hits
        avg_hit_latency_ms: Average latency per cache hit
        current_size: Current number of entries in cache
        max_size: Maximum cache capacity
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_requests: int = 0
    total_latency_ms: float = 0.0
    avg_hit_latency_ms: float = 0.0
    current_size: int = 0
    max_size: int = 1000

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate (0.0-1.0)"""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate (0.0-1.0)"""
        return 1.0 - self.hit_rate

    @property
    def eviction_rate(self) -> float:
        """Calculate eviction rate relative to total requests"""
        if self.total_requests == 0:
            return 0.0
        return self.evictions / self.total_requests

    @property
    def cache_efficiency(self) -> float:
        """
        Overall cache efficiency score (0.0-1.0).

        Combines hit rate with eviction penalty.
        High evictions indicate cache is too small or TTL too high.
        """
        if self.total_requests == 0:
            return 0.0

        # Penalize high eviction rates
        eviction_penalty = min(self.eviction_rate * 0.5, 0.3)

        return max(0.0, self.hit_rate - eviction_penalty)

    def update_from_event(self, event: CacheAccessEvent) -> None:
        """Update metrics from cache access event"""
        self.total_requests += 1

        if event.access_type == CacheAccessType.HIT:
            self.hits += 1
            if event.hit_latency_ms is not None:
                self.total_latency_ms += event.hit_latency_ms
                self.avg_hit_latency_ms = self.total_latency_ms / self.hits

        elif event.access_type == CacheAccessType.MISS:
            self.misses += 1

        elif event.access_type == CacheAccessType.EVICTION:
            self.evictions += 1

        elif event.access_type == CacheAccessType.EXPIRATION:
            self.expirations += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "eviction_rate": self.eviction_rate,
            "cache_efficiency": self.cache_efficiency,
            "avg_hit_latency_ms": self.avg_hit_latency_ms,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "utilization_pct": (
                (self.current_size / self.max_size * 100) if self.max_size > 0 else 0
            ),
        }


@dataclass
class AccessPattern:
    """
    Analyzed access pattern for optimization.

    Attributes:
        hot_keys: Most frequently accessed cache keys
        cold_keys: Least frequently accessed cache keys
        avg_access_interval_sec: Average time between accesses for hot keys
        peak_access_times: Times of day with highest access rates
        content_type_distribution: Distribution of content types accessed
    """

    hot_keys: List[str] = field(default_factory=list)
    cold_keys: List[str] = field(default_factory=list)
    avg_access_interval_sec: float = 0.0
    peak_access_times: List[int] = field(default_factory=list)  # Hours of day (0-23)
    content_type_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "hot_keys_count": len(self.hot_keys),
            "cold_keys_count": len(self.cold_keys),
            "avg_access_interval_sec": self.avg_access_interval_sec,
            "peak_access_times": self.peak_access_times,
            "content_type_distribution": self.content_type_distribution,
        }


@dataclass
class TTLOptimizationResult:
    """
    Result of TTL optimization analysis.

    Attributes:
        recommended_ttl_sec: Recommended TTL in seconds
        current_ttl_sec: Current TTL setting
        expected_hit_rate_improvement: Expected improvement in hit rate
        analysis_window_hours: Time window used for analysis
        confidence_score: Confidence in recommendation (0.0-1.0)
        reasoning: Explanation of recommendation
    """

    recommended_ttl_sec: int = 3600
    current_ttl_sec: int = 3600
    expected_hit_rate_improvement: float = 0.0
    analysis_window_hours: int = 24
    confidence_score: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "recommended_ttl_sec": self.recommended_ttl_sec,
            "current_ttl_sec": self.current_ttl_sec,
            "expected_hit_rate_improvement_pct": self.expected_hit_rate_improvement
            * 100,
            "analysis_window_hours": self.analysis_window_hours,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
        }
