"""
Integration tests for Pattern Dashboard API endpoints.

Tests all 7 new dashboard endpoints end-to-end.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    FeedbackSentiment,
    ModelPatternFeedback,
)


@pytest.fixture
def sample_feedback_data():
    """Create sample feedback data for testing."""
    feedback_items = []
    base_time = datetime.now(timezone.utc) - timedelta(days=7)

    for i in range(20):
        feedback = ModelPatternFeedback(
            feedback_id=uuid4(),
            pattern_id=uuid4(),
            pattern_name=f"test_pattern_{i % 5}",  # 5 different patterns
            execution_id=f"exec_{i}",
            sentiment=(
                FeedbackSentiment.POSITIVE if i % 3 != 0 else FeedbackSentiment.NEUTRAL
            ),
            success=i % 4 != 0,  # 75% success rate
            quality_score=0.7 + (i % 3) * 0.1,  # 0.7, 0.8, 0.9
            performance_score=0.8,
            implicit_signals={"execution_time_ms": 100 + i * 10},
            issues=[f"issue_{i}"] if i % 5 == 0 else [],
            context={
                "pattern_type": "architectural" if i % 2 == 0 else "quality",
                "description": f"Description for pattern {i}",
                "tags": [f"tag{i % 3}"],
            },
            created_at=base_time + timedelta(hours=i),
        )
        feedback_items.append(feedback)

    return feedback_items


@pytest.fixture(autouse=True)
def setup_test_data(sample_feedback_data, monkeypatch):
    """
    Setup test data in the feedback orchestrator.

    Uses monkeypatch to replace the service instance for the test duration.
    autouse=True means this runs for all tests in this module.
    """
    from api.pattern_analytics import routes
    from api.pattern_analytics.service import PatternAnalyticsService

    # Create a service instance with pre-populated feedback
    test_service = PatternAnalyticsService()
    test_service.orchestrator.feedback_store.extend(sample_feedback_data)

    print(
        f"\n[FIXTURE] Created test service with {len(test_service.orchestrator.feedback_store)} feedback items"
    )

    # Use monkeypatch to replace the module attribute
    # This persists for the entire test function
    monkeypatch.setattr(routes, "pattern_analytics_service", test_service)

    return test_service


class TestPatternStatsEndpoint:
    """Tests for GET /api/pattern-analytics/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_pattern_stats_success(self, client, setup_test_data):
        """Test successful retrieval of pattern statistics."""
        response = await client.get("/api/pattern-analytics/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "stats" in data
        assert "generated_at" in data

        # Verify stats fields
        stats = data["stats"]
        assert stats["total_patterns"] > 0
        assert stats["total_feedback"] > 0
        assert 0.0 <= stats["avg_success_rate"] <= 1.0
        assert 0.0 <= stats["avg_quality_score"] <= 1.0
        assert isinstance(stats["patterns_by_type"], dict)
        assert stats["recent_activity_count"] >= 0
        assert stats["high_confidence_patterns"] >= 0

    @pytest.mark.asyncio
    async def test_get_pattern_stats_empty_store(self, client):
        """Test pattern stats with empty feedback store."""
        response = await client.get("/api/pattern-analytics/stats")

        assert response.status_code == 200
        data = response.json()
        stats = data["stats"]
        assert stats["total_patterns"] == 0
        assert stats["total_feedback"] == 0


class TestDiscoveryRateEndpoint:
    """Tests for GET /api/pattern-analytics/discovery-rate endpoint."""

    @pytest.mark.asyncio
    async def test_get_discovery_rate_success(self, client, setup_test_data):
        """Test successful retrieval of discovery rate data."""
        response = await client.get(
            "/api/pattern-analytics/discovery-rate",
            params={"time_range": "7d", "granularity": "day"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "data_points" in data
        assert "time_range" in data
        assert "granularity" in data
        assert "total_discovered" in data

        assert data["time_range"] == "7d"
        assert data["granularity"] == "day"
        assert isinstance(data["data_points"], list)

    @pytest.mark.asyncio
    async def test_get_discovery_rate_different_granularities(
        self, client, setup_test_data
    ):
        """Test discovery rate with different time granularities."""
        for granularity in ["hour", "day", "week"]:
            response = await client.get(
                "/api/pattern-analytics/discovery-rate",
                params={"time_range": "7d", "granularity": granularity},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["granularity"] == granularity


class TestQualityTrendsEndpoint:
    """Tests for GET /api/pattern-analytics/quality-trends endpoint."""

    @pytest.mark.asyncio
    async def test_get_quality_trends_success(self, client, setup_test_data):
        """Test successful retrieval of quality trends."""
        response = await client.get(
            "/api/pattern-analytics/quality-trends", params={"time_range": "30d"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "trends" in data
        assert "time_range" in data
        assert "overall_trend" in data
        assert "trend_velocity" in data

        assert data["time_range"] == "30d"
        assert data["overall_trend"] in [
            "increasing",
            "decreasing",
            "stable",
            "insufficient_data",
        ]
        assert isinstance(data["trend_velocity"], (int, float))

    @pytest.mark.asyncio
    async def test_get_quality_trends_valid_time_ranges(self, client, setup_test_data):
        """Test quality trends with different time ranges."""
        for time_range in ["1d", "7d", "30d", "90d"]:
            response = await client.get(
                "/api/pattern-analytics/quality-trends",
                params={"time_range": time_range},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["time_range"] == time_range


class TestTopPerformingEndpoint:
    """Tests for GET /api/pattern-analytics/top-performing endpoint."""

    @pytest.mark.asyncio
    async def test_get_top_performing_success(self, client, setup_test_data):
        """Test successful retrieval of top performing patterns."""
        response = await client.get(
            "/api/pattern-analytics/top-performing",
            params={"criteria": "performance_score", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "patterns" in data
        assert "total_count" in data
        assert "criteria" in data

        assert data["criteria"] == "performance_score"
        assert isinstance(data["patterns"], list)
        assert len(data["patterns"]) <= 10

        # Verify each pattern has required fields
        if data["patterns"]:
            pattern = data["patterns"][0]
            assert "pattern_id" in pattern
            assert "pattern_name" in pattern
            assert "success_rate" in pattern
            assert "usage_count" in pattern
            assert "avg_quality" in pattern
            assert "performance_score" in pattern
            assert "rank" in pattern

    @pytest.mark.asyncio
    async def test_get_top_performing_different_criteria(self, client, setup_test_data):
        """Test top performing with different ranking criteria."""
        for criteria in ["success_rate", "usage", "quality", "performance_score"]:
            response = await client.get(
                "/api/pattern-analytics/top-performing",
                params={"criteria": criteria, "limit": 5},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["criteria"] == criteria


class TestPatternRelationshipsEndpoint:
    """Tests for GET /api/pattern-analytics/relationships endpoint."""

    @pytest.mark.asyncio
    async def test_get_pattern_relationships_success(self, client, setup_test_data):
        """Test successful retrieval of pattern relationships."""
        response = await client.get(
            "/api/pattern-analytics/relationships", params={"min_co_occurrence": 2}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "nodes" in data
        assert "relationships" in data
        assert "total_nodes" in data
        assert "total_edges" in data

        assert isinstance(data["nodes"], list)
        assert isinstance(data["relationships"], list)
        assert data["total_nodes"] >= 0
        assert data["total_edges"] >= 0

        # Verify node structure if any nodes exist
        if data["nodes"]:
            node = data["nodes"][0]
            assert "pattern_id" in node
            assert "pattern_name" in node
            assert "usage_count" in node
            assert "success_rate" in node
            assert "centrality" in node

        # Verify relationship structure if any exist
        if data["relationships"]:
            rel = data["relationships"][0]
            assert "source_pattern_id" in rel
            assert "target_pattern_id" in rel
            assert "relationship_type" in rel
            assert "strength" in rel
            assert "co_occurrence_count" in rel


class TestPatternSearchEndpoint:
    """Tests for GET /api/pattern-analytics/search endpoint."""

    @pytest.mark.asyncio
    async def test_search_patterns_success(self, client, setup_test_data):
        """Test successful pattern search."""
        response = await client.get(
            "/api/pattern-analytics/search",
            params={"query": "test", "search_type": "full_text", "limit": 20},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "results" in data
        assert "total_results" in data
        assert "query" in data
        assert "search_type" in data

        assert data["query"] == "test"
        assert data["search_type"] == "full_text"
        assert isinstance(data["results"], list)

        # Verify result structure if any results exist
        if data["results"]:
            result = data["results"][0]
            assert "pattern_id" in result
            assert "pattern_name" in result
            assert "relevance_score" in result
            assert "success_rate" in result
            assert "usage_count" in result

    @pytest.mark.asyncio
    async def test_search_patterns_no_results(self, client, setup_test_data):
        """Test search with query that returns no results."""
        response = await client.get(
            "/api/pattern-analytics/search",
            params={"query": "nonexistent_pattern_xyz", "search_type": "full_text"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 0
        assert len(data["results"]) == 0


class TestInfrastructureHealthEndpoint:
    """Tests for GET /api/pattern-analytics/infrastructure-health endpoint."""

    @pytest.mark.asyncio
    async def test_get_infrastructure_health_success(self, client, setup_test_data):
        """Test successful retrieval of infrastructure health."""
        response = await client.get("/api/pattern-analytics/infrastructure-health")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "overall_status" in data
        assert "components" in data
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "avg_response_time_ms" in data
        assert "checked_at" in data

        assert data["overall_status"] in ["healthy", "degraded", "unhealthy"]
        assert isinstance(data["components"], list)
        assert data["uptime_seconds"] >= 0
        assert data["avg_response_time_ms"] >= 0

        # Verify component structure
        if data["components"]:
            component = data["components"][0]
            assert "name" in component
            assert "status" in component
            assert "last_check" in component
            assert component["status"] in ["healthy", "degraded", "unhealthy"]


class TestEndpointErrorHandling:
    """Tests for error handling across all endpoints."""

    @pytest.mark.asyncio
    async def test_discovery_rate_invalid_params(self, client):
        """Test discovery rate with invalid parameters."""
        response = await client.get(
            "/api/pattern-analytics/discovery-rate",
            params={"time_range": "invalid", "granularity": "invalid"},
        )

        # Should still return 200 with default values
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_top_performing_limit_bounds(self, client, setup_test_data):
        """Test top performing with various limit values."""
        # Test with limit=1
        response = await client.get(
            "/api/pattern-analytics/top-performing", params={"limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["patterns"]) <= 1

        # Test with limit=100 (max)
        response = await client.get(
            "/api/pattern-analytics/top-performing", params={"limit": 100}
        )
        assert response.status_code == 200
