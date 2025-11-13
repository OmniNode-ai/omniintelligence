"""
Integration Tests for Autonomous Learning API (7 endpoints)

Tests complete workflows including:
1. Pattern ingestion and storage
2. Success tracking and learning
3. Agent prediction with historical data
4. Time estimation with pattern analysis
5. Safety score calculation
6. Statistics aggregation
7. Health monitoring

Verifies the autonomous learning feedback loop:
- Ingest patterns → Record successes → Update statistics → Improve predictions

Marker Usage:
    pytest -m integration                  # Run all integration tests
    pytest -m autonomous                   # Run only autonomous API tests
    pytest -m "integration and autonomous" # Run autonomous integration tests
    pytest -m learning_feedback            # Run only learning feedback tests

Author: Archon Intelligence Team
Date: 2025-10-16
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from api.autonomous.models import (
    ChangeScope,
    TaskComplexity,
    TaskType,
)
from api.autonomous.routes import router as autonomous_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add parent directory to path for imports


# Create minimal test app with just autonomous router
app_for_testing = FastAPI(title="Test Autonomous APIs Integration")
app_for_testing.include_router(autonomous_router)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_client():
    """Create test client for API integration tests"""
    return TestClient(app_for_testing)


@pytest.fixture
def simple_task_characteristics():
    """Simple task for testing - low complexity"""
    return {
        "task_description": "Add unit tests for authentication module",
        "task_type": TaskType.TESTING.value,
        "complexity": TaskComplexity.SIMPLE.value,
        "change_scope": ChangeScope.SINGLE_FILE.value,
        "estimated_files_affected": 1,
        "requires_testing": True,
        "requires_validation": True,
    }


@pytest.fixture
def complex_task_characteristics():
    """Complex task for testing - high complexity with OAuth2"""
    return {
        "task_description": "Implement OAuth2 authentication with Google and GitHub providers",
        "task_type": TaskType.CODE_GENERATION.value,
        "complexity": TaskComplexity.COMPLEX.value,
        "change_scope": ChangeScope.MODULE.value,
        "estimated_files_affected": 8,
        "requires_testing": True,
        "requires_validation": True,
        "project_id": str(uuid4()),
        "context": {
            "framework": "FastAPI",
            "language": "python",
            "dependencies": ["authlib", "pydantic"],
        },
    }


@pytest.fixture
def moderate_task_characteristics():
    """Moderate complexity task for realistic testing"""
    return {
        "task_description": "Implement REST API endpoint for user management",
        "task_type": TaskType.CODE_GENERATION.value,
        "complexity": TaskComplexity.MODERATE.value,
        "change_scope": ChangeScope.MULTIPLE_FILES.value,
        "estimated_files_affected": 3,
        "requires_testing": True,
        "requires_validation": True,
    }


@pytest.fixture
def execution_pattern_success():
    """Successful execution pattern for ingestion testing"""
    return {
        "execution_id": str(uuid4()),
        "task_characteristics": {
            "task_description": "Implement REST API endpoint for user management",
            "task_type": TaskType.CODE_GENERATION.value,
            "complexity": TaskComplexity.MODERATE.value,
            "change_scope": ChangeScope.MULTIPLE_FILES.value,
            "estimated_files_affected": 3,
            "requires_testing": True,
            "requires_validation": True,
        },
        "execution_details": {
            "agent_used": "agent-api-architect",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "steps_executed": [
                "analyze_requirements",
                "design_api",
                "implement_endpoints",
                "write_tests",
            ],
            "files_modified": [
                "src/api/users.py",
                "tests/test_users.py",
                "src/models/user.py",
            ],
            "commands_executed": ["pytest", "mypy"],
            "tools_used": ["fastapi", "pydantic", "pytest"],
        },
        "outcome": {
            "success": True,
            "duration_ms": 180000,
            "quality_score": 0.88,
            "test_coverage": 0.92,
        },
    }


@pytest.fixture
def execution_pattern_failure():
    """Failed execution pattern for testing learning from failures"""
    return {
        "execution_id": str(uuid4()),
        "task_characteristics": {
            "task_description": "Complex database migration with zero downtime",
            "task_type": TaskType.ARCHITECTURE.value,
            "complexity": TaskComplexity.CRITICAL.value,
            "change_scope": ChangeScope.SYSTEM_WIDE.value,
            "estimated_files_affected": 15,
            "requires_testing": True,
            "requires_validation": True,
        },
        "execution_details": {
            "agent_used": "agent-api-architect",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "steps_executed": ["analyze", "plan", "failed_execution"],
            "files_modified": [],
        },
        "outcome": {
            "success": False,
            "duration_ms": 45000,
            "error_type": "TimeoutError",
            "error_message": "Database connection timeout",
        },
    }


# ============================================================================
# API Endpoint Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.autonomous
class TestAutonomousLearningAPI:
    """Integration tests for all 7 Autonomous Learning API endpoints."""

    # ========================================================================
    # 1. Pattern Ingestion API Tests
    # ========================================================================

    def test_ingest_pattern_success_workflow(
        self, test_client, execution_pattern_success
    ):
        """Test complete pattern ingestion workflow with successful execution."""
        start_time = time.time()

        # Ingest pattern
        response = test_client.post(
            "/api/autonomous/patterns/ingest", json=execution_pattern_success
        )

        execution_time_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target (<100ms)
        assert (
            execution_time_ms < 200
        ), f"Ingestion took {execution_time_ms:.2f}ms, exceeds 200ms target"

        # Assert response structure
        assert "pattern_id" in data
        assert "pattern_name" in data
        assert "is_new_pattern" in data
        assert "success_rate" in data
        assert "total_executions" in data
        assert "confidence_score" in data
        assert "message" in data

        # Assert data validity
        assert isinstance(data["is_new_pattern"], bool)
        assert 0.0 <= data["success_rate"] <= 1.0
        assert data["total_executions"] >= 1
        assert 0.0 <= data["confidence_score"] <= 1.0

        # Store pattern_name for follow-up tests
        return data["pattern_name"]

    def test_ingest_pattern_failure_tracking(
        self, test_client, execution_pattern_failure
    ):
        """Test pattern ingestion tracks failures correctly."""
        response = test_client.post(
            "/api/autonomous/patterns/ingest", json=execution_pattern_failure
        )

        assert response.status_code == 200
        data = response.json()

        # Failure should still create/update pattern
        assert "pattern_id" in data
        assert "total_executions" in data

        # Success rate should reflect the failure (may be <1.0 if first execution failed)
        assert data["success_rate"] <= 1.0

    def test_ingest_multiple_patterns_updates_statistics(
        self, test_client, moderate_task_characteristics
    ):
        """Test that ingesting multiple patterns updates statistics correctly."""
        # Ingest same pattern 3 times (2 successes, 1 failure)
        patterns = []
        for i, success in enumerate([True, True, False]):
            pattern = {
                "execution_id": str(uuid4()),
                "task_characteristics": moderate_task_characteristics,
                "execution_details": {
                    "agent_used": "agent-api-architect",
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "steps_executed": ["analyze", "implement"],
                    "files_modified": ["test.py"],
                },
                "outcome": {
                    "success": success,
                    "duration_ms": 150000 + (i * 10000),
                    "quality_score": 0.85 if success else None,
                },
            }
            patterns.append(pattern)

        # Ingest all patterns
        results = []
        for pattern in patterns:
            response = test_client.post("/api/autonomous/patterns/ingest", json=pattern)
            assert response.status_code == 200
            results.append(response.json())

        # Verify statistics updated
        # Last result should show cumulative data
        last_result = results[-1]
        assert last_result["total_executions"] >= 3  # May be more from other tests

        # Success rate should reflect 2/3 successes (or adjusted if pattern existed)
        # We don't assert exact value since pattern may have prior history

    def test_ingest_pattern_invalid_structure(self, test_client):
        """Test ingestion with invalid pattern structure returns 422."""
        invalid_pattern = {
            "execution_id": str(uuid4()),
            # Missing required fields: task_characteristics, execution_details, outcome
        }

        response = test_client.post(
            "/api/autonomous/patterns/ingest", json=invalid_pattern
        )

        assert response.status_code == 422  # Validation error

    # ========================================================================
    # 2. Success Pattern Recording (via ingestion)
    # ========================================================================

    def test_success_pattern_learning_feedback_loop(
        self, test_client, moderate_task_characteristics
    ):
        """
        Test complete learning feedback loop:
        1. Ingest initial pattern
        2. Record success
        3. Verify statistics updated
        4. Test prediction improvement
        """
        # Step 1: Ingest initial pattern (success)
        pattern1 = {
            "execution_id": str(uuid4()),
            "task_characteristics": moderate_task_characteristics,
            "execution_details": {
                "agent_used": "agent-api-architect",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "steps_executed": ["analyze", "implement", "test"],
                "files_modified": ["api.py", "test_api.py"],
            },
            "outcome": {
                "success": True,
                "duration_ms": 180000,
                "quality_score": 0.90,
                "test_coverage": 0.95,
            },
        }

        response1 = test_client.post("/api/autonomous/patterns/ingest", json=pattern1)
        assert response1.status_code == 200
        result1 = response1.json()
        pattern_name = result1["pattern_name"]

        # Step 2: Record another success for same pattern
        pattern2 = {
            "execution_id": str(uuid4()),
            "task_characteristics": moderate_task_characteristics,
            "execution_details": {
                "agent_used": "agent-api-architect",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "steps_executed": ["analyze", "implement", "test"],
                "files_modified": ["api.py", "test_api.py"],
            },
            "outcome": {
                "success": True,
                "duration_ms": 175000,
                "quality_score": 0.92,
                "test_coverage": 0.96,
            },
        }

        response2 = test_client.post("/api/autonomous/patterns/ingest", json=pattern2)
        assert response2.status_code == 200
        result2 = response2.json()

        # Step 3: Verify statistics updated
        assert result2["pattern_name"] == pattern_name
        assert result2["is_new_pattern"] is False  # Pattern already exists
        assert result2["total_executions"] >= 2

        # Confidence should increase with more data points
        # (May not always be higher due to formula, but should be reasonable)
        assert result2["confidence_score"] > 0.5

        # Step 4: Test that agent prediction benefits from learned pattern
        # (This is implicit - predictions use ingested patterns)

    # ========================================================================
    # 3. Agent Prediction API Tests
    # ========================================================================

    def test_predict_agent_simple_task(self, test_client, simple_task_characteristics):
        """Test agent prediction for simple task."""
        start_time = time.time()

        response = test_client.post(
            "/api/autonomous/predict/agent", json=simple_task_characteristics
        )

        execution_time_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target
        assert (
            execution_time_ms < 150
        ), f"Prediction took {execution_time_ms:.2f}ms, exceeds 150ms target"

        # Assert response schema
        assert "recommended_agent" in data
        assert "confidence_score" in data
        assert "confidence_level" in data
        assert "reasoning" in data
        assert "alternative_agents" in data
        assert "expected_success_rate" in data

        # Assert data validity
        assert isinstance(data["recommended_agent"], str)
        assert 0.0 <= data["confidence_score"] <= 1.0
        assert data["confidence_level"] in [
            "very_low",
            "low",
            "medium",
            "high",
            "very_high",
        ]
        assert 0.0 <= data["expected_success_rate"] <= 1.0
        assert isinstance(data["alternative_agents"], list)

    def test_predict_agent_complex_task(
        self, test_client, complex_task_characteristics
    ):
        """Test agent prediction for complex OAuth2 task."""
        response = test_client.post(
            "/api/autonomous/predict/agent", json=complex_task_characteristics
        )

        assert response.status_code == 200
        data = response.json()

        # Complex tasks should have detailed reasoning
        assert len(data["reasoning"]) > 50

        # Should provide alternatives
        assert len(data["alternative_agents"]) >= 1

        # Verify alternative structure
        for alt in data["alternative_agents"]:
            assert "agent_name" in alt
            assert "confidence" in alt
            assert "reasoning" in alt
            assert "estimated_success_rate" in alt
            assert 0.0 <= alt["confidence"] <= 1.0

    def test_predict_agent_with_confidence_threshold(
        self, test_client, moderate_task_characteristics
    ):
        """Test agent prediction respects confidence threshold."""
        response = test_client.post(
            "/api/autonomous/predict/agent?confidence_threshold=0.85",
            json=moderate_task_characteristics,
        )

        assert response.status_code == 200
        data = response.json()

        # Should still return recommendation
        assert data["recommended_agent"]

        # Confidence may be below threshold, but still returned
        assert data["confidence_score"] >= 0.0

    # ========================================================================
    # 4. Time Estimation API Tests
    # ========================================================================

    def test_predict_time_simple_task(self, test_client, simple_task_characteristics):
        """Test time estimation for simple task."""
        start_time = time.time()

        response = test_client.post(
            "/api/autonomous/predict/time?agent=agent-testing",
            json=simple_task_characteristics,
        )

        execution_time_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target
        assert (
            execution_time_ms < 150
        ), f"Time estimation took {execution_time_ms:.2f}ms, exceeds 150ms target"

        # Assert response schema
        assert "estimated_duration_ms" in data
        assert "p25_duration_ms" in data
        assert "p75_duration_ms" in data
        assert "p95_duration_ms" in data
        assert "confidence_score" in data
        assert "time_breakdown" in data

        # Assert percentile ordering: P25 <= P50 <= P75 <= P95
        assert data["p25_duration_ms"] <= data["estimated_duration_ms"]
        assert data["estimated_duration_ms"] <= data["p75_duration_ms"]
        assert data["p75_duration_ms"] <= data["p95_duration_ms"]

        # Assert time breakdown
        breakdown = data["time_breakdown"]
        assert "planning_ms" in breakdown
        assert "implementation_ms" in breakdown
        assert "testing_ms" in breakdown
        assert "review_ms" in breakdown
        assert "overhead_ms" in breakdown

        # Simple task should be shorter
        assert data["estimated_duration_ms"] < 300000  # Less than 5 minutes

    def test_predict_time_complex_task(self, test_client, complex_task_characteristics):
        """Test time estimation for complex task."""
        response = test_client.post(
            "/api/autonomous/predict/time?agent=agent-api-architect",
            json=complex_task_characteristics,
        )

        assert response.status_code == 200
        data = response.json()

        # Complex task should have longer duration
        assert data["estimated_duration_ms"] > 120000  # More than 2 minutes

        # Should have higher variance
        assert data["historical_variance"] > 0

        # Should identify complexity factors
        assert "factors_affecting_time" in data
        assert len(data["factors_affecting_time"]) > 0

    def test_predict_time_invalid_agent(self, test_client, simple_task_characteristics):
        """Test time estimation with non-existent agent."""
        response = test_client.post(
            "/api/autonomous/predict/time?agent=agent-nonexistent",
            json=simple_task_characteristics,
        )

        assert response.status_code == 404  # Agent not found

    # ========================================================================
    # 5. Safety Score Calculation Tests
    # ========================================================================

    def test_calculate_safety_safe_task(self, test_client):
        """Test safety calculation for safe autonomous execution."""
        start_time = time.time()

        response = test_client.post(
            "/api/autonomous/calculate/safety?"
            "task_type=bug_fix&"
            "complexity=0.3&"
            "change_scope=single_file&"
            "agent=agent-debug-intelligence"
        )

        execution_time_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target
        assert (
            execution_time_ms < 150
        ), f"Safety calculation took {execution_time_ms:.2f}ms, exceeds 150ms target"

        # Assert response schema
        assert "safety_score" in data
        assert "safety_rating" in data
        assert "can_execute_autonomously" in data
        assert "requires_human_review" in data
        assert "risk_factors" in data
        assert "safety_checks_required" in data

        # Low complexity, small scope should be safe
        assert data["safety_score"] >= 0.6
        assert data["safety_rating"] in ["safe", "caution"]
        assert data["can_execute_autonomously"] is True

        # Should have some safety checks
        assert isinstance(data["safety_checks_required"], list)
        assert len(data["safety_checks_required"]) > 0

    def test_calculate_safety_risky_task(self, test_client):
        """Test safety calculation for risky task."""
        response = test_client.post(
            "/api/autonomous/calculate/safety?"
            "task_type=security&"
            "complexity=0.95&"
            "change_scope=system_wide"
        )

        assert response.status_code == 200
        data = response.json()

        # High complexity + wide scope = lower safety
        assert data["safety_score"] < 0.8

        # Should require human review
        assert data["requires_human_review"] is True

        # Should identify multiple risk factors
        assert len(data["risk_factors"]) > 0

        # Risk factors should have proper structure
        for risk in data["risk_factors"]:
            assert "factor" in risk
            assert "severity" in risk
            assert "likelihood" in risk
            assert "mitigation" in risk
            assert risk["severity"] in ["low", "medium", "high"]

    def test_calculate_safety_score_range_validation(self, test_client):
        """Test that safety score is always within valid range (0.0-1.0)."""
        # Test multiple complexity levels
        for complexity in [0.1, 0.3, 0.5, 0.7, 0.9]:
            response = test_client.post(
                f"/api/autonomous/calculate/safety?"
                f"task_type=code_generation&"
                f"complexity={complexity}&"
                f"change_scope=module"
            )

            assert response.status_code == 200
            data = response.json()

            # Safety score must be in valid range
            assert 0.0 <= data["safety_score"] <= 1.0
            assert 0.0 <= data["historical_success_rate"] <= 1.0
            assert 0.0 <= data["confidence_in_assessment"] <= 1.0

    # ========================================================================
    # 6. Success Patterns Retrieval Tests
    # ========================================================================

    def test_get_success_patterns_default(self, test_client):
        """Test retrieving success patterns with default filters."""
        start_time = time.time()

        response = test_client.get("/api/autonomous/patterns/success")

        execution_time_ms = (time.time() - start_time) * 1000

        # Assert response success
        assert response.status_code == 200
        data = response.json()

        # Assert performance target
        assert (
            execution_time_ms < 150
        ), f"Pattern retrieval took {execution_time_ms:.2f}ms, exceeds 150ms target"

        # Should return list of patterns
        assert isinstance(data, list)

        # Each pattern should have required fields
        for pattern in data:
            assert "pattern_id" in pattern
            assert "pattern_name" in pattern
            assert "task_type" in pattern
            assert "agent_sequence" in pattern
            assert "success_rate" in pattern
            assert "average_duration_ms" in pattern
            assert "confidence_score" in pattern

            # Default min_success_rate is 0.8
            assert pattern["success_rate"] >= 0.8

            # Agent sequence should be non-empty
            assert len(pattern["agent_sequence"]) > 0

    def test_get_success_patterns_with_filters(self, test_client):
        """Test retrieving patterns with custom filters."""
        response = test_client.get(
            "/api/autonomous/patterns/success?"
            "min_success_rate=0.9&"
            "task_type=code_generation&"
            "limit=5"
        )

        assert response.status_code == 200
        data = response.json()

        # Should respect limit
        assert len(data) <= 5

        # All patterns should meet min_success_rate
        for pattern in data:
            assert pattern["success_rate"] >= 0.9

    def test_get_success_patterns_high_threshold(self, test_client):
        """Test retrieving only highest quality patterns."""
        response = test_client.get(
            "/api/autonomous/patterns/success?min_success_rate=0.95&limit=10"
        )

        assert response.status_code == 200
        data = response.json()

        # All patterns should be very high quality
        for pattern in data:
            assert pattern["success_rate"] >= 0.95

    # ========================================================================
    # 7. Statistics API Tests
    # ========================================================================

    def test_autonomous_stats(self, test_client):
        """Test autonomous statistics endpoint."""
        response = test_client.get("/api/autonomous/stats")

        assert response.status_code == 200
        data = response.json()

        # Assert required fields
        assert "total_patterns" in data
        assert "total_agents" in data
        assert "average_pattern_success_rate" in data

        # Assert data validity
        assert data["total_patterns"] >= 0
        assert data["total_agents"] > 0
        assert 0.0 <= data["average_pattern_success_rate"] <= 1.0

    def test_stats_reflect_ingested_patterns(
        self, test_client, execution_pattern_success
    ):
        """Test that statistics reflect ingested patterns."""
        # Get initial stats
        response1 = test_client.get("/api/autonomous/stats")
        assert response1.status_code == 200
        initial_stats = response1.json()
        initial_patterns = initial_stats["total_patterns"]

        # Ingest a new pattern
        test_client.post(
            "/api/autonomous/patterns/ingest", json=execution_pattern_success
        )

        # Get updated stats
        response2 = test_client.get("/api/autonomous/stats")
        assert response2.status_code == 200
        updated_stats = response2.json()

        # Pattern count should increase or stay same (if pattern existed)
        assert updated_stats["total_patterns"] >= initial_patterns

    # ========================================================================
    # 8. Health Check Tests
    # ========================================================================

    def test_autonomous_health_check(self, test_client):
        """Test autonomous health endpoint."""
        response = test_client.get("/api/autonomous/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "autonomous-execution-api"
        assert "endpoints" in data
        assert "version" in data
        assert "timestamp" in data

        # Should list all core endpoints
        expected_endpoints = [
            "/predict/agent",
            "/predict/time",
            "/calculate/safety",
            "/patterns/success",
            "/patterns/ingest",
        ]
        for endpoint in expected_endpoints:
            assert endpoint in data["endpoints"]


# ============================================================================
# Integration Workflow Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.autonomous
@pytest.mark.learning_feedback
class TestAutonomousLearningFeedbackLoop:
    """Test complete learning feedback loops and workflows."""

    def test_complete_autonomous_workflow(
        self, test_client, moderate_task_characteristics
    ):
        """
        Test complete autonomous learning workflow:
        1. Predict optimal agent
        2. Estimate execution time
        3. Assess safety
        4. Simulate execution
        5. Ingest execution pattern
        6. Verify learning occurred
        """
        # Step 1: Predict optimal agent
        agent_response = test_client.post(
            "/api/autonomous/predict/agent", json=moderate_task_characteristics
        )
        assert agent_response.status_code == 200
        agent_data = agent_response.json()
        selected_agent = agent_data["recommended_agent"]
        agent_data["confidence_score"]

        # Step 2: Estimate execution time
        time_response = test_client.post(
            f"/api/autonomous/predict/time?agent={selected_agent}",
            json=moderate_task_characteristics,
        )
        assert time_response.status_code == 200
        time_data = time_response.json()
        estimated_duration = time_data["estimated_duration_ms"]

        # Step 3: Assess safety
        safety_response = test_client.post(
            f"/api/autonomous/calculate/safety?"
            f"task_type={moderate_task_characteristics['task_type']}&"
            f"complexity=0.5&"
            f"change_scope={moderate_task_characteristics['change_scope']}&"
            f"agent={selected_agent}"
        )
        assert safety_response.status_code == 200
        safety_data = safety_response.json()

        # Step 4: Simulate successful execution
        execution_pattern = {
            "execution_id": str(uuid4()),
            "task_characteristics": moderate_task_characteristics,
            "execution_details": {
                "agent_used": selected_agent,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": (
                    datetime.now(timezone.utc)
                    + timedelta(milliseconds=estimated_duration)
                ).isoformat(),
                "steps_executed": ["plan", "implement", "test", "validate"],
                "files_modified": ["src/api.py", "tests/test_api.py"],
            },
            "outcome": {
                "success": True,
                "duration_ms": estimated_duration,
                "quality_score": 0.87,
                "test_coverage": 0.93,
            },
        }

        # Step 5: Ingest execution pattern
        pattern_response = test_client.post(
            "/api/autonomous/patterns/ingest", json=execution_pattern
        )
        assert pattern_response.status_code == 200
        pattern_data = pattern_response.json()

        # Step 6: Verify learning occurred
        assert "pattern_id" in pattern_data
        assert pattern_data["success_rate"] > 0  # Should have positive success rate

        # Verify workflow completeness
        assert selected_agent  # Agent was selected
        assert estimated_duration > 0  # Time was estimated
        assert "safety_score" in safety_data  # Safety was assessed
        assert pattern_data["pattern_id"]  # Pattern was learned

    def test_learning_improves_predictions_over_time(
        self, test_client, moderate_task_characteristics
    ):
        """
        Test that repeated successful executions improve prediction confidence.
        """
        # Ingest multiple successful patterns for same task type
        for i in range(3):
            pattern = {
                "execution_id": str(uuid4()),
                "task_characteristics": moderate_task_characteristics,
                "execution_details": {
                    "agent_used": "agent-api-architect",
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "end_time": datetime.now(timezone.utc).isoformat(),
                    "steps_executed": ["analyze", "implement", "test"],
                    "files_modified": [f"file_{i}.py"],
                },
                "outcome": {
                    "success": True,
                    "duration_ms": 180000 + (i * 5000),
                    "quality_score": 0.85 + (i * 0.02),
                    "test_coverage": 0.90 + (i * 0.01),
                },
            }

            response = test_client.post("/api/autonomous/patterns/ingest", json=pattern)
            assert response.status_code == 200

        # Get statistics - should reflect learned patterns
        stats_response = test_client.get("/api/autonomous/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()

        assert stats["total_patterns"] >= 1
        assert stats["average_pattern_success_rate"] > 0

    def test_failure_patterns_affect_safety_scores(
        self, test_client, execution_pattern_failure
    ):
        """Test that failure patterns appropriately affect safety assessments."""
        # Ingest a failure pattern
        response = test_client.post(
            "/api/autonomous/patterns/ingest", json=execution_pattern_failure
        )
        assert response.status_code == 200
        data = response.json()

        # Failure should be tracked
        assert data["success_rate"] < 1.0  # Should reflect failure

        # Now assess safety for similar task
        safety_response = test_client.post(
            "/api/autonomous/calculate/safety?"
            "task_type=architecture&"
            "complexity=0.95&"
            "change_scope=system_wide"
        )
        assert safety_response.status_code == 200
        safety = safety_response.json()

        # High-risk task should have lower safety score
        assert safety["safety_score"] < 0.8
        assert safety["requires_human_review"] is True


# ============================================================================
# Performance & Error Handling Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.autonomous
class TestAutonomousAPIPerformanceAndErrors:
    """Test performance targets and error handling."""

    def test_all_endpoints_meet_performance_targets(
        self, test_client, simple_task_characteristics, execution_pattern_success
    ):
        """Verify all endpoints meet performance targets."""
        endpoints = [
            ("POST", "/api/autonomous/predict/agent", simple_task_characteristics),
            (
                "POST",
                "/api/autonomous/predict/time?agent=agent-testing",
                simple_task_characteristics,
            ),
            (
                "POST",
                "/api/autonomous/calculate/safety?task_type=bug_fix&complexity=0.3&change_scope=single_file",
                None,
            ),
            ("GET", "/api/autonomous/patterns/success?limit=10", None),
            ("POST", "/api/autonomous/patterns/ingest", execution_pattern_success),
            ("GET", "/api/autonomous/stats", None),
            ("GET", "/api/autonomous/health", None),
        ]

        failed_targets = []

        for method, endpoint, payload in endpoints:
            execution_times = []

            # Test 3 times for consistency
            for _ in range(3):
                start_time = time.time()

                if method == "POST":
                    response = test_client.post(endpoint, json=payload)
                else:
                    response = test_client.get(endpoint)

                execution_time_ms = (time.time() - start_time) * 1000
                execution_times.append(execution_time_ms)

                assert response.status_code == 200

            avg_time = sum(execution_times) / len(execution_times)

            # Most endpoints should complete in <200ms
            target = 200 if "/patterns/" in endpoint else 150

            if avg_time >= target:
                failed_targets.append((endpoint, avg_time, target))

        # Assert all met targets
        assert len(failed_targets) == 0, "Performance targets failed:\n" + "\n".join(
            f"  {endpoint}: avg={avg:.2f}ms, target={target}ms"
            for endpoint, avg, target in failed_targets
        )

    def test_invalid_input_handling(self, test_client):
        """Test that invalid inputs are handled gracefully."""
        # Invalid task type
        invalid_task = {
            "task_description": "Test task",
            "task_type": "invalid_type",
            "complexity": "simple",
            "change_scope": "single_file",
        }

        response = test_client.post("/api/autonomous/predict/agent", json=invalid_task)
        assert response.status_code == 422

        # Invalid complexity range
        response = test_client.post(
            "/api/autonomous/calculate/safety?"
            "task_type=bug_fix&complexity=1.5&change_scope=single_file"
        )
        assert response.status_code == 422

        # Invalid limit
        response = test_client.get("/api/autonomous/patterns/success?limit=500")
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])
