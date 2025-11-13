"""
Pipeline Performance Monitoring API

Comprehensive monitoring dashboard API for MCP document indexing pipeline.
Provides real-time metrics, distributed tracing, performance analytics,
and operational insights.

Key Features:
- Real-time pipeline metrics and SLA tracking
- Distributed trace visualization
- Performance bottleneck identification
- Resource utilization monitoring
- Business metrics and throughput analysis
- Alert management and notification
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from server.middleware.metrics_middleware import get_health_status

# Import monitoring infrastructure
from server.middleware.pipeline_metrics import (
    get_pipeline_metrics,
    get_pipeline_status,
    pipeline_metrics,
)
from server.middleware.pipeline_tracing import pipeline_tracer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline/monitoring", tags=["pipeline_monitoring"])

# WebSocket connections for real-time updates
websocket_connections: list[WebSocket] = []


@router.get("/metrics", response_class=PlainTextResponse)
async def get_pipeline_prometheus_metrics():
    """
    Get pipeline metrics in Prometheus format.

    Returns comprehensive metrics for the MCP document indexing pipeline
    including timing, throughput, error rates, and resource utilization.
    """
    try:
        metrics_data, content_type = get_pipeline_metrics()
        return PlainTextResponse(content=metrics_data, media_type=content_type)
    except Exception as e:
        logger.error(f"Error generating pipeline metrics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate pipeline metrics"
        )


@router.get("/status")
async def get_pipeline_status_overview():
    """
    Get comprehensive pipeline status overview.

    Returns:
    - Active pipeline executions
    - Recent performance metrics
    - Service health scores
    - SLA compliance status
    - Current bottlenecks
    """
    try:
        status = get_pipeline_status()

        # Add trace analytics
        trace_analytics = pipeline_tracer.get_trace_analytics(time_window_hours=1)
        status["trace_analytics"] = trace_analytics

        # Add active traces
        active_traces = pipeline_tracer.get_active_traces(limit=50)
        status["active_traces"] = len(active_traces)

        return status
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pipeline status")


@router.get("/performance/dashboard")
async def get_performance_dashboard(
    time_window: str = Query("1h", description="Time window: 15m, 1h, 6h, 24h, 7d"),
    include_traces: bool = Query(True, description="Include trace analytics"),
):
    """
    Get comprehensive performance dashboard data.

    Provides all data needed for a real-time monitoring dashboard:
    - Pipeline performance metrics
    - Service health and latency
    - Throughput and success rates
    - Error patterns and bottlenecks
    - Distributed trace insights
    """
    try:
        # Parse time window
        time_window_hours = {"15m": 0.25, "1h": 1, "6h": 6, "24h": 24, "7d": 168}.get(
            time_window, 1
        )

        # Get pipeline metrics
        pipeline_status = get_pipeline_status()

        # Get trace analytics if requested
        trace_data = None
        if include_traces:
            trace_data = pipeline_tracer.get_trace_analytics(
                time_window_hours=int(time_window_hours)
            )

        # Get system metrics
        system_health = get_health_status()

        # Construct dashboard data
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "time_window": time_window,
            "time_window_hours": time_window_hours,
            # Pipeline overview
            "pipeline": {
                "status": pipeline_status,
                "active_executions": pipeline_status.get("active_executions", 0),
                "recent_executions": pipeline_status.get("metrics", {}).get(
                    "recent_executions", 0
                ),
                "success_rate": pipeline_status.get("metrics", {}).get(
                    "success_rate_last_100", 0
                ),
                "avg_duration": pipeline_status.get("metrics", {}).get(
                    "avg_duration_last_10", 0
                ),
                "sla_compliance": pipeline_status.get("metrics", {}).get(
                    "sla_compliance", {}
                ),
                "bottlenecks": pipeline_status.get("metrics", {}).get(
                    "bottlenecks", []
                ),
            },
            # Service health
            "services": {
                "health_scores": pipeline_status.get("service_health", {}),
                "system_health": system_health,
            },
            # Performance metrics
            "performance": {
                "throughput": {
                    "documents_per_hour": 0,  # Would calculate from metrics
                    "peak_throughput": 0,
                    "current_queue_sizes": {},
                },
                "latency": {
                    "p50": 0,  # Would calculate from metrics
                    "p95": 0,
                    "p99": 0,
                    "by_stage": {},
                },
                "errors": {"error_rate": 0, "error_types": {}, "error_services": {}},
            },
            # Trace analytics
            "traces": trace_data,
            # Alerts and recommendations
            "alerts": {
                "active_alerts": await _get_active_pipeline_alerts(),
                "recommendations": await _get_performance_recommendations(
                    pipeline_status
                ),
            },
        }

        return dashboard_data

    except Exception as e:
        logger.error(f"Error getting performance dashboard: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get performance dashboard"
        )


@router.get("/traces/{correlation_id}")
async def get_trace_details(correlation_id: str):
    """
    Get detailed trace information for a specific correlation ID.

    Returns:
    - Complete trace timeline
    - Service call graph
    - Performance breakdown
    - Error details if any
    """
    try:
        trace_data = pipeline_tracer.get_trace(correlation_id)

        if not trace_data:
            raise HTTPException(status_code=404, detail="Trace not found")

        # Analyze trace for additional insights
        trace_analysis = _analyze_trace(trace_data)

        return {
            "correlation_id": correlation_id,
            "trace_data": trace_data,
            "analysis": trace_analysis,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trace details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trace details")


@router.get("/traces")
async def get_traces_overview(
    limit: int = Query(100, description="Number of traces to return"),
    status: Optional[str] = Query(
        None, description="Filter by status: active, completed, failed"
    ),
    time_window: str = Query("1h", description="Time window for traces"),
):
    """
    Get overview of recent traces.

    Returns list of traces with summary information for trace browser.
    """
    try:
        if status == "active":
            traces = pipeline_tracer.get_active_traces(limit=limit)
        else:
            # Get all traces in time window
            time_window_hours = {"15m": 0.25, "1h": 1, "6h": 6, "24h": 24}.get(
                time_window, 1
            )

            pipeline_tracer.get_trace_analytics(
                time_window_hours=int(time_window_hours)
            )

            traces = []  # Would need to implement trace listing

        return {
            "traces": traces,
            "total_count": len(traces),
            "status_filter": status,
            "time_window": time_window,
        }

    except Exception as e:
        logger.error(f"Error getting traces overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get traces overview")


@router.get("/analytics/performance")
async def get_performance_analytics(
    time_window: str = Query("24h", description="Analysis time window"),
    group_by: str = Query(
        "stage", description="Group by: stage, service, document_type"
    ),
):
    """
    Get detailed performance analytics.

    Provides statistical analysis of pipeline performance:
    - Latency distributions
    - Throughput trends
    - Error pattern analysis
    - Performance regression detection
    """
    try:
        time_window_hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}.get(
            time_window, 24
        )

        # Get trace analytics
        trace_analytics = pipeline_tracer.get_trace_analytics(
            time_window_hours=time_window_hours
        )

        # Get pipeline metrics
        pipeline_status = pipeline_metrics.get_pipeline_metrics()

        analytics = {
            "time_window_hours": time_window_hours,
            "group_by": group_by,
            "generated_at": datetime.now().isoformat(),
            # Performance statistics
            "performance_stats": {
                "average_duration": pipeline_status.get("avg_duration_last_10", 0),
                "success_rate": pipeline_status.get("success_rate_last_100", 0),
                "sla_compliance": pipeline_status.get("sla_compliance", {}),
            },
            # Trend analysis
            "trends": {
                "throughput_trend": "stable",  # Would calculate from metrics
                "latency_trend": "stable",
                "error_rate_trend": "stable",
            },
            # Trace analytics
            "trace_insights": trace_analytics,
            # Recommendations
            "optimization_opportunities": await _identify_optimization_opportunities(
                trace_analytics
            ),
        }

        return analytics

    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get performance analytics"
        )


@router.get("/health/services")
async def get_service_health_detailed():
    """
    Get detailed health status for all pipeline services.

    Returns:
    - Individual service health scores
    - Response time metrics
    - Error rates and patterns
    - Resource utilization
    - Connectivity status
    """
    try:
        services = [
            "archon-server",
            "archon-mcp",
            "archon-bridge",
            "archon-intelligence",
            "archon-search",
            "qdrant",
            "memgraph",
        ]

        service_health = {}

        for service in services:
            health_data = await _check_service_health(service)
            service_health[service] = health_data

        # Calculate overall health score
        health_scores = [
            health.get("health_score", 0) for health in service_health.values()
        ]
        overall_health = sum(health_scores) / len(health_scores) if health_scores else 0

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_health_score": overall_health,
            "services": service_health,
            "critical_services": [
                service
                for service, health in service_health.items()
                if health.get("health_score", 0) < 0.5
            ],
            "recommendations": await _get_health_recommendations(service_health),
        }

    except Exception as e:
        logger.error(f"Error getting service health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service health")


@router.post("/alerts/threshold")
async def create_performance_alert(
    metric_name: str,
    threshold_value: float,
    comparison: str = "greater_than",  # greater_than, less_than, equals
    time_window: str = "5m",
    severity: str = "warning",
):
    """
    Create a performance alert threshold.

    Sets up monitoring alerts for pipeline metrics with configurable
    thresholds and notification preferences.
    """
    try:
        alert_config = {
            "alert_id": f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "metric_name": metric_name,
            "threshold_value": threshold_value,
            "comparison": comparison,
            "time_window": time_window,
            "severity": severity,
            "created_at": datetime.now().isoformat(),
            "enabled": True,
        }

        # Store alert configuration (would use database in production)
        # For now, return the configuration

        return {
            "status": "created",
            "alert": alert_config,
            "message": f"Alert created for {metric_name} {comparison} {threshold_value}",
        }

    except Exception as e:
        logger.error(f"Error creating performance alert: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create performance alert"
        )


@router.websocket("/ws/realtime")
async def websocket_realtime_metrics(websocket: WebSocket):
    """
    WebSocket endpoint for real-time pipeline metrics.

    Streams real-time updates of:
    - Pipeline execution status
    - Performance metrics
    - Service health changes
    - Alert notifications
    """
    await websocket.accept()
    websocket_connections.append(websocket)

    try:
        while True:
            # Send periodic updates
            try:
                # Get current status
                status = get_pipeline_status()

                # Get recent traces
                active_traces = pipeline_tracer.get_active_traces(limit=10)

                update_data = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "status_update",
                    "data": {
                        "pipeline_status": status,
                        "active_traces_count": len(active_traces),
                        "health_score": status.get("service_health", {}),
                    },
                }

                await websocket.send_text(json.dumps(update_data))

                # Wait before next update
                await asyncio.sleep(5)  # Update every 5 seconds

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket update: {e}")
                await asyncio.sleep(10)

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


# Helper functions


async def _check_service_health(service_name: str) -> dict[str, Any]:
    """Check health of a specific service"""
    # This would implement actual health checks for each service
    # For now, return mock data

    base_ports = {
        "archon-server": 8181,
        "archon-mcp": 8051,
        "archon-bridge": 8054,
        "archon-intelligence": 8053,
        "archon-search": 8055,
        "qdrant": 6333,
        "memgraph": 7687,
    }

    try:
        # Would implement actual HTTP/TCP health checks here
        health_data = {
            "service_name": service_name,
            "status": "healthy",
            "health_score": 1.0,
            "response_time_ms": 50,  # Mock data
            "last_check": datetime.now().isoformat(),
            "port": base_ports.get(service_name),
            "details": {
                "connectivity": "ok",
                "resource_usage": "normal",
                "error_rate": 0.0,
            },
        }

        return health_data

    except Exception as e:
        return {
            "service_name": service_name,
            "status": "unhealthy",
            "health_score": 0.0,
            "error": str(e),
            "last_check": datetime.now().isoformat(),
        }


async def _get_active_pipeline_alerts() -> list[dict[str, Any]]:
    """Get currently active pipeline alerts"""
    # This would integrate with alerting system
    # For now, return mock alerts based on current status

    alerts = []

    # Check pipeline metrics for alert conditions
    status = pipeline_metrics.get_pipeline_metrics()

    # Example alert conditions
    if status.get("avg_duration_last_10", 0) > 30:
        alerts.append(
            {
                "id": "alert_001",
                "type": "performance",
                "severity": "warning",
                "title": "High Pipeline Latency",
                "description": f"Average pipeline duration is {status['avg_duration_last_10']:.1f}s (threshold: 30s)",
                "created_at": datetime.now().isoformat(),
                "metric": "avg_duration",
                "current_value": status.get("avg_duration_last_10", 0),
                "threshold": 30,
            }
        )

    if status.get("success_rate_last_100", 1.0) < 0.95:
        alerts.append(
            {
                "id": "alert_002",
                "type": "reliability",
                "severity": "critical",
                "title": "Low Success Rate",
                "description": f"Pipeline success rate is {status['success_rate_last_100']:.1%} (threshold: 95%)",
                "created_at": datetime.now().isoformat(),
                "metric": "success_rate",
                "current_value": status.get("success_rate_last_100", 1.0),
                "threshold": 0.95,
            }
        )

    return alerts


async def _get_performance_recommendations(
    pipeline_status: dict[str, Any],
) -> list[dict[str, Any]]:
    """Get performance optimization recommendations"""
    recommendations = []

    metrics = pipeline_status.get("metrics", {})

    # Check bottlenecks
    bottlenecks = metrics.get("bottlenecks", [])
    for bottleneck in bottlenecks[:3]:  # Top 3 bottlenecks
        recommendations.append(
            {
                "type": "optimization",
                "priority": bottleneck.get("severity", "medium"),
                "title": f"Optimize {bottleneck['stage']} Performance",
                "description": f"Stage {bottleneck['stage']} averages {bottleneck['avg_duration']:.1f}s",
                "action": "Consider scaling or optimization",
                "estimated_impact": "20-30% latency reduction",
            }
        )

    # Check SLA compliance
    sla_compliance = metrics.get("sla_compliance", {})
    for stage, compliance in sla_compliance.items():
        if compliance < 0.9:  # Less than 90% compliance
            recommendations.append(
                {
                    "type": "sla_compliance",
                    "priority": "high",
                    "title": f"Improve {stage} SLA Compliance",
                    "description": f"Only {compliance:.1%} of {stage} operations meet SLA",
                    "action": "Review performance thresholds and optimize",
                    "estimated_impact": "Improved SLA compliance",
                }
            )

    return recommendations


async def _get_health_recommendations(
    service_health: dict[str, Any],
) -> list[dict[str, Any]]:
    """Get service health recommendations"""
    recommendations = []

    for service_name, health_data in service_health.items():
        health_score = health_data.get("health_score", 1.0)

        if health_score < 0.5:
            recommendations.append(
                {
                    "type": "service_health",
                    "priority": "critical",
                    "service": service_name,
                    "title": f"Critical Health Issue: {service_name}",
                    "description": f"Service health score is {health_score:.1%}",
                    "action": "Investigate service logs and restart if necessary",
                }
            )
        elif health_score < 0.8:
            recommendations.append(
                {
                    "type": "service_health",
                    "priority": "warning",
                    "service": service_name,
                    "title": f"Health Degradation: {service_name}",
                    "description": f"Service health score is {health_score:.1%}",
                    "action": "Monitor closely and consider preemptive maintenance",
                }
            )

    return recommendations


def _analyze_trace(trace_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze a trace for insights"""
    if not trace_data:
        return {}

    # Calculate total duration
    stage_events = [e for e in trace_data[1:] if e.get("duration_seconds")]
    total_duration = sum(e["duration_seconds"] for e in stage_events)

    # Find longest stage
    longest_stage = None
    if stage_events:
        longest_stage = max(stage_events, key=lambda x: x["duration_seconds"])

    # Check for errors
    errors = [e for e in trace_data[1:] if e.get("status") == "error"]

    # Calculate service breakdown
    service_breakdown = {}
    for event in stage_events:
        service = event.get("service_name", "unknown")
        duration = event.get("duration_seconds", 0)

        if service not in service_breakdown:
            service_breakdown[service] = {"duration": 0, "calls": 0}

        service_breakdown[service]["duration"] += duration
        service_breakdown[service]["calls"] += 1

    return {
        "total_duration": total_duration,
        "stage_count": len(stage_events),
        "error_count": len(errors),
        "longest_stage": {
            "name": longest_stage.get("stage_name") if longest_stage else None,
            "duration": longest_stage.get("duration_seconds") if longest_stage else 0,
        },
        "service_breakdown": service_breakdown,
        "has_errors": len(errors) > 0,
        "status": "failed" if errors else "completed",
    }


async def _identify_optimization_opportunities(
    trace_analytics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Identify optimization opportunities from trace data"""
    opportunities = []

    # Check service performance
    service_performance = trace_analytics.get("service_performance", {})
    for service, metrics in service_performance.items():
        if metrics.get("average_duration", 0) > 5.0:
            opportunities.append(
                {
                    "type": "service_optimization",
                    "service": service,
                    "title": f"Optimize {service} Performance",
                    "description": f"Service averages {metrics['average_duration']:.1f}s per operation",
                    "priority": (
                        "high" if metrics["average_duration"] > 10.0 else "medium"
                    ),
                    "estimated_impact": "20-40% latency reduction",
                }
            )

        if metrics.get("error_rate", 0) > 0.05:  # 5% error rate
            opportunities.append(
                {
                    "type": "reliability",
                    "service": service,
                    "title": f"Improve {service} Reliability",
                    "description": f"Service has {metrics['error_rate']:.1%} error rate",
                    "priority": "high",
                    "estimated_impact": "Improved success rate",
                }
            )

    # Check bottlenecks
    bottlenecks = trace_analytics.get("bottleneck_analysis", [])
    for bottleneck in bottlenecks[:3]:  # Top 3
        opportunities.append(
            {
                "type": "bottleneck",
                "stage": bottleneck["stage"],
                "title": f"Address {bottleneck['stage']} Bottleneck",
                "description": f"Stage shows {bottleneck['severity']} performance impact",
                "priority": bottleneck["severity"],
                "estimated_impact": "Pipeline throughput improvement",
            }
        )

    return opportunities


# Broadcast helper for WebSocket updates
async def broadcast_pipeline_update(update_data: dict[str, Any]):
    """Broadcast update to all connected WebSocket clients"""
    if not websocket_connections:
        return

    message = json.dumps(
        {
            "timestamp": datetime.now().isoformat(),
            "type": "pipeline_update",
            "data": update_data,
        }
    )

    # Send to all connected clients
    disconnected = []
    for websocket in websocket_connections:
        try:
            await websocket.send_text(message)
        except Exception as e:
            # WebSocket disconnected or send failed - mark for cleanup
            logger.debug(f"Failed to send pipeline update to WebSocket: {e}")
            disconnected.append(websocket)

    # Remove disconnected clients
    for websocket in disconnected:
        websocket_connections.remove(websocket)
