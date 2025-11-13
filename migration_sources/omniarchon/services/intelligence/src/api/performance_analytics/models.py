"""
Pydantic models for Performance Analytics API

Response models for performance baseline reporting, anomaly checking,
and optimization opportunity discovery.

Phase 5C: Performance Intelligence - Workflow 9
Created: 2025-10-15
"""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


# NOTE: correlation_id support enabled for tracing
class BaselineStats(BaseModel):
    """Baseline statistics for an operation"""

    p50: float = Field(
        ..., description="50th percentile (median) duration in milliseconds"
    )
    p95: float = Field(..., description="95th percentile duration in milliseconds")
    p99: float = Field(..., description="99th percentile duration in milliseconds")
    mean: float = Field(..., description="Mean duration in milliseconds")
    std_dev: float = Field(..., description="Standard deviation in milliseconds")
    sample_size: int = Field(..., ge=0, description="Number of measurements used")


class PerformanceMeasurementData(BaseModel):
    """Single performance measurement data point"""

    duration_ms: float = Field(..., description="Operation duration in milliseconds")
    timestamp: datetime = Field(..., description="Measurement timestamp")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class OperationBaseline(BaseModel):
    """Detailed baseline metrics for a specific operation"""

    operation: str = Field(..., description="Operation name")
    baseline: BaselineStats = Field(..., description="Baseline statistics")
    recent_measurements: List[PerformanceMeasurementData] = Field(
        default_factory=list, description="Recent measurements (last 10)"
    )
    trend: str = Field(..., description="Performance trend: improving/declining/stable")
    anomaly_count_24h: int = Field(
        ..., ge=0, description="Number of anomalies detected in last 24h"
    )


class BaselinesResponse(BaseModel):
    """Response model for GET /api/performance-analytics/baselines"""

    baselines: Dict[str, BaselineStats] = Field(
        ..., description="Baseline statistics by operation name"
    )
    total_operations: int = Field(
        ..., ge=0, description="Total number of operations tracked"
    )
    total_measurements: int = Field(
        ..., ge=0, description="Total measurements recorded"
    )
    timestamp: datetime = Field(..., description="Response generation timestamp")


class OptimizationOpportunity(BaseModel):
    """Single optimization opportunity"""

    operation: str = Field(..., description="Operation name")
    current_p95: float = Field(
        ..., description="Current 95th percentile duration in ms"
    )
    estimated_improvement: float = Field(
        ..., ge=0, description="Estimated improvement percentage"
    )
    effort_level: str = Field(..., description="Implementation effort: low/medium/high")
    roi_score: float = Field(..., ge=0, description="Return on investment score")
    priority: str = Field(..., description="Priority level: low/medium/high/critical")
    recommendations: List[str] = Field(
        default_factory=list, description="Specific optimization recommendations"
    )


class OptimizationOpportunitiesResponse(BaseModel):
    """Response model for GET /api/performance-analytics/optimization-opportunities"""

    opportunities: List[OptimizationOpportunity] = Field(
        ..., description="List of optimization opportunities"
    )
    total_opportunities: int = Field(
        ..., ge=0, description="Total opportunities identified"
    )
    avg_roi: float = Field(
        ..., ge=0, description="Average ROI score across all opportunities"
    )
    total_potential_improvement: float = Field(
        ..., ge=0, description="Average improvement potential (%)"
    )


class AnomalyCheckRequest(BaseModel):
    """Request model for POST /api/performance-analytics/operations/{operation}/anomaly-check"""

    duration_ms: float = Field(
        ..., gt=0, description="Current operation duration in milliseconds"
    )


class AnomalyCheckResponse(BaseModel):
    """Response model for anomaly detection"""

    anomaly_detected: bool = Field(..., description="Whether an anomaly was detected")
    z_score: float = Field(..., description="Z-score relative to baseline")
    current_duration_ms: float = Field(
        ..., description="Current operation duration in ms"
    )
    baseline_mean: float = Field(..., description="Baseline mean duration in ms")
    baseline_p95: float = Field(..., description="Baseline 95th percentile in ms")
    deviation_percentage: float = Field(
        ..., description="Percentage deviation from mean"
    )
    severity: str = Field(
        ..., description="Anomaly severity: normal/medium/high/critical"
    )


class OperationTrend(BaseModel):
    """Performance trend for a single operation"""

    trend: str = Field(..., description="Trend direction: improving/declining/stable")
    avg_duration_change: float = Field(
        ..., description="Average duration change percentage"
    )
    anomaly_count: int = Field(
        ..., ge=0, description="Number of anomalies in time window"
    )


class TrendsResponse(BaseModel):
    """Response model for GET /api/performance-analytics/trends"""

    time_window: str = Field(..., description="Time window analyzed (24h/7d/30d)")
    operations: Dict[str, OperationTrend] = Field(
        ..., description="Trends by operation name"
    )
    overall_health: str = Field(
        ..., description="Overall system health: excellent/good/warning/critical"
    )


class HealthResponse(BaseModel):
    """Response model for GET /api/performance-analytics/health"""

    status: str = Field(
        ..., description="Service health status: healthy/degraded/unhealthy"
    )
    baseline_service: str = Field(
        ..., description="Baseline service status: operational/degraded/down"
    )
    optimization_analyzer: str = Field(
        ..., description="Optimization analyzer status: operational/degraded/down"
    )
    total_operations_tracked: int = Field(
        ..., ge=0, description="Number of operations being tracked"
    )
    total_measurements: int = Field(
        ..., ge=0, description="Total measurements recorded"
    )
    uptime_seconds: int = Field(..., ge=0, description="Service uptime in seconds")
