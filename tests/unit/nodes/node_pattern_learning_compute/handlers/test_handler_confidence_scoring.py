# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for confidence scoring handler.

This module tests the confidence scoring functionality:
    - compute_cluster_scores: Decomposed confidence computation
    - Component reading (label_agreement, cluster_cohesion from cluster)
    - frequency_factor calculation
    - Empty cluster handling
    - Confidence formula validation

Key test areas:
    - Reads pre-computed values (does NOT recompute)
    - frequency_factor caps at 1.0
    - Empty cluster raises PatternLearningValidationError
    - Confidence formula is correct (0.40 + 0.30 + 0.30)
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_confidence_scoring import (
    compute_cluster_scores,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_MIN_FREQUENCY,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    ExtractedFeaturesDict,
    PatternClusterDict,
    StructuralFeaturesDict,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def make_structural_features() -> StructuralFeaturesDict:
    """Create minimal structural features for testing."""
    return StructuralFeaturesDict(
        class_count=1,
        function_count=2,
        max_nesting_depth=1,
        line_count=50,
        cyclomatic_complexity=5,
        has_type_hints=True,
        has_docstrings=True,
    )


def make_features(item_id: str) -> ExtractedFeaturesDict:
    """Create minimal features for centroid."""
    return ExtractedFeaturesDict(
        item_id=item_id,
        keywords=("def", "class"),
        pattern_indicators=("NodeCompute",),
        structural=make_structural_features(),
        base_classes=(),
        decorators=(),
        labels=("compute",),
        language="python",
        extraction_quality="full",
    )


def make_cluster(
    cluster_id: str = "cluster-0001",
    pattern_type: str = "NodeCompute",
    member_ids: tuple[str, ...] = ("item-a", "item-b", "item-c"),
    member_count: int = 3,
    internal_similarity: float = 0.85,
    member_pattern_indicators: tuple[tuple[str, ...], ...] | None = None,
    label_agreement: float = 0.9,
) -> PatternClusterDict:
    """Factory function to create PatternClusterDict for testing."""
    if member_pattern_indicators is None:
        member_pattern_indicators = tuple(("NodeCompute",) for _ in member_ids)

    return PatternClusterDict(
        cluster_id=cluster_id,
        pattern_type=pattern_type,
        member_ids=member_ids,
        centroid_features=make_features("centroid"),
        member_count=member_count,
        internal_similarity=internal_similarity,
        member_pattern_indicators=member_pattern_indicators,
        label_agreement=label_agreement,
    )


# =============================================================================
# compute_cluster_scores Tests - Basic Behavior
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresBasic:
    """Tests for basic compute_cluster_scores behavior."""

    def test_returns_all_components(self) -> None:
        """Result should contain all required component fields."""
        cluster = make_cluster()
        result = compute_cluster_scores(cluster)

        assert "label_agreement" in result
        assert "cluster_cohesion" in result
        assert "frequency_factor" in result
        assert "confidence" in result

    def test_reads_label_agreement_from_cluster(self) -> None:
        """label_agreement should be read directly from cluster."""
        cluster = make_cluster(label_agreement=0.75)
        result = compute_cluster_scores(cluster)

        assert result["label_agreement"] == 0.75

    def test_reads_cluster_cohesion_from_internal_similarity(self) -> None:
        """cluster_cohesion should equal cluster's internal_similarity."""
        cluster = make_cluster(internal_similarity=0.92)
        result = compute_cluster_scores(cluster)

        assert result["cluster_cohesion"] == 0.92


# =============================================================================
# compute_cluster_scores Tests - Frequency Factor
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresFrequencyFactor:
    """Tests for frequency_factor calculation."""

    def test_frequency_factor_below_min(self) -> None:
        """frequency_factor should be < 1.0 when member_count < min_frequency."""
        cluster = make_cluster(member_count=3)
        result = compute_cluster_scores(cluster, min_frequency=5)

        expected = 3 / 5  # 0.6
        assert result["frequency_factor"] == pytest.approx(expected)

    def test_frequency_factor_at_min(self) -> None:
        """frequency_factor should be 1.0 when member_count == min_frequency."""
        cluster = make_cluster(member_count=5)
        result = compute_cluster_scores(cluster, min_frequency=5)

        assert result["frequency_factor"] == 1.0

    def test_frequency_factor_above_min_caps_at_one(self) -> None:
        """frequency_factor should cap at 1.0 when member_count > min_frequency."""
        cluster = make_cluster(member_count=10)
        result = compute_cluster_scores(cluster, min_frequency=5)

        assert result["frequency_factor"] == 1.0

    def test_frequency_factor_uses_default_min_frequency(self) -> None:
        """Default min_frequency should be DEFAULT_MIN_FREQUENCY (5)."""
        cluster = make_cluster(member_count=3)
        result = compute_cluster_scores(cluster)

        expected = 3 / DEFAULT_MIN_FREQUENCY
        assert result["frequency_factor"] == pytest.approx(expected)

    def test_frequency_factor_single_member(self) -> None:
        """Single member cluster should have low frequency_factor."""
        cluster = make_cluster(
            member_ids=("item-a",),
            member_count=1,
            member_pattern_indicators=(("NodeCompute",),),
        )
        result = compute_cluster_scores(cluster, min_frequency=5)

        expected = 1 / 5  # 0.2
        assert result["frequency_factor"] == pytest.approx(expected)

    def test_min_frequency_zero_raises_error(self) -> None:
        """min_frequency=0 should raise PatternLearningValidationError."""
        cluster = make_cluster()

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster, min_frequency=0)

        assert "min_frequency" in str(exc_info.value)

    def test_min_frequency_negative_raises_error(self) -> None:
        """Negative min_frequency should raise PatternLearningValidationError."""
        cluster = make_cluster()

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster, min_frequency=-5)

        assert "min_frequency" in str(exc_info.value)


# =============================================================================
# compute_cluster_scores Tests - Confidence Calculation
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresConfidence:
    """Tests for confidence calculation formula."""

    def test_confidence_formula_correct(self) -> None:
        """Confidence should follow 0.40 + 0.30 + 0.30 formula."""
        cluster = make_cluster(
            member_count=5,
            internal_similarity=0.8,
            label_agreement=0.9,
        )
        result = compute_cluster_scores(cluster, min_frequency=5)

        # frequency_factor = 5/5 = 1.0
        # confidence = 0.40 * 0.9 + 0.30 * 0.8 + 0.30 * 1.0
        #            = 0.36 + 0.24 + 0.30 = 0.90
        expected_confidence = 0.40 * 0.9 + 0.30 * 0.8 + 0.30 * 1.0
        assert result["confidence"] == pytest.approx(expected_confidence)

    def test_confidence_all_zeros(self) -> None:
        """Confidence should be 0.0 when all components are 0."""
        cluster = make_cluster(
            member_ids=("item-a",),
            member_count=1,
            internal_similarity=0.0,
            label_agreement=0.0,
            member_pattern_indicators=(("NodeCompute",),),
        )
        # min_frequency very high to make frequency_factor near 0
        result = compute_cluster_scores(cluster, min_frequency=1000)

        # frequency_factor = 1/1000 = 0.001
        # confidence = 0.40 * 0 + 0.30 * 0 + 0.30 * 0.001 ≈ 0.0003
        assert result["confidence"] == pytest.approx(0.0003, abs=0.001)

    def test_confidence_all_ones(self) -> None:
        """Confidence should be 1.0 when all components are 1.0."""
        cluster = make_cluster(
            member_count=10,
            internal_similarity=1.0,
            label_agreement=1.0,
        )
        result = compute_cluster_scores(cluster, min_frequency=5)

        # frequency_factor = min(1.0, 10/5) = 1.0
        # confidence = 0.40 * 1.0 + 0.30 * 1.0 + 0.30 * 1.0 = 1.0
        assert result["confidence"] == pytest.approx(1.0)

    def test_confidence_weights_sum_to_one(self) -> None:
        """Verify that confidence weights (0.40 + 0.30 + 0.30) sum to 1.0."""
        # This is a documentation/sanity check
        assert pytest.approx(1.0) == 0.40 + 0.30 + 0.30


# =============================================================================
# compute_cluster_scores Tests - Empty Cluster Handling
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresEmptyCluster:
    """Tests for empty cluster handling."""

    def test_empty_cluster_raises_error(self) -> None:
        """Empty cluster (member_count=0) should raise PatternLearningValidationError."""
        cluster = make_cluster(
            member_ids=(),
            member_count=0,
            member_pattern_indicators=(),
        )

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        assert "empty cluster" in str(exc_info.value).lower()
        assert "cluster-0001" in str(exc_info.value)

    def test_empty_cluster_error_message_includes_cluster_id(self) -> None:
        """Error message should include cluster_id for debugging."""
        cluster = make_cluster(
            cluster_id="cluster-0042",
            member_ids=(),
            member_count=0,
            member_pattern_indicators=(),
        )

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        assert "cluster-0042" in str(exc_info.value)


# =============================================================================
# compute_cluster_scores Tests - Does NOT Recompute
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresNoRecompute:
    """Tests verifying that compute_cluster_scores reads, not recomputes."""

    def test_does_not_recompute_label_agreement(self) -> None:
        """label_agreement should be read directly, not recomputed from members."""
        # Create cluster where member_pattern_indicators would give different agreement
        # if recomputed, but pre-computed label_agreement is different
        cluster = make_cluster(
            pattern_type="NodeCompute",
            member_ids=("a", "b", "c"),
            member_pattern_indicators=(
                ("NodeCompute",),  # matches
                ("NodeCompute",),  # matches
                ("NodeEffect",),  # doesn't match
            ),
            # If recomputed: 2/3 = 0.667
            # But we set it to 0.5 to verify it reads, not recomputes
            label_agreement=0.5,
        )

        result = compute_cluster_scores(cluster)

        # Should read the 0.5, not recompute 0.667
        assert result["label_agreement"] == 0.5

    def test_does_not_recompute_internal_similarity(self) -> None:
        """cluster_cohesion should equal internal_similarity, not recomputed."""
        cluster = make_cluster(internal_similarity=0.123)
        result = compute_cluster_scores(cluster)

        assert result["cluster_cohesion"] == 0.123


# =============================================================================
# compute_cluster_scores Tests - Component Ranges
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresRanges:
    """Tests verifying component values are in valid ranges."""

    def test_all_components_in_zero_one_range(self) -> None:
        """All component scores should be in [0.0, 1.0]."""
        cluster = make_cluster(
            member_count=3,
            internal_similarity=0.7,
            label_agreement=0.8,
        )
        result = compute_cluster_scores(cluster)

        assert 0.0 <= result["label_agreement"] <= 1.0
        assert 0.0 <= result["cluster_cohesion"] <= 1.0
        assert 0.0 <= result["frequency_factor"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0

    def test_frequency_factor_never_exceeds_one(self) -> None:
        """frequency_factor should never exceed 1.0 even with huge clusters."""
        cluster = make_cluster(member_count=1000)
        result = compute_cluster_scores(cluster, min_frequency=5)

        assert result["frequency_factor"] == 1.0


# =============================================================================
# compute_cluster_scores Tests - Pre-computed Value Validation
# =============================================================================


@pytest.mark.unit
class TestComputeClusterScoresPrecomputedValidation:
    """Tests for validation of pre-computed values (label_agreement, internal_similarity)."""

    def test_label_agreement_above_one_raises_error(self) -> None:
        """label_agreement > 1.0 should raise PatternLearningValidationError."""
        cluster = make_cluster(label_agreement=1.5)

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        error_message = str(exc_info.value)
        assert "label_agreement" in error_message
        assert "1.5" in error_message
        assert "[0.0, 1.0]" in error_message

    def test_label_agreement_below_zero_raises_error(self) -> None:
        """label_agreement < 0.0 should raise PatternLearningValidationError."""
        cluster = make_cluster(label_agreement=-0.1)

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        error_message = str(exc_info.value)
        assert "label_agreement" in error_message
        assert "-0.1" in error_message
        assert "[0.0, 1.0]" in error_message

    def test_internal_similarity_above_one_raises_error(self) -> None:
        """internal_similarity > 1.0 should raise PatternLearningValidationError."""
        cluster = make_cluster(internal_similarity=1.2)

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        error_message = str(exc_info.value)
        assert "internal_similarity" in error_message
        assert "1.2" in error_message
        assert "[0.0, 1.0]" in error_message

    def test_internal_similarity_below_zero_raises_error(self) -> None:
        """internal_similarity < 0.0 should raise PatternLearningValidationError."""
        cluster = make_cluster(internal_similarity=-0.2)

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        error_message = str(exc_info.value)
        assert "internal_similarity" in error_message
        assert "-0.2" in error_message
        assert "[0.0, 1.0]" in error_message

    def test_precomputed_validation_includes_cluster_id(self) -> None:
        """Error message should include cluster_id for debugging."""
        cluster = make_cluster(
            cluster_id="cluster-debug-123",
            label_agreement=2.0,
        )

        with pytest.raises(PatternLearningValidationError) as exc_info:
            compute_cluster_scores(cluster)

        assert "cluster-debug-123" in str(exc_info.value)

    def test_label_agreement_at_boundary_zero_is_valid(self) -> None:
        """label_agreement = 0.0 (boundary) should be accepted."""
        cluster = make_cluster(label_agreement=0.0)
        result = compute_cluster_scores(cluster)

        assert result["label_agreement"] == 0.0

    def test_label_agreement_at_boundary_one_is_valid(self) -> None:
        """label_agreement = 1.0 (boundary) should be accepted."""
        cluster = make_cluster(label_agreement=1.0)
        result = compute_cluster_scores(cluster)

        assert result["label_agreement"] == 1.0

    def test_internal_similarity_at_boundary_zero_is_valid(self) -> None:
        """internal_similarity = 0.0 (boundary) should be accepted."""
        cluster = make_cluster(internal_similarity=0.0)
        result = compute_cluster_scores(cluster)

        assert result["cluster_cohesion"] == 0.0

    def test_internal_similarity_at_boundary_one_is_valid(self) -> None:
        """internal_similarity = 1.0 (boundary) should be accepted."""
        cluster = make_cluster(internal_similarity=1.0)
        result = compute_cluster_scores(cluster)

        assert result["cluster_cohesion"] == 1.0
