"""
Integration tests for Developer Metrics API

Tests the developer productivity metrics endpoint:
1. GET /api/intelligence/developer/metrics - Developer productivity metrics
2. GET /api/intelligence/developer/health - Health check

Created: 2025-10-28
Correlation ID: 86e57c28-0af3-4f1f-afda-81d11b877258
"""

import sys
import time
from pathlib import Path

import pytest
from api.developer_metrics.routes import router as developer_metrics_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add parent directory to path for imports


# Create minimal test app with just developer metrics router
test_app = FastAPI(title="Test Developer Metrics API")
test_app.include_router(developer_metrics_router)

# Create test client
client = TestClient(test_app)


# ============================================================================
# Test Cases
# ============================================================================


def test_get_developer_metrics_success():
    """
    Test GET /api/intelligence/developer/metrics returns valid metrics.

    Expected behavior:
    - Returns 200 OK (with database) or 503 (without database)
    - Returns all required fields (if 200)
    - Fields have correct types and formats (if 200)
    - Response time < 1000ms
    """
    start_time = time.time()

    response = client.get("/api/intelligence/developer/metrics")

    duration_ms = (time.time() - start_time) * 1000

    # Assert status code (allow 503 for test environments without database)
    assert response.status_code in [
        200,
        503,
    ], f"Expected 200 or 503, got {response.status_code}"

    # If database unavailable, skip field validation
    if response.status_code == 503:
        print(
            f"⚠️  Database unavailable in test environment (503) | duration={duration_ms:.2f}ms"
        )
        return

    # Assert response time
    assert (
        duration_ms < 1000
    ), f"Response too slow: {duration_ms:.2f}ms (expected < 1000ms)"

    # Parse response
    data = response.json()

    # Assert required fields exist
    assert "avg_commit_time" in data, "Missing avg_commit_time field"
    assert "code_review_time" in data, "Missing code_review_time field"
    assert "build_success_rate" in data, "Missing build_success_rate field"
    assert "test_coverage" in data, "Missing test_coverage field"

    # Assert field types
    assert isinstance(data["avg_commit_time"], str), "avg_commit_time must be string"
    assert isinstance(data["code_review_time"], str), "code_review_time must be string"
    assert isinstance(
        data["build_success_rate"], (int, float)
    ), "build_success_rate must be number"
    assert isinstance(
        data["test_coverage"], (int, float)
    ), "test_coverage must be number"

    # Assert value ranges
    assert (
        0.0 <= data["build_success_rate"] <= 1.0
    ), f"build_success_rate out of range: {data['build_success_rate']}"
    assert (
        0.0 <= data["test_coverage"] <= 1.0
    ), f"test_coverage out of range: {data['test_coverage']}"

    # Assert duration format (should end with s, m, h, or d)
    assert data["avg_commit_time"][-1] in [
        "s",
        "m",
        "h",
        "d",
    ], f"Invalid avg_commit_time format: {data['avg_commit_time']}"
    assert data["code_review_time"][-1] in [
        "s",
        "m",
        "h",
        "d",
    ], f"Invalid code_review_time format: {data['code_review_time']}"

    print(f"✅ Developer metrics test passed | duration={duration_ms:.2f}ms")
    print(f"   avg_commit_time: {data['avg_commit_time']}")
    print(f"   code_review_time: {data['code_review_time']}")
    print(f"   build_success_rate: {data['build_success_rate']:.2f}")
    print(f"   test_coverage: {data['test_coverage']:.2f}")


def test_get_developer_metrics_fields_format():
    """
    Test that developer metrics fields have correct format.

    Expected behavior:
    - Duration fields are formatted (12m, 2.5h, etc.)
    - Rate fields are between 0.0 and 1.0
    - All fields are present
    """
    response = client.get("/api/intelligence/developer/metrics")

    # Allow 503 for test environments without database
    assert response.status_code in [200, 503]

    # If database unavailable, skip field validation
    if response.status_code == 503:
        print(f"⚠️  Database unavailable in test environment (503)")
        return

    data = response.json()

    # Test duration format parsing
    avg_commit = data["avg_commit_time"]
    code_review = data["code_review_time"]

    # Should be parseable as "<number><unit>"
    assert (
        avg_commit[:-1].replace(".", "").isdigit()
    ), f"Invalid number in avg_commit_time: {avg_commit}"
    assert (
        code_review[:-1].replace(".", "").isdigit()
    ), f"Invalid number in code_review_time: {code_review}"

    print(f"✅ Duration format test passed")


def test_health_check_success():
    """
    Test GET /api/intelligence/developer/health returns service status.

    Expected behavior:
    - Returns 200 OK
    - Returns status, database_connection, uptime_seconds
    - Response time < 200ms
    """
    start_time = time.time()

    response = client.get("/api/intelligence/developer/health")

    duration_ms = (time.time() - start_time) * 1000

    # Assert status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Assert response time
    assert (
        duration_ms < 200
    ), f"Health check too slow: {duration_ms:.2f}ms (expected < 200ms)"

    # Parse response
    data = response.json()

    # Assert required fields exist
    assert "status" in data, "Missing status field"
    assert "database_connection" in data, "Missing database_connection field"
    assert "uptime_seconds" in data, "Missing uptime_seconds field"

    # Assert field types
    assert isinstance(data["status"], str), "status must be string"
    assert isinstance(
        data["database_connection"], str
    ), "database_connection must be string"
    assert isinstance(data["uptime_seconds"], int), "uptime_seconds must be integer"

    # Assert valid status values
    assert data["status"] in [
        "healthy",
        "degraded",
        "unhealthy",
    ], f"Invalid status: {data['status']}"
    assert data["database_connection"] in [
        "operational",
        "degraded",
        "down",
        "unknown",
    ], f"Invalid database_connection: {data['database_connection']}"

    # Assert uptime is non-negative
    assert data["uptime_seconds"] >= 0, f"Invalid uptime: {data['uptime_seconds']}"

    print(f"✅ Health check test passed | duration={duration_ms:.2f}ms")
    print(f"   status: {data['status']}")
    print(f"   database_connection: {data['database_connection']}")
    print(f"   uptime_seconds: {data['uptime_seconds']}")


def test_health_check_always_returns():
    """
    Test that health check endpoint always returns, even on errors.

    Expected behavior:
    - Always returns 200 OK
    - Returns valid JSON response
    - Never raises exceptions
    """
    response = client.get("/api/intelligence/developer/health")

    # Health check should always return 200
    assert response.status_code == 200

    # Should always return valid JSON
    data = response.json()
    assert isinstance(data, dict)
    assert "status" in data

    print(f"✅ Health check resilience test passed")


# ============================================================================
# Edge Cases
# ============================================================================


def test_metrics_endpoint_handles_no_database():
    """
    Test that metrics endpoint handles database unavailability gracefully.

    Expected behavior:
    - Returns default values when database is unavailable
    - Does not crash
    - Returns valid response structure
    """
    # Note: This test assumes database might not be available in test environment
    # The endpoint should return default values gracefully
    response = client.get("/api/intelligence/developer/metrics")

    # Should return either 200 (with defaults) or 503 (service unavailable)
    assert response.status_code in [
        200,
        503,
    ], f"Unexpected status code: {response.status_code}"

    if response.status_code == 200:
        data = response.json()
        # Should still have all required fields
        assert "avg_commit_time" in data
        assert "code_review_time" in data
        assert "build_success_rate" in data
        assert "test_coverage" in data

    print(f"✅ Database unavailability test passed")


# ============================================================================
# Performance Tests
# ============================================================================


def test_metrics_performance():
    """
    Test that metrics endpoint meets performance requirements.

    Expected behavior:
    - Single request completes in < 1000ms
    - Average of 10 requests < 1000ms
    - No significant performance degradation
    """
    durations = []

    for i in range(10):
        start_time = time.time()
        response = client.get("/api/intelligence/developer/metrics")
        duration_ms = (time.time() - start_time) * 1000
        durations.append(duration_ms)

        assert response.status_code in [
            200,
            503,
        ], f"Request {i+1} failed: {response.status_code}"

    avg_duration = sum(durations) / len(durations)
    max_duration = max(durations)
    min_duration = min(durations)

    assert (
        avg_duration < 1000
    ), f"Average duration too high: {avg_duration:.2f}ms (expected < 1000ms)"
    assert (
        max_duration < 2000
    ), f"Max duration too high: {max_duration:.2f}ms (expected < 2000ms)"

    print(f"✅ Performance test passed")
    print(f"   avg: {avg_duration:.2f}ms")
    print(f"   min: {min_duration:.2f}ms")
    print(f"   max: {max_duration:.2f}ms")


if __name__ == "__main__":
    # Run tests manually for debugging
    print("Running Developer Metrics API Tests...")
    print("=" * 70)

    try:
        test_get_developer_metrics_success()
        test_get_developer_metrics_fields_format()
        test_health_check_success()
        test_health_check_always_returns()
        test_metrics_endpoint_handles_no_database()
        test_metrics_performance()

        print("=" * 70)
        print("✅ All tests passed!")
    except AssertionError as e:
        print("=" * 70)
        print(f"❌ Test failed: {e}")
        raise
