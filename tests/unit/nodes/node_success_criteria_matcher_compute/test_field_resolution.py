# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for field path resolution and criteria validation functions.

This module tests the core utility functions of the success criteria matcher:
    - resolve_field_path: Dot-notation path resolution from nested data
    - _validate_criteria_set: Criteria validation (duplicates, operators, weights, regex)

These functions are pure computation with no side effects, making them
ideal for exhaustive unit testing.
"""

from __future__ import annotations

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
    MISSING,
    resolve_field_path,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.exceptions import (
    CriteriaMatchingValidationError,
)
from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers.handler_criteria_matching import (
    _validate_criteria_set,
)


# =============================================================================
# resolve_field_path Tests - Basic Path Resolution
# =============================================================================


class TestResolveFieldPathBasic:
    """Tests for basic field path resolution."""

    def test_simple_key(self) -> None:
        """Simple top-level key should resolve correctly."""
        data = {"status": "success"}
        assert resolve_field_path(data, "status") == "success"

    def test_simple_key_integer_value(self) -> None:
        """Integer values should be resolved correctly."""
        data = {"exit_code": 0}
        assert resolve_field_path(data, "exit_code") == 0

    def test_simple_key_float_value(self) -> None:
        """Float values should be resolved correctly."""
        data = {"score": 0.95}
        assert resolve_field_path(data, "score") == 0.95

    def test_simple_key_boolean_value(self) -> None:
        """Boolean values should be resolved correctly."""
        data = {"enabled": True, "disabled": False}
        assert resolve_field_path(data, "enabled") is True
        assert resolve_field_path(data, "disabled") is False

    def test_simple_key_none_value(self) -> None:
        """None values should be resolved correctly (distinct from MISSING)."""
        data = {"value": None}
        result = resolve_field_path(data, "value")
        assert result is None
        assert result is not MISSING

    def test_simple_key_empty_string_value(self) -> None:
        """Empty string values should be resolved correctly."""
        data = {"message": ""}
        assert resolve_field_path(data, "message") == ""

    def test_simple_key_list_value(self) -> None:
        """List values should be resolved correctly."""
        data = {"items": [1, 2, 3]}
        assert resolve_field_path(data, "items") == [1, 2, 3]

    def test_simple_key_dict_value(self) -> None:
        """Dict values should be resolved correctly."""
        data = {"config": {"a": 1, "b": 2}}
        assert resolve_field_path(data, "config") == {"a": 1, "b": 2}


# =============================================================================
# resolve_field_path Tests - Nested Path Resolution
# =============================================================================


class TestResolveFieldPathNested:
    """Tests for nested field path resolution."""

    def test_nested_key_two_levels(self) -> None:
        """Two-level nested path should resolve correctly."""
        data = {"outputs": {"result": "completed"}}
        assert resolve_field_path(data, "outputs.result") == "completed"

    def test_nested_key_three_levels(self) -> None:
        """Three-level nested path should resolve correctly."""
        data = {"a": {"b": {"c": "deep"}}}
        assert resolve_field_path(data, "a.b.c") == "deep"

    def test_nested_key_many_levels(self) -> None:
        """Deep nesting should resolve correctly."""
        data = {"l1": {"l2": {"l3": {"l4": {"l5": "very_deep"}}}}}
        assert resolve_field_path(data, "l1.l2.l3.l4.l5") == "very_deep"

    def test_nested_key_with_none_intermediate(self) -> None:
        """Path through None intermediate should return MISSING."""
        data = {"parent": None}
        # Cannot traverse through None
        assert resolve_field_path(data, "parent.child") is MISSING

    def test_nested_mixed_types(self) -> None:
        """Nested path with mixed value types should work."""
        data = {
            "config": {
                "count": 42,
                "rate": 0.5,
                "enabled": True,
                "name": "test",
            }
        }
        assert resolve_field_path(data, "config.count") == 42
        assert resolve_field_path(data, "config.rate") == 0.5
        assert resolve_field_path(data, "config.enabled") is True
        assert resolve_field_path(data, "config.name") == "test"


# =============================================================================
# resolve_field_path Tests - List Indexing
# =============================================================================


class TestResolveFieldPathListIndexing:
    """Tests for list index resolution in field paths."""

    def test_list_index_first_element(self) -> None:
        """First list element should be accessible via index 0."""
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        assert resolve_field_path(data, "items.0.name") == "first"

    def test_list_index_second_element(self) -> None:
        """Second list element should be accessible via index 1."""
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        assert resolve_field_path(data, "items.1.name") == "second"

    def test_list_index_last_element(self) -> None:
        """Last element should be accessible by its index."""
        data = {"items": ["a", "b", "c", "d", "e"]}
        assert resolve_field_path(data, "items.4") == "e"

    def test_list_index_nested_list(self) -> None:
        """Nested lists should support chained indexing."""
        data = {"matrix": [[1, 2], [3, 4], [5, 6]]}
        assert resolve_field_path(data, "matrix.0.0") == 1
        assert resolve_field_path(data, "matrix.1.1") == 4
        assert resolve_field_path(data, "matrix.2.0") == 5

    def test_list_index_with_subsequent_key(self) -> None:
        """List index followed by dict key should work."""
        data = {"results": [{"id": "r1", "value": 10}, {"id": "r2", "value": 20}]}
        assert resolve_field_path(data, "results.0.id") == "r1"
        assert resolve_field_path(data, "results.1.value") == 20

    def test_list_index_on_tuple(self) -> None:
        """Tuple should be indexable like a list."""
        data = {"coords": (10, 20, 30)}
        assert resolve_field_path(data, "coords.0") == 10
        assert resolve_field_path(data, "coords.2") == 30

    def test_list_index_zero_padded_not_special(self) -> None:
        """Zero-padded indices should work as plain integers."""
        data = {"items": ["a", "b", "c"]}
        # "00" is still a valid non-negative integer pattern
        assert resolve_field_path(data, "items.00") == "a"
        assert resolve_field_path(data, "items.01") == "b"


# =============================================================================
# resolve_field_path Tests - MISSING Sentinel
# =============================================================================


class TestResolveFieldPathMissing:
    """Tests for MISSING sentinel behavior."""

    def test_missing_key_returns_missing(self) -> None:
        """Non-existent key should return MISSING."""
        data = {"status": "success"}
        assert resolve_field_path(data, "missing_key") is MISSING

    def test_missing_nested_key_returns_missing(self) -> None:
        """Non-existent nested key should return MISSING."""
        data = {"outputs": {"result": "ok"}}
        assert resolve_field_path(data, "outputs.nonexistent") is MISSING

    def test_missing_intermediate_key_returns_missing(self) -> None:
        """Missing intermediate key should return MISSING."""
        data = {"a": {"b": "value"}}
        assert resolve_field_path(data, "x.y.z") is MISSING

    def test_out_of_bounds_list_index_returns_missing(self) -> None:
        """Out of bounds list index should return MISSING."""
        data = {"items": ["a", "b", "c"]}
        assert resolve_field_path(data, "items.3") is MISSING
        assert resolve_field_path(data, "items.100") is MISSING

    def test_list_index_on_non_list_returns_missing(self) -> None:
        """List index on non-list value should return MISSING."""
        data = {"value": "string"}
        assert resolve_field_path(data, "value.0") is MISSING

    def test_list_index_on_dict_returns_missing(self) -> None:
        """Numeric index on dict should return MISSING."""
        data = {"config": {"a": 1, "b": 2}}
        assert resolve_field_path(data, "config.0") is MISSING

    def test_dict_key_on_list_returns_missing(self) -> None:
        """Dict key access on list should return MISSING."""
        data = {"items": [1, 2, 3]}
        assert resolve_field_path(data, "items.name") is MISSING

    def test_empty_dict_returns_missing_for_any_key(self) -> None:
        """Empty dict should return MISSING for any key."""
        data: dict = {}
        assert resolve_field_path(data, "anything") is MISSING

    def test_missing_is_falsy_but_not_none(self) -> None:
        """MISSING should be falsy but distinct from None."""
        assert not MISSING
        assert MISSING is not None
        assert MISSING is not False


# =============================================================================
# resolve_field_path Tests - Validation Errors
# =============================================================================


class TestResolveFieldPathValidationErrors:
    """Tests for invalid path syntax validation."""

    def test_empty_path_raises_error(self) -> None:
        """Empty path string should raise validation error."""
        data = {"key": "value"}
        with pytest.raises(CriteriaMatchingValidationError, match="cannot be empty"):
            resolve_field_path(data, "")

    def test_whitespace_only_path_raises_error(self) -> None:
        """Whitespace-only path should raise validation error."""
        data = {"key": "value"}
        with pytest.raises(CriteriaMatchingValidationError, match="cannot be empty"):
            resolve_field_path(data, "   ")

    def test_leading_dot_raises_error(self) -> None:
        """Leading dot in path should raise validation error."""
        data = {"key": "value"}
        with pytest.raises(
            CriteriaMatchingValidationError, match="leading or trailing dots"
        ):
            resolve_field_path(data, ".key")

    def test_trailing_dot_raises_error(self) -> None:
        """Trailing dot in path should raise validation error."""
        data = {"key": "value"}
        with pytest.raises(
            CriteriaMatchingValidationError, match="leading or trailing dots"
        ):
            resolve_field_path(data, "key.")

    def test_consecutive_dots_raises_error(self) -> None:
        """Consecutive dots (empty token) should raise validation error."""
        data = {"a": {"b": "value"}}
        with pytest.raises(
            CriteriaMatchingValidationError, match="empty token.*consecutive dots"
        ):
            resolve_field_path(data, "a..b")

    def test_multiple_consecutive_dots_raises_error(self) -> None:
        """Multiple consecutive dots should raise validation error."""
        data = {"a": {"b": "value"}}
        with pytest.raises(CriteriaMatchingValidationError, match="empty token"):
            resolve_field_path(data, "a...b")

    def test_negative_index_raises_error(self) -> None:
        """Negative index in path should raise validation error."""
        data = {"items": [1, 2, 3]}
        with pytest.raises(CriteriaMatchingValidationError, match="invalid characters"):
            resolve_field_path(data, "items.-1")

    def test_special_characters_in_token_raises_error(self) -> None:
        """Special characters in token should raise validation error."""
        data = {"key": "value"}
        # Hyphen is not allowed (only alphanumeric + underscore)
        with pytest.raises(CriteriaMatchingValidationError, match="invalid characters"):
            resolve_field_path(data, "key-name")

    def test_space_in_token_raises_error(self) -> None:
        """Space in token should raise validation error."""
        data = {"key name": "value"}
        with pytest.raises(CriteriaMatchingValidationError, match="invalid characters"):
            resolve_field_path(data, "key name")

    def test_brackets_in_token_raises_error(self) -> None:
        """Bracket syntax should raise validation error (use dots)."""
        data = {"items": [1, 2, 3]}
        with pytest.raises(CriteriaMatchingValidationError, match="invalid characters"):
            resolve_field_path(data, "items[0]")


# =============================================================================
# resolve_field_path Tests - Edge Cases
# =============================================================================


class TestResolveFieldPathEdgeCases:
    """Tests for edge cases in field path resolution."""

    def test_underscore_in_key(self) -> None:
        """Underscores in keys should be allowed."""
        data = {"my_key": "value", "another_key_name": "other"}
        assert resolve_field_path(data, "my_key") == "value"
        assert resolve_field_path(data, "another_key_name") == "other"

    def test_numeric_token_treated_as_index(self) -> None:
        """All-digit tokens are treated as list indices, not dict keys.

        This is intentional behavior: "123" is parsed as index 123, not key "123".
        To access dict keys that look like numbers, use non-numeric prefixes.
        """
        # Numeric token on dict returns MISSING (tries index access on dict)
        data = {"123": "numeric_key"}
        assert resolve_field_path(data, "123") is MISSING

        # Workaround: use a prefix for numeric-ish keys
        data = {"item_123": "value"}
        assert resolve_field_path(data, "item_123") == "value"

    def test_single_character_key(self) -> None:
        """Single character keys should work."""
        data = {"a": {"b": {"c": "deep"}}}
        assert resolve_field_path(data, "a") == {"b": {"c": "deep"}}
        assert resolve_field_path(data, "a.b") == {"c": "deep"}
        assert resolve_field_path(data, "a.b.c") == "deep"

    def test_mixed_case_keys(self) -> None:
        """Mixed case keys should be case-sensitive."""
        data = {"Key": "upper", "key": "lower", "KEY": "all_caps"}
        assert resolve_field_path(data, "Key") == "upper"
        assert resolve_field_path(data, "key") == "lower"
        assert resolve_field_path(data, "KEY") == "all_caps"

    def test_very_long_path(self) -> None:
        """Very long paths should work."""
        # Build a deep structure: 50 levels of nesting
        depth = 50
        data: dict = {"value": "bottom"}
        for _ in range(depth):
            data = {"level": data}

        # Path needs depth steps of "level" plus final "value"
        path = ".".join(["level"] * depth) + ".value"
        assert resolve_field_path(data, path) == "bottom"

    def test_empty_list_index_out_of_bounds(self) -> None:
        """Empty list should return MISSING for any index."""
        data = {"items": []}
        assert resolve_field_path(data, "items.0") is MISSING

    def test_list_of_none(self) -> None:
        """List containing None should resolve correctly."""
        data = {"items": [None, "value", None]}
        assert resolve_field_path(data, "items.0") is None
        assert resolve_field_path(data, "items.1") == "value"
        assert resolve_field_path(data, "items.2") is None


# =============================================================================
# _validate_criteria_set Tests - Valid Criteria
# =============================================================================


class TestValidateCriteriaSetValid:
    """Tests for valid criteria set validation."""

    def test_empty_criteria_returns_empty_dict(self) -> None:
        """Empty criteria list should return empty compiled regex dict."""
        result = _validate_criteria_set([])
        assert result == {}

    def test_single_valid_criterion(self) -> None:
        """Single valid criterion should pass validation."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
            }
        ]
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_multiple_valid_criteria(self) -> None:
        """Multiple valid criteria with unique IDs should pass."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
            },
            {
                "criterion_id": "c2",
                "field": "exit_code",
                "operator": "equals",
                "expected_value": 0,
            },
            {
                "criterion_id": "c3",
                "field": "count",
                "operator": "greater_than",
                "expected_value": 10,
            },
        ]
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_all_operators_valid(self) -> None:
        """All supported operators should pass validation."""
        operators = [
            "equals",
            "not_equals",
            "greater_than",
            "less_than",
            "greater_or_equal",
            "less_or_equal",
            "contains",
            "not_contains",
            "regex",
            "is_null",
            "is_not_null",
        ]

        criteria = []
        for i, op in enumerate(operators):
            criterion = {
                "criterion_id": f"c{i}",
                "field": "field",
                "operator": op,
            }
            if op == "regex":
                criterion["expected_value"] = ".*"
            else:
                criterion["expected_value"] = "value"
            criteria.append(criterion)

        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)
        # Should have one compiled regex for the regex operator
        assert len(result) == 1

    def test_zero_weight_allowed(self) -> None:
        """Zero weight should be allowed (non-negative)."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 0.0,
            }
        ]
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_large_weight_allowed(self) -> None:
        """Large weight values should be allowed."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                "weight": 1000000.0,
            }
        ]
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_regex_pattern_compiled(self) -> None:
        """Valid regex patterns should be pre-compiled."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": r"^success.*\d+$",
            }
        ]
        result = _validate_criteria_set(criteria)
        assert "regex_test" in result
        # Should be a compiled pattern
        assert hasattr(result["regex_test"], "search")


# =============================================================================
# _validate_criteria_set Tests - Duplicate ID Errors
# =============================================================================


class TestValidateCriteriaSetDuplicateId:
    """Tests for duplicate criterion_id validation."""

    def test_duplicate_id_raises_error(self) -> None:
        """Duplicate criterion_id should raise validation error."""
        criteria = [
            {
                "criterion_id": "duplicate",
                "field": "status",
                "operator": "equals",
                "expected_value": "a",
            },
            {
                "criterion_id": "duplicate",
                "field": "code",
                "operator": "equals",
                "expected_value": "b",
            },
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Duplicate criterion_id.*'duplicate'"
        ):
            _validate_criteria_set(criteria)

    def test_duplicate_id_case_sensitive(self) -> None:
        """Duplicate ID check should be case-sensitive."""
        criteria = [
            {
                "criterion_id": "Test",
                "field": "a",
                "operator": "equals",
                "expected_value": 1,
            },
            {
                "criterion_id": "test",
                "field": "b",
                "operator": "equals",
                "expected_value": 2,
            },
        ]
        # Should NOT raise - different IDs due to case
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_empty_string_id_can_duplicate(self) -> None:
        """Multiple empty string IDs should raise duplicate error."""
        criteria = [
            {
                "criterion_id": "",
                "field": "a",
                "operator": "equals",
                "expected_value": 1,
            },
            {
                "criterion_id": "",
                "field": "b",
                "operator": "equals",
                "expected_value": 2,
            },
        ]
        with pytest.raises(CriteriaMatchingValidationError, match="Duplicate"):
            _validate_criteria_set(criteria)


# =============================================================================
# _validate_criteria_set Tests - Invalid Operator Errors
# =============================================================================


class TestValidateCriteriaSetInvalidOperator:
    """Tests for invalid operator validation."""

    def test_invalid_operator_raises_error(self) -> None:
        """Unknown operator should raise validation error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "invalid_operator",
                "expected_value": "value",
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError,
            match="Invalid operator 'invalid_operator'",
        ):
            _validate_criteria_set(criteria)

    def test_empty_operator_raises_error(self) -> None:
        """Empty operator string should raise validation error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "",
                "expected_value": "value",
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Invalid operator ''"
        ):
            _validate_criteria_set(criteria)

    def test_typo_in_operator_raises_error(self) -> None:
        """Typo in operator name should raise validation error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equal",  # Missing 's'
                "expected_value": "value",
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Invalid operator 'equal'"
        ):
            _validate_criteria_set(criteria)

    def test_case_sensitive_operator(self) -> None:
        """Operator names should be case-sensitive."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "EQUALS",  # Wrong case
                "expected_value": "value",
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Invalid operator 'EQUALS'"
        ):
            _validate_criteria_set(criteria)


# =============================================================================
# _validate_criteria_set Tests - Negative Weight Errors
# =============================================================================


class TestValidateCriteriaSetNegativeWeight:
    """Tests for negative weight validation."""

    def test_negative_weight_raises_error(self) -> None:
        """Negative weight should raise validation error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "value",
                "weight": -1.0,
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Negative weight.*-1.0"
        ):
            _validate_criteria_set(criteria)

    def test_small_negative_weight_raises_error(self) -> None:
        """Small negative weight should still raise error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "value",
                "weight": -0.001,
            }
        ]
        with pytest.raises(CriteriaMatchingValidationError, match="Negative weight"):
            _validate_criteria_set(criteria)

    def test_large_negative_weight_raises_error(self) -> None:
        """Large negative weight should raise error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "value",
                "weight": -1000000.0,
            }
        ]
        with pytest.raises(CriteriaMatchingValidationError, match="Negative weight"):
            _validate_criteria_set(criteria)

    def test_negative_integer_weight_raises_error(self) -> None:
        """Negative integer weight should raise error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "value",
                "weight": -5,
            }
        ]
        with pytest.raises(CriteriaMatchingValidationError, match="Negative weight"):
            _validate_criteria_set(criteria)


# =============================================================================
# _validate_criteria_set Tests - Invalid Regex Errors
# =============================================================================


class TestValidateCriteriaSetInvalidRegex:
    """Tests for invalid regex pattern validation."""

    def test_invalid_regex_pattern_raises_error(self) -> None:
        """Invalid regex pattern should raise validation error."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": "[invalid(regex",  # Unclosed bracket
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Invalid regex pattern"
        ):
            _validate_criteria_set(criteria)

    def test_unclosed_group_regex_raises_error(self) -> None:
        """Regex with unclosed group should raise error."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": "(unclosed",
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError, match="Invalid regex pattern"
        ):
            _validate_criteria_set(criteria)

    def test_invalid_quantifier_regex_raises_error(self) -> None:
        """Regex with invalid quantifier should raise error."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": "test{invalid}",
            }
        ]
        # This might or might not raise depending on regex engine interpretation
        # Let's test with definitely invalid pattern
        criteria[0]["expected_value"] = "*invalid"  # Leading quantifier
        with pytest.raises(
            CriteriaMatchingValidationError, match="Invalid regex pattern"
        ):
            _validate_criteria_set(criteria)

    def test_non_string_regex_expected_value_raises_error(self) -> None:
        """Regex operator with non-string expected_value should raise error."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": 123,  # Integer, not string
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError,
            match="Regex operator requires string expected_value",
        ):
            _validate_criteria_set(criteria)

    def test_none_regex_expected_value_raises_error(self) -> None:
        """Regex operator with None expected_value should raise error."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": None,
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError,
            match="Regex operator requires string expected_value",
        ):
            _validate_criteria_set(criteria)

    def test_list_regex_expected_value_raises_error(self) -> None:
        """Regex operator with list expected_value should raise error."""
        criteria = [
            {
                "criterion_id": "regex_test",
                "field": "message",
                "operator": "regex",
                "expected_value": ["pattern"],
            }
        ]
        with pytest.raises(
            CriteriaMatchingValidationError,
            match="Regex operator requires string expected_value",
        ):
            _validate_criteria_set(criteria)


# =============================================================================
# _validate_criteria_set Tests - Valid Regex Patterns
# =============================================================================


class TestValidateCriteriaSetValidRegex:
    """Tests for valid regex pattern compilation."""

    def test_simple_regex_compiled(self) -> None:
        """Simple regex pattern should compile successfully."""
        criteria = [
            {
                "criterion_id": "r1",
                "field": "message",
                "operator": "regex",
                "expected_value": "success",
            }
        ]
        result = _validate_criteria_set(criteria)
        assert "r1" in result
        assert result["r1"].search("test success message")

    def test_complex_regex_compiled(self) -> None:
        """Complex regex pattern should compile successfully."""
        criteria = [
            {
                "criterion_id": "r1",
                "field": "message",
                "operator": "regex",
                "expected_value": r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$",
            }
        ]
        result = _validate_criteria_set(criteria)
        assert "r1" in result
        assert result["r1"].search("2024-01-15T10:30:00")

    def test_multiple_regex_compiled(self) -> None:
        """Multiple regex patterns should all be compiled."""
        criteria = [
            {
                "criterion_id": "r1",
                "field": "a",
                "operator": "regex",
                "expected_value": r"\d+",
            },
            {
                "criterion_id": "r2",
                "field": "b",
                "operator": "regex",
                "expected_value": r"[a-z]+",
            },
            {
                "criterion_id": "r3",
                "field": "c",
                "operator": "regex",
                "expected_value": r"test.*end",
            },
        ]
        result = _validate_criteria_set(criteria)
        assert len(result) == 3
        assert "r1" in result
        assert "r2" in result
        assert "r3" in result

    def test_empty_regex_pattern_valid(self) -> None:
        """Empty regex pattern should be valid (matches everything)."""
        criteria = [
            {
                "criterion_id": "r1",
                "field": "message",
                "operator": "regex",
                "expected_value": "",
            }
        ]
        result = _validate_criteria_set(criteria)
        assert "r1" in result
        # Empty pattern matches any string
        assert result["r1"].search("anything")


# =============================================================================
# _validate_criteria_set Tests - Edge Cases
# =============================================================================


class TestValidateCriteriaSetEdgeCases:
    """Tests for edge cases in criteria validation."""

    def test_missing_weight_uses_default(self) -> None:
        """Missing weight should not cause validation error."""
        criteria = [
            {
                "criterion_id": "c1",
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
                # No weight field
            }
        ]
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_missing_criterion_id_uses_empty(self) -> None:
        """Missing criterion_id should default to empty string."""
        criteria = [
            {
                # No criterion_id
                "field": "status",
                "operator": "equals",
                "expected_value": "success",
            }
        ]
        result = _validate_criteria_set(criteria)
        assert isinstance(result, dict)

    def test_validation_order_duplicate_before_operator(self) -> None:
        """Duplicate ID error should be raised even with invalid operator."""
        # First criterion is valid, second has same ID and invalid operator
        # Should still catch duplicate ID
        criteria = [
            {
                "criterion_id": "same",
                "field": "a",
                "operator": "equals",
                "expected_value": 1,
            },
            {
                "criterion_id": "same",
                "field": "b",
                "operator": "invalid",  # Also invalid
                "expected_value": 2,
            },
        ]
        with pytest.raises(CriteriaMatchingValidationError, match="Duplicate"):
            _validate_criteria_set(criteria)

    def test_first_error_wins(self) -> None:
        """First validation error encountered should be raised."""
        # Criterion with invalid operator
        criteria = [
            {
                "criterion_id": "c1",
                "field": "a",
                "operator": "bad_op",
                "expected_value": 1,
                "weight": -1,  # Also invalid
            }
        ]
        # Operator validation happens before weight validation
        with pytest.raises(CriteriaMatchingValidationError, match="Invalid operator"):
            _validate_criteria_set(criteria)
