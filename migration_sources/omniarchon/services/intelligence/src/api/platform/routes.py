"""
Platform Health API Routes

FastAPI router for platform-wide health monitoring endpoints.
"""

import logging

from fastapi import APIRouter, Query
from src.api.platform.models import PlatformHealthResponse
from src.api.platform.service import PlatformHealthService
from src.api.utils import api_error_handler

logger = logging.getLogger(__name__)

# Initialize router with /api/intelligence/platform prefix
router = APIRouter(prefix="/api/intelligence/platform", tags=["Platform Health"])

# Initialize service
platform_health_service = PlatformHealthService()


@router.get(
    "/health",
    response_model=PlatformHealthResponse,
    summary="Get Platform Health Status",
    description=(
        "Get comprehensive platform health status including database, Kafka, and all services. "
        "Returns system-wide health metrics with individual component status."
    ),
)
@api_error_handler("get_platform_health")
async def get_platform_health(
    use_cache: bool = Query(
        True,
        description="Use cached health results if available (30s TTL)",
    )
):
    """
    Get comprehensive platform health status.

    Monitors:
    - **Database**: PostgreSQL connection, query latency, table count
    - **Kafka**: Message broker status, broker/topic counts
    - **Services**: All Omniarchon services (archon-intelligence, archon-qdrant, etc.)

    Returns overall platform status with detailed component breakdowns.

    **Query Parameters:**
    - use_cache: Use cached results if available (default: True)

    **Response:**
    - overall_status: Overall platform health (healthy/degraded/unhealthy)
    - database: Database health with latency and details
    - kafka: Kafka health with lag and details
    - services: Individual service health status with uptime
    - total_response_time_ms: Total health check duration
    - healthy_count: Number of healthy services
    - degraded_count: Number of degraded services
    - unhealthy_count: Number of unhealthy services
    - checked_at: Health check timestamp
    """
    result = await platform_health_service.get_platform_health(use_cache=use_cache)

    logger.info(
        f"Platform health retrieved | overall_status={result.overall_status} | "
        f"healthy={result.healthy_count} degraded={result.degraded_count} "
        f"unhealthy={result.unhealthy_count} | "
        f"total_time={result.total_response_time_ms:.2f}ms"
    )

    return result
