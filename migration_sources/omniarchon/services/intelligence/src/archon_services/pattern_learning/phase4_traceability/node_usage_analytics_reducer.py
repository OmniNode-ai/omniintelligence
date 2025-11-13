"""
ONEX Reducer Node: Pattern Usage Analytics

Purpose: Aggregate pattern usage metrics over time with comprehensive analytics
Pattern: ONEX 4-Node Architecture - Reducer Node
File: node_usage_analytics_reducer.py

Track: Track 3 Phase 4 - Pattern Traceability & Metrics
ONEX Compliant: Reducer node (pure data aggregation, no I/O)
Performance Target: <500ms per pattern analytics computation
"""

import logging
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from src.archon_services.pattern_learning.phase4_traceability.model_contract_pattern_lineage import (
    ModelResult,
)
from src.archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    ContextDistribution,
    ModelContractUsageAnalytics,
    ModelUsageAnalyticsInput,
    ModelUsageAnalyticsOutput,
    PerformanceMetrics,
    SuccessMetrics,
    TimeWindowType,
    TrendAnalysis,
    UsageFrequencyMetrics,
    UsageTrendType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ONEX Reducer Node Implementation
# ============================================================================


class NodeUsageAnalyticsReducer:
    """
    ONEX Reducer node for pattern usage analytics aggregation.

    ONEX Node Type: Reducer (data aggregation, no side effects)

    Features:
    - Usage frequency computation (executions per time period)
    - Success/failure rate analysis
    - Performance percentile calculations (P50, P95, P99)
    - Trend analysis (growing, stable, declining)
    - Context distribution analysis
    - Temporal patterns (time of day, day of week)
    - Quality confidence scoring

    Architecture:
    - Pure functional operations (no external I/O)
    - Receives data from Effect nodes
    - Returns aggregated analytics
    - Stateless (no instance state between calls)

    Performance:
    - Target: <500ms for analytics computation
    - Handles 1000+ execution records efficiently
    - Optimized percentile calculations
    """

    def __init__(self):
        """Initialize usage analytics reducer."""
        self.contract = ModelContractUsageAnalytics()
        logger.info("NodeUsageAnalyticsReducer initialized")

    # ========================================================================
    # Main ONEX Reducer Interface
    # ========================================================================

    async def execute_reduction(
        self, contract: ModelUsageAnalyticsInput
    ) -> ModelResult:
        """
        Execute analytics reduction on pattern usage data.

        This is the main ONEX Reducer interface. It performs pure data
        aggregation and computation without any external I/O.

        Args:
            contract: Input contract with pattern data and configuration

        Returns:
            ModelResult with success status and analytics output in data field

        Raises:
            ValueError: If input contract is invalid
        """
        start_time = time.time()

        try:
            # Validate input
            if not contract.execution_data:
                logger.warning(
                    f"No execution data for pattern {contract.pattern_id}, "
                    "returning empty analytics"
                )
                empty_output = self._create_empty_analytics(contract)
                return ModelResult(
                    success=True,
                    data=empty_output.to_dict(),
                    metadata={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reducer": "NodeUsageAnalyticsReducer",
                        "pattern_id": str(contract.pattern_id),
                        "empty_analytics": True,
                    },
                )

            # Core metrics (always computed)
            usage_metrics = self._compute_usage_frequency(
                contract.execution_data,
                contract.time_window_start,
                contract.time_window_end,
            )

            success_metrics = self._compute_success_metrics(contract.execution_data)

            # Optional metrics (based on flags)
            performance_metrics = None
            if contract.include_performance:
                performance_metrics = self._compute_performance_metrics(
                    contract.execution_data
                )

            trend_analysis = None
            if contract.include_trends:
                trend_analysis = self._compute_trend_analysis(
                    contract.execution_data,
                    contract.time_window_start,
                    contract.time_window_end,
                    contract.time_window_type,
                )

            context_distribution = None
            if contract.include_distribution:
                context_distribution = self._compute_context_distribution(
                    contract.execution_data
                )

            # Analytics quality score
            analytics_quality_score = self._compute_analytics_quality_score(
                len(contract.execution_data),
                contract.time_window_start,
                contract.time_window_end,
            )

            # Compute processing time
            computation_time_ms = (time.time() - start_time) * 1000

            # Build output contract
            output = ModelUsageAnalyticsOutput(
                pattern_id=contract.pattern_id,
                time_window_start=contract.time_window_start,
                time_window_end=contract.time_window_end,
                time_window_type=contract.time_window_type,
                usage_metrics=usage_metrics,
                success_metrics=success_metrics,
                performance_metrics=performance_metrics,
                trend_analysis=trend_analysis,
                context_distribution=context_distribution,
                total_data_points=len(contract.execution_data),
                analytics_quality_score=analytics_quality_score,
                computation_time_ms=computation_time_ms,
                correlation_id=contract.correlation_id,
            )

            logger.info(
                f"Analytics computed for pattern {contract.pattern_id}: "
                f"{usage_metrics.total_executions} executions, "
                f"{success_metrics.success_rate:.1%} success rate, "
                f"{computation_time_ms:.2f}ms"
            )

            # Wrap output in standard ModelResult format
            return ModelResult(
                success=True,
                data=output.to_dict(),
                metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reducer": "NodeUsageAnalyticsReducer",
                    "pattern_id": str(contract.pattern_id),
                    "computation_time_ms": computation_time_ms,
                },
            )

        except Exception as e:
            logger.error(
                f"Analytics computation failed for pattern {contract.pattern_id}: {e}"
            )
            raise

    # ========================================================================
    # Usage Frequency Computation
    # ========================================================================

    def _compute_usage_frequency(
        self,
        execution_data: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
    ) -> UsageFrequencyMetrics:
        """
        Compute usage frequency metrics.

        Args:
            execution_data: List of execution records
            start_time: Analysis window start
            end_time: Analysis window end

        Returns:
            Usage frequency metrics
        """
        total_executions = len(execution_data)

        # Calculate time window duration
        window_duration = end_time - start_time
        days_in_window = max(window_duration.total_seconds() / 86400, 1.0)
        weeks_in_window = max(days_in_window / 7.0, 1.0)
        months_in_window = max(days_in_window / 30.0, 1.0)

        # Per-period averages
        executions_per_day = total_executions / days_in_window
        executions_per_week = total_executions / weeks_in_window
        executions_per_month = total_executions / months_in_window

        # Unique contexts and users
        unique_contexts = len(
            set(rec.get("context_type", "unknown") for rec in execution_data)
        )
        unique_users = len(set(rec.get("agent", "unknown") for rec in execution_data))

        # Peak daily usage
        executions_by_date = defaultdict(int)
        for record in execution_data:
            timestamp = record.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                date_key = timestamp.date()
                executions_by_date[date_key] += 1

        peak_daily_usage = max(executions_by_date.values()) if executions_by_date else 0

        # Time since last use
        time_since_last_use = None
        if execution_data:
            timestamps = []
            for record in execution_data:
                timestamp = record.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    timestamps.append(timestamp)

            if timestamps:
                last_use = max(timestamps)
                now = datetime.now(timezone.utc)
                time_since_last_use = (now - last_use).total_seconds() / 3600  # hours

        return UsageFrequencyMetrics(
            total_executions=total_executions,
            executions_per_day=round(executions_per_day, 2),
            executions_per_week=round(executions_per_week, 2),
            executions_per_month=round(executions_per_month, 2),
            unique_contexts=unique_contexts,
            unique_users=unique_users,
            peak_daily_usage=peak_daily_usage,
            time_since_last_use=(
                round(time_since_last_use, 2) if time_since_last_use else None
            ),
        )

    # ========================================================================
    # Success Metrics Computation
    # ========================================================================

    def _compute_success_metrics(
        self, execution_data: List[Dict[str, Any]]
    ) -> SuccessMetrics:
        """
        Compute success/failure metrics.

        Args:
            execution_data: List of execution records

        Returns:
            Success metrics
        """
        success_count = 0
        failure_count = 0
        timeout_count = 0
        quality_gate_failures = 0
        quality_scores = []

        for record in execution_data:
            # Determine success/failure
            if record.get("success", False):
                success_count += 1
            else:
                failure_count += 1

            # Check for timeouts
            if record.get("timeout", False):
                timeout_count += 1

            # Check quality gate failures
            if not record.get("quality_gates_passed", True):
                quality_gate_failures += 1

            # Collect quality scores
            quality_score = record.get("quality_score")
            if quality_score is not None:
                quality_scores.append(quality_score)

        total = success_count + failure_count
        success_rate = success_count / total if total > 0 else 0.0
        error_rate = failure_count / total if total > 0 else 0.0
        avg_quality_score = statistics.mean(quality_scores) if quality_scores else 0.0

        return SuccessMetrics(
            success_count=success_count,
            failure_count=failure_count,
            success_rate=round(success_rate, 4),
            error_rate=round(error_rate, 4),
            timeout_count=timeout_count,
            quality_gate_failures=quality_gate_failures,
            avg_quality_score=round(avg_quality_score, 4),
        )

    # ========================================================================
    # Performance Metrics Computation
    # ========================================================================

    def _compute_performance_metrics(
        self, execution_data: List[Dict[str, Any]]
    ) -> PerformanceMetrics:
        """
        Compute performance percentile metrics.

        Args:
            execution_data: List of execution records

        Returns:
            Performance metrics with percentiles
        """
        execution_times = []
        for record in execution_data:
            exec_time = record.get("execution_time_ms")
            if exec_time is not None:
                execution_times.append(exec_time)

        if not execution_times:
            return PerformanceMetrics()

        # Sort for percentile calculations
        execution_times.sort()

        # Compute statistics
        avg_time = statistics.mean(execution_times)
        min_time = min(execution_times)
        max_time = max(execution_times)
        total_time = sum(execution_times)

        # Percentiles
        p50 = self._compute_percentile(execution_times, 50)
        p95 = self._compute_percentile(execution_times, 95)
        p99 = self._compute_percentile(execution_times, 99)

        # Standard deviation
        std_dev = statistics.stdev(execution_times) if len(execution_times) > 1 else 0.0

        return PerformanceMetrics(
            avg_execution_time_ms=round(avg_time, 2),
            p50_execution_time_ms=round(p50, 2),
            p95_execution_time_ms=round(p95, 2),
            p99_execution_time_ms=round(p99, 2),
            min_execution_time_ms=round(min_time, 2),
            max_execution_time_ms=round(max_time, 2),
            std_dev_ms=round(std_dev, 2),
            total_execution_time_ms=round(total_time, 2),
        )

    def _compute_percentile(self, sorted_values: List[float], percentile: int) -> float:
        """
        Compute percentile from sorted values.

        Args:
            sorted_values: Pre-sorted list of values
            percentile: Percentile to compute (0-100)

        Returns:
            Percentile value
        """
        if not sorted_values:
            return 0.0

        index = (percentile / 100) * (len(sorted_values) - 1)
        lower = int(index)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = index - lower

        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    # ========================================================================
    # Trend Analysis Computation
    # ========================================================================

    def _compute_trend_analysis(
        self,
        execution_data: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        window_type: TimeWindowType,
    ) -> TrendAnalysis:
        """
        Compute usage trend analysis.

        Args:
            execution_data: List of execution records
            start_time: Analysis window start
            end_time: Analysis window end
            window_type: Type of time window

        Returns:
            Trend analysis with velocity and predictions
        """
        # Group executions by time period
        executions_by_period = self._group_by_time_period(
            execution_data, start_time, end_time, window_type
        )

        # Compute velocity (rate of change)
        velocity = self._compute_velocity(executions_by_period)

        # Compute acceleration (change in velocity)
        acceleration = self._compute_acceleration(executions_by_period)

        # Classify trend type
        trend_type = self._classify_trend(velocity, acceleration, len(execution_data))

        # Compute growth percentage
        growth_percentage = self._compute_growth_percentage(executions_by_period)

        # Compute user retention/churn
        retention_rate, churn_rate = self._compute_retention_metrics(execution_data)

        # Adoption rate (new users per period)
        adoption_rate = self._compute_adoption_rate(execution_data, window_type)

        # Confidence score based on data quality
        confidence_score = self._compute_trend_confidence(
            len(execution_data), len(executions_by_period)
        )

        return TrendAnalysis(
            trend_type=trend_type,
            velocity=round(velocity, 2),
            acceleration=round(acceleration, 2),
            adoption_rate=round(adoption_rate, 2),
            retention_rate=round(retention_rate, 4),
            churn_rate=round(churn_rate, 4),
            growth_percentage=round(growth_percentage, 2),
            confidence_score=round(confidence_score, 4),
        )

    def _group_by_time_period(
        self,
        execution_data: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        window_type: TimeWindowType,
    ) -> List[int]:
        """Group executions into time periods."""
        # Determine period duration
        if window_type == TimeWindowType.HOURLY:
            period_seconds = 3600
        elif window_type == TimeWindowType.DAILY:
            period_seconds = 86400
        elif window_type == TimeWindowType.WEEKLY:
            period_seconds = 604800
        else:
            period_seconds = 86400  # Default to daily

        # Count executions per period
        window_duration = (end_time - start_time).total_seconds()
        num_periods = max(int(window_duration / period_seconds), 1)

        executions_per_period = [0] * num_periods

        for record in execution_data:
            timestamp = record.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

                # Calculate which period this execution belongs to
                seconds_since_start = (timestamp - start_time).total_seconds()
                period_index = int(seconds_since_start / period_seconds)

                if 0 <= period_index < num_periods:
                    executions_per_period[period_index] += 1

        return executions_per_period

    def _compute_velocity(self, executions_by_period: List[int]) -> float:
        """Compute rate of change in executions."""
        if len(executions_by_period) < 2:
            return 0.0

        # Linear regression slope
        n = len(executions_by_period)
        x_mean = (n - 1) / 2
        y_mean = sum(executions_by_period) / n

        numerator = sum(
            (i - x_mean) * (y - y_mean) for i, y in enumerate(executions_by_period)
        )
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        velocity = numerator / denominator if denominator > 0 else 0.0
        return velocity

    def _compute_acceleration(self, executions_by_period: List[int]) -> float:
        """Compute change in velocity (second derivative)."""
        if len(executions_by_period) < 3:
            return 0.0

        # Split into two halves and compare velocities
        mid = len(executions_by_period) // 2
        first_half = executions_by_period[:mid]
        second_half = executions_by_period[mid:]

        velocity_first = self._compute_velocity(first_half)
        velocity_second = self._compute_velocity(second_half)

        acceleration = velocity_second - velocity_first
        return acceleration

    def _classify_trend(
        self, velocity: float, acceleration: float, total_executions: int
    ) -> UsageTrendType:
        """Classify trend type based on velocity and acceleration."""
        # Threshold for considering trend significant
        velocity_threshold = 0.5

        # Check for abandoned patterns first (strong decline + very few executions)
        if velocity <= -2.0 and total_executions < 5:
            return UsageTrendType.ABANDONED

        # Emerging patterns (still building usage history)
        if total_executions < 10:
            return UsageTrendType.EMERGING

        # Stable usage
        if abs(velocity) < velocity_threshold:
            return UsageTrendType.STABLE

        # Growing or declining trends
        if velocity > velocity_threshold:
            return UsageTrendType.GROWING
        elif velocity < -velocity_threshold:
            return UsageTrendType.DECLINING

        return UsageTrendType.STABLE

    def _compute_growth_percentage(self, executions_by_period: List[int]) -> float:
        """Compute growth percentage between first and last period."""
        if len(executions_by_period) < 2:
            return 0.0

        # Compare last period to first period
        first_period = sum(
            executions_by_period[: max(1, len(executions_by_period) // 4)]
        )
        last_period = sum(
            executions_by_period[-(max(1, len(executions_by_period) // 4)) :]
        )

        if first_period == 0:
            return 100.0 if last_period > 0 else 0.0

        growth = ((last_period - first_period) / first_period) * 100
        return growth

    def _compute_retention_metrics(
        self, execution_data: List[Dict[str, Any]]
    ) -> Tuple[float, float]:
        """Compute user retention and churn rates."""
        if len(execution_data) < 2:
            return 0.0, 0.0

        # Group executions by user and time
        users_by_period = defaultdict(set)

        for record in execution_data:
            user = record.get("agent", "unknown")
            timestamp = record.get("timestamp")

            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

                # Group by week
                week = timestamp.isocalendar()[1]
                users_by_period[week].add(user)

        # Calculate retention (users who appear in multiple periods)
        all_users = set()
        returning_users = set()

        periods = sorted(users_by_period.keys())
        for i, period in enumerate(periods):
            period_users = users_by_period[period]

            if i > 0:
                # Users who were active in previous period
                previous_users = users_by_period[periods[i - 1]]
                returning = period_users & previous_users
                returning_users.update(returning)

            all_users.update(period_users)

        retention_rate = len(returning_users) / len(all_users) if all_users else 0.0
        churn_rate = 1.0 - retention_rate

        return retention_rate, churn_rate

    def _compute_adoption_rate(
        self, execution_data: List[Dict[str, Any]], window_type: TimeWindowType
    ) -> float:
        """Compute rate of new user adoption."""
        if not execution_data:
            return 0.0

        # Track first appearance of each user
        user_first_seen = {}

        for record in execution_data:
            user = record.get("agent", "unknown")
            timestamp = record.get("timestamp")

            if timestamp and user not in user_first_seen:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                user_first_seen[user] = timestamp

        # Count new users per week
        new_users_per_week = len(user_first_seen) / max(1, len(execution_data) / 7)
        return new_users_per_week

    def _compute_trend_confidence(
        self, total_executions: int, num_periods: int
    ) -> float:
        """Compute confidence score for trend prediction."""
        # More data = higher confidence
        execution_confidence = min(total_executions / 100, 1.0)

        # More periods = higher confidence
        period_confidence = min(num_periods / 10, 1.0)

        # Combined confidence
        confidence = (execution_confidence * 0.7) + (period_confidence * 0.3)
        return confidence

    # ========================================================================
    # Context Distribution Computation
    # ========================================================================

    def _compute_context_distribution(
        self, execution_data: List[Dict[str, Any]]
    ) -> ContextDistribution:
        """
        Compute distribution of pattern usage across contexts.

        Args:
            execution_data: List of execution records

        Returns:
            Context distribution metrics
        """
        by_context_type = Counter()
        by_agent = Counter()
        by_project = Counter()
        by_file_type = Counter()
        by_time_of_day = Counter()
        by_day_of_week = Counter()

        for record in execution_data:
            # Context type
            context_type = record.get("context_type", "unknown")
            by_context_type[context_type] += 1

            # Agent/user
            agent = record.get("agent", "unknown")
            by_agent[agent] += 1

            # Project
            project = record.get("project", "unknown")
            by_project[project] += 1

            # File type
            file_path = record.get("file_path", "")
            if file_path:
                file_ext = file_path.split(".")[-1] if "." in file_path else "unknown"
                by_file_type[file_ext] += 1

            # Time of day
            timestamp = record.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                hour = timestamp.hour
                by_time_of_day[hour] += 1

                # Day of week (0=Monday, 6=Sunday)
                day_of_week = timestamp.weekday()
                by_day_of_week[day_of_week] += 1

        return ContextDistribution(
            by_context_type=dict(by_context_type),
            by_agent=dict(by_agent),
            by_project=dict(by_project),
            by_file_type=dict(by_file_type),
            by_time_of_day=dict(by_time_of_day),
            by_day_of_week=dict(by_day_of_week),
        )

    # ========================================================================
    # Quality and Utility Methods
    # ========================================================================

    def _compute_analytics_quality_score(
        self, total_data_points: int, start_time: datetime, end_time: datetime
    ) -> float:
        """
        Compute quality/confidence score for analytics.

        Higher scores indicate more reliable analytics.

        Args:
            total_data_points: Number of execution records
            start_time: Analysis window start
            end_time: Analysis window end

        Returns:
            Quality score (0.0-1.0)
        """
        # Data volume score
        volume_score = min(total_data_points / 100, 1.0)

        # Time window coverage score
        window_duration = (end_time - start_time).total_seconds() / 86400  # days
        coverage_score = min(window_duration / 30, 1.0)  # 30 days = perfect

        # Combined score
        quality_score = (volume_score * 0.7) + (coverage_score * 0.3)
        return quality_score

    def _create_empty_analytics(
        self, contract: ModelUsageAnalyticsInput
    ) -> ModelUsageAnalyticsOutput:
        """Create empty analytics result for patterns with no data."""
        return ModelUsageAnalyticsOutput(
            pattern_id=contract.pattern_id,
            time_window_start=contract.time_window_start,
            time_window_end=contract.time_window_end,
            time_window_type=contract.time_window_type,
            usage_metrics=UsageFrequencyMetrics(),
            success_metrics=SuccessMetrics(),
            performance_metrics=(
                PerformanceMetrics() if contract.include_performance else None
            ),
            trend_analysis=TrendAnalysis() if contract.include_trends else None,
            context_distribution=(
                ContextDistribution() if contract.include_distribution else None
            ),
            total_data_points=0,
            analytics_quality_score=0.0,
            computation_time_ms=0.0,
            correlation_id=contract.correlation_id,
        )
