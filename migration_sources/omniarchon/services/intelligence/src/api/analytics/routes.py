"""
Analytics API Routes
FastAPI router for traceability and pattern learning analytics
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from src.api.analytics.mock_data import (
    _MOCK_AGENTS,
    _MOCK_CHAINS,
    _MOCK_ERRORS,
    generate_dashboard_summary,
    generate_endpoint_call,
    generate_hook_execution,
    get_mock_patterns,
    get_mock_traces,
)
from src.api.analytics.models import (
    AgentChainingResponse,
    AgentEffectivenessListResponse,
    DashboardSummaryResponse,
    ErrorAnalysisResponse,
    PatternListResponse,
    PatternUsageStats,
    TraceDetailResponse,
    TraceListResponse,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(
        default=None, description="completed, in_progress, failed"
    ),
    success: Optional[bool] = Query(default=None),
    session_id: Optional[UUID] = Query(default=None),
):
    """
    List execution traces with filtering

    Args:
        limit: Maximum number of traces to return
        offset: Pagination offset
        status: Filter by execution status
        success: Filter by success status
        session_id: Filter by session ID

    Returns:
        Paginated list of execution traces
    """
    traces = get_mock_traces(limit=limit, offset=offset, status=status, success=success)
    total = len(get_mock_traces(limit=1000))  # Mock total count

    return TraceListResponse(
        traces=traces,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(traces)) < total,
    )


@router.get("/traces/{correlation_id}", response_model=TraceDetailResponse)
async def get_trace_detail(correlation_id: UUID):
    """
    Get detailed information about a specific trace

    Args:
        correlation_id: Unique correlation ID for the trace

    Returns:
        Complete trace details with hooks, endpoints, and agent routing
    """
    # Mock: Find trace by correlation_id
    traces = get_mock_traces(limit=1000)
    trace = next((t for t in traces if t.correlation_id == correlation_id), None)

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Generate mock related data
    hooks = [generate_hook_execution(order=i + 1) for i in range(trace.hook_count)]
    endpoints = [generate_endpoint_call() for _ in range(trace.endpoint_count)]

    agent_routing = {
        "agent_selected": trace.agent_selected,
        "confidence_score": trace.routing_confidence,
        "routing_strategy": "pattern_replay",
        "pattern_id": None,
        "alternatives": [],
    }

    return TraceDetailResponse(
        trace=trace,
        agent_routing=agent_routing,
        hooks=hooks,
        endpoints=endpoints,
    )


@router.get("/patterns", response_model=PatternListResponse)
async def list_patterns(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_success_rate: Optional[float] = Query(default=None, ge=0, le=1),
    min_usage_count: Optional[int] = Query(default=None, ge=1),
    domain: Optional[str] = Query(default=None),
):
    """
    List learned success patterns

    Args:
        limit: Maximum number of patterns to return
        offset: Pagination offset
        min_success_rate: Minimum success rate (0.0-1.0)
        min_usage_count: Minimum usage count
        domain: Filter by domain

    Returns:
        Paginated list of success patterns
    """
    patterns = get_mock_patterns(
        limit=limit,
        offset=offset,
        min_success_rate=min_success_rate,
        min_usage_count=min_usage_count,
    )
    total = len(get_mock_patterns(limit=1000))

    return PatternListResponse(
        patterns=patterns,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(patterns)) < total,
    )


@router.get("/patterns/{pattern_id}/usage", response_model=PatternUsageStats)
async def get_pattern_usage(pattern_id: UUID):
    """
    Get usage statistics for a specific pattern

    Args:
        pattern_id: UUID of the pattern

    Returns:
        Pattern usage statistics and trends
    """
    # Mock pattern usage stats
    import random
    from datetime import datetime, timedelta, timezone

    # Generate usage over time (last 30 days)
    usage_over_time = []
    for i in range(30, 0, -1):
        date = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        usage_over_time.append(
            {
                "date": date,
                "count": random.randint(1, 10),
                "success_rate": round(random.uniform(0.7, 0.95), 2),
            }
        )

    return PatternUsageStats(
        pattern_id=pattern_id,
        usage_over_time=usage_over_time,
        total_usage=sum(u["count"] for u in usage_over_time),
        success_rate=round(
            sum(u["success_rate"] for u in usage_over_time) / len(usage_over_time), 4
        ),
        avg_duration_ms=random.randint(1500, 3500),
        recent_trend="increasing" if random.random() > 0.5 else "stable",
    )


@router.get("/agents/effectiveness", response_model=AgentEffectivenessListResponse)
async def get_agent_effectiveness():
    """
    Get effectiveness metrics for all agents

    Returns:
        List of agent effectiveness metrics
    """
    return AgentEffectivenessListResponse(
        agents=_MOCK_AGENTS,
        total_agents=len(_MOCK_AGENTS),
    )


@router.get("/agents/chaining", response_model=AgentChainingResponse)
async def get_agent_chaining_patterns():
    """
    Get common agent chaining patterns

    Returns:
        List of agent chaining patterns with success rates
    """
    # Sort by occurrence count
    sorted_chains = sorted(_MOCK_CHAINS, key=lambda x: x.occurrence_count, reverse=True)

    return AgentChainingResponse(
        patterns=sorted_chains,
        total_patterns=len(sorted_chains),
    )


@router.get("/errors", response_model=ErrorAnalysisResponse)
async def get_error_analysis(
    time_range: Optional[str] = Query(default="24h", description="24h, 7d, 30d"),
    error_type: Optional[str] = Query(default=None),
):
    """
    Get error analysis and patterns

    Args:
        time_range: Time range for analysis (24h, 7d, 30d)
        error_type: Filter by specific error type

    Returns:
        Error patterns with occurrence trends
    """
    errors = _MOCK_ERRORS

    if error_type:
        errors = [e for e in errors if e.error_type == error_type]

    # Calculate recent errors based on time_range
    recent_errors = sum(e.occurrences_24h for e in errors)

    return ErrorAnalysisResponse(
        errors=errors,
        total_error_types=len(set(e.error_type for e in errors)),
        recent_errors_24h=recent_errors,
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary():
    """
    Get high-level dashboard summary metrics

    Returns:
        Dashboard summary with key metrics
    """
    return generate_dashboard_summary()


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "analytics-api",
        "mode": "mock_data",  # Will change to "database" after integration
    }
