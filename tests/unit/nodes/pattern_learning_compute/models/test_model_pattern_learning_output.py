# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ModelPatternLearningOutput.from_patterns() factory method.

This module tests the factory method that splits patterns by lifecycle_state:
    - VALIDATED patterns go to learned_patterns
    - All other states (CANDIDATE, PROVISIONAL, DEPRECATED) go to candidate_patterns
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

import pytest

# Namespace for generating deterministic UUIDs from test IDs
TEST_NAMESPACE = UUID("12345678-1234-5678-1234-567812345678")

from omnibase_core.enums.pattern_learning import (
    EnumPatternLifecycleState,
    EnumPatternType,
)
from omnibase_core.models.pattern_learning import (
    ModelLearnedPattern,
    ModelPatternLearningMetadata,
    ModelPatternLearningMetrics,
    ModelPatternScoreComponents,
    ModelPatternSignature,
)
from omnibase_core.models.primitives.model_semver import ModelSemVer

from omniintelligence.nodes.pattern_learning_compute.models import (
    ModelPatternLearningOutput,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_score_components() -> ModelPatternScoreComponents:
    """Create sample score components for test patterns."""
    return ModelPatternScoreComponents(
        label_agreement=0.85,
        cluster_cohesion=0.90,
        frequency_factor=0.75,
        confidence=0.88,
    )


@pytest.fixture
def sample_signature_info() -> ModelPatternSignature:
    """Create sample signature info for test patterns."""
    return ModelPatternSignature(
        signature="sha256:abc123def456",
        signature_version=ModelSemVer(major=1, minor=0, patch=0),
        signature_inputs=["keywords", "pattern_type", "category"],
        normalization_applied="lowercase_sort_dedupe",
    )


@pytest.fixture
def sample_metrics() -> ModelPatternLearningMetrics:
    """Create sample metrics for output model."""
    return ModelPatternLearningMetrics(
        input_count=100,
        cluster_count=15,
        candidate_count=10,
        learned_count=5,
        discarded_count=3,
        merged_count=2,
        mean_confidence=0.82,
        mean_label_agreement=0.88,
        mean_cluster_cohesion=0.85,
        processing_time_ms=1250.5,
    )


@pytest.fixture
def sample_metadata() -> ModelPatternLearningMetadata:
    """Create sample metadata for output model."""
    return ModelPatternLearningMetadata(
        status="completed",
        model_version=ModelSemVer(major=1, minor=0, patch=0),
        timestamp=datetime.now(timezone.utc),
        deduplication_threshold_used=0.85,
        promotion_threshold_used=0.70,
        training_samples=80,
        validation_samples=20,
        convergence_achieved=True,
        early_stopped=False,
        final_epoch=10,
    )


def make_test_uuid(name: str) -> UUID:
    """Generate a deterministic UUID from a test name for reproducible tests."""
    return uuid5(TEST_NAMESPACE, name)


def create_pattern(
    pattern_name_id: str,
    lifecycle_state: EnumPatternLifecycleState,
    score_components: ModelPatternScoreComponents,
    signature_info: ModelPatternSignature,
) -> ModelLearnedPattern:
    """Helper to create a ModelLearnedPattern with the given lifecycle_state.

    Args:
        pattern_name_id: A human-readable ID used to generate a deterministic UUID.
        lifecycle_state: The lifecycle state for the pattern.
        score_components: Score components for the pattern.
        signature_info: Signature info for the pattern.

    Returns:
        A ModelLearnedPattern with a deterministic UUID based on pattern_name_id.
    """
    now = datetime.now(timezone.utc)
    pattern_uuid = make_test_uuid(pattern_name_id)
    return ModelLearnedPattern(
        pattern_id=pattern_uuid,
        pattern_name=f"test_pattern_{pattern_name_id}",
        pattern_type=EnumPatternType.CODE_PATTERN,
        category="testing",
        subcategory="unit_test",
        tags=["test", "fixture"],
        keywords=["pattern", "learning"],
        score_components=score_components,
        signature_info=signature_info,
        lifecycle_state=lifecycle_state,
        source_count=5,
        first_seen=now,
        last_seen=now,
    )


# =============================================================================
# Tests for from_patterns() Factory Method
# =============================================================================


@pytest.mark.unit
class TestFromPatternsFactoryMethod:
    """Tests for ModelPatternLearningOutput.from_patterns() class method."""

    def test_from_patterns_splits_by_lifecycle_state(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Verify VALIDATED patterns go to learned_patterns, others to candidate_patterns."""
        # Arrange: Create patterns with different lifecycle states
        validated_pattern = create_pattern(
            "p1",
            EnumPatternLifecycleState.VALIDATED,
            sample_score_components,
            sample_signature_info,
        )
        candidate_pattern = create_pattern(
            "p2",
            EnumPatternLifecycleState.CANDIDATE,
            sample_score_components,
            sample_signature_info,
        )
        provisional_pattern = create_pattern(
            "p3",
            EnumPatternLifecycleState.PROVISIONAL,
            sample_score_components,
            sample_signature_info,
        )
        deprecated_pattern = create_pattern(
            "p4",
            EnumPatternLifecycleState.DEPRECATED,
            sample_score_components,
            sample_signature_info,
        )

        all_patterns = [
            validated_pattern,
            candidate_pattern,
            provisional_pattern,
            deprecated_pattern,
        ]

        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=all_patterns,
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        # Assert
        assert len(result.learned_patterns) == 1
        assert result.learned_patterns[0].pattern_id == make_test_uuid("p1")
        assert result.learned_patterns[0].lifecycle_state == EnumPatternLifecycleState.VALIDATED

        assert len(result.candidate_patterns) == 3
        candidate_ids = {p.pattern_id for p in result.candidate_patterns}
        expected_ids = {make_test_uuid("p2"), make_test_uuid("p3"), make_test_uuid("p4")}
        assert candidate_ids == expected_ids

        # Verify all candidate patterns have non-VALIDATED lifecycle states
        for pattern in result.candidate_patterns:
            assert pattern.lifecycle_state != EnumPatternLifecycleState.VALIDATED

    def test_from_patterns_empty_list(
        self,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Empty input returns empty lists for both pattern categories."""
        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        # Assert
        assert result.learned_patterns == []
        assert result.candidate_patterns == []
        assert result.success is True

    def test_from_patterns_all_validated(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """All patterns are VALIDATED -> all in learned_patterns, none in candidate_patterns."""
        # Arrange
        patterns = [
            create_pattern(
                f"p{i}",
                EnumPatternLifecycleState.VALIDATED,
                sample_score_components,
                sample_signature_info,
            )
            for i in range(3)
        ]

        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=patterns,
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        # Assert
        assert len(result.learned_patterns) == 3
        assert len(result.candidate_patterns) == 0

        for pattern in result.learned_patterns:
            assert pattern.lifecycle_state == EnumPatternLifecycleState.VALIDATED

    def test_from_patterns_no_validated(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """No VALIDATED patterns -> all in candidate_patterns, none in learned_patterns."""
        # Arrange: Create patterns with all non-VALIDATED states
        patterns = [
            create_pattern(
                "p1",
                EnumPatternLifecycleState.CANDIDATE,
                sample_score_components,
                sample_signature_info,
            ),
            create_pattern(
                "p2",
                EnumPatternLifecycleState.PROVISIONAL,
                sample_score_components,
                sample_signature_info,
            ),
            create_pattern(
                "p3",
                EnumPatternLifecycleState.DEPRECATED,
                sample_score_components,
                sample_signature_info,
            ),
        ]

        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=patterns,
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        # Assert
        assert len(result.learned_patterns) == 0
        assert len(result.candidate_patterns) == 3

        for pattern in result.candidate_patterns:
            assert pattern.lifecycle_state != EnumPatternLifecycleState.VALIDATED

    def test_from_patterns_with_warnings(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Warnings are passed through correctly."""
        # Arrange
        pattern = create_pattern(
            "p1",
            EnumPatternLifecycleState.VALIDATED,
            sample_score_components,
            sample_signature_info,
        )
        warnings = [
            "Low confidence on pattern p1",
            "Possible duplicate detected",
        ]

        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[pattern],
            metrics=sample_metrics,
            metadata=sample_metadata,
            warnings=warnings,
        )

        # Assert
        assert result.warnings == warnings
        assert len(result.warnings) == 2
        assert "Low confidence on pattern p1" in result.warnings
        assert "Possible duplicate detected" in result.warnings

    def test_from_patterns_with_none_warnings(
        self,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """None warnings defaults to empty list."""
        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[],
            metrics=sample_metrics,
            metadata=sample_metadata,
            warnings=None,
        )

        # Assert
        assert result.warnings == []

    def test_from_patterns_success_always_true(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Factory always sets success=True regardless of input."""
        # Test with empty patterns
        result_empty = ModelPatternLearningOutput.from_patterns(
            all_patterns=[],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )
        assert result_empty.success is True

        # Test with validated patterns
        pattern = create_pattern(
            "p1",
            EnumPatternLifecycleState.VALIDATED,
            sample_score_components,
            sample_signature_info,
        )
        result_with_pattern = ModelPatternLearningOutput.from_patterns(
            all_patterns=[pattern],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )
        assert result_with_pattern.success is True

        # Test with only candidate patterns
        candidate = create_pattern(
            "p2",
            EnumPatternLifecycleState.CANDIDATE,
            sample_score_components,
            sample_signature_info,
        )
        result_candidates = ModelPatternLearningOutput.from_patterns(
            all_patterns=[candidate],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )
        assert result_candidates.success is True

    def test_from_patterns_preserves_metrics_and_metadata(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Metrics and metadata are passed through unchanged."""
        # Arrange
        pattern = create_pattern(
            "p1",
            EnumPatternLifecycleState.VALIDATED,
            sample_score_components,
            sample_signature_info,
        )

        # Act
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[pattern],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        # Assert - verify metrics are preserved
        assert result.metrics.input_count == sample_metrics.input_count
        assert result.metrics.cluster_count == sample_metrics.cluster_count
        assert result.metrics.mean_confidence == sample_metrics.mean_confidence

        # Assert - verify metadata is preserved
        assert result.metadata.status == sample_metadata.status
        assert result.metadata.model_version == sample_metadata.model_version
        assert result.metadata.convergence_achieved == sample_metadata.convergence_achieved


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.unit
class TestFromPatternsEdgeCases:
    """Edge case tests for from_patterns() factory method."""

    def test_from_patterns_single_validated_pattern(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Single VALIDATED pattern goes to learned_patterns."""
        pattern = create_pattern(
            "single",
            EnumPatternLifecycleState.VALIDATED,
            sample_score_components,
            sample_signature_info,
        )

        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[pattern],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        assert len(result.learned_patterns) == 1
        assert len(result.candidate_patterns) == 0
        assert result.learned_patterns[0].pattern_id == make_test_uuid("single")

    def test_from_patterns_single_candidate_pattern(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Single CANDIDATE pattern goes to candidate_patterns."""
        pattern = create_pattern(
            "single",
            EnumPatternLifecycleState.CANDIDATE,
            sample_score_components,
            sample_signature_info,
        )

        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[pattern],
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        assert len(result.learned_patterns) == 0
        assert len(result.candidate_patterns) == 1
        assert result.candidate_patterns[0].pattern_id == make_test_uuid("single")

    def test_from_patterns_large_pattern_list(
        self,
        sample_score_components: ModelPatternScoreComponents,
        sample_signature_info: ModelPatternSignature,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Factory handles large lists correctly."""
        # Create 50 validated and 50 non-validated patterns
        validated_patterns = [
            create_pattern(
                f"validated_{i}",
                EnumPatternLifecycleState.VALIDATED,
                sample_score_components,
                sample_signature_info,
            )
            for i in range(50)
        ]
        candidate_patterns = [
            create_pattern(
                f"candidate_{i}",
                EnumPatternLifecycleState.CANDIDATE,
                sample_score_components,
                sample_signature_info,
            )
            for i in range(50)
        ]

        all_patterns = validated_patterns + candidate_patterns

        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=all_patterns,
            metrics=sample_metrics,
            metadata=sample_metadata,
        )

        assert len(result.learned_patterns) == 50
        assert len(result.candidate_patterns) == 50

    def test_from_patterns_empty_warnings_list(
        self,
        sample_metrics: ModelPatternLearningMetrics,
        sample_metadata: ModelPatternLearningMetadata,
    ) -> None:
        """Explicit empty warnings list is preserved."""
        result = ModelPatternLearningOutput.from_patterns(
            all_patterns=[],
            metrics=sample_metrics,
            metadata=sample_metadata,
            warnings=[],
        )

        assert result.warnings == []
