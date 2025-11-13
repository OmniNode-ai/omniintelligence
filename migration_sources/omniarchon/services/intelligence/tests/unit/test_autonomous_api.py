"""
Comprehensive tests for Track 3 Autonomous Execution APIs

Tests all 5 core endpoints for Track 4 Autonomous System integration:
1. Agent Prediction API
2. Time Estimation API
3. Safety Score API
4. Pattern Query API
5. Pattern Ingestion API

Performance Target: All endpoints must respond in <100ms
"""

# Import the autonomous router directly
import sys
import time
from datetime import datetime, timezone
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
test_app = FastAPI(title="Test Autonomous APIs")
test_app.include_router(autonomous_router)

# Create test client
client = TestClient(test_app)


# ============================================================================
# Fixtures
# ============================================================================


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
    """Complex task for testing - high complexity"""
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
def critical_task_characteristics():
    """Critical task for testing - system-wide impact"""
    return {
        "task_description": "Migrate database schema with zero downtime",
        "task_type": TaskType.ARCHITECTURE.value,
        "complexity": TaskComplexity.CRITICAL.value,
        "change_scope": ChangeScope.SYSTEM_WIDE.value,
        "estimated_files_affected": 15,
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


# ============================================================================
# API 1: Agent Prediction Tests
# ============================================================================


def test_predict_agent_simple_task(simple_task_characteristics):
    """Test agent prediction for simple task - should recommend appropriate agent"""
    start_time = time.time()

    response = client.post(
        "/api/autonomous/predict/agent", json=simple_task_characteristics
    )

    execution_time_ms = (time.time() - start_time) * 1000

    # Assert response success
    assert response.status_code == 200
    data = response.json()

    # Assert performance target
    assert (
        execution_time_ms < 100
    ), f"Performance target missed: {execution_time_ms:.2f}ms"

    # Assert response schema
    assert "recommended_agent" in data
    assert "confidence_score" in data
    assert "confidence_level" in data
    assert "reasoning" in data
    assert "alternative_agents" in data
    assert "expected_success_rate" in data

    # Assert data types and ranges
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

    # Assert reasonable agent selection for testing task
    assert "agent" in data["recommended_agent"]


def test_predict_agent_complex_task(complex_task_characteristics):
    """Test agent prediction for complex OAuth2 task"""
    response = client.post(
        "/api/autonomous/predict/agent", json=complex_task_characteristics
    )

    assert response.status_code == 200
    data = response.json()

    # Complex tasks should have high confidence with detailed reasoning
    assert data["confidence_score"] >= 0.5
    assert len(data["reasoning"]) > 50
    assert len(data["alternative_agents"]) >= 1

    # Should provide multiple alternatives for complex tasks
    for alt in data["alternative_agents"]:
        assert "agent_name" in alt
        assert "confidence" in alt
        assert "reasoning" in alt
        assert 0.0 <= alt["confidence"] <= 1.0


def test_predict_agent_with_confidence_threshold():
    """Test agent prediction with custom confidence threshold"""
    task = {
        "task_description": "Fix bug in authentication flow",
        "task_type": TaskType.BUG_FIX.value,
        "complexity": TaskComplexity.MODERATE.value,
        "change_scope": ChangeScope.SINGLE_FILE.value,
    }

    response = client.post(
        "/api/autonomous/predict/agent?confidence_threshold=0.85", json=task
    )

    assert response.status_code == 200
    data = response.json()

    # High threshold should still return a recommendation
    assert data["recommended_agent"]
    assert data["confidence_score"] >= 0.0  # May be below threshold but still returned


def test_predict_agent_invalid_task_type():
    """Test agent prediction with invalid task type - should return 422"""
    invalid_task = {
        "task_description": "Test task",
        "task_type": "invalid_type",  # Invalid enum value
        "complexity": TaskComplexity.SIMPLE.value,
        "change_scope": ChangeScope.SINGLE_FILE.value,
    }

    response = client.post("/api/autonomous/predict/agent", json=invalid_task)

    assert response.status_code == 422  # Validation error


def test_predict_agent_missing_required_fields():
    """Test agent prediction with missing required fields"""
    incomplete_task = {
        "task_description": "Test task"
        # Missing required fields: task_type
    }

    response = client.post("/api/autonomous/predict/agent", json=incomplete_task)

    assert response.status_code == 422  # Validation error


def test_predict_agent_empty_description():
    """Test agent prediction with too short description"""
    invalid_task = {
        "task_description": "Short",  # Less than 10 characters (min_length)
        "task_type": TaskType.CODE_GENERATION.value,
        "complexity": TaskComplexity.SIMPLE.value,
        "change_scope": ChangeScope.SINGLE_FILE.value,
    }

    response = client.post("/api/autonomous/predict/agent", json=invalid_task)

    assert response.status_code == 422  # Validation error


# ============================================================================
# API 2: Time Estimation Tests
# ============================================================================


def test_predict_time_simple_task(simple_task_characteristics):
    """Test time estimation for simple task - should be fast"""
    start_time = time.time()

    response = client.post(
        "/api/autonomous/predict/time?agent=agent-testing",
        json=simple_task_characteristics,
    )

    execution_time_ms = (time.time() - start_time) * 1000

    # Assert response success
    assert response.status_code == 200
    data = response.json()

    # Assert performance target
    assert (
        execution_time_ms < 100
    ), f"Performance target missed: {execution_time_ms:.2f}ms"

    # Assert response schema
    assert "estimated_duration_ms" in data
    assert "p25_duration_ms" in data
    assert "p75_duration_ms" in data
    assert "p95_duration_ms" in data
    assert "confidence_score" in data
    assert "time_breakdown" in data
    assert "historical_variance" in data

    # Assert percentile ordering: P25 < P50 < P75 < P95
    assert data["p25_duration_ms"] <= data["estimated_duration_ms"]
    assert data["estimated_duration_ms"] <= data["p75_duration_ms"]
    assert data["p75_duration_ms"] <= data["p95_duration_ms"]

    # Assert time breakdown components
    breakdown = data["time_breakdown"]
    assert "planning_ms" in breakdown
    assert "implementation_ms" in breakdown
    assert "testing_ms" in breakdown
    assert "review_ms" in breakdown
    assert "overhead_ms" in breakdown

    # Simple task should have shorter duration
    assert data["estimated_duration_ms"] < 300000  # Less than 5 minutes


def test_predict_time_complex_task(complex_task_characteristics):
    """Test time estimation for complex OAuth2 task - should be longer"""
    response = client.post(
        "/api/autonomous/predict/time?agent=agent-api-architect",
        json=complex_task_characteristics,
    )

    assert response.status_code == 200
    data = response.json()

    # Complex task should have longer duration
    assert data["estimated_duration_ms"] > 120000  # More than 2 minutes

    # Should have higher variance for complex tasks
    assert data["historical_variance"] > 0

    # Should identify complexity factors
    assert "factors_affecting_time" in data
    assert len(data["factors_affecting_time"]) > 0

    # Complex tasks should have significant testing time
    assert data["time_breakdown"]["testing_ms"] > 0


def test_predict_time_critical_task(critical_task_characteristics):
    """Test time estimation for critical system-wide task"""
    response = client.post(
        "/api/autonomous/predict/time?agent=agent-api-architect",
        json=critical_task_characteristics,
    )

    assert response.status_code == 200
    data = response.json()

    # Critical tasks should have very long duration
    assert data["estimated_duration_ms"] > 300000  # More than 5 minutes

    # Wide percentile range for high uncertainty
    percentile_range = data["p95_duration_ms"] - data["p25_duration_ms"]
    assert percentile_range > 200000  # Significant variance


def test_predict_time_invalid_agent():
    """Test time estimation with non-existent agent"""
    task = {
        "task_description": "Test task for invalid agent",
        "task_type": TaskType.CODE_GENERATION.value,
        "complexity": TaskComplexity.SIMPLE.value,
        "change_scope": ChangeScope.SINGLE_FILE.value,
    }

    response = client.post(
        "/api/autonomous/predict/time?agent=agent-nonexistent", json=task
    )

    assert response.status_code == 404  # Agent not found


def test_predict_time_missing_agent_parameter():
    """Test time estimation without agent parameter"""
    task = {
        "task_description": "Test task without agent",
        "task_type": TaskType.CODE_GENERATION.value,
        "complexity": TaskComplexity.SIMPLE.value,
        "change_scope": ChangeScope.SINGLE_FILE.value,
    }

    response = client.post("/api/autonomous/predict/time", json=task)

    assert response.status_code == 422  # Missing required query parameter


# ============================================================================
# API 3: Safety Score Tests
# ============================================================================


def test_calculate_safety_safe_task():
    """Test safety calculation for safe autonomous execution"""
    start_time = time.time()

    response = client.post(
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
        execution_time_ms < 100
    ), f"Performance target missed: {execution_time_ms:.2f}ms"

    # Assert response schema
    assert "safety_score" in data
    assert "safety_rating" in data
    assert "can_execute_autonomously" in data
    assert "requires_human_review" in data
    assert "historical_success_rate" in data
    assert "risk_factors" in data
    assert "safety_checks_required" in data

    # Low complexity, small scope should be safe
    assert data["safety_score"] >= 0.6
    assert data["safety_rating"] in ["safe", "caution"]
    assert data["can_execute_autonomously"] is True

    # Should have some safety checks
    assert isinstance(data["safety_checks_required"], list)
    assert len(data["safety_checks_required"]) > 0


def test_calculate_safety_risky_task():
    """Test safety calculation for risky task - high complexity, wide scope"""
    response = client.post(
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

    # Risk factors should have severity and mitigation
    for risk in data["risk_factors"]:
        assert "factor" in risk
        assert "severity" in risk
        assert "likelihood" in risk
        assert "mitigation" in risk
        assert risk["severity"] in ["low", "medium", "high"]


def test_calculate_safety_moderate_task():
    """Test safety calculation for moderate complexity task"""
    response = client.post(
        "/api/autonomous/calculate/safety?"
        "task_type=code_generation&"
        "complexity=0.5&"
        "change_scope=module"
    )

    assert response.status_code == 200
    data = response.json()

    # Moderate task should get caution rating
    assert 0.4 <= data["safety_score"] <= 0.9
    assert data["safety_rating"] in ["safe", "caution"]

    # Should have reasonable success rate
    assert data["historical_success_rate"] >= 0.5


def test_calculate_safety_invalid_complexity():
    """Test safety calculation with out-of-range complexity"""
    # Test complexity > 1.0
    response = client.post(
        "/api/autonomous/calculate/safety?"
        "task_type=bug_fix&"
        "complexity=1.5&"  # Invalid: >1.0
        "change_scope=single_file"
    )

    assert response.status_code == 422  # Validation error


def test_calculate_safety_missing_parameters():
    """Test safety calculation with missing required parameters"""
    response = client.post(
        "/api/autonomous/calculate/safety?task_type=bug_fix"
        # Missing: complexity, change_scope
    )

    assert response.status_code == 422  # Validation error


# ============================================================================
# API 4: Success Patterns Tests
# ============================================================================


def test_get_success_patterns_default():
    """Test retrieving success patterns with default filters"""
    start_time = time.time()

    response = client.get("/api/autonomous/patterns/success")

    execution_time_ms = (time.time() - start_time) * 1000

    # Assert response success
    assert response.status_code == 200
    data = response.json()

    # Assert performance target
    assert (
        execution_time_ms < 100
    ), f"Performance target missed: {execution_time_ms:.2f}ms"

    # Should return list of patterns
    assert isinstance(data, list)

    # Each pattern should have required fields
    for pattern in data:
        assert "pattern_id" in pattern
        assert "pattern_name" in pattern
        assert "pattern_hash" in pattern
        assert "task_type" in pattern
        assert "agent_sequence" in pattern
        assert "success_rate" in pattern
        assert "average_duration_ms" in pattern
        assert "confidence_score" in pattern

        # Default min_success_rate is 0.8
        assert pattern["success_rate"] >= 0.8

        # Agent sequence should be non-empty
        assert len(pattern["agent_sequence"]) > 0


def test_get_success_patterns_with_filters():
    """Test retrieving patterns with custom filters"""
    response = client.get(
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


def test_get_success_patterns_high_threshold():
    """Test retrieving only highest quality patterns"""
    response = client.get(
        "/api/autonomous/patterns/success?min_success_rate=0.95&limit=10"
    )

    assert response.status_code == 200
    data = response.json()

    # All patterns should be very high quality
    for pattern in data:
        assert pattern["success_rate"] >= 0.95
        assert pattern["confidence_score"] >= 0.8


def test_get_success_patterns_invalid_success_rate():
    """Test with invalid success rate (out of range)"""
    response = client.get("/api/autonomous/patterns/success?min_success_rate=1.5")

    assert response.status_code == 422  # Validation error


def test_get_success_patterns_invalid_limit():
    """Test with invalid limit (exceeds max)"""
    response = client.get("/api/autonomous/patterns/success?limit=500")

    assert response.status_code == 422  # Validation error (max is 100)


# ============================================================================
# API 5: Pattern Ingestion Tests
# ============================================================================


def test_ingest_pattern_success(execution_pattern_success):
    """Test ingesting successful execution pattern"""
    start_time = time.time()

    response = client.post(
        "/api/autonomous/patterns/ingest", json=execution_pattern_success
    )

    execution_time_ms = (time.time() - start_time) * 1000

    # Assert response success
    assert response.status_code == 200
    data = response.json()

    # Assert performance target
    assert (
        execution_time_ms < 100
    ), f"Performance target missed: {execution_time_ms:.2f}ms"

    # Assert response schema
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


def test_ingest_pattern_failure():
    """Test ingesting failed execution pattern"""
    failed_pattern = {
        "execution_id": str(uuid4()),
        "task_characteristics": {
            "task_description": "Complex database migration",
            "task_type": TaskType.ARCHITECTURE.value,
            "complexity": TaskComplexity.CRITICAL.value,
            "change_scope": ChangeScope.SYSTEM_WIDE.value,
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

    response = client.post("/api/autonomous/patterns/ingest", json=failed_pattern)

    assert response.status_code == 200
    data = response.json()

    # Failure should still create/update pattern
    assert "pattern_id" in data
    assert "total_executions" in data

    # Success rate should reflect the failure
    assert data["success_rate"] < 1.0


def test_ingest_pattern_invalid_structure():
    """Test ingesting pattern with invalid structure"""
    invalid_pattern = {
        "execution_id": str(uuid4()),
        # Missing required fields: task_characteristics, execution_details, outcome
    }

    response = client.post("/api/autonomous/patterns/ingest", json=invalid_pattern)

    assert response.status_code == 422  # Validation error


# ============================================================================
# Health & Stats Tests
# ============================================================================


def test_autonomous_health_check():
    """Test autonomous APIs health endpoint"""
    response = client.get("/api/autonomous/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "autonomous-execution-api"
    assert "endpoints" in data
    assert len(data["endpoints"]) == 5  # 5 core endpoints


def test_autonomous_stats():
    """Test autonomous APIs statistics endpoint"""
    response = client.get("/api/autonomous/stats")

    assert response.status_code == 200
    data = response.json()

    assert "total_patterns" in data
    assert "total_agents" in data
    assert "average_pattern_success_rate" in data
    assert data["total_patterns"] >= 0
    assert data["total_agents"] > 0


# ============================================================================
# Performance Regression Tests
# ============================================================================


def test_all_endpoints_meet_performance_target(
    simple_task_characteristics, execution_pattern_success
):
    """Verify all endpoints consistently meet <100ms performance target"""

    endpoints_to_test = [
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
    ]

    failed_targets = []

    for method, endpoint, payload in endpoints_to_test:
        # Run 3 times to check consistency
        execution_times = []

        for _ in range(3):
            start_time = time.time()

            if method == "POST":
                response = client.post(endpoint, json=payload)
            else:
                response = client.get(endpoint)

            execution_time_ms = (time.time() - start_time) * 1000
            execution_times.append(execution_time_ms)

            assert response.status_code == 200

        avg_time = sum(execution_times) / len(execution_times)

        if avg_time >= 100:
            failed_targets.append((endpoint, avg_time, execution_times))

    # Assert all endpoints met target
    assert len(failed_targets) == 0, "Performance targets failed:\n" + "\n".join(
        f"  {endpoint}: avg={avg:.2f}ms, times={times}"
        for endpoint, avg, times in failed_targets
    )


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_workflow_agent_to_pattern():
    """Test complete workflow: predict agent → estimate time → assess safety → ingest pattern"""

    # Step 1: Predict optimal agent
    task_chars = {
        "task_description": "Implement user authentication with JWT tokens",
        "task_type": TaskType.CODE_GENERATION.value,
        "complexity": TaskComplexity.MODERATE.value,
        "change_scope": ChangeScope.MODULE.value,
        "estimated_files_affected": 4,
        "requires_testing": True,
        "requires_validation": True,
    }

    agent_response = client.post("/api/autonomous/predict/agent", json=task_chars)
    assert agent_response.status_code == 200
    agent_data = agent_response.json()
    selected_agent = agent_data["recommended_agent"]

    # Step 2: Estimate execution time
    time_response = client.post(
        f"/api/autonomous/predict/time?agent={selected_agent}", json=task_chars
    )
    assert time_response.status_code == 200
    time_data = time_response.json()
    estimated_duration = time_data["estimated_duration_ms"]

    # Step 3: Assess safety
    safety_response = client.post(
        "/api/autonomous/calculate/safety?"
        f"task_type={task_chars['task_type']}&"
        f"complexity=0.5&"
        f"change_scope={task_chars['change_scope']}&"
        f"agent={selected_agent}"
    )
    assert safety_response.status_code == 200
    safety_data = safety_response.json()

    # Step 4: Simulate execution and ingest pattern
    execution_pattern = {
        "execution_id": str(uuid4()),
        "task_characteristics": task_chars,
        "execution_details": {
            "agent_used": selected_agent,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "steps_executed": ["plan", "implement", "test"],
            "files_modified": ["src/auth.py", "tests/test_auth.py"],
        },
        "outcome": {
            "success": True,
            "duration_ms": estimated_duration,
            "quality_score": 0.85,
        },
    }

    pattern_response = client.post(
        "/api/autonomous/patterns/ingest", json=execution_pattern
    )
    assert pattern_response.status_code == 200
    pattern_data = pattern_response.json()

    # Verify complete workflow
    assert selected_agent  # Agent was selected
    assert estimated_duration > 0  # Time was estimated
    assert "safety_score" in safety_data  # Safety was assessed
    assert "pattern_id" in pattern_data  # Pattern was ingested


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
