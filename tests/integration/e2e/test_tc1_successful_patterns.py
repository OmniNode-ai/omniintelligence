# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""TC1: E2E integration tests for successful session pattern extraction.

This test case verifies that the pattern learning pipeline correctly extracts
patterns with positive confidence from successful coding sessions.

Test Scenario:
    - Input: 5 training data items from successful sessions (code generation,
      refactoring, test generation, API endpoints, configuration)
    - Expected: Patterns extracted with confidence >= 0.5
    - Expected: Patterns have correct structure (domain, signature, etc.)

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
    - fixtures.py: sample_successful_session_data() fixture
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.integration.e2e.fixtures import sample_successful_session_data

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
        HandlerPatternLearning,
    )


# =============================================================================
# Constants
# =============================================================================

# Minimum confidence threshold for successful patterns
MIN_CONFIDENCE_THRESHOLD: float = 0.5

# Minimum expected patterns from successful session data
MIN_EXPECTED_PATTERNS: int = 1


# =============================================================================
# TC1: Successful Session Pattern Extraction Tests
# =============================================================================


@pytest.mark.integration
class TestTC1SuccessfulPatternExtraction:
    """Test class for TC1: successful session pattern extraction.

    Verifies that the pattern learning pipeline:
    1. Successfully processes training data from successful sessions
    2. Extracts patterns with positive confidence (>= 0.5)
    3. Produces patterns with correct structure
    """

    def test_successful_session_extracts_patterns(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that successful session data produces extracted patterns.

        This is the main test case for TC1, verifying that the pattern learning
        pipeline can process training data from successful coding sessions and
        produce learned/candidate patterns.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange: Get successful session training data
        training_data = sample_successful_session_data()
        assert len(training_data) == 5, "Expected 5 training data items"

        # Act: Run pattern learning pipeline
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert: Pipeline succeeded
        assert result["success"] is True, (
            f"Pattern learning should succeed for valid training data. "
            f"Warnings: {result['warnings']}"
        )

        # Assert: At least some patterns were extracted
        total_patterns = len(result["learned_patterns"]) + len(result["candidate_patterns"])
        assert total_patterns >= MIN_EXPECTED_PATTERNS, (
            f"Expected at least {MIN_EXPECTED_PATTERNS} patterns, "
            f"got {total_patterns} (learned={len(result['learned_patterns'])}, "
            f"candidates={len(result['candidate_patterns'])})"
        )

        # Assert: Metrics are populated
        assert result["metrics"] is not None, "Metrics should be populated"
        assert result["metrics"].input_count == 5, (
            f"Expected input_count=5, got {result['metrics'].input_count}"
        )

    def test_pattern_confidence_is_positive(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that extracted patterns have positive confidence.

        Verifies the confidence scoring of patterns from successful sessions:
        - All patterns have confidence > 0 (non-zero)
        - Learned patterns (if any) have confidence >= promotion threshold
        - Mean confidence is positive

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange
        training_data = sample_successful_session_data()

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert: Pipeline succeeded
        assert result["success"] is True

        # Collect all patterns
        all_patterns = list(result["learned_patterns"]) + list(result["candidate_patterns"])
        assert len(all_patterns) >= MIN_EXPECTED_PATTERNS, (
            "Should have at least one pattern to verify confidence"
        )

        # Assert: All patterns have positive (> 0) confidence
        for pattern in all_patterns:
            confidence = pattern.score_components.confidence
            assert confidence > 0, (
                f"Pattern '{pattern.pattern_name}' has confidence {confidence:.3f}, "
                f"expected > 0 (positive confidence)"
            )

        # Assert: Learned patterns have confidence >= threshold (default 0.7)
        for pattern in result["learned_patterns"]:
            confidence = pattern.score_components.confidence
            assert confidence >= MIN_CONFIDENCE_THRESHOLD, (
                f"Learned pattern '{pattern.pattern_name}' has confidence {confidence:.3f}, "
                f"expected >= {MIN_CONFIDENCE_THRESHOLD} for learned patterns"
            )

        # Assert: Mean confidence from metrics is positive
        assert result["metrics"].mean_confidence > 0, (
            f"Mean confidence {result['metrics'].mean_confidence:.3f} should be > 0"
        )

    def test_pattern_has_required_fields(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that extracted patterns have all required structural fields.

        Verifies that patterns from the learning pipeline have:
        - pattern_id (UUID)
        - pattern_name (non-empty string)
        - pattern_type (valid enum)
        - category (non-empty string)
        - signature_info with valid signature
        - score_components with confidence
        - lifecycle_state

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange
        training_data = sample_successful_session_data()

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert: Pipeline succeeded
        assert result["success"] is True

        # Collect all patterns
        all_patterns = list(result["learned_patterns"]) + list(result["candidate_patterns"])
        assert len(all_patterns) >= MIN_EXPECTED_PATTERNS, (
            "Should have at least one pattern to verify structure"
        )

        # Assert: Each pattern has required fields
        for pattern in all_patterns:
            # Identity fields
            assert pattern.pattern_id is not None, "pattern_id should not be None"
            assert pattern.pattern_name, "pattern_name should not be empty"

            # Type classification
            assert pattern.pattern_type is not None, "pattern_type should not be None"
            assert pattern.category, "category should not be empty"

            # Signature info
            assert pattern.signature_info is not None, (
                "signature_info should not be None"
            )
            assert pattern.signature_info.signature, (
                f"Pattern '{pattern.pattern_name}' should have non-empty signature"
            )
            assert pattern.signature_info.signature_version is not None, (
                "signature_version should not be None"
            )

            # Score components
            assert pattern.score_components is not None, (
                "score_components should not be None"
            )
            assert 0.0 <= pattern.score_components.confidence <= 1.0, (
                f"Confidence {pattern.score_components.confidence} should be in [0, 1]"
            )
            assert 0.0 <= pattern.score_components.label_agreement <= 1.0, (
                f"label_agreement should be in [0, 1]"
            )
            assert 0.0 <= pattern.score_components.cluster_cohesion <= 1.0, (
                f"cluster_cohesion should be in [0, 1]"
            )

            # Lifecycle state
            assert pattern.lifecycle_state is not None, (
                "lifecycle_state should not be None"
            )

            # Source tracking
            assert pattern.source_count >= 1, (
                f"source_count should be >= 1, got {pattern.source_count}"
            )

            # Timestamps
            assert pattern.first_seen is not None, "first_seen should not be None"
            assert pattern.last_seen is not None, "last_seen should not be None"

    def test_learned_patterns_are_validated(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that learned_patterns have lifecycle_state=VALIDATED.

        Verifies the lifecycle state assignment for patterns that meet
        the promotion threshold.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        from omnibase_core.enums.pattern_learning import EnumPatternLifecycleState

        # Arrange
        training_data = sample_successful_session_data()

        # Act: Use lower threshold to ensure some patterns are promoted
        result = pattern_learning_handler.handle(
            training_data=training_data,
            promotion_threshold=0.5,  # Lower threshold to promote more patterns
        )

        # Assert: Pipeline succeeded
        assert result["success"] is True

        # Assert: All learned_patterns have VALIDATED state
        for pattern in result["learned_patterns"]:
            assert pattern.lifecycle_state == EnumPatternLifecycleState.VALIDATED, (
                f"Pattern '{pattern.pattern_name}' in learned_patterns should have "
                f"lifecycle_state=VALIDATED, got {pattern.lifecycle_state}"
            )

    def test_candidate_patterns_are_not_validated(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that candidate_patterns do NOT have lifecycle_state=VALIDATED.

        Verifies the lifecycle state assignment for patterns below the
        promotion threshold.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        from omnibase_core.enums.pattern_learning import EnumPatternLifecycleState

        # Arrange
        training_data = sample_successful_session_data()

        # Act: Use very high threshold to ensure patterns are candidates
        result = pattern_learning_handler.handle(
            training_data=training_data,
            promotion_threshold=0.99,  # Very high threshold
        )

        # Assert: Pipeline succeeded
        assert result["success"] is True

        # Assert: All candidate_patterns are NOT VALIDATED
        for pattern in result["candidate_patterns"]:
            assert pattern.lifecycle_state != EnumPatternLifecycleState.VALIDATED, (
                f"Pattern '{pattern.pattern_name}' in candidate_patterns should NOT have "
                f"lifecycle_state=VALIDATED, got {pattern.lifecycle_state}"
            )

    def test_metadata_contains_processing_info(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that metadata contains processing information.

        Verifies that the returned metadata includes:
        - status
        - model_version
        - timestamp
        - promotion_threshold_used
        - training_samples count

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        from omnibase_core.enums.pattern_learning import EnumPatternLearningStatus

        # Arrange
        training_data = sample_successful_session_data()

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert: Pipeline succeeded
        assert result["success"] is True

        # Assert: Metadata is populated
        metadata = result["metadata"]
        assert metadata is not None, "metadata should not be None"

        # Check status
        assert metadata.status == EnumPatternLearningStatus.COMPLETED, (
            f"Expected status=COMPLETED, got {metadata.status}"
        )

        # Check model version
        assert metadata.model_version is not None, (
            "model_version should not be None"
        )

        # Check timestamp
        assert metadata.timestamp is not None, "timestamp should not be None"

        # Check threshold tracking
        assert 0.0 <= metadata.promotion_threshold_used <= 1.0, (
            f"promotion_threshold_used should be in [0, 1], "
            f"got {metadata.promotion_threshold_used}"
        )

        # Check training samples count
        assert metadata.training_samples == 5, (
            f"Expected training_samples=5, got {metadata.training_samples}"
        )


# =============================================================================
# Additional Verification Tests
# =============================================================================


@pytest.mark.integration
class TestTC1MetricsVerification:
    """Additional tests for verifying metrics from successful sessions."""

    def test_metrics_input_count_matches_training_data(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that metrics.input_count matches the training data count.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange
        training_data = sample_successful_session_data()
        expected_count = len(training_data)

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert
        assert result["success"] is True
        assert result["metrics"].input_count == expected_count, (
            f"Expected input_count={expected_count}, "
            f"got {result['metrics'].input_count}"
        )

    def test_metrics_cluster_count_is_positive(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that metrics.cluster_count is positive for valid training data.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange
        training_data = sample_successful_session_data()

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert
        assert result["success"] is True
        assert result["metrics"].cluster_count >= 1, (
            f"Expected cluster_count >= 1, got {result['metrics'].cluster_count}"
        )

    def test_metrics_processing_time_is_positive(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that processing time is tracked and positive.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange
        training_data = sample_successful_session_data()

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert
        assert result["success"] is True
        assert result["metrics"].processing_time_ms > 0, (
            f"Expected processing_time_ms > 0, "
            f"got {result['metrics'].processing_time_ms}"
        )


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.integration
class TestTC1EdgeCases:
    """Edge case tests for successful session pattern extraction."""

    def test_single_item_training_data(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test pattern learning with a single training item.

        Verifies that the pipeline handles minimal input gracefully.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange: Use just first item
        training_data = sample_successful_session_data()[:1]
        assert len(training_data) == 1

        # Act
        result = pattern_learning_handler.handle(training_data=training_data)

        # Assert: Should succeed even with single item
        assert result["success"] is True
        assert result["metrics"].input_count == 1

    def test_high_threshold_produces_fewer_learned(
        self,
        pattern_learning_handler: HandlerPatternLearning,
    ) -> None:
        """Test that higher thresholds produce fewer learned patterns.

        Verifies threshold behavior by comparing low vs high threshold results.

        Args:
            pattern_learning_handler: Initialized pattern learning handler fixture.
        """
        # Arrange
        training_data = sample_successful_session_data()

        # Act with low threshold
        result_low = pattern_learning_handler.handle(
            training_data=training_data,
            promotion_threshold=0.3,
        )

        # Act with high threshold
        result_high = pattern_learning_handler.handle(
            training_data=training_data,
            promotion_threshold=0.9,
        )

        # Assert: Both should succeed
        assert result_low["success"] is True
        assert result_high["success"] is True

        # Assert: High threshold should have fewer or equal learned patterns
        assert len(result_high["learned_patterns"]) <= len(result_low["learned_patterns"]), (
            f"High threshold ({len(result_high['learned_patterns'])}) should produce "
            f"fewer or equal learned patterns than low threshold "
            f"({len(result_low['learned_patterns'])})"
        )
