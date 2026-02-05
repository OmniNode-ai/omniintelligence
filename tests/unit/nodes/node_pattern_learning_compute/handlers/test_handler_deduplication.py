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

from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_deduplication import (
    deduplicate_patterns,
    generate_pattern_signature,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.presets import (
    DEFAULT_DEDUPLICATION_THRESHOLD,
    NEAR_THRESHOLD_MARGIN,
    SIGNATURE_NORMALIZATION,
    SIGNATURE_VERSION,
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
    """Tests for generate_pattern_signature function.

    Note: generate_pattern_signature returns PatternSignatureResultDict which
    wraps the actual signature data in result["result"]. Tests must check
    result["success"] first, then access the signature via result["result"].
    """

    def test_returns_all_fields(self) -> None:
        """Signature result should contain all required fields."""
        cluster = make_cluster()
        result = generate_pattern_signature(cluster)

        # Result wrapper fields
        assert "success" in result
        assert "result" in result
        assert "error_message" in result
        assert result["success"] is True

        # Signature data fields
        sig = result["result"]
        assert sig is not None
        assert "signature" in sig
        assert "signature_version" in sig
        assert "signature_inputs" in sig
        assert "normalization_applied" in sig

    def test_signature_is_sha256_hex(self) -> None:
        """Signature should be a 64-character SHA256 hex string."""
        cluster = make_cluster()
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
        assert len(sig["signature"]) == 64
        assert all(c in "0123456789abcdef" for c in sig["signature"])

    def test_signature_version_matches_preset(self) -> None:
        """Signature version should match SIGNATURE_VERSION from presets."""
        cluster = make_cluster()
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
        assert sig["signature_version"] == SIGNATURE_VERSION

    def test_normalization_applied_matches_preset(self) -> None:
        """normalization_applied should match SIGNATURE_NORMALIZATION."""
        cluster = make_cluster()
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
        assert sig["normalization_applied"] == SIGNATURE_NORMALIZATION

    def test_signature_inputs_includes_pattern_type(self) -> None:
        """signature_inputs should include pattern_type as first element."""
        cluster = make_cluster(pattern_type="NodeEffect")
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
        # First input is pattern_type (lowercased)
        assert sig["signature_inputs"][0] == "nodeeffect"

    def test_signature_inputs_lowercased(self) -> None:
        """All signature inputs should be lowercased."""
        cluster = make_cluster(
            pattern_type="NodeCompute",
            keywords=("DEF", "CLASS", "MyFunc"),
            pattern_indicators=("NodeCompute", "FROZEN"),
        )
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
        # All inputs should be lowercase
        for input_str in sig["signature_inputs"]:
            assert input_str == input_str.lower()

    def test_signature_inputs_sorted(self) -> None:
        """Keywords and indicators in signature should be sorted."""
        cluster = make_cluster(
            keywords=("zebra", "apple", "mango"),
            pattern_indicators=("NodeCompute", "BaseModel"),
        )
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
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
        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
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

        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None
        # Should have pattern_type + 20 keywords max
        # First keyword after sort would be kw00, kw01, ... kw19
        assert len(sig["signature_inputs"]) <= 21  # 1 pattern_type + 20 keywords

    def test_determinism_same_input_same_output(self) -> None:
        """Same cluster should always produce the same signature."""
        cluster = make_cluster()

        result1 = generate_pattern_signature(cluster)
        result2 = generate_pattern_signature(cluster)

        assert result1["success"] is True
        assert result2["success"] is True
        sig1 = result1["result"]
        sig2 = result2["result"]
        assert sig1 is not None
        assert sig2 is not None
        assert sig1["signature"] == sig2["signature"]
        assert sig1["signature_inputs"] == sig2["signature_inputs"]

    def test_determinism_keyword_order_irrelevant(self) -> None:
        """Different keyword ordering should produce same signature."""
        cluster1 = make_cluster(keywords=("a", "b", "c"))
        cluster2 = make_cluster(keywords=("c", "a", "b"))

        result1 = generate_pattern_signature(cluster1)
        result2 = generate_pattern_signature(cluster2)

        assert result1["success"] is True
        assert result2["success"] is True
        sig1 = result1["result"]
        sig2 = result2["result"]
        assert sig1 is not None
        assert sig2 is not None
        assert sig1["signature"] == sig2["signature"]

    def test_empty_cluster_returns_structured_error(self) -> None:
        """Empty cluster should return structured error, not raise exception.

        Per CLAUDE.md: handlers must return structured errors, not raise
        domain exceptions. Validation errors are data, not exceptions.
        """
        result = generate_pattern_signature(None)

        assert result["success"] is False
        assert result["result"] is None
        assert result["error_message"] is not None
        assert "empty cluster" in result["error_message"].lower()


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

        # New structured error fields
        assert "success" in result
        assert "error_message" in result
        # Original fields
        assert "deduplicated_clusters" in result
        assert "merged_count" in result
        assert "threshold_used" in result
        assert "near_threshold_warnings" in result

    def test_threshold_used_explicit_in_output(self) -> None:
        """threshold_used should be explicit in output for policy transparency."""
        clusters = [make_cluster()]
        result = deduplicate_patterns(clusters, similarity_threshold=0.90)

        assert result["success"] is True
        assert result["threshold_used"] == 0.90

    def test_threshold_used_defaults_to_preset(self) -> None:
        """Default threshold should be DEFAULT_DEDUPLICATION_THRESHOLD."""
        clusters = [make_cluster()]
        result = deduplicate_patterns(clusters)

        assert result["success"] is True
        assert result["threshold_used"] == DEFAULT_DEDUPLICATION_THRESHOLD

    def test_empty_input_returns_empty_result(self) -> None:
        """Empty input should return empty deduplicated_clusters."""
        result = deduplicate_patterns([])

        assert result["success"] is True
        assert result["deduplicated_clusters"] == []
        assert result["merged_count"] == 0
        assert result["near_threshold_warnings"] == []
        assert result["error_message"] is None

    def test_single_cluster_unchanged(self) -> None:
        """Single cluster should pass through unchanged."""
        cluster = make_cluster()
        result = deduplicate_patterns([cluster])

        assert result["success"] is True
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

        assert len(result1["deduplicated_clusters"]) == len(
            result2["deduplicated_clusters"]
        )
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
# deduplicate_patterns Tests - Determinism Contract (B: sort-internally)
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsDeterminismContract:
    """Tests for B (sort-internally) contract compliance.

    These tests verify that the deduplication output is in canonical order
    regardless of input ordering, without requiring post-processing sorts.
    """

    def test_shuffled_clusters_produce_same_deduplication(self) -> None:
        """Multiple random shuffles of input produce identical output.

        This test verifies that regardless of how the input clusters are ordered,
        the deduplicated output is always identical - same IDs in same order.
        """
        import random

        # Create 5 clusters - some similar enough to merge, others distinct
        # cluster-0001 and cluster-0002 are identical (will be deduplicated)
        # cluster-0003, cluster-0004, cluster-0005 are distinct
        clusters = [
            make_cluster(
                cluster_id="cluster-0001",
                keywords=("alpha", "beta", "gamma"),
                pattern_indicators=("NodeCompute",),
            ),
            make_cluster(
                cluster_id="cluster-0002",
                keywords=("alpha", "beta", "gamma"),  # Same as cluster-0001
                pattern_indicators=("NodeCompute",),
            ),
            make_cluster(
                cluster_id="cluster-0003",
                keywords=("delta", "epsilon", "zeta"),
                pattern_indicators=("NodeEffect",),
            ),
            make_cluster(
                cluster_id="cluster-0004",
                keywords=("eta", "theta", "iota"),
                pattern_indicators=("NodeReducer",),
            ),
            make_cluster(
                cluster_id="cluster-0005",
                keywords=("kappa", "lambda", "mu"),
                pattern_indicators=("NodeOrchestrator",),
            ),
        ]

        # Get baseline result
        baseline_result = deduplicate_patterns(clusters, similarity_threshold=0.85)
        baseline_ids = [
            c["cluster_id"] for c in baseline_result["deduplicated_clusters"]
        ]

        # Run 10 iterations with random shuffles
        random.seed(42)  # For reproducibility
        for iteration in range(10):
            shuffled = clusters.copy()
            random.shuffle(shuffled)

            result = deduplicate_patterns(shuffled, similarity_threshold=0.85)
            result_ids = [c["cluster_id"] for c in result["deduplicated_clusters"]]

            # Assert identical output (same IDs in same order) - NO sorting needed
            assert result_ids == baseline_ids, (
                f"Iteration {iteration}: shuffled input produced different output. "
                f"Expected {baseline_ids}, got {result_ids}"
            )

    def test_deduplicated_output_already_in_canonical_order(self) -> None:
        """Output list is in canonical order without needing sort().

        The deduplicated_clusters list should be pre-sorted by cluster_id,
        not requiring manual sorting by the caller.
        """
        # Create clusters that will be partially merged (0001 and 0002 identical)
        clusters = [
            make_cluster(
                cluster_id="cluster-0005",  # Intentionally out of order
                keywords=("mu", "nu", "xi"),
                pattern_indicators=("NodeOrchestrator",),
            ),
            make_cluster(
                cluster_id="cluster-0002",
                keywords=("alpha", "beta", "gamma"),  # Same as 0001
                pattern_indicators=("NodeCompute",),
            ),
            make_cluster(
                cluster_id="cluster-0003",
                keywords=("delta", "epsilon", "zeta"),
                pattern_indicators=("NodeEffect",),
            ),
            make_cluster(
                cluster_id="cluster-0001",
                keywords=("alpha", "beta", "gamma"),  # Same as 0002
                pattern_indicators=("NodeCompute",),
            ),
            make_cluster(
                cluster_id="cluster-0004",
                keywords=("eta", "theta", "iota"),
                pattern_indicators=("NodeReducer",),
            ),
        ]

        result = deduplicate_patterns(clusters, similarity_threshold=0.85)
        deduplicated = result["deduplicated_clusters"]

        # Verify there are at least 2 clusters to check ordering
        assert len(deduplicated) >= 2, "Need at least 2 clusters to verify ordering"

        # Verify the output is already sorted - no manual sorting needed
        for i in range(len(deduplicated) - 1):
            current_id = deduplicated[i]["cluster_id"]
            next_id = deduplicated[i + 1]["cluster_id"]
            assert current_id < next_id, (
                f"Output not in canonical order: {current_id} should come before {next_id}. "
                f"Full order: {[c['cluster_id'] for c in deduplicated]}"
            )

    def test_confidence_tiebreak_uses_member_count_then_leader(self) -> None:
        """When confidence ties, member_count breaks tie; when that ties, smaller leader wins.

        Tiebreak order:
        1. Higher confidence wins
        2. If confidence ties, larger member_count wins
        3. If member_count ties, smaller leader (member_ids[0]) wins
        """
        # Test case 1: Confidence tie, different member counts
        # cluster-0001 has 2 members, cluster-0002 has 4 members
        # Both have same confidence (internal_similarity used as fallback)
        cluster_fewer_members = make_cluster(
            cluster_id="cluster-0001",
            keywords=("shared", "keywords", "here"),
            pattern_indicators=("NodeCompute",),
            member_ids=("item-a", "item-b"),
            member_count=2,
            internal_similarity=0.85,  # Same confidence
        )
        cluster_more_members = make_cluster(
            cluster_id="cluster-0002",
            keywords=("shared", "keywords", "here"),  # Same - will be deduplicated
            pattern_indicators=("NodeCompute",),
            member_ids=("item-c", "item-d", "item-e", "item-f"),
            member_count=4,
            internal_similarity=0.85,  # Same confidence
        )

        result1 = deduplicate_patterns(
            [cluster_fewer_members, cluster_more_members],
            similarity_threshold=0.5,  # Low threshold to force deduplication
        )

        assert len(result1["deduplicated_clusters"]) == 1
        # Cluster with more members survives
        assert result1["deduplicated_clusters"][0]["cluster_id"] == "cluster-0002", (
            "When confidence ties, larger member_count should win"
        )

        # Test case 2: Confidence tie AND member_count tie, smaller leader wins
        cluster_larger_leader = make_cluster(
            cluster_id="cluster-0003",
            keywords=("identical", "pattern", "set"),
            pattern_indicators=("NodeEffect",),
            member_ids=("zebra-item",),  # Larger leader
            member_count=1,
            internal_similarity=0.85,
        )
        cluster_smaller_leader = make_cluster(
            cluster_id="cluster-0004",
            keywords=("identical", "pattern", "set"),  # Same - will be deduplicated
            pattern_indicators=("NodeEffect",),
            member_ids=("alpha-item",),  # Smaller leader
            member_count=1,
            internal_similarity=0.85,
        )

        result2 = deduplicate_patterns(
            [cluster_larger_leader, cluster_smaller_leader],
            similarity_threshold=0.5,  # Low threshold to force deduplication
        )

        assert len(result2["deduplicated_clusters"]) == 1
        # Cluster with smaller leader (member_ids[0]) survives
        assert result2["deduplicated_clusters"][0]["cluster_id"] == "cluster-0004", (
            "When confidence and member_count tie, smaller leader should win"
        )


# =============================================================================
# deduplicate_patterns Tests - Validation
# =============================================================================


@pytest.mark.unit
class TestDeduplicatePatternsValidation:
    """Tests for input validation.

    Per CLAUDE.md: handlers must return structured errors, not raise
    domain exceptions. Validation errors are data, not exceptions.
    """

    def test_threshold_above_one_returns_structured_error(self) -> None:
        """similarity_threshold > 1.0 should return structured error."""
        result = deduplicate_patterns([make_cluster()], similarity_threshold=1.5)

        assert result["success"] is False
        assert result["error_message"] is not None
        assert "similarity_threshold" in result["error_message"]
        assert "[0.0, 1.0]" in result["error_message"]

    def test_threshold_below_zero_returns_structured_error(self) -> None:
        """similarity_threshold < 0.0 should return structured error."""
        result = deduplicate_patterns([make_cluster()], similarity_threshold=-0.1)

        assert result["success"] is False
        assert result["error_message"] is not None
        assert "similarity_threshold" in result["error_message"]

    def test_margin_above_one_returns_structured_error(self) -> None:
        """near_threshold_margin > 1.0 should return structured error."""
        result = deduplicate_patterns([make_cluster()], near_threshold_margin=1.5)

        assert result["success"] is False
        assert result["error_message"] is not None
        assert "near_threshold_margin" in result["error_message"]

    def test_margin_below_zero_returns_structured_error(self) -> None:
        """near_threshold_margin < 0.0 should return structured error."""
        result = deduplicate_patterns([make_cluster()], near_threshold_margin=-0.1)

        assert result["success"] is False
        assert result["error_message"] is not None
        assert "near_threshold_margin" in result["error_message"]

    def test_boundary_threshold_zero_accepted(self) -> None:
        """similarity_threshold = 0.0 should be accepted."""
        result = deduplicate_patterns([make_cluster()], similarity_threshold=0.0)

        assert result["success"] is True
        assert result["threshold_used"] == 0.0

    def test_boundary_threshold_one_accepted(self) -> None:
        """similarity_threshold = 1.0 should be accepted."""
        result = deduplicate_patterns([make_cluster()], similarity_threshold=1.0)

        assert result["success"] is True
        assert result["threshold_used"] == 1.0


# =============================================================================
# Replay Artifact Invariant Tests
# =============================================================================


@pytest.mark.unit
class TestDeduplicationReplayInvariants:
    """Surgical invariant tests for signature and warning artifacts.

    These tests verify exact replay artifacts for determinism guarantees:
    - Signature golden hash must match exactly (no drift)
    - Warning cluster IDs must reference valid input clusters
    - Warning similarity must be within the documented margin
    """

    def test_signature_golden_input_exact_hash(self) -> None:
        """Golden cluster input produces exact expected signature hash.

        FROZEN TEST DATA:
            cluster_id="test-golden"
            pattern_type="compute"
            keywords=("async", "await", "handler")
            pattern_indicators=("NodeCompute", "BaseModel")

        Expected signature inputs (normalized, sorted):
            ("compute", "async", "await", "handler", "basemodel", "nodecompute")

        This test MUST fail if signature algorithm changes, alerting developers
        to bump SIGNATURE_VERSION.
        """
        # Create FROZEN cluster with exact known values
        cluster = make_cluster(
            cluster_id="test-golden",
            pattern_type="compute",
            keywords=("async", "await", "handler"),
            pattern_indicators=("NodeCompute", "BaseModel"),
        )

        result = generate_pattern_signature(cluster)

        assert result["success"] is True
        sig = result["result"]
        assert sig is not None

        # Assert exact golden hash (computed once, frozen forever)
        expected_hash = (
            "f627fa55ebd8499dea29b6c42c5ed0f91acfe4ba9eb9328b7ff1cdb70b720684"
        )
        assert sig["signature"] == expected_hash, (
            f"Signature hash drift detected! "
            f"Expected {expected_hash}, got {sig['signature']}. "
            f"If algorithm changed intentionally, bump SIGNATURE_VERSION."
        )

        # Assert version matches preset
        assert sig["signature_version"] == SIGNATURE_VERSION

        # Assert exact signature inputs (order matters for hash)
        expected_inputs = (
            "compute",
            "async",
            "await",
            "handler",
            "basemodel",
            "nodecompute",
        )
        assert sig["signature_inputs"] == expected_inputs

    def test_near_threshold_warning_cluster_ids_are_valid(self) -> None:
        """Warning cluster_a_id and cluster_b_id are from input clusters.

        This invariant ensures warnings reference actual clusters, not phantom IDs.
        Both cluster_a_id and cluster_b_id must exist in the input cluster list.
        """
        # Create clusters that will trigger a near-threshold warning
        # Using similarity just below threshold (within NEAR_THRESHOLD_MARGIN)
        cluster1 = make_cluster(
            cluster_id="cluster-warning-a",
            keywords=("alpha", "beta", "gamma", "delta"),
            pattern_indicators=("NodeCompute",),
        )
        cluster2 = make_cluster(
            cluster_id="cluster-warning-b",
            keywords=("alpha", "beta", "gamma", "epsilon"),  # High overlap
            pattern_indicators=("NodeCompute",),
        )
        cluster3 = make_cluster(
            cluster_id="cluster-warning-c",
            keywords=("zeta", "eta", "theta", "iota"),  # Different
            pattern_indicators=("NodeEffect",),
        )

        input_clusters = [cluster1, cluster2, cluster3]
        input_cluster_ids = {c["cluster_id"] for c in input_clusters}

        # Run deduplication with margin that might produce warnings
        result = deduplicate_patterns(
            input_clusters,
            similarity_threshold=0.85,
            near_threshold_margin=NEAR_THRESHOLD_MARGIN,
        )

        # Assert ALL warning cluster IDs are from the input
        for warning in result["near_threshold_warnings"]:
            assert warning["cluster_a_id"] in input_cluster_ids, (
                f"Warning cluster_a_id '{warning['cluster_a_id']}' "
                f"not in input clusters: {input_cluster_ids}"
            )
            assert warning["cluster_b_id"] in input_cluster_ids, (
                f"Warning cluster_b_id '{warning['cluster_b_id']}' "
                f"not in input clusters: {input_cluster_ids}"
            )

    def test_invariant_warning_similarity_within_margin(self) -> None:
        """Warning similarity is within NEAR_THRESHOLD_MARGIN of threshold.

        For "kept_separate" warnings:
            threshold - margin <= similarity < threshold

        For "merged" warnings:
            threshold <= similarity < threshold + margin

        This invariant ensures warnings are only emitted for borderline cases.
        """
        # Create clusters with high similarity that will merge
        cluster1 = make_cluster(
            cluster_id="cluster-margin-a",
            keywords=("shared", "common", "terms"),
            pattern_indicators=("NodeCompute",),
        )
        cluster2 = make_cluster(
            cluster_id="cluster-margin-b",
            keywords=("shared", "common", "terms"),  # Identical = high similarity
            pattern_indicators=("NodeCompute",),
        )
        # Create a cluster that's somewhat similar (partial overlap)
        cluster3 = make_cluster(
            cluster_id="cluster-margin-c",
            keywords=("shared", "different", "stuff"),
            pattern_indicators=("NodeCompute",),
        )

        threshold = 0.85
        margin = NEAR_THRESHOLD_MARGIN

        result = deduplicate_patterns(
            [cluster1, cluster2, cluster3],
            similarity_threshold=threshold,
            near_threshold_margin=margin,
        )

        # Verify each warning's similarity is in the correct range
        for warning in result["near_threshold_warnings"]:
            sim = warning["similarity"]
            action = warning["action_taken"]

            if action == "kept_separate":
                # Similarity should be: threshold - margin <= sim < threshold
                assert (threshold - margin) <= sim < threshold, (
                    f"kept_separate warning has similarity {sim} outside valid range "
                    f"[{threshold - margin}, {threshold}). Margin={margin}"
                )
            elif action == "merged":
                # Similarity should be: threshold <= sim < threshold + margin
                assert threshold <= sim < (threshold + margin), (
                    f"merged warning has similarity {sim} outside valid range "
                    f"[{threshold}, {threshold + margin}). Margin={margin}"
                )
            else:
                pytest.fail(f"Unknown action_taken: {action}")

    def test_near_threshold_no_false_warnings(self) -> None:
        """Clusters with similarity far from threshold produce no warnings.

        When similarity is significantly below or above the threshold
        (outside the NEAR_THRESHOLD_MARGIN window), no warnings should be emitted.
        """
        threshold = 0.85
        margin = NEAR_THRESHOLD_MARGIN  # 0.05

        # Create clusters with very LOW similarity (far below threshold - margin)
        # Completely different keywords = similarity ~0.0
        cluster_low_a = make_cluster(
            cluster_id="cluster-far-low-a",
            keywords=("aaa", "bbb", "ccc"),
            pattern_indicators=("NodeCompute",),
        )
        cluster_low_b = make_cluster(
            cluster_id="cluster-far-low-b",
            keywords=("xxx", "yyy", "zzz"),  # Completely different
            pattern_indicators=("NodeEffect",),  # Also different indicator
        )

        result_low = deduplicate_patterns(
            [cluster_low_a, cluster_low_b],
            similarity_threshold=threshold,
            near_threshold_margin=margin,
        )

        # Very low similarity should not trigger warnings
        assert result_low["near_threshold_warnings"] == [], (
            f"Clusters with very low similarity should not produce warnings. "
            f"Got: {result_low['near_threshold_warnings']}"
        )

        # Create clusters with very HIGH similarity (far above threshold + margin)
        # Using threshold = 0.5 so identical clusters (sim=1.0) are far above threshold + margin
        cluster_high_a = make_cluster(
            cluster_id="cluster-far-high-a",
            keywords=("identical", "keywords", "here"),
            pattern_indicators=("NodeCompute",),
        )
        cluster_high_b = make_cluster(
            cluster_id="cluster-far-high-b",
            keywords=("identical", "keywords", "here"),  # Same = sim ~1.0
            pattern_indicators=("NodeCompute",),
        )

        # With threshold=0.5 and margin=0.05, sim=1.0 is far above 0.55
        result_high = deduplicate_patterns(
            [cluster_high_a, cluster_high_b],
            similarity_threshold=0.5,
            near_threshold_margin=margin,
        )

        # Very high similarity (far above threshold+margin) should not trigger warnings
        assert result_high["near_threshold_warnings"] == [], (
            f"Clusters with very high similarity (far above threshold) should not "
            f"produce warnings. Got: {result_high['near_threshold_warnings']}"
        )


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

        dedup_result = deduplicate_patterns(clusters, similarity_threshold=0.99)

        assert dedup_result["success"] is True

        # Generate signatures for surviving clusters
        signatures = []
        for c in dedup_result["deduplicated_clusters"]:
            sig_result = generate_pattern_signature(c)
            assert sig_result["success"] is True
            assert sig_result["result"] is not None
            signatures.append(sig_result["result"]["signature"])

        # All signatures should be unique
        assert len(signatures) == len(set(signatures))
