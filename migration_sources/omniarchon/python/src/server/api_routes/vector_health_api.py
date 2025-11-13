"""
Vector Collection Health Monitoring API

RESTful API endpoints for vector collection health monitoring, providing:
- Real-time collection balance tracking
- Performance threshold monitoring
- Vector routing accuracy metrics
- Collection health visualization data
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from server.services.vector_collection_health_monitor import (
    CollectionHealthStatus,
    VectorRoutingResult,
    get_vector_health_monitor,
    start_vector_monitoring,
    stop_vector_monitoring,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vector-health", tags=["Vector Health Monitoring"])


@router.get("/status")
async def get_vector_health_status():
    """
    Get overall vector collection health status.

    Returns:
        Dict with overall status, monitoring state, and active alerts count
    """
    try:
        monitor = get_vector_health_monitor()
        health_status = await monitor.get_health_status()
        return JSONResponse(
            content={
                "success": True,
                "data": health_status,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get vector health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_vector_health_dashboard():
    """
    Get comprehensive dashboard data for vector collection health visualization.

    Returns:
        Complete monitoring dashboard data including:
        - Collection metrics (size, performance, health)
        - Balance metrics between collections
        - Routing accuracy and performance
        - Active alerts and thresholds
    """
    try:
        monitor = get_vector_health_monitor()
        dashboard_data = monitor.get_dashboard_data()

        return JSONResponse(
            content={
                "success": True,
                "data": dashboard_data,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def get_collection_metrics(
    collection: Optional[str] = Query(None, description="Specific collection name"),
    hours: int = Query(1, description="Hours of history to return", ge=1, le=24),
):
    """
    Get collection-specific metrics and performance data.

    Args:
        collection: Optional specific collection name to filter by
        hours: Number of hours of historical data to return

    Returns:
        Collection metrics including size, performance, and health indicators
    """
    try:
        monitor = get_vector_health_monitor()

        # Filter metrics by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Get filtered metrics
        filtered_metrics = [
            {
                "timestamp": m.timestamp.isoformat(),
                "collection_name": m.collection_name,
                "total_vectors": m.total_vectors,
                "indexed_vectors": m.indexed_vectors,
                "avg_search_time_ms": m.avg_search_time_ms,
                "p95_search_time_ms": m.p95_search_time_ms,
                "memory_usage_mb": m.memory_usage_mb,
                "disk_usage_mb": m.disk_usage_mb,
                "health_status": m.health_status.value,
                "error_rate": m.error_rate,
                "availability_percentage": m.availability_percentage,
                "avg_quality_score": m.avg_quality_score,
                "min_quality_score": m.min_quality_score,
                "max_quality_score": m.max_quality_score,
            }
            for m in monitor.collection_metrics_history
            if m.timestamp >= cutoff_time
            and (not collection or m.collection_name == collection)
        ]

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "metrics": filtered_metrics,
                    "total_metrics": len(filtered_metrics),
                    "time_window_hours": hours,
                    "collection_filter": collection,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get collection metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance")
async def get_collection_balance_metrics(
    hours: int = Query(1, description="Hours of history to return", ge=1, le=24)
):
    """
    Get collection balance metrics between main and quality collections.

    Args:
        hours: Number of hours of historical data to return

    Returns:
        Balance metrics including size ratios, performance comparison, and balance health
    """
    try:
        monitor = get_vector_health_monitor()

        # Filter balance metrics by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        filtered_balance = [
            {
                "timestamp": b.timestamp.isoformat(),
                "main_collection_size": b.main_collection_size,
                "quality_collection_size": b.quality_collection_size,
                "size_balance_ratio": b.size_balance_ratio,
                "main_avg_search_time": b.main_avg_search_time,
                "quality_avg_search_time": b.quality_avg_search_time,
                "performance_ratio": b.performance_ratio,
                "balance_status": b.balance_status.value,
                "imbalance_severity": b.imbalance_severity,
            }
            for b in monitor.balance_metrics_history
            if b.timestamp >= cutoff_time
        ]

        # Calculate balance trends
        balance_trend = "stable"
        if len(filtered_balance) >= 2:
            recent_ratio = filtered_balance[-1]["size_balance_ratio"]
            older_ratio = filtered_balance[0]["size_balance_ratio"]
            ratio_change = abs(recent_ratio - older_ratio)

            if ratio_change > 0.1:
                balance_trend = "unstable"
            elif recent_ratio > older_ratio:
                balance_trend = "growing"
            elif recent_ratio < older_ratio:
                balance_trend = "shrinking"

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "balance_metrics": filtered_balance,
                    "balance_trend": balance_trend,
                    "total_records": len(filtered_balance),
                    "time_window_hours": hours,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get balance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routing")
async def get_routing_metrics(
    hours: int = Query(1, description="Hours of history to return", ge=1, le=24)
):
    """
    Get vector routing accuracy and performance metrics.

    Args:
        hours: Number of hours of historical data to return

    Returns:
        Routing metrics including accuracy, error rates, and performance data
    """
    try:
        monitor = get_vector_health_monitor()

        # Filter routing metrics by time window
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        filtered_routing = [
            {
                "timestamp": r.timestamp.isoformat(),
                "total_routing_decisions": r.total_routing_decisions,
                "main_collection_routes": r.main_collection_routes,
                "quality_collection_routes": r.quality_collection_routes,
                "routing_errors": r.routing_errors,
                "routing_accuracy_percentage": r.routing_accuracy_percentage,
                "routing_error_rate": r.routing_error_rate,
                "avg_routing_time_ms": r.avg_routing_time_ms,
                "routing_timeouts": r.routing_timeouts,
                "correctly_routed_high_quality": r.correctly_routed_high_quality,
                "correctly_routed_low_quality": r.correctly_routed_low_quality,
                "misrouted_documents": r.misrouted_documents,
            }
            for r in monitor.routing_metrics_history
            if r.timestamp >= cutoff_time
        ]

        # Calculate routing statistics
        total_decisions = sum(r["total_routing_decisions"] for r in filtered_routing)
        total_errors = sum(r["routing_errors"] for r in filtered_routing)
        avg_accuracy = (
            (
                sum(r["routing_accuracy_percentage"] for r in filtered_routing)
                / len(filtered_routing)
            )
            if filtered_routing
            else 0.0
        )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "routing_metrics": filtered_routing,
                    "summary": {
                        "total_decisions": total_decisions,
                        "total_errors": total_errors,
                        "average_accuracy": avg_accuracy,
                        "overall_error_rate": (
                            total_errors / total_decisions
                            if total_decisions > 0
                            else 0.0
                        ),
                    },
                    "total_records": len(filtered_routing),
                    "time_window_hours": hours,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get routing metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, description="Filter by alert severity"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
):
    """
    Get active vector collection health alerts.

    Args:
        severity: Optional severity filter (healthy, warning, critical, degraded)
        alert_type: Optional alert type filter (balance, performance, routing, health)

    Returns:
        List of active alerts with details and filtering information
    """
    try:
        monitor = get_vector_health_monitor()

        # Get all active alerts
        all_alerts = list(monitor.active_alerts.values())

        # Apply filters
        filtered_alerts = []
        for alert in all_alerts:
            if severity and alert.severity.value != severity.lower():
                continue
            if alert_type and alert.alert_type != alert_type.lower():
                continue

            filtered_alerts.append(
                {
                    "alert_id": alert.alert_id,
                    "timestamp": alert.timestamp.isoformat(),
                    "severity": alert.severity.value,
                    "collection": alert.collection,
                    "metric": alert.metric,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "message": alert.message,
                    "alert_type": alert.alert_type,
                    "age_minutes": (datetime.utcnow() - alert.timestamp).total_seconds()
                    / 60,
                }
            )

        # Sort by severity and timestamp
        severity_order = {"critical": 0, "warning": 1, "degraded": 2, "healthy": 3}
        filtered_alerts.sort(
            key=lambda a: (severity_order.get(a["severity"], 4), a["timestamp"]),
            reverse=True,
        )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "alerts": filtered_alerts,
                    "total_alerts": len(filtered_alerts),
                    "filters": {"severity": severity, "alert_type": alert_type},
                    "alert_counts": {
                        "critical": len(
                            [a for a in filtered_alerts if a["severity"] == "critical"]
                        ),
                        "warning": len(
                            [a for a in filtered_alerts if a["severity"] == "warning"]
                        ),
                        "degraded": len(
                            [a for a in filtered_alerts if a["severity"] == "degraded"]
                        ),
                    },
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/thresholds")
async def get_alert_thresholds():
    """
    Get current alert thresholds and monitoring configuration.

    Returns:
        Current alert thresholds and monitoring parameters
    """
    try:
        monitor = get_vector_health_monitor()

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "alert_thresholds": monitor.thresholds,
                    "monitoring_config": {
                        "main_collection": monitor.main_collection,
                        "quality_collection": monitor.quality_collection,
                        "monitoring_interval": monitor.monitoring_interval,
                        "qdrant_url": monitor.qdrant_url,
                    },
                    "health_status_values": [
                        status.value for status in CollectionHealthStatus
                    ],
                    "routing_result_values": [
                        result.value for result in VectorRoutingResult
                    ],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to get thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/start")
async def start_vector_health_monitoring():
    """
    Start vector collection health monitoring.

    Returns:
        Success status and monitoring information
    """
    try:
        await start_vector_monitoring()

        return JSONResponse(
            content={
                "success": True,
                "message": "Vector collection health monitoring started",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to start vector monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/stop")
async def stop_vector_health_monitoring():
    """
    Stop vector collection health monitoring.

    Returns:
        Success status and shutdown information
    """
    try:
        await stop_vector_monitoring()

        return JSONResponse(
            content={
                "success": True,
                "message": "Vector collection health monitoring stopped",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to stop vector monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/routing/record")
async def record_routing_decision(
    decision: str,
    routing_time_ms: float,
    document_type: Optional[str] = None,
    quality_score: Optional[float] = None,
):
    """
    Record a vector routing decision for metrics tracking.

    Args:
        decision: Routing decision (main, quality, error)
        routing_time_ms: Time taken for routing decision
        document_type: Optional document type for analysis
        quality_score: Optional quality score for validation

    Returns:
        Success status
    """
    try:
        monitor = get_vector_health_monitor()
        monitor.record_routing_decision(decision, routing_time_ms)

        return JSONResponse(
            content={
                "success": True,
                "message": "Routing decision recorded",
                "data": {
                    "decision": decision,
                    "routing_time_ms": routing_time_ms,
                    "document_type": document_type,
                    "quality_score": quality_score,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to record routing decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance/record")
async def record_search_performance(
    search_time_ms: float,
    collection: str,
    query_type: Optional[str] = None,
    result_count: Optional[int] = None,
):
    """
    Record search performance metrics for monitoring.

    Args:
        search_time_ms: Search execution time in milliseconds
        collection: Collection name where search was performed
        query_type: Optional query type classification
        result_count: Optional number of results returned

    Returns:
        Success status
    """
    try:
        monitor = get_vector_health_monitor()
        monitor.record_search_performance(search_time_ms)

        return JSONResponse(
            content={
                "success": True,
                "message": "Search performance recorded",
                "data": {
                    "search_time_ms": search_time_ms,
                    "collection": collection,
                    "query_type": query_type,
                    "result_count": result_count,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Failed to record search performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/export")
async def export_metrics(
    format: str = Query("json", description="Export format (json, csv)"),
    hours: int = Query(24, description="Hours of data to export", ge=1, le=168),
):
    """
    Export vector collection health metrics for external analysis.

    Args:
        format: Export format (json or csv)
        hours: Number of hours of data to export

    Returns:
        Exported metrics data in requested format
    """
    try:
        monitor = get_vector_health_monitor()
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Collect all metrics
        export_data = {
            "export_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "time_window_hours": hours,
                "format": format,
            },
            "collection_metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "collection_name": m.collection_name,
                    "total_vectors": m.total_vectors,
                    "avg_search_time_ms": m.avg_search_time_ms,
                    "health_status": m.health_status.value,
                    "memory_usage_mb": m.memory_usage_mb,
                }
                for m in monitor.collection_metrics_history
                if m.timestamp >= cutoff_time
            ],
            "balance_metrics": [
                {
                    "timestamp": b.timestamp.isoformat(),
                    "size_balance_ratio": b.size_balance_ratio,
                    "balance_status": b.balance_status.value,
                    "imbalance_severity": b.imbalance_severity,
                }
                for b in monitor.balance_metrics_history
                if b.timestamp >= cutoff_time
            ],
            "routing_metrics": [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "routing_accuracy_percentage": r.routing_accuracy_percentage,
                    "routing_error_rate": r.routing_error_rate,
                    "avg_routing_time_ms": r.avg_routing_time_ms,
                }
                for r in monitor.routing_metrics_history
                if r.timestamp >= cutoff_time
            ],
        }

        if format.lower() == "json":
            return JSONResponse(content={"success": True, "data": export_data})
        else:
            # For CSV format, you would convert to CSV here
            # For now, return JSON with CSV indication
            return JSONResponse(
                content={
                    "success": True,
                    "message": "CSV export not yet implemented",
                    "data": export_data,
                }
            )

    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
