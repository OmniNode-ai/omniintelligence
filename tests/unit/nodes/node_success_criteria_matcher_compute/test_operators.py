"""Unit tests for apply_operator() covering all 11 operators.

This module tests the operator application logic in the success criteria
matcher, covering all comparison operators and their edge cases.

Operators tested:
    - equals, not_equals: Exact value comparison
    - greater_than, less_than, greater_or_equal, less_or_equal: Numeric comparison
    - contains, not_contains: Membership/substring tests
    - regex: Pattern matching
    - is_null, is_not_null: Null checks
"""

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_success_criteria_matcher_compute.handlers import (
    MISSING,
    EnumCriteriaOperator,
    apply_operator,
)

# =============================================================================
# EQUALS Operator Tests
# =============================================================================


class TestEqualsOperator:
    """Tests for EnumCriteriaOperator.EQUALS."""

    def test_string_equality(self) -> None:
        """String values that are equal should match."""
        matched, reason = apply_operator("hello", EnumCriteriaOperator.EQUALS, "hello")
        assert matched is True
        assert "equals" in reason.lower()

    def test_string_inequality(self) -> None:
        """String values that differ should not match."""
        matched, reason = apply_operator("hello", EnumCriteriaOperator.EQUALS, "world")
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_integer_equality(self) -> None:
        """Integer values that are equal should match."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.EQUALS, 42)
        assert matched is True
        assert "equals" in reason.lower()

    def test_integer_inequality(self) -> None:
        """Integer values that differ should not match."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.EQUALS, 0)
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_float_equality(self) -> None:
        """Float values that are equal should match."""
        matched, reason = apply_operator(3.14, EnumCriteriaOperator.EQUALS, 3.14)
        assert matched is True
        assert "equals" in reason.lower()

    def test_float_inequality(self) -> None:
        """Float values that differ should not match."""
        matched, reason = apply_operator(3.14, EnumCriteriaOperator.EQUALS, 2.71)
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_boolean_true_equality(self) -> None:
        """Boolean True values should match."""
        matched, reason = apply_operator(True, EnumCriteriaOperator.EQUALS, True)
        assert matched is True
        assert "equals" in reason.lower()

    def test_boolean_false_equality(self) -> None:
        """Boolean False values should match."""
        matched, reason = apply_operator(False, EnumCriteriaOperator.EQUALS, False)
        assert matched is True
        assert "equals" in reason.lower()

    def test_boolean_inequality(self) -> None:
        """Boolean True vs False should not match."""
        matched, reason = apply_operator(True, EnumCriteriaOperator.EQUALS, False)
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_none_equality(self) -> None:
        """None values should match each other."""
        matched, reason = apply_operator(None, EnumCriteriaOperator.EQUALS, None)
        assert matched is True
        assert "equals" in reason.lower()

    def test_none_vs_value_inequality(self) -> None:
        """None should not equal a non-None value."""
        matched, reason = apply_operator(None, EnumCriteriaOperator.EQUALS, "value")
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_different_types_int_vs_str(self) -> None:
        """Integer vs string comparison should fail (type-sensitive)."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.EQUALS, "42")
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_different_types_float_vs_int(self) -> None:
        """Float 1.0 equals int 1 in Python (numeric coercion)."""
        matched, _reason = apply_operator(1.0, EnumCriteriaOperator.EQUALS, 1)
        # Python considers 1.0 == 1 to be True
        assert matched is True

    def test_list_equality(self) -> None:
        """List values that are equal should match."""
        matched, reason = apply_operator(
            [1, 2, 3], EnumCriteriaOperator.EQUALS, [1, 2, 3]
        )
        assert matched is True
        assert "equals" in reason.lower()

    def test_list_inequality(self) -> None:
        """List values that differ should not match."""
        matched, reason = apply_operator([1, 2, 3], EnumCriteriaOperator.EQUALS, [1, 2])
        assert matched is False
        assert "does not equal" in reason.lower()

    def test_dict_equality(self) -> None:
        """Dict values that are equal should match."""
        matched, reason = apply_operator(
            {"a": 1, "b": 2}, EnumCriteriaOperator.EQUALS, {"a": 1, "b": 2}
        )
        assert matched is True
        assert "equals" in reason.lower()

    def test_missing_value_fails(self) -> None:
        """MISSING value should fail equals comparison."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.EQUALS, "value")
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# NOT_EQUALS Operator Tests
# =============================================================================


class TestNotEqualsOperator:
    """Tests for EnumCriteriaOperator.NOT_EQUALS."""

    def test_different_values_match(self) -> None:
        """Different values should match for not_equals."""
        matched, reason = apply_operator(
            "hello", EnumCriteriaOperator.NOT_EQUALS, "world"
        )
        assert matched is True
        assert "does not equal" in reason.lower()

    def test_same_values_fail(self) -> None:
        """Same values should fail for not_equals."""
        matched, reason = apply_operator(
            "hello", EnumCriteriaOperator.NOT_EQUALS, "hello"
        )
        assert matched is False
        assert "equals" in reason.lower()

    def test_different_integers(self) -> None:
        """Different integers should match for not_equals."""
        matched, _reason = apply_operator(42, EnumCriteriaOperator.NOT_EQUALS, 0)
        assert matched is True

    def test_same_integers_fail(self) -> None:
        """Same integers should fail for not_equals."""
        matched, _reason = apply_operator(42, EnumCriteriaOperator.NOT_EQUALS, 42)
        assert matched is False

    def test_none_vs_value(self) -> None:
        """None vs non-None should match for not_equals."""
        matched, _reason = apply_operator(
            None, EnumCriteriaOperator.NOT_EQUALS, "value"
        )
        assert matched is True

    def test_none_vs_none_fails(self) -> None:
        """None vs None should fail for not_equals."""
        matched, _reason = apply_operator(None, EnumCriteriaOperator.NOT_EQUALS, None)
        assert matched is False

    def test_missing_value_fails(self) -> None:
        """MISSING value should fail not_equals comparison."""
        matched, reason = apply_operator(
            MISSING, EnumCriteriaOperator.NOT_EQUALS, "value"
        )
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# GREATER_THAN Operator Tests
# =============================================================================


class TestGreaterThanOperator:
    """Tests for EnumCriteriaOperator.GREATER_THAN."""

    def test_integer_greater(self) -> None:
        """Larger integer should match greater_than."""
        matched, reason = apply_operator(10, EnumCriteriaOperator.GREATER_THAN, 5)
        assert matched is True
        assert "10 > 5" in reason

    def test_integer_equal_fails(self) -> None:
        """Equal integer should fail greater_than."""
        matched, reason = apply_operator(5, EnumCriteriaOperator.GREATER_THAN, 5)
        assert matched is False
        assert "is not >" in reason

    def test_integer_less_fails(self) -> None:
        """Smaller integer should fail greater_than."""
        matched, reason = apply_operator(3, EnumCriteriaOperator.GREATER_THAN, 5)
        assert matched is False
        assert "is not >" in reason

    def test_float_greater(self) -> None:
        """Larger float should match greater_than."""
        matched, _reason = apply_operator(3.14, EnumCriteriaOperator.GREATER_THAN, 2.71)
        assert matched is True

    def test_float_less_fails(self) -> None:
        """Smaller float should fail greater_than."""
        matched, _reason = apply_operator(2.71, EnumCriteriaOperator.GREATER_THAN, 3.14)
        assert matched is False

    def test_mixed_int_float(self) -> None:
        """Integer greater than float should match."""
        matched, _reason = apply_operator(5, EnumCriteriaOperator.GREATER_THAN, 4.99)
        assert matched is True

    def test_negative_numbers(self) -> None:
        """Negative number comparison should work."""
        matched, _reason = apply_operator(-1, EnumCriteriaOperator.GREATER_THAN, -5)
        assert matched is True

    def test_non_numeric_actual_fails(self) -> None:
        """Non-numeric actual value should fail with reason."""
        matched, reason = apply_operator("10", EnumCriteriaOperator.GREATER_THAN, 5)
        assert matched is False
        assert "not numeric" in reason.lower()

    def test_non_numeric_expected_fails(self) -> None:
        """Non-numeric expected value should fail with reason."""
        matched, reason = apply_operator(10, EnumCriteriaOperator.GREATER_THAN, "5")
        assert matched is False
        assert "not numeric" in reason.lower()

    def test_boolean_not_numeric(self) -> None:
        """Boolean should not be treated as numeric."""
        matched, reason = apply_operator(True, EnumCriteriaOperator.GREATER_THAN, 0)
        assert matched is False
        assert "not numeric" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.GREATER_THAN, 5)
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# LESS_THAN Operator Tests
# =============================================================================


class TestLessThanOperator:
    """Tests for EnumCriteriaOperator.LESS_THAN."""

    def test_integer_less(self) -> None:
        """Smaller integer should match less_than."""
        matched, reason = apply_operator(3, EnumCriteriaOperator.LESS_THAN, 5)
        assert matched is True
        assert "3 < 5" in reason

    def test_integer_equal_fails(self) -> None:
        """Equal integer should fail less_than."""
        matched, reason = apply_operator(5, EnumCriteriaOperator.LESS_THAN, 5)
        assert matched is False
        assert "is not <" in reason

    def test_integer_greater_fails(self) -> None:
        """Larger integer should fail less_than."""
        matched, reason = apply_operator(10, EnumCriteriaOperator.LESS_THAN, 5)
        assert matched is False
        assert "is not <" in reason

    def test_float_less(self) -> None:
        """Smaller float should match less_than."""
        matched, _reason = apply_operator(2.71, EnumCriteriaOperator.LESS_THAN, 3.14)
        assert matched is True

    def test_negative_numbers(self) -> None:
        """Negative number comparison should work."""
        matched, _reason = apply_operator(-5, EnumCriteriaOperator.LESS_THAN, -1)
        assert matched is True

    def test_non_numeric_actual_fails(self) -> None:
        """Non-numeric actual value should fail with reason."""
        matched, reason = apply_operator("3", EnumCriteriaOperator.LESS_THAN, 5)
        assert matched is False
        assert "not numeric" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.LESS_THAN, 5)
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# GREATER_OR_EQUAL Operator Tests
# =============================================================================


class TestGreaterOrEqualOperator:
    """Tests for EnumCriteriaOperator.GREATER_OR_EQUAL."""

    def test_integer_greater(self) -> None:
        """Larger integer should match greater_or_equal."""
        matched, reason = apply_operator(10, EnumCriteriaOperator.GREATER_OR_EQUAL, 5)
        assert matched is True
        assert "10 >= 5" in reason

    def test_integer_equal(self) -> None:
        """Equal integer should match greater_or_equal."""
        matched, reason = apply_operator(5, EnumCriteriaOperator.GREATER_OR_EQUAL, 5)
        assert matched is True
        assert "5 >= 5" in reason

    def test_integer_less_fails(self) -> None:
        """Smaller integer should fail greater_or_equal."""
        matched, reason = apply_operator(3, EnumCriteriaOperator.GREATER_OR_EQUAL, 5)
        assert matched is False
        assert "is not >=" in reason

    def test_float_equal(self) -> None:
        """Equal float should match greater_or_equal."""
        matched, _reason = apply_operator(
            3.14, EnumCriteriaOperator.GREATER_OR_EQUAL, 3.14
        )
        assert matched is True

    def test_non_numeric_fails(self) -> None:
        """Non-numeric value should fail with reason."""
        matched, reason = apply_operator("10", EnumCriteriaOperator.GREATER_OR_EQUAL, 5)
        assert matched is False
        assert "not numeric" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(
            MISSING, EnumCriteriaOperator.GREATER_OR_EQUAL, 5
        )
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# LESS_OR_EQUAL Operator Tests
# =============================================================================


class TestLessOrEqualOperator:
    """Tests for EnumCriteriaOperator.LESS_OR_EQUAL."""

    def test_integer_less(self) -> None:
        """Smaller integer should match less_or_equal."""
        matched, reason = apply_operator(3, EnumCriteriaOperator.LESS_OR_EQUAL, 5)
        assert matched is True
        assert "3 <= 5" in reason

    def test_integer_equal(self) -> None:
        """Equal integer should match less_or_equal."""
        matched, reason = apply_operator(5, EnumCriteriaOperator.LESS_OR_EQUAL, 5)
        assert matched is True
        assert "5 <= 5" in reason

    def test_integer_greater_fails(self) -> None:
        """Larger integer should fail less_or_equal."""
        matched, reason = apply_operator(10, EnumCriteriaOperator.LESS_OR_EQUAL, 5)
        assert matched is False
        assert "is not <=" in reason

    def test_float_equal(self) -> None:
        """Equal float should match less_or_equal."""
        matched, _reason = apply_operator(
            2.71, EnumCriteriaOperator.LESS_OR_EQUAL, 2.71
        )
        assert matched is True

    def test_non_numeric_fails(self) -> None:
        """Non-numeric value should fail with reason."""
        matched, reason = apply_operator("3", EnumCriteriaOperator.LESS_OR_EQUAL, 5)
        assert matched is False
        assert "not numeric" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.LESS_OR_EQUAL, 5)
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# CONTAINS Operator Tests
# =============================================================================


class TestContainsOperator:
    """Tests for EnumCriteriaOperator.CONTAINS."""

    def test_string_contains_substring(self) -> None:
        """String containing substring should match."""
        matched, reason = apply_operator(
            "hello world", EnumCriteriaOperator.CONTAINS, "world"
        )
        assert matched is True
        assert "contains" in reason.lower()

    def test_string_contains_at_start(self) -> None:
        """String containing substring at start should match."""
        matched, _reason = apply_operator(
            "hello world", EnumCriteriaOperator.CONTAINS, "hello"
        )
        assert matched is True

    def test_string_contains_exact(self) -> None:
        """String equal to search term should match (contains itself)."""
        matched, _reason = apply_operator(
            "hello", EnumCriteriaOperator.CONTAINS, "hello"
        )
        assert matched is True

    def test_string_not_contains_fails(self) -> None:
        """String not containing substring should fail."""
        matched, reason = apply_operator(
            "hello world", EnumCriteriaOperator.CONTAINS, "foo"
        )
        assert matched is False
        assert "does not satisfy" in reason.lower()

    def test_string_contains_empty(self) -> None:
        """Any string contains empty string."""
        matched, _reason = apply_operator("hello", EnumCriteriaOperator.CONTAINS, "")
        assert matched is True

    def test_list_contains_element(self) -> None:
        """List containing element should match."""
        matched, reason = apply_operator([1, 2, 3], EnumCriteriaOperator.CONTAINS, 2)
        assert matched is True
        assert "contains" in reason.lower()

    def test_list_not_contains_element_fails(self) -> None:
        """List not containing element should fail."""
        matched, reason = apply_operator([1, 2, 3], EnumCriteriaOperator.CONTAINS, 4)
        assert matched is False
        assert "not in collection" in reason.lower()

    def test_list_contains_string(self) -> None:
        """List containing string should match."""
        matched, _reason = apply_operator(
            ["a", "b", "c"], EnumCriteriaOperator.CONTAINS, "b"
        )
        assert matched is True

    def test_tuple_contains_element(self) -> None:
        """Tuple containing element should match."""
        matched, _reason = apply_operator((1, 2, 3), EnumCriteriaOperator.CONTAINS, 2)
        assert matched is True

    def test_set_contains_element(self) -> None:
        """Set containing element should match."""
        matched, _reason = apply_operator({1, 2, 3}, EnumCriteriaOperator.CONTAINS, 2)
        assert matched is True

    def test_dict_contains_key(self) -> None:
        """Dict containing key should match (checks keys, not values)."""
        matched, reason = apply_operator(
            {"a": 1, "b": 2}, EnumCriteriaOperator.CONTAINS, "a"
        )
        assert matched is True
        assert "dict keys" in reason.lower()

    def test_dict_not_contains_key_fails(self) -> None:
        """Dict not containing key should fail."""
        matched, reason = apply_operator(
            {"a": 1, "b": 2}, EnumCriteriaOperator.CONTAINS, "c"
        )
        assert matched is False
        assert "not in dict keys" in reason.lower()

    def test_dict_contains_checks_keys_not_values(self) -> None:
        """Dict contains should check keys, not values."""
        matched, _reason = apply_operator(
            {"a": 1, "b": 2}, EnumCriteriaOperator.CONTAINS, 1
        )
        # 1 is a value, not a key
        assert matched is False

    def test_unsupported_type_fails(self) -> None:
        """Unsupported type should fail with reason."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.CONTAINS, 4)
        assert matched is False
        assert "unsupported for type" in reason.lower()

    def test_none_type_unsupported(self) -> None:
        """None type should fail contains with reason."""
        matched, reason = apply_operator(None, EnumCriteriaOperator.CONTAINS, "x")
        assert matched is False
        assert "unsupported for type" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(
            MISSING, EnumCriteriaOperator.CONTAINS, "value"
        )
        assert matched is False
        assert "missing" in reason.lower()

    def test_string_contains_none_converts_to_empty(self) -> None:
        """Searching for None in string should convert to empty string."""
        matched, _reason = apply_operator("hello", EnumCriteriaOperator.CONTAINS, None)
        # None is converted to "" which is contained in any string
        assert matched is True


# =============================================================================
# NOT_CONTAINS Operator Tests
# =============================================================================


class TestNotContainsOperator:
    """Tests for EnumCriteriaOperator.NOT_CONTAINS."""

    def test_string_not_contains_substring(self) -> None:
        """String not containing substring should match."""
        matched, reason = apply_operator(
            "hello world", EnumCriteriaOperator.NOT_CONTAINS, "foo"
        )
        assert matched is True
        assert "not_contains" in reason.lower()

    def test_string_contains_substring_fails(self) -> None:
        """String containing substring should fail not_contains."""
        matched, reason = apply_operator(
            "hello world", EnumCriteriaOperator.NOT_CONTAINS, "world"
        )
        assert matched is False
        assert "does not satisfy" in reason.lower()

    def test_list_not_contains_element(self) -> None:
        """List not containing element should match."""
        matched, reason = apply_operator(
            [1, 2, 3], EnumCriteriaOperator.NOT_CONTAINS, 4
        )
        assert matched is True
        assert "not_contains" in reason.lower()

    def test_list_contains_element_fails(self) -> None:
        """List containing element should fail not_contains."""
        matched, _reason = apply_operator(
            [1, 2, 3], EnumCriteriaOperator.NOT_CONTAINS, 2
        )
        assert matched is False

    def test_dict_not_contains_key(self) -> None:
        """Dict not containing key should match."""
        matched, reason = apply_operator(
            {"a": 1}, EnumCriteriaOperator.NOT_CONTAINS, "b"
        )
        assert matched is True
        assert "not_contains" in reason.lower()

    def test_dict_contains_key_fails(self) -> None:
        """Dict containing key should fail not_contains."""
        matched, _reason = apply_operator(
            {"a": 1}, EnumCriteriaOperator.NOT_CONTAINS, "a"
        )
        assert matched is False

    def test_unsupported_type_fails(self) -> None:
        """Unsupported type should fail with reason."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.NOT_CONTAINS, 4)
        assert matched is False
        assert "unsupported for type" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(
            MISSING, EnumCriteriaOperator.NOT_CONTAINS, "value"
        )
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# REGEX Operator Tests
# =============================================================================


class TestRegexOperator:
    """Tests for EnumCriteriaOperator.REGEX."""

    def test_valid_regex_matches(self) -> None:
        """Valid regex pattern that matches should succeed."""
        matched, reason = apply_operator("hello123", EnumCriteriaOperator.REGEX, r"\d+")
        assert matched is True
        assert "matches pattern" in reason.lower()

    def test_valid_regex_no_match(self) -> None:
        """Valid regex pattern that doesn't match should fail."""
        matched, reason = apply_operator("hello", EnumCriteriaOperator.REGEX, r"\d+")
        assert matched is False
        assert "does not match pattern" in reason.lower()

    def test_regex_anchor_start(self) -> None:
        """Regex with start anchor should work."""
        matched, _reason = apply_operator(
            "hello world", EnumCriteriaOperator.REGEX, r"^hello"
        )
        assert matched is True

    def test_regex_anchor_end(self) -> None:
        """Regex with end anchor should work."""
        matched, _reason = apply_operator(
            "hello world", EnumCriteriaOperator.REGEX, r"world$"
        )
        assert matched is True

    def test_regex_full_match(self) -> None:
        """Regex for full string match."""
        matched, _reason = apply_operator(
            "hello", EnumCriteriaOperator.REGEX, r"^hello$"
        )
        assert matched is True

    def test_regex_full_match_fails(self) -> None:
        """Regex for full string match that fails."""
        matched, _reason = apply_operator(
            "hello world", EnumCriteriaOperator.REGEX, r"^hello$"
        )
        assert matched is False

    def test_regex_case_sensitive(self) -> None:
        """Regex is case-sensitive by default."""
        matched, _reason = apply_operator("HELLO", EnumCriteriaOperator.REGEX, r"hello")
        assert matched is False

    def test_regex_case_insensitive_flag(self) -> None:
        """Regex with case-insensitive flag."""
        matched, _reason = apply_operator(
            "HELLO", EnumCriteriaOperator.REGEX, r"(?i)hello"
        )
        assert matched is True

    def test_regex_special_characters(self) -> None:
        """Regex with escaped special characters."""
        matched, _reason = apply_operator(
            "file.txt", EnumCriteriaOperator.REGEX, r"file\.txt"
        )
        assert matched is True

    def test_regex_group_capture(self) -> None:
        """Regex with capture groups should match."""
        matched, _reason = apply_operator(
            "error: 404", EnumCriteriaOperator.REGEX, r"error: (\d+)"
        )
        assert matched is True

    def test_regex_converts_to_string(self) -> None:
        """Non-string actual values are converted to string for matching."""
        matched, _reason = apply_operator(12345, EnumCriteriaOperator.REGEX, r"234")
        assert matched is True

    def test_regex_none_converts_to_empty(self) -> None:
        """None actual value converts to empty string."""
        matched, _reason = apply_operator(None, EnumCriteriaOperator.REGEX, r"^$")
        assert matched is True

    def test_regex_empty_pattern_matches_anything(self) -> None:
        """Empty pattern matches any string (via re.search)."""
        matched, _reason = apply_operator("hello", EnumCriteriaOperator.REGEX, r"")
        assert matched is True

    def test_invalid_regex_pattern_fails(self) -> None:
        """Invalid regex pattern should fail (when called directly via apply_operator)."""
        matched, reason = apply_operator(
            "test", EnumCriteriaOperator.REGEX, r"[invalid"
        )
        assert matched is False
        assert "invalid regex" in reason.lower()

    def test_non_string_pattern_fails(self) -> None:
        """Non-string pattern should fail with reason."""
        matched, reason = apply_operator("test", EnumCriteriaOperator.REGEX, 123)
        assert matched is False
        assert "must be string" in reason.lower()

    def test_missing_fails(self) -> None:
        """MISSING value should fail with reason."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.REGEX, r"\d+")
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# IS_NULL Operator Tests
# =============================================================================


class TestIsNullOperator:
    """Tests for EnumCriteriaOperator.IS_NULL."""

    def test_none_is_null(self) -> None:
        """None value should match is_null."""
        matched, reason = apply_operator(None, EnumCriteriaOperator.IS_NULL, None)
        assert matched is True
        assert "is null" in reason.lower()

    def test_string_is_not_null(self) -> None:
        """String value should fail is_null."""
        matched, reason = apply_operator("hello", EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "expected null" in reason.lower()

    def test_integer_is_not_null(self) -> None:
        """Integer value should fail is_null."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "expected null" in reason.lower()

    def test_zero_is_not_null(self) -> None:
        """Zero (falsy but not None) should fail is_null."""
        matched, reason = apply_operator(0, EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "expected null" in reason.lower()

    def test_empty_string_is_not_null(self) -> None:
        """Empty string (falsy but not None) should fail is_null."""
        matched, reason = apply_operator("", EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "expected null" in reason.lower()

    def test_empty_list_is_not_null(self) -> None:
        """Empty list (falsy but not None) should fail is_null."""
        matched, reason = apply_operator([], EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "expected null" in reason.lower()

    def test_false_is_not_null(self) -> None:
        """False (falsy but not None) should fail is_null."""
        matched, reason = apply_operator(False, EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "expected null" in reason.lower()

    def test_missing_fails_is_null(self) -> None:
        """MISSING value should fail is_null (MISSING != None)."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "missing, not null" in reason.lower()


# =============================================================================
# IS_NOT_NULL Operator Tests
# =============================================================================


class TestIsNotNullOperator:
    """Tests for EnumCriteriaOperator.IS_NOT_NULL."""

    def test_string_is_not_null(self) -> None:
        """String value should match is_not_null."""
        matched, reason = apply_operator(
            "hello", EnumCriteriaOperator.IS_NOT_NULL, None
        )
        assert matched is True
        assert "not null" in reason.lower()

    def test_integer_is_not_null(self) -> None:
        """Integer value should match is_not_null."""
        matched, reason = apply_operator(42, EnumCriteriaOperator.IS_NOT_NULL, None)
        assert matched is True
        assert "not null" in reason.lower()

    def test_zero_is_not_null(self) -> None:
        """Zero (falsy but not None) should match is_not_null."""
        matched, _reason = apply_operator(0, EnumCriteriaOperator.IS_NOT_NULL, None)
        assert matched is True

    def test_empty_string_is_not_null(self) -> None:
        """Empty string (falsy but not None) should match is_not_null."""
        matched, _reason = apply_operator("", EnumCriteriaOperator.IS_NOT_NULL, None)
        assert matched is True

    def test_empty_list_is_not_null(self) -> None:
        """Empty list (falsy but not None) should match is_not_null."""
        matched, _reason = apply_operator([], EnumCriteriaOperator.IS_NOT_NULL, None)
        assert matched is True

    def test_false_is_not_null(self) -> None:
        """False (falsy but not None) should match is_not_null."""
        matched, _reason = apply_operator(False, EnumCriteriaOperator.IS_NOT_NULL, None)
        assert matched is True

    def test_none_fails_is_not_null(self) -> None:
        """None value should fail is_not_null."""
        matched, reason = apply_operator(None, EnumCriteriaOperator.IS_NOT_NULL, None)
        assert matched is False
        assert "is null" in reason.lower()

    def test_missing_fails_is_not_null(self) -> None:
        """MISSING value should fail is_not_null."""
        matched, reason = apply_operator(
            MISSING, EnumCriteriaOperator.IS_NOT_NULL, None
        )
        assert matched is False
        assert "missing" in reason.lower()


# =============================================================================
# MISSING Sentinel Edge Cases
# =============================================================================


class TestMissingSentinel:
    """Tests for MISSING sentinel behavior across all operators."""

    @pytest.mark.parametrize(
        "operator",
        [
            EnumCriteriaOperator.EQUALS,
            EnumCriteriaOperator.NOT_EQUALS,
            EnumCriteriaOperator.GREATER_THAN,
            EnumCriteriaOperator.LESS_THAN,
            EnumCriteriaOperator.GREATER_OR_EQUAL,
            EnumCriteriaOperator.LESS_OR_EQUAL,
            EnumCriteriaOperator.CONTAINS,
            EnumCriteriaOperator.NOT_CONTAINS,
            EnumCriteriaOperator.REGEX,
        ],
    )
    def test_missing_fails_all_comparison_operators(
        self, operator: EnumCriteriaOperator
    ) -> None:
        """MISSING should fail all comparison operators with 'field is missing' reason."""
        matched, reason = apply_operator(MISSING, operator, "any_value")
        assert matched is False
        assert "missing" in reason.lower()

    def test_missing_is_null_returns_specific_reason(self) -> None:
        """MISSING with is_null should return specific 'missing, not null' reason."""
        matched, reason = apply_operator(MISSING, EnumCriteriaOperator.IS_NULL, None)
        assert matched is False
        assert "missing, not null" in reason.lower()

    def test_missing_is_not_null_returns_specific_reason(self) -> None:
        """MISSING with is_not_null should return specific 'missing' reason."""
        matched, reason = apply_operator(
            MISSING, EnumCriteriaOperator.IS_NOT_NULL, None
        )
        assert matched is False
        assert reason == "value is missing"
