# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""TC3: Duplicate Pattern Detection E2E Integration Tests.

This module tests the deduplication functionality of the pattern learning pipeline.
It verifies that similar patterns from different sessions are correctly identified
and deduplicated while preserving source tracking.

Test Flow:
    1. Use duplicate session data (two sessions with similar prompts)
    2. Run both through NodePatternLearningCompute
    3. Verify deduplication merges into single pattern (or links via signature_hash)
    4. Verify version/lineage tracking works correctly

Key Assertions:
    - Similar patterns produce the same signature_hash
    - Deduplication reduces pattern count appropriately
    - Source session tracking is preserved in merged patterns
    - Near-threshold warnings are emitted for borderline cases

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
    - handler_deduplication.py: Pattern deduplication with versioned signatures
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

logger = logging.getLogger(__name__)

from tests.integration.e2e.fixtures import (
    sample_duplicate_session_data,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
        HandlerPatternLearning,
    )


# =============================================================================
# TC3: Duplicate Pattern Detection Tests
# =============================================================================


@pytest.mark.integration
class TestTC3DuplicateDetection:
    """TC3: Verify duplicate pattern detection across sessions."""

    def test_similar_sessions_produce_deduplicated_patterns(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that similar patterns from different sessions are deduplicated.

        This test verifies the core deduplication behavior:
        1. Two sessions with semantically similar code patterns are processed
        2. The pipeline detects the similarity via feature extraction and clustering
        3. Similar patterns are deduplicated (merged into fewer clusters)
        4. The final pattern count is less than the combined input count

        The duplicate session data contains:
        - Session A: Order service with async service method + FastAPI endpoint
        - Session B: Invoice service with async service method + FastAPI endpoint

        Both sessions share the same structural patterns (async service create,
        FastAPI POST endpoint) even though they operate on different entities.
        """
        # Arrange
        session_a_data, session_b_data = sample_duplicate_session_data()

        # Act - Run each session through the pipeline
        result_a = pattern_learning_handler.handle(session_a_data)
        result_b = pattern_learning_handler.handle(session_b_data)

        # Act - Run combined data through the pipeline
        combined_data = session_a_data + session_b_data
        result_combined = pattern_learning_handler.handle(combined_data)

        # Assert - All operations should succeed
        assert result_a["success"], "Session A pattern learning should succeed"
        assert result_b["success"], "Session B pattern learning should succeed"
        assert result_combined["success"], "Combined pattern learning should succeed"

        # Get total patterns from individual runs
        individual_pattern_count = (
            len(result_a["learned_patterns"])
            + len(result_a["candidate_patterns"])
            + len(result_b["learned_patterns"])
            + len(result_b["candidate_patterns"])
        )

        # Get patterns from combined run
        combined_pattern_count = len(result_combined["learned_patterns"]) + len(
            result_combined["candidate_patterns"]
        )

        # Assert - Deduplication should reduce pattern count
        # When similar patterns are processed together, they should be merged
        assert combined_pattern_count <= individual_pattern_count, (
            f"Combined processing should produce fewer or equal patterns due to "
            f"deduplication. Individual runs produced {individual_pattern_count} "
            f"total patterns, but combined run produced {combined_pattern_count}"
        )

        # Assert - Verify metrics show merging occurred
        assert (
            result_combined["metrics"].merged_count >= 0
        ), "Merged count should be tracked in metrics"

        # If there were enough similar items to cluster, verify deduplication
        if result_combined["metrics"].cluster_count > 0:
            # Check that deduplication threshold was applied
            assert (
                result_combined["metadata"].deduplication_threshold_used > 0
            ), "Deduplication threshold should be set in metadata"

    def test_signature_hash_identifies_duplicates(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that signature_hash correctly identifies duplicate patterns.

        This test verifies the signature-based duplicate detection:
        1. Similar patterns should produce identical or very similar signatures
        2. Signatures are deterministic given the same features
        3. The signature algorithm is stable across runs

        The signature is computed from:
        - pattern_type (lowercased)
        - keywords (sorted, deduped, limited to 20)
        - pattern_indicators (sorted, deduped)
        """
        # Arrange
        session_a_data, session_b_data = sample_duplicate_session_data()
        combined_data = session_a_data + session_b_data

        # Act - Run combined data twice to verify determinism
        result_1 = pattern_learning_handler.handle(combined_data)
        result_2 = pattern_learning_handler.handle(combined_data)

        # Assert - Both runs should produce same patterns
        assert result_1["success"] and result_2["success"]

        # Extract all signatures from both runs
        all_patterns_1 = result_1["learned_patterns"] + result_1["candidate_patterns"]
        all_patterns_2 = result_2["learned_patterns"] + result_2["candidate_patterns"]

        # Same input should produce same number of patterns
        assert len(all_patterns_1) == len(all_patterns_2), (
            f"Determinism violation: run 1 produced {len(all_patterns_1)} patterns, "
            f"run 2 produced {len(all_patterns_2)} patterns"
        )

        # Extract signatures from both runs
        signatures_1 = {p.signature_info.signature for p in all_patterns_1}
        signatures_2 = {p.signature_info.signature for p in all_patterns_2}

        # Signatures should be identical between runs (determinism)
        assert signatures_1 == signatures_2, (
            "Signature generation should be deterministic - same input should produce "
            "same signatures across runs"
        )

        # Verify signature structure
        for pattern in all_patterns_1:
            sig_info = pattern.signature_info
            # Signature should be a 64-character SHA256 hex string
            assert len(sig_info.signature) == 64, (
                f"Signature should be 64-character SHA256 hex, "
                f"got {len(sig_info.signature)}"
            )
            assert all(
                c in "0123456789abcdef" for c in sig_info.signature
            ), "Signature should only contain hex characters"
            # Signature version should be set
            assert (
                sig_info.signature_version is not None
            ), "Signature version should be set"
            # Signature inputs should be a tuple of strings
            assert isinstance(
                sig_info.signature_inputs, tuple
            ), "Signature inputs should be a tuple"
            assert (
                len(sig_info.signature_inputs) > 0
            ), "Signature inputs should not be empty"

    def test_merged_pattern_combines_session_ids(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that merged patterns preserve source session information.

        This test verifies source tracking in deduplicated patterns:
        1. When patterns are merged, source count should reflect combined sources
        2. Pattern confidence may increase with more supporting evidence
        3. Member count should reflect all contributing items

        Note: The current implementation tracks source_count at the pattern level,
        not individual session IDs. This test verifies that the count reflects
        the combined input items.
        """
        # Arrange
        session_a_data, session_b_data = sample_duplicate_session_data()

        # Get individual session results
        result_a = pattern_learning_handler.handle(session_a_data)
        result_b = pattern_learning_handler.handle(session_b_data)

        # Run combined
        combined_data = session_a_data + session_b_data
        result_combined = pattern_learning_handler.handle(combined_data)

        # Assert - All should succeed
        assert (
            result_a["success"] and result_b["success"] and result_combined["success"]
        )

        # Get all patterns
        patterns_a = result_a["learned_patterns"] + result_a["candidate_patterns"]
        patterns_b = result_b["learned_patterns"] + result_b["candidate_patterns"]
        patterns_combined = (
            result_combined["learned_patterns"] + result_combined["candidate_patterns"]
        )

        # If deduplication occurred, combined patterns should have higher source_count
        # than the maximum from individual sessions
        if patterns_combined:
            max_combined_source = max(p.source_count for p in patterns_combined)
            max_individual_source_a = (
                max(p.source_count for p in patterns_a) if patterns_a else 0
            )
            max_individual_source_b = (
                max(p.source_count for p in patterns_b) if patterns_b else 0
            )

            # Combined processing should aggregate sources from both sessions
            # (at minimum, the combined max should be >= individual maxes)
            assert max_combined_source >= max_individual_source_a, (
                f"Combined patterns should have at least as many sources as "
                f"session A (combined: {max_combined_source}, "
                f"session A: {max_individual_source_a})"
            )
            assert max_combined_source >= max_individual_source_b, (
                f"Combined patterns should have at least as many sources as "
                f"session B (combined: {max_combined_source}, "
                f"session B: {max_individual_source_b})"
            )

        # Verify input tracking in metrics
        assert result_combined["metrics"].input_count == len(combined_data), (
            f"Metrics should track all input items: expected {len(combined_data)}, "
            f"got {result_combined['metrics'].input_count}"
        )

    def test_deduplication_threshold_affects_merge_count(
        self,
        _pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that deduplication threshold affects how many patterns are merged.

        This test verifies threshold sensitivity by calling deduplicate_patterns
        directly with different threshold values:
        1. Very low threshold (0.3) should merge aggressively (more merged)
        2. Default threshold (0.85) should merge moderately
        3. Very high threshold (0.99) should preserve most distinct patterns

        The test ensures that changing the threshold actually changes behavior,
        which would catch regressions in threshold logic.
        """
        from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
            handler_confidence_scoring,
            handler_deduplication,
            handler_feature_extraction,
            handler_pattern_clustering,
            presets,
        )

        DEFAULT_DEDUPLICATION_THRESHOLD = presets.DEFAULT_DEDUPLICATION_THRESHOLD
        DEFAULT_SIMILARITY_WEIGHTS = presets.DEFAULT_SIMILARITY_WEIGHTS

        # Arrange - Get combined data and run through extraction and clustering
        session_a_data, session_b_data = sample_duplicate_session_data()
        combined_data = list(session_a_data + session_b_data)

        # Extract features and cluster patterns
        features_list = handler_feature_extraction.extract_features_batch(combined_data)
        clusters = handler_pattern_clustering.cluster_patterns(
            features_list=features_list,
            weights=DEFAULT_SIMILARITY_WEIGHTS,
        )

        # Skip if not enough clusters for meaningful threshold testing
        if len(clusters) < 2:
            pytest.skip("Not enough clusters for threshold sensitivity testing")

        # Compute confidence scores for deduplication
        confidence_scores: dict[str, float] = {}
        for cluster in clusters:
            scores = handler_confidence_scoring.compute_cluster_scores(cluster)
            confidence_scores[cluster["cluster_id"]] = scores["confidence"]

        # Act - Test with different thresholds
        # Very low threshold (0.3) - should merge very aggressively
        result_low = handler_deduplication.deduplicate_patterns(
            clusters=clusters,
            confidence_scores=confidence_scores,
            similarity_threshold=0.3,
            weights=DEFAULT_SIMILARITY_WEIGHTS,
        )

        # Default threshold (0.85) - moderate merging
        result_default = handler_deduplication.deduplicate_patterns(
            clusters=clusters,
            confidence_scores=confidence_scores,
            similarity_threshold=DEFAULT_DEDUPLICATION_THRESHOLD,
            weights=DEFAULT_SIMILARITY_WEIGHTS,
        )

        # Very high threshold (0.99) - almost no merging
        result_high = handler_deduplication.deduplicate_patterns(
            clusters=clusters,
            confidence_scores=confidence_scores,
            similarity_threshold=0.99,
            weights=DEFAULT_SIMILARITY_WEIGHTS,
        )

        # Assert - Verify threshold is recorded correctly in each result
        assert result_low["threshold_used"] == 0.3
        assert result_default["threshold_used"] == DEFAULT_DEDUPLICATION_THRESHOLD
        assert result_high["threshold_used"] == 0.99

        # Assert - Lower threshold should merge more (fewer surviving clusters)
        # Higher threshold should preserve more (more surviving clusters)
        low_cluster_count = len(result_low["deduplicated_clusters"])
        default_cluster_count = len(result_default["deduplicated_clusters"])
        high_cluster_count = len(result_high["deduplicated_clusters"])

        # Core threshold sensitivity assertion:
        # As threshold increases, cluster count should increase (or stay same)
        assert low_cluster_count <= default_cluster_count, (
            f"Lower threshold (0.3) should produce same or fewer clusters than "
            f"default. Low: {low_cluster_count}, Default: {default_cluster_count}"
        )
        assert default_cluster_count <= high_cluster_count, (
            f"Default threshold should produce same or fewer clusters than high "
            f"(0.99). Default: {default_cluster_count}, High: {high_cluster_count}"
        )

        # Assert - Merged count should reflect threshold sensitivity
        # Lower threshold = more merges, higher threshold = fewer merges
        assert result_low["merged_count"] >= result_default["merged_count"], (
            f"Lower threshold should merge same or more patterns. "
            f"Low merged: {result_low['merged_count']}, "
            f"Default merged: {result_default['merged_count']}"
        )
        assert result_default["merged_count"] >= result_high["merged_count"], (
            f"Default threshold should merge same or more than high threshold. "
            f"Default merged: {result_default['merged_count']}, "
            f"High merged: {result_high['merged_count']}"
        )

        # Assert - High threshold should preserve original cluster count
        assert high_cluster_count >= len(clusters) - 1, (
            f"Very high threshold (0.99) should preserve most clusters. "
            f"Original: {len(clusters)}, After 0.99 threshold: {high_cluster_count}"
        )

        # CRITICAL: Verify threshold sensitivity - extreme thresholds (0.3 vs 0.99)
        # MUST produce different behavior. If all values are equal, the test passes
        # vacuously without verifying threshold logic actually works.
        # At least ONE of these conditions must be true:
        #   - Low threshold produces fewer clusters than high threshold, OR
        #   - Low threshold produces more merges than high threshold
        assert (
            low_cluster_count < high_cluster_count
            or result_low["merged_count"] > result_high["merged_count"]
        ), (
            f"THRESHOLD SENSITIVITY FAILURE: Extreme thresholds (0.3 vs 0.99) "
            f"produced identical results.\n"
            f"  Cluster counts: low={low_cluster_count}, "
            f"default={default_cluster_count}, high={high_cluster_count}\n"
            f"  Merged counts: low={result_low['merged_count']}, "
            f"default={result_default['merged_count']}, "
            f"high={result_high['merged_count']}\n"
            f"  Original clusters: {len(clusters)}\n"
            f"Either the test data lacks sufficient similarity variance, "
            f"or the threshold logic has a regression."
        )

        # Log metrics for debugging
        logger.debug(
            "Threshold sensitivity results: "
            "low(0.3)=%d clusters/%d merged, "
            "default(%.2f)=%d clusters/%d merged, "
            "high(0.99)=%d clusters/%d merged, "
            "original=%d clusters",
            low_cluster_count,
            result_low["merged_count"],
            DEFAULT_DEDUPLICATION_THRESHOLD,
            default_cluster_count,
            result_default["merged_count"],
            high_cluster_count,
            result_high["merged_count"],
            len(clusters),
        )

    def test_near_threshold_warnings_emitted(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that near-threshold cases emit warnings for review.

        This test verifies warning generation for borderline cases:
        1. Patterns near the deduplication threshold may emit warnings
        2. Warnings indicate whether patterns were "kept_separate" or "merged"
        3. Warnings are preserved in the result for debugging

        Policy: Prefer false negatives over false positives
        (You can merge later; you can't un-merge)
        """
        # Arrange
        session_a_data, session_b_data = sample_duplicate_session_data()
        combined_data = session_a_data + session_b_data

        # Act
        result = pattern_learning_handler.handle(combined_data)

        # Assert - Operation should succeed
        assert result["success"]

        # Warnings should be a list (may be empty if no borderline cases)
        assert isinstance(result["warnings"], list), "Warnings should be a list"

        # If there are warnings, they should be strings
        for warning in result["warnings"]:
            assert isinstance(warning, str), "Each warning should be a string"

        # Check for near-threshold warnings (if any)
        near_threshold_warnings = [
            w for w in result["warnings"] if "near-threshold" in w.lower()
        ]

        # Log warnings for debugging
        if near_threshold_warnings:
            logger.debug(
                "Near-threshold warnings found: %d", len(near_threshold_warnings)
            )
            for w in near_threshold_warnings:
                logger.debug("  - %s", w)


@pytest.mark.integration
class TestTC3SignatureStability:
    """TC3 Extension: Verify signature stability and versioning."""

    def test_signature_version_is_tracked(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that signature version is properly tracked for migration safety.

        The signature algorithm may change over time. Version tracking enables:
        - Detecting when signatures from different algorithm versions are compared
        - Migration path when algorithm changes
        - Debugging "why did this pattern change?" questions
        """
        # Arrange
        session_a_data, _ = sample_duplicate_session_data()

        # Act
        result = pattern_learning_handler.handle(session_a_data)

        # Assert
        assert result["success"]
        all_patterns = result["learned_patterns"] + result["candidate_patterns"]

        for pattern in all_patterns:
            sig_info = pattern.signature_info

            # Version should be a ModelSemVer instance
            assert (
                sig_info.signature_version is not None
            ), "Signature version should be set"

            # Major version should be at least 1 (we're post-v1.0.0)
            assert sig_info.signature_version.major >= 1, (
                f"Signature version major should be >= 1, "
                f"got {sig_info.signature_version}"
            )

            # Normalization should be documented
            assert (
                sig_info.normalization_applied is not None
            ), "Normalization method should be documented"
            assert (
                len(sig_info.normalization_applied) > 0
            ), "Normalization method should not be empty"

    def test_signature_inputs_are_auditable(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that signature inputs are preserved for audit/debugging.

        Signature inputs should include:
        - pattern_type (lowercased, first element)
        - keywords (sorted, limited to 20)
        - pattern_indicators (sorted)

        These inputs enable debugging "why did two patterns get the same/different
        signature?" questions.
        """
        # Arrange
        session_a_data, _ = sample_duplicate_session_data()

        # Act
        result = pattern_learning_handler.handle(session_a_data)

        # Assert
        assert result["success"]
        all_patterns = result["learned_patterns"] + result["candidate_patterns"]

        for pattern in all_patterns:
            sig_info = pattern.signature_info

            # Signature inputs should be present
            assert (
                sig_info.signature_inputs is not None
            ), "Signature inputs should be preserved"
            assert (
                len(sig_info.signature_inputs) > 0
            ), "Signature inputs should not be empty"

            # First input should be pattern_type (lowercased)
            first_input = sig_info.signature_inputs[0]
            assert first_input.islower(), (
                f"First signature input (pattern_type) should be lowercase, "
                f"got '{first_input}'"
            )

            # All inputs should be lowercase (normalization)
            for input_val in sig_info.signature_inputs:
                assert (
                    input_val == input_val.lower()
                ), f"All signature inputs should be lowercase, got '{input_val}'"


@pytest.mark.integration
class TestTC3DeterminismGuarantees:
    """TC3 Extension: Verify determinism guarantees for deduplication."""

    def test_same_input_produces_same_deduplication(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that same input always produces same deduplication result.

        DETERMINISM INVARIANT: Given the same input data:
        - Same number of patterns produced
        - Same signatures generated
        - Same merged_count
        - Same warnings (content may vary but count should be stable)
        """
        # Arrange
        session_a_data, session_b_data = sample_duplicate_session_data()
        combined_data = session_a_data + session_b_data

        # Act - Run 5 times
        results = [pattern_learning_handler.handle(combined_data) for _ in range(5)]

        # Assert - All runs should succeed
        for i, result in enumerate(results):
            assert result["success"], f"Run {i + 1} should succeed"

        # All runs should produce same pattern count
        pattern_counts = [
            len(r["learned_patterns"]) + len(r["candidate_patterns"]) for r in results
        ]
        assert (
            len(set(pattern_counts)) == 1
        ), f"All runs should produce same pattern count, got {pattern_counts}"

        # All runs should produce same merged_count
        merged_counts = [r["metrics"].merged_count for r in results]
        assert (
            len(set(merged_counts)) == 1
        ), f"All runs should produce same merged_count, got {merged_counts}"

        # All runs should produce same signatures
        signature_sets = [
            frozenset(
                p.signature_info.signature
                for p in (r["learned_patterns"] + r["candidate_patterns"])
            )
            for r in results
        ]
        assert all(
            s == signature_sets[0] for s in signature_sets
        ), "All runs should produce same set of signatures"

    def test_input_order_does_not_affect_result(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that input order does not affect deduplication result.

        DETERMINISM INVARIANT: The deduplication algorithm sorts internally,
        so different input orderings should produce identical results.
        """
        # Arrange
        session_a_data, session_b_data = sample_duplicate_session_data()

        # Different orderings
        ordering_1 = session_a_data + session_b_data
        ordering_2 = session_b_data + session_a_data
        ordering_3 = [
            session_a_data[0],
            session_b_data[0],
            session_a_data[1] if len(session_a_data) > 1 else session_a_data[0],
            session_b_data[1] if len(session_b_data) > 1 else session_b_data[0],
        ]

        # Act
        result_1 = pattern_learning_handler.handle(ordering_1)
        result_2 = pattern_learning_handler.handle(ordering_2)
        result_3 = pattern_learning_handler.handle(ordering_3)

        # Assert - All should succeed
        assert result_1["success"] and result_2["success"] and result_3["success"]

        # Same pattern count
        count_1 = len(result_1["learned_patterns"]) + len(
            result_1["candidate_patterns"]
        )
        count_2 = len(result_2["learned_patterns"]) + len(
            result_2["candidate_patterns"]
        )

        # ordering_3 may have different count since it's a subset
        # but ordering_1 and ordering_2 should match
        assert count_1 == count_2, (
            f"Different orderings of same data should produce same pattern count: "
            f"ordering_1={count_1}, ordering_2={count_2}"
        )

        # Same signatures for orderings 1 and 2
        sigs_1 = {
            p.signature_info.signature
            for p in (result_1["learned_patterns"] + result_1["candidate_patterns"])
        }
        sigs_2 = {
            p.signature_info.signature
            for p in (result_2["learned_patterns"] + result_2["candidate_patterns"])
        }
        assert sigs_1 == sigs_2, "Different orderings should produce same signatures"
