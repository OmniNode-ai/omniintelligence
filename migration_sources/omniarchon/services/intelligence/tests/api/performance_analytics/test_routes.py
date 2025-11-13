"""
Comprehensive tests for Performance Analytics API

Tests all 6 endpoints with realistic data and scenarios.

Phase 5C: Performance Intelligence - Workflow 9
Created: 2025-10-15
"""

from datetime import datetime, timezone
from typing import Dict, List

import numpy as np
import pytest

# The pyproject.toml has pythonpath configured, so we can import directly
from archon_services.performance.baseline_service import (
    PerformanceBaselineService,
    PerformanceMeasurement,
)
from fastapi.testclient import TestClient


# Test Data Constants
class TestDataConstants:
    """Centralized test data constants for performance analytics tests"""

    MAX_MEASUREMENTS = 100
    MIN_BASELINE_SAMPLES = 2
    RECENT_MEASUREMENTS_LIMIT = 10

    # Operation test data with realistic durations (in milliseconds)
    OPERATION_DURATIONS = {
        "codegen_validation": [450, 480, 520, 460, 500, 470, 490, 510, 480, 495],
        "api_request": [150, 160, 140, 155, 165, 148, 152, 158, 162, 151],
        "database_query": [2000, 2100, 1950, 2050, 2150, 2000, 2100, 2050, 2000, 2100],
    }

    # Anomaly detection thresholds
    NORMAL_DURATION_MULTIPLIER = 1.0
    ANOMALY_DURATION_MULTIPLIER = 10.0
    ANOMALY_Z_SCORE_THRESHOLD = 3.0


class TestDataBuilder:
    """Builder class for creating test data and baselines"""

    @staticmethod
    def create_measurement(
        operation: str, duration_ms: float, context: Dict = None
    ) -> PerformanceMeasurement:
        """Create a single performance measurement"""
        return PerformanceMeasurement(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
            context=context or {"test": True},
        )

    @staticmethod
    def compute_baseline_stats(durations: List[float]) -> Dict:
        """Compute baseline statistics from duration measurements"""
        if len(durations) < TestDataConstants.MIN_BASELINE_SAMPLES:
            return None

        return {
            "p50": float(np.percentile(durations, 50)),
            "p95": float(np.percentile(durations, 95)),
            "p99": float(np.percentile(durations, 99)),
            "mean": float(np.mean(durations)),
            "std_dev": float(np.std(durations)),
            "sample_size": len(durations),
        }

    @staticmethod
    def populate_service_with_measurements(
        service: PerformanceBaselineService, operations_data: Dict[str, List[float]]
    ) -> None:
        """Populate service with measurements and compute baselines"""
        for operation, durations in operations_data.items():
            # Add measurements to service
            for duration in durations:
                measurement = TestDataBuilder.create_measurement(operation, duration)
                service.measurements.append(measurement)
                service._measurement_count += 1

            # Compute and store baseline statistics
            baseline_stats = TestDataBuilder.compute_baseline_stats(durations)
            if baseline_stats:
                service.baselines[operation] = baseline_stats


@pytest.fixture
def baseline_service():
    """Create a PerformanceBaselineService with test data and pre-computed baselines"""
    service = PerformanceBaselineService(
        max_measurements=TestDataConstants.MAX_MEASUREMENTS
    )

    # Populate service with test measurements and baselines
    TestDataBuilder.populate_service_with_measurements(
        service, TestDataConstants.OPERATION_DURATIONS
    )

    return service


@pytest.fixture
def client(baseline_service):
    """Create test client with initialized service"""
    from api.performance_analytics.routes import initialize_services, router
    from fastapi import FastAPI

    # Initialize the routes with the test service
    initialize_services(baseline_service)

    # Create a minimal test FastAPI app with just the performance analytics router
    test_app = FastAPI(title="Test App")
    test_app.include_router(router)

    # Return TestClient with the test app
    return TestClient(test_app)


class TestHelpers:
    """Helper methods for common test assertions and operations"""

    @staticmethod
    def assert_baseline_structure(baseline: Dict) -> None:
        """Assert that a baseline has the required structure"""
        required_fields = ["p50", "p95", "p99", "mean", "std_dev", "sample_size"]
        for field in required_fields:
            assert field in baseline, f"Missing required field: {field}"

        # Verify statistical ordering
        assert baseline["p95"] >= baseline["p50"], "p95 should be >= p50"
        assert baseline["p99"] >= baseline["p95"], "p99 should be >= p95"
        assert baseline["mean"] > 0, "mean should be positive"
        assert baseline["sample_size"] > 0, "sample_size should be positive"

    @staticmethod
    def assert_baselines_response_structure(data: Dict) -> None:
        """Assert the standard baselines response structure"""
        required_fields = [
            "baselines",
            "total_operations",
            "total_measurements",
            "timestamp",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @staticmethod
    def assert_operation_metrics_structure(data: Dict, operation: str) -> None:
        """Assert operation metrics response structure"""
        assert data["operation"] == operation
        required_fields = [
            "baseline",
            "recent_measurements",
            "trend",
            "anomaly_count_24h",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify trend is valid
        valid_trends = ["improving", "declining", "stable"]
        assert data["trend"] in valid_trends, f"Invalid trend: {data['trend']}"

    @staticmethod
    def assert_optimization_opportunity_structure(opportunity: Dict) -> None:
        """Assert optimization opportunity structure"""
        required_fields = [
            "operation",
            "current_p95",
            "estimated_improvement",
            "effort_level",
            "roi_score",
            "priority",
            "recommendations",
        ]
        for field in required_fields:
            assert field in opportunity, f"Missing required field: {field}"

        # Verify enum values
        assert opportunity["effort_level"] in ["low", "medium", "high"]
        assert opportunity["priority"] in ["low", "medium", "high"]

    @staticmethod
    def assert_anomaly_response_structure(data: Dict) -> None:
        """Assert anomaly detection response structure"""
        required_fields = [
            "anomaly_detected",
            "z_score",
            "current_duration_ms",
            "baseline_mean",
            "baseline_p95",
            "deviation_percentage",
            "severity",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @staticmethod
    def assert_trends_response_structure(data: Dict, time_window: str) -> None:
        """Assert trends response structure"""
        assert data["time_window"] == time_window
        assert "operations" in data
        assert "overall_health" in data

        # Verify overall health is valid
        valid_health = ["excellent", "good", "warning", "critical"]
        assert data["overall_health"] in valid_health

    @staticmethod
    def assert_health_response_structure(data: Dict) -> None:
        """Assert health check response structure"""
        required_fields = [
            "status",
            "baseline_service",
            "optimization_analyzer",
            "total_operations_tracked",
            "total_measurements",
            "uptime_seconds",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify status enums
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert data["baseline_service"] in ["operational", "degraded", "down"]
        assert data["optimization_analyzer"] in ["operational", "degraded", "down"]


class TestPerformanceAnalyticsAPI:
    """Test suite for Performance Analytics API endpoints"""

    def test_get_baselines_all(self, client):
        """Test GET /api/performance-analytics/baselines - all operations"""
        response = client.get("/api/performance-analytics/baselines")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_baselines_response_structure(data)

        # Verify baselines exist for all test operations
        expected_operations = list(TestDataConstants.OPERATION_DURATIONS.keys())
        assert len(data["baselines"]) == len(expected_operations)
        for operation in expected_operations:
            assert operation in data["baselines"]

        # Verify baseline structure for one operation
        baseline = data["baselines"]["codegen_validation"]
        TestHelpers.assert_baseline_structure(baseline)

        # Verify counts
        assert data["total_operations"] == len(expected_operations)
        total_measurements = sum(
            len(durations)
            for durations in TestDataConstants.OPERATION_DURATIONS.values()
        )
        assert data["total_measurements"] == total_measurements

    def test_get_baselines_filtered(self, client):
        """Test GET /api/performance-analytics/baselines?operation=X"""
        response = client.get(
            "/api/performance-analytics/baselines?operation=codegen_validation"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify only requested operation returned
        assert len(data["baselines"]) == 1
        assert "codegen_validation" in data["baselines"]
        assert data["total_operations"] == 1

    def test_get_baselines_not_found(self, client):
        """Test GET /api/performance-analytics/baselines with non-existent operation"""
        response = client.get(
            "/api/performance-analytics/baselines?operation=nonexistent_operation"
        )

        assert response.status_code == 404
        assert "No baseline found" in response.json()["detail"]

    def test_get_operation_metrics(self, client):
        """Test GET /api/performance-analytics/operations/{operation}/metrics"""
        operation = "codegen_validation"
        response = client.get(
            f"/api/performance-analytics/operations/{operation}/metrics"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_operation_metrics_structure(data, operation)

        # Verify baseline data
        baseline = data["baseline"]
        TestHelpers.assert_baseline_structure(baseline)
        expected_sample_size = len(TestDataConstants.OPERATION_DURATIONS[operation])
        assert baseline["sample_size"] == expected_sample_size

        # Verify recent measurements
        assert len(data["recent_measurements"]) > 0
        assert (
            len(data["recent_measurements"])
            <= TestDataConstants.RECENT_MEASUREMENTS_LIMIT
        )

    def test_get_operation_metrics_not_found(self, client):
        """Test metrics endpoint with non-existent operation"""
        response = client.get(
            "/api/performance-analytics/operations/nonexistent/metrics"
        )

        assert response.status_code == 404
        assert "No baseline found" in response.json()["detail"]

    def test_get_optimization_opportunities(self, client):
        """Test GET /api/performance-analytics/optimization-opportunities"""
        response = client.get("/api/performance-analytics/optimization-opportunities")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "opportunities" in data
        assert "total_opportunities" in data
        assert "avg_roi" in data
        assert "total_potential_improvement" in data

        # Verify opportunities structure using helper
        if data["total_opportunities"] > 0:
            opportunity = data["opportunities"][0]
            TestHelpers.assert_optimization_opportunity_structure(opportunity)

    def test_get_optimization_opportunities_filtered(self, client):
        """Test optimization opportunities with filters"""
        response = client.get(
            "/api/performance-analytics/optimization-opportunities"
            "?min_roi=5.0&max_effort=medium"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all opportunities meet filter criteria
        for opportunity in data["opportunities"]:
            assert opportunity["roi_score"] >= 5.0
            assert opportunity["effort_level"] in ["low", "medium"]

    def test_check_performance_anomaly_normal(self, client):
        """Test POST anomaly check with normal duration"""
        operation = "codegen_validation"
        # Use a normal duration from our test data
        normal_duration = (
            TestDataConstants.OPERATION_DURATIONS[operation][0]
            * TestDataConstants.NORMAL_DURATION_MULTIPLIER
        )

        response = client.post(
            f"/api/performance-analytics/operations/{operation}/anomaly-check",
            json={"duration_ms": normal_duration},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_anomaly_response_structure(data)

        # Normal duration should not be anomaly
        assert data["anomaly_detected"] is False
        assert data["severity"] == "normal"
        assert data["current_duration_ms"] == normal_duration

    def test_check_performance_anomaly_detected(self, client):
        """Test POST anomaly check with anomalous duration"""
        operation = "codegen_validation"
        # Use an anomalous duration (10x the baseline mean)
        baseline_mean = np.mean(TestDataConstants.OPERATION_DURATIONS[operation])
        anomaly_duration = baseline_mean * TestDataConstants.ANOMALY_DURATION_MULTIPLIER

        response = client.post(
            f"/api/performance-analytics/operations/{operation}/anomaly-check",
            json={"duration_ms": anomaly_duration},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_anomaly_response_structure(data)

        # Anomaly should be detected
        assert data["anomaly_detected"] is True
        assert data["severity"] in ["medium", "high", "critical"]
        assert abs(data["z_score"]) > TestDataConstants.ANOMALY_Z_SCORE_THRESHOLD

    def test_check_performance_anomaly_no_baseline(self, client):
        """Test anomaly check for operation without baseline"""
        response = client.post(
            "/api/performance-analytics/operations/nonexistent_operation/anomaly-check",
            json={"duration_ms": 500.0},
        )

        # Should still return response, not error
        assert response.status_code == 200
        data = response.json()
        assert data["anomaly_detected"] is False
        assert data["severity"] == "normal"

    def test_get_trends_24h(self, client):
        """Test GET /api/performance-analytics/trends?time_window=24h"""
        time_window = "24h"
        response = client.get(
            f"/api/performance-analytics/trends?time_window={time_window}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_trends_response_structure(data, time_window)

        # Verify operation trends
        for operation, trend_data in data["operations"].items():
            assert "trend" in trend_data
            assert "avg_duration_change" in trend_data
            assert "anomaly_count" in trend_data
            assert trend_data["trend"] in ["improving", "declining", "stable"]

    def test_get_trends_7d(self, client):
        """Test trends with 7d window"""
        time_window = "7d"
        response = client.get(
            f"/api/performance-analytics/trends?time_window={time_window}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_trends_response_structure(data, time_window)

    def test_health_check(self, client):
        """Test GET /api/performance-analytics/health"""
        response = client.get("/api/performance-analytics/health")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure using helper
        TestHelpers.assert_health_response_structure(data)

        # Verify counts are non-negative
        assert data["total_operations_tracked"] >= 0
        assert data["total_measurements"] >= 0
        assert data["uptime_seconds"] >= 0


class TestPerformanceAnalyticsEdgeCases:
    """Test edge cases and error handling"""

    def test_invalid_time_window(self, client):
        """Test trends with invalid time window"""
        response = client.get("/api/performance-analytics/trends?time_window=invalid")

        # Should use default (24h) instead of failing
        assert response.status_code == 200
        data = response.json()
        assert data["time_window"] == "invalid"  # Returns what was requested

    def test_anomaly_check_invalid_duration(self, client):
        """Test anomaly check with invalid duration"""
        response = client.post(
            "/api/performance-analytics/operations/codegen_validation/anomaly-check",
            json={"duration_ms": -100.0},  # Negative duration
        )

        # Should return validation error
        assert response.status_code == 422  # Validation error

    def test_baselines_empty_service(self):
        """Test baselines with empty service"""
        from api.performance_analytics.routes import initialize_services, router
        from fastapi import FastAPI

        # Create empty service
        empty_service = PerformanceBaselineService(
            max_measurements=TestDataConstants.MAX_MEASUREMENTS
        )
        initialize_services(empty_service)

        # Create a minimal test FastAPI app
        test_app = FastAPI(title="Test App")
        test_app.include_router(router)

        client = TestClient(test_app)
        response = client.get("/api/performance-analytics/baselines")

        assert response.status_code == 200
        data = response.json()

        # Verify empty response structure
        TestHelpers.assert_baselines_response_structure(data)
        assert len(data["baselines"]) == 0
        assert data["total_operations"] == 0
        assert data["total_measurements"] == 0


class TestPerformanceAnalyticsIntegration:
    """Integration tests with realistic scenarios"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, baseline_service):
        """Test complete workflow: record -> baseline -> analyze -> optimize"""
        service = baseline_service
        test_operation = "test_operation"
        num_measurements = 10
        base_duration = 500.0
        duration_increment = 10.0

        # Step 1: Record additional measurements (at least 10 for baseline)
        for i in range(num_measurements):
            duration = base_duration + i * duration_increment
            await service.record_measurement(test_operation, duration, {"iteration": i})

        # Step 2: Update baseline for the new operation
        await service._update_baseline(test_operation)

        # Step 3: Get baseline and verify structure
        baseline = await service.get_baseline(test_operation)
        assert baseline is not None
        assert baseline["sample_size"] >= num_measurements
        TestHelpers.assert_baseline_structure(baseline)

        # Step 4: Detect anomaly with high duration
        baseline_mean = baseline["mean"]
        anomaly_duration = baseline_mean * TestDataConstants.ANOMALY_DURATION_MULTIPLIER
        anomaly_result = await service.detect_performance_anomaly(
            test_operation, anomaly_duration
        )
        assert anomaly_result["anomaly_detected"] is True

        # Step 5: Get recent measurements
        recent = service.get_recent_measurements(
            test_operation, limit=TestDataConstants.RECENT_MEASUREMENTS_LIMIT
        )
        assert len(recent) == num_measurements

    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        import concurrent.futures

        def make_request():
            return client.get("/api/performance-analytics/baselines")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
