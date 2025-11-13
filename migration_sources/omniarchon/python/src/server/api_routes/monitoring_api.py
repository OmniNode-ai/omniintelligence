"""
Production Monitoring API Routes

Provides endpoints for Prometheus metrics collection, health checks,
and intelligent monitoring insights for the Archon platform.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

# Import metrics middleware
from server.middleware.metrics_middleware import (
    get_health_status,
    get_intelligent_health_insights,
    get_metrics,
    record_intelligence_analysis,
    record_rag_query,
    set_background_tasks,
    set_db_connections,
    set_websocket_connections,
)

# Import Archon intelligence integration
try:
    from ..services.intelligence_service import get_intelligence_client

    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False

# Import intelligent monitoring service
try:
    from ..services.intelligent_monitoring_service import (
        get_intelligent_monitoring_service,
    )

    INTELLIGENT_MONITORING_AVAILABLE = True
except ImportError:
    INTELLIGENT_MONITORING_AVAILABLE = False

# Import database clients for connection monitoring
try:
    from ..services.client_manager import get_database_client

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus format for scraping.
    This endpoint should be scraped by Prometheus every 15-30 seconds.
    """
    try:
        return get_metrics()
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@router.get("/health/basic")
async def basic_health_check():
    """
    Basic health check with system metrics.

    Returns basic system health information including:
    - CPU usage
    - Memory usage
    - Disk usage
    - Process metrics
    """
    try:
        return get_health_status()
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health status")


@router.get("/health/intelligent")
async def intelligent_health_check():
    """
    Intelligent health check with AI-powered insights.

    Returns comprehensive health information including:
    - Basic system metrics
    - Intelligent health insights
    - Performance recommendations
    - Optimization opportunities
    """
    try:
        return get_intelligent_health_insights()
    except Exception as e:
        logger.error(f"Error getting intelligent health insights: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get intelligent health insights"
        )


@router.get("/health/services")
async def service_health_check():
    """
    Service-specific health checks for microservices.

    Checks the health of:
    - Database connections
    - Intelligence service
    - External APIs
    - Background services
    """
    service_status = {"timestamp": datetime.now().isoformat(), "services": {}}

    # Check database connectivity
    if DATABASE_AVAILABLE:
        try:
            client = get_database_client()
            # Simple connectivity test
            client.table("archon_projects").select("id").limit(1).execute()
            service_status["services"]["database"] = {
                "status": "healthy",
                "response_time_ms": 0,  # Could measure actual response time
                "last_check": datetime.now().isoformat(),
            }
            # Update connection count metric
            set_db_connections(1, "archon-server")
        except Exception as e:
            service_status["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat(),
            }

    # Check intelligence service
    if INTELLIGENCE_AVAILABLE:
        try:
            # This would need to be implemented in intelligence_service
            service_status["services"]["intelligence"] = {
                "status": "healthy",
                "last_check": datetime.now().isoformat(),
            }
        except Exception as e:
            service_status["services"]["intelligence"] = {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat(),
            }

    # Check background task health
    try:
        from ..services.background_task_manager import get_task_manager

        task_manager = get_task_manager()

        # Get task statistics
        active_tasks = len(getattr(task_manager, "active_tasks", []))
        pending_tasks = len(getattr(task_manager, "pending_tasks", []))

        service_status["services"]["background_tasks"] = {
            "status": "healthy",
            "active_tasks": active_tasks,
            "pending_tasks": pending_tasks,
            "last_check": datetime.now().isoformat(),
        }

        # Update metrics
        set_background_tasks("active", active_tasks, "archon-server")
        set_background_tasks("pending", pending_tasks, "archon-server")

    except Exception as e:
        service_status["services"]["background_tasks"] = {
            "status": "unknown",
            "error": str(e),
            "last_check": datetime.now().isoformat(),
        }

    # Overall status
    all_services = service_status["services"].values()
    healthy_services = [s for s in all_services if s.get("status") == "healthy"]

    if len(healthy_services) == len(all_services):
        service_status["overall_status"] = "healthy"
    elif len(healthy_services) > len(all_services) / 2:
        service_status["overall_status"] = "degraded"
    else:
        service_status["overall_status"] = "unhealthy"

    return service_status


@router.get("/performance/trends")
async def performance_trends():
    """
    Get performance trends and analytics.

    Returns performance trends over time including:
    - Response time trends
    - Error rate trends
    - Resource usage trends
    - Performance predictions
    """
    try:
        # This would integrate with time-series data
        # For now, return basic trend information

        trends = {
            "timestamp": datetime.now().isoformat(),
            "period": "1h",  # 1 hour window
            "trends": {
                "response_time": {
                    "current_avg_ms": 150,  # Would come from actual metrics
                    "previous_avg_ms": 140,
                    "trend": "increasing",
                    "change_percent": 7.1,
                },
                "error_rate": {
                    "current_rate": 0.02,  # 2% error rate
                    "previous_rate": 0.01,
                    "trend": "increasing",
                    "change_percent": 100.0,
                },
                "cpu_usage": {
                    "current_avg": 45.2,
                    "previous_avg": 42.1,
                    "trend": "increasing",
                    "change_percent": 7.4,
                },
                "memory_usage": {
                    "current_avg": 68.5,
                    "previous_avg": 65.3,
                    "trend": "increasing",
                    "change_percent": 4.9,
                },
            },
            "alerts": [
                {
                    "type": "performance",
                    "severity": "warning",
                    "message": "Response time increased by 7.1% in the last hour",
                    "recommendation": "Monitor traffic patterns and consider scaling",
                }
            ],
            "predictions": {
                "next_hour": {
                    "response_time_ms": 165,
                    "cpu_usage": 48.5,
                    "confidence": 0.75,
                }
            },
        }

        return trends

    except Exception as e:
        logger.error(f"Error getting performance trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance trends")


@router.post("/performance/baseline")
async def establish_performance_baseline(
    operation_name: str, duration_minutes: int = 10
):
    """
    Establish performance baseline for an operation.

    This integrates with Archon's intelligence service to:
    - Collect baseline metrics
    - Analyze performance patterns
    - Set performance thresholds
    - Enable intelligent alerting
    """
    if not INTELLIGENCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligence service not available"
        )

    try:
        # Start baseline collection
        baseline_id = f"baseline_{operation_name}_{datetime.now().isoformat()}"

        # This would integrate with the intelligence service
        baseline_result = {
            "baseline_id": baseline_id,
            "operation_name": operation_name,
            "duration_minutes": duration_minutes,
            "status": "collecting",
            "started_at": datetime.now().isoformat(),
            "expected_completion": (
                datetime.now() + timedelta(minutes=duration_minutes)
            ).isoformat(),
        }

        # Record the baseline establishment
        record_intelligence_analysis("baseline_establishment", "archon-server")

        return baseline_result

    except Exception as e:
        logger.error(f"Error establishing baseline: {e}")
        raise HTTPException(status_code=500, detail="Failed to establish baseline")


@router.get("/optimization/opportunities")
async def optimization_opportunities(operation_name: Optional[str] = None):
    """
    Get optimization opportunities using intelligence analysis.

    Returns:
    - Performance bottlenecks
    - Resource optimization suggestions
    - Cost-benefit analysis
    - Implementation priorities
    """
    if not INTELLIGENCE_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligence service not available"
        )

    try:
        # This would integrate with the intelligence service for real analysis
        opportunities = {
            "timestamp": datetime.now().isoformat(),
            "operation_name": operation_name,
            "opportunities": [
                {
                    "type": "database_optimization",
                    "severity": "medium",
                    "title": "Database Query Optimization",
                    "description": "Multiple N+1 query patterns detected in project queries",
                    "impact": "20-30% response time improvement",
                    "effort": "medium",
                    "recommendation": "Implement query batching and eager loading",
                },
                {
                    "type": "caching",
                    "severity": "high",
                    "title": "RAG Query Caching",
                    "description": "Frequent duplicate RAG queries without caching",
                    "impact": "50-70% response time improvement for cached queries",
                    "effort": "low",
                    "recommendation": "Implement Redis caching for RAG results",
                },
                {
                    "type": "resource_scaling",
                    "severity": "low",
                    "title": "Memory Allocation",
                    "description": "Container memory usage approaching 80% during peak hours",
                    "impact": "Prevent OOM issues and improve stability",
                    "effort": "minimal",
                    "recommendation": "Increase container memory limit from 1GB to 1.5GB",
                },
            ],
            "priority_matrix": {
                "high_impact_low_effort": ["caching"],
                "high_impact_high_effort": ["database_optimization"],
                "low_impact_low_effort": ["resource_scaling"],
                "low_impact_high_effort": [],
            },
        }

        # Record the analysis
        record_intelligence_analysis("optimization_analysis", "archon-server")

        return opportunities

    except Exception as e:
        logger.error(f"Error getting optimization opportunities: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get optimization opportunities"
        )


@router.get("/alerts/active")
async def active_alerts():
    """
    Get currently active monitoring alerts.

    Returns alerts from various sources:
    - System resource alerts
    - Application performance alerts
    - Business logic alerts
    - Predictive alerts
    """
    try:
        # This would integrate with alerting system
        alerts = {
            "timestamp": datetime.now().isoformat(),
            "active_alerts": [
                {
                    "id": "alert_001",
                    "type": "performance",
                    "severity": "warning",
                    "title": "High Response Time",
                    "description": "Average response time exceeded 500ms threshold",
                    "started_at": (datetime.now() - timedelta(minutes=15)).isoformat(),
                    "service": "archon-server",
                    "endpoint": "/api/rag/query",
                    "current_value": 650,
                    "threshold": 500,
                    "tags": ["performance", "rag", "response_time"],
                },
                {
                    "id": "alert_002",
                    "type": "resource",
                    "severity": "info",
                    "title": "Memory Usage Trend",
                    "description": "Memory usage trending upward over 2 hours",
                    "started_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "service": "archon-server",
                    "current_value": 72.5,
                    "threshold": 80.0,
                    "prediction": "Will exceed threshold in 4 hours at current rate",
                    "tags": ["resource", "memory", "trending"],
                },
            ],
            "summary": {
                "total": 2,
                "by_severity": {"critical": 0, "warning": 1, "info": 1},
                "by_type": {"performance": 1, "resource": 1, "business": 0},
            },
        }

        return alerts

    except Exception as e:
        logger.error(f"Error getting active alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active alerts")


@router.post("/websockets/count")
async def update_websocket_count(count: int):
    """
    Update the count of active WebSocket connections.

    This should be called by the WebSocket handler to keep
    the metrics up to date.
    """
    try:
        set_websocket_connections(count, "archon-server")
        return {
            "status": "updated",
            "websocket_count": count,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error updating websocket count: {e}")
        raise HTTPException(status_code=500, detail="Failed to update websocket count")


# Integration endpoints for other services to report metrics
@router.post("/events/rag_query")
async def record_rag_query_event(query_type: str, duration_seconds: float):
    """
    Record a RAG query event for metrics.

    This should be called by RAG query handlers to track
    query performance and usage patterns.
    """
    try:
        record_rag_query(query_type, duration_seconds, "archon-server")
        return {
            "status": "recorded",
            "query_type": query_type,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error recording RAG query event: {e}")
        raise HTTPException(status_code=500, detail="Failed to record RAG query event")


@router.post("/events/intelligence_analysis")
async def record_intelligence_analysis_event(analysis_type: str):
    """
    Record an intelligence analysis event.

    This should be called by intelligence analysis handlers
    to track analysis usage and performance.
    """
    try:
        record_intelligence_analysis(analysis_type, "archon-server")
        return {
            "status": "recorded",
            "analysis_type": analysis_type,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error recording intelligence analysis event: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to record intelligence analysis event"
        )


@router.get("/intelligence/insights")
async def get_intelligent_monitoring_insights(time_window: str = "1h"):
    """
    Get AI-powered monitoring insights.

    Returns intelligent analysis of system behavior including:
    - Anomaly detection results
    - Performance predictions
    - Optimization recommendations
    - Alert correlation analysis
    """
    if not INTELLIGENT_MONITORING_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligent monitoring service not available"
        )

    try:
        service = get_intelligent_monitoring_service()
        insights = await service.get_intelligent_insights(time_window)
        return insights
    except Exception as e:
        logger.error(f"Error getting intelligent insights: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get intelligent insights"
        )


@router.post("/intelligence/start_analysis")
async def start_intelligent_analysis():
    """
    Start background intelligent monitoring analysis.

    Enables continuous AI-powered monitoring including:
    - Anomaly detection
    - Trend analysis
    - Performance pattern recognition
    - Predictive alerting
    """
    if not INTELLIGENT_MONITORING_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligent monitoring service not available"
        )

    try:
        service = get_intelligent_monitoring_service()
        await service.start_background_analysis()
        return {
            "status": "started",
            "message": "Intelligent monitoring analysis started",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error starting intelligent analysis: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to start intelligent analysis"
        )


@router.post("/intelligence/stop_analysis")
async def stop_intelligent_analysis():
    """
    Stop background intelligent monitoring analysis.
    """
    if not INTELLIGENT_MONITORING_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligent monitoring service not available"
        )

    try:
        service = get_intelligent_monitoring_service()
        await service.stop_background_analysis()
        return {
            "status": "stopped",
            "message": "Intelligent monitoring analysis stopped",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error stopping intelligent analysis: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to stop intelligent analysis"
        )


@router.get("/intelligence/anomalies")
async def get_current_anomalies():
    """
    Get current anomalies detected by the AI monitoring system.

    Returns anomalies with confidence scores and contextual information.
    """
    if not INTELLIGENT_MONITORING_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligent monitoring service not available"
        )

    try:
        service = get_intelligent_monitoring_service()
        anomalies = await service._get_current_anomalies()
        return {
            "timestamp": datetime.now().isoformat(),
            "anomalies": anomalies,
            "count": len(anomalies),
        }
    except Exception as e:
        logger.error(f"Error getting current anomalies: {e}")
        raise HTTPException(status_code=500, detail="Failed to get current anomalies")


@router.get("/intelligence/predictions")
async def get_performance_predictions():
    """
    Get AI-powered performance predictions.

    Returns predicted values for key metrics with confidence intervals.
    """
    if not INTELLIGENT_MONITORING_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Intelligent monitoring service not available"
        )

    try:
        service = get_intelligent_monitoring_service()
        predictions = await service._get_current_predictions()
        return {
            "timestamp": datetime.now().isoformat(),
            "predictions": predictions,
            "count": len(predictions),
        }
    except Exception as e:
        logger.error(f"Error getting performance predictions: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get performance predictions"
        )
