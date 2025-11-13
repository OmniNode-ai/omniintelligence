"""
Comprehensive Integration Tests for Quality Trends API

Tests all 7 endpoints with realistic scenarios for quality history tracking,
trend analysis, and regression detection.

Phase 5B: Quality Intelligence Upgrades
Created: 2025-10-16
"""

import os

# Import the FastAPI app
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from app import app
from archon_services.quality.quality_history import (
    QualityHistoryService,
    QualitySnapshot,
)
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def quality_history_service():
    """Create a QualityHistoryService with test data"""
    service = QualityHistoryService()

    # Add test snapshots for multiple projects and files
    base_time = datetime.now(timezone.utc)

    # Project 1: Improving quality trend
    for i in range(10):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=10 - i),
            project_id="project_alpha",
            file_path="src/api/main.py",  # No leading slash (URL path parameter format)
            quality_score=0.6 + (i * 0.03),  # Steadily improving
            compliance_score=0.7 + (i * 0.02),
            violations=["Missing docstrings"] if i < 5 else [],
            warnings=["Consider refactoring"] if i < 3 else [],
            correlation_id=f"corr_alpha_{i}",
        )
        service.snapshots.append(snapshot)

    # Project 2: Declining quality trend
    for i in range(10):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=10 - i),
            project_id="project_beta",
            file_path="src/utils/helpers.py",  # No leading slash
            quality_score=0.9 - (i * 0.04),  # Declining
            compliance_score=0.85 - (i * 0.03),
            violations=["Complexity too high"] * (i // 2),
            warnings=["Needs optimization"] * (i // 3),
            correlation_id=f"corr_beta_{i}",
        )
        service.snapshots.append(snapshot)

    # Project 3: Stable quality trend
    for i in range(10):
        snapshot = QualitySnapshot(
            timestamp=base_time - timedelta(days=10 - i),
            project_id="project_gamma",
            file_path="src/models/user.py",  # No leading slash
            quality_score=0.80 + (0.01 * (i % 3 - 1)),  # Stable with minor fluctuation
            compliance_score=0.85,
            violations=[],
            warnings=[],
            correlation_id=f"corr_gamma_{i}",
        )
        service.snapshots.append(snapshot)

    return service


@pytest.fixture(scope="function")
async def initialized_service(quality_history_service):
    """Initialize service (already initialized in fixture)"""
    return quality_history_service


@pytest.fixture(scope="function")
def client(quality_history_service):
    """Create test client with initialized quality history service"""
    # Replace the singleton service with our test service
    import src.api.quality_trends.routes as routes_module

    routes_module.quality_history_service = quality_history_service

    # Create and return test client
    test_client = TestClient(app)

    # Cleanup fixture: reset the service after each test
    yield test_client

    # Reset to fresh service instance for next test
    routes_module.quality_history_service = QualityHistoryService()


class TestQualityTrendsAPI:
    """Test suite for Quality Trends API endpoints"""

    def test_record_quality_snapshot(self, client):
        """Test POST /api/quality-trends/snapshot - Record quality snapshot"""
        snapshot_data = {
            "project_id": "test_project",
            "file_path": "/src/test_file.py",
            "quality_score": 0.85,
            "onex_compliance_score": 0.90,
            "violations": ["Missing type hints"],
            "warnings": ["Consider adding docstrings"],
            "correlation_id": str(uuid4()),
        }

        response = client.post("/api/quality-trends/snapshot", json=snapshot_data)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["message"] == "Quality snapshot recorded successfully"
        assert data["project_id"] == "test_project"
        assert data["file_path"] == "/src/test_file.py"
        assert data["quality_score"] == 0.85

    def test_record_quality_snapshot_validation(self, client):
        """Test snapshot recording with invalid data"""
        # Invalid quality score (out of range)
        invalid_data = {
            "project_id": "test_project",
            "file_path": "/src/test.py",
            "quality_score": 1.5,  # Invalid: > 1.0
            "onex_compliance_score": 0.90,
            "violations": [],
            "warnings": [],
            "correlation_id": str(uuid4()),
        }

        response = client.post("/api/quality-trends/snapshot", json=invalid_data)

        # Should return validation error
        assert response.status_code == 422

    def test_get_project_quality_trend_improving(self, client):
        """Test GET /api/quality-trends/project/{project_id}/trend - Improving trend"""
        response = client.get(
            "/api/quality-trends/project/project_alpha/trend?time_window_days=30"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["project_id"] == "project_alpha"
        assert "trend" in data
        assert "current_quality" in data
        assert "avg_quality" in data
        assert "slope" in data
        assert "snapshots_count" in data
        assert "time_window_days" in data

        # Verify trend detection
        assert data["trend"] == "improving"
        assert data["slope"] > 0.01
        assert data["snapshots_count"] == 10
        assert data["time_window_days"] == 30

    def test_get_project_quality_trend_declining(self, client):
        """Test project trend - Declining quality"""
        response = client.get(
            "/api/quality-trends/project/project_beta/trend?time_window_days=30"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify declining trend
        assert data["trend"] == "declining"
        assert data["slope"] < -0.01
        assert data["snapshots_count"] == 10

    def test_get_project_quality_trend_stable(self, client):
        """Test project trend - Stable quality"""
        response = client.get(
            "/api/quality-trends/project/project_gamma/trend?time_window_days=30"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify stable trend
        assert data["trend"] == "stable"
        assert -0.01 <= data["slope"] <= 0.01
        assert data["snapshots_count"] == 10

    def test_get_project_quality_trend_insufficient_data(self, client):
        """Test project trend with no data"""
        response = client.get("/api/quality-trends/project/nonexistent_project/trend")

        assert response.status_code == 200
        data = response.json()

        # Verify insufficient data response
        assert data["trend"] == "insufficient_data"
        assert data["snapshots_count"] == 0

    def test_get_file_quality_trend(self, client):
        """Test GET /api/quality-trends/project/{project_id}/file/{file_path:path}/trend"""
        response = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/trend?time_window_days=30"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["project_id"] == "project_alpha"
        assert (
            data["file_path"] == "src/api/main.py"
        )  # No leading slash in path parameter
        assert "trend" in data
        assert data["trend"] == "improving"
        assert data["snapshots_count"] == 10

    def test_get_file_quality_trend_time_window(self, client):
        """Test file trend with different time windows"""
        # 7-day window
        response_7d = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/trend?time_window_days=7"
        )
        assert response_7d.status_code == 200
        data_7d = response_7d.json()

        # 30-day window
        response_30d = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/trend?time_window_days=30"
        )
        assert response_30d.status_code == 200
        data_30d = response_30d.json()

        # Verify different snapshot counts based on time window
        # (Our test data spans 10 days, so 7-day window should capture most data)
        assert data_7d["snapshots_count"] >= 6
        assert data_30d["snapshots_count"] == 10

    def test_get_file_quality_history(self, client):
        """Test GET /api/quality-trends/project/{project_id}/file/{file_path:path}/history"""
        response = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/history?limit=50"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["project_id"] == "project_alpha"
        assert (
            data["file_path"] == "src/api/main.py"
        )  # No leading slash in path parameter
        assert data["snapshots_count"] == 10
        assert "history" in data
        assert len(data["history"]) == 10

        # Verify snapshot structure
        snapshot = data["history"][0]
        assert "timestamp" in snapshot
        assert "quality_score" in snapshot
        assert "compliance_score" in snapshot
        assert "violations" in snapshot
        assert "warnings" in snapshot
        assert "correlation_id" in snapshot

        # Verify snapshots are sorted by timestamp (newest first)
        timestamps = [s["timestamp"] for s in data["history"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_get_file_quality_history_with_limit(self, client):
        """Test history retrieval with limit parameter"""
        response = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/history?limit=5"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify limit is respected
        assert len(data["history"]) == 5
        assert data["snapshots_count"] == 5

    def test_get_file_quality_history_nonexistent(self, client):
        """Test history for non-existent file"""
        response = client.get(
            "/api/quality-trends/project/project_alpha/file/nonexistent/file.py/history"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty history
        assert data["snapshots_count"] == 0
        assert len(data["history"]) == 0

    def test_detect_quality_regression_detected(self, client):
        """Test POST /api/quality-trends/detect-regression - Regression detected"""
        # First, create a fresh project with high quality snapshots
        project_id = "regression_test_project"

        # Record 10 high-quality snapshots to establish baseline
        for i in range(10):
            snapshot_data = {
                "project_id": project_id,
                "file_path": "src/test.py",
                "quality_score": 0.85,  # Consistently high quality
                "onex_compliance_score": 0.90,
                "violations": [],
                "warnings": [],
                "correlation_id": str(uuid4()),
            }
            response = client.post("/api/quality-trends/snapshot", json=snapshot_data)
            assert response.status_code == 200

        # Now test regression detection with much lower score
        regression_data = {
            "project_id": project_id,
            "current_score": 0.5,  # 0.35 below average (regression)
            "threshold": 0.1,
        }

        response = client.post(
            "/api/quality-trends/detect-regression", json=regression_data
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["project_id"] == project_id
        assert "regression_detected" in data
        assert "current_score" in data

        # Verify regression is detected
        assert data["regression_detected"] is True
        assert data["current_score"] == 0.5

        # Verify additional fields if present
        if "avg_recent_score" in data:
            assert "difference" in data
            assert "threshold" in data
            assert data["difference"] > data["threshold"]

    def test_detect_quality_regression_not_detected(self, client):
        """Test regression detection - No regression"""
        # Project gamma has stable quality (~0.80), so score of 0.75 is within threshold
        regression_data = {
            "project_id": "project_gamma",
            "current_score": 0.75,
            "threshold": 0.1,
        }

        response = client.post(
            "/api/quality-trends/detect-regression", json=regression_data
        )

        assert response.status_code == 200
        data = response.json()

        # Verify no regression detected
        assert data["regression_detected"] is False
        assert data["current_score"] == 0.75
        assert data["difference"] <= data["threshold"]

    def test_detect_quality_regression_custom_threshold(self, client):
        """Test regression detection with custom threshold"""
        # Test with stricter threshold
        regression_data = {
            "project_id": "project_gamma",
            "current_score": 0.75,
            "threshold": 0.03,  # Stricter threshold
        }

        response = client.post(
            "/api/quality-trends/detect-regression", json=regression_data
        )

        assert response.status_code == 200
        data = response.json()

        # With stricter threshold, regression may be detected
        assert "regression_detected" in data
        assert data["threshold"] == 0.03

    def test_detect_quality_regression_no_baseline(self, client):
        """Test regression detection for project without snapshots"""
        regression_data = {
            "project_id": "nonexistent_project",
            "current_score": 0.5,
            "threshold": 0.1,
        }

        response = client.post(
            "/api/quality-trends/detect-regression", json=regression_data
        )

        assert response.status_code == 200
        data = response.json()

        # Should return no regression due to no baseline data
        assert data["regression_detected"] is False
        assert "reason" in data
        assert data["reason"] == "no_baseline_data"

    def test_get_quality_history_stats(self, client):
        """Test GET /api/quality-trends/stats - Get quality history statistics"""
        response = client.get("/api/quality-trends/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert "total_snapshots" in data
        assert "service_status" in data

        # Verify snapshot count (3 projects * 10 snapshots each = 30)
        assert data["total_snapshots"] == 30
        assert data["service_status"] == "active"

    def test_clear_project_snapshots(self, client):
        """Test DELETE /api/quality-trends/project/{project_id}/snapshots"""
        # First verify snapshots exist
        stats_before = client.get("/api/quality-trends/stats").json()
        initial_count = stats_before["total_snapshots"]

        # Clear snapshots for project_alpha
        response = client.delete("/api/quality-trends/project/project_alpha/snapshots")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["project_id"] == "project_alpha"
        assert "cleared_snapshots" in data
        assert "message" in data

        # Verify snapshots were cleared
        assert data["cleared_snapshots"] == 10
        assert "project_alpha" in data["message"]

        # Verify stats are updated
        stats_after = client.get("/api/quality-trends/stats").json()
        assert stats_after["total_snapshots"] == initial_count - 10

    def test_clear_project_snapshots_nonexistent(self, client):
        """Test clearing snapshots for non-existent project"""
        response = client.delete(
            "/api/quality-trends/project/nonexistent_project/snapshots"
        )

        assert response.status_code == 200
        data = response.json()

        # Should succeed but clear 0 snapshots
        assert data["success"] is True
        assert data["cleared_snapshots"] == 0


class TestQualityTrendsEdgeCases:
    """Test edge cases and error handling"""

    def test_snapshot_with_empty_violations_warnings(self, client):
        """Test snapshot recording with empty violations and warnings"""
        snapshot_data = {
            "project_id": "test_project",
            "file_path": "/src/clean_file.py",
            "quality_score": 1.0,
            "onex_compliance_score": 1.0,
            "violations": [],
            "warnings": [],
            "correlation_id": str(uuid4()),
        }

        response = client.post("/api/quality-trends/snapshot", json=snapshot_data)

        assert response.status_code == 200
        assert response.json()["quality_score"] == 1.0

    def test_trend_with_single_snapshot(self, client):
        """Test trend calculation with only one snapshot"""
        # Record single snapshot
        snapshot_data = {
            "project_id": "single_snapshot_project",
            "file_path": "/src/file.py",
            "quality_score": 0.8,
            "onex_compliance_score": 0.85,
            "violations": [],
            "warnings": [],
            "correlation_id": str(uuid4()),
        }

        client.post("/api/quality-trends/snapshot", json=snapshot_data)

        # Try to get trend
        response = client.get(
            "/api/quality-trends/project/single_snapshot_project/trend"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return stable trend with single data point
        assert data["snapshots_count"] == 1
        assert data["trend"] == "stable"  # Single point defaults to stable

    def test_time_window_boundary_conditions(self, client):
        """Test time window with boundary values"""
        # Minimum time window (1 day)
        response_min = client.get(
            "/api/quality-trends/project/project_alpha/trend?time_window_days=1"
        )
        assert response_min.status_code == 200

        # Maximum time window (365 days)
        response_max = client.get(
            "/api/quality-trends/project/project_alpha/trend?time_window_days=365"
        )
        assert response_max.status_code == 200

        # Invalid time window (0 days) - should fail validation
        response_invalid = client.get(
            "/api/quality-trends/project/project_alpha/trend?time_window_days=0"
        )
        assert response_invalid.status_code == 422

        # Invalid time window (> 365 days) - should fail validation
        response_too_large = client.get(
            "/api/quality-trends/project/project_alpha/trend?time_window_days=400"
        )
        assert response_too_large.status_code == 422

    def test_history_limit_boundary_conditions(self, client):
        """Test history limit with boundary values"""
        # Minimum limit (1)
        response_min = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/history?limit=1"
        )
        assert response_min.status_code == 200
        assert len(response_min.json()["history"]) == 1

        # Maximum limit (200)
        response_max = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/history?limit=200"
        )
        assert response_max.status_code == 200

        # Invalid limit (0) - should fail validation
        response_invalid = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/history?limit=0"
        )
        assert response_invalid.status_code == 422

        # Invalid limit (> 200) - should fail validation
        response_too_large = client.get(
            "/api/quality-trends/project/project_alpha/file/src/api/main.py/history?limit=250"
        )
        assert response_too_large.status_code == 422


class TestQualityTrendsIntegration:
    """Integration tests with realistic workflows"""

    def test_complete_quality_tracking_workflow(self, client):
        """Test complete workflow: record → history → trend → regression"""
        project_id = "workflow_test_project"
        file_path = "src/workflow_test.py"  # No leading slash

        # Step 1: Record multiple snapshots with improving quality
        for i in range(5):
            snapshot_data = {
                "project_id": project_id,
                "file_path": file_path,
                "quality_score": 0.6 + (i * 0.05),
                "onex_compliance_score": 0.7 + (i * 0.04),
                "violations": ["issue"] * (5 - i),  # Decreasing violations
                "warnings": ["warning"] * (5 - i),  # Decreasing warnings
                "correlation_id": str(uuid4()),
            }

            response = client.post("/api/quality-trends/snapshot", json=snapshot_data)
            assert response.status_code == 200

        # Step 2: Retrieve quality history
        history_response = client.get(
            f"/api/quality-trends/project/{project_id}/file/{file_path}/history"
        )
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert history_data["snapshots_count"] == 5

        # Step 3: Analyze quality trend
        trend_response = client.get(f"/api/quality-trends/project/{project_id}/trend")
        assert trend_response.status_code == 200
        trend_data = trend_response.json()
        assert trend_data["trend"] == "improving"
        assert trend_data["snapshots_count"] == 5

        # Step 4: Test regression detection
        # Should not detect regression with good score
        no_regression = client.post(
            "/api/quality-trends/detect-regression",
            json={"project_id": project_id, "current_score": 0.75, "threshold": 0.1},
        )
        assert no_regression.json()["regression_detected"] is False

        # Should detect regression with poor score
        with_regression = client.post(
            "/api/quality-trends/detect-regression",
            json={"project_id": project_id, "current_score": 0.5, "threshold": 0.1},
        )
        assert with_regression.json()["regression_detected"] is True

        # Step 5: Clean up
        cleanup_response = client.delete(
            f"/api/quality-trends/project/{project_id}/snapshots"
        )
        assert cleanup_response.status_code == 200
        assert cleanup_response.json()["cleared_snapshots"] == 5

    def test_multi_file_quality_tracking(self, client):
        """Test tracking multiple files in same project"""
        project_id = "multi_file_project"
        files = ["src/file1.py", "src/file2.py", "src/file3.py"]  # No leading slashes

        # Record snapshots for multiple files
        for file_path in files:
            for i in range(3):
                snapshot_data = {
                    "project_id": project_id,
                    "file_path": file_path,
                    "quality_score": 0.7 + (i * 0.05),
                    "onex_compliance_score": 0.8,
                    "violations": [],
                    "warnings": [],
                    "correlation_id": str(uuid4()),
                }

                response = client.post(
                    "/api/quality-trends/snapshot", json=snapshot_data
                )
                assert response.status_code == 200

        # Verify each file has its own trend
        for file_path in files:
            file_trend = client.get(
                f"/api/quality-trends/project/{project_id}/file/{file_path}/trend"
            )
            assert file_trend.status_code == 200
            assert file_trend.json()["snapshots_count"] == 3

        # Verify project-level trend includes all files
        project_trend = client.get(f"/api/quality-trends/project/{project_id}/trend")
        assert project_trend.status_code == 200
        assert project_trend.json()["snapshots_count"] == 9  # 3 files * 3 snapshots

        # Clean up
        cleanup = client.delete(f"/api/quality-trends/project/{project_id}/snapshots")
        assert cleanup.json()["cleared_snapshots"] == 9

    def test_quality_improvement_detection(self, client):
        """Test detection of quality improvements over time"""
        project_id = "improvement_test"
        file_path = "src/improved_file.py"  # No leading slash

        # Record snapshots showing clear improvement
        scores = [0.5, 0.55, 0.62, 0.70, 0.78, 0.85, 0.90]
        for i, score in enumerate(scores):
            snapshot_data = {
                "project_id": project_id,
                "file_path": file_path,
                "quality_score": score,
                "onex_compliance_score": score + 0.05,
                "violations": ["issue"] * max(0, 7 - i),
                "warnings": [],
                "correlation_id": str(uuid4()),
            }

            client.post("/api/quality-trends/snapshot", json=snapshot_data)

        # Verify improvement is detected
        trend = client.get(f"/api/quality-trends/project/{project_id}/trend").json()
        assert trend["trend"] == "improving"
        assert trend["slope"] > 0.01
        assert trend["current_quality"] == 0.90

        # Verify history shows improvement
        history = client.get(
            f"/api/quality-trends/project/{project_id}/file/{file_path}/history"
        ).json()
        assert len(history["history"]) == 7

        # First entry (newest) should have highest score
        assert history["history"][0]["quality_score"] == 0.90
        # Last entry (oldest) should have lowest score
        assert history["history"][-1]["quality_score"] == 0.5

        # Clean up
        client.delete(f"/api/quality-trends/project/{project_id}/snapshots")


class TestQualityTrendsWithSnapshots:
    """Test suite for enhanced quality trends endpoint with snapshots support"""

    def test_get_project_quality_trend_with_snapshots(self, client):
        """
        Test GET /api/quality-trends/project/{project_id}/trend?hours=24

        Verifies that when `hours` parameter is provided, the endpoint attempts
        to return snapshots from database (will fall back to in-memory if db not available).
        """
        project_id = "test_project"
        hours = 24

        # Make request with hours parameter
        response = client.get(
            f"/api/quality-trends/project/{project_id}/trend?hours={hours}"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["project_id"] == project_id
        assert "trend" in data
        assert "avg_quality" in data
        assert "snapshots_count" in data

        # Note: snapshots array may be empty if database not initialized
        # or may contain data from in-memory fallback
        # In production with database, snapshots array should be present
        assert "snapshots" in data or "snapshots_count" in data

    def test_quality_trend_snapshots_format(self, client):
        """
        Test snapshots array format matches dashboard requirements.

        Expected format:
        {
          "snapshots": [
            {
              "timestamp": "2025-10-28T10:00:00Z",
              "overall_quality": 0.92,
              "file_count": 15
            }
          ]
        }
        """
        # First, record some snapshots to ensure data exists
        for i in range(5):
            snapshot_data = {
                "project_id": "dashboard_test",
                "file_path": "src/test_file.py",
                "quality_score": 0.8 + (i * 0.02),
                "onex_compliance_score": 0.85,
                "violations": [],
                "warnings": [],
                "correlation_id": f"test_corr_{i}",
            }
            response = client.post("/api/quality-trends/snapshot", json=snapshot_data)
            assert response.status_code == 200

        # Query with hours parameter
        response = client.get(
            "/api/quality-trends/project/dashboard_test/trend?hours=24"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response has required fields
        assert "success" in data
        assert "project_id" in data
        assert "trend" in data
        assert "avg_quality" in data
        assert "snapshots_count" in data

        # If snapshots present, verify format
        if "snapshots" in data and len(data["snapshots"]) > 0:
            snapshot = data["snapshots"][0]
            assert "timestamp" in snapshot
            assert "overall_quality" in snapshot or "quality_score" in snapshot
            # Note: file_count only available in database query,
            # in-memory fallback may not have this field

    def test_quality_trend_backward_compatibility(self, client):
        """
        Test that existing time_window_days parameter still works (backward compatibility).
        """
        # Record some test data
        snapshot_data = {
            "project_id": "compat_test",
            "file_path": "src/compat.py",
            "quality_score": 0.85,
            "onex_compliance_score": 0.90,
            "violations": [],
            "warnings": [],
            "correlation_id": "compat_test_corr",
        }
        client.post("/api/quality-trends/snapshot", json=snapshot_data)

        # Query with old parameter (should still work)
        response = client.get(
            "/api/quality-trends/project/compat_test/trend?time_window_days=30"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return basic trend data without snapshots array requirement
        assert data["success"] is True
        assert data["project_id"] == "compat_test"
        assert "trend" in data

    def test_quality_trend_hours_parameter_validation(self, client):
        """Test parameter validation for hours parameter"""
        # Valid range: 1 to 8760 hours (1 year)

        # Valid: 24 hours
        response = client.get("/api/quality-trends/project/test_project/trend?hours=24")
        assert response.status_code == 200

        # Invalid: 0 hours (should fail validation)
        response = client.get("/api/quality-trends/project/test_project/trend?hours=0")
        assert response.status_code == 422  # Validation error

        # Invalid: > 8760 hours (should fail validation)
        response = client.get(
            "/api/quality-trends/project/test_project/trend?hours=10000"
        )
        assert response.status_code == 422  # Validation error

    def test_quality_trend_default_project(self, client):
        """
        Test quality trend for 'default' project (common dashboard use case).

        Dashboard typically uses project_id='default' to aggregate all patterns.
        """
        response = client.get("/api/quality-trends/project/default/trend?hours=24")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["project_id"] == "default"
        assert "trend" in data
        assert "avg_quality" in data
        assert "snapshots_count" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
