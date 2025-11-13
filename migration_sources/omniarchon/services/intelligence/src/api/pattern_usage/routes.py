"""
Pattern Usage API Routes

FastAPI router for pattern usage tracking and analytics.
Provides endpoints to query pattern usage statistics, trends, and analytics.

Created: 2025-10-28
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from src.config.database import get_db_pool
from src.usage_tracking.analytics import (
    PatternUsageStats,
    TrendDirection,
    UsageAnalytics,
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/patterns/usage", tags=["Pattern Usage"])


# Response models
class PatternUsageResponse(BaseModel):
    """Response model for pattern usage statistics."""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    usage_count: int
    last_used_at: Optional[str]
    used_by_agents: List[str]
    agent_count: int
    trend: str
    trend_percentage: float
    first_used_at: Optional[str]
    days_since_last_use: Optional[int]


class TopPatternsResponse(BaseModel):
    """Response model for top patterns list."""

    patterns: List[PatternUsageResponse]
    total_count: int


class UnusedPattern(BaseModel):
    """Unused pattern model."""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    created_at: str
    age_days: int
    usage_count: int


class UnusedPatternsResponse(BaseModel):
    """Response model for unused patterns."""

    patterns: List[UnusedPattern]
    total_count: int


class StalePattern(BaseModel):
    """Stale pattern model."""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    usage_count: int
    last_used_at: Optional[str]
    days_since_use: Optional[int]


class StalePatternsResponse(BaseModel):
    """Response model for stale patterns."""

    patterns: List[StalePattern]
    total_count: int


class AgentUsagePattern(BaseModel):
    """Pattern used by agent."""

    pattern_id: str
    pattern_name: str
    pattern_type: str
    usage_count: int
    last_used_at: Optional[str]
    used_by_agents: List[str]


class AgentUsageResponse(BaseModel):
    """Response model for agent usage."""

    agent_name: str
    patterns: List[AgentUsagePattern]
    pattern_count: int


class UsageSummaryResponse(BaseModel):
    """Response model for usage summary."""

    total_patterns: int
    used_patterns: int
    unused_patterns: int
    total_usage: int
    avg_usage_per_pattern: float
    usage_rate: float
    total_agents: int


# Initialize analytics service
async def get_analytics() -> UsageAnalytics:
    """Get usage analytics instance with database pool."""
    db_pool = await get_db_pool()
    return UsageAnalytics(db_pool)


@router.get(
    "/{pattern_id}",
    response_model=PatternUsageResponse,
    summary="Get Pattern Usage Statistics",
    description="Get usage statistics for a specific pattern including usage count, trends, and agent usage.",
)
async def get_pattern_usage(
    pattern_id: str,
    include_trend: bool = Query(True, description="Include trend calculation"),
):
    """
    Get usage statistics for a specific pattern.

    Args:
        pattern_id: Pattern ID to query
        include_trend: Whether to include trend calculation

    Returns:
        Pattern usage statistics

    Raises:
        HTTPException: 404 if pattern not found
    """
    try:
        analytics = await get_analytics()
        stats = await analytics.get_pattern_usage(pattern_id, include_trend)

        if not stats:
            raise HTTPException(
                status_code=404, detail=f"Pattern not found: {pattern_id}"
            )

        return PatternUsageResponse(
            pattern_id=stats.pattern_id,
            pattern_name=stats.pattern_name,
            pattern_type=stats.pattern_type,
            usage_count=stats.usage_count,
            last_used_at=stats.last_used_at.isoformat() if stats.last_used_at else None,
            used_by_agents=stats.used_by_agents,
            agent_count=stats.agent_count,
            trend=stats.trend_direction.value,
            trend_percentage=stats.trend_percentage,
            first_used_at=(
                stats.first_used_at.isoformat() if stats.first_used_at else None
            ),
            days_since_last_use=stats.days_since_last_use,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting pattern usage for {pattern_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/top",
    response_model=TopPatternsResponse,
    summary="Get Top Used Patterns",
    description="Get most used patterns sorted by usage count.",
)
async def get_top_patterns(
    limit: int = Query(20, ge=1, le=100, description="Number of patterns to return"),
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
):
    """
    Get most used patterns.

    Args:
        limit: Number of patterns to return (1-100)
        pattern_type: Optional pattern type filter

    Returns:
        List of top used patterns
    """
    try:
        analytics = await get_analytics()
        patterns = await analytics.get_top_patterns(limit, pattern_type)

        return TopPatternsResponse(
            patterns=[
                PatternUsageResponse(
                    pattern_id=p.pattern_id,
                    pattern_name=p.pattern_name,
                    pattern_type=p.pattern_type,
                    usage_count=p.usage_count,
                    last_used_at=p.last_used_at.isoformat() if p.last_used_at else None,
                    used_by_agents=p.used_by_agents,
                    agent_count=p.agent_count,
                    trend=p.trend_direction.value,
                    trend_percentage=p.trend_percentage,
                    first_used_at=(
                        p.first_used_at.isoformat() if p.first_used_at else None
                    ),
                    days_since_last_use=p.days_since_last_use,
                )
                for p in patterns
            ],
            total_count=len(patterns),
        )

    except Exception as e:
        logger.error(f"Error getting top patterns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/unused",
    response_model=UnusedPatternsResponse,
    summary="Get Unused Patterns",
    description="Get patterns that have never been used. Useful for identifying candidates for removal.",
)
async def get_unused_patterns(
    min_age_days: int = Query(
        30, ge=1, le=365, description="Minimum age in days to consider"
    ),
):
    """
    Get patterns that have never been used.

    Args:
        min_age_days: Minimum age in days (avoids flagging new patterns)

    Returns:
        List of unused patterns
    """
    try:
        analytics = await get_analytics()
        patterns = await analytics.get_unused_patterns(min_age_days)

        return UnusedPatternsResponse(
            patterns=[UnusedPattern(**p) for p in patterns],
            total_count=len(patterns),
        )

    except Exception as e:
        logger.error(f"Error getting unused patterns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stale",
    response_model=StalePatternsResponse,
    summary="Get Stale Patterns",
    description="Get patterns not used in specified number of days.",
)
async def get_stale_patterns(
    days_inactive: int = Query(
        90, ge=1, le=365, description="Days of inactivity threshold"
    ),
):
    """
    Get patterns not used recently.

    Args:
        days_inactive: Days of inactivity threshold

    Returns:
        List of stale patterns
    """
    try:
        analytics = await get_analytics()
        patterns = await analytics.get_stale_patterns(days_inactive)

        return StalePatternsResponse(
            patterns=[StalePattern(**p) for p in patterns],
            total_count=len(patterns),
        )

    except Exception as e:
        logger.error(f"Error getting stale patterns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-agent/{agent_name}",
    response_model=AgentUsageResponse,
    summary="Get Patterns Used by Agent",
    description="Get all patterns used by a specific agent.",
)
async def get_usage_by_agent(
    agent_name: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum patterns to return"),
):
    """
    Get patterns used by a specific agent.

    Args:
        agent_name: Agent name to query
        limit: Maximum number of patterns to return

    Returns:
        List of patterns used by the agent
    """
    try:
        analytics = await get_analytics()
        patterns = await analytics.get_usage_by_agent(agent_name, limit)

        return AgentUsageResponse(
            agent_name=agent_name,
            patterns=[AgentUsagePattern(**p) for p in patterns],
            pattern_count=len(patterns),
        )

    except Exception as e:
        logger.error(f"Error getting usage by agent {agent_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    summary="Get Usage Summary",
    description="Get overall usage summary statistics across all patterns.",
)
async def get_usage_summary():
    """
    Get overall usage summary statistics.

    Returns:
        Summary statistics including total patterns, usage rates, etc.
    """
    try:
        analytics = await get_analytics()
        summary = await analytics.get_usage_summary()

        return UsageSummaryResponse(**summary)

    except Exception as e:
        logger.error(f"Error getting usage summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
