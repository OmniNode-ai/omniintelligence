"""
Integration tests for Intelligence Metrics API - Quality Impact Endpoint

Tests the /api/intelligence/metrics/quality-impact endpoint end-to-end.
Correlation ID: 86e57c28-0af3-4f1f-afda-81d11b877258
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


class TestQualityImpactEndpoint:
    """Tests for GET /api/intelligence/metrics/quality-impact endpoint."""

    @pytest.mark.asyncio
    async def test_quality_impact_success_24h(self, test_client):
        """Test successful retrieval of quality impact metrics for 24h window."""
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=24h"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "improvements" in data
        assert "total_improvements" in data
        assert "avg_impact" in data
        assert "max_impact" in data
        assert "min_impact" in data
        assert "time_window" in data
        assert "generated_at" in data

        # Verify time_window
        assert data["time_window"] == "24h"

        # Verify statistics are numeric
        assert isinstance(data["avg_impact"], (int, float))
        assert isinstance(data["max_impact"], (int, float))
        assert isinstance(data["min_impact"], (int, float))

        # Verify improvements is a list
        assert isinstance(data["improvements"], list)
        assert data["total_improvements"] == len(data["improvements"])

    @pytest.mark.asyncio
    async def test_quality_impact_different_time_windows(self, test_client):
        """Test quality impact with different time windows."""
        time_windows = ["1h", "24h", "7d", "30d"]

        for window in time_windows:
            response = await test_client.get(
                f"/api/intelligence/metrics/quality-impact?time_window={window}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["time_window"] == window

    @pytest.mark.asyncio
    async def test_quality_impact_invalid_time_window(self, test_client):
        """Test quality impact with invalid time window."""
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=invalid"
        )

        # Should return 422 validation error for invalid time window
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_quality_impact_improvement_data_structure(self, test_client):
        """Test quality impact improvement data structure."""
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=7d"
        )

        assert response.status_code == 200
        data = response.json()

        # If there are improvements, verify their structure
        if data["improvements"]:
            improvement = data["improvements"][0]

            # Verify required fields
            assert "timestamp" in improvement
            assert "before_quality" in improvement
            assert "after_quality" in improvement
            assert "impact" in improvement

            # Verify data types and ranges
            assert isinstance(improvement["timestamp"], str)
            assert 0.0 <= improvement["before_quality"] <= 1.0
            assert 0.0 <= improvement["after_quality"] <= 1.0
            assert isinstance(improvement["impact"], (int, float))

            # Verify optional fields
            if "pattern_applied" in improvement:
                assert isinstance(improvement["pattern_applied"], str)
            if "pattern_id" in improvement:
                assert isinstance(improvement["pattern_id"], str)
            if "confidence" in improvement:
                assert 0.0 <= improvement["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_quality_impact_empty_result(self, test_client):
        """Test quality impact when no data is available."""
        # Query for 1h window which is likely to have no data in test environment
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=1h"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty improvements list
        assert data["improvements"] == []
        assert data["total_improvements"] == 0
        assert data["avg_impact"] == 0.0
        assert data["max_impact"] == 0.0
        assert data["min_impact"] == 0.0

    @pytest.mark.asyncio
    async def test_quality_impact_statistics_consistency(self, test_client):
        """Test that quality impact statistics are consistent with data."""
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=30d"
        )

        assert response.status_code == 200
        data = response.json()

        if data["improvements"]:
            impacts = [imp["impact"] for imp in data["improvements"]]

            # Verify max_impact is actually the maximum
            assert data["max_impact"] >= max(impacts) - 0.0001  # Account for rounding

            # Verify min_impact is actually the minimum
            assert data["min_impact"] <= min(impacts) + 0.0001  # Account for rounding

            # Verify avg_impact is reasonable
            calculated_avg = sum(impacts) / len(impacts)
            assert (
                abs(data["avg_impact"] - calculated_avg) < 0.0001
            )  # Account for rounding

    @pytest.mark.asyncio
    async def test_quality_impact_timestamp_ordering(self, test_client):
        """Test that quality impacts are ordered by timestamp descending."""
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=30d"
        )

        assert response.status_code == 200
        data = response.json()

        if len(data["improvements"]) > 1:
            timestamps = [
                datetime.fromisoformat(imp["timestamp"].replace("Z", "+00:00"))
                for imp in data["improvements"]
            ]

            # Verify descending order
            for i in range(len(timestamps) - 1):
                assert timestamps[i] >= timestamps[i + 1], (
                    f"Timestamps not in descending order: "
                    f"{timestamps[i]} should be >= {timestamps[i + 1]}"
                )

    @pytest.mark.asyncio
    async def test_quality_impact_generated_at_timestamp(self, test_client):
        """Test that generated_at timestamp is recent and valid."""
        before_request = datetime.now(timezone.utc)
        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=24h"
        )
        after_request = datetime.now(timezone.utc)

        assert response.status_code == 200
        data = response.json()

        # Parse generated_at timestamp
        generated_at = datetime.fromisoformat(
            data["generated_at"].replace("Z", "+00:00")
        )

        # Verify it's within the request time window (with 1 second buffer)
        assert (
            before_request - timedelta(seconds=1)
            <= generated_at
            <= after_request + timedelta(seconds=1)
        )


class TestQualityImpactHealthEndpoint:
    """Tests for GET /api/intelligence/metrics/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, test_client):
        """Test health check endpoint returns success."""
        response = await test_client.get("/api/intelligence/metrics/health")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "status" in data
        assert "service" in data
        assert "database_pool_initialized" in data

        # Verify service name
        assert data["service"] == "intelligence-metrics-api"

        # Verify database pool status
        assert isinstance(data["database_pool_initialized"], bool)


class TestQualityImpactDatabaseIntegration:
    """Tests for database integration of quality impact endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Skip by default, enable when database is available
        reason="Requires database with pattern_quality_metrics table",
    )
    async def test_quality_impact_with_real_data(self, test_client):
        """Test quality impact with real database data."""
        # This test requires the database to be populated with test data
        # Enable this test when running against a test database with sample data

        response = await test_client.get(
            "/api/intelligence/metrics/quality-impact?time_window=7d"
        )

        assert response.status_code == 200
        data = response.json()

        # If database has data, verify structure
        if data["total_improvements"] > 0:
            assert len(data["improvements"]) > 0
            assert data["avg_impact"] != 0.0

            # Verify impact calculation
            for improvement in data["improvements"]:
                expected_impact = (
                    improvement["after_quality"] - improvement["before_quality"]
                )
                assert abs(improvement["impact"] - expected_impact) < 0.0001
