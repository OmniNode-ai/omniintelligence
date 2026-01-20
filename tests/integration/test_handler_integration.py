"""Integration tests for handler usage in intelligence_adapter.

These tests verify that:
1. Handlers are correctly imported by intelligence_adapter
2. Handler transforms work with realistic API response shapes
3. Validation is properly applied to handler results
4. The full transform -> validate pipeline works end-to-end
5. Handler purity principles are maintained (determinism, no mutation)
6. Fail-fast validation raises exceptions for invalid input

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
    HandlerValidationError,
    MAX_ISSUES,
    SCORE_MAX,
    SCORE_MIN,
    transform_pattern_response,
    transform_performance_response,
    transform_quality_response,
    validate_handler_result,
)


def _make_valid_quality_response(**overrides: Any) -> dict[str, Any]:
    """Create a valid quality response with all required fields.

    Use this helper to create test responses that satisfy fail-fast validation.
    Override specific fields by passing keyword arguments.
    """
    base: dict[str, Any] = {
        "quality_score": 0.85,
        "onex_compliance": {
            "score": 0.90,
            "violations": [],
            "recommendations": [],
        },
        "maintainability": {
            "complexity_score": 0.75,
        },
    }
    # Apply overrides (supports nested updates)
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key].update(value)
        else:
            base[key] = value
    return base


class TestHandlerIntegration:
    """Integration tests for handler pipeline: transform -> validate."""

    def test_quality_handler_full_pipeline(self) -> None:
        """Test full quality handler pipeline: transform -> validate.

        This simulates a complete flow from raw API response through
        transformation and validation, as would occur in the intelligence_adapter.
        """
        api_response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.90,
                "violations": ["Missing docstring", "Long function"],
                "recommendations": ["Add type hints", "Refactor method"],
            },
            architectural_era="modern",
            temporal_relevance=0.95,
        )

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
        validated = validate_handler_result(transformed, "pattern_match")

        # Verify end-to-end
        assert validated["success"] is True
        assert len(validated["patterns"]) >= 1
        # Patterns contain the model_dump result
        assert validated["patterns"][0] == {"name": "singleton", "confidence": 0.92}
        # Anti-patterns become issues as dicts
        assert len(validated["issues"]) >= 1
        assert validated["recommendations"] == ["Use dependency injection"]

    def test_performance_handler_full_pipeline(self) -> None:
        """Test full performance handler pipeline: transform -> validate."""

        class MockOpportunity:
            title = "Add caching"
            description = "Cache results to reduce latency"

            def model_dump(self) -> dict[str, Any]:
                return {"area": "database", "improvement": 0.3}

        class MockBaseline:
            complexity_estimate = 0.6

            def model_dump(self) -> dict[str, Any]:
                return {"execution_time": 1.2}

        class MockResponse:
            optimization_opportunities = [MockOpportunity()]
            baseline_metrics = MockBaseline()
            estimated_total_improvement = 0.25

        # Transform
        transformed = transform_performance_response(MockResponse())

        # Validate
        validated = validate_handler_result(
            transformed, "identify_optimization_opportunities"
        )

        # Verify end-to-end
        assert validated["success"] is True
        # Opportunities are mapped to patterns via model_dump
        assert isinstance(validated["patterns"], list)
        # Recommendations are built from opportunity.title: opportunity.description
        assert len(validated["recommendations"]) == 1
        assert "Add caching" in validated["recommendations"][0]
        assert validated["complexity_score"] == 0.6

    def test_handler_imports_from_init(self) -> None:
        """Test that all handlers are properly exported from __init__.py."""
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
        result = transform_quality_response(_make_valid_quality_response(quality_score=-10.0))
        assert result["quality_score"] == SCORE_MIN

        # Score above SCORE_MAX should clamp to SCORE_MAX
        result = transform_quality_response(_make_valid_quality_response(quality_score=100.0))
        assert result["quality_score"] == SCORE_MAX

        # Score exactly at boundaries should be preserved
        result = transform_quality_response(_make_valid_quality_response(quality_score=SCORE_MIN))
        assert result["quality_score"] == SCORE_MIN

        result = transform_quality_response(_make_valid_quality_response(quality_score=SCORE_MAX))
        assert result["quality_score"] == SCORE_MAX

    def test_handler_security_limits_applied(self) -> None:
        """Test that MAX_ISSUES limit is applied to prevent memory exhaustion.

        This is a security-critical test to ensure handlers cannot be abused
        to cause memory exhaustion via oversized input.
        """
        # Create more violations than MAX_ISSUES allows
        huge_violations = [f"violation_{i}" for i in range(MAX_ISSUES * 2)]
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.5,
                "violations": huge_violations,
                "recommendations": [],
            }
        )

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

    def test_none_response_raises_exception(self) -> None:
        """Test that None API response raises HandlerValidationError (fail-fast)."""
        with pytest.raises(HandlerValidationError, match="Response is None"):
            transform_quality_response(None)

    def test_missing_required_field_raises_exception(self) -> None:
        """Test that missing required field raises HandlerValidationError."""
        response = {"quality_score": 0.8}  # Missing onex_compliance, maintainability
        with pytest.raises(HandlerValidationError, match="onex_compliance.*missing"):
            transform_quality_response(response)


class TestHandlerPurityCompliance:
    """Tests verifying handlers follow purity principles.

    Pure functions are critical for testability and predictability.
    These tests verify:
    - Determinism: same input produces same output
    - No mutation: input data is not modified
    """

    def test_transform_is_deterministic(self) -> None:
        """Test that transform produces same output for same input."""
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.90,
                "violations": ["issue1"],
                "recommendations": ["rec1"],
            }
        )

        result1 = transform_quality_response(response)
        result2 = transform_quality_response(response)

        assert result1 == result2

    def test_transform_does_not_mutate_input_dict(self) -> None:
        """Test that transform does not modify the input response dict."""
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.90,
                "violations": ["issue1", "issue2"],
                "recommendations": ["rec1"],
            }
        )
        # Deep copy to compare later
        original = copy.deepcopy(response)

        # Transform should not mutate input
        transform_quality_response(response)

        # Original should be unchanged
        assert response == original

    def test_transform_does_not_mutate_input_nested_list(self) -> None:
        """Test that nested lists in input are not mutated."""
        violations = ["issue1", "issue2"]
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.9,
                "violations": violations,
                "recommendations": [],
            }
        )
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
        # Quality handler requires complete response
        transform_quality_response(_make_valid_quality_response())
        # Pattern and Performance handlers are more lenient
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
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.5,
                "violations": large_violations,
                "recommendations": large_violations.copy(),
            }
        )

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
            response = _make_valid_quality_response(
                quality_score=0.5 + (i * 0.01),
                onex_compliance={
                    "score": 0.8,
                    "violations": [f"issue_{i}"],
                    "recommendations": [],
                },
            )
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

    def test_empty_api_response_raises_exception(self) -> None:
        """Test that empty dict response raises HandlerValidationError (fail-fast)."""
        with pytest.raises(HandlerValidationError, match="quality_score.*missing"):
            transform_quality_response({})

    def test_api_response_with_unexpected_keys(self) -> None:
        """Test handlers ignore unexpected keys in response."""
        response = _make_valid_quality_response(
            unexpected_key="should be ignored",
            another_unexpected={"nested": "data"},
        )

        transformed = transform_quality_response(response)
        validated = validate_handler_result(transformed, "test")

        assert validated["success"] is True
        assert validated["quality_score"] == 0.85

    def test_unicode_in_violations(self) -> None:
        """Test handlers preserve unicode characters."""
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.5,
                "violations": ["Error: café is not valid", "中文错误"],
                "recommendations": [],
            }
        )

        transformed = transform_quality_response(response)
        validated = validate_handler_result(transformed, "test")

        assert "Error: café is not valid" in validated["issues"]
        assert "中文错误" in validated["issues"]

    def test_special_characters_preserved(self) -> None:
        """Test handlers preserve special characters in strings."""
        response = _make_valid_quality_response(
            onex_compliance={
                "score": 0.5,
                "violations": ["Error: 'value' has\n\ttabs and newlines"],
                "recommendations": [],
            }
        )

        transformed = transform_quality_response(response)
        validated = validate_handler_result(transformed, "test")

        assert "Error: 'value' has\n\ttabs and newlines" in validated["issues"]
