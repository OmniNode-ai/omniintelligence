"""
Intelligence Events API Routes

FastAPI router for real-time intelligence event streaming.
Provides endpoints for the Pattern Dashboard Event Flow page.
"""

import asyncio
import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from src.api.intelligence_events.models import EventsStreamResponse
from src.api.intelligence_events.service import IntelligenceEventsService

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/intelligence", tags=["intelligence-events"])

# Service and database pool management
_service: Optional[IntelligenceEventsService] = None
_db_pool = None
_db_pool_lock = asyncio.Lock()


async def get_db_pool():
    """
    Get database connection pool (shared with other services).

    Returns:
        Optional[asyncpg.Pool]: Database connection pool or None
    """
    global _db_pool

    if _db_pool is None:
        async with _db_pool_lock:
            if _db_pool is None:
                try:
                    import asyncpg

                    # Get database URL from environment
                    db_url = os.getenv("TRACEABILITY_DB_URL") or os.getenv(
                        "DATABASE_URL"
                    )

                    # If no database URL is configured, skip database connection
                    if not db_url or db_url.strip() == "":
                        logger.info(
                            "ℹ️  No database URL configured - Using mock data for events"
                        )
                        return None

                    logger.info(f"🔗 Connecting to database for intelligence events...")
                    _db_pool = await asyncpg.create_pool(
                        db_url,
                        min_size=2,
                        max_size=10,
                        command_timeout=10,
                    )
                    logger.info(f"✅ Database pool created for intelligence events")

                except ImportError:
                    logger.warning("asyncpg not available - Using mock data for events")
                    _db_pool = None
                except Exception as e:
                    logger.error(
                        f"❌ Failed to create database pool: {e} - Using mock data"
                    )
                    _db_pool = None

    return _db_pool


async def get_service() -> IntelligenceEventsService:
    """Get or create intelligence events service instance"""
    global _service

    if _service is None:
        db_pool = await get_db_pool()
        _service = IntelligenceEventsService(db_pool=db_pool)

    return _service


@router.get(
    "/events/stream",
    response_model=EventsStreamResponse,
    summary="Get Intelligence Events Stream",
    description=(
        "Get real-time stream of intelligence events from multiple sources. "
        "Aggregates agent actions, routing decisions, and errors into a unified timeline. "
        "Supports filtering by event type, agent name, correlation ID, and time window."
    ),
)
async def get_events_stream(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of events to return (1-1000)",
    ),
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type: agent_action, routing_decision, or error",
    ),
    agent_name: Optional[str] = Query(
        None,
        description="Filter by agent name (exact match)",
    ),
    correlation_id: Optional[UUID] = Query(
        None,
        description="Filter by correlation ID to trace related events",
    ),
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
        description="Time window in hours (1-168, default: 24)",
    ),
):
    """
    Get intelligence events stream with filtering.

    **Query Parameters:**
    - limit: Maximum number of events (1-1000, default: 100)
    - event_type: Filter by type (agent_action, routing_decision, error)
    - agent_name: Filter by agent name
    - correlation_id: Filter by correlation ID
    - hours: Time window in hours (1-168, default: 24h)

    **Response:**
    - events: List of events ordered by timestamp descending
    - total: Total number of events in response
    - time_range: Start and end time of events
    - event_counts: Count of events by type

    **Event Types:**
    - agent_action: Agent tool calls, decisions, success markers
    - routing_decision: Agent routing decisions with confidence scores
    - error: Error events from agent executions
    """
    try:
        service = await get_service()

        result = await service.get_events_stream(
            limit=limit,
            event_type=event_type,
            agent_name=agent_name,
            correlation_id=correlation_id,
            hours=hours,
        )

        logger.info(
            f"Events stream retrieved | total={result['total']} | "
            f"types={result['event_counts']}"
        )

        return EventsStreamResponse(**result)

    except Exception as e:
        logger.error(f"Error retrieving events stream: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve events stream: {str(e)}",
        )


@router.get(
    "/health",
    summary="Health Check",
    description="Check intelligence events API health and database connectivity",
)
async def health_check():
    """Health check endpoint"""
    db_pool = await get_db_pool()
    db_status = "connected" if db_pool else "not_configured"

    return {
        "status": "healthy",
        "service": "intelligence-events-api",
        "database": db_status,
    }


async def cleanup_db_pool():
    """Cleanup database pool on shutdown"""
    global _db_pool

    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Intelligence Events: Database pool closed")
