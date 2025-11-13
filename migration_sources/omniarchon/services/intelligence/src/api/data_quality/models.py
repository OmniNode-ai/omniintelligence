"""
Data Quality API Models

Pydantic models for data quality monitoring and orphan tracking endpoints.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class OrphanCountResponse(BaseModel):
    """Response model for orphan count endpoint."""

    orphan_count: int = Field(..., description="Number of orphaned FILE nodes")
    total_files: int = Field(..., description="Total number of FILE nodes")
    orphan_percentage: float = Field(..., description="Percentage of orphaned files")
    timestamp: str = Field(..., description="Timestamp of the check (ISO format)")


class TreeHealthResponse(BaseModel):
    """Response model for tree health endpoint."""

    project_nodes: int = Field(..., description="Number of PROJECT nodes")
    directory_nodes: int = Field(..., description="Number of DIRECTORY nodes")
    contains_relationships: int = Field(
        ..., description="Number of CONTAINS relationships"
    )
    orphan_count: int = Field(..., description="Number of orphaned FILE nodes")
    total_files: int = Field(..., description="Total number of FILE nodes")
    orphan_percentage: float = Field(..., description="Percentage of orphaned files")
    health_status: str = Field(
        ..., description="Overall health status: 'healthy', 'degraded', or 'critical'"
    )
    timestamp: str = Field(..., description="Timestamp of the check (ISO format)")


class OrphanMetricDataPoint(BaseModel):
    """Single data point in orphan metrics history."""

    timestamp: str = Field(..., description="Timestamp (ISO format)")
    orphan_count: int = Field(..., description="Orphan count at this time")
    orphan_percentage: float = Field(..., description="Orphan percentage at this time")


class MetricsHistoryResponse(BaseModel):
    """Response model for metrics history endpoint."""

    total_entries: int = Field(..., description="Total number of historical entries")
    time_range_hours: Optional[float] = Field(
        None, description="Time range covered (hours)"
    )
    metrics: List[OrphanMetricDataPoint] = Field(
        ..., description="Historical metrics data points"
    )
    growth_rate_per_hour: Optional[float] = Field(
        None, description="Calculated growth rate (orphans per hour)"
    )
    growth_rate_per_day: Optional[float] = Field(
        None, description="Calculated growth rate (orphans per day)"
    )


class AlertRequest(BaseModel):
    """Request model for triggering manual alert."""

    severity: str = Field(
        "warning", description="Alert severity: 'info', 'warning', or 'critical'"
    )
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    context: Optional[Dict] = Field(None, description="Additional context data")


class AlertResponse(BaseModel):
    """Response model for alert endpoint."""

    alert_id: str = Field(..., description="Unique alert identifier")
    timestamp: str = Field(..., description="Alert timestamp (ISO format)")
    severity: str = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    sent: bool = Field(..., description="Whether alert was sent successfully")


class DataQualityMetrics(BaseModel):
    """Complete data quality metrics."""

    orphan_count: int
    total_files: int
    orphan_percentage: float
    project_nodes: int
    directory_nodes: int
    contains_relationships: int
    health_status: str
    ingestion_success_rate: Optional[float] = None
    timestamp: str


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(
        ..., description="Service health status: 'healthy', 'degraded', or 'unhealthy'"
    )
    timestamp: str = Field(..., description="Timestamp (ISO format)")
    checks: Dict[str, bool] = Field(..., description="Individual health checks")
    message: Optional[str] = Field(None, description="Additional health information")
