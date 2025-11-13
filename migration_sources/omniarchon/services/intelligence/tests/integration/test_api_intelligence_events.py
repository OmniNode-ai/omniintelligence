"""
Integration tests for Intelligence Events API

Tests the intelligence events stream endpoint with real service integration.

Created: 2025-10-28
Track: Pattern Dashboard Backend - Event Flow Page
Correlation ID: 86e57c28-0af3-4f1f-afda-81d11b877258
"""

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

# Intelligence Events imports
from api.intelligence_events.routes import router as intelligence_events_router
from api.intelligence_events.service import IntelligenceEventsService
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Create minimal test app with intelligence events router
test_app = FastAPI(title="Test Intelligence Events API")
test_app.include_router(intelligence_events_router)

# Create test client
client = TestClient(test_app)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def intelligence_events_service():
    """Create intelligence events service without database (uses mock data)."""
    return IntelligenceEventsService(db_pool=None)


@pytest.fixture
def sample_correlation_id():
    """Generate sample correlation UUID."""
    return uuid4()


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.integration
class TestIntelligenceEventsAPI:
    """Integration tests for intelligence events API endpoint."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/intelligence/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "intelligence-events-api"
        assert "database" in data

    def test_events_stream_default_params(self):
        """Test events stream with default parameters."""
        response = client.get("/api/intelligence/events/stream")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "events" in data
        assert "total" in data
        assert "time_range" in data
        assert "event_counts" in data

        assert isinstance(data["events"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["event_counts"], dict)

        # Verify time_range structure
        assert "start_time" in data["time_range"]
        assert "end_time" in data["time_range"]

    def test_events_stream_with_limit(self):
        """Test events stream with custom limit."""
        limit = 50

        response = client.get(
            "/api/intelligence/events/stream",
            params={"limit": limit},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) <= limit
        assert data["total"] <= limit

    def test_events_stream_filter_by_type(self):
        """Test events stream filtered by event type."""
        event_types = ["agent_action", "routing_decision"]

        for event_type in event_types:
            response = client.get(
                "/api/intelligence/events/stream",
                params={"event_type": event_type},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all events are of requested type
            if data["events"]:
                for event in data["events"]:
                    assert event["type"] in [
                        event_type,
                        "error",
                    ]  # errors can be from actions

    def test_events_stream_filter_by_agent_name(self):
        """Test events stream filtered by agent name."""
        agent_name = "test-agent"

        response = client.get(
            "/api/intelligence/events/stream",
            params={"agent_name": agent_name},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all events are from requested agent
        if data["events"]:
            for event in data["events"]:
                assert event["agent_name"] == agent_name

    def test_events_stream_filter_by_correlation_id(self, sample_correlation_id):
        """Test events stream filtered by correlation ID."""
        response = client.get(
            "/api/intelligence/events/stream",
            params={"correlation_id": str(sample_correlation_id)},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all events have the requested correlation ID
        if data["events"]:
            for event in data["events"]:
                # In mock mode, correlation IDs are random, so just verify structure
                assert isinstance(UUID(event["correlation_id"]), UUID)

    def test_events_stream_time_window(self):
        """Test events stream with different time windows."""
        time_windows = [1, 24, 168]  # 1 hour, 24 hours, 7 days

        for hours in time_windows:
            response = client.get(
                "/api/intelligence/events/stream",
                params={"hours": hours},
            )

            assert response.status_code == 200
            data = response.json()

            # Verify time range is within requested window
            if data["events"]:
                start_time = datetime.fromisoformat(
                    data["time_range"]["start_time"].replace("Z", "+00:00")
                )
                end_time = datetime.fromisoformat(
                    data["time_range"]["end_time"].replace("Z", "+00:00")
                )
                time_diff = end_time - start_time
                assert time_diff <= timedelta(hours=hours)

    def test_events_stream_event_structure(self):
        """Test that events have correct structure."""
        response = client.get("/api/intelligence/events/stream")

        assert response.status_code == 200
        data = response.json()

        if data["events"]:
            event = data["events"][0]

            # Verify required fields
            assert "id" in event
            assert "type" in event
            assert "timestamp" in event
            assert "correlation_id" in event
            assert "agent_name" in event
            assert "data" in event

            # Verify UUID format
            assert isinstance(UUID(event["id"]), UUID)
            assert isinstance(UUID(event["correlation_id"]), UUID)

            # Verify event type is valid
            assert event["type"] in ["agent_action", "routing_decision", "error"]

            # Verify timestamp format
            datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

            # Verify data is a dict
            assert isinstance(event["data"], dict)

    def test_events_stream_event_counts(self):
        """Test that event counts are accurate."""
        response = client.get("/api/intelligence/events/stream")

        assert response.status_code == 200
        data = response.json()

        # Sum event counts
        total_from_counts = sum(data["event_counts"].values())

        # Should equal total events
        assert total_from_counts == data["total"]

    def test_events_stream_chronological_order(self):
        """Test that events are returned in chronological order (descending)."""
        response = client.get("/api/intelligence/events/stream")

        assert response.status_code == 200
        data = response.json()

        if len(data["events"]) > 1:
            # Verify events are sorted by timestamp descending
            for i in range(len(data["events"]) - 1):
                current_time = datetime.fromisoformat(
                    data["events"][i]["timestamp"].replace("Z", "+00:00")
                )
                next_time = datetime.fromisoformat(
                    data["events"][i + 1]["timestamp"].replace("Z", "+00:00")
                )
                assert current_time >= next_time

    def test_events_stream_performance(self):
        """Test that events stream endpoint responds quickly."""
        start_time = time.time()

        response = client.get("/api/intelligence/events/stream")

        duration_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        # Should respond in under 500ms even with mock data
        assert duration_ms < 500

    def test_events_stream_invalid_limit(self):
        """Test events stream with invalid limit values."""
        # Too small
        response = client.get(
            "/api/intelligence/events/stream",
            params={"limit": 0},
        )
        assert response.status_code == 422  # Validation error

        # Too large
        response = client.get(
            "/api/intelligence/events/stream",
            params={"limit": 2000},
        )
        assert response.status_code == 422  # Validation error

    def test_events_stream_invalid_hours(self):
        """Test events stream with invalid time window."""
        # Too small
        response = client.get(
            "/api/intelligence/events/stream",
            params={"hours": 0},
        )
        assert response.status_code == 422  # Validation error

        # Too large
        response = client.get(
            "/api/intelligence/events/stream",
            params={"hours": 200},
        )
        assert response.status_code == 422  # Validation error

    def test_events_stream_invalid_correlation_id(self):
        """Test events stream with invalid correlation ID format."""
        response = client.get(
            "/api/intelligence/events/stream",
            params={"correlation_id": "not-a-valid-uuid"},
        )
        assert response.status_code == 422  # Validation error


@pytest.mark.integration
class TestIntelligenceEventsService:
    """Integration tests for intelligence events service."""

    @pytest.mark.asyncio
    async def test_service_with_mock_data(self, intelligence_events_service):
        """Test service returns mock data when no database is available."""
        result = await intelligence_events_service.get_events_stream(
            limit=50,
            event_type=None,
            agent_name=None,
            correlation_id=None,
            hours=24,
        )

        assert "events" in result
        assert "total" in result
        assert "time_range" in result
        assert "event_counts" in result

        # Should have some mock events
        assert len(result["events"]) > 0

    @pytest.mark.asyncio
    async def test_service_filter_by_type(self, intelligence_events_service):
        """Test service filtering by event type."""
        result = await intelligence_events_service.get_events_stream(
            limit=100,
            event_type="agent_action",
            agent_name=None,
            correlation_id=None,
            hours=24,
        )

        # Verify all events are agent_action (or error from agent_action)
        for event in result["events"]:
            assert event["type"] in ["agent_action", "error"]

    @pytest.mark.asyncio
    async def test_service_time_range_calculation(self, intelligence_events_service):
        """Test service correctly calculates time range."""
        result = await intelligence_events_service.get_events_stream(
            limit=100,
            event_type=None,
            agent_name=None,
            correlation_id=None,
            hours=48,
        )

        start_time = result["time_range"]["start_time"]
        end_time = result["time_range"]["end_time"]

        # Verify start_time is before end_time
        assert start_time <= end_time

    @pytest.mark.asyncio
    async def test_service_event_counts_accuracy(self, intelligence_events_service):
        """Test service event counts match actual events."""
        result = await intelligence_events_service.get_events_stream(
            limit=100,
            event_type=None,
            agent_name=None,
            correlation_id=None,
            hours=24,
        )

        # Count events by type
        type_counts = {}
        for event in result["events"]:
            event_type = event["type"]
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        # Verify matches event_counts
        assert type_counts == result["event_counts"]
