"""
Pattern Analytics API Routes

FastAPI router for pattern success rate tracking and analytics reporting.
Part of MVP Phase 5A - Intelligence Features Enhancement.

Refactored to use shared error handling utilities for consistency and maintainability.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from src.api.pattern_analytics.models import (
    DiscoveryRateResponse,
    EmergingPatternsResponse,
    InfrastructureHealthResponse,
    PatternHistoryResponse,
    PatternRelationshipsResponse,
    PatternSearchResponse,
    PatternStatsResponse,
    PatternSuccessRatesResponse,
    QualityTrendsResponse,
    TopPatternsResponse,
    TopPerformingResponse,
    UsageStatsResponse,
)
from src.api.pattern_analytics.service import PatternAnalyticsService
from src.api.utils import api_error_handler, handle_not_found

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/pattern-analytics", tags=["Pattern Analytics"])

# Initialize service (will be used by all endpoints)
pattern_analytics_service = PatternAnalyticsService()


@router.get(
    "/success-rates",
    response_model=PatternSuccessRatesResponse,
    summary="Get Pattern Success Rates",
    description=(
        "Get success rates for all patterns with optional filtering. "
        "Success rate is calculated as the ratio of successful executions to total executions. "
        "Confidence is adjusted based on sample size (full confidence at 30+ samples)."
    ),
)
@api_error_handler("get_pattern_success_rates")
async def get_pattern_success_rates(
    pattern_type: Optional[str] = Query(
        None,
        description="Filter by pattern type (architectural, quality, performance, reliability, etc.)",
    ),
    min_samples: int = Query(
        5,
        ge=1,
        le=1000,
        description="Minimum number of feedback samples required for inclusion",
    ),
):
    """
    Get success rates for all patterns.

    Returns patterns sorted by success rate descending, with summary statistics.

    **Query Parameters:**
    - pattern_type: Optional filter by pattern type
    - min_samples: Minimum sample size (default: 5)

    **Response:**
    - patterns: List of pattern success rates with metrics
    - summary: Aggregate statistics (total patterns, average success rate, high confidence count)
    """
    result = await pattern_analytics_service.get_pattern_success_rates(
        pattern_type=pattern_type,
        min_samples=min_samples,
    )

    logger.info(
        f"Success rates retrieved | total_patterns={result['summary']['total_patterns']}"
    )

    return PatternSuccessRatesResponse(**result)


@router.get(
    "/top-patterns",
    response_model=TopPatternsResponse,
    summary="Get Top Performing Patterns",
    description=(
        "Get top performing patterns by node type, ranked by weighted score (success_rate * confidence). "
        "Useful for identifying the most reliable patterns for a given ONEX node type."
    ),
)
@api_error_handler("get_top_performing_patterns")
async def get_top_performing_patterns(
    node_type: Optional[str] = Query(
        None,
        description="Filter by ONEX node type (Effect, Compute, Reducer, Orchestrator)",
    ),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of top patterns to return"
    ),
):
    """
    Get top performing patterns by node type.

    Returns patterns ranked by weighted performance score (success_rate * confidence).

    **Query Parameters:**
    - node_type: Optional filter by ONEX node type
    - limit: Maximum results (default: 10, max: 100)

    **Response:**
    - top_patterns: List of top patterns with ranking
    - total_patterns: Number of patterns returned
    - filter_criteria: Applied filters
    """
    result = await pattern_analytics_service.get_top_performing_patterns(
        node_type=node_type,
        limit=limit,
    )

    logger.info(f"Top patterns retrieved | count={result['total_patterns']}")

    return TopPatternsResponse(**result)


@router.get(
    "/emerging-patterns",
    response_model=EmergingPatternsResponse,
    summary="Get Emerging Patterns",
    description=(
        "Get patterns that are emerging recently based on usage frequency and growth rate. "
        "Useful for identifying new patterns gaining adoption."
    ),
)
@api_error_handler("get_emerging_patterns")
async def get_emerging_patterns(
    min_frequency: int = Query(
        5, ge=1, le=1000, description="Minimum usage frequency in time window"
    ),
    time_window_hours: int = Query(
        24, ge=1, le=720, description="Time window for analysis (hours, max: 30 days)"
    ),
):
    """
    Get patterns that are emerging recently.

    Returns patterns sorted by growth rate, showing recent adoption trends.

    **Query Parameters:**
    - min_frequency: Minimum usage count in time window (default: 5)
    - time_window_hours: Analysis time window (default: 24 hours)

    **Response:**
    - emerging_patterns: List of emerging patterns with growth metrics
    - total_emerging: Number of emerging patterns found
    - time_window_hours: Analysis window
    - filter_criteria: Applied filters
    """
    result = await pattern_analytics_service.get_emerging_patterns(
        min_frequency=min_frequency,
        time_window_hours=time_window_hours,
    )

    logger.info(f"Emerging patterns detected | count={result['total_emerging']}")

    return EmergingPatternsResponse(**result)


@router.get(
    "/usage-stats",
    response_model=UsageStatsResponse,
    summary="Get Pattern Usage Statistics",
    description=(
        "Get usage statistics for patterns with time-based aggregation. "
        "Returns usage counts per time period for trend analysis."
    ),
)
@api_error_handler("get_usage_stats")
async def get_usage_stats(
    pattern_id: Optional[str] = Query(
        None,
        description="Filter to specific pattern ID (optional)",
    ),
    time_range: str = Query(
        "7d",
        description="Time range for analysis (1d, 7d, 30d, 90d)",
    ),
    group_by: str = Query(
        "day",
        description="Aggregation granularity (hour, day, week)",
    ),
):
    """
    Get usage statistics for patterns.

    Returns usage counts aggregated by time bucket for each pattern.

    **Query Parameters:**
    - pattern_id: Optional filter to specific pattern
    - time_range: Time window (1d=1 day, 7d=7 days, 30d=30 days, 90d=90 days)
    - group_by: Time bucket granularity (hour, day, or week)

    **Response:**
    - patterns: List of patterns with usage data points
    - time_range: Time range analyzed
    - granularity: Data granularity used
    - total_patterns: Number of patterns with usage data
    """
    from uuid import UUID

    # Convert pattern_id string to UUID if provided
    pattern_uuid = None
    if pattern_id:
        try:
            pattern_uuid = UUID(pattern_id)
        except ValueError:
            logger.warning(f"Invalid pattern_id format: {pattern_id}")
            # Continue with None, will return empty result

    result = await pattern_analytics_service.get_usage_stats(
        pattern_id=pattern_uuid,
        time_range=time_range,
        group_by=group_by,
    )

    logger.info(
        f"Usage stats retrieved | total_patterns={result['total_patterns']} | time_range={time_range} | granularity={group_by}"
    )

    return UsageStatsResponse(**result)


@router.get(
    "/pattern/{pattern_id}/history",
    response_model=PatternHistoryResponse,
    summary="Get Pattern Feedback History",
    description=(
        "Get complete feedback history for a specific pattern, including all execution results, "
        "quality scores, and performance metrics."
    ),
)
@api_error_handler("get_pattern_feedback_history")
async def get_pattern_feedback_history(
    pattern_id: str,
):
    """
    Get feedback history for a specific pattern.

    Returns all feedback items for the pattern, sorted by timestamp (most recent first),
    with summary statistics.

    **Path Parameters:**
    - pattern_id: Unique pattern identifier

    **Response:**
    - pattern_id: Pattern identifier
    - pattern_name: Pattern display name
    - feedback_history: List of feedback items with execution details
    - summary: Aggregate statistics (success rate, quality scores, execution times)
    """
    result = await pattern_analytics_service.get_pattern_feedback_history(
        pattern_id=pattern_id,
    )

    if result["summary"]["total_feedback"] == 0:
        raise handle_not_found("pattern feedback", pattern_id)

    logger.info(
        f"Feedback history retrieved | pattern_id={pattern_id} | total_feedback={result['summary']['total_feedback']}"
    )

    return PatternHistoryResponse(**result)


@router.get(
    "/health",
    summary="Infrastructure Health Check",
    description="Check infrastructure service health (Qdrant, PostgreSQL, Kafka)",
)
@api_error_handler("get_infrastructure_health")
async def health_check(
    use_cache: bool = Query(
        True,
        description="Use cached health results if available (30s TTL)",
    )
):
    """
    Infrastructure health check for Pattern Dashboard.

    Checks health of:
    - Qdrant vector database
    - PostgreSQL database
    - Kafka message broker

    **Query Parameters:**
    - use_cache: Use cached results if available (default: True)

    **Response:**
    - overall_status: Overall infrastructure health (healthy/degraded/unhealthy)
    - services: Individual service health status
    - total_response_time_ms: Total health check time
    - healthy_count: Number of healthy services
    - degraded_count: Number of degraded services
    - unhealthy_count: Number of unhealthy services
    - checked_at: Timestamp of health check
    """
    from src.archon_services.health_monitor import get_health_monitor

    health_monitor = get_health_monitor()
    health_status = await health_monitor.check_all_services(use_cache=use_cache)

    logger.info(
        f"Infrastructure health check completed | overall_status={health_status.overall_status.value} | "
        f"healthy={health_status.healthy_count} degraded={health_status.degraded_count} "
        f"unhealthy={health_status.unhealthy_count} | "
        f"total_time={health_status.total_response_time_ms:.2f}ms"
    )

    return health_status


# ============================================================================
# New Dashboard Endpoints (7 endpoints)
# ============================================================================


@router.get(
    "/stats",
    response_model=PatternStatsResponse,
    summary="Get Overall Pattern Statistics",
    description="Get comprehensive pattern statistics including totals, averages, and breakdowns",
)
@api_error_handler("get_pattern_stats")
async def get_pattern_stats():
    """
    Get overall pattern statistics.

    Returns:
    - Total patterns count
    - Total feedback count
    - Average success rate
    - Average quality score
    - Patterns by type breakdown
    - Recent activity count (24h)
    - High confidence patterns count
    """
    result = await pattern_analytics_service.get_pattern_stats()
    logger.info(
        f"Pattern stats retrieved | total_patterns={result['stats']['total_patterns']}"
    )
    return PatternStatsResponse(**result)


@router.get(
    "/discovery-rate",
    response_model=DiscoveryRateResponse,
    summary="Get Pattern Discovery Rate",
    description="Get time-series data showing pattern discovery rate over time",
)
@api_error_handler("get_discovery_rate")
async def get_discovery_rate(
    time_range: str = Query("7d", description="Time range (1d, 7d, 30d, 90d)"),
    granularity: str = Query("day", description="Time granularity (hour, day, week)"),
):
    """
    Get pattern discovery rate over time.

    Query Parameters:
    - time_range: Time window for analysis
    - granularity: Data point granularity

    Returns time-series data points with counts and pattern type breakdowns.
    """
    result = await pattern_analytics_service.get_discovery_rate(
        time_range=time_range,
        granularity=granularity,
    )
    logger.info(
        f"Discovery rate computed | total_discovered={result['total_discovered']}"
    )
    return DiscoveryRateResponse(**result)


@router.get(
    "/quality-trends",
    response_model=QualityTrendsResponse,
    summary="Get Quality Trends",
    description="Get quality score trends over time with overall trend analysis",
)
@api_error_handler("get_quality_trends")
async def get_quality_trends(
    time_range: str = Query("30d", description="Time range (1d, 7d, 30d, 90d)"),
):
    """
    Get quality trends over time.

    Query Parameters:
    - time_range: Time window for analysis

    Returns:
    - Time-series quality data points
    - Overall trend direction
    - Trend velocity (rate of change)
    """
    result = await pattern_analytics_service.get_quality_trends(time_range=time_range)
    logger.info(f"Quality trends computed | overall_trend={result['overall_trend']}")
    return QualityTrendsResponse(**result)


@router.get(
    "/top-performing",
    response_model=TopPerformingResponse,
    summary="Get Top Performing Patterns",
    description="Get top performing patterns ranked by various criteria",
)
@api_error_handler("get_top_performing")
async def get_top_performing(
    criteria: str = Query(
        "performance_score",
        description="Ranking criteria (success_rate, usage, quality, performance_score)",
    ),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
):
    """
    Get top performing patterns.

    Query Parameters:
    - criteria: Ranking criteria
    - limit: Maximum patterns to return

    Returns ranked list of top patterns with performance metrics.
    """
    result = await pattern_analytics_service.get_top_performing_new(
        criteria=criteria,
        limit=limit,
    )
    logger.info(f"Top performing patterns retrieved | count={len(result['patterns'])}")
    return TopPerformingResponse(**result)


@router.get(
    "/relationships",
    response_model=PatternRelationshipsResponse,
    summary="Get Pattern Relationships",
    description="Get pattern relationship network data for visualization",
)
@api_error_handler("get_pattern_relationships")
async def get_pattern_relationships(
    min_co_occurrence: int = Query(2, ge=1, description="Minimum co-occurrence count"),
):
    """
    Get pattern relationship network data.

    Query Parameters:
    - min_co_occurrence: Minimum times patterns used together

    Returns:
    - Pattern nodes with centrality metrics
    - Pattern relationships/edges
    - Network statistics
    """
    result = await pattern_analytics_service.get_pattern_relationships(
        min_co_occurrence=min_co_occurrence,
    )
    logger.info(
        f"Pattern relationships computed | nodes={result['total_nodes']} | edges={result['total_edges']}"
    )
    return PatternRelationshipsResponse(**result)


@router.get(
    "/search",
    response_model=PatternSearchResponse,
    summary="Search Patterns",
    description="Search patterns using full-text or vector search",
)
@api_error_handler("search_patterns")
async def search_patterns(
    query: str = Query(..., description="Search query"),
    search_type: str = Query(
        "full_text", description="Search type (full_text, vector, hybrid)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    Search for patterns.

    Query Parameters:
    - query: Search query string
    - search_type: Type of search to perform
    - limit: Maximum results

    Returns ranked search results with relevance scores.
    """
    result = await pattern_analytics_service.search_patterns(
        query=query,
        search_type=search_type,
        limit=limit,
    )
    logger.info(
        f"Pattern search completed | query='{query}' | results={result['total_results']}"
    )
    return PatternSearchResponse(**result)


@router.get(
    "/infrastructure-health",
    response_model=InfrastructureHealthResponse,
    summary="Get Infrastructure Health",
    description="Get health status of pattern analytics infrastructure components",
)
@api_error_handler("get_infrastructure_health")
async def get_infrastructure_health():
    """
    Get infrastructure health status.

    Returns:
    - Overall health status
    - Component-level health details
    - Uptime and performance metrics
    """
    result = await pattern_analytics_service.get_infrastructure_health()
    logger.info(f"Infrastructure health checked | status={result['overall_status']}")
    return InfrastructureHealthResponse(**result)
