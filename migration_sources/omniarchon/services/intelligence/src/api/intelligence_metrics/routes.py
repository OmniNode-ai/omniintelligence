"""
Intelligence Metrics API Routes

FastAPI router for intelligence-driven quality improvement metrics:
1. GET /api/intelligence/metrics/quality-impact - Quality improvement tracking

Performance Target: <200ms for dashboard queries
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from src.api.intelligence_metrics.models import (
    OperationsPerMinuteResponse,
    QualityImpactResponse,
    QualityImprovementData,
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/intelligence/metrics", tags=["intelligence-metrics"])

# Global database pool (initialized externally)
_db_pool: Optional[asyncpg.Pool] = None


def initialize_db_pool(pool: asyncpg.Pool):
    """
    Initialize database pool for intelligence metrics.

    Called from app.py lifespan to inject database pool.
    """
    global _db_pool
    _db_pool = pool
    logger.info("Intelligence Metrics API database pool initialized")


def _get_time_window_hours(time_window: str) -> int:
    """Convert time window string to hours"""
    time_windows = {
        "1h": 1,
        "24h": 24,
        "7d": 24 * 7,
        "30d": 24 * 30,
    }
    return time_windows.get(time_window, 24)


@router.get(
    "/quality-impact",
    response_model=QualityImpactResponse,
    summary="Get Quality Improvement Impact",
    description=(
        "Returns quality improvement metrics showing the impact of pattern "
        "applications over time. Calculates before/after quality deltas from "
        "pattern_quality_metrics table."
    ),
)
async def get_quality_impact(
    time_window: str = Query(
        default="24h",
        description="Time window for analysis (1h, 24h, 7d, 30d)",
        pattern="^(1h|24h|7d|30d)$",
    ),
):
    """
    Get quality improvement impact metrics.

    Query Parameters:
    - time_window: Time window for analysis (1h, 24h, 7d, 30d)

    Response:
    - improvements: List of quality improvement data points
    - total_improvements: Count of improvement records
    - avg_impact: Average quality improvement
    - max_impact: Maximum quality improvement
    - min_impact: Minimum quality improvement
    - time_window: Requested time window
    - generated_at: Response timestamp
    """
    try:
        logger.info(
            f"GET /api/intelligence/metrics/quality-impact | time_window={time_window}"
        )

        if not _db_pool:
            raise HTTPException(
                status_code=503,
                detail="Database pool not initialized",
            )

        # Calculate time range
        hours = _get_time_window_hours(time_window)
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Query pattern quality metrics with consecutive measurements
        # Calculate impact as delta between consecutive quality scores
        query = """
        WITH ranked_metrics AS (
            SELECT
                pqm.pattern_id,
                pqm.quality_score,
                pqm.confidence,
                pqm.measurement_timestamp,
                pqm.version,
                pln.pattern_name,
                LAG(pqm.quality_score) OVER (
                    PARTITION BY pqm.pattern_id
                    ORDER BY pqm.measurement_timestamp
                ) as previous_quality,
                LAG(pqm.measurement_timestamp) OVER (
                    PARTITION BY pqm.pattern_id
                    ORDER BY pqm.measurement_timestamp
                ) as previous_timestamp
            FROM pattern_quality_metrics pqm
            LEFT JOIN pattern_lineage_nodes pln ON pln.id = pqm.pattern_id
            WHERE pqm.measurement_timestamp >= $1
            ORDER BY pqm.measurement_timestamp DESC
        )
        SELECT
            pattern_id,
            pattern_name,
            quality_score as after_quality,
            previous_quality as before_quality,
            (quality_score - previous_quality) as impact,
            measurement_timestamp as timestamp,
            confidence
        FROM ranked_metrics
        WHERE previous_quality IS NOT NULL
            AND previous_timestamp IS NOT NULL
            AND (quality_score - previous_quality) != 0
        ORDER BY measurement_timestamp DESC
        LIMIT 1000;
        """

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(query, start_time)

        # Process results
        improvements = []
        for row in rows:
            improvements.append(
                QualityImprovementData(
                    timestamp=row["timestamp"],
                    before_quality=float(row["before_quality"]),
                    after_quality=float(row["after_quality"]),
                    impact=float(row["impact"]),
                    pattern_applied=row["pattern_name"] or "unknown",
                    pattern_id=str(row["pattern_id"]),
                    confidence=float(row["confidence"]) if row["confidence"] else None,
                )
            )

        # Calculate statistics
        if improvements:
            impacts = [imp.impact for imp in improvements]
            avg_impact = sum(impacts) / len(impacts)
            max_impact = max(impacts)
            min_impact = min(impacts)
        else:
            avg_impact = 0.0
            max_impact = 0.0
            min_impact = 0.0

        return QualityImpactResponse(
            improvements=improvements,
            total_improvements=len(improvements),
            avg_impact=round(avg_impact, 4),
            max_impact=round(max_impact, 4),
            min_impact=round(min_impact, 4),
            time_window=time_window,
            generated_at=datetime.now(timezone.utc),
        )

    except asyncpg.PostgresError as e:
        logger.error(f"Database error in quality-impact endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in quality-impact endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get(
    "/operations-per-minute",
    response_model=OperationsPerMinuteResponse,
    summary="Get Operations Per Minute Metrics",
    description=(
        "Returns minute-by-minute operation counts from the agent_actions table "
        "for dashboard graphing. Shows total operations per minute across all agents."
    ),
)
async def get_operations_per_minute(
    time_window: str = Query(
        default="24h",
        description="Time window for analysis (1h, 24h, 7d, 30d)",
        pattern="^(1h|24h|7d|30d)$",
    ),
):
    """
    Get operations-per-minute metrics for dashboard graphing.

    Query Parameters:
    - time_window: Time window for analysis (1h, 24h, 7d, 30d)

    Response:
    - timestamps: List of timestamps (truncated to minute)
    - operations: List of operation counts per timestamp
    - time_window: Requested time window
    - total_operations: Total operations in the time window
    - avg_operations_per_minute: Average operations per minute

    Performance Target: <200ms for dashboard queries
    """
    try:
        logger.info(
            f"GET /api/intelligence/metrics/operations-per-minute | time_window={time_window}"
        )

        if not _db_pool:
            raise HTTPException(
                status_code=503,
                detail="Database pool not initialized",
            )

        # Calculate time range
        hours = _get_time_window_hours(time_window)
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Query agent_actions table for operations per minute
        query = """
        SELECT
            DATE_TRUNC('minute', created_at) as timestamp,
            COUNT(*) as operations
        FROM agent_actions
        WHERE created_at >= $1
        GROUP BY DATE_TRUNC('minute', created_at)
        ORDER BY timestamp ASC;
        """

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(query, start_time)

        # Process results
        timestamps = []
        operations = []
        total_operations = 0

        for row in rows:
            timestamps.append(row["timestamp"])
            op_count = int(row["operations"])
            operations.append(op_count)
            total_operations += op_count

        # Calculate average
        avg_operations = total_operations / len(timestamps) if timestamps else 0.0

        return OperationsPerMinuteResponse(
            timestamps=timestamps,
            operations=operations,
            time_window=time_window,
            total_operations=total_operations,
            avg_operations_per_minute=round(avg_operations, 2),
        )

    except asyncpg.PostgresError as e:
        logger.error(f"Database error in operations-per-minute endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in operations-per-minute endpoint: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for intelligence metrics API"""
    return {
        "status": "healthy" if _db_pool else "degraded",
        "service": "intelligence-metrics-api",
        "database_pool_initialized": _db_pool is not None,
    }
