"""
Data Quality API Routes

FastAPI router for data quality monitoring, orphan tracking, and alerting.

Endpoints:
- GET /api/data-quality/orphan-count - Get current orphan count
- GET /api/data-quality/tree-health - Get tree health metrics
- GET /api/data-quality/metrics - Get historical metrics
- POST /api/data-quality/alert - Trigger manual alert
- GET /api/data-quality/health - Service health check
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from neo4j import GraphDatabase
from src.api.data_quality.models import (
    AlertRequest,
    AlertResponse,
    DataQualityMetrics,
    HealthCheckResponse,
    MetricsHistoryResponse,
    OrphanCountResponse,
    OrphanMetricDataPoint,
    TreeHealthResponse,
)
from src.constants.memgraph_labels import MemgraphLabels, MemgraphRelationships

logger = logging.getLogger(__name__)

# Configure router
router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])

# Constants
METRICS_FILE = (
    Path(__file__).parent.parent.parent.parent.parent / "logs" / "orphan_metrics.json"
)
ALERTS_FILE = (
    Path(__file__).parent.parent.parent.parent.parent / "logs" / "orphan_alerts.json"
)


def get_memgraph_driver():
    """Get Memgraph driver connection."""
    memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://memgraph:7687")
    return GraphDatabase.driver(memgraph_uri)


# ============================================================================
# Orphan Count Endpoint
# ============================================================================


@router.get("/orphan-count", response_model=OrphanCountResponse)
async def get_orphan_count():
    """
    Get current orphan count.

    Returns the number of FILE nodes that are not connected to a PROJECT node
    via CONTAINS relationships (i.e., orphaned files).

    Returns:
        OrphanCountResponse: Orphan count, total files, and percentage
    """
    try:
        driver = get_memgraph_driver()

        with driver.session() as session:
            # Get orphan count
            orphan_count = session.run(
                f"""
                MATCH (f:{MemgraphLabels.FILE})
                WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                OPTIONAL MATCH orphan_path = (f)<-[:{MemgraphRelationships.CONTAINS}*]-(:{MemgraphLabels.PROJECT})
                WITH f, orphan_path
                WHERE orphan_path IS NULL
                RETURN count(f) as count
                """
            ).single()["count"]

            # Get total files
            total_files = session.run(
                f"""
                MATCH (f:{MemgraphLabels.FILE})
                WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                RETURN count(f) as count
                """
            ).single()["count"]

        driver.close()

        orphan_percentage = (orphan_count / total_files * 100) if total_files > 0 else 0

        return OrphanCountResponse(
            orphan_count=orphan_count,
            total_files=total_files,
            orphan_percentage=round(orphan_percentage, 2),
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to get orphan count: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to query orphan count: {str(e)}"
        )


# ============================================================================
# Tree Health Endpoint
# ============================================================================


@router.get("/tree-health", response_model=TreeHealthResponse)
async def get_tree_health():
    """
    Get tree health metrics.

    Returns comprehensive metrics about the tree graph structure including
    PROJECT nodes, DIRECTORY nodes, CONTAINS relationships, and orphan count.

    Returns:
        TreeHealthResponse: Complete tree health metrics
    """
    try:
        driver = get_memgraph_driver()

        with driver.session() as session:
            # Get PROJECT node count
            project_count = session.run(
                f"MATCH (p:{MemgraphLabels.PROJECT}) RETURN count(p) as count"
            ).single()["count"]

            # Get DIRECTORY node count
            directory_count = session.run(
                f"MATCH (d:{MemgraphLabels.DIRECTORY}) RETURN count(d) as count"
            ).single()["count"]

            # Get CONTAINS relationship count
            contains_count = session.run(
                f"MATCH ()-[r:{MemgraphRelationships.CONTAINS}]->() RETURN count(r) as count"
            ).single()["count"]

            # Get orphan count
            orphan_count = session.run(
                f"""
                MATCH (f:{MemgraphLabels.FILE})
                WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                OPTIONAL MATCH orphan_path = (f)<-[:{MemgraphRelationships.CONTAINS}*]-(:{MemgraphLabels.PROJECT})
                WITH f, orphan_path
                WHERE orphan_path IS NULL
                RETURN count(f) as count
                """
            ).single()["count"]

            # Get total files
            total_files = session.run(
                f"""
                MATCH (f:{MemgraphLabels.FILE})
                WHERE f.entity_id STARTS WITH 'archon://' OR f.path CONTAINS '/'
                RETURN count(f) as count
                """
            ).single()["count"]

        driver.close()

        orphan_percentage = (orphan_count / total_files * 100) if total_files > 0 else 0

        # Determine health status
        if orphan_count == 0 and project_count > 0 and directory_count > 0:
            health_status = "healthy"
        elif orphan_percentage < 10:
            health_status = "degraded"
        else:
            health_status = "critical"

        return TreeHealthResponse(
            project_nodes=project_count,
            directory_nodes=directory_count,
            contains_relationships=contains_count,
            orphan_count=orphan_count,
            total_files=total_files,
            orphan_percentage=round(orphan_percentage, 2),
            health_status=health_status,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to get tree health: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to query tree health: {str(e)}"
        )


# ============================================================================
# Metrics History Endpoint
# ============================================================================


@router.get("/metrics", response_model=MetricsHistoryResponse)
async def get_metrics_history(hours: int = 24):
    """
    Get historical orphan metrics.

    Returns historical orphan count data for the specified time range.
    Includes calculated growth rates if sufficient data is available.

    Args:
        hours: Number of hours of history to return (default: 24)

    Returns:
        MetricsHistoryResponse: Historical metrics with growth rates
    """
    try:
        if not METRICS_FILE.exists():
            return MetricsHistoryResponse(
                total_entries=0,
                time_range_hours=None,
                metrics=[],
                growth_rate_per_hour=None,
                growth_rate_per_day=None,
            )

        with open(METRICS_FILE, "r") as f:
            data = json.load(f)
            all_metrics = data.get("metrics", [])

        # Filter to requested time range
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = []

        for metric in all_metrics:
            timestamp = datetime.fromisoformat(metric["timestamp"])
            if timestamp >= cutoff_time:
                recent_metrics.append(
                    OrphanMetricDataPoint(
                        timestamp=metric["timestamp"],
                        orphan_count=metric["orphan_count"],
                        orphan_percentage=metric["orphan_percentage"],
                    )
                )

        # Calculate growth rates
        growth_rate_hour = None
        growth_rate_day = None
        time_range_hours = None

        if len(recent_metrics) >= 2:
            first = recent_metrics[0]
            last = recent_metrics[-1]

            first_time = datetime.fromisoformat(first.timestamp)
            last_time = datetime.fromisoformat(last.timestamp)

            time_diff_hours = (last_time - first_time).total_seconds() / 3600
            time_range_hours = round(time_diff_hours, 2)

            if time_diff_hours > 0:
                orphan_diff = last.orphan_count - first.orphan_count
                growth_rate_hour = round(orphan_diff / time_diff_hours, 2)
                growth_rate_day = round(growth_rate_hour * 24, 2)

        return MetricsHistoryResponse(
            total_entries=len(recent_metrics),
            time_range_hours=time_range_hours,
            metrics=recent_metrics,
            growth_rate_per_hour=growth_rate_hour,
            growth_rate_per_day=growth_rate_day,
        )

    except Exception as e:
        logger.error(f"Failed to get metrics history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load metrics history: {str(e)}"
        )


# ============================================================================
# Manual Alert Endpoint
# ============================================================================


@router.post("/alert", response_model=AlertResponse)
async def trigger_alert(request: AlertRequest):
    """
    Trigger a manual alert.

    Sends an alert through the orphan alerting system. Useful for testing
    or manually notifying about data quality issues.

    Args:
        request: Alert configuration (severity, title, message, context)

    Returns:
        AlertResponse: Alert confirmation with ID and timestamp
    """
    try:
        # Ensure alerts directory exists
        ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing alerts
        if ALERTS_FILE.exists():
            with open(ALERTS_FILE, "r") as f:
                alert_data = json.load(f)
                alerts = alert_data.get("alerts", [])
        else:
            alerts = []

        # Create alert
        alert_id = f"manual_{datetime.utcnow().timestamp()}"
        timestamp = datetime.utcnow().isoformat()

        alert = {
            "alert_id": alert_id,
            "timestamp": timestamp,
            "severity": request.severity,
            "title": request.title,
            "message": request.message,
            "context": request.context or {},
        }

        # Add to history
        alerts.append(alert)

        # Keep only last 1000 alerts
        if len(alerts) > 1000:
            alerts = alerts[-1000:]

        # Save alerts
        with open(ALERTS_FILE, "w") as f:
            json.dump({"alerts": alerts}, f, indent=2)

        logger.info(
            f"Manual alert triggered: {request.title} (severity: {request.severity})"
        )

        return AlertResponse(
            alert_id=alert_id,
            timestamp=timestamp,
            severity=request.severity,
            title=request.title,
            message=request.message,
            sent=True,
        )

    except Exception as e:
        logger.error(f"Failed to trigger alert: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger alert: {str(e)}"
        )


# ============================================================================
# Health Check Endpoint
# ============================================================================


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Data quality service health check.

    Verifies that all components of the data quality monitoring system
    are functioning correctly.

    Returns:
        HealthCheckResponse: Health status and individual checks
    """
    checks = {}
    all_healthy = True

    # Check Memgraph connectivity
    try:
        driver = get_memgraph_driver()
        with driver.session() as session:
            session.run("RETURN 1").single()
        driver.close()
        checks["memgraph"] = True
    except Exception as e:
        logger.error(f"Memgraph health check failed: {e}")
        checks["memgraph"] = False
        all_healthy = False

    # Check metrics file accessibility
    try:
        checks["metrics_file"] = METRICS_FILE.exists()
        if not checks["metrics_file"]:
            all_healthy = False
    except Exception:
        checks["metrics_file"] = False
        all_healthy = False

    # Check alerts file directory
    try:
        checks["alerts_directory"] = ALERTS_FILE.parent.exists()
    except Exception:
        checks["alerts_directory"] = False

    # Determine overall status
    if all_healthy:
        status = "healthy"
        message = "All data quality checks passed"
    elif checks.get("memgraph", False):
        status = "degraded"
        message = "Data quality service operational but some features degraded"
    else:
        status = "unhealthy"
        message = "Critical data quality components unavailable"

    return HealthCheckResponse(
        status=status,
        timestamp=datetime.utcnow().isoformat(),
        checks=checks,
        message=message,
    )
