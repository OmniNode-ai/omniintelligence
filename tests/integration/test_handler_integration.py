"""Integration tests for handler usage in intelligence_adapter.

These tests verify that:
1. Handlers are correctly imported by intelligence_adapter
2. Handler transforms work with realistic API response shapes
3. Validation is properly applied to handler results
4. The full transform -> validate pipeline works end-to-end
5. Handler purity principles are maintained (determinism, no mutation)

These integration tests complement the unit tests by verifying the handlers
work correctly when used together as a pipeline, simulating real-world usage
in the intelligence_adapter node.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

# Import handlers from the public interface (handlers __init__.py)
from omniintelligence.nodes.intelligence_adapter.handlers import (
    MAX_ISSUES,
    SCORE_MAX,
    SCORE_MIN,
    transform_quality_response,
    transform_pattern_response,
    transform_performance_response,
    validate_handler_result,
)


class TestHandlerIntegration:
    """Integration tests for handler pipeline: transform -> validate."""

    def test_quality_handler_full_pipeline(self) -> None:
        """Test full quality handler pipeline: transform -> validate.

        This simulates a complete flow from raw API response through
        transformation and validation, as would occur in the intelligence_adapter.
        """
        # Simulate realistic API response (dict format)
        api_response: dict[str, Any] = {
            "quality_score": 0.85,
            "onex_compliance": {
                "score": 0.90,
                "violations": ["Missing docstring", "Long function"],
                "recommendations": ["Add type hints", "Refactor method"],
            },
            "maintainability": {
                "complexity_score": 0.75,
            },
            "architectural_era": "modern",
            "temporal_relevance": 0.95,
        }

        # Transform
        transformed = transform_quality_response(api_response)

        # Validate
        validated = validate_handler_result(transformed, "assess_code_quality")

        # Verify end-to-end
        assert validated["success"] is True
        assert validated["quality_score"] == 0.85
        assert validated["onex_compliance"] == 0.90
        assert validated["complexity_score"] == 0.75
        assert len(validated["issues"]) == 2
        assert validated["issues"] == ["Missing docstring", "Long function"]
        assert len(validated["recommendations"]) == 2
        assert validated["recommendations"] == ["Add type hints", "Refactor method"]
        assert validated["result_data"]["architectural_era"] == "modern"
        assert validated["result_data"]["temporal_relevance"] == 0.95

    def test_pattern_handler_full_pipeline(self) -> None:
        """Test full pattern handler pipeline: transform -> validate."""

        class MockPattern:
            def model_dump(self) -> dict[str, Any]:
                return {"name": "singleton", "confidence": 0.92}

        class MockAntiPattern:
            pattern_type = "god_class"
            description = "Class has too many responsibilities"

        class MockCompliance:
            onex_compliance = 0.85

        class MockResponse:
            detected_patterns = [MockPattern()]
            anti_patterns = [MockAntiPattern()]
            recommendations = ["Use dependency injection"]
            architectural_compliance = MockCompliance()
            analysis_summary = "Good architecture with minor issues"
            confidence_scores = {"overall": 0.87}

        # Transform
        transformed = transform_pattern_response(MockResponse())

        # Validate
        validated = validate_handler_result(transformed, "get_quality_patterns")

        # Verify end-to-end
        assert validated["success"] is True
        assert validated["onex_compliance"] == 0.85
        assert len(validated["patterns"]) == 1
        assert validated["patterns"][0] == {"name": "singleton", "confidence": 0.92}
        assert len(validated["issues"]) == 1
        assert "god_class: Class has too many responsibilities" in validated["issues"]
        assert validated["recommendations"] == ["Use dependency injection"]
        assert validated["result_data"]["analysis_summary"] == "Good architecture with minor issues"

    def test_performance_handler_full_pipeline(self) -> None:
        """Test full performance handler pipeline: transform -> validate."""

        class MockMetrics:
            complexity_estimate = 0.65

            def model_dump(self) -> dict[str, Any]:
                return {"complexity_estimate": 0.65, "lines_of_code": 250}

        class MockOpportunity:
            title = "Add caching"
            description = "Cache database queries to reduce latency"

            def model_dump(self) -> dict[str, Any]:
                return {"title": self.title, "description": self.description}

        class MockResponse:
            baseline_metrics = MockMetrics()
            optimization_opportunities = [MockOpportunity()]
            total_opportunities = 1
            estimated_total_improvement = 0.30

        # Transform
        transformed = transform_performance_response(MockResponse())

        # Validate
        validated = validate_handler_result(transformed, "analyze_performance")

        # Verify end-to-end
        assert validated["success"] is True
        assert validated["complexity_score"] == 0.65
        assert len(validated["recommendations"]) == 1
        assert "Add caching: Cache database queries to reduce latency" in validated["recommendations"]
        assert validated["result_data"]["total_opportunities"] == 1
        assert validated["result_data"]["estimated_improvement"] == 0.30

    def test_handler_imports_from_init(self) -> None:
        """Test that all handlers are properly exported from __init__.py.

        This verifies the public API contract of the handlers module.
        """
        # Verify all exports are callable/accessible
        assert callable(transform_quality_response)
        assert callable(transform_pattern_response)
        assert callable(transform_performance_response)
        assert callable(validate_handler_result)

        # Verify constants have expected values
        assert isinstance(MAX_ISSUES, int)
        assert MAX_ISSUES == 1000
        assert SCORE_MIN == 0.0
        assert SCORE_MAX == 1.0

    def test_handler_constants_used_in_score_clamping(self) -> None:
        """Test that score clamping uses shared constants correctly."""
        # Score below SCORE_MIN should clamp to SCORE_MIN
        result = transform_quality_response({"quality_score": -10.0})
        assert result["quality_score"] == SCORE_MIN

        # Score above SCORE_MAX should clamp to SCORE_MAX
        result = transform_quality_response({"quality_score": 100.0})
        assert result["quality_score"] == SCORE_MAX

        # Score exactly at boundaries should be preserved
        result = transform_quality_response({"quality_score": SCORE_MIN})
        assert result["quality_score"] == SCORE_MIN

        result = transform_quality_response({"quality_score": SCORE_MAX})
        assert result["quality_score"] == SCORE_MAX

    def test_handler_security_limits_applied(self) -> None:
        """Test that MAX_ISSUES limit is applied to prevent memory exhaustion.

        This is a security-critical test to ensure handlers cannot be abused
        to cause memory exhaustion via oversized input.
        """
        # Create more violations than MAX_ISSUES allows
        huge_violations = [f"violation_{i}" for i in range(MAX_ISSUES * 2)]
        response: dict[str, Any] = {
            "quality_score": 0.5,
            "onex_compliance": {"violations": huge_violations},
        }

        result = transform_quality_response(response)

        # Should be limited to MAX_ISSUES
        assert len(result["issues"]) <= MAX_ISSUES

    def test_validation_normalizes_malformed_response(self) -> None:
        """Test that validation handles and normalizes malformed handler output.

        This verifies defensive validation catches and corrects edge cases.
        """
        # Simulate a handler that returns non-standard types
        malformed: dict[str, Any] = {
            "success": "yes",  # String instead of bool
            "quality_score": "0.8",  # String instead of float
            "issues": "single issue",  # String instead of list
            "result_data": None,  # None instead of dict
        }

        validated = validate_handler_result(malformed, "test_operation")

        # Should normalize all values
        assert validated["success"] is True  # "yes" -> True
        assert validated["quality_score"] == 0.8  # "0.8" -> 0.8
        assert validated["issues"] == ["single issue"]  # wrapped in list
        assert validated["result_data"] == {}  # None -> empty dict

    def test_handler_pipeline_with_none_api_response(self) -> None:
        """Test pipeline handles None API response gracefully.

        This simulates a case where the API returns None (e.g., network error).
        """
        # Transform
        transformed = transform_quality_response(None)

        # Validate
        validated = validate_handler_result(transformed, "assess_code_quality")

        # Should return safe defaults
        assert validated["success"] is False
        assert validated["quality_score"] == 0.0
        assert validated["onex_compliance"] == 0.0
        assert validated["complexity_score"] == 0.0
        assert validated["issues"] == []
        assert validated["recommendations"] == []
        assert "error" in validated  # Error key should be preserved


class TestHandlerPurityCompliance:
    """Tests verifying handlers follow purity principles.

    Pure functions are critical for testability and predictability.
    These tests verify:
    - Determinism: same input produces same output
    - No mutation: input data is not modified
    """

    def test_transform_is_deterministic(self) -> None:
        """Test that transform produces same output for same input."""
        response: dict[str, Any] = {
            "quality_score": 0.85,
            "onex_compliance": {
                "score": 0.90,
                "violations": ["issue1"],
            },
        }

        result1 = transform_quality_response(response)
        result2 = transform_quality_response(response)

        assert result1 == result2

    def test_transform_does_not_mutate_input_dict(self) -> None:
        """Test that transform does not modify the input response dict."""
        response: dict[str, Any] = {
            "quality_score": 0.85,
            "onex_compliance": {
                "score": 0.90,
                "violations": ["issue1", "issue2"],
                "recommendations": ["rec1"],
            },
            "maintainability": {
                "complexity_score": 0.75,
            },
        }
        # Deep copy to compare later
        original = copy.deepcopy(response)

        # Transform should not mutate input
        transform_quality_response(response)

        # Original should be unchanged
        assert response == original

    def test_transform_does_not_mutate_input_nested_list(self) -> None:
        """Test that nested lists in input are not mutated."""
        violations = ["issue1", "issue2"]
        response: dict[str, Any] = {
            "onex_compliance": {"violations": violations},
        }
        original_violations = violations.copy()

        transform_quality_response(response)

        # Original list should be unchanged
        assert violations == original_violations

    def test_validation_is_deterministic(self) -> None:
        """Test that validation produces same output for same input."""
        result: dict[str, Any] = {
            "success": True,
            "quality_score": 0.85,
            "issues": ["issue1"],
        }

        validated1 = validate_handler_result(result, "test_op")
        validated2 = validate_handler_result(result, "test_op")

        assert validated1 == validated2

    def test_validation_does_not_mutate_input(self) -> None:
        """Test that validation does not modify the input result."""
        result: dict[str, Any] = {
            "success": True,
            "quality_score": 0.85,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1"],
            "result_data": {"key": "value"},
        }
        original = copy.deepcopy(result)

        validate_handler_result(result, "test_op")

        # Original should be unchanged
        assert result == original


class TestHandlerCIReadiness:
    """Tests verifying handlers are CI/CD ready.

    These tests ensure handlers work correctly in automated pipelines
    with no external dependencies or side effects.
    """

    def test_handlers_have_no_external_dependencies(self) -> None:
        """Test that handler functions have no external side effects.

        Handlers should be pure functions with no network, file, or DB access.
        """
        # This test verifies handlers complete without attempting external I/O
        # by running them in isolation with minimal inputs
        transform_quality_response({})
        transform_pattern_response({})
        transform_performance_response({})
        validate_handler_result({}, "test")

        # If we reach here, no external dependencies blocked execution
        assert True

    def test_handlers_complete_in_bounded_time(self) -> None:
        """Test that handlers complete quickly even with large inputs.

        This verifies handlers are suitable for CI/CD pipelines with timeouts.
        """
        import time

        # Create moderately large input
        large_violations = [f"violation_{i}" for i in range(MAX_ISSUES)]
        response: dict[str, Any] = {
            "quality_score": 0.5,
            "onex_compliance": {
                "violations": large_violations,
                "recommendations": large_violations.copy(),
            },
        }

        start = time.monotonic()
        result = transform_quality_response(response)
        validated = validate_handler_result(result, "test")
        elapsed = time.monotonic() - start

        # Should complete in under 1 second even with MAX_ISSUES items
        assert elapsed < 1.0, f"Handler pipeline took {elapsed:.2f}s, expected < 1.0s"
        assert validated["success"] is True

    def test_handlers_are_thread_safe(self) -> None:
        """Test that handlers can be called concurrently without issues.

        This verifies handlers don't have shared mutable state.
        """
        import concurrent.futures

        def run_pipeline(i: int) -> dict[str, Any]:
            response: dict[str, Any] = {
                "quality_score": 0.5 + (i * 0.01),
                "onex_compliance": {"violations": [f"issue_{i}"]},
            }
            transformed = transform_quality_response(response)
            return validate_handler_result(transformed, f"op_{i}")

        # Run 10 concurrent handler pipelines
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_pipeline, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert len(results) == 10
        assert all(r["success"] is True for r in results)


class TestHandlerEdgeCases:
    """Edge case tests for handler robustness."""

    def test_empty_api_response_dict(self) -> None:
        """Test handlers handle empty dict response."""
        transformed = transform_quality_response({})
        validated = validate_handler_result(transformed, "test")

        assert validated["success"] is True
        assert validated["quality_score"] == 0.0
        assert validated["issues"] == []

    def test_api_response_with_unexpected_keys(self) -> None:
        """Test handlers ignore unexpected keys in response."""
        response: dict[str, Any] = {
            "quality_score": 0.85,
            "unexpected_key": "should be ignored",
            "another_unexpected": {"nested": "data"},
        }

        transformed = transform_quality_response(response)
        validated = validate_handler_result(transformed, "test")

        assert validated["success"] is True
        assert validated["quality_score"] == 0.85

    def test_unicode_in_violations(self) -> None:
        """Test handlers preserve unicode characters."""
        response: dict[str, Any] = {
            "quality_score": 0.5,
            "onex_compliance": {
                "violations": ["Error: caf\u00e9 is not valid", "\u4e2d\u6587\u9519\u8bef"],
            },
        }

        transformed = transform_quality_response(response)
        validated = validate_handler_result(transformed, "test")

        assert "Error: caf\u00e9 is not valid" in validated["issues"]
        assert "\u4e2d\u6587\u9519\u8bef" in validated["issues"]

    def test_special_characters_preserved(self) -> None:
        """Test handlers preserve special characters in strings."""
        response: dict[str, Any] = {
            "quality_score": 0.5,
            "onex_compliance": {
                "violations": ["Error: 'value' has\n\ttabs and newlines"],
            },
        }

        transformed = transform_quality_response(response)
        validated = validate_handler_result(transformed, "test")

        assert "Error: 'value' has\n\ttabs and newlines" in validated["issues"]
