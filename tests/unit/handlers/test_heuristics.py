# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for contribution heuristic functions.

This module tests the pure heuristic functions in handlers/heuristics.py:
- compute_equal_split: Equal credit distribution
- compute_recency_weighted: Linear ramp with position-based weights
- compute_first_match: All credit to first pattern
- apply_heuristic: Dispatcher function

Test cases cover:
- Empty input handling
- Single pattern handling
- Multiple patterns without duplicates
- Multiple patterns with duplicates (accumulation)
- Confidence scores per method

Reference:
    - OMN-1679: FEEDBACK-004 contribution heuristic for outcome attribution
"""

from __future__ import annotations

from uuid import UUID

import pytest

from omniintelligence.enums import EnumHeuristicMethod, HEURISTIC_CONFIDENCE
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.heuristics import (
    apply_heuristic,
    compute_equal_split,
    compute_first_match,
    compute_recency_weighted,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pattern_a() -> UUID:
    """First test pattern."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def pattern_b() -> UUID:
    """Second test pattern."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def pattern_c() -> UUID:
    """Third test pattern."""
    return UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# =============================================================================
# Test Class: compute_equal_split
# =============================================================================


@pytest.mark.unit
class TestComputeEqualSplit:
    """Tests for equal split heuristic."""

    def test_empty_input_returns_empty_dict(self) -> None:
        """Empty pattern list returns empty weights."""
        result = compute_equal_split([])
        assert result == {}

    def test_single_pattern_gets_full_weight(self, pattern_a: UUID) -> None:
        """Single pattern gets weight of 1.0."""
        result = compute_equal_split([pattern_a])
        assert result == {str(pattern_a): 1.0}

    def test_two_patterns_get_half_each(self, pattern_a: UUID, pattern_b: UUID) -> None:
        """Two patterns each get 0.5."""
        result = compute_equal_split([pattern_a, pattern_b])
        assert result[str(pattern_a)] == 0.5
        assert result[str(pattern_b)] == 0.5

    def test_three_patterns_get_one_third_each(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """Three patterns each get 1/3."""
        result = compute_equal_split([pattern_a, pattern_b, pattern_c])
        expected = 1.0 / 3
        assert abs(result[str(pattern_a)] - expected) < 1e-9
        assert abs(result[str(pattern_b)] - expected) < 1e-9
        assert abs(result[str(pattern_c)] - expected) < 1e-9

    def test_weights_sum_to_one(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """All weights sum to 1.0."""
        result = compute_equal_split([pattern_a, pattern_b, pattern_c])
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-9

    def test_duplicate_patterns_accumulate_weight(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """Pattern appearing twice gets double weight.

        [A, B, A] -> A appears 2x, B appears 1x
        Each occurrence gets 1/3, so A=2/3, B=1/3
        """
        result = compute_equal_split([pattern_a, pattern_b, pattern_a])
        # A: 1/3 + 1/3 = 2/3
        assert abs(result[str(pattern_a)] - 2.0 / 3) < 1e-9
        # B: 1/3
        assert abs(result[str(pattern_b)] - 1.0 / 3) < 1e-9

    def test_many_duplicates_still_sum_to_one(self, pattern_a: UUID) -> None:
        """Many duplicates of same pattern still sum to 1.0."""
        result = compute_equal_split([pattern_a] * 10)
        # Single pattern, all occurrences accumulate to ~1.0
        assert len(result) == 1
        assert abs(result[str(pattern_a)] - 1.0) < 1e-9


# =============================================================================
# Test Class: compute_recency_weighted
# =============================================================================


@pytest.mark.unit
class TestComputeRecencyWeighted:
    """Tests for recency-weighted heuristic."""

    def test_empty_input_returns_empty_dict(self) -> None:
        """Empty pattern list returns empty weights."""
        result = compute_recency_weighted([])
        assert result == {}

    def test_single_pattern_gets_full_weight(self, pattern_a: UUID) -> None:
        """Single pattern gets weight of 1.0."""
        result = compute_recency_weighted([pattern_a])
        assert result == {str(pattern_a): 1.0}

    def test_two_patterns_later_gets_more(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """Second pattern gets more weight than first.

        Positions: A=1, B=2. Sum=3.
        A=1/3, B=2/3.
        """
        result = compute_recency_weighted([pattern_a, pattern_b])
        assert abs(result[str(pattern_a)] - 1.0 / 3) < 1e-9
        assert abs(result[str(pattern_b)] - 2.0 / 3) < 1e-9

    def test_three_patterns_linear_ramp(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """Three patterns: weights increase linearly.

        Positions: A=1, B=2, C=3. Sum=6.
        A=1/6, B=2/6, C=3/6.
        """
        result = compute_recency_weighted([pattern_a, pattern_b, pattern_c])
        assert abs(result[str(pattern_a)] - 1.0 / 6) < 1e-9
        assert abs(result[str(pattern_b)] - 2.0 / 6) < 1e-9
        assert abs(result[str(pattern_c)] - 3.0 / 6) < 1e-9

    def test_weights_sum_to_one(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """All weights sum to 1.0."""
        result = compute_recency_weighted([pattern_a, pattern_b, pattern_c])
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-9

    def test_later_duplicate_gets_more_weight(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """Pattern appearing later gets more weight.

        [A, B, A] -> positions 1, 2, 3. Sum=6.
        A: positions 1 and 3 = 1/6 + 3/6 = 4/6 = 2/3
        B: position 2 = 2/6 = 1/3
        """
        result = compute_recency_weighted([pattern_a, pattern_b, pattern_a])
        assert abs(result[str(pattern_a)] - 4.0 / 6) < 1e-9
        assert abs(result[str(pattern_b)] - 2.0 / 6) < 1e-9

    def test_five_patterns_distribution(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """Five patterns with duplicates.

        [A, B, C, A, B] -> positions 1, 2, 3, 4, 5. Sum=15.
        A: 1+4 = 5/15 = 1/3
        B: 2+5 = 7/15
        C: 3 = 3/15 = 1/5
        """
        result = compute_recency_weighted(
            [pattern_a, pattern_b, pattern_c, pattern_a, pattern_b]
        )
        assert abs(result[str(pattern_a)] - 5.0 / 15) < 1e-9
        assert abs(result[str(pattern_b)] - 7.0 / 15) < 1e-9
        assert abs(result[str(pattern_c)] - 3.0 / 15) < 1e-9
        assert abs(sum(result.values()) - 1.0) < 1e-9


# =============================================================================
# Test Class: compute_first_match
# =============================================================================


@pytest.mark.unit
class TestComputeFirstMatch:
    """Tests for first-match heuristic."""

    def test_empty_input_returns_empty_dict(self) -> None:
        """Empty pattern list returns empty weights."""
        result = compute_first_match([])
        assert result == {}

    def test_single_pattern_gets_full_weight(self, pattern_a: UUID) -> None:
        """Single pattern gets weight of 1.0."""
        result = compute_first_match([pattern_a])
        assert result == {str(pattern_a): 1.0}

    def test_first_pattern_gets_all_credit(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """Only first pattern gets any credit."""
        result = compute_first_match([pattern_a, pattern_b, pattern_c])
        assert result == {str(pattern_a): 1.0}
        assert str(pattern_b) not in result
        assert str(pattern_c) not in result

    def test_duplicates_first_still_wins(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """Even with duplicates, first pattern gets all credit."""
        result = compute_first_match([pattern_a, pattern_b, pattern_a])
        assert result == {str(pattern_a): 1.0}


# =============================================================================
# Test Class: apply_heuristic dispatcher
# =============================================================================


@pytest.mark.unit
class TestApplyHeuristic:
    """Tests for the heuristic dispatcher function."""

    def test_empty_input_returns_empty_and_zero_confidence(self) -> None:
        """Empty pattern list returns ({}, 0.0)."""
        weights, confidence = apply_heuristic(
            method=EnumHeuristicMethod.EQUAL_SPLIT,
            ordered_pattern_ids=[],
        )
        assert weights == {}
        assert confidence == 0.0

    def test_equal_split_dispatches_correctly(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """EQUAL_SPLIT dispatches to compute_equal_split."""
        weights, confidence = apply_heuristic(
            method=EnumHeuristicMethod.EQUAL_SPLIT,
            ordered_pattern_ids=[pattern_a, pattern_b],
        )
        assert weights[str(pattern_a)] == 0.5
        assert weights[str(pattern_b)] == 0.5
        assert confidence == HEURISTIC_CONFIDENCE[EnumHeuristicMethod.EQUAL_SPLIT.value]
        assert confidence == 0.5

    def test_recency_weighted_dispatches_correctly(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """RECENCY_WEIGHTED dispatches to compute_recency_weighted."""
        weights, confidence = apply_heuristic(
            method=EnumHeuristicMethod.RECENCY_WEIGHTED,
            ordered_pattern_ids=[pattern_a, pattern_b],
        )
        assert abs(weights[str(pattern_a)] - 1.0 / 3) < 1e-9
        assert abs(weights[str(pattern_b)] - 2.0 / 3) < 1e-9
        assert (
            confidence
            == HEURISTIC_CONFIDENCE[EnumHeuristicMethod.RECENCY_WEIGHTED.value]
        )
        assert confidence == 0.4

    def test_first_match_dispatches_correctly(
        self, pattern_a: UUID, pattern_b: UUID
    ) -> None:
        """FIRST_MATCH dispatches to compute_first_match."""
        weights, confidence = apply_heuristic(
            method=EnumHeuristicMethod.FIRST_MATCH,
            ordered_pattern_ids=[pattern_a, pattern_b],
        )
        assert weights == {str(pattern_a): 1.0}
        assert confidence == HEURISTIC_CONFIDENCE[EnumHeuristicMethod.FIRST_MATCH.value]
        assert confidence == 0.3

    def test_all_methods_return_weights_summing_to_one(
        self, pattern_a: UUID, pattern_b: UUID, pattern_c: UUID
    ) -> None:
        """All heuristic methods return weights that sum to 1.0."""
        patterns = [pattern_a, pattern_b, pattern_c]

        for method in EnumHeuristicMethod:
            weights, _ = apply_heuristic(
                method=method,
                ordered_pattern_ids=patterns,
            )
            total = sum(weights.values())
            assert abs(total - 1.0) < 1e-9, f"{method.value} weights don't sum to 1.0"


# =============================================================================
# Test Class: Confidence Values
# =============================================================================


@pytest.mark.unit
class TestConfidenceValues:
    """Tests verifying confidence values match specification."""

    def test_equal_split_confidence_is_0_5(self) -> None:
        """EQUAL_SPLIT has confidence 0.5."""
        assert HEURISTIC_CONFIDENCE[EnumHeuristicMethod.EQUAL_SPLIT.value] == 0.5

    def test_recency_weighted_confidence_is_0_4(self) -> None:
        """RECENCY_WEIGHTED has confidence 0.4."""
        assert HEURISTIC_CONFIDENCE[EnumHeuristicMethod.RECENCY_WEIGHTED.value] == 0.4

    def test_first_match_confidence_is_0_3(self) -> None:
        """FIRST_MATCH has confidence 0.3."""
        assert HEURISTIC_CONFIDENCE[EnumHeuristicMethod.FIRST_MATCH.value] == 0.3

    def test_confidence_order_matches_spec(self) -> None:
        """Confidence: EQUAL_SPLIT > RECENCY_WEIGHTED > FIRST_MATCH."""
        equal = HEURISTIC_CONFIDENCE[EnumHeuristicMethod.EQUAL_SPLIT.value]
        recency = HEURISTIC_CONFIDENCE[EnumHeuristicMethod.RECENCY_WEIGHTED.value]
        first = HEURISTIC_CONFIDENCE[EnumHeuristicMethod.FIRST_MATCH.value]

        assert equal > recency > first


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_large_number_of_patterns(self) -> None:
        """Handles large number of patterns without precision loss."""
        patterns = [UUID(int=i) for i in range(100)]

        weights, _confidence = apply_heuristic(
            method=EnumHeuristicMethod.EQUAL_SPLIT,
            ordered_pattern_ids=patterns,
        )

        # All weights should sum to 1.0
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9

        # Each pattern should have weight 0.01
        for pid in patterns:
            assert abs(weights[str(pid)] - 0.01) < 1e-9

    def test_same_pattern_many_times_equal_split(self, pattern_a: UUID) -> None:
        """Same pattern repeated N times in equal_split."""
        patterns = [pattern_a] * 5

        weights, _ = apply_heuristic(
            method=EnumHeuristicMethod.EQUAL_SPLIT,
            ordered_pattern_ids=patterns,
        )

        # Single unique pattern, gets all weight
        assert len(weights) == 1
        assert weights[str(pattern_a)] == 1.0

    def test_same_pattern_many_times_recency_weighted(self, pattern_a: UUID) -> None:
        """Same pattern repeated N times in recency_weighted."""
        patterns = [pattern_a] * 5

        weights, _ = apply_heuristic(
            method=EnumHeuristicMethod.RECENCY_WEIGHTED,
            ordered_pattern_ids=patterns,
        )

        # Single unique pattern, accumulates all position weights
        # Positions: 1, 2, 3, 4, 5. Sum = 15. Total = 15/15 = 1.0
        assert len(weights) == 1
        assert abs(weights[str(pattern_a)] - 1.0) < 1e-9

    def test_uuid_string_format_is_lowercase(self, pattern_a: UUID) -> None:
        """UUID keys in weights dict are lowercase strings."""
        weights, _ = apply_heuristic(
            method=EnumHeuristicMethod.EQUAL_SPLIT,
            ordered_pattern_ids=[pattern_a],
        )

        key = next(iter(weights.keys()))
        assert key == str(pattern_a)
        assert key == key.lower()
        assert "-" in key  # Standard UUID format with hyphens
