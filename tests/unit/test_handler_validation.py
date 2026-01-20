"""Unit tests for handler return value validation.

These tests verify the validation logic for handler transform results,
ensuring proper type checking, default values, and error handling.

Coverage:
- Normal case with complete valid result
- None result handling
- Non-dict result handling
- Type validation for scalar fields (success, scores)
- Type validation for collection fields (lists, dicts)
- Value clamping for numeric fields
- Preservation of additional keys
- Logging of validation issues
"""

from __future__ import annotations

import logging

import pytest

from omniintelligence.nodes.intelligence_adapter.handlers.validation import (
    validate_handler_result,
)


class TestValidateHandlerResultBasics:
    """Tests for basic validation functionality."""

    def test_complete_valid_result(self) -> None:
        """Test validation of a complete, valid result."""
        result = {
            "success": True,
            "quality_score": 0.85,
            "onex_compliance": 0.9,
            "complexity_score": 0.7,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1"],
            "patterns": [{"name": "singleton"}],
            "result_data": {"key": "value"},
        }
        validated = validate_handler_result(result, "test_operation")

        assert validated["success"] is True
        assert validated["quality_score"] == 0.85
        assert validated["onex_compliance"] == 0.9
        assert validated["complexity_score"] == 0.7
        assert validated["issues"] == ["issue1", "issue2"]
        assert validated["recommendations"] == ["rec1"]
        assert validated["patterns"] == [{"name": "singleton"}]
        assert validated["result_data"] == {"key": "value"}

    def test_none_result(self) -> None:
        """Test validation when result is None."""
        validated = validate_handler_result(None, "test_operation")

        assert validated["success"] is False
        assert validated["quality_score"] == 0.0
        assert validated["onex_compliance"] == 0.0
        assert validated["complexity_score"] == 0.0
        assert validated["issues"] == []
        assert validated["recommendations"] == []
        assert validated["patterns"] == []
        assert "validation_error" in validated["result_data"]

    def test_non_dict_result_string(self) -> None:
        """Test validation when result is a string."""
        validated = validate_handler_result("unexpected_string", "test_operation")

        assert validated["success"] is True
        assert validated["quality_score"] == 0.0
        assert validated["result_data"]["raw_result"] == "unexpected_string"

    def test_non_dict_result_list(self) -> None:
        """Test validation when result is a list."""
        validated = validate_handler_result([1, 2, 3], "test_operation")

        assert validated["success"] is True
        assert validated["result_data"]["raw_result"] == [1, 2, 3]

    def test_non_dict_result_number(self) -> None:
        """Test validation when result is a number."""
        validated = validate_handler_result(42, "test_operation")

        assert validated["success"] is True
        assert validated["result_data"]["raw_result"] == 42

    def test_empty_dict_result(self) -> None:
        """Test validation of an empty dict result."""
        validated = validate_handler_result({}, "test_operation")

        # All defaults should be applied
        assert validated["success"] is True  # Default
        assert validated["quality_score"] == 0.0
        assert validated["onex_compliance"] == 0.0
        assert validated["complexity_score"] == 0.0
        assert validated["issues"] == []
        assert validated["recommendations"] == []
        assert validated["patterns"] == []
        assert validated["result_data"] == {}


class TestSuccessValidation:
    """Tests for success field validation."""

    def test_success_true(self) -> None:
        """Test success=True is preserved."""
        result = {"success": True}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is True

    def test_success_false(self) -> None:
        """Test success=False is preserved."""
        result = {"success": False}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is False

    def test_success_none(self) -> None:
        """Test success=None defaults to True."""
        result = {"success": None}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is True

    def test_success_missing(self) -> None:
        """Test missing success defaults to True."""
        result = {}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is True

    def test_success_integer_1(self) -> None:
        """Test success=1 is converted to True."""
        result = {"success": 1}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is True

    def test_success_integer_0(self) -> None:
        """Test success=0 is converted to False."""
        result = {"success": 0}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is False

    def test_success_string_true(self) -> None:
        """Test success='true' is converted to True."""
        result = {"success": "true"}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is True

    def test_success_string_false(self) -> None:
        """Test success='false' is converted to False."""
        result = {"success": "false"}
        validated = validate_handler_result(result, "test")
        assert validated["success"] is False


class TestNumericFieldValidation:
    """Tests for numeric field validation (quality_score, onex_compliance, complexity_score)."""

    def test_quality_score_valid(self) -> None:
        """Test valid quality_score is preserved."""
        result = {"quality_score": 0.75}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 0.75

    def test_quality_score_integer(self) -> None:
        """Test integer quality_score is converted to float."""
        result = {"quality_score": 1}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 1.0
        assert isinstance(validated["quality_score"], float)

    def test_quality_score_string_numeric(self) -> None:
        """Test string quality_score is converted to float."""
        result = {"quality_score": "0.85"}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 0.85

    def test_quality_score_string_invalid(self) -> None:
        """Test invalid string quality_score defaults to 0.0."""
        result = {"quality_score": "not_a_number"}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 0.0

    def test_quality_score_none(self) -> None:
        """Test None quality_score defaults to 0.0."""
        result = {"quality_score": None}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 0.0

    def test_quality_score_clamped_high(self) -> None:
        """Test quality_score > 1.0 is clamped to 1.0."""
        result = {"quality_score": 1.5}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 1.0

    def test_quality_score_clamped_low(self) -> None:
        """Test quality_score < 0.0 is clamped to 0.0."""
        result = {"quality_score": -0.5}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 0.0

    def test_onex_compliance_valid(self) -> None:
        """Test valid onex_compliance is preserved."""
        result = {"onex_compliance": 0.9}
        validated = validate_handler_result(result, "test")
        assert validated["onex_compliance"] == 0.9

    def test_onex_compliance_clamped(self) -> None:
        """Test out-of-range onex_compliance is clamped."""
        result = {"onex_compliance": 2.0}
        validated = validate_handler_result(result, "test")
        assert validated["onex_compliance"] == 1.0

    def test_complexity_score_valid(self) -> None:
        """Test valid complexity_score is preserved."""
        result = {"complexity_score": 0.6}
        validated = validate_handler_result(result, "test")
        assert validated["complexity_score"] == 0.6

    def test_complexity_score_clamped(self) -> None:
        """Test out-of-range complexity_score is clamped."""
        result = {"complexity_score": -0.1}
        validated = validate_handler_result(result, "test")
        assert validated["complexity_score"] == 0.0


class TestListFieldValidation:
    """Tests for list field validation (issues, recommendations, patterns)."""

    def test_issues_valid_list(self) -> None:
        """Test valid issues list is preserved."""
        result = {"issues": ["issue1", "issue2"]}
        validated = validate_handler_result(result, "test")
        assert validated["issues"] == ["issue1", "issue2"]

    def test_issues_empty_list(self) -> None:
        """Test empty issues list is preserved."""
        result = {"issues": []}
        validated = validate_handler_result(result, "test")
        assert validated["issues"] == []

    def test_issues_none(self) -> None:
        """Test None issues defaults to empty list."""
        result = {"issues": None}
        validated = validate_handler_result(result, "test")
        assert validated["issues"] == []

    def test_issues_missing(self) -> None:
        """Test missing issues defaults to empty list."""
        result = {}
        validated = validate_handler_result(result, "test")
        assert validated["issues"] == []

    def test_issues_tuple_converted(self) -> None:
        """Test tuple issues is converted to list."""
        result = {"issues": ("issue1", "issue2")}
        validated = validate_handler_result(result, "test")
        assert validated["issues"] == ["issue1", "issue2"]

    def test_issues_single_value_wrapped(self) -> None:
        """Test single value issues is wrapped in list."""
        result = {"issues": "single_issue"}
        validated = validate_handler_result(result, "test")
        assert validated["issues"] == ["single_issue"]

    def test_recommendations_valid(self) -> None:
        """Test valid recommendations list is preserved."""
        result = {"recommendations": ["rec1"]}
        validated = validate_handler_result(result, "test")
        assert validated["recommendations"] == ["rec1"]

    def test_recommendations_single_value_wrapped(self) -> None:
        """Test single recommendation is wrapped in list."""
        result = {"recommendations": "single_rec"}
        validated = validate_handler_result(result, "test")
        assert validated["recommendations"] == ["single_rec"]

    def test_patterns_valid(self) -> None:
        """Test valid patterns list is preserved."""
        result = {"patterns": [{"name": "factory"}]}
        validated = validate_handler_result(result, "test")
        assert validated["patterns"] == [{"name": "factory"}]

    def test_patterns_set_converted(self) -> None:
        """Test set patterns is converted to list."""
        result = {"patterns": {"a", "b"}}
        validated = validate_handler_result(result, "test")
        assert isinstance(validated["patterns"], list)
        assert set(validated["patterns"]) == {"a", "b"}


class TestDictFieldValidation:
    """Tests for dict field validation (result_data)."""

    def test_result_data_valid(self) -> None:
        """Test valid result_data dict is preserved."""
        result = {"result_data": {"key": "value", "nested": {"a": 1}}}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"] == {"key": "value", "nested": {"a": 1}}

    def test_result_data_empty_dict(self) -> None:
        """Test empty result_data dict is preserved."""
        result = {"result_data": {}}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"] == {}

    def test_result_data_none(self) -> None:
        """Test None result_data defaults to empty dict."""
        result = {"result_data": None}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"] == {}

    def test_result_data_missing(self) -> None:
        """Test missing result_data defaults to empty dict."""
        result = {}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"] == {}

    def test_result_data_list_not_converted(self) -> None:
        """Test list result_data becomes empty dict (can't convert)."""
        result = {"result_data": [1, 2, 3]}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"] == {}

    def test_result_data_string_not_converted(self) -> None:
        """Test string result_data becomes empty dict (can't convert)."""
        result = {"result_data": "not_a_dict"}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"] == {}


class TestAdditionalKeysPreservation:
    """Tests for preservation of additional (non-standard) keys."""

    def test_preserves_error_key(self) -> None:
        """Test that 'error' key from handlers is preserved."""
        result = {
            "success": False,
            "error": "Something went wrong",
            "quality_score": 0.0,
        }
        validated = validate_handler_result(result, "test")
        assert validated["error"] == "Something went wrong"

    def test_preserves_custom_keys(self) -> None:
        """Test that custom keys are preserved."""
        result = {
            "success": True,
            "custom_field": "custom_value",
            "another_field": 123,
        }
        validated = validate_handler_result(result, "test")
        assert validated["custom_field"] == "custom_value"
        assert validated["another_field"] == 123


class TestLoggingBehavior:
    """Tests for validation logging behavior."""

    def test_logs_warning_on_none_result(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that warning is logged when result is None."""
        with caplog.at_level(logging.WARNING):
            validate_handler_result(None, "my_operation", log_issues=True)

        assert "my_operation" in caplog.text
        assert "None" in caplog.text or "using default values" in caplog.text

    def test_logs_warning_on_non_dict_result(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that warning is logged when result is not a dict."""
        with caplog.at_level(logging.WARNING):
            validate_handler_result("not_a_dict", "my_operation", log_issues=True)

        assert "my_operation" in caplog.text
        assert "str" in caplog.text or "dict" in caplog.text

    def test_logs_warning_on_type_mismatch(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that warning is logged when field has wrong type."""
        with caplog.at_level(logging.WARNING):
            validate_handler_result(
                {"quality_score": "not_a_number"}, "my_operation", log_issues=True
            )

        assert "my_operation" in caplog.text
        assert "quality_score" in caplog.text

    def test_no_log_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no warning is logged when log_issues=False."""
        with caplog.at_level(logging.WARNING):
            validate_handler_result(None, "my_operation", log_issues=False)

        # Should not log when disabled
        assert "my_operation" not in caplog.text

    def test_logs_multiple_issues(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that multiple validation issues are logged together."""
        with caplog.at_level(logging.WARNING):
            validate_handler_result(
                {
                    "success": "not_bool",
                    "quality_score": "not_number",
                    "issues": "not_list",
                },
                "multi_issue_op",
                log_issues=True,
            )

        assert "multi_issue_op" in caplog.text


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_boundary_score_0(self) -> None:
        """Test score at lower boundary 0.0."""
        result = {"quality_score": 0.0}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 0.0

    def test_boundary_score_1(self) -> None:
        """Test score at upper boundary 1.0."""
        result = {"quality_score": 1.0}
        validated = validate_handler_result(result, "test")
        assert validated["quality_score"] == 1.0

    def test_float_precision(self) -> None:
        """Test that float precision is maintained."""
        result = {"quality_score": 0.123456789}
        validated = validate_handler_result(result, "test")
        assert abs(validated["quality_score"] - 0.123456789) < 1e-10

    def test_large_list(self) -> None:
        """Test validation with large list."""
        large_list = [f"issue_{i}" for i in range(1000)]
        result = {"issues": large_list}
        validated = validate_handler_result(result, "test")
        assert len(validated["issues"]) == 1000

    def test_nested_result_data(self) -> None:
        """Test deeply nested result_data is preserved."""
        nested = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        result = {"result_data": nested}
        validated = validate_handler_result(result, "test")
        assert validated["result_data"]["level1"]["level2"]["level3"]["value"] == "deep"

    def test_special_characters_in_strings(self) -> None:
        """Test strings with special characters are preserved."""
        result = {"issues": ["Error: 'value' is \n invalid \t chars"]}
        validated = validate_handler_result(result, "test")
        assert validated["issues"][0] == "Error: 'value' is \n invalid \t chars"

    def test_unicode_strings(self) -> None:
        """Test unicode strings are preserved."""
        result = {"issues": ["Error with unicode: \u00e9\u00e0\u00fc"]}
        validated = validate_handler_result(result, "test")
        assert validated["issues"][0] == "Error with unicode: \u00e9\u00e0\u00fc"


class TestIntegrationWithHandlers:
    """Integration tests simulating real handler output validation."""

    def test_quality_handler_output(self) -> None:
        """Test validation of typical quality handler output."""
        # Simulate output from transform_quality_response
        result = {
            "success": True,
            "quality_score": 0.85,
            "onex_compliance": 0.9,
            "complexity_score": 0.7,
            "issues": ["missing docstring"],
            "recommendations": ["add docstrings"],
            "patterns": [],
            "result_data": {
                "architectural_era": "modern",
                "temporal_relevance": 0.95,
            },
        }
        validated = validate_handler_result(result, "assess_code_quality")

        assert validated["success"] is True
        assert validated["quality_score"] == 0.85
        assert validated["onex_compliance"] == 0.9
        assert validated["complexity_score"] == 0.7
        assert validated["issues"] == ["missing docstring"]
        assert validated["result_data"]["architectural_era"] == "modern"

    def test_pattern_handler_output(self) -> None:
        """Test validation of typical pattern handler output."""
        # Simulate output from transform_pattern_response
        result = {
            "success": True,
            "onex_compliance": 0.88,
            "patterns": [{"name": "singleton", "confidence": 0.9}],
            "issues": ["god_class: Class does too much"],
            "recommendations": ["Use dependency injection"],
            "result_data": {
                "analysis_summary": "Good patterns detected",
                "confidence_scores": {"overall": 0.85},
            },
        }
        validated = validate_handler_result(result, "get_quality_patterns")

        assert validated["success"] is True
        assert validated["onex_compliance"] == 0.88
        assert len(validated["patterns"]) == 1
        assert validated["patterns"][0]["name"] == "singleton"

    def test_performance_handler_output(self) -> None:
        """Test validation of typical performance handler output."""
        # Simulate output from transform_performance_response
        result = {
            "success": True,
            "complexity_score": 0.7,
            "recommendations": ["Cache results: Add caching"],
            "result_data": {
                "baseline_metrics": {"complexity_estimate": 0.7},
                "optimization_opportunities": [{"title": "Cache", "description": "Add caching"}],
                "total_opportunities": 1,
                "estimated_improvement": 0.25,
            },
        }
        validated = validate_handler_result(result, "analyze_performance")

        assert validated["success"] is True
        assert validated["complexity_score"] == 0.7
        assert validated["recommendations"] == ["Cache results: Add caching"]
        assert validated["result_data"]["total_opportunities"] == 1

    def test_handler_output_with_error(self) -> None:
        """Test validation of handler output with error key (None response case)."""
        # Simulate output from transform_quality_response when response is None
        result = {
            "success": False,
            "quality_score": 0.0,
            "onex_compliance": 0.0,
            "complexity_score": 0.0,
            "issues": [],
            "recommendations": [],
            "patterns": [],
            "result_data": {},
            "error": "Response is None - cannot transform quality assessment",
        }
        validated = validate_handler_result(result, "assess_code_quality")

        assert validated["success"] is False
        assert validated["error"] == "Response is None - cannot transform quality assessment"
