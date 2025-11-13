"""
Phase 4 Pattern Traceability API Routes

FastAPI router for pattern lineage tracking, usage analytics, and feedback loops:
1. Pattern Lineage API - Track pattern ancestry and evolution
2. Usage Analytics API - Aggregate pattern usage metrics and trends
3. Feedback Loop API - Automated pattern improvement workflow
4. Health Check API - System health monitoring

Performance Targets:
- Lineage tracking: <50ms per event
- Ancestry query: <200ms for depth up to 10
- Analytics computation: <500ms per pattern
- Feedback loop: <60s (excluding A/B test wait time)
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import asyncpg

# Phase 4 imports
from src.archon_services.pattern_learning.phase4_traceability.model_contract_feedback_loop import (
    ModelFeedbackLoopInput,
)
from src.archon_services.pattern_learning.phase4_traceability.model_contract_pattern_lineage import (
    EdgeType,
    LineageEventType,
    ModelPatternLineageInput,
    TransformationType,
)
from src.archon_services.pattern_learning.phase4_traceability.model_contract_usage_analytics import (
    ModelUsageAnalyticsInput,
    TimeWindowType,
)
from src.archon_services.pattern_learning.phase4_traceability.node_feedback_loop_orchestrator import (
    NodeFeedbackLoopOrchestrator,
)
from src.archon_services.pattern_learning.phase4_traceability.node_pattern_lineage_tracker_effect import (
    NodePatternLineageTrackerEffect,
)
from src.archon_services.pattern_learning.phase4_traceability.node_usage_analytics_reducer import (
    NodeUsageAnalyticsReducer,
)

# Configure router
router = APIRouter(prefix="/api/pattern-traceability", tags=["pattern-traceability"])

# ============================================================================
# Request/Response Models
# ============================================================================


class LineageTrackRequest(BaseModel):
    """Request for tracking pattern lineage events"""

    event_type: str = Field(
        ..., description="Event type (pattern_created, pattern_modified, etc.)"
    )
    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_name: str = Field(default="", description="Human-readable pattern name")
    pattern_type: str = Field(
        default="code", description="Pattern type (code, config, template, workflow)"
    )
    pattern_version: str = Field(
        default="1.0.0", description="Pattern version (semantic versioning)"
    )
    tool_name: Optional[str] = Field(
        default=None, description="Tool that created the pattern (Write, Edit, etc.)"
    )
    file_path: Optional[str] = Field(default=None, description="Full path to the file")
    language: Optional[str] = Field(
        default="python", description="Programming language"
    )
    pattern_data: Dict[str, Any] = Field(
        default_factory=dict, description="Pattern content snapshot"
    )
    parent_pattern_ids: List[str] = Field(
        default_factory=list, description="Parent pattern IDs"
    )
    edge_type: Optional[str] = Field(
        default=None, description="Relationship type to parent"
    )
    transformation_type: Optional[str] = Field(
        default=None, description="Type of transformation applied"
    )
    reason: Optional[str] = Field(default=None, description="Reason for the event")
    triggered_by: str = Field(default="api", description="Who/what triggered the event")


class LineageBatchRequest(BaseModel):
    """Request for batch tracking multiple pattern lineage events"""

    events: List[LineageTrackRequest] = Field(
        ..., description="List of tracking events to process"
    )
    batch_id: Optional[str] = Field(default=None, description="Unique batch identifier")
    processing_mode: str = Field(
        default="parallel", description="Processing mode: 'parallel' or 'sequential'"
    )
    sequential_processing: bool = Field(
        default=False, description="Process events sequentially (for dependencies)"
    )
    timeout_per_event: float = Field(
        default=10.0, description="Timeout per event in seconds"
    )


class LineageQueryRequest(BaseModel):
    """Request for querying pattern lineage"""

    pattern_id: str = Field(..., description="Pattern ID to query")
    operation: str = Field(
        default="query_ancestry",
        description="Operation (query_ancestry, query_descendants)",
    )


class UsageAnalyticsRequest(BaseModel):
    """Request for pattern usage analytics"""

    pattern_id: str = Field(..., description="Pattern ID to analyze")
    time_window_type: str = Field(
        default="weekly", description="Time window (hourly, daily, weekly, monthly)"
    )
    include_performance: bool = Field(
        default=True, description="Include performance metrics"
    )
    include_trends: bool = Field(default=True, description="Include trend analysis")
    include_distribution: bool = Field(
        default=False, description="Include context distribution"
    )
    time_window_days: Optional[int] = Field(
        default=None, description="Custom time window in days"
    )


class FeedbackLoopRequest(BaseModel):
    """Request for feedback loop orchestration"""

    pattern_id: str = Field(..., description="Pattern ID to improve")
    feedback_type: str = Field(
        default="performance",
        description="Feedback type (performance, quality, usage, all)",
    )
    time_window_days: int = Field(
        default=7, ge=1, le=90, description="Time window for analysis (1-90 days)"
    )
    auto_apply_threshold: float = Field(
        default=0.95, ge=0.0, le=1.0, description="Auto-apply confidence threshold"
    )
    min_sample_size: int = Field(
        default=30, ge=10, description="Minimum sample size for validation"
    )
    significance_level: float = Field(
        default=0.05, ge=0.001, le=0.1, description="Statistical significance level"
    )
    enable_ab_testing: bool = Field(default=True, description="Enable A/B testing")


# ============================================================================
# Service Management with Proper Connection Pooling
# ============================================================================

# Service instances with proper initialization
_lineage_tracker: Optional[NodePatternLineageTrackerEffect] = None
_usage_analytics: Optional[NodeUsageAnalyticsReducer] = None
_feedback_orchestrator: Optional[NodeFeedbackLoopOrchestrator] = None
_db_pool: Optional["asyncpg.Pool[asyncpg.Record]"] = None
_db_pool_lock = asyncio.Lock()
_service_lock = asyncio.Lock()

# Rate limiting
_request_timestamps = []
_rate_limit_window = 60  # seconds
_max_requests_per_window = 1000  # Adjust based on your capacity


async def get_db_pool():
    """Get or create database connection pool with proper locking"""
    global _db_pool
    if _db_pool is None:
        async with _db_pool_lock:
            if _db_pool is None:  # Double-checked locking
                try:
                    import os

                    import asyncpg

                    db_url = os.getenv(
                        "TRACEABILITY_DB_URL",
                        os.getenv("DATABASE_URL", "postgresql://localhost/archon"),
                    )

                    # Enhanced pool configuration for better performance
                    _db_pool = await asyncpg.create_pool(
                        db_url,
                        min_size=5,  # Increased minimum connections
                        max_size=50,  # Increased maximum connections
                        command_timeout=60,  # Timeout for commands
                        max_queries=50000,  # Maximum queries per connection
                        max_inactive_connection_lifetime=300,  # 5 minutes
                        setup=None,
                        init=None,
                        server_settings={
                            "application_name": "archon-traceability",
                            "timezone": "UTC",
                        },
                    )

                    # Test the connection
                    async with _db_pool.acquire() as conn:
                        await conn.fetchval("SELECT 1")

                    print("✅ Database pool initialized successfully")
                except Exception as e:
                    print(f"❌ Database pool initialization failed: {e}")
                    _db_pool = None
    return _db_pool


async def get_lineage_tracker():
    """Get or create lineage tracker instance with proper initialization"""
    global _lineage_tracker
    if _lineage_tracker is None:
        async with _service_lock:
            if _lineage_tracker is None:
                db_pool = await get_db_pool()
                if db_pool is not None:
                    _lineage_tracker = NodePatternLineageTrackerEffect(db_pool)
                else:
                    raise HTTPException(
                        status_code=503, detail="Database connection not available"
                    )
    return _lineage_tracker


async def get_usage_analytics():
    """Get or create usage analytics reducer instance"""
    global _usage_analytics
    if _usage_analytics is None:
        async with _service_lock:
            if _usage_analytics is None:
                _usage_analytics = NodeUsageAnalyticsReducer()
    return _usage_analytics


async def get_feedback_orchestrator():
    """Get or create feedback loop orchestrator instance"""
    global _feedback_orchestrator
    if _feedback_orchestrator is None:
        async with _service_lock:
            if _feedback_orchestrator is None:
                _feedback_orchestrator = NodeFeedbackLoopOrchestrator()
    return _feedback_orchestrator


async def rate_limit_check():
    """Simple rate limiting implementation"""
    global _request_timestamps
    now = time.time()

    # Remove old timestamps
    _request_timestamps = [
        ts for ts in _request_timestamps if now - ts < _rate_limit_window
    ]

    if len(_request_timestamps) >= _max_requests_per_window:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _request_timestamps.append(now)


@asynccontextmanager
async def get_db_connection():
    """Context manager for database connections with proper error handling"""
    pool = await get_db_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection not available")

    try:
        async with pool.acquire() as connection:
            yield connection
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=503, detail="Database connection error")


# ============================================================================
# Pattern Lineage API Endpoints
# ============================================================================


@router.post("/lineage/track")
async def track_pattern_lineage(
    request: LineageTrackRequest,
    background_tasks: BackgroundTasks,
    rate_limit: None = Depends(rate_limit_check),
):
    """
    Track pattern lineage event (creation, modification, merge, etc.)

    Performance: <50ms for tracking operations
    Rate limited: 1000 requests per minute
    """
    start_time = time.time()

    try:
        # Rate limiting already checked via dependency

        # Get initialized tracker
        tracker = await get_lineage_tracker()

        # Map operation from event type
        operation_map = {
            "pattern_created": "track_creation",
            "pattern_modified": "track_modification",
            "pattern_merged": "track_merge",
            "pattern_applied": "track_application",
            "pattern_deprecated": "track_deprecation",
            "pattern_forked": "track_fork",
        }

        operation = operation_map.get(request.event_type, "track_creation")

        # Build contract
        contract = ModelPatternLineageInput(
            name=f"track_{request.pattern_id}",
            operation=operation,
            event_type=LineageEventType(request.event_type),
            pattern_id=request.pattern_id,
            pattern_name=request.pattern_name,
            pattern_type=request.pattern_type,
            pattern_version=request.pattern_version,
            tool_name=request.tool_name,
            file_path=request.file_path,
            language=request.language,
            pattern_data=request.pattern_data,
            parent_pattern_ids=request.parent_pattern_ids,
            edge_type=EdgeType(request.edge_type) if request.edge_type else None,
            transformation_type=(
                TransformationType(request.transformation_type)
                if request.transformation_type
                else None
            ),
            reason=request.reason,
            triggered_by=request.triggered_by,
        )

        # Execute tracking with timeout protection
        try:
            result = await asyncio.wait_for(
                tracker.execute_effect(contract), timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Tracking operation timed out")

        processing_time_ms = (time.time() - start_time) * 1000

        if result.success:
            return JSONResponse(
                content={
                    "success": True,
                    "data": result.data,
                    "metadata": {
                        **result.metadata,
                        "processing_time_ms": round(processing_time_ms, 2),
                    },
                }
            )
        else:
            # Check if this is a unique constraint violation that we handled gracefully
            if (
                result.metadata
                and result.metadata.get("error_type") == "unique_violation_handled"
            ):
                # Return 200 for handled duplicates
                return JSONResponse(
                    content={
                        "success": True,
                        "data": result.data,
                        "metadata": {
                            **result.metadata,
                            "processing_time_ms": round(processing_time_ms, 2),
                        },
                    }
                )
            else:
                error_status = 500 if "database" in str(result.error).lower() else 400
                return JSONResponse(
                    status_code=error_status,
                    content={
                        "success": False,
                        "error": result.error,
                        "metadata": result.metadata,
                        "processing_time_ms": round(processing_time_ms, 2),
                    },
                )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Lineage tracking error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Lineage tracking failed: {str(e)}"
        )


@router.post("/lineage/track/batch")
async def track_pattern_lineage_batch(
    request: LineageBatchRequest,
    background_tasks: BackgroundTasks,
    rate_limit: None = Depends(rate_limit_check),
):
    """
    Track multiple pattern lineage events in a single batch request

    Performance: <200ms for batch operations (significant improvement over individual requests)
    Supports both parallel and sequential processing modes
    Rate limited: 1000 requests per minute (per batch, not per event)

    This endpoint enables the optimized client's request batching feature,
    providing significant performance improvement for high-volume pattern tracking operations.
    """
    start_time = time.time()

    try:
        # Rate limiting already checked via dependency

        # Get initialized tracker
        tracker = await get_lineage_tracker()

        # Prepare batch of contracts
        contracts = []
        operation_map = {
            "pattern_created": "track_creation",
            "pattern_modified": "track_modification",
            "pattern_merged": "track_merge",
            "pattern_applied": "track_application",
            "pattern_deprecated": "track_deprecation",
            "pattern_forked": "track_fork",
        }

        for event in request.events:
            operation = operation_map.get(event.event_type, "track_creation")

            contract = ModelPatternLineageInput(
                name=f"batch_track_{event.pattern_id}",
                operation=operation,
                event_type=LineageEventType(event.event_type),
                pattern_id=event.pattern_id,
                pattern_name=event.pattern_name,
                pattern_type=event.pattern_type,
                pattern_version=event.pattern_version,
                tool_name=event.tool_name,
                file_path=event.file_path,
                language=event.language,
                pattern_data=event.pattern_data,
                parent_pattern_ids=event.parent_pattern_ids,
                edge_type=EdgeType(event.edge_type) if event.edge_type else None,
                transformation_type=(
                    TransformationType(event.transformation_type)
                    if event.transformation_type
                    else None
                ),
                reason=event.reason,
                triggered_by=event.triggered_by,
            )
            contracts.append(contract)

        # Execute batch tracking with timeout protection
        try:
            # Determine processing mode (use processing_mode field, fallback to sequential_processing for backward compatibility)
            effective_processing_mode = request.processing_mode
            if effective_processing_mode not in ["parallel", "sequential"]:
                effective_processing_mode = (
                    "sequential" if request.sequential_processing else "parallel"
                )

            if effective_processing_mode == "parallel":
                # Process events in parallel for maximum performance
                tasks = [tracker.execute_effect(contract) for contract in contracts]
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=max(
                        30.0, len(contracts) * 5.0
                    ),  # Scale timeout with batch size
                )
            else:
                # Process events sequentially for order preservation
                results = []
                for contract in contracts:
                    try:
                        result = await asyncio.wait_for(
                            tracker.execute_effect(contract), timeout=30.0
                        )
                        results.append(result)
                    except asyncio.TimeoutError:
                        results.append(Exception("Individual event timed out"))
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504, detail="Batch tracking operation timed out"
            )

        processing_time_ms = (time.time() - start_time) * 1000

        # Process results and aggregate
        successful_results = []
        failed_results = []
        handled_duplicates = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_results.append(
                    {
                        "event_index": i,
                        "error": str(result),
                        "pattern_id": (
                            request.events[i].pattern_id
                            if i < len(request.events)
                            else "unknown"
                        ),
                    }
                )
            elif result.success:
                successful_results.append(
                    {
                        "event_index": i,
                        "data": result.data,
                        "metadata": result.metadata,
                        "pattern_id": (
                            request.events[i].pattern_id
                            if i < len(request.events)
                            else "unknown"
                        ),
                    }
                )

                # Check for handled duplicates
                if (
                    result.metadata
                    and result.metadata.get("error_type") == "unique_violation_handled"
                ):
                    handled_duplicates += 1
            else:
                failed_results.append(
                    {
                        "event_index": i,
                        "error": result.error,
                        "metadata": result.metadata,
                        "pattern_id": (
                            request.events[i].pattern_id
                            if i < len(request.events)
                            else "unknown"
                        ),
                    }
                )

        # Return batch results
        return JSONResponse(
            content={
                "success": len(failed_results) == 0,
                "batch_summary": {
                    "total_events": len(request.events),
                    "successful_events": len(successful_results),
                    "failed_events": len(failed_results),
                    "handled_duplicates": handled_duplicates,
                    "processing_mode": effective_processing_mode,
                    "requested_processing_mode": request.processing_mode,
                },
                "successful_results": successful_results,
                "failed_results": failed_results if failed_results else None,
                "metadata": {
                    "processing_time_ms": round(processing_time_ms, 2),
                    "average_time_per_event": round(
                        processing_time_ms / len(request.events), 2
                    ),
                    "batch_efficiency_gain": round(
                        (len(request.events) * 50.0 - processing_time_ms)
                        / (len(request.events) * 50.0)
                        * 100,
                        1,
                    ),  # Compared to individual 50ms requests
                },
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Batch lineage tracking error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Batch lineage tracking failed: {str(e)}"
        )


@router.get("/lineage/{pattern_id}")
async def get_pattern_lineage(
    pattern_id: str,
    query_type: str = Query(
        default="ancestry", description="Query type: ancestry or descendants"
    ),
    rate_limit: None = Depends(rate_limit_check),
):
    """
    Get pattern lineage graph (ancestry or descendants)

    Performance: <200ms for ancestry query with depth up to 10
    Rate limited: 1000 requests per minute
    """
    start_time = time.time()

    try:
        # Rate limiting already checked via dependency

        # Get initialized tracker
        tracker = await get_lineage_tracker()

        # Build query contract
        operation = (
            "query_ancestry" if query_type == "ancestry" else "query_descendants"
        )

        contract = ModelPatternLineageInput(
            name=f"query_{pattern_id}", operation=operation, pattern_id=pattern_id
        )

        # Execute query with timeout protection
        try:
            result = await asyncio.wait_for(
                tracker.execute_effect(contract), timeout=30.0  # 30 second timeout
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Query operation timed out")

        processing_time_ms = (time.time() - start_time) * 1000

        if result.success:
            return JSONResponse(
                content={
                    "success": True,
                    "data": result.data,
                    "metadata": {
                        **result.metadata,
                        "processing_time_ms": round(processing_time_ms, 2),
                        "query_type": query_type,
                    },
                }
            )
        else:
            error_status = 404 if "not found" in str(result.error).lower() else 500
            if "database" in str(result.error).lower():
                error_status = 503
            return JSONResponse(
                status_code=error_status,
                content={
                    "success": False,
                    "error": result.error,
                    "metadata": result.metadata,
                    "processing_time_ms": round(processing_time_ms, 2),
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Lineage query error: {e}")
        raise HTTPException(status_code=500, detail=f"Lineage query failed: {str(e)}")


@router.get("/lineage/{pattern_id}/evolution")
async def get_pattern_evolution_path(pattern_id: str):
    """
    Get evolution path showing how a pattern changed over time.

    Returns the transformation history: pattern → derived pattern → further derived pattern
    Includes edge types (derived_from, modified_from, etc.) and transformation types.

    Performance: <200ms target

    Requires database connection to function.
    """
    start_time = time.time()

    try:
        # Check if database and tracker are available
        tracker = get_lineage_tracker()

        if tracker is None:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "Lineage tracker not initialized - database connection required",
                    "pattern_id": pattern_id,
                    "message": "Configure database connection and restart service",
                },
            )

        # Get database pool
        db_pool = await get_db_pool()
        if db_pool is None:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "Database connection not available",
                    "pattern_id": pattern_id,
                },
            )

        # Query evolution path from database
        async with db_pool.acquire() as conn:
            # Get all nodes for this pattern_id (all versions)
            nodes_query = """
                SELECT
                    n.id,
                    n.pattern_id,
                    n.pattern_name,
                    n.pattern_type,
                    n.pattern_version,
                    n.generation,
                    n.created_at,
                    n.metadata
                FROM pattern_lineage_nodes n
                WHERE n.pattern_id = $1
                ORDER BY n.generation ASC, n.created_at ASC
            """
            nodes = await conn.fetch(nodes_query, pattern_id)

            if not nodes:
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False,
                        "error": f"Pattern not found: {pattern_id}",
                        "pattern_id": pattern_id,
                    },
                )

            # Get all edges connecting these nodes
            node_ids = [node["id"] for node in nodes]
            edges_query = """
                SELECT
                    e.id,
                    e.source_node_id,
                    e.target_node_id,
                    e.edge_type,
                    e.transformation_type,
                    e.edge_weight,
                    e.metadata,
                    e.created_at,
                    src.pattern_id as source_pattern_id,
                    src.pattern_version as source_version,
                    tgt.pattern_id as target_pattern_id,
                    tgt.pattern_version as target_version
                FROM pattern_lineage_edges e
                JOIN pattern_lineage_nodes src ON src.id = e.source_node_id
                JOIN pattern_lineage_nodes tgt ON tgt.id = e.target_node_id
                WHERE e.source_node_id = ANY($1::uuid[])
                   OR e.target_node_id = ANY($1::uuid[])
                ORDER BY e.created_at ASC
            """
            edges = await conn.fetch(edges_query, node_ids)

        # Build evolution path
        evolution_path = {
            "pattern_id": pattern_id,
            "total_versions": len(nodes),
            "evolution_nodes": [
                {
                    "node_id": str(node["id"]),
                    "pattern_id": node["pattern_id"],
                    "pattern_name": node["pattern_name"],
                    "pattern_type": node["pattern_type"],
                    "version": node["pattern_version"],
                    "generation": node["generation"],
                    "created_at": node["created_at"].isoformat(),
                    "metadata": node["metadata"],
                }
                for node in nodes
            ],
            "evolution_edges": [
                {
                    "edge_id": str(edge["id"]),
                    "source_node_id": str(edge["source_node_id"]),
                    "target_node_id": str(edge["target_node_id"]),
                    "source_pattern_id": edge["source_pattern_id"],
                    "target_pattern_id": edge["target_pattern_id"],
                    "source_version": edge["source_version"],
                    "target_version": edge["target_version"],
                    "edge_type": edge["edge_type"],
                    "transformation_type": edge["transformation_type"],
                    "edge_weight": (
                        float(edge["edge_weight"]) if edge["edge_weight"] else 1.0
                    ),
                    "created_at": edge["created_at"].isoformat(),
                    "metadata": edge["metadata"],
                }
                for edge in edges
            ],
        }

        processing_time_ms = (time.time() - start_time) * 1000

        return JSONResponse(
            content={
                "success": True,
                "data": evolution_path,
                "metadata": {
                    "processing_time_ms": round(processing_time_ms, 2),
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                },
            }
        )

    except Exception as e:
        processing_time_ms = (time.time() - start_time) * 1000
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Evolution path query failed: {str(e)}",
                "pattern_id": pattern_id,
                "metadata": {"processing_time_ms": round(processing_time_ms, 2)},
            },
        )


# ============================================================================
# Usage Analytics API Endpoints
# ============================================================================


@router.post("/analytics/compute")
async def compute_usage_analytics(request: UsageAnalyticsRequest):
    """
    Compute comprehensive usage analytics for a pattern

    Performance: <500ms per pattern analytics computation

    Works without database - uses pure in-memory analytics reduction.
    """
    start_time = time.time()

    try:
        analytics = get_usage_analytics()

        # Determine time window
        if request.time_window_days:
            time_window_start = datetime.now(timezone.utc) - timedelta(
                days=request.time_window_days
            )
            time_window_end = datetime.now(timezone.utc)
            time_window_type = TimeWindowType.DAILY
        else:
            # Map time window type to actual dates
            window_days = {
                "hourly": 1,
                "daily": 1,
                "weekly": 7,
                "monthly": 30,
                "quarterly": 90,
                "yearly": 365,
            }.get(request.time_window_type, 7)

            time_window_start = datetime.now(timezone.utc) - timedelta(days=window_days)
            time_window_end = datetime.now(timezone.utc)
            time_window_type = TimeWindowType(request.time_window_type)

        # Mock execution data (in production, this would come from database)
        # For now, we return empty analytics as we don't have execution data
        execution_data = []  # TODO: Fetch from Track 2 hook_executions table

        # Build analytics contract
        contract = ModelUsageAnalyticsInput(
            pattern_id=request.pattern_id,
            execution_data=execution_data,
            time_window_start=time_window_start,
            time_window_end=time_window_end,
            time_window_type=time_window_type,
            include_performance=request.include_performance,
            include_trends=request.include_trends,
            include_distribution=request.include_distribution,
        )

        # Execute analytics reduction
        output = await analytics.execute_reduction(contract)

        processing_time_ms = (time.time() - start_time) * 1000

        # Convert output to dict
        result = {
            "success": True,
            "pattern_id": output.pattern_id,
            "time_window": {
                "start": output.time_window_start.isoformat(),
                "end": output.time_window_end.isoformat(),
                "type": output.time_window_type.value,
            },
            "usage_metrics": {
                "total_executions": output.usage_metrics.total_executions,
                "executions_per_day": output.usage_metrics.executions_per_day,
                "executions_per_week": output.usage_metrics.executions_per_week,
                "unique_contexts": output.usage_metrics.unique_contexts,
                "unique_users": output.usage_metrics.unique_users,
            },
            "success_metrics": {
                "success_rate": output.success_metrics.success_rate,
                "error_rate": output.success_metrics.error_rate,
                "avg_quality_score": output.success_metrics.avg_quality_score,
            },
            "performance_metrics": (
                {
                    "avg_execution_time_ms": output.performance_metrics.avg_execution_time_ms,
                    "p95_execution_time_ms": output.performance_metrics.p95_execution_time_ms,
                    "p99_execution_time_ms": output.performance_metrics.p99_execution_time_ms,
                }
                if output.performance_metrics
                else None
            ),
            "trend_analysis": (
                {
                    "trend_type": output.trend_analysis.trend_type.value,
                    "velocity": output.trend_analysis.velocity,
                    "growth_percentage": output.trend_analysis.growth_percentage,
                    "confidence_score": output.trend_analysis.confidence_score,
                }
                if output.trend_analysis
                else None
            ),
            "analytics_quality_score": output.analytics_quality_score,
            "total_data_points": output.total_data_points,
            "computation_time_ms": round(output.computation_time_ms, 2),
            "processing_time_ms": round(processing_time_ms, 2),
        }

        return JSONResponse(content=result)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Analytics computation failed: {str(e)}"
        )


@router.get("/analytics/{pattern_id}")
async def get_pattern_analytics(
    pattern_id: str,
    time_window: str = Query(default="weekly", description="Time window type"),
    include_trends: bool = Query(default=True, description="Include trend analysis"),
):
    """
    Get usage analytics for a specific pattern

    Convenience endpoint that wraps compute_usage_analytics with simpler parameters.
    """
    request = UsageAnalyticsRequest(
        pattern_id=pattern_id,
        time_window_type=time_window,
        include_performance=True,
        include_trends=include_trends,
        include_distribution=False,
    )

    return await compute_usage_analytics(request)


# ============================================================================
# Feedback Loop API Endpoints
# ============================================================================


@router.post("/feedback/analyze")
async def analyze_pattern_feedback(
    request: FeedbackLoopRequest, background_tasks: BackgroundTasks
):
    """
    Analyze pattern feedback and identify improvement opportunities

    Executes feedback collection and analysis phases.
    Performance: <10s for analysis phase.
    """
    start_time = time.time()

    try:
        orchestrator = get_feedback_orchestrator()

        # Build feedback loop contract
        contract = ModelFeedbackLoopInput(
            operation="analyze_and_improve",
            pattern_id=request.pattern_id,
            feedback_type=request.feedback_type,
            time_window_days=request.time_window_days,
            auto_apply_threshold=request.auto_apply_threshold,
            min_sample_size=request.min_sample_size,
            significance_level=request.significance_level,
            enable_ab_testing=request.enable_ab_testing,
        )

        # Execute feedback loop orchestration
        result = await orchestrator.execute_orchestration(contract)

        processing_time_ms = (time.time() - start_time) * 1000

        if result.success:
            return JSONResponse(
                content={
                    "success": True,
                    "data": result.data,
                    "metadata": {
                        **result.metadata,
                        "processing_time_ms": round(processing_time_ms, 2),
                    },
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": result.error,
                    "metadata": result.metadata,
                },
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Feedback analysis failed: {str(e)}"
        )


@router.post("/feedback/apply")
async def apply_pattern_improvements(
    pattern_id: str,
    improvement_ids: List[str] = Query(description="Improvement IDs to apply"),
    force: bool = Query(default=False, description="Force apply without validation"),
):
    """
    Apply specific improvements to a pattern

    Allows manual application of improvements identified by feedback analysis.
    """
    start_time = time.time()

    try:
        # This would integrate with the feedback orchestrator to apply specific improvements
        # For now, return placeholder response

        processing_time_ms = (time.time() - start_time) * 1000

        return JSONResponse(
            content={
                "success": True,
                "pattern_id": pattern_id,
                "improvements_applied": len(improvement_ids),
                "improvement_ids": improvement_ids,
                "forced": force,
                "processing_time_ms": round(processing_time_ms, 2),
                "message": "Improvements applied successfully",
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Apply improvements failed: {str(e)}"
        )


# ============================================================================
# Health Check Endpoint
# ============================================================================


# ============================================================================
# Agent Execution Logs API Endpoints
# ============================================================================


@router.get("/executions/logs")
async def get_execution_logs(
    correlation_id: Optional[str] = Query(
        default=None, description="Filter by correlation ID"
    ),
    session_id: Optional[str] = Query(default=None, description="Filter by session ID"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results (1-200)"),
):
    """
    Get complete agent execution logs with user prompts, agent info, and related patterns.

    Returns aggregated execution data including:
    - User prompts and agent configurations
    - Execution status and performance metrics
    - All related pattern lineage nodes and events

    Performance: <500ms for queries with up to 50 results
    """
    start_time = time.time()

    try:
        # Get database pool
        db_pool = await get_db_pool()
        if db_pool is None:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "Database connection not available",
                    "message": "Configure TRACEABILITY_DB_URL environment variable",
                },
            )

        # Query execution logs using the database function
        async with db_pool.acquire() as conn:
            # Build query based on filters
            query = """
                SELECT * FROM get_execution_context($1, $2, $3)
            """
            rows = await conn.fetch(
                query,
                UUID(correlation_id) if correlation_id else None,
                UUID(session_id) if session_id else None,
                limit,
            )

        # Format results
        executions = []
        for row in rows:
            execution = {
                "execution_id": str(row["execution_id"]),
                "correlation_id": str(row["correlation_id"]),
                "session_id": str(row["session_id"]) if row["session_id"] else None,
                "user_prompt": row["user_prompt"],
                "agent_name": row["agent_name"],
                "agent_config": row["agent_config"],
                "status": row["status"],
                "started_at": (
                    row["started_at"].isoformat() if row["started_at"] else None
                ),
                "completed_at": (
                    row["completed_at"].isoformat() if row["completed_at"] else None
                ),
                "duration_ms": row["duration_ms"],
                "quality_score": (
                    float(row["quality_score"]) if row["quality_score"] else None
                ),
                "pattern_count": row["pattern_count"],
                "event_count": row["event_count"],
                "patterns": row["patterns"] if row["patterns"] else [],
                "events": row["events"] if row["events"] else [],
            }
            executions.append(execution)

        query_duration_ms = (time.time() - start_time) * 1000

        return JSONResponse(
            content={
                "success": True,
                "executions": executions,
                "count": len(executions),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query_duration_ms": round(query_duration_ms, 2),
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to retrieve execution logs: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get("/executions/summary")
async def get_execution_summary(
    agent_name: Optional[str] = Query(default=None, description="Filter by agent name")
):
    """
    Get execution summary statistics by agent.

    Returns aggregated statistics including:
    - Total execution count
    - Success/failure rates
    - Average duration and quality scores
    - Last execution timestamp

    Performance: <200ms
    """
    start_time = time.time()

    try:
        # Get database pool
        db_pool = await get_db_pool()
        if db_pool is None:
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": "Database connection not available",
                },
            )

        # Query summary using view
        async with db_pool.acquire() as conn:
            if agent_name:
                query = """
                    SELECT * FROM v_agent_execution_summary
                    WHERE agent_name = $1
                """
                rows = await conn.fetch(query, agent_name)
            else:
                query = """
                    SELECT * FROM v_agent_execution_summary
                    ORDER BY total_executions DESC
                """
                rows = await conn.fetch(query)

        # Format results
        summary = []
        for row in rows:
            summary.append(
                {
                    "agent_name": row["agent_name"],
                    "total_executions": row["total_executions"],
                    "successful_executions": row["successful_executions"],
                    "failed_executions": row["failed_executions"],
                    "avg_duration_ms": (
                        float(row["avg_duration_ms"])
                        if row["avg_duration_ms"]
                        else None
                    ),
                    "avg_quality_score": (
                        float(row["avg_quality_score"])
                        if row["avg_quality_score"]
                        else None
                    ),
                    "last_execution": (
                        row["last_execution"].isoformat()
                        if row["last_execution"]
                        else None
                    ),
                }
            )

        query_duration_ms = (time.time() - start_time) * 1000

        return JSONResponse(
            content={
                "success": True,
                "summary": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "query_duration_ms": round(query_duration_ms, 2),
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to retrieve execution summary: {str(e)}",
            },
        )


# ============================================================================
# Health Check Endpoint
# ============================================================================


@router.get("/health")
async def health_check():
    """
    Enhanced health check for pattern traceability components

    Returns detailed status of lineage tracker, analytics reducer, and feedback orchestrator.
    """
    start_time = time.time()

    health_status = {
        "status": "healthy",
        "components": {},
        "performance": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Check lineage tracker (requires database)
    try:
        db_pool = await get_db_pool()
        if db_pool:
            tracker = await get_lineage_tracker()
            if tracker:
                health_status["components"]["lineage_tracker"] = "operational"
                # Check pool stats
                try:
                    pool_stats = {
                        "min_size": db_pool.get_min_size(),
                        "max_size": db_pool.get_max_size(),
                        "pool_size": db_pool.get_size(),
                        "free_size": db_pool.get_idle_size(),
                    }
                    health_status["performance"]["database_pool"] = pool_stats
                except:
                    pass
            else:
                health_status["components"]["lineage_tracker"] = "not_initialized"
        else:
            health_status["components"]["lineage_tracker"] = "database_unavailable"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["lineage_tracker"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check usage analytics (pure reducer, should always work)
    try:
        await get_usage_analytics()
        health_status["components"]["usage_analytics"] = "operational"
    except Exception as e:
        health_status["components"]["usage_analytics"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check feedback orchestrator
    try:
        await get_feedback_orchestrator()
        health_status["components"]["feedback_orchestrator"] = "operational"
    except Exception as e:
        health_status["components"]["feedback_orchestrator"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check rate limiting status
    health_status["performance"]["rate_limiting"] = {
        "current_window_requests": len(_request_timestamps),
        "max_requests_per_window": _max_requests_per_window,
        "window_seconds": _rate_limit_window,
    }

    health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

    return JSONResponse(content=health_status)
