#!/usr/bin/env python3
"""
Integration Tests for Pattern Extraction System

Tests the complete pipeline with real-world scenarios.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nodes.node_pattern_assembler_orchestrator import (
    ModelPatternExtractionInput,
    NodePatternAssemblerOrchestrator,
)


async def test_code_generation_scenario():
    """Test complete code generation scenario."""
    print("\n" + "=" * 70)
    print("Test 1: Code Generation Scenario")
    print("=" * 70)

    orchestrator = NodePatternAssemblerOrchestrator()

    input_data = ModelPatternExtractionInput(
        request_text="Generate async function for database connection with error handling and retry logic",
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
                        "function": "add_error_handling",
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
        - Try/except error handling added
        - Exponential backoff retry logic implemented
        - Connection pooling support added
        - Proper resource cleanup with context manager
        """,
        success_criteria=[
            "generated",
            "async",
            "error handling",
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

    # Print results
    print(f"✅ Intent: {result.intent} ({result.intent_confidence:.2%} confidence)")
    print(f"✅ Keywords: {', '.join(result.keywords[:8])}")
    print(f"✅ Phrases: {', '.join(result.phrases[:3])}")
    print(f"✅ Execution flow: {' → '.join(result.execution_flow)}")
    print(
        f"✅ Success: {result.success_status} ({result.success_confidence:.2%} confidence)"
    )
    print(f"✅ Matched criteria: {', '.join(result.matched_criteria)}")
    print(f"✅ Processing time: {result.metadata['processing_time_ms']:.2f}ms")


async def test_debugging_scenario():
    """Test complete debugging scenario."""
    print("\n" + "=" * 70)
    print("Test 2: Debugging Scenario")
    print("=" * 70)

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

    # Print results
    print(f"✅ Intent: {result.intent} ({result.intent_confidence:.2%} confidence)")
    print(f"✅ Keywords: {', '.join(result.keywords[:8])}")
    print(f"✅ Error events in trace: {error_count}")
    print(f"✅ Execution flow: {' → '.join(result.execution_flow)}")
    print(f"✅ Success: {result.success_status} (correctly identified failure)")
    print(f"✅ Timing stats: {list(result.timing_summary.keys())[:3]}")
    print(f"✅ Processing time: {result.metadata['processing_time_ms']:.2f}ms")


async def test_testing_scenario():
    """Test complete testing scenario."""
    print("\n" + "=" * 70)
    print("Test 3: Testing Scenario")
    print("=" * 70)

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

    # Print results
    print(f"✅ Intent: {result.intent} ({result.intent_confidence:.2%} confidence)")
    print(f"✅ Keywords: {', '.join(result.keywords[:8])}")
    print(f"✅ Phrases: {', '.join(result.phrases[:3])}")
    print(f"✅ Success: {result.success_status}")
    print(f"✅ Matched criteria: {result.matched_criteria}")
    print(f"✅ Processing time: {result.metadata['processing_time_ms']:.2f}ms")


async def test_empty_input_handling():
    """Test handling of empty/invalid inputs."""
    print("\n" + "=" * 70)
    print("Test 4: Empty Input Handling")
    print("=" * 70)

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
    print("✅ Gracefully handled empty input")
    print(f"✅ Intent: {result.intent}")
    print(f"✅ Success: {result.success_status} (no criteria to fail)")
    print(f"✅ Processing time: {result.metadata['processing_time_ms']:.2f}ms")


async def test_parallel_execution_performance():
    """Test parallel execution performance advantage."""
    print("\n" + "=" * 70)
    print("Test 5: Parallel Execution Performance")
    print("=" * 70)

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
    print(f"✅ Average processing time (5 runs): {avg_time:.2f}ms")
    print(f"✅ Min time: {min(times):.2f}ms")
    print(f"✅ Max time: {max(times):.2f}ms")
    print(
        f"✅ Parallel execution enabled: {result.metadata.get('parallel_execution', False)}"
    )

    assert avg_time < 100, f"Performance degraded: {avg_time}ms > 100ms target"
    print("✅ Performance target met (<100ms)")


async def test_correlation_id_propagation():
    """Test correlation ID propagation through pipeline."""
    print("\n" + "=" * 70)
    print("Test 6: Correlation ID Propagation")
    print("=" * 70)

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
    print(f"✅ Correlation ID preserved: {result.correlation_id}")
    print("✅ Traceable through all nodes")


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
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
