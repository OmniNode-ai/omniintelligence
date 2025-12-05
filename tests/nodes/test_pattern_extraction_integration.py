"""
Integration Tests for Pattern Extraction System

Tests the complete pipeline with real-world scenarios.
Migrated from omniarchon to omniintelligence.
"""

import asyncio
import json
import sys

import pytest

# Import from omniintelligence package
from omniintelligence.nodes.pattern_extraction.node_pattern_assembler_orchestrator import (
    ModelPatternExtractionInput,
    NodePatternAssemblerOrchestrator,
)


@pytest.mark.asyncio
async def test_code_generation_scenario():
    """Test complete code generation scenario."""
    orchestrator = NodePatternAssemblerOrchestrator()

    input_data = ModelPatternExtractionInput(
        request_text="Generate and create async function to implement database connection with exception handling and retry logic",
        execution_trace=json.dumps(
            {
                "events": [
                    {
                        "type": "function_call",
                        "function": "analyze_requirements",
                        "timestamp": "2025-10-02T10:00:00Z",
                        "duration_ms": 15.3,
                    },
                    {
                        "type": "function_call",
                        "function": "generate_async_function",
                        "duration_ms": 45.2,
                    },
                    {
                        "type": "function_call",
                        "function": "add_exception_handling",
                        "duration_ms": 12.5,
                    },
                    {
                        "type": "function_call",
                        "function": "add_retry_logic",
                        "duration_ms": 18.7,
                    },
                    {"type": "status", "status": "completed", "duration_ms": 5.1},
                ]
            }
        ),
        execution_result="""
        Function generated successfully with following features:
        - Async/await pattern implemented
        - Try/except exception handling added
        - Exponential backoff retry logic implemented
        - Connection pooling support added
        - Proper resource cleanup with context manager
        """,
        success_criteria=[
            "generated",
            "async",
            "exception handling",
            "retry logic",
            "completed",
        ],
        trace_format="json",
    )

    result = await orchestrator.execute_orchestration(input_data)

    # Assertions
    assert (
        result.intent == "code_generation"
    ), f"Expected code_generation, got {result.intent}"
    assert (
        result.intent_confidence >= 0.8
    ), f"Low confidence: {result.intent_confidence}"
    assert len(result.keywords) >= 5, f"Too few keywords: {len(result.keywords)}"
    assert result.success_status is True, "Expected success status"
    assert (
        len(result.matched_criteria) >= 4
    ), f"Expected 4+ matches, got {len(result.matched_criteria)}"


@pytest.mark.asyncio
async def test_debugging_scenario():
    """Test complete debugging scenario."""
    orchestrator = NodePatternAssemblerOrchestrator()

    input_data = ModelPatternExtractionInput(
        request_text="Debug authentication failure in JWT token validation",
        execution_trace=json.dumps(
            {
                "events": [
                    {
                        "type": "function_call",
                        "function": "load_config",
                        "duration_ms": 5.2,
                    },
                    {
                        "type": "function_call",
                        "function": "validate_jwt_token",
                        "duration_ms": 25.7,
                    },
                    {
                        "type": "error",
                        "function": "verify_signature",
                        "error": "Invalid signature - token expired",
                        "duration_ms": 3.1,
                    },
                    {
                        "type": "function_call",
                        "function": "check_token_expiry",
                        "duration_ms": 2.3,
                    },
                    {
                        "type": "error",
                        "error": "Token expired 120 seconds ago",
                        "duration_ms": 1.2,
                    },
                ]
            }
        ),
        execution_result="Error: JWT token expired. Token was issued at 2025-10-02T08:00:00Z and expired at 2025-10-02T09:00:00Z. Current time: 2025-10-02T09:02:00Z.",
        success_criteria=["fixed", "validated", "authentication working"],
        trace_format="json",
    )

    result = await orchestrator.execute_orchestration(input_data)

    # Assertions
    assert result.intent == "debugging", f"Expected debugging, got {result.intent}"
    assert len(result.trace_events) > 0, "Expected trace events"
    # Error events are in trace_events, not a separate field
    error_count = sum(
        1 for e in result.trace_events if e.get("type") == "error" or e.get("error")
    )
    assert error_count > 0, "Expected error events in trace"
    assert result.success_status is False, "Expected failure (not fixed)"


@pytest.mark.asyncio
async def test_testing_scenario():
    """Test complete testing scenario."""
    orchestrator = NodePatternAssemblerOrchestrator()

    input_data = ModelPatternExtractionInput(
        request_text="Run integration tests for payment processing API with edge cases",
        execution_trace="""
        [INFO] Test suite started: payment_processing_tests
        [INFO] Function: test_valid_payment - PASSED (Duration: 125.5 ms)
        [INFO] Function: test_invalid_card - PASSED (Duration: 95.3 ms)
        [INFO] Function: test_expired_card - PASSED (Duration: 87.2 ms)
        [INFO] Function: test_insufficient_funds - PASSED (Duration: 102.1 ms)
        [ERROR] Function: test_network_timeout - FAILED (Error: Timeout after 30s)
        [INFO] Status: 4/5 tests passed
        """,
        execution_result="Test suite completed: 4 passed, 1 failed. Coverage: 85%. Network timeout test needs retry logic.",
        success_criteria=["all tests passed", r"\d+ passed", "coverage"],
        trace_format="log",
    )

    result = await orchestrator.execute_orchestration(input_data)

    # Assertions
    assert result.intent == "testing", f"Expected testing, got {result.intent}"
    assert len(result.keywords) > 0, "Expected keywords"


@pytest.mark.asyncio
async def test_empty_input_handling():
    """Test handling of empty/invalid inputs."""
    orchestrator = NodePatternAssemblerOrchestrator()

    input_data = ModelPatternExtractionInput(
        request_text="",
        execution_trace="",
        execution_result="",
        success_criteria=[],
    )

    result = await orchestrator.execute_orchestration(input_data)

    # Should handle gracefully
    assert (
        result.intent == "unknown"
    ), f"Expected unknown for empty input, got {result.intent}"


@pytest.mark.asyncio
async def test_parallel_execution_performance():
    """Test parallel execution performance advantage."""
    orchestrator = NodePatternAssemblerOrchestrator()

    # Large context to test performance
    large_context = (
        """
    Implementing comprehensive authentication system with OAuth2, JWT tokens,
    refresh token rotation, role-based access control, multi-factor authentication,
    session management, password hashing with bcrypt, security headers, CORS configuration,
    rate limiting, brute force protection, account lockout policies, and audit logging.
    """
        * 10
    )

    input_data = ModelPatternExtractionInput(
        request_text=large_context,
        execution_trace=json.dumps(
            {"events": [{"type": "test", "duration_ms": 1.0}] * 50}
        ),
        execution_result=large_context,
        success_criteria=["oauth2", "jwt", "security"],
        trace_format="json",
    )

    # Run multiple times for average
    times = []
    for _ in range(5):
        result = await orchestrator.execute_orchestration(input_data)
        times.append(result.metadata["processing_time_ms"])

    avg_time = sum(times) / len(times)

    assert avg_time < 100, f"Performance degraded: {avg_time}ms > 100ms target"


@pytest.mark.asyncio
async def test_correlation_id_propagation():
    """Test correlation ID propagation through pipeline."""
    orchestrator = NodePatternAssemblerOrchestrator()

    test_correlation_id = "test-correlation-12345"

    input_data = ModelPatternExtractionInput(
        request_text="Test correlation ID tracking",
        execution_trace=json.dumps({"events": []}),
        execution_result="Test completed",
        success_criteria=["completed"],
        correlation_id=test_correlation_id,
    )

    result = await orchestrator.execute_orchestration(input_data)

    # Verify correlation ID preserved
    assert result.correlation_id == test_correlation_id, "Correlation ID not preserved"


class TestPatternExtractionIntegration:
    """Test class for pattern extraction integration tests."""

    @pytest.mark.asyncio
    async def test_code_generation_scenario(self):
        """Test complete code generation scenario."""
        await test_code_generation_scenario()

    @pytest.mark.asyncio
    async def test_debugging_scenario(self):
        """Test complete debugging scenario."""
        await test_debugging_scenario()

    @pytest.mark.asyncio
    async def test_testing_scenario(self):
        """Test complete testing scenario."""
        await test_testing_scenario()

    @pytest.mark.asyncio
    async def test_empty_input_handling(self):
        """Test handling of empty/invalid inputs."""
        await test_empty_input_handling()

    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self):
        """Test parallel execution performance advantage."""
        await test_parallel_execution_performance()

    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self):
        """Test correlation ID propagation through pipeline."""
        await test_correlation_id_propagation()


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 70)
    print("PATTERN EXTRACTION INTEGRATION TESTS")
    print("=" * 70)

    tests = [
        test_code_generation_scenario,
        test_debugging_scenario,
        test_testing_scenario,
        test_empty_input_handling,
        test_parallel_execution_performance,
        test_correlation_id_propagation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            print(f"PASSED: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAILED: {test.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__} - {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    # Support running as a script or via pytest
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
