"""
ONEX Contract Models: Cache Optimization Operations

Purpose: Define contracts for cache optimization Orchestrator node operations
Pattern: ONEX 4-Node Architecture - Contract Models
File: model_contract_cache_optimizer.py

Track: Track 3 Phase 2 - Cache Optimization & Analysis
ONEX Compliant: Contract naming convention (model_contract_*)
"""

# Import from phase1_foundation storage contracts
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

# ============================================================================
# Import Base Contracts from Phase 1
# ============================================================================


phase1_path = Path(__file__).parent.parent / "phase1_foundation" / "storage"
sys.path.insert(0, str(phase1_path))

from uuid import UUID, uuid4

from model_contract_pattern_storage import ModelContractBase

# ============================================================================
# Cache Optimizer Operations
# ============================================================================


# NOTE: correlation_id support enabled for tracing
class CacheOptimizerOperation(str, Enum):
    """Cache optimizer operation types"""

    ANALYZE_HIT_RATE = "analyze_hit_rate"
    OPTIMIZE_TTL = "optimize_ttl"
    BENCHMARK_PERFORMANCE = "benchmark_performance"
    ANALYZE_ACCESS_PATTERNS = "analyze_access_patterns"
    WARM_CACHE = "warm_cache"
    COMPARE_EVICTION_POLICIES = "compare_eviction_policies"
    GENERATE_OPTIMIZATION_REPORT = "generate_optimization_report"


# ============================================================================
# Orchestrator Contract Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelContractOrchestrator(ModelContractBase):
    """
    ONEX Orchestrator contract for complex workflow operations.

    Orchestrator nodes handle:
    - Multi-step workflows
    - Coordination between nodes
    - Complex business logic
    - Analysis and optimization

    Attributes:
        operation: Specific orchestration operation to execute
        node_type: Fixed as 'orchestrator' for Orchestrator nodes
    """

    operation: str = "orchestrate"
    node_type: str = "orchestrator"


# ============================================================================
# Cache Optimizer Contract (Specialized Orchestrator Contract)
# ============================================================================


@dataclass
class ModelContractCacheOptimizer(ModelContractOrchestrator):
    """
    Specialized contract for cache optimization operations.

    Extends ModelContractOrchestrator with cache-specific fields for:
    - Hit rate analysis
    - TTL optimization
    - Performance benchmarking
    - Access pattern analysis

    Operations:
        - analyze_hit_rate: Analyze cache hit rates over time windows
        - optimize_ttl: Optimize TTL based on access patterns
        - benchmark_performance: Benchmark cache performance
        - analyze_access_patterns: Analyze access patterns for optimization
        - warm_cache: Warm cache with historical data
        - compare_eviction_policies: Compare LRU vs LFU eviction
        - generate_optimization_report: Generate comprehensive optimization report

    Attributes:
        operation: One of CacheOptimizerOperation enum values
        time_window_hours: Time window for analysis (default: 24)
        target_hit_rate: Target hit rate for optimization (default: 0.8)
        benchmark_requests: Number of requests for benchmarking (default: 1000)
        analysis_params: Additional analysis parameters

    Example - Analyze Hit Rate:
        >>> contract = ModelContractCacheOptimizer(
        ...     name="analyze_cache_hit_rate",
        ...     operation="analyze_hit_rate",
        ...     time_window_hours=24
        ... )

    Example - Optimize TTL:
        >>> contract = ModelContractCacheOptimizer(
        ...     name="optimize_ttl_for_80pct_hit_rate",
        ...     operation="optimize_ttl",
        ...     target_hit_rate=0.8,
        ...     time_window_hours=48
        ... )

    Example - Benchmark Performance:
        >>> contract = ModelContractCacheOptimizer(
        ...     name="benchmark_cache_performance",
        ...     operation="benchmark_performance",
        ...     benchmark_requests=1000
        ... )
    """

    # Cache-specific fields
    operation: str = CacheOptimizerOperation.ANALYZE_HIT_RATE.value
    time_window_hours: int = 24
    target_hit_rate: float = 0.8
    benchmark_requests: int = 1000
    analysis_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate contract after initialization."""
        # Set default name if not provided
        if not self.name:
            self.name = f"cache_optimizer_{self.operation}"

        # Set default description
        if not self.description:
            self.description = f"Cache optimization operation: {self.operation}"

        # Validate operation-specific requirements
        if self.operation == CacheOptimizerOperation.ANALYZE_HIT_RATE.value:
            if self.time_window_hours <= 0:
                raise ValueError("Time window must be positive")

        elif self.operation == CacheOptimizerOperation.OPTIMIZE_TTL.value:
            if not (0.0 < self.target_hit_rate <= 1.0):
                raise ValueError("Target hit rate must be between 0.0 and 1.0")
            if self.time_window_hours <= 0:
                raise ValueError("Time window must be positive")

        elif self.operation == CacheOptimizerOperation.BENCHMARK_PERFORMANCE.value:
            if self.benchmark_requests <= 0:
                raise ValueError("Benchmark requests must be positive")

        elif self.operation == CacheOptimizerOperation.WARM_CACHE.value:
            if "content_samples" not in self.analysis_params:
                raise ValueError(
                    "Warm cache operation requires 'content_samples' in analysis_params"
                )


# ============================================================================
# Optimization Result Models
# ============================================================================


@dataclass
class ModelHitRateAnalysis:
    """
    Hit rate analysis result.

    Attributes:
        time_window_hours: Analysis time window
        total_requests: Total requests in window
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        hit_rate: Overall hit rate (0.0-1.0)
        hit_rate_trend: Trend direction (increasing, decreasing, stable)
        recommendations: Optimization recommendations
    """

    time_window_hours: int
    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    hit_rate_trend: str
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "time_window_hours": self.time_window_hours,
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.hit_rate,
            "hit_rate_pct": self.hit_rate * 100,
            "hit_rate_trend": self.hit_rate_trend,
            "recommendations": self.recommendations,
        }


@dataclass
class ModelTTLOptimization:
    """
    TTL optimization result.

    Attributes:
        current_ttl_sec: Current TTL setting
        recommended_ttl_sec: Optimized TTL recommendation
        expected_hit_rate_improvement: Expected improvement
        confidence_score: Confidence in recommendation (0.0-1.0)
        reasoning: Explanation of recommendation
    """

    current_ttl_sec: int
    recommended_ttl_sec: int
    expected_hit_rate_improvement: float
    confidence_score: float
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "current_ttl_sec": self.current_ttl_sec,
            "recommended_ttl_sec": self.recommended_ttl_sec,
            "expected_hit_rate_improvement_pct": self.expected_hit_rate_improvement
            * 100,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
        }


@dataclass
class ModelPerformanceBenchmark:
    """
    Performance benchmark result.

    Attributes:
        total_requests: Total benchmark requests
        avg_latency_ms: Average latency
        p50_latency_ms: 50th percentile latency
        p95_latency_ms: 95th percentile latency
        p99_latency_ms: 99th percentile latency
        throughput_req_per_sec: Throughput in requests per second
        hit_rate: Cache hit rate during benchmark
    """

    total_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_req_per_sec: float
    hit_rate: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "total_requests": self.total_requests,
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "throughput_req_per_sec": self.throughput_req_per_sec,
            "hit_rate": self.hit_rate,
            "hit_rate_pct": self.hit_rate * 100,
        }
