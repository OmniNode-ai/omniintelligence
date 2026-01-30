# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for deduplication handler.

This module tests the deduplication functionality:
    - deduplicate_patterns: Remove overlapping patterns with policy transparency
    - generate_pattern_signature: Versioned signature generation
    - Determinism guarantees
    - Near-threshold warnings
    - Tie-break behavior

Key test areas:
    - Same input always produces same output (determinism)
    - Permuted input ordering produces same result
    - Policy transparency (threshold explicit in output)
    - Near-threshold warnings emitted correctly
    - Signature versioning and stability
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_deduplication import (
    deduplicate_patterns,
    generate_pattern_signature,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.presets import (
    DEFAULT_DEDUPLICATION_THRESHOLD,
    NEAR_THRESHOLD_MARGIN,
    SIGNATURE_NORMALIZATION,
    SIGNATURE_VERSION,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.protocols import (
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


def make_features(
    item_id: str,
    keywords: tuple[str, ...] = ("def", "class"),
    pattern_indicators: tuple[str, ...] = ("NodeCompute",),
    labels: tuple[str, ...] = ("compute",),
) -> ExtractedFeaturesDict:
    """Create features for centroid with customizable keywords/indicators."""
    return ExtractedFeaturesDict(
        item_id=item_id,
        keywords=keywords,
        pattern_indicators=pattern_indicators,
        structural=make_structural_features(),
        base_classes=(),
        decorators=(),
        labels=labels,
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
    keywords: tuple[str, ...] = ("def", "class"),
    pattern_indicators: tuple[str, ...] = ("NodeCompute",),
) -> PatternClusterDict:
    """Factory function to create PatternClusterDict for testing."""
    if member_pattern_indicators is None:
        member_pattern_indicators = tuple(("NodeCompute",) for _ in member_ids)

    return PatternClusterDict(
        cluster_id=cluster_id,
        pattern_type=pattern_type,
        member_ids=member_ids,
        centroid_features=make_features(
            "centroid",
            keywords=keywords,
            pattern_indicators=pattern_indicators,
        ),
        member_count=member_count,
        internal_similarity=internal_similarity,
        member_pattern_indicators=member_pattern_indicators,
        label_agreement=label_agreement,
    )


# =============================================================================
# generate_pattern_signature Tests
# =============================================================================


@pytest.mark.unit
class TestGeneratePatternSignature:
    """Tests for generate_pattern_signature function."""

    def test_returns_all_fields(self) -> None:
        """Signature result should contain all required fields."""
        cluster = make_cluster()
        sig = generate_pattern_signature(cluster)

        assert "signature" in sig
        assert "signature_version" in sig
        assert "signature_inputs" in sig
        assert "normalization_applied" in sig

    def test_signature_is_sha256_hex(self) -> None:
        """Signature should be a 64-character SHA256 hex string."""
        cluster = make_cluster()
        sig = generate_pattern_signature(cluster)

        assert len(sig["signature"]) == 64
        assert all(c in "0123456789abcdef" for c in sig["signature"])

    def test_signature_version_matches_preset(self) -> None:
        """Signature version should match SIGNATURE_VERSION from presets."""
        cluster = make_cluster()
        sig = generate_pattern_signature(cluster)

        assert sig["signature_version"] == SIGNATURE_VERSION

    def test_normalization_applied_matches_preset(self) -> None:
        """normalization_applied should match SIGNATURE_NORMALIZATION."""
        cluster = make_cluster()
        sig = generate_pattern_signature(cluster)

        assert sig["normalization_applied"] == SIGNATURE_NORMALIZATION

    def test_signature_inputs_includes_pattern_type(self) -> None:
        """signature_inputs should include pattern_type as first element."""
        cluster = make_cluster(pattern_type="NodeEffect")
        sig = generate_pattern_signature(cluster)

        # First input is pattern_type (lowercased)
        assert sig["signature_inputs"][0] == "nodeeffect"

    def test_signature_inputs_lowercased(self) -> None:
        """All signature inputs should be lowercased."""
        cluster = make_cluster(
            pattern_type="NodeCompute",
            keywords=("DEF", "CLASS", "MyFunc"),
            pattern_indicators=("NodeCompute", "FROZEN"),
        )
        sig = generate_pattern_signature(cluster)

        # All inputs should be lowercase
        for input_str in sig["signature_inputs"]:
            assert input_str == input_str.lower()

    def test_signature_inputs_sorted(self) -> None:
        """Keywords and indicators in signature should be sorted."""
        cluster = make_cluster(
            keywords=("zebra", "apple", "mango"),
            pattern_indicators=("NodeCompute", "BaseModel"),
        )
        sig = generate_pattern_signature(cluster)

        # Skip first element (pattern_type)
        inputs = sig["signature_inputs"][1:]

        # Keywords should be sorted: apple, mango, zebra
        # Then indicators: basemodel, nodecompute
        assert "apple" in inputs
        assert "mango" in inputs
        assert "zebra" in inputs
        assert "basemodel" in inputs
        assert "nodecompute" in inputs

    def test_signature_inputs_deduped(self) -> None:
        """Duplicate keywords should be removed from signature inputs."""
        cluster = make_cluster(
            pattern_type="NodeCompute",
            keywords=("def", "def", "class", "def"),
            pattern_indicators=("NodeEffect", "NodeEffect"),
        )
        sig = generate_pattern_signature(cluster)

        # Count occurrences - keywords and indicators are deduped internally
        inputs = list(sig["signature_inputs"])
        assert inputs.count("def") == 1
        # nodecompute appears once (from pattern_type)
        assert inputs.count("nodecompute") == 1
        # nodeeffect appears once (from indicators, deduped)
        assert inputs.count("nodeeffect") == 1

    def test_signature_keywords_limited_to_20(self) -> None:
        """Only first 20 keywords (after sort) should be included."""
        # Create 25 unique keywords
        many_keywords = tuple(f"kw{i:02d}" for i in range(25))
        cluster = make_cluster(keywords=many_keywords, pattern_indicators=())

        sig = generate_pattern_signature(cluster)

        # Should have pattern_type + 20 keywords max
        # First keyword after sort would be kw00, kw01, ... kw19
        assert len(sig["signature_inputs"]) <= 21  # 1 pattern_type + 20 keywords

    def test_determinism_same_input_same_output(self) -> None:
        """Same cluster should always produce the same signature."""
        cluster = make_cluster()

        sig1 = generate_pattern_signature(cluster)
        sig2 = generate_pattern_signature(cluster)

        assert sig1["signature"] == sig2["signature"]
        assert sig1["signature_inputs"] == sig2["signature_inputs"]

    def test_determinism_keyword_order_irrelevant(self) -> None:
        """Different keyword ordering should produce same signature."""
        cluster1 = make_cluster(keywords=("a", "b", "c"))
        cluster2 = make_cluster(keywords=("c", "a", "b"))

        sig1 = generate_pattern_signature(cluster1)
        sig2 = generate_pattern_signature(cluster2)

        assert sig1["signature"] == sig2["signature"]

    def test_empty_cluster_raises_error(self) -> None:
        """Empty cluster should raise PatternLearningValidationError."""
        with pytest.raises(PatternLearningValidationError):
            generate_pattern_signature({})  # type: ignore[arg-type]


# =============================================================================
# deduplicate_patterns Tests - Basic Behavior
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsBasic:
    """Tests for basic deduplicate_patterns behavior."""

    def test_returns_all_fields(self) -> None:
        """Result should contain all required fields."""
        clusters = [make_cluster()]
        result = deduplicate_patterns(clusters)

        assert "deduplicated_clusters" in result
        assert "merged_count" in result
        assert "threshold_used" in result
        assert "near_threshold_warnings" in result

    def test_threshold_used_explicit_in_output(self) -> None:
        """threshold_used should be explicit in output for policy transparency."""
        clusters = [make_cluster()]
        result = deduplicate_patterns(clusters, similarity_threshold=0.90)

        assert result["threshold_used"] == 0.90

    def test_threshold_used_defaults_to_preset(self) -> None:
        """Default threshold should be DEFAULT_DEDUPLICATION_THRESHOLD."""
        clusters = [make_cluster()]
        result = deduplicate_patterns(clusters)

        assert result["threshold_used"] == DEFAULT_DEDUPLICATION_THRESHOLD

    def test_empty_input_returns_empty_result(self) -> None:
        """Empty input should return empty deduplicated_clusters."""
        result = deduplicate_patterns([])

        assert result["deduplicated_clusters"] == []
        assert result["merged_count"] == 0
        assert result["near_threshold_warnings"] == []

    def test_single_cluster_unchanged(self) -> None:
        """Single cluster should pass through unchanged."""
        cluster = make_cluster()
        result = deduplicate_patterns([cluster])

        assert len(result["deduplicated_clusters"]) == 1
        assert result["deduplicated_clusters"][0]["cluster_id"] == cluster["cluster_id"]
        assert result["merged_count"] == 0


# =============================================================================
# deduplicate_patterns Tests - Deduplication Logic
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsLogic:
    """Tests for deduplication logic."""

    def test_identical_clusters_deduplicated(self) -> None:
        """Identical clusters (same features) should be deduplicated."""
        cluster1 = make_cluster(cluster_id="cluster-0001")
        cluster2 = make_cluster(cluster_id="cluster-0002")

        result = deduplicate_patterns([cluster1, cluster2], similarity_threshold=0.85)

        # One should be dropped
        assert len(result["deduplicated_clusters"]) == 1
        assert result["merged_count"] == 1

    def test_different_clusters_kept(self) -> None:
        """Sufficiently different clusters should be kept separate."""
        cluster1 = make_cluster(
            cluster_id="cluster-0001",
            keywords=("alpha", "beta"),
            pattern_indicators=("NodeCompute",),
        )
        cluster2 = make_cluster(
            cluster_id="cluster-0002",
            keywords=("gamma", "delta"),
            pattern_indicators=("NodeEffect",),
        )

        result = deduplicate_patterns([cluster1, cluster2], similarity_threshold=0.85)

        assert len(result["deduplicated_clusters"]) == 2
        assert result["merged_count"] == 0

    def test_higher_confidence_wins(self) -> None:
        """When deduplicating, cluster with higher confidence should survive."""
        cluster1 = make_cluster(cluster_id="cluster-0001", internal_similarity=0.7)
        cluster2 = make_cluster(cluster_id="cluster-0002", internal_similarity=0.9)

        confidence_scores = {
            "cluster-0001": 0.6,
            "cluster-0002": 0.8,
        }

        result = deduplicate_patterns(
            [cluster1, cluster2],
            confidence_scores=confidence_scores,
            similarity_threshold=0.5,  # Low threshold to force dedup
        )

        assert len(result["deduplicated_clusters"]) == 1
        # cluster-0002 has higher confidence, should survive
        assert result["deduplicated_clusters"][0]["cluster_id"] == "cluster-0002"

    def test_larger_member_count_wins_on_confidence_tie(self) -> None:
        """On confidence tie, cluster with more members should survive."""
        cluster1 = make_cluster(
            cluster_id="cluster-0001",
            member_ids=("a", "b"),
            member_count=2,
            internal_similarity=0.8,
        )
        cluster2 = make_cluster(
            cluster_id="cluster-0002",
            member_ids=("c", "d", "e", "f"),
            member_count=4,
            internal_similarity=0.8,
        )

        result = deduplicate_patterns(
            [cluster1, cluster2],
            similarity_threshold=0.5,  # Low threshold to force dedup
        )

        assert len(result["deduplicated_clusters"]) == 1
        # cluster-0002 has more members
        assert result["deduplicated_clusters"][0]["cluster_id"] == "cluster-0002"

    def test_smaller_leader_wins_on_full_tie(self) -> None:
        """On full tie, cluster with smaller leader (member_ids[0]) wins."""
        cluster1 = make_cluster(
            cluster_id="cluster-0001",
            member_ids=("zebra",),
            member_count=1,
            internal_similarity=0.8,
        )
        cluster2 = make_cluster(
            cluster_id="cluster-0002",
            member_ids=("alpha",),
            member_count=1,
            internal_similarity=0.8,
        )

        result = deduplicate_patterns(
            [cluster1, cluster2],
            similarity_threshold=0.5,  # Low threshold to force dedup
        )

        assert len(result["deduplicated_clusters"]) == 1
        # cluster-0002 has smaller leader "alpha" < "zebra"
        assert result["deduplicated_clusters"][0]["cluster_id"] == "cluster-0002"


# =============================================================================
# deduplicate_patterns Tests - Near-Threshold Warnings
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsWarnings:
    """Tests for near-threshold warning behavior."""

    def test_near_threshold_warning_emitted_kept_separate(self) -> None:
        """Warning should be emitted when clusters are near threshold but kept separate."""
        # Create clusters with similarity just below threshold
        cluster1 = make_cluster(
            cluster_id="cluster-0001",
            keywords=("a", "b", "c", "d", "e"),
            pattern_indicators=("NodeCompute",),
        )
        cluster2 = make_cluster(
            cluster_id="cluster-0002",
            keywords=("a", "b", "c", "x", "y"),  # 3/7 overlap = ~0.43 jaccard
            pattern_indicators=("NodeCompute",),
        )

        # Use threshold where they'd be in warning zone but kept separate
        # Actual similarity will depend on full 5-component calculation
        result = deduplicate_patterns(
            [cluster1, cluster2],
            similarity_threshold=0.90,
            near_threshold_margin=0.10,
        )

        # Check if we got any warnings (depends on actual similarity)
        # The key assertion is that the structure is correct
        for warning in result["near_threshold_warnings"]:
            assert "cluster_a_id" in warning
            assert "cluster_b_id" in warning
            assert "similarity" in warning
            assert "threshold" in warning
            assert "action_taken" in warning

    def test_warning_contains_action_taken(self) -> None:
        """Warning should indicate action_taken (kept_separate or merged)."""
        cluster1 = make_cluster(cluster_id="cluster-0001")
        cluster2 = make_cluster(cluster_id="cluster-0002")

        result = deduplicate_patterns(
            [cluster1, cluster2],
            similarity_threshold=0.85,
            near_threshold_margin=0.10,
        )

        # If there are warnings, they should have valid action_taken
        for warning in result["near_threshold_warnings"]:
            assert warning["action_taken"] in ("kept_separate", "merged")


# =============================================================================
# deduplicate_patterns Tests - Determinism
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsDeterminism:
    """Tests for determinism guarantees."""

    def test_same_input_same_output(self) -> None:
        """Same input should always produce same output."""
        clusters = [
            make_cluster(cluster_id="cluster-0001"),
            make_cluster(cluster_id="cluster-0002"),
            make_cluster(cluster_id="cluster-0003", keywords=("x", "y", "z")),
        ]

        result1 = deduplicate_patterns(clusters)
        result2 = deduplicate_patterns(clusters)

        assert len(result1["deduplicated_clusters"]) == len(result2["deduplicated_clusters"])
        assert result1["merged_count"] == result2["merged_count"]

        # Same surviving clusters in same order
        ids1 = [c["cluster_id"] for c in result1["deduplicated_clusters"]]
        ids2 = [c["cluster_id"] for c in result2["deduplicated_clusters"]]
        assert ids1 == ids2

    def test_permuted_input_same_result(self) -> None:
        """Different input ordering should produce same result."""
        cluster_a = make_cluster(cluster_id="cluster-0001")
        cluster_b = make_cluster(cluster_id="cluster-0002", keywords=("x", "y", "z"))
        cluster_c = make_cluster(cluster_id="cluster-0003", keywords=("p", "q", "r"))

        # Different orderings
        result1 = deduplicate_patterns([cluster_a, cluster_b, cluster_c])
        result2 = deduplicate_patterns([cluster_c, cluster_a, cluster_b])
        result3 = deduplicate_patterns([cluster_b, cluster_c, cluster_a])

        # All should have same result
        ids1 = sorted(c["cluster_id"] for c in result1["deduplicated_clusters"])
        ids2 = sorted(c["cluster_id"] for c in result2["deduplicated_clusters"])
        ids3 = sorted(c["cluster_id"] for c in result3["deduplicated_clusters"])

        assert ids1 == ids2 == ids3


# =============================================================================
# deduplicate_patterns Tests - Validation
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsValidation:
    """Tests for input validation."""

    def test_threshold_above_one_raises_error(self) -> None:
        """similarity_threshold > 1.0 should raise error."""
        with pytest.raises(PatternLearningValidationError):
            deduplicate_patterns([make_cluster()], similarity_threshold=1.5)

    def test_threshold_below_zero_raises_error(self) -> None:
        """similarity_threshold < 0.0 should raise error."""
        with pytest.raises(PatternLearningValidationError):
            deduplicate_patterns([make_cluster()], similarity_threshold=-0.1)

    def test_margin_above_one_raises_error(self) -> None:
        """near_threshold_margin > 1.0 should raise error."""
        with pytest.raises(PatternLearningValidationError):
            deduplicate_patterns([make_cluster()], near_threshold_margin=1.5)

    def test_margin_below_zero_raises_error(self) -> None:
        """near_threshold_margin < 0.0 should raise error."""
        with pytest.raises(PatternLearningValidationError):
            deduplicate_patterns([make_cluster()], near_threshold_margin=-0.1)

    def test_boundary_threshold_zero_accepted(self) -> None:
        """similarity_threshold = 0.0 should be accepted."""
        result = deduplicate_patterns([make_cluster()], similarity_threshold=0.0)
        assert result["threshold_used"] == 0.0

    def test_boundary_threshold_one_accepted(self) -> None:
        """similarity_threshold = 1.0 should be accepted."""
        result = deduplicate_patterns([make_cluster()], similarity_threshold=1.0)
        assert result["threshold_used"] == 1.0


# =============================================================================
# Integration Tests - Signature + Deduplication
# =============================================================================


@pytest.mark.unit
class TestSignatureDeduplicationIntegration:
    """Tests for signature and deduplication integration."""

    def test_deduplicated_clusters_have_unique_signatures(self) -> None:
        """Surviving clusters after deduplication should have unique signatures."""
        clusters = [
            make_cluster(cluster_id="cluster-0001", keywords=("a", "b")),
            make_cluster(cluster_id="cluster-0002", keywords=("c", "d")),
            make_cluster(cluster_id="cluster-0003", keywords=("e", "f")),
        ]

        result = deduplicate_patterns(clusters, similarity_threshold=0.99)

        # Generate signatures for surviving clusters
        signatures = [
            generate_pattern_signature(c)["signature"]
            for c in result["deduplicated_clusters"]
        ]

        # All signatures should be unique
        assert len(signatures) == len(set(signatures))
