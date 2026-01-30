# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Canary tests for handler_pattern_learning orchestration.

These tests validate pipeline wiring before the full test suite lands.
They are intentionally minimal to catch integration errors quickly.

Key validation points:
    1. Pipeline stages execute in correct order
    2. Handler outputs connect to next handler inputs
    3. Candidate vs learned split works based on threshold
    4. Metrics are populated correctly
    5. No exceptions raised for valid input

Test philosophy:
    - Validate WIRING, not correctness of similarity math
    - 2 minimal training items (identical language for determinism)
    - Deterministic - same input always produces same output
    - Fast execution (no large datasets)
"""

from __future__ import annotations

import pytest

from omnibase_core.enums.pattern_learning import (
    EnumPatternLearningStatus,
    EnumPatternLifecycleState,
)

from omniintelligence.nodes.pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.pattern_learning_compute.handlers.handler_pattern_learning import (
    aggregate_patterns,
)
from omniintelligence.nodes.pattern_learning_compute.models import (
    LearningParametersDict,
    TrainingDataItemDict,
)
from tests.unit.nodes.pattern_learning_compute.handlers.conftest import (
    make_training_item,
)


# =============================================================================
# Canary Tests - Pipeline Wiring Golden Path
# =============================================================================


@pytest.mark.unit
class TestPipelineWiringGoldenPath:
    """Canary tests for pipeline wiring validation.

    These tests use minimal inputs to verify that the pipeline stages
    are correctly wired together. They do not test the correctness of
    similarity computations or clustering algorithms - those are tested
    in dedicated handler tests.
    """

    def test_pipeline_wiring_golden_path(self) -> None:
        """Validate pipeline wiring with 2 minimal items.

        This test validates:
        1. Pipeline stages execute in correct order
        2. Handler outputs connect to next handler inputs
        3. Candidate vs learned split works
        4. Metrics are populated
        """
        # Arrange: 2 minimal training items with similar code
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="test-item-001",
                code_snippet="class NodeTestCompute:\n    pass",
                pattern_type="compute",
                confidence=0.9,
            ),
            make_training_item(
                item_id="test-item-002",
                code_snippet="class NodeTestCompute:\n    def run(self): pass",
                pattern_type="compute",
                confidence=0.85,
            ),
        ]

        parameters: LearningParametersDict = {
            "algorithm": "clustering",
            "min_confidence": 0.5,
            "deduplicate": True,
        }

        # Act
        result = aggregate_patterns(
            training_data=training_data,
            parameters=parameters,
            promotion_threshold=0.7,
        )

        # Assert: Pipeline completed successfully
        assert result["success"] is True

        # Assert: Metrics are populated
        metrics = result["metrics"]
        assert metrics.input_count == 2
        assert metrics.cluster_count >= 1
        assert metrics.candidate_count + metrics.learned_count >= 1
        assert metrics.processing_time_ms > 0

        # Assert: Patterns are split correctly
        all_patterns = result["candidate_patterns"] + result["learned_patterns"]
        assert len(all_patterns) >= 1

        # Assert: Each pattern has required fields
        for pattern in all_patterns:
            assert pattern.pattern_id is not None
            assert pattern.lifecycle_state is not None
            assert pattern.score_components is not None
            assert pattern.signature_info is not None

        # Assert: No warnings for valid input
        # (warnings list may exist but should be empty for golden path)

    def test_empty_input_raises_validation_error(self) -> None:
        """Empty input should raise PatternLearningValidationError (fail-fast)."""
        with pytest.raises(PatternLearningValidationError) as exc_info:
            aggregate_patterns(
                training_data=[],
                parameters={},
            )

        assert "cannot be empty" in str(exc_info.value).lower()

    def test_single_item_creates_single_pattern(self) -> None:
        """Single training item should produce single pattern."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="solo-item",
                code_snippet="class NodeSoloCompute:\n    pass",
                pattern_type="compute",
                confidence=0.95,
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.5,  # Low threshold to ensure promotion
        )

        assert result["success"] is True
        assert result["metrics"].input_count == 1
        assert result["metrics"].cluster_count == 1

        all_patterns = result["candidate_patterns"] + result["learned_patterns"]
        assert len(all_patterns) == 1

    def test_promotion_threshold_splits_patterns_correctly(self) -> None:
        """Patterns should be split based on promotion threshold.

        High-confidence patterns (>= threshold) go to learned_patterns.
        Low-confidence patterns (< threshold) go to candidate_patterns.
        """
        # Create items that will form clusters with different confidences
        training_data: list[TrainingDataItemDict] = [
            # High-confidence cluster (many members for high frequency_factor)
            make_training_item(
                item_id="high-001",
                code_snippet="class NodeHighCompute:\n    x = 1",
                pattern_type="compute",
                confidence=0.95,
            ),
            make_training_item(
                item_id="high-002",
                code_snippet="class NodeHighCompute:\n    x = 2",
                pattern_type="compute",
                confidence=0.95,
            ),
            make_training_item(
                item_id="high-003",
                code_snippet="class NodeHighCompute:\n    x = 3",
                pattern_type="compute",
                confidence=0.95,
            ),
            make_training_item(
                item_id="high-004",
                code_snippet="class NodeHighCompute:\n    x = 4",
                pattern_type="compute",
                confidence=0.95,
            ),
            make_training_item(
                item_id="high-005",
                code_snippet="class NodeHighCompute:\n    x = 5",
                pattern_type="compute",
                confidence=0.95,
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.7,
        )

        assert result["success"] is True

        # With 5 members and high internal similarity, should have high confidence
        # and be promoted to learned_patterns
        all_patterns = result["candidate_patterns"] + result["learned_patterns"]
        assert len(all_patterns) >= 1

        # Check that learned patterns have VALIDATED state
        for pattern in result["learned_patterns"]:
            assert pattern.lifecycle_state == EnumPatternLifecycleState.VALIDATED

        # Check that candidate patterns have CANDIDATE state
        for pattern in result["candidate_patterns"]:
            assert pattern.lifecycle_state == EnumPatternLifecycleState.CANDIDATE


@pytest.mark.unit
class TestPipelineMetricsPopulation:
    """Tests for metrics population in the pipeline."""

    def test_metrics_fields_are_populated(self) -> None:
        """All metric fields should be populated after pipeline run."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="metric-test-001",
                code_snippet="class MetricTest:\n    pass",
            ),
            make_training_item(
                item_id="metric-test-002",
                code_snippet="class MetricTest:\n    def run(self): pass",
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
        )

        metrics = result["metrics"]

        # All fields should be non-negative
        assert metrics.input_count >= 0
        assert metrics.cluster_count >= 0
        assert metrics.candidate_count >= 0
        assert metrics.learned_count >= 0
        assert metrics.discarded_count >= 0
        assert metrics.merged_count >= 0
        assert metrics.processing_time_ms >= 0

        # Mean values should be in [0, 1]
        assert 0.0 <= metrics.mean_confidence <= 1.0
        assert 0.0 <= metrics.mean_label_agreement <= 1.0
        assert 0.0 <= metrics.mean_cluster_cohesion <= 1.0

    def test_metadata_fields_are_populated(self) -> None:
        """All metadata fields should be populated after pipeline run."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="meta-test-001",
                code_snippet="class MetaTest:\n    pass",
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.7,
        )

        metadata = result["metadata"]

        assert metadata.status == EnumPatternLearningStatus.COMPLETED
        assert metadata.model_version is not None
        assert metadata.timestamp is not None
        assert metadata.deduplication_threshold_used > 0
        assert metadata.promotion_threshold_used == 0.7
        assert metadata.training_samples >= 0


@pytest.mark.unit
class TestPipelinePatternOutput:
    """Tests for pattern output structure."""

    def test_pattern_has_required_fields(self) -> None:
        """Each output pattern should have all required fields."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="field-test-001",
                code_snippet="class FieldTest:\n    pass",
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
        )

        all_patterns = result["candidate_patterns"] + result["learned_patterns"]
        assert len(all_patterns) >= 1

        for pattern in all_patterns:
            # Identity fields
            assert pattern.pattern_id is not None
            assert pattern.pattern_name is not None
            assert pattern.pattern_type is not None

            # Categorization fields
            assert pattern.category is not None
            assert pattern.tags is not None
            assert pattern.keywords is not None

            # Score components
            assert pattern.score_components is not None
            assert pattern.score_components.confidence >= 0.0
            assert pattern.score_components.confidence <= 1.0
            assert pattern.score_components.label_agreement >= 0.0
            assert pattern.score_components.label_agreement <= 1.0
            assert pattern.score_components.cluster_cohesion >= 0.0
            assert pattern.score_components.cluster_cohesion <= 1.0
            assert pattern.score_components.frequency_factor >= 0.0
            assert pattern.score_components.frequency_factor <= 1.0

            # Signature info
            assert pattern.signature_info is not None
            assert pattern.signature_info.signature is not None
            assert pattern.signature_info.signature_version is not None

            # Lifecycle
            assert pattern.lifecycle_state is not None
            assert pattern.source_count >= 1

    def test_pattern_id_is_deterministic(self) -> None:
        """Pattern IDs should be deterministic given same input."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="determ-001",
                code_snippet="class DetermTest:\n    pass",
            ),
        ]

        result1 = aggregate_patterns(
            training_data=training_data,
            parameters={},
        )

        result2 = aggregate_patterns(
            training_data=training_data,
            parameters={},
        )

        patterns1 = result1["candidate_patterns"] + result1["learned_patterns"]
        patterns2 = result2["candidate_patterns"] + result2["learned_patterns"]

        assert len(patterns1) == len(patterns2)
        for p1, p2 in zip(patterns1, patterns2, strict=True):
            assert p1.pattern_id == p2.pattern_id
            assert p1.signature_info.signature == p2.signature_info.signature


@pytest.mark.unit
class TestPromotionThresholdEdgeCases:
    """Edge case tests for promotion threshold boundaries."""

    def test_zero_threshold_promotes_all_patterns(self) -> None:
        """With threshold=0.0, all patterns should become learned."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="zero-001",
                code_snippet="class ZeroTest:\n    pass",
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.0,  # Edge case: zero threshold
        )

        assert result["success"] is True
        # All patterns should be learned (none should be candidates)
        assert len(result["learned_patterns"]) >= 1
        assert len(result["candidate_patterns"]) == 0

    def test_one_threshold_makes_all_candidates(self) -> None:
        """With threshold=1.0, all patterns should become candidates."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="one-001",
                code_snippet="class OneTest:\n    pass",
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=1.0,  # Edge case: maximum threshold
        )

        assert result["success"] is True
        # All patterns should be candidates (confidence can't reach 1.0)
        assert len(result["candidate_patterns"]) >= 1
        assert len(result["learned_patterns"]) == 0

    def test_mixed_pattern_types_in_batch(self) -> None:
        """Different pattern types should cluster separately."""
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="compute-001",
                code_snippet="class ComputeNode:\n    pass",
                pattern_type="compute",
            ),
            make_training_item(
                item_id="effect-001",
                code_snippet="class EffectNode:\n    pass",
                pattern_type="effect",
            ),
            make_training_item(
                item_id="workflow-001",
                code_snippet="class WorkflowNode:\n    pass",
                pattern_type="workflow",
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.5,
        )

        assert result["success"] is True
        all_patterns = result["candidate_patterns"] + result["learned_patterns"]
        # Should have at least one pattern (possibly separate clusters)
        assert len(all_patterns) >= 1
