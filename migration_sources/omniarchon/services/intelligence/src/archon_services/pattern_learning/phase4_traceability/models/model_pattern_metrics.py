"""
Phase 4 Traceability - Pattern Metrics Models

Models for tracking pattern usage, performance, and health metrics.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class ModelPatternUsageMetrics(BaseModel):
    """
    Pattern usage metrics for analytics.

    Tracks pattern usage over time with success/failure breakdown.
    """

    pattern_id: UUID = Field(..., description="Pattern UUID")

    pattern_name: str = Field(..., description="Pattern name for display")

    metrics_date: date = Field(..., description="Metrics date")

    execution_count: int = Field(
        default=0, ge=0, description="Total executions on this date"
    )

    success_count: int = Field(default=0, ge=0, description="Successful executions")

    failure_count: int = Field(default=0, ge=0, description="Failed executions")

    success_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Success rate for this date"
    )

    context_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown by context (e.g., {'api_development': 10, 'debugging': 5})",
    )

    avg_execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="Average execution time in milliseconds"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metrics creation timestamp",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "metrics_date": "2025-10-02",
                "execution_count": 42,
                "success_count": 38,
                "failure_count": 4,
                "success_rate": 0.905,
                "context_breakdown": {"api_development": 25, "debugging": 17},
                "avg_execution_time_ms": 450.5,
                "created_at": "2025-10-02T23:59:59Z",
            }
        }
    )


class ModelPatternPerformanceMetrics(BaseModel):
    """
    Pattern performance metrics.

    Detailed performance statistics for pattern execution.
    """

    pattern_id: UUID = Field(..., description="Pattern UUID")

    pattern_name: str = Field(..., description="Pattern name for display")

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metrics timestamp",
    )

    execution_time_ms: float = Field(
        ..., ge=0.0, description="Execution time in milliseconds"
    )

    memory_usage_mb: Optional[float] = Field(
        default=None, ge=0.0, description="Memory usage in megabytes"
    )

    cpu_usage_percent: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="CPU usage percentage"
    )

    http_calls: int = Field(default=0, ge=0, description="Number of HTTP calls made")

    database_queries: int = Field(
        default=0, ge=0, description="Number of database queries"
    )

    cache_hits: int = Field(default=0, ge=0, description="Number of cache hits")

    cache_misses: int = Field(default=0, ge=0, description="Number of cache misses")

    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality score for this execution"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional performance metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "timestamp": "2025-10-02T14:30:00Z",
                "execution_time_ms": 450.5,
                "memory_usage_mb": 125.3,
                "cpu_usage_percent": 45.2,
                "http_calls": 3,
                "database_queries": 5,
                "cache_hits": 8,
                "cache_misses": 2,
                "quality_score": 0.92,
                "metadata": {
                    "context": "api_development",
                    "agent": "agent-debug-intelligence",
                },
            }
        }
    )


class ModelPatternHealthMetrics(BaseModel):
    """
    Overall pattern health metrics.

    Aggregated health indicators for pattern monitoring.
    """

    pattern_id: UUID = Field(..., description="Pattern UUID")

    pattern_name: str = Field(..., description="Pattern name for display")

    time_window_days: int = Field(
        default=7, ge=1, description="Time window for health calculation (days)"
    )

    total_executions: int = Field(
        default=0, ge=0, description="Total executions in time window"
    )

    avg_success_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Average success rate in time window"
    )

    avg_execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="Average execution time in time window"
    )

    p50_execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="Median execution time"
    )

    p95_execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="95th percentile execution time"
    )

    p99_execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="99th percentile execution time"
    )

    error_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Error rate in time window"
    )

    trend: str = Field(
        default="stable",
        description="Usage trend: 'increasing', 'stable', 'decreasing'",
    )

    health_status: str = Field(
        default="healthy",
        description="Overall health: 'healthy', 'warning', 'critical'",
    )

    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )

    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Health calculation timestamp",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "time_window_days": 7,
                "total_executions": 294,
                "avg_success_rate": 0.92,
                "avg_execution_time_ms": 450.5,
                "p50_execution_time_ms": 425.0,
                "p95_execution_time_ms": 650.0,
                "p99_execution_time_ms": 800.0,
                "error_rate": 0.08,
                "trend": "increasing",
                "health_status": "healthy",
                "recommendations": [
                    "Consider caching for improved performance",
                    "Monitor error rate trend",
                ],
                "calculated_at": "2025-10-02T20:00:00Z",
            }
        }
    )


class ModelPatternTrendAnalysis(BaseModel):
    """
    Trend analysis for pattern usage over time.

    Analyzes pattern adoption, growth, and retention trends.
    """

    pattern_id: UUID = Field(..., description="Pattern UUID")

    pattern_name: str = Field(..., description="Pattern name for display")

    analysis_period_days: int = Field(
        default=30, ge=1, description="Analysis period in days"
    )

    daily_executions: List[int] = Field(
        default_factory=list,
        description="Daily execution counts (ordered chronologically)",
    )

    weekly_growth_rate: float = Field(
        default=0.0,
        description="Week-over-week growth rate (e.g., 0.15 for 15% growth)",
    )

    monthly_retention_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Monthly retention rate (0.0-1.0)"
    )

    adoption_velocity: float = Field(
        default=0.0,
        ge=0.0,
        description="Adoption velocity score (higher = faster adoption)",
    )

    trend_direction: str = Field(
        default="stable",
        description="Trend direction: 'growing', 'stable', 'declining'",
    )

    seasonality_detected: bool = Field(
        default=False, description="Whether seasonal patterns detected"
    )

    peak_usage_days: List[str] = Field(
        default_factory=list,
        description="Days of week with peak usage (e.g., ['monday', 'wednesday'])",
    )

    usage_pattern: str = Field(
        default="steady",
        description="Usage pattern: 'steady', 'burst', 'declining', 'growing'",
    )

    forecast_next_week: Optional[float] = Field(
        default=None, ge=0.0, description="Forecasted executions for next week"
    )

    forecast_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in forecast (0.0-1.0)"
    )

    anomalies_detected: List[Dict[str, Any]] = Field(
        default_factory=list, description="Detected usage anomalies"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional trend metadata"
    )

    calculated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analysis calculation timestamp",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
                "pattern_name": "api_debug_pattern",
                "analysis_period_days": 30,
                "daily_executions": [10, 12, 15, 18, 20, 22, 25, 28, 30, 32],
                "weekly_growth_rate": 0.15,
                "monthly_retention_rate": 0.85,
                "adoption_velocity": 0.78,
                "trend_direction": "growing",
                "seasonality_detected": True,
                "peak_usage_days": ["monday", "wednesday", "friday"],
                "usage_pattern": "growing",
                "forecast_next_week": 35.5,
                "forecast_confidence": 0.82,
                "anomalies_detected": [
                    {
                        "date": "2025-10-01",
                        "type": "spike",
                        "magnitude": 2.5,
                        "reason": "new feature launch",
                    }
                ],
                "metadata": {"regression_r2": 0.92, "trend_strength": "strong"},
                "calculated_at": "2025-10-02T20:00:00Z",
            }
        }
    )
