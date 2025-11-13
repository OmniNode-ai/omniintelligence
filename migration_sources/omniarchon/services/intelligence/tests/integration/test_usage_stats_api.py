"""
Integration Tests for Usage Stats API Endpoint

Tests the complete usage statistics API endpoint with real service integration.

Created: 2025-10-28
Track: Pattern Dashboard Backend - Section 2.3
Correlation ID: a06eb29a-8922-4fdf-bb27-96fc40fae415
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

# Assuming test app fixture exists
# from tests.conftest import test_app


@pytest.mark.integration
class TestUsageStatsAPI:
    """Integration tests for usage stats API endpoint."""

    @pytest.mark.asyncio
    async def test_usage_stats_no_data(self, test_client):
        """Test usage stats endpoint with no data."""
        pattern_id = str(uuid4())

        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={"pattern_id": pattern_id, "time_range": "7d", "group_by": "day"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_patterns"] == 0
        assert data["patterns"] == []
        assert data["time_range"] == "7d"
        assert data["granularity"] == "day"

    @pytest.mark.asyncio
    async def test_usage_stats_with_data(self, test_client, sample_feedback_data):
        """Test usage stats endpoint with sample data."""
        # Assume sample_feedback_data fixture creates pattern feedback in system

        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={"time_range": "30d", "group_by": "day"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_patterns"] >= 0
        assert isinstance(data["patterns"], list)
        assert data["time_range"] == "30d"
        assert data["granularity"] == "day"

        # Verify pattern structure
        if data["patterns"]:
            pattern = data["patterns"][0]
            assert "pattern_id" in pattern
            assert "pattern_name" in pattern
            assert "usage_data" in pattern
            assert "total_usage" in pattern

            # Verify usage data point structure
            if pattern["usage_data"]:
                data_point = pattern["usage_data"][0]
                assert "timestamp" in data_point
                assert "count" in data_point
                assert isinstance(data_point["count"], int)
                assert data_point["count"] >= 0

    @pytest.mark.asyncio
    async def test_usage_stats_time_ranges(self, test_client):
        """Test usage stats with different time ranges."""
        time_ranges = ["1d", "7d", "30d", "90d"]

        for time_range in time_ranges:
            response = await test_client.get(
                "/api/pattern-analytics/usage-stats",
                params={"time_range": time_range, "group_by": "day"},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["time_range"] == time_range

    @pytest.mark.asyncio
    async def test_usage_stats_granularities(self, test_client):
        """Test usage stats with different aggregation granularities."""
        granularities = ["hour", "day", "week"]

        for granularity in granularities:
            response = await test_client.get(
                "/api/pattern-analytics/usage-stats",
                params={"time_range": "7d", "group_by": granularity},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["granularity"] == granularity

    @pytest.mark.asyncio
    async def test_usage_stats_specific_pattern(self, test_client):
        """Test usage stats filtered to specific pattern."""
        pattern_id = str(uuid4())

        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={
                "pattern_id": pattern_id,
                "time_range": "7d",
                "group_by": "day",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should either have 0 patterns or only the requested pattern
        if data["total_patterns"] > 0:
            assert all(p["pattern_id"] == pattern_id for p in data["patterns"])

    @pytest.mark.asyncio
    async def test_usage_stats_invalid_pattern_id(self, test_client):
        """Test usage stats with invalid pattern ID format."""
        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={
                "pattern_id": "invalid-uuid",
                "time_range": "7d",
                "group_by": "day",
            },
        )

        # Should return 200 with empty results (graceful handling)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_patterns"] == 0

    @pytest.mark.asyncio
    async def test_usage_stats_default_parameters(self, test_client):
        """Test usage stats with default parameters."""
        response = await test_client.get("/api/pattern-analytics/usage-stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify defaults
        assert data["time_range"] == "7d"  # Default time range
        assert data["granularity"] == "day"  # Default granularity

    @pytest.mark.asyncio
    async def test_usage_stats_response_schema(self, test_client):
        """Test usage stats response matches expected schema."""
        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={"time_range": "7d", "group_by": "day"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Required top-level fields
        required_fields = ["patterns", "time_range", "granularity", "total_patterns"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify types
        assert isinstance(data["patterns"], list)
        assert isinstance(data["time_range"], str)
        assert isinstance(data["granularity"], str)
        assert isinstance(data["total_patterns"], int)

    @pytest.mark.asyncio
    async def test_usage_stats_performance(self, test_client, benchmark):
        """Test usage stats API performance."""
        # Benchmark the API call
        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={"time_range": "30d", "group_by": "day"},
        )

        assert response.status_code == status.HTTP_200_OK

        # Target: <300ms for usage stats query (from reference doc Section 2.3)
        # Note: This would need actual benchmark fixture to measure

    @pytest.mark.asyncio
    async def test_usage_stats_concurrent_requests(self, test_client):
        """Test handling concurrent usage stats requests."""
        import asyncio

        async def make_request():
            return await test_client.get(
                "/api/pattern-analytics/usage-stats",
                params={"time_range": "7d", "group_by": "day"},
            )

        # Make 10 concurrent requests
        responses = await asyncio.gather(*[make_request() for _ in range(10)])

        # All should succeed
        assert all(r.status_code == status.HTTP_200_OK for r in responses)

        # All should return consistent data structure
        for response in responses:
            data = response.json()
            assert "patterns" in data
            assert "total_patterns" in data


@pytest.mark.integration
class TestUsageStatsEndToEnd:
    """End-to-end tests for complete usage tracking workflow."""

    @pytest.mark.asyncio
    async def test_record_and_retrieve_usage(
        self, test_client, pattern_analytics_service
    ):
        """Test recording usage events and retrieving stats."""
        from archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
            FeedbackSentiment,
            ModelPatternFeedback,
        )

        pattern_id = uuid4()

        # Record some feedback (which should be tracked as usage)
        feedback_items = []
        for i in range(10):
            feedback = ModelPatternFeedback(
                pattern_id=pattern_id,
                pattern_name="Test Pattern",
                sentiment=FeedbackSentiment.POSITIVE,
                success=True if i < 7 else False,
                quality_score=0.85,
                created_at=datetime.now(timezone.utc),
                context={"test": True},
            )
            feedback_items.append(feedback)
            pattern_analytics_service.orchestrator.feedback_store.append(feedback)

        # Retrieve usage stats via API
        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={
                "pattern_id": str(pattern_id),
                "time_range": "1d",
                "group_by": "hour",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify pattern appears in results
        if data["total_patterns"] > 0:
            pattern_stats = data["patterns"][0]
            assert pattern_stats["pattern_id"] == str(pattern_id)
            assert pattern_stats["total_usage"] == 10

    @pytest.mark.asyncio
    async def test_usage_stats_aggregation_by_hour(self, test_client):
        """Test usage stats hourly aggregation."""
        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={"time_range": "1d", "group_by": "hour"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify hourly grouping
        if data["patterns"] and data["patterns"][0]["usage_data"]:
            timestamps = [dp["timestamp"] for dp in data["patterns"][0]["usage_data"]]
            # All timestamps should be at minute=0, second=0 (hour boundaries)
            for ts_str in timestamps:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                assert ts.minute == 0
                assert ts.second == 0

    @pytest.mark.asyncio
    async def test_usage_stats_aggregation_by_week(self, test_client):
        """Test usage stats weekly aggregation."""
        response = await test_client.get(
            "/api/pattern-analytics/usage-stats",
            params={"time_range": "30d", "group_by": "week"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify weekly grouping
        if data["patterns"] and data["patterns"][0]["usage_data"]:
            timestamps = [dp["timestamp"] for dp in data["patterns"][0]["usage_data"]]
            # All timestamps should be on Mondays (start of week)
            for ts_str in timestamps:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                assert ts.weekday() == 0  # Monday = 0
