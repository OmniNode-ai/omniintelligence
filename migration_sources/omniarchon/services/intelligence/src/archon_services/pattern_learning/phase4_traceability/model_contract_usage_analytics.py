"""
ONEX Contract Models: Usage Analytics Operations

Purpose: Define contracts for pattern usage analytics aggregation
Pattern: ONEX 4-Node Architecture - Reducer Node Contracts
File: model_contract_usage_analytics.py

Track: Track 3 Phase 4 - Pattern Traceability & Metrics
ONEX Compliant: Contract naming convention (model_contract_*)
Performance Target: <500ms per pattern analytics computation
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ============================================================================
# Enumerations
# ============================================================================


class UsageTrendType(str, Enum):
    """Pattern usage trend classifications"""

    GROWING = "growing"  # Usage increasing over time
    STABLE = "stable"  # Consistent usage rate
    DECLINING = "declining"  # Usage decreasing over time
    EMERGING = "emerging"  # New pattern gaining traction
    ABANDONED = "abandoned"  # No recent usage


class TimeWindowType(str, Enum):
    """Time window types for analytics aggregation"""

    HOURLY = "hourly"  # Last hour
    DAILY = "daily"  # Last 24 hours
    WEEKLY = "weekly"  # Last 7 days
    MONTHLY = "monthly"  # Last 30 days
    QUARTERLY = "quarterly"  # Last 90 days
    YEARLY = "yearly"  # Last 365 days
    ALL_TIME = "all_time"  # Complete history

    # Alias values for test compatibility
    LAST_24_HOURS = "daily"  # Alias for DAILY
    LAST_7_DAYS = "weekly"  # Alias for WEEKLY
    LAST_30_DAYS = "monthly"  # Alias for MONTHLY
    LAST_90_DAYS = "quarterly"  # Alias for QUARTERLY
    CUSTOM = "custom"  # Custom time window


class AnalyticsGranularity(str, Enum):
    """Granularity level for analytics breakdown"""

    SUMMARY = "summary"  # High-level overview only
    DETAILED = "detailed"  # Includes breakdowns and distributions
    COMPREHENSIVE = "comprehensive"  # Full analysis with trends and predictions

    # Alias values for test compatibility (these map to detail levels)
    HOURLY = "detailed"  # Alias for DETAILED
    DAILY = "detailed"  # Alias for DETAILED
    WEEKLY = "summary"  # Alias for SUMMARY


# ============================================================================
# Analytics Data Models
# ============================================================================


@dataclass
class UsageFrequencyMetrics:
    """
    Pattern usage frequency metrics.

    Attributes:
        total_executions: Total number of pattern executions
        executions_per_day: Average executions per day
        executions_per_week: Average executions per week
        executions_per_month: Average executions per month
        unique_contexts: Number of unique contexts where pattern used
        unique_users: Number of unique users/agents using pattern
        peak_daily_usage: Maximum executions in a single day
        time_since_last_use: Hours since last pattern execution
    """

    total_executions: int = 0
    executions_per_day: float = 0.0
    executions_per_week: float = 0.0
    executions_per_month: float = 0.0
    unique_contexts: int = 0
    unique_users: int = 0
    peak_daily_usage: int = 0
    time_since_last_use: Optional[float] = None


@dataclass
class PerformanceMetrics:
    """
    Pattern performance metrics.

    Attributes:
        avg_execution_time_ms: Average execution time in milliseconds
        p50_execution_time_ms: 50th percentile (median) execution time
        p95_execution_time_ms: 95th percentile execution time
        p99_execution_time_ms: 99th percentile execution time
        min_execution_time_ms: Minimum execution time
        max_execution_time_ms: Maximum execution time
        std_dev_ms: Standard deviation of execution times
        total_execution_time_ms: Total cumulative execution time
    """

    avg_execution_time_ms: float = 0.0
    p50_execution_time_ms: float = 0.0
    p95_execution_time_ms: float = 0.0
    p99_execution_time_ms: float = 0.0
    min_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    std_dev_ms: float = 0.0
    total_execution_time_ms: float = 0.0


@dataclass
class SuccessMetrics:
    """
    Pattern success/failure metrics.

    Attributes:
        success_count: Number of successful executions
        failure_count: Number of failed executions
        success_rate: Percentage of successful executions (0.0-1.0)
        error_rate: Percentage of failed executions (0.0-1.0)
        timeout_count: Number of timeout occurrences
        quality_gate_failures: Number of quality gate failures
        avg_quality_score: Average quality score across executions
    """

    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    error_rate: float = 0.0
    timeout_count: int = 0
    quality_gate_failures: int = 0
    avg_quality_score: float = 0.0


@dataclass
class TrendAnalysis:
    """
    Usage trend analysis over time.

    Attributes:
        trend_type: Classification of usage trend
        velocity: Rate of change (executions per day change)
        acceleration: Rate of velocity change (is it speeding up/slowing down)
        adoption_rate: New users adopting pattern (users per week)
        retention_rate: Users continuing to use pattern (0.0-1.0)
        churn_rate: Users who stopped using pattern (0.0-1.0)
        growth_percentage: Percentage growth over previous period
        confidence_score: Confidence in trend prediction (0.0-1.0)
    """

    trend_type: UsageTrendType = UsageTrendType.STABLE
    velocity: float = 0.0
    acceleration: float = 0.0
    adoption_rate: float = 0.0
    retention_rate: float = 0.0
    churn_rate: float = 0.0
    growth_percentage: float = 0.0
    confidence_score: float = 0.0


@dataclass
class ContextDistribution:
    """
    Distribution of pattern usage across contexts.

    Attributes:
        by_context_type: Executions grouped by context type
        by_agent: Executions grouped by agent/user
        by_project: Executions grouped by project
        by_file_type: Executions grouped by file type
        by_time_of_day: Executions grouped by hour (0-23)
        by_day_of_week: Executions grouped by day (0-6, Mon-Sun)
    """

    by_context_type: Dict[str, int] = field(default_factory=dict)
    by_agent: Dict[str, int] = field(default_factory=dict)
    by_project: Dict[str, int] = field(default_factory=dict)
    by_file_type: Dict[str, int] = field(default_factory=dict)
    by_time_of_day: Dict[int, int] = field(default_factory=dict)
    by_day_of_week: Dict[int, int] = field(default_factory=dict)


# ============================================================================
# Input Contract
# ============================================================================


@dataclass
class ModelUsageAnalyticsInput:
    """
    Input contract for usage analytics reducer node.

    This contract defines what data is needed to compute analytics
    for a specific pattern over a time window.

    Attributes:
        pattern_id: UUID of pattern to analyze
        time_window_start: Start of analysis window (UTC)
        time_window_end: End of analysis window (UTC)
        time_window_type: Type of time window for context
        granularity: Level of detail in analytics output
        include_trends: Whether to compute trend analysis
        include_performance: Whether to compute performance metrics
        include_distribution: Whether to compute context distribution
        include_predictions: Whether to include future trend predictions
        execution_data: Raw execution records for the pattern
        correlation_id: Correlation ID for tracing
    """

    pattern_id: UUID
    time_window_start: datetime
    time_window_end: datetime
    time_window_type: TimeWindowType = TimeWindowType.DAILY
    granularity: AnalyticsGranularity = AnalyticsGranularity.DETAILED

    # Feature flags for optional computations
    include_trends: bool = True
    include_performance: bool = True
    include_distribution: bool = True
    include_predictions: bool = False

    # Input data (from Effect nodes)
    execution_data: List[Dict[str, Any]] = field(default_factory=list)

    # Tracing
    correlation_id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        """Validate input contract after initialization."""
        if self.time_window_end <= self.time_window_start:
            raise ValueError("time_window_end must be after time_window_start")

        # Ensure timezone-aware datetimes
        if self.time_window_start.tzinfo is None:
            self.time_window_start = self.time_window_start.replace(tzinfo=timezone.utc)
        if self.time_window_end.tzinfo is None:
            self.time_window_end = self.time_window_end.replace(tzinfo=timezone.utc)


# ============================================================================
# Output Contract
# ============================================================================


@dataclass
class ModelUsageAnalyticsOutput:
    """
    Output contract for usage analytics reducer node.

    Contains comprehensive analytics results for a pattern.

    Attributes:
        pattern_id: UUID of analyzed pattern
        time_window_start: Start of analysis window
        time_window_end: End of analysis window
        time_window_type: Type of time window analyzed

        # Core metrics (always included)
        usage_metrics: Usage frequency metrics
        success_metrics: Success/failure metrics

        # Optional metrics (based on input flags)
        performance_metrics: Performance metrics (if include_performance=True)
        trend_analysis: Trend analysis (if include_trends=True)
        context_distribution: Context distribution (if include_distribution=True)

        # Summary information
        total_data_points: Number of execution records analyzed
        analytics_quality_score: Quality/confidence score for analytics (0.0-1.0)
        computation_time_ms: Time taken to compute analytics

        # Metadata
        correlation_id: Correlation ID for tracing
        computed_at: When analytics were computed
        metadata: Additional analytics metadata
    """

    pattern_id: UUID
    time_window_start: datetime
    time_window_end: datetime
    time_window_type: TimeWindowType

    # Core metrics (always present)
    usage_metrics: UsageFrequencyMetrics
    success_metrics: SuccessMetrics

    # Optional metrics
    performance_metrics: Optional[PerformanceMetrics] = None
    trend_analysis: Optional[TrendAnalysis] = None
    context_distribution: Optional[ContextDistribution] = None

    # Summary
    total_data_points: int = 0
    analytics_quality_score: float = 0.0
    computation_time_ms: float = 0.0

    # Metadata
    correlation_id: UUID = field(default_factory=uuid4)
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert analytics output to dictionary format."""
        result = {
            "pattern_id": str(self.pattern_id),
            "time_window": {
                "start": self.time_window_start.isoformat(),
                "end": self.time_window_end.isoformat(),
                "type": self.time_window_type.value,
            },
            "usage_metrics": {
                "total_executions": self.usage_metrics.total_executions,
                "executions_per_day": self.usage_metrics.executions_per_day,
                "executions_per_week": self.usage_metrics.executions_per_week,
                "executions_per_month": self.usage_metrics.executions_per_month,
                "unique_contexts": self.usage_metrics.unique_contexts,
                "unique_users": self.usage_metrics.unique_users,
                "peak_daily_usage": self.usage_metrics.peak_daily_usage,
                "time_since_last_use": self.usage_metrics.time_since_last_use,
            },
            "success_metrics": {
                "success_count": self.success_metrics.success_count,
                "failure_count": self.success_metrics.failure_count,
                "success_rate": self.success_metrics.success_rate,
                "error_rate": self.success_metrics.error_rate,
                "timeout_count": self.success_metrics.timeout_count,
                "quality_gate_failures": self.success_metrics.quality_gate_failures,
                "avg_quality_score": self.success_metrics.avg_quality_score,
            },
            "summary": {
                "total_data_points": self.total_data_points,
                "analytics_quality_score": self.analytics_quality_score,
                "computation_time_ms": self.computation_time_ms,
            },
            "correlation_id": str(self.correlation_id),
            "computed_at": self.computed_at.isoformat(),
            "metadata": self.metadata,
        }

        # Add optional metrics if present
        if self.performance_metrics:
            result["performance_metrics"] = {
                "avg_execution_time_ms": self.performance_metrics.avg_execution_time_ms,
                "p50_execution_time_ms": self.performance_metrics.p50_execution_time_ms,
                "p95_execution_time_ms": self.performance_metrics.p95_execution_time_ms,
                "p99_execution_time_ms": self.performance_metrics.p99_execution_time_ms,
                "min_execution_time_ms": self.performance_metrics.min_execution_time_ms,
                "max_execution_time_ms": self.performance_metrics.max_execution_time_ms,
                "std_dev_ms": self.performance_metrics.std_dev_ms,
                "total_execution_time_ms": self.performance_metrics.total_execution_time_ms,
            }

        if self.trend_analysis:
            result["trend_analysis"] = {
                "trend_type": self.trend_analysis.trend_type.value,
                "velocity": self.trend_analysis.velocity,
                "acceleration": self.trend_analysis.acceleration,
                "adoption_rate": self.trend_analysis.adoption_rate,
                "retention_rate": self.trend_analysis.retention_rate,
                "churn_rate": self.trend_analysis.churn_rate,
                "growth_percentage": self.trend_analysis.growth_percentage,
                "confidence_score": self.trend_analysis.confidence_score,
            }

        if self.context_distribution:
            result["context_distribution"] = {
                "by_context_type": self.context_distribution.by_context_type,
                "by_agent": self.context_distribution.by_agent,
                "by_project": self.context_distribution.by_project,
                "by_file_type": self.context_distribution.by_file_type,
                "by_time_of_day": self.context_distribution.by_time_of_day,
                "by_day_of_week": self.context_distribution.by_day_of_week,
            }

        return result


# ============================================================================
# ONEX Reducer Contract (Base)
# ============================================================================


@dataclass
class ModelContractUsageAnalytics:
    """
    ONEX Reducer contract for usage analytics operations.

    Reducer nodes handle:
    - Data aggregation and reduction
    - Pure functional transformations
    - No side effects
    - No external I/O (data comes from Effect nodes)

    Attributes:
        name: Operation name
        description: Operation description
        version: Contract version
        node_type: Fixed as 'reducer' for Reducer nodes
        correlation_id: Correlation ID for tracing
        created_at: Contract creation timestamp
    """

    name: str = "usage_analytics_reducer"
    description: str = "Pattern usage analytics aggregation and computation"
    version: str = "1.0.0"
    node_type: str = "reducer"
    correlation_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate contract after initialization."""
        if self.node_type != "reducer":
            raise ValueError(
                f"Invalid node_type for usage analytics: {self.node_type}. "
                "Must be 'reducer'"
            )
