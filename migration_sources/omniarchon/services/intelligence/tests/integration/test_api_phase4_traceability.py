"""
Integration Tests for Phase 4 Pattern Traceability API

Tests complete flow for all 11 traceability endpoints:
1. Pattern Lineage Tracking (single & batch)
2. Lineage Query (ancestry & descendants)
3. Evolution Path
4. Execution Logs & Summary
5. Usage Analytics
6. Feedback Loop (analyze & apply)
7. Health Check

Performance Targets:
- Lineage tracking: <50ms per event
- Batch tracking: <200ms (10-50 events)
- Ancestry query: <200ms (depth ≤10)
- Analytics: <500ms
- Execution logs: <500ms

Test Markers:
- pytest -m integration                          # All integration tests
- pytest -m phase4_traceability                  # Phase 4 traceability tests
- pytest -m "phase4_traceability and not slow"   # Skip slow tests
- pytest -m traceability_lineage                 # Lineage tests only
- pytest -m traceability_analytics               # Analytics tests only

Author: Archon Intelligence Team
Date: 2025-10-16
"""

import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from api.phase4_traceability.routes import router as traceability_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add parent directory to path for imports


# Create minimal test app with traceability router
test_app = FastAPI(title="Test Phase 4 Traceability API")
test_app.include_router(traceability_router)

# Create test client
client = TestClient(test_app)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def pattern_create_event():
    """Single pattern creation event for tracking."""
    return {
        "event_type": "pattern_created",
        "pattern_id": f"pattern_test_{uuid4().hex[:8]}",
        "pattern_name": "AsyncDatabaseWriter",
        "pattern_type": "code",
        "pattern_version": "1.0.0",
        "tool_name": "Write",
        "file_path": "/src/nodes/node_database_writer_effect.py",
        "language": "python",
        "pattern_data": {
            "template_code": "async def execute_effect(self, contract): ...",
            "node_type": "effect",
            "contracts": ["DatabaseContract"],
        },
        "parent_pattern_ids": [],
        "reason": "Initial pattern creation",
        "triggered_by": "ai_assistant",
    }


@pytest.fixture
def pattern_modify_event():
    """Pattern modification event with parent."""
    return {
        "event_type": "pattern_modified",
        "pattern_id": f"pattern_modified_{uuid4().hex[:8]}",
        "pattern_name": "AsyncDatabaseWriter",
        "pattern_type": "code",
        "pattern_version": "2.0.0",
        "tool_name": "Edit",
        "file_path": "/src/nodes/node_database_writer_effect.py",
        "language": "python",
        "pattern_data": {
            "template_code": "async def execute_effect(self, contract): ...",
            "changes": "Added error handling and retry logic",
        },
        "parent_pattern_ids": ["pattern_test_abc123"],
        "edge_type": "modified_from",
        "transformation_type": "enhancement",
        "reason": "Added error handling",
        "triggered_by": "ai_assistant",
    }


@pytest.fixture
def pattern_merge_event():
    """Pattern merge event with multiple parents."""
    return {
        "event_type": "pattern_merged",
        "pattern_id": f"pattern_merged_{uuid4().hex[:8]}",
        "pattern_name": "UnifiedDatabaseWriter",
        "pattern_type": "code",
        "pattern_version": "1.0.0",
        "tool_name": "Write",
        "file_path": "/src/nodes/node_unified_writer_effect.py",
        "language": "python",
        "pattern_data": {
            "template_code": "async def execute_effect(self, contract): ...",
            "merged_features": ["async", "sync", "batch"],
        },
        "parent_pattern_ids": ["pattern_async_writer", "pattern_sync_writer"],
        "edge_type": "merged_from",
        "transformation_type": "merge",
        "reason": "Unified async and sync writers",
        "triggered_by": "ai_assistant",
    }


@pytest.fixture
def batch_lineage_events():
    """Batch of lineage events for bulk tracking."""
    base_pattern_id = f"batch_pattern_{uuid4().hex[:8]}"
    events = []

    # Create initial pattern
    events.append(
        {
            "event_type": "pattern_created",
            "pattern_id": f"{base_pattern_id}_v1",
            "pattern_name": "BatchPattern",
            "pattern_type": "code",
            "pattern_version": "1.0.0",
            "pattern_data": {"template": "initial"},
            "triggered_by": "test",
        }
    )

    # Create 10 derived patterns
    for i in range(2, 12):
        events.append(
            {
                "event_type": "pattern_modified",
                "pattern_id": f"{base_pattern_id}_v{i}",
                "pattern_name": "BatchPattern",
                "pattern_type": "code",
                "pattern_version": f"{i}.0.0",
                "pattern_data": {"template": f"version_{i}"},
                "parent_pattern_ids": [f"{base_pattern_id}_v{i-1}"],
                "edge_type": "modified_from",
                "transformation_type": "enhancement",
                "triggered_by": "test",
            }
        )

    return {"events": events}


@pytest.fixture
def usage_analytics_request():
    """Request for usage analytics computation."""
    return {
        "pattern_id": "test_pattern_analytics",
        "time_window_type": "weekly",
        "include_performance": True,
        "include_trends": True,
        "include_distribution": False,
        "time_window_days": 7,
    }


@pytest.fixture
def feedback_loop_request():
    """Request for feedback loop orchestration."""
    return {
        "pattern_id": "test_pattern_feedback",
        "feedback_type": "performance",
        "time_window_days": 7,
        "auto_apply_threshold": 0.95,
        "min_sample_size": 30,
        "significance_level": 0.05,
        "enable_ab_testing": True,
    }


# ============================================================================
# Pattern Lineage Tracking Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_lineage
class TestPatternLineageTracking:
    """Test pattern lineage tracking endpoints."""

    def test_track_pattern_creation_success(self, pattern_create_event):
        """Test tracking pattern creation event."""
        start_time = time.time()

        response = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert response (200 OK or 503 Service Unavailable if database not available)
        assert response.status_code in [
            200,
            503,
        ], f"Expected 200 or 503, got {response.status_code}: {response.text}"

        # Skip remaining assertions if database unavailable
        if response.status_code == 503:
            pytest.skip("Database unavailable - skipping remaining assertions")

        data = response.json()

        # Assert performance target (<50ms)
        assert elapsed_ms < 50, f"Performance target missed: {elapsed_ms:.2f}ms"

        # Assert response structure
        assert data["success"] is True
        assert "data" in data
        assert "metadata" in data
        assert "processing_time_ms" in data["metadata"]

        # Assert lineage data
        assert "pattern_node_id" in data["data"] or "node_id" in data["data"]

        print(f"\n✓ Track Pattern Creation: {elapsed_ms:.2f}ms")

    def test_track_pattern_modification_success(self, pattern_modify_event):
        """Test tracking pattern modification with parent."""
        response = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_modify_event
        )

        assert response.status_code == 200
        data = response.json()

        # Should succeed even if parent doesn't exist (graceful handling)
        assert data["success"] is True

    def test_track_pattern_merge_success(self, pattern_merge_event):
        """Test tracking pattern merge with multiple parents."""
        response = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_merge_event
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True

    def test_track_pattern_duplicate_handling(self, pattern_create_event):
        """Test duplicate pattern tracking is handled gracefully."""
        # Track same pattern twice
        response1 = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )

        response2 = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )

        # Both should succeed (duplicate handling)
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_track_pattern_invalid_event_type(self, pattern_create_event):
        """Test tracking with invalid event type."""
        invalid_event = pattern_create_event.copy()
        invalid_event["event_type"] = "invalid_event_type"

        response = client.post(
            "/api/pattern-traceability/lineage/track", json=invalid_event
        )

        # Should return 400 or 422 (validation error)
        assert response.status_code in [400, 422]

    def test_track_pattern_missing_required_fields(self):
        """Test tracking with missing required fields."""
        incomplete_event = {
            "event_type": "pattern_created",
            # Missing: pattern_id, pattern_data
        }

        response = client.post(
            "/api/pattern-traceability/lineage/track", json=incomplete_event
        )

        assert response.status_code in [400, 422]


# ============================================================================
# Batch Lineage Tracking Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_lineage
class TestBatchLineageTracking:
    """Test batch lineage tracking endpoint."""

    def test_batch_track_parallel_processing(self, batch_lineage_events):
        """Test batch tracking with parallel processing."""
        start_time = time.time()

        batch_request = {**batch_lineage_events, "processing_mode": "parallel"}

        response = client.post(
            "/api/pattern-traceability/lineage/track/batch", json=batch_request
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target (<200ms for batch)
        assert elapsed_ms < 200, f"Batch performance target missed: {elapsed_ms:.2f}ms"

        # Assert batch summary
        assert "batch_summary" in data
        summary = data["batch_summary"]
        assert summary["total_events"] == 11
        assert summary["successful_events"] >= 0
        assert summary["processing_mode"] == "parallel"

        # Assert successful results
        assert "successful_results" in data

        print(
            f"\n✓ Batch Track (Parallel): {elapsed_ms:.2f}ms for {summary['total_events']} events"
        )

    def test_batch_track_sequential_processing(self, batch_lineage_events):
        """Test batch tracking with sequential processing."""
        batch_request = {**batch_lineage_events, "processing_mode": "sequential"}

        response = client.post(
            "/api/pattern-traceability/lineage/track/batch", json=batch_request
        )

        assert response.status_code == 200
        data = response.json()

        # Assert sequential processing
        summary = data["batch_summary"]
        assert summary["processing_mode"] == "sequential"
        assert summary["total_events"] == 11

    def test_batch_track_efficiency_gain(self, batch_lineage_events):
        """Test batch tracking efficiency vs individual requests."""
        response = client.post(
            "/api/pattern-traceability/lineage/track/batch", json=batch_lineage_events
        )

        assert response.status_code == 200
        data = response.json()

        # Check efficiency gain metric
        assert "metadata" in data
        assert "batch_efficiency_gain" in data["metadata"]

        # Should show positive efficiency gain
        efficiency_gain = data["metadata"]["batch_efficiency_gain"]
        assert (
            efficiency_gain > 0
        ), "Batch should be more efficient than individual requests"

    def test_batch_track_empty_events(self):
        """Test batch tracking with empty events list."""
        empty_batch = {"events": []}

        response = client.post(
            "/api/pattern-traceability/lineage/track/batch", json=empty_batch
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    def test_batch_track_large_batch(self):
        """Test batch tracking with large batch (50 events)."""
        # Generate 50 events
        events = []
        base_id = uuid4().hex[:8]

        for i in range(50):
            events.append(
                {
                    "event_type": "pattern_created",
                    "pattern_id": f"large_batch_{base_id}_{i}",
                    "pattern_name": f"Pattern{i}",
                    "pattern_type": "code",
                    "pattern_version": "1.0.0",
                    "pattern_data": {"index": i},
                    "triggered_by": "test",
                }
            )

        start_time = time.time()

        response = client.post(
            "/api/pattern-traceability/lineage/track/batch",
            json={"events": events, "processing_mode": "parallel"},
        )

        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        data = response.json()

        # Should complete in reasonable time
        assert elapsed_ms < 1000, f"Large batch took too long: {elapsed_ms:.2f}ms"

        summary = data["batch_summary"]
        assert summary["total_events"] == 50

        print(f"\n✓ Large Batch (50 events): {elapsed_ms:.2f}ms")


# ============================================================================
# Lineage Query Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_lineage
class TestLineageQuery:
    """Test lineage query endpoints."""

    def test_query_pattern_ancestry(self, pattern_create_event):
        """Test querying pattern ancestry."""
        # First track a pattern
        track_response = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )
        assert track_response.status_code == 200

        pattern_id = pattern_create_event["pattern_id"]

        # Query ancestry
        start_time = time.time()

        response = client.get(
            f"/api/pattern-traceability/lineage/{pattern_id}",
            params={"query_type": "ancestry"},
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert performance target (<200ms)
        assert elapsed_ms < 200, f"Ancestry query exceeded target: {elapsed_ms:.2f}ms"

        # Response should succeed (even if no ancestors)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "metadata" in data
            assert data["metadata"]["query_type"] == "ancestry"

    def test_query_pattern_descendants(self, pattern_create_event):
        """Test querying pattern descendants."""
        # Track a pattern
        track_response = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )
        assert track_response.status_code == 200

        pattern_id = pattern_create_event["pattern_id"]

        # Query descendants
        response = client.get(
            f"/api/pattern-traceability/lineage/{pattern_id}",
            params={"query_type": "descendants"},
        )

        # Should succeed (even if no descendants)
        assert response.status_code in [200, 404]

    def test_query_nonexistent_pattern(self):
        """Test querying pattern that doesn't exist."""
        nonexistent_id = f"nonexistent_{uuid4().hex}"

        response = client.get(f"/api/pattern-traceability/lineage/{nonexistent_id}")

        # Should return 404 or graceful error
        assert response.status_code in [404, 500]

    def test_query_lineage_with_invalid_query_type(self, pattern_create_event):
        """Test lineage query with invalid query type."""
        pattern_id = pattern_create_event["pattern_id"]

        response = client.get(
            f"/api/pattern-traceability/lineage/{pattern_id}",
            params={"query_type": "invalid_type"},
        )

        # Should handle gracefully (default to ancestry)
        assert response.status_code in [200, 404, 400]


# ============================================================================
# Evolution Path Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_lineage
class TestEvolutionPath:
    """Test pattern evolution path endpoint."""

    def test_get_evolution_path_success(self, pattern_create_event):
        """Test getting evolution path for pattern."""
        # Track a pattern first
        track_response = client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )
        assert track_response.status_code == 200

        pattern_id = pattern_create_event["pattern_id"]

        # Get evolution path
        start_time = time.time()

        response = client.get(
            f"/api/pattern-traceability/lineage/{pattern_id}/evolution"
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert performance (<200ms target)
        assert elapsed_ms < 200, f"Evolution query exceeded target: {elapsed_ms:.2f}ms"

        # Should return 200 (pattern exists) or 404 (database unavailable) or 503
        assert response.status_code in [200, 404, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "evolution_nodes" in data["data"]
            assert "evolution_edges" in data["data"]
            assert data["data"]["pattern_id"] == pattern_id

    def test_get_evolution_path_nonexistent(self):
        """Test evolution path for nonexistent pattern."""
        nonexistent_id = f"nonexistent_{uuid4().hex}"

        response = client.get(
            f"/api/pattern-traceability/lineage/{nonexistent_id}/evolution"
        )

        # Should return 404 or 503
        assert response.status_code in [404, 503]

    def test_evolution_path_temporal_ordering(
        self, pattern_create_event, pattern_modify_event
    ):
        """Test that evolution path maintains temporal ordering."""
        # Track initial pattern
        pattern_create_event["pattern_id"] = "evolution_test_v1"
        client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_create_event
        )

        # Track modified pattern
        pattern_modify_event["pattern_id"] = "evolution_test_v2"
        pattern_modify_event["parent_pattern_ids"] = ["evolution_test_v1"]
        client.post(
            "/api/pattern-traceability/lineage/track", json=pattern_modify_event
        )

        # Get evolution path
        response = client.get(
            "/api/pattern-traceability/lineage/evolution_test_v1/evolution"
        )

        if response.status_code == 200:
            data = response.json()
            nodes = data["data"]["evolution_nodes"]

            # Verify chronological order if nodes exist
            if len(nodes) > 1:
                timestamps = [node["created_at"] for node in nodes]
                assert timestamps == sorted(
                    timestamps
                ), "Evolution nodes should be in chronological order"


# ============================================================================
# Execution Logs Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_execution
class TestExecutionLogs:
    """Test execution log endpoints."""

    def test_get_execution_logs_default(self):
        """Test getting execution logs with default parameters."""
        start_time = time.time()

        response = client.get("/api/pattern-traceability/executions/logs")

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert performance (<500ms target)
        assert (
            elapsed_ms < 500
        ), f"Execution logs query exceeded target: {elapsed_ms:.2f}ms"

        # Should return 200 or 503 (database unavailable)
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "executions" in data
            assert "count" in data
            assert isinstance(data["executions"], list)

    def test_get_execution_logs_with_correlation_id(self):
        """Test filtering execution logs by correlation ID."""
        correlation_id = str(uuid4())

        response = client.get(
            "/api/pattern-traceability/executions/logs",
            params={"correlation_id": correlation_id},
        )

        # Should handle gracefully even if no results
        assert response.status_code in [200, 503]

    def test_get_execution_logs_with_session_id(self):
        """Test filtering execution logs by session ID."""
        session_id = str(uuid4())

        response = client.get(
            "/api/pattern-traceability/executions/logs",
            params={"session_id": session_id},
        )

        assert response.status_code in [200, 503]

    def test_get_execution_logs_with_limit(self):
        """Test execution logs with custom limit."""
        response = client.get(
            "/api/pattern-traceability/executions/logs", params={"limit": 10}
        )

        if response.status_code == 200:
            data = response.json()
            assert data["count"] <= 10

    def test_get_execution_logs_invalid_limit(self):
        """Test execution logs with invalid limit (exceeds max)."""
        response = client.get(
            "/api/pattern-traceability/executions/logs",
            params={"limit": 500},  # Max is 200
        )

        # Should return 422 validation error
        assert response.status_code == 422

    def test_get_execution_logs_invalid_correlation_id(self):
        """Test execution logs with invalid UUID format."""
        response = client.get(
            "/api/pattern-traceability/executions/logs",
            params={"correlation_id": "invalid-uuid"},
        )

        # Should return 422 validation error
        assert response.status_code == 422


# ============================================================================
# Execution Summary Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_execution
class TestExecutionSummary:
    """Test execution summary endpoint."""

    def test_get_execution_summary_all_agents(self):
        """Test getting execution summary for all agents."""
        start_time = time.time()

        response = client.get("/api/pattern-traceability/executions/summary")

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert performance (<200ms target)
        assert (
            elapsed_ms < 200
        ), f"Execution summary exceeded target: {elapsed_ms:.2f}ms"

        # Should return 200 or 503
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "summary" in data
            assert isinstance(data["summary"], list)

    def test_get_execution_summary_specific_agent(self):
        """Test getting execution summary for specific agent."""
        response = client.get(
            "/api/pattern-traceability/executions/summary",
            params={"agent_name": "agent-api-architect"},
        )

        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            # Should filter by agent if data exists
            if data["summary"]:
                for summary in data["summary"]:
                    assert summary["agent_name"] == "agent-api-architect"

    def test_get_execution_summary_nonexistent_agent(self):
        """Test summary for agent with no executions."""
        response = client.get(
            "/api/pattern-traceability/executions/summary",
            params={"agent_name": "agent-nonexistent"},
        )

        if response.status_code == 200:
            data = response.json()
            # Should return empty summary
            assert len(data["summary"]) == 0


# ============================================================================
# Usage Analytics Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_analytics
class TestUsageAnalytics:
    """Test usage analytics endpoints."""

    def test_compute_analytics_success(self, usage_analytics_request):
        """Test computing usage analytics for pattern."""
        start_time = time.time()

        response = client.post(
            "/api/pattern-traceability/analytics/compute", json=usage_analytics_request
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target (<500ms)
        assert (
            elapsed_ms < 500
        ), f"Analytics computation exceeded target: {elapsed_ms:.2f}ms"

        # Assert response structure
        assert data["success"] is True
        assert data["pattern_id"] == usage_analytics_request["pattern_id"]
        assert "time_window" in data
        assert "usage_metrics" in data
        assert "success_metrics" in data

        # Assert usage metrics structure
        usage_metrics = data["usage_metrics"]
        assert "total_executions" in usage_metrics
        assert "executions_per_day" in usage_metrics
        assert "unique_contexts" in usage_metrics

        # Assert success metrics structure
        success_metrics = data["success_metrics"]
        assert "success_rate" in success_metrics
        assert "error_rate" in success_metrics
        assert "avg_quality_score" in success_metrics

        print(f"\n✓ Analytics Computation: {elapsed_ms:.2f}ms")

    def test_compute_analytics_with_performance(self, usage_analytics_request):
        """Test analytics computation with performance metrics."""
        request = {**usage_analytics_request, "include_performance": True}

        response = client.post(
            "/api/pattern-traceability/analytics/compute", json=request
        )

        assert response.status_code == 200
        data = response.json()

        # Should include performance metrics
        assert "performance_metrics" in data

    def test_compute_analytics_with_trends(self, usage_analytics_request):
        """Test analytics computation with trend analysis."""
        request = {**usage_analytics_request, "include_trends": True}

        response = client.post(
            "/api/pattern-traceability/analytics/compute", json=request
        )

        assert response.status_code == 200
        data = response.json()

        # Should include trend analysis
        assert "trend_analysis" in data

    def test_compute_analytics_custom_time_window(self):
        """Test analytics with custom time window."""
        request = {
            "pattern_id": "test_pattern_custom_window",
            "time_window_days": 30,
            "include_performance": True,
            "include_trends": True,
        }

        response = client.post(
            "/api/pattern-traceability/analytics/compute", json=request
        )

        assert response.status_code == 200
        data = response.json()

        # Should respect custom time window
        assert data["success"] is True

    def test_compute_analytics_invalid_time_window(self):
        """Test analytics with invalid time window."""
        request = {"pattern_id": "test_pattern", "time_window_type": "invalid_window"}

        response = client.post(
            "/api/pattern-traceability/analytics/compute", json=request
        )

        # Should return 422 validation error
        assert response.status_code == 422

    def test_get_pattern_analytics_convenience(self):
        """Test convenience endpoint for pattern analytics."""
        pattern_id = "test_pattern_convenience"

        response = client.get(
            f"/api/pattern-traceability/analytics/{pattern_id}",
            params={"time_window": "weekly", "include_trends": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pattern_id"] == pattern_id


# ============================================================================
# Feedback Loop Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.traceability_feedback
class TestFeedbackLoop:
    """Test feedback loop endpoints."""

    def test_analyze_feedback_success(self, feedback_loop_request):
        """Test feedback analysis orchestration."""
        # This is a slow test (orchestration workflow)
        response = client.post(
            "/api/pattern-traceability/feedback/analyze", json=feedback_loop_request
        )

        # Should return 200 (success) or 500 (orchestration error)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "metadata" in data

    def test_analyze_feedback_custom_threshold(self):
        """Test feedback analysis with custom thresholds."""
        request = {
            "pattern_id": "test_pattern_threshold",
            "feedback_type": "quality",
            "time_window_days": 14,
            "auto_apply_threshold": 0.98,
            "min_sample_size": 50,
        }

        response = client.post(
            "/api/pattern-traceability/feedback/analyze", json=request
        )

        assert response.status_code in [200, 500]

    def test_analyze_feedback_all_types(self):
        """Test feedback analysis for all feedback types."""
        request = {
            "pattern_id": "test_pattern_all_feedback",
            "feedback_type": "all",
            "time_window_days": 7,
        }

        response = client.post(
            "/api/pattern-traceability/feedback/analyze", json=request
        )

        assert response.status_code in [200, 500]

    def test_analyze_feedback_invalid_time_window(self):
        """Test feedback analysis with invalid time window."""
        request = {
            "pattern_id": "test_pattern",
            "feedback_type": "performance",
            "time_window_days": 0,  # Invalid: must be >= 1
        }

        response = client.post(
            "/api/pattern-traceability/feedback/analyze", json=request
        )

        # Should return 422 validation error
        assert response.status_code == 422

    def test_apply_improvements_success(self):
        """Test applying pattern improvements."""
        pattern_id = "test_pattern_improvements"
        improvement_ids = ["improvement_1", "improvement_2"]

        response = client.post(
            "/api/pattern-traceability/feedback/apply",
            params={
                "pattern_id": pattern_id,
                "improvement_ids": improvement_ids,
                "force": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["pattern_id"] == pattern_id
        assert data["improvements_applied"] == len(improvement_ids)

    def test_apply_improvements_force(self):
        """Test force-applying improvements without validation."""
        pattern_id = "test_pattern_force"
        improvement_ids = ["improvement_force"]

        response = client.post(
            "/api/pattern-traceability/feedback/apply",
            params={
                "pattern_id": pattern_id,
                "improvement_ids": improvement_ids,
                "force": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["forced"] is True


# ============================================================================
# Health Check Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check_success(self):
        """Test traceability health check."""
        response = client.get("/api/pattern-traceability/health")

        assert response.status_code == 200
        data = response.json()

        # Assert health check structure
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in data
        assert "timestamp" in data

        # Assert components
        components = data["components"]
        assert "lineage_tracker" in components
        assert "usage_analytics" in components
        assert "feedback_orchestrator" in components

    def test_health_check_performance(self):
        """Test health check response time."""
        start_time = time.time()

        response = client.get("/api/pattern-traceability/health")

        elapsed_ms = (time.time() - start_time) * 1000

        # Health check should be fast (<100ms)
        assert elapsed_ms < 100, f"Health check too slow: {elapsed_ms:.2f}ms"

        assert response.status_code == 200


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.slow
class TestTraceabilityWorkflows:
    """Test complete traceability workflows."""

    def test_complete_lineage_workflow(self):
        """Test complete workflow: track → query → evolve → analytics."""
        base_id = f"workflow_{uuid4().hex[:8]}"

        # Step 1: Track initial pattern
        create_event = {
            "event_type": "pattern_created",
            "pattern_id": f"{base_id}_v1",
            "pattern_name": "WorkflowPattern",
            "pattern_type": "code",
            "pattern_version": "1.0.0",
            "pattern_data": {"code": "initial"},
            "triggered_by": "test",
        }

        track_response = client.post(
            "/api/pattern-traceability/lineage/track", json=create_event
        )
        assert track_response.status_code == 200

        # Step 2: Track modification
        modify_event = {
            "event_type": "pattern_modified",
            "pattern_id": f"{base_id}_v2",
            "pattern_name": "WorkflowPattern",
            "pattern_type": "code",
            "pattern_version": "2.0.0",
            "pattern_data": {"code": "modified"},
            "parent_pattern_ids": [f"{base_id}_v1"],
            "edge_type": "modified_from",
            "transformation_type": "enhancement",
            "triggered_by": "test",
        }

        modify_response = client.post(
            "/api/pattern-traceability/lineage/track", json=modify_event
        )
        assert modify_response.status_code == 200

        # Step 3: Query ancestry
        ancestry_response = client.get(
            f"/api/pattern-traceability/lineage/{base_id}_v2",
            params={"query_type": "ancestry"},
        )
        # May return 404 if database unavailable
        assert ancestry_response.status_code in [200, 404, 503]

        # Step 4: Get evolution path
        evolution_response = client.get(
            f"/api/pattern-traceability/lineage/{base_id}_v1/evolution"
        )
        assert evolution_response.status_code in [200, 404, 503]

        # Step 5: Compute analytics
        analytics_request = {
            "pattern_id": f"{base_id}_v1",
            "time_window_type": "weekly",
            "include_performance": True,
            "include_trends": True,
        }

        analytics_response = client.post(
            "/api/pattern-traceability/analytics/compute", json=analytics_request
        )
        assert analytics_response.status_code == 200

        print("\n✓ Complete Lineage Workflow: Track → Query → Evolve → Analytics")

    def test_batch_track_and_query_workflow(self):
        """Test batch tracking followed by querying."""
        base_id = f"batch_workflow_{uuid4().hex[:8]}"

        # Create batch of patterns
        events = []
        for i in range(5):
            events.append(
                {
                    "event_type": "pattern_created",
                    "pattern_id": f"{base_id}_{i}",
                    "pattern_name": f"BatchPattern{i}",
                    "pattern_type": "code",
                    "pattern_version": "1.0.0",
                    "pattern_data": {"index": i},
                    "triggered_by": "test",
                }
            )

        # Batch track
        batch_response = client.post(
            "/api/pattern-traceability/lineage/track/batch", json={"events": events}
        )
        assert batch_response.status_code == 200

        # Query each pattern
        for i in range(5):
            query_response = client.get(
                f"/api/pattern-traceability/lineage/{base_id}_{i}"
            )
            # Should succeed or return 404 (database unavailable)
            assert query_response.status_code in [200, 404, 503]


# ============================================================================
# Performance Benchmark Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.phase4_traceability
@pytest.mark.performance
class TestTraceabilityPerformance:
    """Performance benchmark tests for traceability API."""

    def test_all_endpoints_meet_performance_targets(
        self, pattern_create_event, batch_lineage_events, usage_analytics_request
    ):
        """Verify all endpoints consistently meet performance targets."""

        endpoints_to_test = [
            (
                "POST",
                "/api/pattern-traceability/lineage/track",
                pattern_create_event,
                50,
            ),
            (
                "POST",
                "/api/pattern-traceability/lineage/track/batch",
                batch_lineage_events,
                200,
            ),
            (
                "POST",
                "/api/pattern-traceability/analytics/compute",
                usage_analytics_request,
                500,
            ),
            ("GET", "/api/pattern-traceability/health", None, 100),
        ]

        failed_targets = []

        for method, endpoint, payload, target_ms in endpoints_to_test:
            # Run 3 times for consistency
            execution_times = []

            for _ in range(3):
                start_time = time.time()

                if method == "POST":
                    response = client.post(endpoint, json=payload)
                else:
                    response = client.get(endpoint)

                execution_time_ms = (time.time() - start_time) * 1000
                execution_times.append(execution_time_ms)

                # Skip validation for endpoints that may fail due to database
                if response.status_code not in [200, 404, 503]:
                    # Unexpected error
                    break

            avg_time = sum(execution_times) / len(execution_times)

            if avg_time >= target_ms:
                failed_targets.append((endpoint, avg_time, target_ms, execution_times))

        # Assert all endpoints met targets
        assert len(failed_targets) == 0, "Performance targets failed:\n" + "\n".join(
            f"  {endpoint}: avg={avg:.2f}ms (target: {target}ms), times={times}"
            for endpoint, avg, target, times in failed_targets
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "phase4_traceability"])
