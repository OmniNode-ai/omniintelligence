"""
Integration Tests for Performance Analytics API

Tests complete flow for 6 performance analytics endpoints:
1. GET /api/performance-analytics/baselines - All operation baselines
2. GET /api/performance-analytics/operations/{operation}/metrics - Detailed metrics
3. GET /api/performance-analytics/optimization-opportunities - Optimization suggestions
4. POST /api/performance-analytics/operations/{operation}/anomaly-check - Anomaly detection
5. GET /api/performance-analytics/trends - Performance trends analysis
6. GET /api/performance-analytics/health - Service health check

Phase 5C: Performance Intelligence - Workflow 9

Key Test Scenarios:
- Baseline calculation from measurements
- Percentile accuracy (p50, p95, p99)
- Z-score anomaly detection (threshold: 3.0 std devs)
- ROI-based opportunity ranking
- Trend analysis (improving/declining/stable)
- Statistical accuracy validation

Performance Targets:
- API response: <200ms per endpoint
- Baseline calculation: <10ms
- Anomaly detection: <5ms

Author: Archon Intelligence Team
Date: 2025-10-16
"""

from datetime import datetime

import pytest
from archon_services.performance.baseline_service import PerformanceBaselineService

# ============================================================================
# Test Markers
# ============================================================================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.performance_analytics,
]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def baseline_service():
    """Create and populate baseline service with test data"""
    service = PerformanceBaselineService(max_measurements=1000)

    # Record measurements for operation 1: Fast operation
    for i in range(50):
        await service.record_measurement(
            operation="fast_operation",
            duration_ms=100 + (i % 20),  # 100-120ms range
            context={"test": "fixture"},
        )

    # Record measurements for operation 2: Slow operation
    for i in range(50):
        await service.record_measurement(
            operation="slow_operation",
            duration_ms=800 + (i % 100),  # 800-900ms range
            context={"test": "fixture"},
        )

    # Record measurements for operation 3: Variable operation
    for i in range(50):
        await service.record_measurement(
            operation="variable_operation",
            duration_ms=200 + (i * 10),  # 200-690ms range (high variance)
            context={"test": "fixture"},
        )

    # Record measurements for operation 4: Critical operation (very slow)
    for i in range(30):
        await service.record_measurement(
            operation="critical_operation",
            duration_ms=2500 + (i % 200),  # 2500-2700ms range
            context={"test": "fixture", "priority": "high"},
        )

    return service


@pytest.fixture
async def initialize_baseline_service(baseline_service):
    """Initialize performance analytics API with baseline service"""
    from api.performance_analytics.routes import initialize_services

    initialize_services(baseline_service)
    yield
    # Cleanup after test


# ============================================================================
# Baseline Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
class TestBaselinesAPI:
    """Tests for GET /api/performance-analytics/baselines endpoint"""

    async def test_get_all_baselines_success(
        self, test_client, initialize_baseline_service
    ):
        """Test getting all operation baselines"""
        response = await test_client.get("/api/performance-analytics/baselines")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "baselines" in data
        assert "total_operations" in data
        assert "total_measurements" in data
        assert "timestamp" in data

        # Verify baseline data
        assert data["total_operations"] == 4
        assert data["total_measurements"] == 180  # 50 + 50 + 50 + 30

        # Verify baseline statistics structure
        for operation_name, baseline in data["baselines"].items():
            assert "p50" in baseline
            assert "p95" in baseline
            assert "p99" in baseline
            assert "mean" in baseline
            assert "std_dev" in baseline
            assert "sample_size" in baseline

    async def test_get_baselines_filter_by_operation(
        self, test_client, initialize_baseline_service
    ):
        """Test filtering baselines by specific operation"""
        response = await test_client.get(
            "/api/performance-analytics/baselines",
            params={"operation": "fast_operation"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify only one operation returned
        assert data["total_operations"] == 1
        assert "fast_operation" in data["baselines"]
        assert len(data["baselines"]) == 1

        # Verify baseline values are reasonable for fast operation
        baseline = data["baselines"]["fast_operation"]
        assert 100 <= baseline["p50"] <= 120
        assert 100 <= baseline["p95"] <= 120
        assert 100 <= baseline["mean"] <= 120

    async def test_get_baselines_nonexistent_operation(
        self, test_client, initialize_baseline_service
    ):
        """Test filtering by nonexistent operation returns 404"""
        response = await test_client.get(
            "/api/performance-analytics/baselines",
            params={"operation": "nonexistent_operation"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "No baseline found" in data["detail"]

    async def test_baseline_percentile_accuracy(
        self, test_client, initialize_baseline_service
    ):
        """Test percentile calculation accuracy"""
        response = await test_client.get(
            "/api/performance-analytics/baselines",
            params={"operation": "fast_operation"},
        )

        assert response.status_code == 200
        data = response.json()
        baseline = data["baselines"]["fast_operation"]

        # Verify p50 < p95 < p99 (percentiles should be ordered)
        assert baseline["p50"] < baseline["p95"]
        assert baseline["p95"] <= baseline["p99"]

        # Verify mean is reasonable
        assert baseline["p50"] <= baseline["mean"] <= baseline["p95"]

    async def test_baselines_timestamp_format(
        self, test_client, initialize_baseline_service
    ):
        """Test timestamp is in correct ISO format"""
        response = await test_client.get("/api/performance-analytics/baselines")

        assert response.status_code == 200
        data = response.json()

        # Verify timestamp can be parsed
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert timestamp.tzinfo is not None  # Should be timezone-aware


# ============================================================================
# Operation Metrics Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
class TestOperationMetricsAPI:
    """Tests for GET /api/performance-analytics/operations/{operation}/metrics endpoint"""

    async def test_get_operation_metrics_success(
        self, test_client, initialize_baseline_service
    ):
        """Test getting detailed metrics for specific operation"""
        response = await test_client.get(
            "/api/performance-analytics/operations/fast_operation/metrics"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["operation"] == "fast_operation"
        assert "baseline" in data
        assert "recent_measurements" in data
        assert "trend" in data
        assert "anomaly_count_24h" in data

        # Verify baseline statistics
        baseline = data["baseline"]
        assert baseline["sample_size"] >= 10
        assert baseline["p95"] > baseline["p50"]

        # Verify recent measurements
        assert len(data["recent_measurements"]) <= 10  # Default recent_count
        for measurement in data["recent_measurements"]:
            assert "duration_ms" in measurement
            assert "timestamp" in measurement
            assert "context" in measurement

        # Verify trend value
        assert data["trend"] in ["improving", "declining", "stable"]

    async def test_get_operation_metrics_custom_recent_count(
        self, test_client, initialize_baseline_service
    ):
        """Test getting metrics with custom recent_count"""
        response = await test_client.get(
            "/api/performance-analytics/operations/slow_operation/metrics",
            params={"recent_count": 5},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify exactly 5 recent measurements returned
        assert len(data["recent_measurements"]) == 5

    async def test_get_operation_metrics_recent_count_limits(
        self, test_client, initialize_baseline_service
    ):
        """Test recent_count parameter limits (1-100)"""
        # Test minimum limit (1)
        response = await test_client.get(
            "/api/performance-analytics/operations/fast_operation/metrics",
            params={"recent_count": 1},
        )
        assert response.status_code == 200
        assert len(response.json()["recent_measurements"]) == 1

        # Test maximum limit (100)
        response = await test_client.get(
            "/api/performance-analytics/operations/fast_operation/metrics",
            params={"recent_count": 100},
        )
        assert response.status_code == 200
        # Should return up to 100 (but may be less if fewer measurements exist)
        assert len(response.json()["recent_measurements"]) <= 100

    async def test_get_operation_metrics_nonexistent_operation(
        self, test_client, initialize_baseline_service
    ):
        """Test getting metrics for nonexistent operation returns 404"""
        response = await test_client.get(
            "/api/performance-analytics/operations/nonexistent_operation/metrics"
        )

        assert response.status_code == 404
        data = response.json()
        assert "No baseline found" in data["detail"]

    async def test_operation_metrics_trend_detection(
        self, test_client, initialize_baseline_service
    ):
        """Test trend detection logic"""
        # Variable operation should show trend based on increasing durations
        response = await test_client.get(
            "/api/performance-analytics/operations/variable_operation/metrics"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify trend is detected
        assert data["trend"] in ["improving", "declining", "stable"]

        # For variable_operation with increasing durations, should detect declining performance
        # (200ms → 690ms shows degradation)
        assert data["trend"] == "declining"

    async def test_operation_metrics_anomaly_count(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly count calculation"""
        response = await test_client.get(
            "/api/performance-analytics/operations/critical_operation/metrics"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify anomaly count is non-negative
        assert data["anomaly_count_24h"] >= 0


# ============================================================================
# Optimization Opportunities Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
class TestOptimizationOpportunitiesAPI:
    """Tests for GET /api/performance-analytics/optimization-opportunities endpoint"""

    async def test_get_optimization_opportunities_success(
        self, test_client, initialize_baseline_service
    ):
        """Test getting prioritized optimization opportunities"""
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "opportunities" in data
        assert "total_opportunities" in data
        assert "avg_roi" in data
        assert "total_potential_improvement" in data

        # Verify opportunities are present (operations > 500ms threshold)
        assert data["total_opportunities"] >= 2  # slow_operation and critical_operation

        # Verify opportunity structure
        for opportunity in data["opportunities"]:
            assert "operation" in opportunity
            assert "current_p95" in opportunity
            assert "estimated_improvement" in opportunity
            assert "effort_level" in opportunity
            assert "roi_score" in opportunity
            assert "priority" in opportunity
            assert "recommendations" in opportunity

            # Verify values are reasonable
            assert opportunity["current_p95"] > 500  # Threshold
            assert 0 <= opportunity["estimated_improvement"] <= 100
            assert opportunity["effort_level"] in ["low", "medium", "high"]
            assert opportunity["roi_score"] >= 0
            assert opportunity["priority"] in ["low", "medium", "high"]

    async def test_optimization_opportunities_roi_ordering(
        self, test_client, initialize_baseline_service
    ):
        """Test opportunities are sorted by ROI score (descending)"""
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities"
        )

        assert response.status_code == 200
        data = response.json()

        opportunities = data["opportunities"]
        if len(opportunities) > 1:
            # Verify ROI scores are in descending order
            roi_scores = [opp["roi_score"] for opp in opportunities]
            assert roi_scores == sorted(roi_scores, reverse=True)

    async def test_optimization_opportunities_min_roi_filter(
        self, test_client, initialize_baseline_service
    ):
        """Test filtering by minimum ROI score"""
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities",
            params={"min_roi": 15.0},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all opportunities meet min_roi threshold
        for opportunity in data["opportunities"]:
            assert opportunity["roi_score"] >= 15.0

    async def test_optimization_opportunities_max_effort_filter(
        self, test_client, initialize_baseline_service
    ):
        """Test filtering by maximum effort level"""
        # Filter to only low effort
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities",
            params={"max_effort": "low"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all opportunities have low effort
        for opportunity in data["opportunities"]:
            assert opportunity["effort_level"] == "low"

    async def test_optimization_opportunities_empty_baselines(self, test_client):
        """Test optimization opportunities with no baselines"""
        # Initialize with empty baseline service
        from api.performance_analytics.routes import initialize_services

        empty_service = PerformanceBaselineService(max_measurements=1000)
        initialize_services(empty_service)

        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify empty response
        assert data["opportunities"] == []
        assert data["total_opportunities"] == 0
        assert data["avg_roi"] == 0.0
        assert data["total_potential_improvement"] == 0.0

    async def test_optimization_opportunities_recommendations(
        self, test_client, initialize_baseline_service
    ):
        """Test that opportunities include actionable recommendations"""
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all opportunities have recommendations
        for opportunity in data["opportunities"]:
            assert len(opportunity["recommendations"]) > 0
            # Verify recommendations are strings
            for rec in opportunity["recommendations"]:
                assert isinstance(rec, str)
                assert len(rec) > 0


# ============================================================================
# Anomaly Detection Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
class TestAnomalyDetectionAPI:
    """Tests for POST /api/performance-analytics/operations/{operation}/anomaly-check endpoint"""

    async def test_anomaly_detection_normal_duration(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly detection with normal duration (no anomaly)"""
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": 110.0},  # Within normal range (100-120ms)
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["anomaly_detected"] is False
        assert "z_score" in data
        assert abs(data["z_score"]) < 3.0  # Below threshold
        assert data["current_duration_ms"] == 110.0
        assert data["baseline_mean"] > 0
        assert data["baseline_p95"] > 0
        assert "deviation_percentage" in data
        assert data["severity"] == "normal"

    async def test_anomaly_detection_extreme_duration(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly detection with extreme duration (anomaly detected)"""
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": 5000.0},  # Way above normal (100-120ms)
        )

        assert response.status_code == 200
        data = response.json()

        # Verify anomaly detected
        assert data["anomaly_detected"] is True
        assert abs(data["z_score"]) > 3.0  # Above threshold
        assert data["current_duration_ms"] == 5000.0
        assert data["severity"] in ["medium", "high", "critical"]

    async def test_anomaly_detection_z_score_calculation(
        self, test_client, initialize_baseline_service
    ):
        """Test Z-score calculation accuracy"""
        # Get baseline first
        baseline_response = await test_client.get(
            "/api/performance-analytics/baselines",
            params={"operation": "fast_operation"},
        )
        baseline = baseline_response.json()["baselines"]["fast_operation"]

        # Test with duration = mean + 3*std_dev (exactly at threshold)
        threshold_duration = baseline["mean"] + (3.0 * baseline["std_dev"])

        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": threshold_duration},
        )

        assert response.status_code == 200
        data = response.json()

        # Z-score should be approximately 3.0
        assert 2.9 <= abs(data["z_score"]) <= 3.1

    async def test_anomaly_detection_severity_levels(
        self, test_client, initialize_baseline_service
    ):
        """Test different severity levels based on Z-score"""
        baseline_response = await test_client.get(
            "/api/performance-analytics/baselines",
            params={"operation": "fast_operation"},
        )
        baseline = baseline_response.json()["baselines"]["fast_operation"]

        # Test medium severity (z_score = 3.5)
        medium_duration = baseline["mean"] + (3.5 * baseline["std_dev"])
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": medium_duration},
        )
        assert response.status_code == 200
        assert response.json()["severity"] == "medium"

        # Test high severity (z_score = 4.5)
        high_duration = baseline["mean"] + (4.5 * baseline["std_dev"])
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": high_duration},
        )
        assert response.status_code == 200
        assert response.json()["severity"] == "high"

        # Test critical severity (z_score = 5.5)
        critical_duration = baseline["mean"] + (5.5 * baseline["std_dev"])
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": critical_duration},
        )
        assert response.status_code == 200
        assert response.json()["severity"] == "critical"

    async def test_anomaly_detection_no_baseline(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly detection for operation without baseline"""
        response = await test_client.post(
            "/api/performance-analytics/operations/nonexistent_operation/anomaly-check",
            json={"duration_ms": 100.0},
        )

        assert response.status_code == 200
        data = response.json()

        # No baseline means no anomaly detected
        assert data["anomaly_detected"] is False
        assert data["z_score"] == 0.0
        assert data["severity"] == "normal"

    async def test_anomaly_detection_deviation_percentage(
        self, test_client, initialize_baseline_service
    ):
        """Test deviation percentage calculation"""
        baseline_response = await test_client.get(
            "/api/performance-analytics/baselines",
            params={"operation": "fast_operation"},
        )
        baseline = baseline_response.json()["baselines"]["fast_operation"]

        # Test with 200% of mean (2x slower)
        double_duration = baseline["mean"] * 2.0

        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": double_duration},
        )

        assert response.status_code == 200
        data = response.json()

        # Deviation should be approximately 100%
        assert 95 <= data["deviation_percentage"] <= 105


# ============================================================================
# Performance Trends Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
class TestPerformanceTrendsAPI:
    """Tests for GET /api/performance-analytics/trends endpoint"""

    async def test_get_trends_default_24h(
        self, test_client, initialize_baseline_service
    ):
        """Test getting trends with default 24h window"""
        response = await test_client.get("/api/performance-analytics/trends")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["time_window"] == "24h"
        assert "operations" in data
        assert "overall_health" in data

        # Verify overall health status
        assert data["overall_health"] in ["excellent", "good", "warning", "critical"]

        # Verify operation trends
        for operation_name, trend in data["operations"].items():
            assert "trend" in trend
            assert "avg_duration_change" in trend
            assert "anomaly_count" in trend

            assert trend["trend"] in ["improving", "declining", "stable"]
            assert isinstance(trend["avg_duration_change"], (int, float))
            assert trend["anomaly_count"] >= 0

    async def test_get_trends_7d_window(self, test_client, initialize_baseline_service):
        """Test getting trends with 7d window"""
        response = await test_client.get(
            "/api/performance-analytics/trends", params={"time_window": "7d"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_window"] == "7d"

    async def test_get_trends_30d_window(
        self, test_client, initialize_baseline_service
    ):
        """Test getting trends with 30d window"""
        response = await test_client.get(
            "/api/performance-analytics/trends", params={"time_window": "30d"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_window"] == "30d"

    async def test_get_trends_overall_health_calculation(
        self, test_client, initialize_baseline_service
    ):
        """Test overall health status calculation"""
        response = await test_client.get("/api/performance-analytics/trends")

        assert response.status_code == 200
        data = response.json()

        # Health should reflect overall system state
        operations = data["operations"]
        declining_count = sum(
            1 for op in operations.values() if op["trend"] == "declining"
        )
        total_operations = len(operations)

        if declining_count == 0:
            # No declining operations should result in excellent or good health
            assert data["overall_health"] in ["excellent", "good"]
        elif declining_count > total_operations * 0.5:
            # More than 50% declining should result in warning or critical
            assert data["overall_health"] in ["warning", "critical"]

    async def test_get_trends_empty_operations(self, test_client):
        """Test trends with no operations tracked"""
        from api.performance_analytics.routes import initialize_services

        empty_service = PerformanceBaselineService(max_measurements=1000)
        initialize_services(empty_service)

        response = await test_client.get("/api/performance-analytics/trends")

        assert response.status_code == 200
        data = response.json()

        # Empty operations should return good health by default
        assert data["operations"] == {}
        assert data["overall_health"] == "good"

    async def test_get_trends_trend_direction_accuracy(
        self, test_client, initialize_baseline_service
    ):
        """Test trend direction detection accuracy"""
        response = await test_client.get("/api/performance-analytics/trends")

        assert response.status_code == 200
        data = response.json()

        # Variable operation (200ms → 690ms) should show declining trend
        if "variable_operation" in data["operations"]:
            assert data["operations"]["variable_operation"]["trend"] == "declining"
            assert data["operations"]["variable_operation"]["avg_duration_change"] > 5


# ============================================================================
# Health Check Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
class TestHealthCheckAPI:
    """Tests for GET /api/performance-analytics/health endpoint"""

    async def test_health_check_success(self, test_client, initialize_baseline_service):
        """Test health check with healthy service"""
        response = await test_client.get("/api/performance-analytics/health")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert data["baseline_service"] in ["operational", "down"]
        assert data["optimization_analyzer"] in ["operational", "down"]
        assert "total_operations_tracked" in data
        assert "total_measurements" in data
        assert "uptime_seconds" in data

        # Verify healthy state
        assert data["status"] == "healthy"
        assert data["baseline_service"] == "operational"
        assert data["total_operations_tracked"] >= 0
        assert data["total_measurements"] >= 0
        assert data["uptime_seconds"] >= 0

    async def test_health_check_uptime_tracking(
        self, test_client, initialize_baseline_service
    ):
        """Test uptime is tracked correctly"""
        import time

        # First health check
        response1 = await test_client.get("/api/performance-analytics/health")
        uptime1 = response1.json()["uptime_seconds"]

        # Wait 1 second
        time.sleep(1)

        # Second health check
        response2 = await test_client.get("/api/performance-analytics/health")
        uptime2 = response2.json()["uptime_seconds"]

        # Uptime should increase
        assert uptime2 > uptime1

    async def test_health_check_operation_tracking(
        self, test_client, initialize_baseline_service
    ):
        """Test operation tracking in health check"""
        response = await test_client.get("/api/performance-analytics/health")

        assert response.status_code == 200
        data = response.json()

        # Should track 4 operations from fixture
        assert data["total_operations_tracked"] == 4
        assert data["total_measurements"] == 180


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
@pytest.mark.error_handling
class TestPerformanceAnalyticsEdgeCases:
    """Edge case and error handling tests"""

    async def test_invalid_recent_count_below_minimum(
        self, test_client, initialize_baseline_service
    ):
        """Test recent_count below minimum (1) returns validation error"""
        response = await test_client.get(
            "/api/performance-analytics/operations/fast_operation/metrics",
            params={"recent_count": 0},
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_recent_count_above_maximum(
        self, test_client, initialize_baseline_service
    ):
        """Test recent_count above maximum (100) returns validation error"""
        response = await test_client.get(
            "/api/performance-analytics/operations/fast_operation/metrics",
            params={"recent_count": 101},
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_min_roi_negative(
        self, test_client, initialize_baseline_service
    ):
        """Test negative min_roi returns validation error"""
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities",
            params={"min_roi": -1.0},
        )

        assert response.status_code == 422  # Validation error

    async def test_invalid_max_effort_value(
        self, test_client, initialize_baseline_service
    ):
        """Test invalid max_effort value (handled gracefully)"""
        response = await test_client.get(
            "/api/performance-analytics/optimization-opportunities",
            params={"max_effort": "invalid"},
        )

        # Should accept but treat as 'high' (default fallback)
        assert response.status_code == 200

    async def test_anomaly_check_invalid_duration(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly check with invalid duration"""
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": -10.0},  # Negative duration
        )

        assert response.status_code == 422  # Validation error

    async def test_anomaly_check_missing_duration(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly check without duration"""
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={},
        )

        assert response.status_code == 422  # Validation error

    async def test_trends_invalid_time_window(
        self, test_client, initialize_baseline_service
    ):
        """Test trends with invalid time window (handled gracefully)"""
        response = await test_client.get(
            "/api/performance-analytics/trends", params={"time_window": "invalid"}
        )

        # Should default to 24h
        assert response.status_code == 200
        data = response.json()
        assert data["time_window"] == "invalid"  # Preserved but defaults to 24h parsing


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance_analytics
@pytest.mark.performance
class TestPerformanceAnalyticsPerformance:
    """Performance tests for API endpoints"""

    async def test_baselines_api_performance(
        self, test_client, initialize_baseline_service
    ):
        """Test baselines API response time <200ms"""
        import time

        start = time.time()
        response = await test_client.get("/api/performance-analytics/baselines")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert (
            elapsed_ms < 200
        ), f"Baselines API took {elapsed_ms:.2f}ms, exceeds 200ms target"

    async def test_metrics_api_performance(
        self, test_client, initialize_baseline_service
    ):
        """Test metrics API response time <200ms"""
        import time

        start = time.time()
        response = await test_client.get(
            "/api/performance-analytics/operations/fast_operation/metrics"
        )
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert (
            elapsed_ms < 200
        ), f"Metrics API took {elapsed_ms:.2f}ms, exceeds 200ms target"

    async def test_anomaly_detection_performance(
        self, test_client, initialize_baseline_service
    ):
        """Test anomaly detection response time <50ms"""
        import time

        start = time.time()
        response = await test_client.post(
            "/api/performance-analytics/operations/fast_operation/anomaly-check",
            json={"duration_ms": 110.0},
        )
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert (
            elapsed_ms < 50
        ), f"Anomaly detection took {elapsed_ms:.2f}ms, exceeds 50ms target"
