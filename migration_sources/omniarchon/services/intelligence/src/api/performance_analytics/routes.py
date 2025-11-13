"""
Performance Analytics API Routes

FastAPI router implementing 6 endpoints for performance analytics:
1. GET /api/performance-analytics/baselines - All operation baselines
2. GET /api/performance-analytics/operations/{operation}/metrics - Detailed metrics
3. GET /api/performance-analytics/optimization-opportunities - Optimization suggestions
4. POST /api/performance-analytics/operations/{operation}/anomaly-check - Anomaly detection
5. GET /api/performance-analytics/trends - Performance trends analysis
6. GET /api/performance-analytics/health - Service health check

Phase 5C: Performance Intelligence - Workflow 9
Created: 2025-10-15
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query
from src.api.performance_analytics.models import (
    AnomalyCheckRequest,
    AnomalyCheckResponse,
    BaselinesResponse,
    BaselineStats,
    HealthResponse,
    OperationBaseline,
    OperationTrend,
    OptimizationOpportunitiesResponse,
    OptimizationOpportunity,
    PerformanceMeasurementData,
    TrendsResponse,
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/performance-analytics", tags=["Performance Analytics"])

# Global service components (initialized in lifespan)
baseline_service = None
service_start_time = None


def initialize_services(baseline_svc):
    """
    Initialize performance analytics services.

    Called from app.py lifespan to inject baseline service.
    """
    global baseline_service, service_start_time
    baseline_service = baseline_svc
    service_start_time = time.time()
    logger.info("Performance Analytics API initialized")


@router.get(
    "/baselines",
    response_model=BaselinesResponse,
    summary="Get All Operation Baselines",
    description=(
        "Returns baseline statistics for all tracked operations. "
        "Includes p50, p95, p99, mean, std_dev, and sample size for each operation."
    ),
)
async def get_all_baselines(
    operation: Optional[str] = Query(
        None, description="Filter by specific operation name"
    ),
):
    """
    Get all operation baselines with statistics.

    Query Parameters:
    - operation: Optional filter for specific operation

    Response:
    - baselines: Dictionary of baseline statistics by operation name
    - total_operations: Total number of operations tracked
    - total_measurements: Total measurements recorded
    - timestamp: Response generation timestamp
    """
    try:
        logger.info(f"GET /api/performance-analytics/baselines | operation={operation}")

        if not baseline_service:
            raise HTTPException(
                status_code=503, detail="Performance baseline service not initialized"
            )

        # Get all baselines
        all_baselines = await baseline_service.get_all_baselines()

        # Filter if operation specified
        if operation:
            if operation not in all_baselines:
                raise HTTPException(
                    status_code=404,
                    detail=f"No baseline found for operation: {operation}",
                )
            all_baselines = {operation: all_baselines[operation]}

        # Convert to response format
        baselines_response = {}
        for op_name, baseline_data in all_baselines.items():
            baselines_response[op_name] = BaselineStats(
                p50=baseline_data["p50"],
                p95=baseline_data["p95"],
                p99=baseline_data["p99"],
                mean=baseline_data["mean"],
                std_dev=baseline_data["std_dev"],
                sample_size=baseline_data["sample_size"],
            )

        # Calculate totals
        total_measurements = baseline_service.get_measurement_count()

        logger.info(
            f"Baselines retrieved | total_operations={len(baselines_response)} | "
            f"total_measurements={total_measurements}"
        )

        return BaselinesResponse(
            baselines=baselines_response,
            total_operations=len(baselines_response),
            total_measurements=total_measurements,
            timestamp=datetime.now(timezone.utc),
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError) as e:
        logger.error(f"Invalid data structure in baselines: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve baselines: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors (database, network, etc.)
        logger.error(f"Unexpected error retrieving baselines: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve baselines: {str(e)}"
        )


@router.get(
    "/operations/{operation}/metrics",
    response_model=OperationBaseline,
    summary="Get Operation Metrics",
    description=(
        "Returns detailed performance metrics for a specific operation including "
        "baseline statistics, recent measurements, trend analysis, and anomaly count."
    ),
)
async def get_operation_metrics(
    operation: str = Path(..., description="Operation name to retrieve metrics for"),
    recent_count: int = Query(
        10, ge=1, le=100, description="Number of recent measurements to include"
    ),
):
    """
    Get detailed metrics for specific operation.

    Path Parameters:
    - operation: Operation name

    Query Parameters:
    - recent_count: Number of recent measurements to return (default: 10)

    Response:
    - operation: Operation name
    - baseline: Baseline statistics
    - recent_measurements: Recent measurement data points
    - trend: Performance trend (improving/declining/stable)
    - anomaly_count_24h: Number of anomalies in last 24h
    """
    try:
        logger.info(
            f"GET /api/performance-analytics/operations/{operation}/metrics | recent_count={recent_count}"
        )

        if not baseline_service:
            raise HTTPException(
                status_code=503, detail="Performance baseline service not initialized"
            )

        # Get baseline for operation
        baseline_data = await baseline_service.get_baseline(operation)

        if not baseline_data:
            raise HTTPException(
                status_code=404, detail=f"No baseline found for operation: {operation}"
            )

        # Get recent measurements
        recent_measurements = baseline_service.get_recent_measurements(
            operation=operation, limit=recent_count
        )

        # Convert measurements to response format
        measurement_data = []
        for measurement in recent_measurements:
            measurement_data.append(
                PerformanceMeasurementData(
                    duration_ms=measurement.duration_ms,
                    timestamp=measurement.timestamp,
                    context=measurement.context,
                )
            )

        # Analyze trend (simple heuristic based on recent measurements)
        trend = "stable"
        if len(recent_measurements) >= 5:
            first_half = [
                m.duration_ms
                for m in recent_measurements[: len(recent_measurements) // 2]
            ]
            second_half = [
                m.duration_ms
                for m in recent_measurements[len(recent_measurements) // 2 :]
            ]

            if first_half and second_half:
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)

                change_pct = ((avg_second - avg_first) / avg_first) * 100

                if change_pct < -5:
                    trend = "improving"
                elif change_pct > 5:
                    trend = "declining"

        # Count anomalies in last 24h (simplified - check measurements exceeding 2*p95)
        anomaly_count = 0
        threshold = baseline_data["p95"] * 2
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

        for measurement in recent_measurements:
            if (
                measurement.timestamp >= cutoff_time
                and measurement.duration_ms > threshold
            ):
                anomaly_count += 1

        logger.info(
            f"Operation metrics retrieved | operation={operation} | "
            f"trend={trend} | anomalies_24h={anomaly_count}"
        )

        return OperationBaseline(
            operation=operation,
            baseline=BaselineStats(**baseline_data),
            recent_measurements=measurement_data,
            trend=trend,
            anomaly_count_24h=anomaly_count,
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, IndexError) as e:
        logger.error(f"Invalid data in operation metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve operation metrics: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors (database, network, etc.)
        logger.error(
            f"Unexpected error retrieving operation metrics: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve operation metrics: {str(e)}"
        )


@router.get(
    "/optimization-opportunities",
    response_model=OptimizationOpportunitiesResponse,
    summary="Get Optimization Opportunities",
    description=(
        "Returns prioritized optimization opportunities based on current performance baselines. "
        "Opportunities are ranked by ROI score (improvement / effort)."
    ),
)
async def get_optimization_opportunities(
    min_roi: float = Query(1.0, ge=0.0, description="Minimum ROI score to include"),
    max_effort: str = Query(
        "high", description="Maximum effort level: low/medium/high"
    ),
):
    """
    Get prioritized optimization opportunities.

    Query Parameters:
    - min_roi: Minimum ROI score (default: 1.0)
    - max_effort: Maximum effort level (default: high)

    Response:
    - opportunities: List of optimization opportunities
    - total_opportunities: Count of opportunities
    - avg_roi: Average ROI score
    - total_potential_improvement: Average improvement potential (%)
    """
    try:
        logger.info(
            f"GET /api/performance-analytics/optimization-opportunities | "
            f"min_roi={min_roi} | max_effort={max_effort}"
        )

        if not baseline_service:
            raise HTTPException(
                status_code=503, detail="Performance baseline service not initialized"
            )

        # Get all baselines
        all_baselines = await baseline_service.get_all_baselines()

        if not all_baselines:
            logger.info("No baselines available for optimization analysis")
            return OptimizationOpportunitiesResponse(
                opportunities=[],
                total_opportunities=0,
                avg_roi=0.0,
                total_potential_improvement=0.0,
            )

        # Analyze each operation for optimization opportunities
        opportunities = []
        effort_map = {"low": 1, "medium": 2, "high": 3}
        max_effort_value = effort_map.get(max_effort.lower(), 3)

        for operation, baseline in all_baselines.items():
            # High p95 suggests opportunity for optimization
            if baseline["p95"] > 500:  # > 500ms
                estimated_improvement = min(
                    60.0, (baseline["p95"] - 500) / baseline["p95"] * 100
                )

                # Determine effort level based on p95
                if baseline["p95"] > 2000:
                    effort = "high"
                    effort_value = 3
                elif baseline["p95"] > 1000:
                    effort = "medium"
                    effort_value = 2
                else:
                    effort = "low"
                    effort_value = 1

                # Calculate ROI score
                roi_score = (
                    estimated_improvement / effort_value if effort_value > 0 else 0
                )

                # Filter by max_effort and min_roi
                if effort_value <= max_effort_value and roi_score >= min_roi:
                    # Determine priority
                    if roi_score > 20:
                        priority = "high"
                    elif roi_score > 10:
                        priority = "medium"
                    else:
                        priority = "low"

                    # Generate recommendations
                    recommendations = []
                    if baseline["p95"] > 1500:
                        recommendations.append(
                            "Add caching layer for frequently accessed data"
                        )
                    if baseline["mean"] > 800:
                        recommendations.append(
                            "Implement batch processing for bulk operations"
                        )
                    if baseline["std_dev"] > baseline["mean"] * 0.5:
                        recommendations.append(
                            "Investigate and reduce performance variance"
                        )

                    opportunities.append(
                        OptimizationOpportunity(
                            operation=operation,
                            current_p95=baseline["p95"],
                            estimated_improvement=estimated_improvement,
                            effort_level=effort,
                            roi_score=roi_score,
                            priority=priority,
                            recommendations=recommendations
                            or ["Review operation implementation for optimization"],
                        )
                    )

        # Sort by ROI score (descending)
        opportunities.sort(key=lambda x: x.roi_score, reverse=True)

        # Calculate statistics
        total_opportunities = len(opportunities)
        avg_roi = (
            sum(o.roi_score for o in opportunities) / total_opportunities
            if total_opportunities > 0
            else 0.0
        )
        total_potential_improvement = (
            sum(o.estimated_improvement for o in opportunities) / total_opportunities
            if total_opportunities > 0
            else 0.0
        )

        logger.info(
            f"Optimization opportunities identified | total={total_opportunities} | "
            f"avg_roi={avg_roi:.2f} | avg_improvement={total_potential_improvement:.2f}%"
        )

        return OptimizationOpportunitiesResponse(
            opportunities=opportunities,
            total_opportunities=total_opportunities,
            avg_roi=round(avg_roi, 2),
            total_potential_improvement=round(total_potential_improvement, 2),
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError) as e:
        logger.error(f"Invalid data in optimization opportunities: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve optimization opportunities: {str(e)}",
        )
    except Exception as e:
        # Catch-all for unexpected errors (database, network, etc.)
        logger.error(
            f"Unexpected error retrieving optimization opportunities: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve optimization opportunities: {str(e)}",
        )


@router.post(
    "/operations/{operation}/anomaly-check",
    response_model=AnomalyCheckResponse,
    summary="Check for Performance Anomaly",
    description=(
        "Detects if the current operation duration is a performance anomaly "
        "using Z-score analysis against the established baseline."
    ),
)
async def check_performance_anomaly(
    request: AnomalyCheckRequest,
    operation: str = Path(..., description="Operation name to check"),
):
    """
    Check if current duration is a performance anomaly.

    Path Parameters:
    - operation: Operation name

    Request Body:
    - duration_ms: Current operation duration in milliseconds

    Response:
    - anomaly_detected: Whether anomaly was detected
    - z_score: Z-score relative to baseline
    - current_duration_ms: Input duration
    - baseline_mean: Baseline mean duration
    - baseline_p95: Baseline 95th percentile
    - deviation_percentage: Percentage deviation from mean
    - severity: Anomaly severity (normal/medium/high/critical)
    """
    try:
        logger.info(
            f"POST /api/performance-analytics/operations/{operation}/anomaly-check | "
            f"duration_ms={request.duration_ms}"
        )

        if not baseline_service:
            raise HTTPException(
                status_code=503, detail="Performance baseline service not initialized"
            )

        # Perform anomaly detection
        result = await baseline_service.detect_performance_anomaly(
            operation=operation,
            current_duration_ms=request.duration_ms,
            threshold_std_devs=3.0,
        )

        # Determine severity based on z-score
        if "reason" in result and result["reason"] == "no_baseline":
            severity = "normal"
        elif result.get("anomaly_detected"):
            z_score = abs(result["z_score"])
            if z_score > 5:
                severity = "critical"
            elif z_score > 4:
                severity = "high"
            elif z_score > 3:
                severity = "medium"
            else:
                severity = "normal"
        else:
            severity = "normal"

        logger.info(
            f"Anomaly check complete | operation={operation} | "
            f"anomaly_detected={result.get('anomaly_detected', False)} | "
            f"severity={severity}"
        )

        return AnomalyCheckResponse(
            anomaly_detected=result.get("anomaly_detected", False),
            z_score=result.get("z_score", 0.0),
            current_duration_ms=request.duration_ms,
            baseline_mean=result.get("baseline_mean", 0.0),
            baseline_p95=result.get("baseline_p95", 0.0),
            deviation_percentage=result.get("deviation_percentage", 0.0),
            severity=severity,
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, ZeroDivisionError) as e:
        logger.error(f"Invalid data in anomaly check: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to perform anomaly check: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors (database, network, etc.)
        logger.error(f"Unexpected error in anomaly check: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to perform anomaly check: {str(e)}"
        )


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Get Performance Trends",
    description=(
        "Returns performance trends across all operations for the specified time window. "
        "Analyzes trend direction, duration changes, and anomaly counts."
    ),
)
async def get_performance_trends(
    time_window: str = Query(
        "24h", description="Time window for trend analysis: 24h/7d/30d"
    ),
):
    """
    Get performance trends across all operations.

    Query Parameters:
    - time_window: Time window for analysis (default: 24h)

    Response:
    - time_window: Analysis time window
    - operations: Trends by operation name
    - overall_health: System health status (excellent/good/warning/critical)
    """
    try:
        logger.info(
            f"GET /api/performance-analytics/trends | time_window={time_window}"
        )

        if not baseline_service:
            raise HTTPException(
                status_code=503, detail="Performance baseline service not initialized"
            )

        # Parse time window
        hours_map = {"24h": 24, "7d": 168, "30d": 720}
        hours = hours_map.get(time_window.lower(), 24)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get all operations
        operations = baseline_service.get_operations()

        if not operations:
            logger.info("No operations tracked for trend analysis")
            return TrendsResponse(
                time_window=time_window, operations={}, overall_health="good"
            )

        # Analyze trends for each operation
        operation_trends = {}
        total_anomalies = 0
        total_operations = len(operations)
        degraded_operations = 0

        for operation in operations:
            recent_measurements = baseline_service.get_recent_measurements(
                operation=operation, limit=50
            )

            # Filter by time window
            windowed_measurements = [
                m for m in recent_measurements if m.timestamp >= cutoff_time
            ]

            if len(windowed_measurements) < 2:
                # Not enough data for trend analysis
                operation_trends[operation] = OperationTrend(
                    trend="stable", avg_duration_change=0.0, anomaly_count=0
                )
                continue

            # Calculate trend
            mid_point = len(windowed_measurements) // 2
            first_half = windowed_measurements[:mid_point]
            second_half = windowed_measurements[mid_point:]

            avg_first = sum(m.duration_ms for m in first_half) / len(first_half)
            avg_second = sum(m.duration_ms for m in second_half) / len(second_half)

            avg_duration_change = (
                ((avg_second - avg_first) / avg_first) * 100 if avg_first > 0 else 0.0
            )

            if avg_duration_change < -5:
                trend = "improving"
            elif avg_duration_change > 5:
                trend = "declining"
                degraded_operations += 1
            else:
                trend = "stable"

            # Count anomalies (durations > 2 * mean)
            mean_duration = sum(m.duration_ms for m in windowed_measurements) / len(
                windowed_measurements
            )
            anomaly_count = sum(
                1 for m in windowed_measurements if m.duration_ms > mean_duration * 2
            )
            total_anomalies += anomaly_count

            operation_trends[operation] = OperationTrend(
                trend=trend,
                avg_duration_change=round(avg_duration_change, 2),
                anomaly_count=anomaly_count,
            )

        # Determine overall health
        if degraded_operations == 0 and total_anomalies < total_operations * 0.1:
            overall_health = "excellent"
        elif (
            degraded_operations < total_operations * 0.2
            and total_anomalies < total_operations * 0.3
        ):
            overall_health = "good"
        elif degraded_operations < total_operations * 0.5:
            overall_health = "warning"
        else:
            overall_health = "critical"

        logger.info(
            f"Trends analyzed | time_window={time_window} | "
            f"total_operations={total_operations} | "
            f"overall_health={overall_health}"
        )

        return TrendsResponse(
            time_window=time_window,
            operations=operation_trends,
            overall_health=overall_health,
        )

    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, IndexError, ZeroDivisionError) as e:
        logger.error(f"Invalid data in trends analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve trends: {str(e)}"
        )
    except Exception as e:
        # Catch-all for unexpected errors (database, network, etc.)
        logger.error(f"Unexpected error retrieving trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve trends: {str(e)}"
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check performance analytics service health and component status",
)
async def health_check(correlation_id: Optional[UUID] = None):
    """
    Performance analytics service health check.

    Returns service status, component status, and uptime information.
    """
    try:
        logger.info(
            f"GET /api/performance-analytics/health | correlation_id={correlation_id}"
        )

        # Check baseline service
        baseline_status = "operational" if baseline_service else "down"

        # Optimization analyzer status (placeholder for Workflow 8)
        optimization_status = (
            "operational"  # Will be integrated with OptimizationAnalyzer
        )

        # Get statistics
        total_operations = (
            len(baseline_service.get_operations()) if baseline_service else 0
        )
        total_measurements = (
            baseline_service.get_measurement_count() if baseline_service else 0
        )

        # Calculate uptime
        uptime_seconds = (
            int(time.time() - service_start_time) if service_start_time else 0
        )

        # Overall status
        if baseline_status == "operational" and optimization_status == "operational":
            status = "healthy"
        elif baseline_status == "operational" or optimization_status == "operational":
            status = "degraded"
        else:
            status = "unhealthy"

        logger.info(
            f"Health check complete | status={status} | "
            f"operations={total_operations} | measurements={total_measurements}"
        )

        return HealthResponse(
            status=status,
            baseline_service=baseline_status,
            optimization_analyzer=optimization_status,
            total_operations_tracked=total_operations,
            total_measurements=total_measurements,
            uptime_seconds=uptime_seconds,
        )

    except Exception as e:
        # Health check should always return, catch all exceptions
        logger.error(f"Health check failed: {e}", exc_info=True)
        return HealthResponse(
            status="unhealthy",
            baseline_service="unknown",
            optimization_analyzer="unknown",
            total_operations_tracked=0,
            total_measurements=0,
            uptime_seconds=0,
        )
