"""
Optimization Opportunity Identification

Analyzes performance baselines to identify slow operations and generate
ROI-ranked optimization recommendations.

Features:
- Slow operation identification (p95 > threshold)
- Improvement potential estimation (high: 40-60%, medium: 20-40%, low: 10-20%)
- Effort level estimation (low: 1.0, medium: 2.0, high: 3.0)
- ROI calculation (improvement / effort_score)
- Priority classification (critical, high, medium, low)
- Specific, actionable recommendations

Phase 5C: Performance Intelligence
Created: 2025-10-15
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.archon_services.performance.baseline_service import PerformanceBaselineService

logger = logging.getLogger(__name__)


@dataclass
class OptimizationOpportunity:
    """
    Optimization opportunity recommendation.

    Represents a performance optimization opportunity with estimated
    improvement potential, implementation effort, ROI score, and
    specific actionable recommendations.
    """

    operation: str
    current_performance: Dict[str, float]  # p50, p95, p99, mean, std_dev
    estimated_improvement: float  # percentage (0-100)
    effort_level: str  # "low", "medium", "high"
    roi_score: float  # improvement / effort_score
    recommendations: List[str]  # Specific actionable suggestions
    priority: str  # "critical", "high", "medium", "low"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "operation": self.operation,
            "current_performance": self.current_performance,
            "estimated_improvement": self.estimated_improvement,
            "effort_level": self.effort_level,
            "roi_score": self.roi_score,
            "recommendations": self.recommendations,
            "priority": self.priority,
        }


class OptimizationAnalyzer:
    """
    Identify and prioritize performance optimization opportunities.

    Analyzes performance baseline data to find slow operations and
    generate ROI-ranked recommendations for improvement.

    Algorithm:
    1. Identify slow operations (p95 > threshold)
    2. Estimate improvement potential based on operation characteristics
    3. Estimate implementation effort
    4. Calculate ROI score (improvement / effort)
    5. Generate specific, actionable recommendations
    6. Prioritize by ROI and criticality

    Performance Targets:
    - Opportunity identification: <100ms for 10 operations
    - Analysis per operation: <20ms
    - Memory usage: <10MB
    """

    # Improvement estimation thresholds
    HIGH_IMPROVEMENT_THRESHOLD = 1000.0  # ms (p95)
    MEDIUM_IMPROVEMENT_THRESHOLD = 500.0  # ms (p95)
    HIGH_VARIANCE_THRESHOLD = 1.0  # std_dev / mean ratio

    # Effort estimation scores
    EFFORT_SCORES = {
        "low": 1.0,
        "medium": 2.0,
        "high": 3.0,
    }

    def __init__(self, baseline_service: PerformanceBaselineService):
        """
        Initialize optimization analyzer.

        Args:
            baseline_service: Performance baseline service for accessing metrics
        """
        self.baseline_service = baseline_service
        logger.info("OptimizationAnalyzer initialized")

    async def identify_opportunities(
        self, min_p95_ms: float = 500.0, max_recommendations: Optional[int] = None
    ) -> List[OptimizationOpportunity]:
        """
        Identify optimization opportunities from performance baselines.

        Analyzes all operations with established baselines and identifies
        those exceeding the p95 threshold. Returns opportunities sorted
        by ROI score (highest first).

        Args:
            min_p95_ms: Minimum p95 threshold for slow operations (default: 500ms)
            max_recommendations: Maximum number of opportunities to return (default: None)

        Returns:
            List of optimization opportunities sorted by ROI (highest first)
        """
        opportunities = []

        # Get all operations with baselines
        all_baselines = await self.baseline_service.get_all_baselines()

        logger.debug(
            f"Analyzing {len(all_baselines)} operations for optimization opportunities "
            f"(min_p95={min_p95_ms}ms)"
        )

        # Analyze each operation
        for operation, metrics in all_baselines.items():
            # Check if operation exceeds threshold
            if metrics.get("p95", 0.0) > min_p95_ms:
                opportunity = await self._analyze_opportunity(operation, metrics)
                if opportunity:
                    opportunities.append(opportunity)

        # Sort by ROI score (highest first)
        opportunities.sort(key=lambda x: x.roi_score, reverse=True)

        # Limit results if requested
        if max_recommendations is not None:
            opportunities = opportunities[:max_recommendations]

        logger.info(
            f"Identified {len(opportunities)} optimization opportunities "
            f"(threshold: {min_p95_ms}ms)"
        )

        return opportunities

    async def _analyze_opportunity(
        self, operation: str, metrics: Dict[str, float]
    ) -> Optional[OptimizationOpportunity]:
        """
        Analyze a specific operation for optimization potential.

        Args:
            operation: Operation name
            metrics: Performance metrics (p50, p95, p99, mean, std_dev, sample_size)

        Returns:
            OptimizationOpportunity if analysis successful, None otherwise
        """
        try:
            # Estimate improvement potential
            estimated_improvement = await self._estimate_improvement(operation, metrics)

            # Estimate implementation effort
            effort_level = await self._estimate_effort(operation, metrics)

            # Calculate ROI score
            roi_score = self._calculate_roi(estimated_improvement, effort_level)

            # Generate recommendations
            recommendations = await self._generate_recommendations(operation, metrics)

            # Determine priority
            priority = self._determine_priority(metrics, roi_score)

            opportunity = OptimizationOpportunity(
                operation=operation,
                current_performance=metrics.copy(),
                estimated_improvement=estimated_improvement,
                effort_level=effort_level,
                roi_score=roi_score,
                recommendations=recommendations,
                priority=priority,
            )

            logger.debug(
                f"Analyzed {operation}: improvement={estimated_improvement:.1f}%, "
                f"effort={effort_level}, ROI={roi_score:.2f}, priority={priority}"
            )

            return opportunity

        except (ValueError, KeyError, AttributeError, ZeroDivisionError) as e:
            logger.error(f"Invalid metrics data for {operation}: {e}")
            return None
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Unexpected error analyzing opportunity for {operation}: {e}")
            return None

    async def _estimate_improvement(
        self, operation: str, metrics: Dict[str, float]
    ) -> float:
        """
        Estimate potential improvement percentage.

        Algorithm:
        - High improvement potential (40-60%):
          * p95 > 1000ms (very slow)
          * High std_dev/mean ratio (variance indicates bottlenecks)
          * I/O-bound operations (validation, pattern matching)
        - Medium improvement potential (20-40%):
          * p95 between 500-1000ms
          * Moderate variance
          * CPU-bound operations
        - Low improvement potential (10-20%):
          * p95 between 300-500ms
          * Low variance
          * Already optimized operations

        Args:
            operation: Operation name
            metrics: Performance metrics

        Returns:
            Estimated improvement percentage (0-100)
        """
        p95 = metrics.get("p95", 0.0)
        mean = metrics.get("mean", 0.0)
        std_dev = metrics.get("std_dev", 0.0)

        # Calculate variance ratio (std_dev / mean)
        variance_ratio = std_dev / mean if mean > 0 else 0.0

        # Base improvement estimate on p95
        if p95 > self.HIGH_IMPROVEMENT_THRESHOLD:
            # Very slow operations: 40-60% improvement potential
            base_improvement = 50.0
        elif p95 > self.MEDIUM_IMPROVEMENT_THRESHOLD:
            # Moderately slow operations: 20-40% improvement potential
            base_improvement = 30.0
        else:
            # Slightly slow operations: 10-20% improvement potential
            base_improvement = 15.0

        # Adjust based on variance (high variance suggests bottlenecks)
        if variance_ratio > self.HIGH_VARIANCE_THRESHOLD:
            base_improvement += 10.0  # High variance: more optimization potential
        elif variance_ratio > 0.5:
            base_improvement += 5.0  # Moderate variance

        # Adjust based on operation type
        if self._is_io_bound_operation(operation):
            base_improvement += 10.0  # I/O operations have high improvement potential
        elif self._is_validation_operation(operation):
            base_improvement += 8.0  # Validation operations benefit from caching

        # Cap at 60% (realistic maximum improvement)
        estimated_improvement = min(base_improvement, 60.0)

        return round(estimated_improvement, 1)

    async def _estimate_effort(self, operation: str, metrics: Dict[str, float]) -> str:
        """
        Estimate implementation effort level.

        Algorithm:
        - Low effort:
          * Simple caching opportunities (lookups, searches)
          * Configuration changes
          * Library upgrades
        - Medium effort:
          * Algorithm optimization (validation, complex pattern matching)
          * Database query optimization
          * Parallel processing
        - High effort:
          * Architectural changes
          * External service dependencies
          * Complex refactoring

        Args:
            operation: Operation name
            metrics: Performance metrics

        Returns:
            Effort level: "low", "medium", or "high"
        """
        # Check for high-effort opportunities first
        if self._is_architectural_operation(
            operation
        ) or self._is_external_service_operation(operation):
            return "high"  # Architectural changes

        # Check for low-effort opportunities (simple lookups and searches)
        # Must check before validation/pattern to catch simple lookups
        if "lookup" in operation.lower() or "search" in operation.lower():
            return "low"  # Simple caching for lookups/searches

        # Check for medium-effort opportunities (complex operations)
        if self._is_validation_operation(operation):
            return "medium"  # Validation requires algorithm optimization

        if self._is_pattern_operation(operation) and "matching" in operation.lower():
            return "medium"  # Complex pattern matching (not simple lookups)

        # Check for remaining cacheable operations
        if self._is_cacheable_operation(operation):
            return "low"  # Simple caching

        # Default to medium effort
        return "medium"

    def _calculate_roi(self, improvement: float, effort_level: str) -> float:
        """
        Calculate ROI score (improvement / effort).

        Higher ROI indicates better return on investment.

        Args:
            improvement: Estimated improvement percentage
            effort_level: Effort level ("low", "medium", "high")

        Returns:
            ROI score (higher is better)
        """
        effort_score = self.EFFORT_SCORES.get(effort_level, 2.0)
        roi_score = improvement / effort_score
        return round(roi_score, 2)

    async def _generate_recommendations(
        self, operation: str, metrics: Dict[str, float]
    ) -> List[str]:
        """
        Generate specific, actionable optimization recommendations.

        Recommendation types:
        - Caching: For operations with p95 > 1000ms and repetitive patterns
        - Batch processing: For operations with high frequency
        - Parallel execution: For operations with multiple independent subtasks
        - Database optimization: For data-access operations with high variance
        - Algorithm improvement: For compute-intensive operations
        - Service optimization: For external API calls

        Args:
            operation: Operation name
            metrics: Performance metrics

        Returns:
            List of specific, actionable recommendations
        """
        recommendations = []
        p95 = metrics.get("p95", 0.0)
        mean = metrics.get("mean", 0.0)
        std_dev = metrics.get("std_dev", 0.0)

        # Caching recommendations (very slow operations)
        if p95 > self.HIGH_IMPROVEMENT_THRESHOLD:
            if self._is_validation_operation(operation):
                recommendations.append(
                    f"Add Redis caching for validation results "
                    f"(estimated 60% improvement from {p95:.0f}ms to {p95*0.4:.0f}ms)"
                )
            elif self._is_pattern_operation(operation):
                recommendations.append(
                    f"Implement result caching for pattern matching "
                    f"(estimated 50% improvement from {p95:.0f}ms to {p95*0.5:.0f}ms)"
                )
            else:
                recommendations.append(
                    f"Consider adding caching layer "
                    f"(estimated 40-60% improvement from {p95:.0f}ms)"
                )

        # High variance recommendations (bottleneck detection)
        variance_ratio = std_dev / mean if mean > 0 else 0.0
        if variance_ratio > self.HIGH_VARIANCE_THRESHOLD:
            recommendations.append(
                f"High variance detected (std_dev/mean={variance_ratio:.2f}) - "
                f"investigate bottlenecks and add instrumentation"
            )

        # Batch processing recommendations
        if self._is_validation_operation(operation):
            recommendations.append(
                "Implement batch validation to reduce overhead "
                "(estimated 30-40% improvement)"
            )

        # Parallel execution recommendations
        if p95 > self.MEDIUM_IMPROVEMENT_THRESHOLD and self._can_parallelize(operation):
            recommendations.append(
                "Parallelize independent subtasks across multiple cores "
                "(estimated 35-45% improvement)"
            )

        # Database optimization recommendations
        if "database" in operation.lower() or "query" in operation.lower():
            recommendations.append(
                "Add database indexes on frequently queried columns "
                "(estimated 50% improvement)"
            )
            recommendations.append(
                "Consider connection pooling for database operations "
                "(estimated 20-30% improvement)"
            )

        # Async/await recommendations
        if self._is_io_bound_operation(operation):
            recommendations.append(
                "Use async/await for I/O operations to improve concurrency "
                "(estimated 35% improvement)"
            )

        # Algorithm optimization recommendations
        if self._is_compute_intensive(operation):
            recommendations.append(
                "Profile and optimize hot code paths with algorithmic improvements "
                "(estimated 25-35% improvement)"
            )

        # Ensure we have at least one recommendation
        if not recommendations:
            recommendations.append(
                f"Investigate performance bottleneck for {operation} "
                f"(current p95: {p95:.0f}ms)"
            )

        return recommendations

    def _determine_priority(self, metrics: Dict[str, float], roi_score: float) -> str:
        """
        Determine priority classification.

        Priority levels:
        - Critical: p95 > 2000ms or ROI > 40
        - High: p95 > 1000ms or ROI > 20
        - Medium: p95 > 500ms or ROI > 10
        - Low: Otherwise

        Args:
            metrics: Performance metrics
            roi_score: Calculated ROI score

        Returns:
            Priority: "critical", "high", "medium", or "low"
        """
        p95 = metrics.get("p95", 0.0)

        if p95 > 2000.0 or roi_score > 40.0:
            return "critical"
        elif p95 > 1000.0 or roi_score > 20.0:
            return "high"
        elif p95 > 500.0 or roi_score > 10.0:
            return "medium"
        else:
            return "low"

    # Helper methods for operation classification

    def _is_io_bound_operation(self, operation: str) -> bool:
        """Check if operation is I/O-bound."""
        io_keywords = [
            "read",
            "write",
            "fetch",
            "load",
            "save",
            "query",
            "api",
            "http",
            "request",
        ]
        return any(keyword in operation.lower() for keyword in io_keywords)

    def _is_validation_operation(self, operation: str) -> bool:
        """Check if operation is validation-related."""
        return "validation" in operation.lower() or "validate" in operation.lower()

    def _is_pattern_operation(self, operation: str) -> bool:
        """Check if operation is pattern-related."""
        return "pattern" in operation.lower()

    def _is_cacheable_operation(self, operation: str) -> bool:
        """Check if operation is cacheable."""
        cacheable_keywords = ["lookup", "search", "pattern", "validation", "query"]
        return any(keyword in operation.lower() for keyword in cacheable_keywords)

    def _is_architectural_operation(self, operation: str) -> bool:
        """Check if operation requires architectural changes."""
        arch_keywords = ["orchestration", "workflow", "coordination", "pipeline"]
        return any(keyword in operation.lower() for keyword in arch_keywords)

    def _is_external_service_operation(self, operation: str) -> bool:
        """Check if operation involves external services."""
        external_keywords = ["api", "http", "service", "remote", "external"]
        return any(keyword in operation.lower() for keyword in external_keywords)

    def _can_parallelize(self, operation: str) -> bool:
        """Check if operation can be parallelized."""
        parallelizable_keywords = ["batch", "multi", "aggregate", "collect", "process"]
        return any(keyword in operation.lower() for keyword in parallelizable_keywords)

    def _is_compute_intensive(self, operation: str) -> bool:
        """Check if operation is compute-intensive."""
        compute_keywords = [
            "analyze",
            "calculate",
            "compute",
            "process",
            "parse",
            "transform",
        ]
        return any(keyword in operation.lower() for keyword in compute_keywords)
