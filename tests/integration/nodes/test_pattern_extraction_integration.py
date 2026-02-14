"""Integration Tests for Pattern Assembly Orchestration.

Tests the complete pattern assembly orchestrator pipeline with real-world
scenarios. Calls handle_pattern_assembly_orchestrate directly (without
injected compute nodes) to verify orchestration workflow, input validation,
output structure, correlation ID propagation, and performance.

The orchestrator coordinates:
1. Trace parsing (execution_trace_parser_compute)
2. Intent classification (node_intent_classifier_compute)
3. Criteria matching (success_criteria_matcher_compute)
4. Pattern assembly (internal)

Without injected compute nodes, the orchestrator uses simulated fallback
results for each step, which is sufficient for testing the orchestration
workflow itself.
"""

import uuid

import pytest

from omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers.handler_orchestrate import (
    handle_pattern_assembly_orchestrate,
)
from omniintelligence.nodes.node_pattern_assembler_orchestrator.models import (
    ModelPatternAssemblyInput,
    SuccessCriterionDict,
)

# =============================================================================
# Standalone Test Functions
# =============================================================================


@pytest.mark.integration
async def test_code_generation_scenario() -> None:
    """Test complete code generation scenario.

    Verifies the orchestrator produces a valid assembled pattern from
    code-generation-related content and execution traces.
    """
    correlation_id = str(uuid.uuid4())

    input_data = ModelPatternAssemblyInput(
        raw_data={
            "content": (
                "Generate and create async function to implement database "
                "connection with exception handling and retry logic"
            ),
            "execution_traces": [
                {
                    "operation_name": "analyze_requirements",
                    "duration_ms": 15.3,
                    "status": "ok",
                },
                {
                    "operation_name": "generate_async_function",
                    "duration_ms": 45.2,
                    "status": "ok",
                },
                {
                    "operation_name": "add_exception_handling",
                    "duration_ms": 12.5,
                    "status": "ok",
                },
                {
                    "operation_name": "add_retry_logic",
                    "duration_ms": 18.7,
                    "status": "ok",
                },
            ],
        },
        success_criteria=[
            SuccessCriterionDict(
                criterion_id="generated",
                field="status",
                operator="equals",
                expected_value="success",
            ),
            SuccessCriterionDict(
                criterion_id="async",
                field="output_type",
                operator="contains",
                expected_value="async",
            ),
            SuccessCriterionDict(
                criterion_id="exception_handling",
                field="features",
                operator="contains",
                expected_value="exception",
            ),
            SuccessCriterionDict(
                criterion_id="retry_logic",
                field="features",
                operator="contains",
                expected_value="retry",
            ),
            SuccessCriterionDict(
                criterion_id="completed",
                field="status",
                operator="equals",
                expected_value="completed",
            ),
        ],
        correlation_id=correlation_id,
    )

    result = await handle_pattern_assembly_orchestrate(input_data)

    # Verify success
    assert result.success is True, f"Expected success, got metadata: {result.metadata}"
    assert result.correlation_id == correlation_id

    # Verify assembled pattern structure
    pattern = result.assembled_pattern
    assert pattern.get("pattern_id"), "Missing pattern_id"
    assert pattern.get("pattern_type") == "generative", (
        f"Expected generative pattern type for code_generation intent, "
        f"got {pattern.get('pattern_type')}"
    )
    assert pattern.get("confidence", 0) >= 0.5, (
        f"Low confidence: {pattern.get('confidence')}"
    )
    assert pattern.get("validity") is True, "Pattern should be valid"

    # Verify component results
    components = result.component_results
    assert components.get("primary_intent") == "code_generation"
    assert components.get("intent_confidence", 0) >= 0.5
    assert components.get("trace_events_parsed", 0) >= 4
    assert components.get("criteria_matched", 0) >= 5

    # Verify metadata
    assert result.metadata is not None
    assert result.metadata.get("status") == "completed"
    assert result.metadata.get("processing_time_ms", -1) >= 0


@pytest.mark.integration
async def test_debugging_scenario() -> None:
    """Test complete debugging scenario.

    Verifies the orchestrator handles debugging-related content with
    error traces and produces a valid assembled pattern.
    """
    input_data = ModelPatternAssemblyInput(
        raw_data={
            "content": "Debug authentication failure in JWT token validation",
            "execution_traces": [
                {
                    "operation_name": "load_config",
                    "duration_ms": 5.2,
                    "status": "ok",
                },
                {
                    "operation_name": "validate_jwt_token",
                    "duration_ms": 25.7,
                    "status": "error",
                    "tags": {"error": "Invalid signature"},
                },
                {
                    "operation_name": "verify_signature",
                    "duration_ms": 3.1,
                    "status": "error",
                    "tags": {"error": "Token expired"},
                },
                {
                    "operation_name": "check_token_expiry",
                    "duration_ms": 2.3,
                    "status": "error",
                    "tags": {"error": "Token expired 120 seconds ago"},
                },
            ],
        },
        success_criteria=[
            SuccessCriterionDict(
                criterion_id="fixed",
                field="status",
                operator="equals",
                expected_value="fixed",
            ),
            SuccessCriterionDict(
                criterion_id="validated",
                field="status",
                operator="equals",
                expected_value="validated",
            ),
        ],
        correlation_id=str(uuid.uuid4()),
    )

    result = await handle_pattern_assembly_orchestrate(input_data)

    # Verify success (orchestration succeeded even if debugging scenario found issues)
    assert result.success is True, f"Expected success, got metadata: {result.metadata}"

    # Verify assembled pattern has valid structure
    pattern = result.assembled_pattern
    assert pattern.get("pattern_id"), "Missing pattern_id"
    assert pattern.get("pattern_type"), "Missing pattern_type"
    assert pattern.get("validity") is True, "Pattern should be valid"

    # Verify component results include trace data
    components = result.component_results
    assert components.get("trace_events_parsed", 0) > 0, "Expected parsed trace events"


@pytest.mark.integration
async def test_testing_scenario() -> None:
    """Test complete testing scenario.

    Verifies the orchestrator handles test-related content with
    structured trace data representing test execution results.
    """
    input_data = ModelPatternAssemblyInput(
        raw_data={
            "content": (
                "Run integration tests for payment processing API with edge cases. "
                "Test suite completed: 4 passed, 1 failed. Coverage: 85%. "
                "Network timeout test needs retry logic."
            ),
            "execution_traces": [
                {
                    "operation_name": "test_valid_payment",
                    "duration_ms": 125.5,
                    "status": "passed",
                },
                {
                    "operation_name": "test_invalid_card",
                    "duration_ms": 95.3,
                    "status": "passed",
                },
                {
                    "operation_name": "test_expired_card",
                    "duration_ms": 87.2,
                    "status": "passed",
                },
                {
                    "operation_name": "test_insufficient_funds",
                    "duration_ms": 102.1,
                    "status": "passed",
                },
                {
                    "operation_name": "test_network_timeout",
                    "duration_ms": 30000.0,
                    "status": "failed",
                    "tags": {"error": "Timeout after 30s"},
                },
            ],
        },
        success_criteria=[
            SuccessCriterionDict(
                criterion_id="tests_passed",
                field="status",
                operator="contains",
                expected_value="passed",
            ),
            SuccessCriterionDict(
                criterion_id="coverage",
                field="coverage",
                operator="greater_than",
                expected_value=80,
            ),
        ],
        correlation_id=str(uuid.uuid4()),
    )

    result = await handle_pattern_assembly_orchestrate(input_data)

    # Verify success
    assert result.success is True, f"Expected success, got metadata: {result.metadata}"

    # Verify pattern has content
    pattern = result.assembled_pattern
    assert pattern.get("pattern_id"), "Missing pattern_id"
    assert len(pattern.get("tags", [])) > 0, "Expected tags"

    # Verify component results
    components = result.component_results
    assert components.get("primary_intent"), "Expected primary_intent"


@pytest.mark.integration
async def test_empty_input_handling() -> None:
    """Test handling of empty/invalid inputs.

    Verifies the orchestrator returns a structured validation error
    when input lacks both content and execution traces.
    """
    input_data = ModelPatternAssemblyInput(
        raw_data={},
        success_criteria=[],
    )

    result = await handle_pattern_assembly_orchestrate(input_data)

    # Should return structured error (never raises)
    assert result.success is False, "Expected failure for empty input"
    assert result.metadata is not None
    assert result.metadata.get("status") == "validation_failed"


@pytest.mark.integration
async def test_parallel_execution_performance() -> None:
    """Test execution performance with large input.

    Verifies the orchestrator processes large contexts within
    acceptable time limits (under 500ms average across 5 runs).
    """
    large_context = (
        "Implementing comprehensive authentication system with OAuth2, JWT tokens, "
        "refresh token rotation, role-based access control, multi-factor authentication, "
        "session management, password hashing with bcrypt, security headers, CORS configuration, "
        "rate limiting, brute force protection, account lockout policies, and audit logging. "
    ) * 10

    correlation_id = str(uuid.uuid4())
    input_data = ModelPatternAssemblyInput(
        raw_data={
            "content": large_context,
            "execution_traces": [
                {
                    "operation_name": f"test_step_{i}",
                    "duration_ms": 1.0,
                    "status": "ok",
                }
                for i in range(50)
            ],
        },
        success_criteria=[
            SuccessCriterionDict(
                criterion_id="oauth2",
                field="features",
                operator="contains",
                expected_value="oauth2",
            ),
            SuccessCriterionDict(
                criterion_id="jwt",
                field="features",
                operator="contains",
                expected_value="jwt",
            ),
            SuccessCriterionDict(
                criterion_id="security",
                field="features",
                operator="contains",
                expected_value="security",
            ),
        ],
        correlation_id=correlation_id,
    )

    # Run multiple times for average
    times: list[int] = []
    for _ in range(5):
        result = await handle_pattern_assembly_orchestrate(input_data)
        assert result.success is True, (
            f"Expected success, got metadata: {result.metadata}"
        )
        assert result.metadata is not None
        times.append(result.metadata.get("processing_time_ms", 0))

    avg_time = sum(times) / len(times)
    assert avg_time < 500, f"Performance degraded: {avg_time}ms > 500ms target"


@pytest.mark.integration
async def test_correlation_id_propagation() -> None:
    """Test correlation ID propagation through pipeline.

    Verifies the correlation ID from input is preserved in the output
    across all orchestration steps.
    """
    test_correlation_id = str(uuid.uuid4())

    input_data = ModelPatternAssemblyInput(
        raw_data={
            "content": "Test correlation ID tracking through the orchestration pipeline",
        },
        success_criteria=[
            SuccessCriterionDict(
                criterion_id="completed",
                field="status",
                operator="equals",
                expected_value="completed",
            ),
        ],
        correlation_id=test_correlation_id,
    )

    result = await handle_pattern_assembly_orchestrate(input_data)

    # Verify correlation ID preserved
    assert result.correlation_id == test_correlation_id, (
        f"Correlation ID not preserved: expected {test_correlation_id}, "
        f"got {result.correlation_id}"
    )


# =============================================================================
# Test Class (delegates to standalone functions)
# =============================================================================


class TestPatternExtractionIntegration:
    """Test class for pattern extraction integration tests."""

    async def test_code_generation_scenario(self) -> None:
        """Test complete code generation scenario."""
        await test_code_generation_scenario()

    async def test_debugging_scenario(self) -> None:
        """Test complete debugging scenario."""
        await test_debugging_scenario()

    async def test_testing_scenario(self) -> None:
        """Test complete testing scenario."""
        await test_testing_scenario()

    async def test_empty_input_handling(self) -> None:
        """Test handling of empty/invalid inputs."""
        await test_empty_input_handling()

    async def test_parallel_execution_performance(self) -> None:
        """Test parallel execution performance advantage."""
        await test_parallel_execution_performance()

    async def test_correlation_id_propagation(self) -> None:
        """Test correlation ID propagation through pipeline."""
        await test_correlation_id_propagation()
