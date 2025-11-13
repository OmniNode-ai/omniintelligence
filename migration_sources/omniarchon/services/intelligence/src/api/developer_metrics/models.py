"""
Pydantic models for Developer Metrics API

Response models for developer experience and productivity metrics.

Created: 2025-10-28
Correlation ID: 86e57c28-0af3-4f1f-afda-81d11b877258
"""

from pydantic import BaseModel, Field


class DeveloperMetricsResponse(BaseModel):
    """Response model for GET /api/intelligence/developer/metrics"""

    avg_commit_time: str = Field(
        ...,
        description="Average time to complete a commit (formatted as 12m, 2.5h, etc.)",
    )
    code_review_time: str = Field(
        ..., description="Average code review time (formatted as 2.5h, 1.2d, etc.)"
    )
    build_success_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Build/execution success rate (0.0 - 1.0)"
    )
    test_coverage: float = Field(
        ..., ge=0.0, le=1.0, description="Test coverage percentage (0.0 - 1.0)"
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""

    status: str = Field(
        ..., description="Service health status: healthy/degraded/unhealthy"
    )
    database_connection: str = Field(
        ..., description="Database connection status: operational/degraded/down"
    )
    uptime_seconds: int = Field(..., ge=0, description="Service uptime in seconds")
