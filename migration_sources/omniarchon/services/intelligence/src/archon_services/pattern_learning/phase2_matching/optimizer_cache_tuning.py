"""
Cache Optimization & Analysis - ONEX Orchestrator Node

Analyzes cache performance and provides optimization recommendations
for TTL, eviction policies, and cache warming strategies.

ONEX Pattern: Orchestrator (complex workflow coordination)
Performance Target: >80% cache hit rate with optimized settings

File: optimizer_cache_tuning.py
Track: Track 3 Phase 2 - Agent 5: Cache Optimization & Analysis
"""

import logging
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.archon_services.models import ModelResult
from src.archon_services.pattern_learning.phase2_matching.model_contract_cache_optimizer import (
    CacheOptimizerOperation,
    ModelContractCacheOptimizer,
    ModelHitRateAnalysis,
    ModelPerformanceBenchmark,
    ModelTTLOptimization,
)
from src.archon_services.pattern_learning.phase2_matching.models_cache import (
    AccessPattern,
    CacheAccessEvent,
    CacheAccessType,
)
from src.archon_services.pattern_learning.phase2_matching.reducer_semantic_cache import (
    SemanticAnalysisResult,
    SemanticCacheReducer,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ONEX Orchestrator Node: Cache Optimizer
# ============================================================================


class NodeCacheOptimizerOrchestrator:
    """
    Cache optimization and analysis orchestrator node.

    ONEX Node Type: Orchestrator (complex workflow coordination)

    Responsibilities:
    - Analyze cache hit rates over time windows
    - Optimize TTL based on access patterns
    - Benchmark cache performance
    - Analyze access patterns for optimization insights
    - Provide cache warming strategies
    - Compare eviction policy effectiveness

    Performance Targets:
    - >80% cache hit rate in production
    - <500ms average latency with cache
    - TTL optimization improves hit rate measurably

    Architecture:
    - Coordinates between cache metrics, access logs, and optimization algorithms
    - Implements multi-step analysis workflows
    - Provides actionable recommendations based on data analysis
    """

    def __init__(self, cache: SemanticCacheReducer):
        """
        Initialize cache optimizer orchestrator.

        Args:
            cache: SemanticCacheReducer instance to optimize
        """
        self.cache = cache
        self.access_log: List[CacheAccessEvent] = []
        self.access_timestamps: defaultdict[str, List[float]] = defaultdict(list)
        self.access_frequency: Counter[str] = Counter()

        logger.info("NodeCacheOptimizerOrchestrator initialized")

    # ========================================================================
    # ONEX Orchestrator Execution Method
    # ========================================================================

    async def execute_orchestration(
        self, contract: ModelContractCacheOptimizer
    ) -> ModelResult:
        """
        Execute cache optimization orchestration.

        ONEX signature for Orchestrator nodes.

        Args:
            contract: Cache optimizer contract with operation details

        Returns:
            ModelResult with optimization results or error
        """
        try:
            operation = contract.operation

            # Route to appropriate orchestration workflow
            if operation == CacheOptimizerOperation.ANALYZE_HIT_RATE.value:
                result_data = await self._orchestrate_hit_rate_analysis(contract)

            elif operation == CacheOptimizerOperation.OPTIMIZE_TTL.value:
                result_data = await self._orchestrate_ttl_optimization(contract)

            elif operation == CacheOptimizerOperation.BENCHMARK_PERFORMANCE.value:
                result_data = await self._orchestrate_performance_benchmark(contract)

            elif operation == CacheOptimizerOperation.ANALYZE_ACCESS_PATTERNS.value:
                result_data = await self._orchestrate_access_pattern_analysis(contract)

            elif operation == CacheOptimizerOperation.WARM_CACHE.value:
                result_data = await self._orchestrate_cache_warming(contract)

            elif (
                operation == CacheOptimizerOperation.GENERATE_OPTIMIZATION_REPORT.value
            ):
                result_data = await self._orchestrate_optimization_report(contract)

            else:
                return ModelResult(
                    success=False,
                    error=f"Unknown cache optimizer operation: {operation}",
                    metadata={"correlation_id": str(contract.correlation_id)},
                )

            return ModelResult(
                success=True,
                data=result_data,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Cache optimization failed: {e}", exc_info=True)
            return ModelResult(
                success=False,
                error=str(e),
                metadata={"correlation_id": str(contract.correlation_id)},
            )

    # ========================================================================
    # Orchestration Workflows
    # ========================================================================

    async def _orchestrate_hit_rate_analysis(
        self, contract: ModelContractCacheOptimizer
    ) -> Dict[str, Any]:
        """
        Orchestrate hit rate analysis workflow.

        Steps:
        1. Filter access events by time window
        2. Calculate hit/miss statistics
        3. Analyze hit rate trends
        4. Generate recommendations

        Args:
            contract: Contract with time_window_hours parameter

        Returns:
            Hit rate analysis results
        """
        time_window_hours = contract.time_window_hours
        cutoff_time = time.time() - (time_window_hours * 3600)

        # Filter events within time window
        recent_events = [
            event
            for event in self.access_log
            if event.timestamp.timestamp() >= cutoff_time
        ]

        # Calculate statistics
        total_requests = len(
            [
                e
                for e in recent_events
                if e.access_type in [CacheAccessType.HIT, CacheAccessType.MISS]
            ]
        )
        cache_hits = len(
            [e for e in recent_events if e.access_type == CacheAccessType.HIT]
        )
        cache_misses = len(
            [e for e in recent_events if e.access_type == CacheAccessType.MISS]
        )

        hit_rate = cache_hits / total_requests if total_requests > 0 else 0.0

        # Analyze trend (compare first half vs second half of window)
        if len(recent_events) >= 10:
            midpoint = len(recent_events) // 2
            first_half = recent_events[:midpoint]
            second_half = recent_events[midpoint:]

            first_half_requests = len(
                [
                    e
                    for e in first_half
                    if e.access_type in [CacheAccessType.HIT, CacheAccessType.MISS]
                ]
            )
            second_half_requests = len(
                [
                    e
                    for e in second_half
                    if e.access_type in [CacheAccessType.HIT, CacheAccessType.MISS]
                ]
            )

            first_half_hits = len(
                [e for e in first_half if e.access_type == CacheAccessType.HIT]
            )
            second_half_hits = len(
                [e for e in second_half if e.access_type == CacheAccessType.HIT]
            )

            first_hit_rate = (
                first_half_hits / first_half_requests
                if first_half_requests > 0
                else 0.0
            )
            second_hit_rate = (
                second_half_hits / second_half_requests
                if second_half_requests > 0
                else 0.0
            )

            if second_hit_rate > first_hit_rate + 0.05:
                trend = "increasing"
            elif second_hit_rate < first_hit_rate - 0.05:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Generate recommendations
        recommendations = []
        if hit_rate < 0.6:
            recommendations.append(
                "Hit rate is low (<60%). Consider increasing cache size or TTL."
            )
        elif hit_rate < 0.8:
            recommendations.append(
                "Hit rate is moderate (60-80%). Some optimization possible."
            )
        else:
            recommendations.append("Hit rate is good (>80%). Cache is performing well.")

        if trend == "decreasing":
            recommendations.append(
                "Hit rate is decreasing. Investigate cache churn or changing access patterns."
            )

        # Create result model
        analysis = ModelHitRateAnalysis(
            time_window_hours=time_window_hours,
            total_requests=total_requests,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            hit_rate=hit_rate,
            hit_rate_trend=trend,
            recommendations=recommendations,
        )

        return analysis.to_dict()

    async def _orchestrate_ttl_optimization(
        self, contract: ModelContractCacheOptimizer
    ) -> Dict[str, Any]:
        """
        Orchestrate TTL optimization workflow.

        Steps:
        1. Analyze access patterns and inter-access intervals
        2. Calculate optimal TTL for target hit rate
        3. Estimate expected improvement
        4. Provide confidence score and reasoning

        Args:
            contract: Contract with target_hit_rate and time_window_hours

        Returns:
            TTL optimization results
        """
        target_hit_rate = contract.target_hit_rate
        current_ttl = self.cache.default_ttl

        # Analyze access patterns
        access_intervals: List[float] = []
        for cache_key, timestamps in self.access_timestamps.items():
            if len(timestamps) >= 2:
                sorted_times = sorted(timestamps)
                for i in range(1, len(sorted_times)):
                    interval = sorted_times[i] - sorted_times[i - 1]
                    access_intervals.append(interval)

        if not access_intervals:
            # No data - return conservative recommendation
            return ModelTTLOptimization(
                current_ttl_sec=current_ttl,
                recommended_ttl_sec=current_ttl,
                expected_hit_rate_improvement=0.0,
                confidence_score=0.0,
                reasoning="Insufficient access pattern data for optimization",
            ).to_dict()

        # Calculate statistics
        avg_interval = statistics.mean(access_intervals)
        median_interval = statistics.median(access_intervals)

        # Determine optimal TTL based on access patterns
        # Strategy: Set TTL to capture majority of re-accesses
        if target_hit_rate >= 0.9:
            # High target - use 95th percentile interval
            sorted_intervals = sorted(access_intervals)
            percentile_95 = sorted_intervals[int(len(sorted_intervals) * 0.95)]
            recommended_ttl = int(percentile_95)
        elif target_hit_rate >= 0.8:
            # Good target - use 90th percentile interval
            sorted_intervals = sorted(access_intervals)
            percentile_90 = sorted_intervals[int(len(sorted_intervals) * 0.90)]
            recommended_ttl = int(percentile_90)
        else:
            # Moderate target - use median interval
            recommended_ttl = int(median_interval * 1.5)

        # Ensure reasonable bounds
        recommended_ttl = max(300, min(recommended_ttl, 86400))  # 5 min to 24 hours

        # Estimate improvement
        current_hit_rate = self.cache.metrics.hit_rate
        if current_hit_rate < target_hit_rate:
            expected_improvement = min(
                target_hit_rate - current_hit_rate, 0.2
            )  # Cap at 20% improvement
        else:
            expected_improvement = 0.0

        # Calculate confidence based on data quality
        confidence = min(
            1.0, len(access_intervals) / 1000.0
        )  # Higher confidence with more data

        # Generate reasoning
        if recommended_ttl > current_ttl:
            reasoning = (
                f"Increasing TTL from {current_ttl}s to {recommended_ttl}s to capture more re-accesses. "
                f"Average re-access interval is {avg_interval:.1f}s."
            )
        elif recommended_ttl < current_ttl:
            reasoning = (
                f"Decreasing TTL from {current_ttl}s to {recommended_ttl}s to reduce stale entries. "
                f"Median re-access interval is {median_interval:.1f}s."
            )
        else:
            reasoning = (
                f"Current TTL ({current_ttl}s) is optimal for observed access patterns."
            )

        return ModelTTLOptimization(
            current_ttl_sec=current_ttl,
            recommended_ttl_sec=recommended_ttl,
            expected_hit_rate_improvement=expected_improvement,
            confidence_score=confidence,
            reasoning=reasoning,
        ).to_dict()

    async def _orchestrate_performance_benchmark(
        self, contract: ModelContractCacheOptimizer
    ) -> Dict[str, Any]:
        """
        Orchestrate performance benchmark workflow.

        Steps:
        1. Generate synthetic cache access patterns
        2. Measure latencies for cache hits and misses
        3. Calculate percentiles and throughput
        4. Analyze cache effectiveness during benchmark

        Args:
            contract: Contract with benchmark_requests parameter

        Returns:
            Performance benchmark results
        """
        num_requests = contract.benchmark_requests

        # Generate test content (mix of repeated and unique)
        test_contents: List[str] = []
        for i in range(num_requests):
            if i < num_requests * 0.3:  # 30% unique (should miss)
                test_contents.append(f"unique_content_{i}")
            else:  # 70% repeated (should hit after first access)
                test_contents.append(f"repeated_content_{i % 100}")

        # Shuffle to simulate realistic access pattern
        import random

        random.shuffle(test_contents)

        # Benchmark
        latencies: List[float] = []
        hits = 0
        misses = 0

        start_time = time.time()

        for content in test_contents:
            request_start = time.time()

            # Simulate cache access
            result = await self.cache.get(content)

            if result is None:
                # Cache miss - simulate creating result
                misses += 1
                dummy_result = SemanticAnalysisResult(
                    content_hash=self.cache.get_cache_key(content),
                    keywords=["test"],
                    intent="testing",
                    confidence=0.9,
                )
                await self.cache.set(content, dummy_result)
            else:
                hits += 1

            request_end = time.time()
            latencies.append((request_end - request_start) * 1000)  # Convert to ms

        end_time = time.time()
        total_time = end_time - start_time

        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        sorted_latencies = sorted(latencies)
        p50 = sorted_latencies[len(sorted_latencies) // 2]
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        throughput = num_requests / total_time
        hit_rate = hits / num_requests if num_requests > 0 else 0.0

        return ModelPerformanceBenchmark(
            total_requests=num_requests,
            avg_latency_ms=avg_latency,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            throughput_req_per_sec=throughput,
            hit_rate=hit_rate,
        ).to_dict()

    async def _orchestrate_access_pattern_analysis(
        self, contract: ModelContractCacheOptimizer
    ) -> Dict[str, Any]:
        """
        Orchestrate access pattern analysis workflow.

        Analyzes:
        - Hot vs cold keys
        - Access frequency distribution
        - Temporal access patterns
        - Content type distribution

        Args:
            contract: Analysis contract

        Returns:
            Access pattern analysis results
        """
        # Identify hot and cold keys
        hot_threshold = 10  # Keys accessed 10+ times are "hot"
        hot_keys = [
            key
            for key, count in self.access_frequency.items()
            if count >= hot_threshold
        ]
        cold_keys = [key for key, count in self.access_frequency.items() if count == 1]

        # Calculate average access interval for hot keys
        avg_intervals = []
        for key in hot_keys:
            if key in self.access_timestamps and len(self.access_timestamps[key]) >= 2:
                timestamps = sorted(self.access_timestamps[key])
                intervals = [
                    timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))
                ]
                avg_intervals.extend(intervals)

        avg_access_interval = statistics.mean(avg_intervals) if avg_intervals else 0.0

        # Analyze peak access times (by hour)
        hour_counts = Counter()
        for event in self.access_log:
            hour = event.timestamp.hour
            hour_counts[hour] += 1

        peak_hours = [hour for hour, _ in hour_counts.most_common(3)]

        # Content type distribution (from metadata)
        content_types = Counter()
        for event in self.access_log:
            content_type = event.metadata.get("content_type", "unknown")
            content_types[content_type] += 1

        pattern = AccessPattern(
            hot_keys=hot_keys[:10],  # Top 10 hot keys
            cold_keys=cold_keys[:10],  # Sample 10 cold keys
            avg_access_interval_sec=avg_access_interval,
            peak_access_times=sorted(peak_hours),
            content_type_distribution=dict(content_types),
        )

        return pattern.to_dict()

    async def _orchestrate_cache_warming(
        self, contract: ModelContractCacheOptimizer
    ) -> Dict[str, Any]:
        """
        Orchestrate cache warming workflow.

        Pre-populates cache with frequently accessed content.

        Args:
            contract: Contract with content_samples in analysis_params

        Returns:
            Cache warming results
        """
        content_samples = contract.analysis_params.get("content_samples", [])

        warmed_count = 0
        failed_count = 0

        for content in content_samples:
            try:
                # Create dummy result for warming
                dummy_result = SemanticAnalysisResult(
                    content_hash=self.cache.get_cache_key(content),
                    keywords=["warmed"],
                    intent="cache_warming",
                    confidence=1.0,
                )
                await self.cache.set(content, dummy_result)
                warmed_count += 1
            except Exception as e:
                logger.warning(f"Cache warming failed for sample: {e}")
                failed_count += 1

        return {
            "total_samples": len(content_samples),
            "warmed_count": warmed_count,
            "failed_count": failed_count,
            "success_rate": (
                warmed_count / len(content_samples) if content_samples else 0.0
            ),
        }

    async def _orchestrate_optimization_report(
        self, contract: ModelContractCacheOptimizer
    ) -> Dict[str, Any]:
        """
        Orchestrate comprehensive optimization report generation.

        Combines multiple analyses into single report.

        Args:
            contract: Analysis contract

        Returns:
            Comprehensive optimization report
        """
        # Run all analyses
        hit_rate_contract = ModelContractCacheOptimizer(
            name="hit_rate_analysis",
            operation=CacheOptimizerOperation.ANALYZE_HIT_RATE.value,
            time_window_hours=contract.time_window_hours,
        )
        hit_rate_analysis = await self._orchestrate_hit_rate_analysis(hit_rate_contract)

        ttl_contract = ModelContractCacheOptimizer(
            name="ttl_optimization",
            operation=CacheOptimizerOperation.OPTIMIZE_TTL.value,
            target_hit_rate=contract.target_hit_rate,
        )
        ttl_optimization = await self._orchestrate_ttl_optimization(ttl_contract)

        pattern_contract = ModelContractCacheOptimizer(
            name="access_patterns",
            operation=CacheOptimizerOperation.ANALYZE_ACCESS_PATTERNS.value,
        )
        access_patterns = await self._orchestrate_access_pattern_analysis(
            pattern_contract
        )

        # Compile report
        return {
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "cache_metrics": self.cache.metrics.to_dict(),
            "hit_rate_analysis": hit_rate_analysis,
            "ttl_optimization": ttl_optimization,
            "access_patterns": access_patterns,
            "overall_recommendations": self._generate_overall_recommendations(
                hit_rate_analysis, ttl_optimization, access_patterns
            ),
        }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _generate_overall_recommendations(
        self,
        hit_rate_analysis: Dict[str, Any],
        ttl_optimization: Dict[str, Any],
        access_patterns: Dict[str, Any],
    ) -> List[str]:
        """Generate overall optimization recommendations"""
        recommendations = []

        # Hit rate recommendations
        hit_rate = hit_rate_analysis.get("hit_rate", 0.0)
        if hit_rate < 0.8:
            recommendations.append(
                f"PRIORITY: Improve cache hit rate ({hit_rate*100:.1f}% → target 80%). "
                f"Consider TTL optimization and cache size increase."
            )

        # TTL recommendations
        ttl_improvement = ttl_optimization.get("expected_hit_rate_improvement_pct", 0.0)
        if ttl_improvement > 5.0:
            recommendations.append(
                f"Implement recommended TTL ({ttl_optimization['recommended_ttl_sec']}s) "
                f"for estimated {ttl_improvement:.1f}% hit rate improvement."
            )

        # Access pattern recommendations
        hot_keys_count = access_patterns.get("hot_keys_count", 0)
        if hot_keys_count > self.cache.max_size * 0.8:
            recommendations.append(
                f"Consider increasing cache size. Hot keys ({hot_keys_count}) approaching "
                f"cache capacity ({self.cache.max_size})."
            )

        return recommendations

    # ========================================================================
    # Public Analysis Methods (convenience wrappers)
    # ========================================================================

    async def analyze_hit_rate(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Analyze cache hit rate over time window.

        Convenience wrapper for direct usage.

        Args:
            time_window_hours: Hours to analyze

        Returns:
            Hit rate analysis results
        """
        contract = ModelContractCacheOptimizer(
            name="analyze_hit_rate",
            operation=CacheOptimizerOperation.ANALYZE_HIT_RATE.value,
            time_window_hours=time_window_hours,
        )
        result = await self.execute_orchestration(contract)
        return result.data if result.success else {"error": result.error}

    async def optimize_ttl(self, target_hit_rate: float = 0.8) -> Dict[str, Any]:
        """
        Optimize TTL to achieve target hit rate.

        Convenience wrapper for direct usage.

        Args:
            target_hit_rate: Target hit rate (0.0-1.0)

        Returns:
            TTL optimization results with recommended TTL
        """
        contract = ModelContractCacheOptimizer(
            name="optimize_ttl",
            operation=CacheOptimizerOperation.OPTIMIZE_TTL.value,
            target_hit_rate=target_hit_rate,
        )
        result = await self.execute_orchestration(contract)
        return result.data if result.success else {"error": result.error}

    async def benchmark_performance(self, num_requests: int = 1000) -> Dict[str, Any]:
        """
        Benchmark cache performance.

        Convenience wrapper for direct usage.

        Args:
            num_requests: Number of benchmark requests

        Returns:
            Performance benchmark results
        """
        contract = ModelContractCacheOptimizer(
            name="benchmark_performance",
            operation=CacheOptimizerOperation.BENCHMARK_PERFORMANCE.value,
            benchmark_requests=num_requests,
        )
        result = await self.execute_orchestration(contract)
        return result.data if result.success else {"error": result.error}

    # ========================================================================
    # Access Event Tracking
    # ========================================================================

    def track_access(self, event: CacheAccessEvent) -> None:
        """
        Track cache access event for analysis.

        Args:
            event: Cache access event to log
        """
        self.access_log.append(event)

        # Update access tracking structures
        if event.access_type in [CacheAccessType.HIT, CacheAccessType.MISS]:
            self.access_timestamps[event.cache_key].append(event.timestamp.timestamp())
            self.access_frequency[event.cache_key] += 1

        # Limit log size (keep last 10000 events)
        if len(self.access_log) > 10000:
            self.access_log = self.access_log[-10000:]


# ============================================================================
# Convenience Alias (ONEX naming convention)
# ============================================================================

CacheOptimizer = NodeCacheOptimizerOrchestrator
