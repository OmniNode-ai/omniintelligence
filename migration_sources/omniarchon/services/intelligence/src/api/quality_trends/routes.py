"""
Quality Trends API Routes

FastAPI endpoints for quality history tracking, trend analysis, and regression detection.
Part of Phase 5B: Quality Intelligence Upgrades.

Endpoints:
- GET /project/{project_id}/trend - Get quality trend for project with optional snapshots from database
- GET /project/{project_id}/file/{file_path:path}/history - Get file quality history
- POST /detect-regression - Detect quality regression

Refactored to use shared error handling utilities for consistency and maintainability.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.api.pattern_analytics.service import PatternAnalyticsService
from src.api.utils import api_error_handler
from src.archon_services.quality.quality_history import QualityHistoryService

logger = logging.getLogger(__name__)

# Initialize quality history service (singleton)
quality_history_service = QualityHistoryService()

# Initialize pattern analytics service (for database queries)
# Note: db_pool will be injected via initialize_db_pool() if available
pattern_analytics_service: Optional[PatternAnalyticsService] = None

# Create router
router = APIRouter(prefix="/api/quality-trends", tags=["Quality Trends"])


def initialize_db_pool(db_pool):
    """
    Initialize database pool for pattern analytics service.
    Called from app.py during startup.

    Args:
        db_pool: asyncpg connection pool
    """
    global pattern_analytics_service
    pattern_analytics_service = PatternAnalyticsService(db_pool=db_pool)
    logger.info("Database pool initialized for quality trends with snapshots support")


class QualitySnapshotRequest(BaseModel):
    """Request model for recording a quality snapshot"""

    project_id: str = Field(..., description="Project identifier")
    file_path: str = Field(..., description="File path")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Quality score (0-1)")
    onex_compliance_score: float = Field(
        ..., ge=0.0, le=1.0, description="ONEX compliance score (0-1)"
    )
    violations: list[str] = Field(
        default_factory=list, description="List of violations"
    )
    warnings: list[str] = Field(default_factory=list, description="List of warnings")
    correlation_id: str = Field(..., description="Correlation ID for traceability")


class RegressionDetectionRequest(BaseModel):
    """Request model for regression detection"""

    project_id: str = Field(..., description="Project identifier")
    current_score: float = Field(
        ..., ge=0.0, le=1.0, description="Current quality score to check"
    )
    threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Regression threshold (default: 0.1)"
    )


@router.post("/snapshot")
@api_error_handler("record_quality_snapshot")
async def record_quality_snapshot(request: QualitySnapshotRequest):
    """
    Record a quality snapshot for trend tracking.

    This endpoint is typically called by validation handlers to record
    quality metrics over time.
    """
    validation_result = {
        "quality_score": request.quality_score,
        "onex_compliance_score": request.onex_compliance_score,
        "violations": request.violations,
        "warnings": request.warnings,
    }

    await quality_history_service.record_snapshot(
        project_id=request.project_id,
        file_path=request.file_path,
        validation_result=validation_result,
        correlation_id=request.correlation_id,
    )

    return {
        "success": True,
        "message": "Quality snapshot recorded successfully",
        "project_id": request.project_id,
        "file_path": request.file_path,
        "quality_score": request.quality_score,
    }


@router.get("/project/{project_id}/trend")
@api_error_handler("get_project_quality_trend")
async def get_project_quality_trend(
    project_id: str,
    time_window_days: int = Query(
        30, ge=1, le=365, description="Time window in days (legacy parameter)"
    ),
    hours: int = Query(
        None,
        ge=1,
        le=8760,
        description="Time window in hours (preferred for dashboard)",
    ),
):
    """
    Get quality trend for a project over time with optional snapshots array.

    **NEW**: When `hours` parameter is provided and database is available,
    returns enhanced response with time-series snapshots from pattern_quality_metrics table.

    Uses linear regression to calculate trend slope and determine if quality
    is improving, declining, or stable.

    Args:
        project_id: Project identifier
        time_window_days: Time window in days (default: 30, max: 365) - used for in-memory fallback
        hours: Time window in hours (preferred) - enables database query with snapshots

    Returns:
        Quality trend analysis including:
        - success: Boolean indicating successful query
        - project_id: Project identifier
        - trend: "improving" | "declining" | "stable" | "insufficient_data"
        - avg_quality: Average quality in time window
        - snapshots_count: Number of snapshots analyzed
        - snapshots: (NEW) Array of time-series data points with:
            - timestamp: ISO timestamp
            - overall_quality: Average quality score
            - file_count: Number of unique patterns measured

    Dashboard Integration:
        Use `hours` parameter to get snapshots from database:
        - GET /api/quality-trends/project/default/trend?hours=24
        - Response includes snapshots array for time-series visualization
    """
    # Try database-backed query first if hours parameter provided and service available
    if hours is not None and pattern_analytics_service is not None:
        try:
            logger.info(
                f"Using database query for quality trend | "
                f"project_id={project_id} | hours={hours}"
            )
            trend_data = (
                await pattern_analytics_service.get_quality_trend_with_snapshots(
                    project_id=project_id,
                    hours=hours,
                )
            )
            return trend_data
        except Exception as e:
            logger.warning(
                f"Database query failed, falling back to in-memory | "
                f"project_id={project_id}: {e}"
            )
            # Fall through to in-memory fallback

    # Fallback to in-memory quality history service
    logger.info(
        f"Using in-memory quality trend | "
        f"project_id={project_id} | time_window_days={time_window_days}"
    )
    trend_data = await quality_history_service.get_quality_trend(
        project_id=project_id,
        file_path=None,  # Project-level trend
        time_window_days=time_window_days,
    )

    return {"success": True, "project_id": project_id, **trend_data}


@router.get("/project/{project_id}/file/{file_path:path}/trend")
@api_error_handler("get_file_quality_trend")
async def get_file_quality_trend(
    project_id: str,
    file_path: str,
    time_window_days: int = Query(30, ge=1, le=365, description="Time window in days"),
):
    """
    Get quality trend for a specific file over time.

    Args:
        project_id: Project identifier
        file_path: File path
        time_window_days: Time window in days (default: 30, max: 365)

    Returns:
        Quality trend analysis for the specific file
    """
    trend_data = await quality_history_service.get_quality_trend(
        project_id=project_id, file_path=file_path, time_window_days=time_window_days
    )

    return {
        "success": True,
        "project_id": project_id,
        "file_path": file_path,
        **trend_data,
    }


@router.get("/project/{project_id}/file/{file_path:path}/history")
@api_error_handler("get_file_quality_history")
async def get_file_quality_history(
    project_id: str,
    file_path: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of snapshots"),
):
    """
    Get quality history for a specific file.

    Returns historical quality snapshots sorted by timestamp (newest first).

    Args:
        project_id: Project identifier
        file_path: File path
        limit: Maximum number of snapshots to return (default: 50, max: 200)

    Returns:
        List of quality snapshots with timestamps, scores, violations, and warnings
    """
    history = await quality_history_service.get_quality_history(
        project_id=project_id, file_path=file_path, limit=limit
    )

    return {
        "success": True,
        "project_id": project_id,
        "file_path": file_path,
        "snapshots_count": len(history),
        "history": history,
    }


@router.post("/detect-regression")
@api_error_handler("detect_quality_regression")
async def detect_quality_regression(request: RegressionDetectionRequest):
    """
    Detect quality regression by comparing current score to recent average.

    Compares the current quality score against the average of the last 10 snapshots.
    A regression is detected if the current score falls below the average by more
    than the threshold (default: 0.1 or 10%).

    Args:
        request: RegressionDetectionRequest with project_id, current_score, and threshold

    Returns:
        Regression detection result including:
        - regression_detected: Boolean indicating if regression was detected
        - current_score: Score being checked
        - avg_recent_score: Average of recent snapshots
        - difference: Difference from average
        - threshold: Threshold used for detection
    """
    regression_result = await quality_history_service.detect_quality_regression(
        project_id=request.project_id,
        current_score=request.current_score,
        threshold=request.threshold,
    )

    return {"success": True, "project_id": request.project_id, **regression_result}


@router.get("/stats")
async def get_quality_history_stats():
    """
    Get statistics about the quality history service.

    Returns:
        Statistics including total snapshots stored
    """
    try:
        total_snapshots = quality_history_service.get_snapshot_count()

        return {
            "success": True,
            "total_snapshots": total_snapshots,
            "service_status": "active",
        }

    except Exception as e:
        logger.error(f"Failed to get quality history stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/project/{project_id}/snapshots")
async def clear_project_snapshots(project_id: str):
    """
    Clear all snapshots for a specific project.

    WARNING: This operation cannot be undone.

    Args:
        project_id: Project identifier

    Returns:
        Number of snapshots cleared
    """
    try:
        cleared_count = quality_history_service.clear_snapshots(project_id=project_id)

        return {
            "success": True,
            "project_id": project_id,
            "cleared_snapshots": cleared_count,
            "message": f"Cleared {cleared_count} snapshots for project {project_id}",
        }

    except Exception as e:
        logger.error(f"Failed to clear snapshots for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
