"""
Performance Learning Optimizer for Archon Intelligence Service

Advanced performance optimization with machine learning insights and >10% improvement targets.
Adapted from omnibase_3 PerformanceLearningOptimizer patterns for Archon's architecture.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class OptimizationCategory(Enum):
    """Categories of performance optimizations"""

    QUERY_OPTIMIZATION = "query_optimization"
    CACHING_STRATEGY = "caching_strategy"
    BATCH_PROCESSING = "batch_processing"
    CONCURRENCY_TUNING = "concurrency_tuning"
    MEMORY_OPTIMIZATION = "memory_optimization"
    ALGORITHM_IMPROVEMENT = "algorithm_improvement"


@dataclass
class PerformanceBaseline:
    """Baseline performance metrics for comparison"""

    operation_name: str
    average_response_time_ms: float
    throughput_ops_per_sec: float
    memory_usage_mb: float
    cpu_utilization_percent: float
    error_rate_percent: float
    timestamp: datetime
    sample_size: int


@dataclass
class OptimizationResult:
    """Result of a performance optimization attempt"""

    optimization_id: str
    category: OptimizationCategory
    description: str
    baseline_metrics: PerformanceBaseline
    optimized_metrics: PerformanceBaseline
    improvement_percentage: float
    cost_benefit_ratio: float
    implementation_effort_hours: float
    risk_assessment: str
    success: bool
    applied_at: Optional[datetime] = None


class PerformanceOptimizer:
    """
    Advanced performance optimization with machine learning insights.

    Continuously monitors system performance, identifies bottlenecks,
    and applies optimization strategies with >10% improvement targets.
    """

    def __init__(self, db_connection_string: str = None):
        """Initialize performance optimizer with monitoring capabilities"""

        self.db_connection_string = db_connection_string
        self.optimization_history: List[OptimizationResult] = []
        self.current_baselines: Dict[str, PerformanceBaseline] = {}

        # Performance improvement targets
        self.improvement_targets = {
            "minimum_improvement_percent": 10.0,
            "target_improvement_percent": 25.0,
            "maximum_acceptable_regression_percent": 5.0,
        }

        # Optimization strategies with expected improvements
        self.optimization_strategies = {
            OptimizationCategory.QUERY_OPTIMIZATION: {
                "strategies": [
                    "add_database_indexes",
                    "optimize_join_order",
                    "implement_query_caching",
                    "use_prepared_statements",
                ],
                "expected_improvement": 0.30,
                "implementation_effort": 4.0,
            },
            OptimizationCategory.CACHING_STRATEGY: {
                "strategies": [
                    "implement_redis_caching",
                    "add_memory_cache_layer",
                    "optimize_cache_eviction",
                    "implement_query_result_caching",
                ],
                "expected_improvement": 0.50,
                "implementation_effort": 6.0,
            },
            OptimizationCategory.BATCH_PROCESSING: {
                "strategies": [
                    "implement_bulk_operations",
                    "optimize_batch_sizes",
                    "add_parallel_processing",
                    "implement_streaming_processing",
                ],
                "expected_improvement": 0.40,
                "implementation_effort": 8.0,
            },
            OptimizationCategory.CONCURRENCY_TUNING: {
                "strategies": [
                    "optimize_thread_pool_sizes",
                    "implement_async_processing",
                    "add_connection_pooling",
                    "optimize_lock_contention",
                ],
                "expected_improvement": 0.25,
                "implementation_effort": 5.0,
            },
            OptimizationCategory.MEMORY_OPTIMIZATION: {
                "strategies": [
                    "implement_memory_pooling",
                    "optimize_object_lifecycle",
                    "reduce_memory_allocations",
                    "implement_lazy_loading",
                ],
                "expected_improvement": 0.20,
                "implementation_effort": 6.0,
            },
        }

    async def establish_performance_baseline(
        self, operation_name: str, duration_minutes: int = 10
    ) -> PerformanceBaseline:
        """
        Establish performance baseline for an operation.

        Args:
            operation_name: Name of operation to baseline
            duration_minutes: How long to monitor for baseline

        Returns:
            PerformanceBaseline with current metrics
        """
        logger.info(f"Establishing performance baseline for {operation_name}")

        metrics = []
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        while datetime.now(timezone.utc) < end_time:
            try:
                # Measure current performance
                start_time = time.time()

                # Execute operation (placeholder - would call actual operation)
                await self._execute_test_operation(operation_name)

                response_time_ms = (time.time() - start_time) * 1000

                # Collect system metrics
                memory_usage = await self._get_memory_usage()
                cpu_utilization = await self._get_cpu_utilization()
                error_count = await self._get_error_count(operation_name)

                metrics.append(
                    {
                        "response_time_ms": response_time_ms,
                        "memory_usage_mb": memory_usage,
                        "cpu_utilization_percent": cpu_utilization,
                        "error_count": error_count,
                    }
                )

                # Wait between samples
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error collecting baseline metrics: {e}")
                continue

        # Calculate baseline statistics
        if not metrics:
            raise ValueError(f"Failed to collect baseline metrics for {operation_name}")

        avg_response_time = np.mean([m["response_time_ms"] for m in metrics])
        throughput = 1000 / avg_response_time  # ops per second
        avg_memory = np.mean([m["memory_usage_mb"] for m in metrics])
        avg_cpu = np.mean([m["cpu_utilization_percent"] for m in metrics])
        total_errors = sum(m["error_count"] for m in metrics)
        error_rate = (total_errors / len(metrics)) * 100

        baseline = PerformanceBaseline(
            operation_name=operation_name,
            average_response_time_ms=avg_response_time,
            throughput_ops_per_sec=throughput,
            memory_usage_mb=avg_memory,
            cpu_utilization_percent=avg_cpu,
            error_rate_percent=error_rate,
            timestamp=datetime.now(timezone.utc),
            sample_size=len(metrics),
        )

        self.current_baselines[operation_name] = baseline
        logger.info(
            f"Baseline established: {avg_response_time:.2f}ms avg, {throughput:.2f} ops/sec"
        )

        return baseline

    async def identify_optimization_opportunities(
        self, operation_name: str
    ) -> List[Dict[str, Any]]:
        """
        Identify potential optimization opportunities for an operation.

        Args:
            operation_name: Operation to analyze

        Returns:
            List of optimization opportunities with predicted impact
        """
        if operation_name not in self.current_baselines:
            raise ValueError(f"No baseline found for {operation_name}")

        baseline = self.current_baselines[operation_name]
        opportunities = []

        # Analyze current performance against thresholds
        if baseline.average_response_time_ms > 1000:  # > 1 second
            opportunities.append(
                {
                    "category": OptimizationCategory.QUERY_OPTIMIZATION,
                    "issue": "High response time",
                    "current_value": baseline.average_response_time_ms,
                    "target_value": baseline.average_response_time_ms
                    * 0.7,  # 30% improvement
                    "expected_improvement_percent": 30.0,
                    "priority": "high",
                }
            )

        if baseline.memory_usage_mb > 512:  # > 512 MB
            opportunities.append(
                {
                    "category": OptimizationCategory.MEMORY_OPTIMIZATION,
                    "issue": "High memory usage",
                    "current_value": baseline.memory_usage_mb,
                    "target_value": baseline.memory_usage_mb * 0.8,  # 20% reduction
                    "expected_improvement_percent": 20.0,
                    "priority": "medium",
                }
            )

        if baseline.cpu_utilization_percent > 80:  # > 80% CPU
            opportunities.append(
                {
                    "category": OptimizationCategory.CONCURRENCY_TUNING,
                    "issue": "High CPU utilization",
                    "current_value": baseline.cpu_utilization_percent,
                    "target_value": 70.0,
                    "expected_improvement_percent": 15.0,
                    "priority": "high",
                }
            )

        if baseline.throughput_ops_per_sec < 10:  # < 10 ops/sec
            opportunities.append(
                {
                    "category": OptimizationCategory.BATCH_PROCESSING,
                    "issue": "Low throughput",
                    "current_value": baseline.throughput_ops_per_sec,
                    "target_value": baseline.throughput_ops_per_sec
                    * 1.5,  # 50% improvement
                    "expected_improvement_percent": 50.0,
                    "priority": "high",
                }
            )

        # Sort by expected improvement and priority
        opportunities.sort(
            key=lambda x: (
                {"high": 3, "medium": 2, "low": 1}[x["priority"]],
                x["expected_improvement_percent"],
            ),
            reverse=True,
        )

        logger.info(
            f"Identified {len(opportunities)} optimization opportunities for {operation_name}"
        )
        return opportunities

    async def apply_optimization(
        self,
        operation_name: str,
        optimization_category: OptimizationCategory,
        test_duration_minutes: int = 5,
    ) -> OptimizationResult:
        """
        Apply an optimization and measure its impact.

        Args:
            operation_name: Operation to optimize
            optimization_category: Type of optimization to apply
            test_duration_minutes: How long to test the optimization

        Returns:
            OptimizationResult with before/after metrics
        """
        if operation_name not in self.current_baselines:
            raise ValueError(f"No baseline found for {operation_name}")

        baseline = self.current_baselines[operation_name]
        optimization_id = (
            f"{operation_name}_{optimization_category.value}_{int(time.time())}"
        )

        logger.info(
            f"Applying {optimization_category.value} optimization to {operation_name}"
        )

        try:
            # Apply the optimization (placeholder implementation)
            await self._apply_optimization_strategy(
                operation_name, optimization_category
            )

            # Measure performance after optimization
            await asyncio.sleep(2)  # Allow optimization to take effect

            optimized_baseline = await self.establish_performance_baseline(
                f"{operation_name}_optimized", test_duration_minutes
            )

            # Calculate improvement metrics
            response_time_improvement = (
                (
                    baseline.average_response_time_ms
                    - optimized_baseline.average_response_time_ms
                )
                / baseline.average_response_time_ms
                * 100
            )

            throughput_improvement = (
                (
                    optimized_baseline.throughput_ops_per_sec
                    - baseline.throughput_ops_per_sec
                )
                / baseline.throughput_ops_per_sec
                * 100
            )

            # Use the better of the two improvements
            overall_improvement = max(response_time_improvement, throughput_improvement)

            # Determine if optimization was successful
            success = (
                overall_improvement
                >= self.improvement_targets["minimum_improvement_percent"]
            )

            # Calculate cost-benefit ratio
            strategy_config = self.optimization_strategies[optimization_category]
            cost_benefit_ratio = (
                overall_improvement / strategy_config["implementation_effort"]
            )

            # Assess risk
            risk_assessment = self._assess_optimization_risk(
                baseline, optimized_baseline, optimization_category
            )

            result = OptimizationResult(
                optimization_id=optimization_id,
                category=optimization_category,
                description=f"{optimization_category.value} applied to {operation_name}",
                baseline_metrics=baseline,
                optimized_metrics=optimized_baseline,
                improvement_percentage=overall_improvement,
                cost_benefit_ratio=cost_benefit_ratio,
                implementation_effort_hours=strategy_config["implementation_effort"],
                risk_assessment=risk_assessment,
                success=success,
                applied_at=datetime.now(timezone.utc),
            )

            self.optimization_history.append(result)

            logger.info(
                f"Optimization {'SUCCESSFUL' if success else 'FAILED'}: "
                f"{overall_improvement:.1f}% improvement (target: {self.improvement_targets['minimum_improvement_percent']}%)"
            )

            return result

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            return OptimizationResult(
                optimization_id=optimization_id,
                category=optimization_category,
                description=f"Failed optimization: {str(e)}",
                baseline_metrics=baseline,
                optimized_metrics=baseline,  # No change due to failure
                improvement_percentage=0.0,
                cost_benefit_ratio=0.0,
                implementation_effort_hours=0.0,
                risk_assessment="high",
                success=False,
            )

    async def generate_optimization_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive optimization report.

        Returns:
            Report with optimization history and recommendations
        """
        successful_optimizations = [
            opt for opt in self.optimization_history if opt.success
        ]
        failed_optimizations = [
            opt for opt in self.optimization_history if not opt.success
        ]

        if successful_optimizations:
            avg_improvement = np.mean(
                [opt.improvement_percentage for opt in successful_optimizations]
            )
            best_optimization = max(
                successful_optimizations, key=lambda x: x.improvement_percentage
            )
        else:
            avg_improvement = 0.0
            best_optimization = None

        # Calculate total time saved (estimated)
        total_time_saved_hours = sum(
            opt.improvement_percentage / 100 * opt.implementation_effort_hours
            for opt in successful_optimizations
        )

        report = {
            "summary": {
                "total_optimizations_attempted": len(self.optimization_history),
                "successful_optimizations": len(successful_optimizations),
                "failed_optimizations": len(failed_optimizations),
                "success_rate_percent": len(successful_optimizations)
                / max(len(self.optimization_history), 1)
                * 100,
                "average_improvement_percent": avg_improvement,
                "total_time_saved_hours": total_time_saved_hours,
            },
            "best_optimization": (
                {
                    "optimization_id": (
                        best_optimization.optimization_id if best_optimization else None
                    ),
                    "category": (
                        best_optimization.category.value if best_optimization else None
                    ),
                    "improvement_percent": (
                        best_optimization.improvement_percentage
                        if best_optimization
                        else 0.0
                    ),
                    "cost_benefit_ratio": (
                        best_optimization.cost_benefit_ratio
                        if best_optimization
                        else 0.0
                    ),
                }
                if best_optimization
                else None
            ),
            "optimization_by_category": {},
            "recommendations": [],
        }

        # Group by category
        for category in OptimizationCategory:
            category_opts = [
                opt for opt in successful_optimizations if opt.category == category
            ]
            if category_opts:
                avg_improvement = np.mean(
                    [opt.improvement_percentage for opt in category_opts]
                )
                report["optimization_by_category"][category.value] = {
                    "attempts": len(category_opts),
                    "average_improvement_percent": avg_improvement,
                    "best_improvement_percent": max(
                        opt.improvement_percentage for opt in category_opts
                    ),
                }

        # Generate recommendations
        if avg_improvement < self.improvement_targets["target_improvement_percent"]:
            report["recommendations"].append(
                f"Overall improvement ({avg_improvement:.1f}%) below target "
                f"({self.improvement_targets['target_improvement_percent']}%). "
                "Consider more aggressive optimization strategies."
            )

        if len(failed_optimizations) > len(successful_optimizations):
            report["recommendations"].append(
                "High failure rate detected. Review optimization strategies and implementation approach."
            )

        # Identify high-impact categories for future focus
        if report["optimization_by_category"]:
            best_category = max(
                report["optimization_by_category"].items(),
                key=lambda x: x[1]["average_improvement_percent"],
            )
            report["recommendations"].append(
                f"Focus on {best_category[0]} optimizations - showing best results "
                f"({best_category[1]['average_improvement_percent']:.1f}% avg improvement)"
            )

        return report

    # Helper methods for optimization implementation

    async def _execute_test_operation(self, operation_name: str):
        """Execute a test operation for baseline measurement"""
        # Placeholder - would execute actual operation
        await asyncio.sleep(
            0.1 + np.random.random() * 0.2
        )  # Simulate variable operation time

    async def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        # Placeholder - would get actual memory usage
        return 256 + np.random.random() * 256

    async def _get_cpu_utilization(self) -> float:
        """Get current CPU utilization percentage"""
        # Placeholder - would get actual CPU usage
        return 30 + np.random.random() * 50

    async def _get_error_count(self, operation_name: str) -> int:
        """Get error count for operation"""
        # Placeholder - would get actual error count
        return int(np.random.random() * 3)

    async def _apply_optimization_strategy(
        self, operation_name: str, category: OptimizationCategory
    ):
        """Apply specific optimization strategy"""
        # Placeholder - would implement actual optimization
        logger.info(f"Applying {category.value} strategy to {operation_name}")
        await asyncio.sleep(1)  # Simulate optimization time

    def _assess_optimization_risk(
        self,
        baseline: PerformanceBaseline,
        optimized: PerformanceBaseline,
        category: OptimizationCategory,
    ) -> str:
        """Assess risk level of optimization"""

        # Check for regressions
        response_time_regression = (
            optimized.average_response_time_ms > baseline.average_response_time_ms
        )
        error_rate_increase = optimized.error_rate_percent > baseline.error_rate_percent

        if response_time_regression or error_rate_increase:
            return "high"

        # Category-specific risk assessment
        high_risk_categories = [
            OptimizationCategory.CONCURRENCY_TUNING,
            OptimizationCategory.BATCH_PROCESSING,
        ]

        if category in high_risk_categories:
            return "medium"

        return "low"
