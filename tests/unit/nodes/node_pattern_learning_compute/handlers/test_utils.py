# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for pattern learning utility functions.

This module tests the shared utility functions for pattern learning handlers:
    - jaccard_similarity: Set similarity computation
    - normalize_identifier: Single identifier normalization
    - normalize_identifiers: Collection normalization with deduplication
    - compute_normalized_distance: Numeric distance normalization
    - distance_to_similarity: Distance to similarity conversion
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_learning_compute.handlers.utils import (
    compute_normalized_distance,
    distance_to_similarity,
    jaccard_similarity,
    normalize_identifier,
    normalize_identifiers,
)

# =============================================================================
# jaccard_similarity Tests
# =============================================================================


@pytest.mark.unit
class TestJaccardSimilarity:
    """Tests for the jaccard_similarity function."""

    # -------------------------------------------------------------------------
    # Empty Set Cases
    # -------------------------------------------------------------------------

    def test_both_sets_empty_returns_zero(self) -> None:
        """Empty sets should return 0.0 by convention."""
        result = jaccard_similarity(set(), set())
        assert result == 0.0

    def test_first_set_empty_returns_zero(self) -> None:
        """Empty first set with non-empty second set returns 0.0."""
        result = jaccard_similarity(set(), {"a", "b", "c"})
        assert result == 0.0

    def test_second_set_empty_returns_zero(self) -> None:
        """Non-empty first set with empty second set returns 0.0."""
        result = jaccard_similarity({"a", "b", "c"}, set())
        assert result == 0.0

    # -------------------------------------------------------------------------
    # Identical Set Cases
    # -------------------------------------------------------------------------

    def test_identical_sets_return_one(self) -> None:
        """Identical non-empty sets should return 1.0."""
        set_a = {"a", "b", "c"}
        set_b = {"a", "b", "c"}
        result = jaccard_similarity(set_a, set_b)
        assert result == 1.0

    def test_identical_single_element_sets(self) -> None:
        """Identical single-element sets should return 1.0."""
        result = jaccard_similarity({"x"}, {"x"})
        assert result == 1.0

    def test_identical_large_sets(self) -> None:
        """Identical large sets should return 1.0."""
        large_set = {f"item_{i}" for i in range(100)}
        result = jaccard_similarity(large_set, large_set.copy())
        assert result == 1.0

    # -------------------------------------------------------------------------
    # Disjoint Set Cases
    # -------------------------------------------------------------------------

    def test_disjoint_sets_return_zero(self) -> None:
        """Completely disjoint sets should return 0.0."""
        result = jaccard_similarity({"a", "b", "c"}, {"d", "e", "f"})
        assert result == 0.0

    def test_disjoint_single_element_sets(self) -> None:
        """Disjoint single-element sets should return 0.0."""
        result = jaccard_similarity({"a"}, {"b"})
        assert result == 0.0

    # -------------------------------------------------------------------------
    # Partial Overlap Cases
    # -------------------------------------------------------------------------

    def test_partial_overlap_half(self) -> None:
        """Sets with 50% overlap should return 0.5.

        intersection = {b, c} = 2
        union = {a, b, c, d} = 4
        similarity = 2/4 = 0.5
        """
        result = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert result == 0.5

    def test_partial_overlap_one_third(self) -> None:
        """Sets with 1/3 overlap.

        intersection = {c} = 1
        union = {a, b, c, d, e} = 5
        similarity = 1/5 = 0.2
        """
        result = jaccard_similarity({"a", "b", "c"}, {"c", "d", "e"})
        assert result == pytest.approx(0.2)

    def test_partial_overlap_two_thirds(self) -> None:
        """Sets with 2/3 overlap.

        intersection = {a, b} = 2
        union = {a, b, c} = 3
        similarity = 2/3 = 0.666...
        """
        result = jaccard_similarity({"a", "b"}, {"a", "b", "c"})
        assert result == pytest.approx(2 / 3)

    def test_subset_returns_ratio(self) -> None:
        """When one set is subset of another.

        intersection = {a, b} = 2
        union = {a, b, c, d} = 4
        similarity = 2/4 = 0.5
        """
        result = jaccard_similarity({"a", "b"}, {"a", "b", "c", "d"})
        assert result == 0.5

    def test_superset_returns_ratio(self) -> None:
        """When first set is superset of second.

        intersection = {a, b} = 2
        union = {a, b, c, d} = 4
        similarity = 2/4 = 0.5
        """
        result = jaccard_similarity({"a", "b", "c", "d"}, {"a", "b"})
        assert result == 0.5

    # -------------------------------------------------------------------------
    # Symmetry Tests
    # -------------------------------------------------------------------------

    def test_symmetry(self) -> None:
        """jaccard_similarity(A, B) should equal jaccard_similarity(B, A)."""
        set_a = {"a", "b", "c"}
        set_b = {"b", "c", "d", "e"}

        result_ab = jaccard_similarity(set_a, set_b)
        result_ba = jaccard_similarity(set_b, set_a)

        assert result_ab == result_ba

    # -------------------------------------------------------------------------
    # Boundary Value Tests
    # -------------------------------------------------------------------------

    def test_returns_value_in_valid_range(self) -> None:
        """Result should always be in [0.0, 1.0]."""
        test_cases = [
            (set(), set()),
            ({"a"}, {"b"}),
            ({"a", "b"}, {"a", "b"}),
            ({"a"}, {"a", "b", "c", "d", "e"}),
            ({f"x{i}" for i in range(50)}, {f"x{i}" for i in range(25, 75)}),
        ]

        for set_a, set_b in test_cases:
            result = jaccard_similarity(set_a, set_b)
            assert 0.0 <= result <= 1.0, f"Out of range for {set_a} vs {set_b}"


# =============================================================================
# normalize_identifier Tests
# =============================================================================


@pytest.mark.unit
class TestNormalizeIdentifier:
    """Tests for the normalize_identifier function."""

    # -------------------------------------------------------------------------
    # Case Conversion
    # -------------------------------------------------------------------------

    def test_converts_uppercase_to_lowercase(self) -> None:
        """Uppercase letters should be converted to lowercase."""
        assert normalize_identifier("MYCLASS") == "myclass"

    def test_converts_mixed_case_to_lowercase(self) -> None:
        """Mixed case should be converted to all lowercase."""
        assert normalize_identifier("MyClassName") == "myclassname"

    def test_preserves_lowercase(self) -> None:
        """Already lowercase strings should be unchanged."""
        assert normalize_identifier("myfunction") == "myfunction"

    def test_preserves_numbers(self) -> None:
        """Numbers in identifiers should be preserved."""
        assert normalize_identifier("Class123") == "class123"
        assert normalize_identifier("123abc") == "123abc"

    def test_preserves_underscores(self) -> None:
        """Underscores should be preserved."""
        assert normalize_identifier("my_class_name") == "my_class_name"
        assert normalize_identifier("MY_CONSTANT") == "my_constant"

    # -------------------------------------------------------------------------
    # Whitespace Handling
    # -------------------------------------------------------------------------

    def test_strips_leading_whitespace(self) -> None:
        """Leading whitespace should be stripped."""
        assert normalize_identifier("  MyClass") == "myclass"
        assert normalize_identifier("\t\tMyClass") == "myclass"

    def test_strips_trailing_whitespace(self) -> None:
        """Trailing whitespace should be stripped."""
        assert normalize_identifier("MyClass  ") == "myclass"
        assert normalize_identifier("MyClass\t\t") == "myclass"

    def test_strips_both_leading_and_trailing_whitespace(self) -> None:
        """Both leading and trailing whitespace should be stripped."""
        assert normalize_identifier("  CONSTANT  ") == "constant"
        assert normalize_identifier("\t MyClass \n") == "myclass"

    def test_internal_whitespace_preserved(self) -> None:
        """Internal whitespace is preserved (though unusual for identifiers)."""
        # This is a valid edge case - internal spaces are kept
        assert normalize_identifier("my class") == "my class"

    def test_whitespace_only_returns_empty(self) -> None:
        """Whitespace-only input should return empty string."""
        assert normalize_identifier("   ") == ""
        assert normalize_identifier("\t\n") == ""

    # -------------------------------------------------------------------------
    # Edge Cases
    # -------------------------------------------------------------------------

    def test_empty_string_returns_empty(self) -> None:
        """Empty string should return empty string."""
        assert normalize_identifier("") == ""

    def test_single_character(self) -> None:
        """Single character should be normalized."""
        assert normalize_identifier("A") == "a"
        assert normalize_identifier("z") == "z"

    def test_unicode_lowercase(self) -> None:
        """Unicode characters should be lowercased where applicable."""
        # Python's str.lower() handles Unicode
        assert normalize_identifier("CAFE") == "cafe"
        # Note: accented characters may behave differently
        assert normalize_identifier("Cafe") == "cafe"

    def test_special_characters_preserved(self) -> None:
        """Special characters (other than whitespace) are preserved."""
        assert normalize_identifier("__init__") == "__init__"
        assert normalize_identifier("_PrivateVar") == "_privatevar"


# =============================================================================
# normalize_identifiers Tests
# =============================================================================


@pytest.mark.unit
class TestNormalizeIdentifiers:
    """Tests for the normalize_identifiers function."""

    # -------------------------------------------------------------------------
    # Basic Normalization
    # -------------------------------------------------------------------------

    def test_normalizes_mixed_case(self) -> None:
        """All identifiers should be normalized to lowercase."""
        result = normalize_identifiers(["MyClass", "my_func", "MY_CONST"])
        assert result == ("my_const", "my_func", "myclass")

    def test_returns_sorted_tuple(self) -> None:
        """Result should be sorted alphabetically."""
        result = normalize_identifiers(["Z", "A", "M"])
        assert result == ("a", "m", "z")

    def test_returns_tuple_not_list(self) -> None:
        """Result should be a tuple for immutability."""
        result = normalize_identifiers(["a", "b"])
        assert isinstance(result, tuple)

    # -------------------------------------------------------------------------
    # Deduplication
    # -------------------------------------------------------------------------

    def test_removes_exact_duplicates(self) -> None:
        """Exact duplicates should be removed."""
        result = normalize_identifiers(["MyClass", "MyClass", "MyClass"])
        assert result == ("myclass",)

    def test_removes_case_insensitive_duplicates(self) -> None:
        """Case-different duplicates should be removed."""
        result = normalize_identifiers(["MyClass", "myclass", "MYCLASS"])
        assert result == ("myclass",)

    def test_removes_whitespace_duplicates(self) -> None:
        """Whitespace-different duplicates should be removed."""
        result = normalize_identifiers(["MyClass", "  MyClass  ", "\tMyClass"])
        assert result == ("myclass",)

    def test_multiple_duplicates_reduced(self) -> None:
        """Multiple different duplicates are all reduced."""
        result = normalize_identifiers(
            ["ClassA", "classa", "CLASSA", "ClassB", "classb", "CLASSB"]
        )
        assert result == ("classa", "classb")

    # -------------------------------------------------------------------------
    # Empty and Whitespace Handling
    # -------------------------------------------------------------------------

    def test_empty_list_returns_empty_tuple(self) -> None:
        """Empty input should return empty tuple."""
        result = normalize_identifiers([])
        assert result == ()

    def test_removes_empty_strings(self) -> None:
        """Empty strings should be removed from output."""
        result = normalize_identifiers(["", "valid", ""])
        assert result == ("valid",)

    def test_removes_whitespace_only_strings(self) -> None:
        """Whitespace-only strings should be removed."""
        result = normalize_identifiers(["   ", "valid", "\t\n"])
        assert result == ("valid",)

    def test_all_empty_strings_returns_empty_tuple(self) -> None:
        """If all inputs are empty/whitespace, return empty tuple."""
        result = normalize_identifiers(["", "   ", "\t"])
        assert result == ()

    # -------------------------------------------------------------------------
    # Unicode Handling
    # -------------------------------------------------------------------------

    def test_unicode_normalization(self) -> None:
        """Unicode identifiers should be normalized."""
        result = normalize_identifiers(["Cafe", "CAFE", "cafe"])
        assert result == ("cafe",)

    def test_unicode_preserved_after_lowercase(self) -> None:
        """Unicode characters are preserved after lowercasing."""
        # Standard ASCII test
        result = normalize_identifiers(["Alpha", "Beta"])
        assert result == ("alpha", "beta")

    # -------------------------------------------------------------------------
    # Input Types
    # -------------------------------------------------------------------------

    def test_accepts_list(self) -> None:
        """Should accept list input."""
        result = normalize_identifiers(["a", "b", "c"])
        assert result == ("a", "b", "c")

    def test_accepts_tuple(self) -> None:
        """Should accept tuple input."""
        result = normalize_identifiers(("a", "b", "c"))
        assert result == ("a", "b", "c")

    def test_accepts_set(self) -> None:
        """Should accept set input."""
        result = normalize_identifiers({"c", "a", "b"})
        assert result == ("a", "b", "c")

    def test_accepts_generator(self) -> None:
        """Should accept generator input."""
        result = normalize_identifiers(x for x in ["C", "A", "B"])
        assert result == ("a", "b", "c")

    # -------------------------------------------------------------------------
    # Sorting Behavior
    # -------------------------------------------------------------------------

    def test_sorting_is_case_insensitive_result(self) -> None:
        """Sorted result is alphabetical on normalized values."""
        result = normalize_identifiers(["zebra", "Apple", "MANGO"])
        assert result == ("apple", "mango", "zebra")

    def test_deterministic_output(self) -> None:
        """Same input should always produce same output."""
        inputs = ["C", "A", "B", "D"]
        result1 = normalize_identifiers(inputs)
        result2 = normalize_identifiers(inputs)
        result3 = normalize_identifiers(reversed(inputs))

        assert result1 == result2 == result3 == ("a", "b", "c", "d")


# =============================================================================
# compute_normalized_distance Tests
# =============================================================================


@pytest.mark.unit
class TestComputeNormalizedDistance:
    """Tests for the compute_normalized_distance function."""

    # -------------------------------------------------------------------------
    # Zero Distance Cases
    # -------------------------------------------------------------------------

    def test_identical_values_return_zero(self) -> None:
        """Identical values should return 0.0 distance."""
        assert compute_normalized_distance(10, 10, 100) == 0.0
        assert compute_normalized_distance(0, 0, 100) == 0.0
        assert compute_normalized_distance(50.5, 50.5, 100) == 0.0

    def test_zero_values_return_zero(self) -> None:
        """Both zero values should return 0.0 distance."""
        assert compute_normalized_distance(0, 0, 50) == 0.0

    # -------------------------------------------------------------------------
    # Maximum Distance Cases
    # -------------------------------------------------------------------------

    def test_max_difference_returns_one(self) -> None:
        """Difference equal to max_expected returns 1.0."""
        assert compute_normalized_distance(0, 100, 100) == 1.0
        assert compute_normalized_distance(100, 0, 100) == 1.0

    def test_difference_at_max_expected(self) -> None:
        """When |a-b| == max_expected, should return 1.0."""
        assert compute_normalized_distance(25, 75, 50) == 1.0
        assert compute_normalized_distance(10, 60, 50) == 1.0

    # -------------------------------------------------------------------------
    # Clamping (Beyond Max) Cases
    # -------------------------------------------------------------------------

    def test_beyond_max_clamped_to_one(self) -> None:
        """Difference exceeding max_expected should be clamped to 1.0."""
        result = compute_normalized_distance(0, 200, 100)
        assert result == 1.0

    def test_far_beyond_max_clamped_to_one(self) -> None:
        """Very large differences should be clamped to 1.0."""
        result = compute_normalized_distance(0, 10000, 100)
        assert result == 1.0

    def test_negative_values_clamped(self) -> None:
        """Negative value differences should still be clamped."""
        result = compute_normalized_distance(-100, 100, 50)
        assert result == 1.0

    # -------------------------------------------------------------------------
    # Intermediate Distance Cases
    # -------------------------------------------------------------------------

    def test_half_distance(self) -> None:
        """Half of max_expected should return 0.5."""
        assert compute_normalized_distance(25, 75, 100) == 0.5
        assert compute_normalized_distance(0, 50, 100) == 0.5

    def test_quarter_distance(self) -> None:
        """Quarter of max_expected should return 0.25."""
        assert compute_normalized_distance(0, 25, 100) == 0.25

    def test_three_quarter_distance(self) -> None:
        """Three quarters of max_expected should return 0.75."""
        assert compute_normalized_distance(0, 75, 100) == 0.75

    def test_floating_point_precision(self) -> None:
        """Should handle floating point values correctly."""
        result = compute_normalized_distance(0.1, 0.3, 1.0)
        assert result == pytest.approx(0.2)

    # -------------------------------------------------------------------------
    # Symmetry Tests
    # -------------------------------------------------------------------------

    def test_symmetry(self) -> None:
        """Distance(a, b) should equal distance(b, a)."""
        result_ab = compute_normalized_distance(10, 40, 100)
        result_ba = compute_normalized_distance(40, 10, 100)
        assert result_ab == result_ba

    # -------------------------------------------------------------------------
    # Invalid max_expected Tests
    # -------------------------------------------------------------------------

    def test_zero_max_expected_raises_error(self) -> None:
        """Zero max_expected should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            compute_normalized_distance(10, 20, 0)

        assert "max_expected must be positive" in str(exc_info.value)
        assert "0" in str(exc_info.value)

    def test_negative_max_expected_raises_error(self) -> None:
        """Negative max_expected should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            compute_normalized_distance(10, 20, -50)

        assert "max_expected must be positive" in str(exc_info.value)
        assert "-50" in str(exc_info.value)

    def test_very_small_negative_max_expected_raises_error(self) -> None:
        """Very small negative max_expected should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            compute_normalized_distance(10, 20, -0.001)

        assert "max_expected must be positive" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Boundary Value Tests
    # -------------------------------------------------------------------------

    def test_returns_value_in_valid_range(self) -> None:
        """Result should always be in [0.0, 1.0]."""
        test_cases = [
            (0, 0, 100),
            (100, 100, 100),
            (0, 100, 100),
            (0, 1000, 100),  # Beyond max
            (-50, 50, 200),
            (0.001, 0.002, 0.01),
        ]

        for a, b, max_exp in test_cases:
            result = compute_normalized_distance(a, b, max_exp)
            assert 0.0 <= result <= 1.0, f"Out of range for ({a}, {b}, {max_exp})"

    def test_very_small_max_expected(self) -> None:
        """Should handle very small positive max_expected."""
        result = compute_normalized_distance(0.0001, 0.0002, 0.001)
        assert result == pytest.approx(0.1)


# =============================================================================
# distance_to_similarity Tests
# =============================================================================


@pytest.mark.unit
class TestDistanceToSimilarity:
    """Tests for the distance_to_similarity function."""

    # -------------------------------------------------------------------------
    # Boundary Value Cases
    # -------------------------------------------------------------------------

    def test_zero_distance_returns_one(self) -> None:
        """Zero distance should return 1.0 similarity."""
        assert distance_to_similarity(0.0) == 1.0

    def test_one_distance_returns_zero(self) -> None:
        """Maximum distance (1.0) should return 0.0 similarity."""
        assert distance_to_similarity(1.0) == 0.0

    # -------------------------------------------------------------------------
    # Middle Value Cases
    # -------------------------------------------------------------------------

    def test_half_distance_returns_half_similarity(self) -> None:
        """Distance of 0.5 should return similarity of 0.5."""
        assert distance_to_similarity(0.5) == 0.5

    def test_quarter_distance(self) -> None:
        """Distance of 0.25 should return similarity of 0.75."""
        assert distance_to_similarity(0.25) == 0.75

    def test_three_quarter_distance(self) -> None:
        """Distance of 0.75 should return similarity of 0.25."""
        assert distance_to_similarity(0.75) == 0.25

    def test_arbitrary_distance(self) -> None:
        """Arbitrary distance should return correct similarity."""
        assert distance_to_similarity(0.3) == pytest.approx(0.7)
        assert distance_to_similarity(0.7) == pytest.approx(0.3)
        assert distance_to_similarity(0.1) == pytest.approx(0.9)

    # -------------------------------------------------------------------------
    # Precision Tests
    # -------------------------------------------------------------------------

    def test_floating_point_precision(self) -> None:
        """Should handle floating point values with precision."""
        assert distance_to_similarity(0.333333) == pytest.approx(0.666667, rel=1e-5)
        assert distance_to_similarity(0.123456) == pytest.approx(0.876544, rel=1e-5)

    def test_very_small_distance(self) -> None:
        """Very small distance should return nearly 1.0 similarity."""
        result = distance_to_similarity(0.0001)
        assert result == pytest.approx(0.9999)

    def test_nearly_one_distance(self) -> None:
        """Nearly maximum distance should return nearly 0.0 similarity."""
        result = distance_to_similarity(0.9999)
        assert result == pytest.approx(0.0001)

    # -------------------------------------------------------------------------
    # Property Tests
    # -------------------------------------------------------------------------

    def test_inverse_relationship(self) -> None:
        """distance + similarity should always equal 1.0."""
        distances = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]

        for d in distances:
            s = distance_to_similarity(d)
            assert d + s == pytest.approx(1.0)

    def test_monotonically_decreasing(self) -> None:
        """Similarity should decrease as distance increases."""
        distances = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        similarities = [distance_to_similarity(d) for d in distances]

        for i in range(len(similarities) - 1):
            assert similarities[i] > similarities[i + 1]

    # -------------------------------------------------------------------------
    # Edge Cases (Out of Expected Range)
    # -------------------------------------------------------------------------

    def test_negative_distance_produces_similarity_above_one(self) -> None:
        """Negative distance (invalid) produces similarity > 1.0.

        Note: This is technically invalid input but the function doesn't
        validate. Tests document actual behavior.
        """
        result = distance_to_similarity(-0.5)
        assert result == 1.5  # 1.0 - (-0.5) = 1.5

    def test_distance_above_one_produces_negative_similarity(self) -> None:
        """Distance > 1.0 (invalid) produces negative similarity.

        Note: This is technically invalid input but the function doesn't
        validate. Tests document actual behavior.
        """
        result = distance_to_similarity(1.5)
        assert result == -0.5  # 1.0 - 1.5 = -0.5


# =============================================================================
# Integration Tests (Combining Functions)
# =============================================================================


@pytest.mark.unit
class TestUtilsIntegration:
    """Integration tests combining multiple utility functions."""

    def test_distance_to_similarity_with_normalized_distance(self) -> None:
        """compute_normalized_distance output works with distance_to_similarity."""
        distance = compute_normalized_distance(0, 50, 100)
        similarity = distance_to_similarity(distance)

        assert distance == 0.5
        assert similarity == 0.5

    def test_identical_values_produce_max_similarity(self) -> None:
        """Identical values through full pipeline produce 1.0 similarity."""
        distance = compute_normalized_distance(42, 42, 100)
        similarity = distance_to_similarity(distance)

        assert distance == 0.0
        assert similarity == 1.0

    def test_max_difference_produces_min_similarity(self) -> None:
        """Maximum difference through full pipeline produces 0.0 similarity."""
        distance = compute_normalized_distance(0, 100, 100)
        similarity = distance_to_similarity(distance)

        assert distance == 1.0
        assert similarity == 0.0

    def test_jaccard_with_normalized_identifiers(self) -> None:
        """jaccard_similarity works with normalize_identifiers output."""
        ids_a = normalize_identifiers(["MyClass", "MyFunc", "MyConst"])
        ids_b = normalize_identifiers(["myclass", "OtherFunc", "myconst"])

        # Convert tuples to sets for Jaccard
        set_a = set(ids_a)
        set_b = set(ids_b)

        # intersection = {myclass, myconst} = 2
        # union = {myclass, myfunc, myconst, otherfunc} = 4
        # similarity = 2/4 = 0.5
        similarity = jaccard_similarity(set_a, set_b)
        assert similarity == 0.5
