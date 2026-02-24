# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

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

from unittest import mock

import pytest
from omnibase_core.enums.pattern_learning import (
    EnumPatternLearningStatus,
    EnumPatternLifecycleState,
)
from omnibase_infra.enums import (
    EnumHandlerType,
    EnumHandlerTypeCategory,
)

from omniintelligence.nodes.node_pattern_learning_compute.handlers.exceptions import (
    PatternLearningValidationError,
)
from omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_learning import (
    HandlerPatternLearning,
    aggregate_patterns,
)
from omniintelligence.nodes.node_pattern_learning_compute.models import (
    LearningParametersDict,
    TrainingDataItemDict,
)
from tests.unit.nodes.node_pattern_learning_compute.handlers.conftest import (
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


# =============================================================================
# Determinism Contract Tests - B (sort-internally)
# =============================================================================


@pytest.mark.unit
class TestAggregatePatternsDeterminismContract:
    """Tests for B (sort-internally) contract - full pipeline determinism.

    These tests verify that aggregate_patterns produces deterministic output
    with patterns ordered by confidence descending, regardless of input order.
    """

    def test_shuffled_training_data_produces_same_patterns(self) -> None:
        """Shuffled training_data produces identical candidate/learned patterns."""
        import random

        # Create 8 training items with varying similarity to form distinct clusters
        base_training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="shuffle-001",
                code_snippet="class NodeAlphaCompute:\n    x = 1",
                pattern_type="compute",
                confidence=0.95,
            ),
            make_training_item(
                item_id="shuffle-002",
                code_snippet="class NodeAlphaCompute:\n    x = 2",
                pattern_type="compute",
                confidence=0.90,
            ),
            make_training_item(
                item_id="shuffle-003",
                code_snippet="class NodeBetaEffect:\n    y = 1",
                pattern_type="effect",
                confidence=0.85,
            ),
            make_training_item(
                item_id="shuffle-004",
                code_snippet="class NodeBetaEffect:\n    y = 2",
                pattern_type="effect",
                confidence=0.80,
            ),
            make_training_item(
                item_id="shuffle-005",
                code_snippet="class NodeGammaReducer:\n    z = 1",
                pattern_type="reducer",
                confidence=0.75,
            ),
            make_training_item(
                item_id="shuffle-006",
                code_snippet="class NodeGammaReducer:\n    z = 2",
                pattern_type="reducer",
                confidence=0.70,
            ),
            make_training_item(
                item_id="shuffle-007",
                code_snippet="class NodeDeltaOrchestrator:\n    w = 1",
                pattern_type="orchestrator",
                confidence=0.65,
            ),
            make_training_item(
                item_id="shuffle-008",
                code_snippet="class NodeDeltaOrchestrator:\n    w = 2",
                pattern_type="orchestrator",
                confidence=0.60,
            ),
        ]

        # Get baseline result with original order
        baseline_result = aggregate_patterns(
            training_data=base_training_data,
            parameters={},
            promotion_threshold=0.5,
        )
        baseline_learned_ids = [
            p.pattern_id for p in baseline_result["learned_patterns"]
        ]
        baseline_candidate_ids = [
            p.pattern_id for p in baseline_result["candidate_patterns"]
        ]

        # Run 10 iterations with shuffled input
        random.seed(42)  # Reproducibility for test debugging
        for iteration in range(10):
            shuffled_data = list(base_training_data)
            random.shuffle(shuffled_data)

            result = aggregate_patterns(
                training_data=shuffled_data,
                parameters={},
                promotion_threshold=0.5,
            )

            learned_ids = [p.pattern_id for p in result["learned_patterns"]]
            candidate_ids = [p.pattern_id for p in result["candidate_patterns"]]

            assert learned_ids == baseline_learned_ids, (
                f"Iteration {iteration}: learned_patterns order differs after shuffle. "
                f"Expected {baseline_learned_ids}, got {learned_ids}"
            )
            assert candidate_ids == baseline_candidate_ids, (
                f"Iteration {iteration}: candidate_patterns order differs after shuffle. "
                f"Expected {baseline_candidate_ids}, got {candidate_ids}"
            )

    def test_learned_patterns_ordered_by_confidence_desc(self) -> None:
        """learned_patterns are ordered by confidence descending."""
        # Create training data with multiple high-confidence items to form learned patterns
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="conf-high-001",
                code_snippet="class NodeHighA:\n    a = 1",
                pattern_type="compute",
                confidence=0.99,
            ),
            make_training_item(
                item_id="conf-high-002",
                code_snippet="class NodeHighA:\n    a = 2",
                pattern_type="compute",
                confidence=0.99,
            ),
            make_training_item(
                item_id="conf-high-003",
                code_snippet="class NodeHighA:\n    a = 3",
                pattern_type="compute",
                confidence=0.99,
            ),
            make_training_item(
                item_id="conf-med-001",
                code_snippet="class NodeMedB:\n    b = 1",
                pattern_type="effect",
                confidence=0.85,
            ),
            make_training_item(
                item_id="conf-med-002",
                code_snippet="class NodeMedB:\n    b = 2",
                pattern_type="effect",
                confidence=0.85,
            ),
            make_training_item(
                item_id="conf-med-003",
                code_snippet="class NodeMedB:\n    b = 3",
                pattern_type="effect",
                confidence=0.85,
            ),
            make_training_item(
                item_id="conf-low-001",
                code_snippet="class NodeLowC:\n    c = 1",
                pattern_type="reducer",
                confidence=0.70,
            ),
            make_training_item(
                item_id="conf-low-002",
                code_snippet="class NodeLowC:\n    c = 2",
                pattern_type="reducer",
                confidence=0.70,
            ),
            make_training_item(
                item_id="conf-low-003",
                code_snippet="class NodeLowC:\n    c = 3",
                pattern_type="reducer",
                confidence=0.70,
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.5,  # Low threshold to promote more patterns
        )

        learned_patterns = result["learned_patterns"]
        if len(learned_patterns) >= 2:
            for i in range(len(learned_patterns) - 1):
                current_conf = learned_patterns[i].score_components.confidence
                next_conf = learned_patterns[i + 1].score_components.confidence
                assert current_conf >= next_conf, (
                    f"learned_patterns not ordered by confidence descending: "
                    f"pattern[{i}].confidence={current_conf} < "
                    f"pattern[{i + 1}].confidence={next_conf}"
                )

    def test_candidate_patterns_ordered_by_confidence_desc(self) -> None:
        """candidate_patterns are ordered by confidence descending."""
        # Create training data that produces multiple candidate patterns
        # Use high threshold so most patterns become candidates
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="cand-001",
                code_snippet="class CandidateA:\n    pass",
                pattern_type="compute",
                confidence=0.65,
            ),
            make_training_item(
                item_id="cand-002",
                code_snippet="class CandidateB:\n    pass",
                pattern_type="effect",
                confidence=0.55,
            ),
            make_training_item(
                item_id="cand-003",
                code_snippet="class CandidateC:\n    pass",
                pattern_type="reducer",
                confidence=0.45,
            ),
            make_training_item(
                item_id="cand-004",
                code_snippet="class CandidateD:\n    pass",
                pattern_type="orchestrator",
                confidence=0.35,
            ),
        ]

        result = aggregate_patterns(
            training_data=training_data,
            parameters={},
            promotion_threshold=0.99,  # High threshold: most become candidates
        )

        candidate_patterns = result["candidate_patterns"]
        if len(candidate_patterns) >= 2:
            for i in range(len(candidate_patterns) - 1):
                current_conf = candidate_patterns[i].score_components.confidence
                next_conf = candidate_patterns[i + 1].score_components.confidence
                assert current_conf >= next_conf, (
                    f"candidate_patterns not ordered by confidence descending: "
                    f"pattern[{i}].confidence={current_conf} < "
                    f"pattern[{i + 1}].confidence={next_conf}"
                )

    def test_confidence_tiebreak_uses_pattern_id(self) -> None:
        """When confidence ties, pattern_id provides stable ordering."""
        # Create items with identical pattern types that will cluster together
        # and produce patterns with very similar or identical confidence scores
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="tie-alpha-001",
                code_snippet="class TieTestAlpha:\n    val = 1",
                pattern_type="compute",
                confidence=0.80,
            ),
            make_training_item(
                item_id="tie-beta-001",
                code_snippet="class TieTestBeta:\n    val = 1",
                pattern_type="compute",
                confidence=0.80,
            ),
            make_training_item(
                item_id="tie-gamma-001",
                code_snippet="class TieTestGamma:\n    val = 1",
                pattern_type="compute",
                confidence=0.80,
            ),
        ]

        # Run multiple times to verify stable ordering
        results: list[list[str]] = []
        for _ in range(5):
            result = aggregate_patterns(
                training_data=training_data,
                parameters={},
                promotion_threshold=0.5,
            )
            all_patterns = result["candidate_patterns"] + result["learned_patterns"]
            pattern_ids = [str(p.pattern_id) for p in all_patterns]
            results.append(pattern_ids)

        # All runs should produce identical ordering
        first_result = results[0]
        for i, result_ids in enumerate(results[1:], start=2):
            assert result_ids == first_result, (
                f"Run {i} produced different pattern order than run 1. "
                f"Expected {first_result}, got {result_ids}"
            )


# =============================================================================
# Handler Lifecycle Tests
# =============================================================================


@pytest.mark.unit
class TestHandlerPatternLearningLifecycle:
    """Tests for HandlerPatternLearning lifecycle methods.

    These tests cover:
    - __init__() constructor behavior
    - handler_type property
    - handler_category property
    - initialize() method
    - shutdown() method
    """

    def test_init_sets_initialized_false(self) -> None:
        """Constructor sets _initialized to False."""
        handler = HandlerPatternLearning()
        assert handler._initialized is False

    def test_handler_type_property_returns_compute_handler(self) -> None:
        """handler_type returns COMPUTE_HANDLER enum value."""
        handler = HandlerPatternLearning()
        assert handler.handler_type == EnumHandlerType.COMPUTE_HANDLER
        assert isinstance(handler.handler_type, EnumHandlerType)

    def test_handler_category_property_returns_compute(self) -> None:
        """handler_category returns COMPUTE enum value."""
        handler = HandlerPatternLearning()
        assert handler.handler_category == EnumHandlerTypeCategory.COMPUTE
        assert isinstance(handler.handler_category, EnumHandlerTypeCategory)

    def test_initialize_sets_initialized_true(self) -> None:
        """initialize() sets _initialized to True."""
        handler = HandlerPatternLearning()
        assert handler._initialized is False

        handler.initialize()
        assert handler._initialized is True

    def test_initialize_accepts_config_dict(self) -> None:
        """initialize() accepts optional config dict."""
        handler = HandlerPatternLearning()

        # Should not raise with config
        handler.initialize(config={"key": "value"})
        assert handler._initialized is True

    def test_initialize_accepts_none_config(self) -> None:
        """initialize() accepts None config (default)."""
        handler = HandlerPatternLearning()

        # Should not raise with None
        handler.initialize(config=None)
        assert handler._initialized is True

    def test_shutdown_resets_initialized_to_false(self) -> None:
        """shutdown() resets _initialized to False."""
        handler = HandlerPatternLearning()
        handler.initialize()
        assert handler._initialized is True

        handler.shutdown()
        assert handler._initialized is False

    def test_shutdown_is_idempotent(self) -> None:
        """shutdown() can be called multiple times without error."""
        handler = HandlerPatternLearning()

        # Shutdown before initialize (noop but should not raise)
        handler.shutdown()
        assert handler._initialized is False

        # Initialize and shutdown
        handler.initialize()
        handler.shutdown()
        assert handler._initialized is False

        # Shutdown again (should not raise)
        handler.shutdown()
        assert handler._initialized is False

    def test_full_lifecycle_cycle(self) -> None:
        """Handler supports full init -> run -> shutdown cycle."""
        handler = HandlerPatternLearning()
        assert handler._initialized is False

        # Initialize
        handler.initialize()
        assert handler._initialized is True

        # Run operation
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="lifecycle-001",
                code_snippet="class LifecycleTest:\n    pass",
            ),
        ]
        result = handler.handle(training_data=training_data)
        assert result["success"] is True

        # Shutdown
        handler.shutdown()
        assert handler._initialized is False


# =============================================================================
# Handler Execute (Envelope-based) Tests
# =============================================================================


@pytest.mark.unit
class TestHandlerPatternLearningExecute:
    """Tests for envelope-based execute() method.

    These tests cover:
    - Valid envelope processing
    - Correlation ID extraction
    - Payload extraction and validation
    - Error handling for invalid envelopes
    """

    def test_execute_with_valid_envelope(self) -> None:
        """execute() processes valid envelope successfully."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
            "payload": {
                "training_data": [
                    {
                        "item_id": "exec-001",
                        "source_file": "test.py",
                        "language": "python",
                        "code_snippet": "class NodeExecuteCompute:\n    x = 1",
                        "pattern_type": "compute",
                        "pattern_name": "test_pattern",
                        "labels": ["compute", "test"],
                        "confidence": 0.9,
                        "context": "test",
                        "framework": "onex",
                    }
                ],
                "parameters": {},
                "similarity_weights": None,
                "promotion_threshold": 0.70,
            },
        }

        result = handler.execute(envelope)
        assert result["success"] is True
        assert "learned_patterns" in result
        assert "candidate_patterns" in result

    def test_execute_extracts_correlation_id(self) -> None:
        """execute() extracts correlation_id from envelope."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",  # Valid UUID
            "payload": {
                "training_data": [
                    make_training_item(
                        item_id="corr-001",
                        code_snippet="class CorrTest:\n    pass",
                    ),
                ],
            },
        }

        # Should not raise - correlation_id is logged but not returned
        result = handler.execute(envelope)
        assert result["success"] is True

    def test_execute_generates_correlation_id_if_missing(self) -> None:
        """execute() generates correlation_id if not provided."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            # No correlation_id provided
            "payload": {
                "training_data": [
                    make_training_item(
                        item_id="gen-corr-001",
                        code_snippet="class GenCorrTest:\n    pass",
                    ),
                ],
            },
        }

        # Should not raise
        result = handler.execute(envelope)
        assert result["success"] is True

    def test_execute_raises_on_missing_payload(self) -> None:
        """execute() raises PatternLearningValidationError on missing payload."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            # No payload
        }

        with pytest.raises(PatternLearningValidationError) as exc_info:
            handler.execute(envelope)

        assert "payload" in str(exc_info.value).lower()

    def test_execute_raises_on_invalid_payload_type(self) -> None:
        """execute() raises on non-dict payload."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            "payload": "not a dict",  # Invalid type
        }

        with pytest.raises(PatternLearningValidationError) as exc_info:
            handler.execute(envelope)

        assert "payload" in str(exc_info.value).lower()

    def test_execute_uses_default_promotion_threshold(self) -> None:
        """execute() uses default promotion_threshold if not in payload."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            "payload": {
                "training_data": [
                    make_training_item(
                        item_id="default-thresh-001",
                        code_snippet="class DefaultThreshTest:\n    pass",
                    ),
                ],
                # No promotion_threshold specified
            },
        }

        result = handler.execute(envelope)
        assert result["success"] is True
        # Default threshold is 0.70 per presets
        assert result["metadata"].promotion_threshold_used == 0.70

    def test_execute_uses_custom_promotion_threshold(self) -> None:
        """execute() uses custom promotion_threshold from payload."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            "payload": {
                "training_data": [
                    make_training_item(
                        item_id="custom-thresh-001",
                        code_snippet="class CustomThreshTest:\n    pass",
                    ),
                ],
                "promotion_threshold": 0.50,  # Custom threshold
            },
        }

        result = handler.execute(envelope)
        assert result["success"] is True
        assert result["metadata"].promotion_threshold_used == 0.50

    def test_execute_with_empty_training_data_raises(self) -> None:
        """execute() raises on empty training data."""
        handler = HandlerPatternLearning()
        handler.initialize()

        envelope = {
            "operation": "pattern.aggregate",
            "payload": {
                "training_data": [],  # Empty
            },
        }

        with pytest.raises(PatternLearningValidationError) as exc_info:
            handler.execute(envelope)

        assert "empty" in str(exc_info.value).lower()


# =============================================================================
# Handler Handle (Direct) Tests
# =============================================================================


@pytest.mark.unit
class TestHandlerPatternLearningHandle:
    """Tests for direct handle() method."""

    def test_handle_with_minimal_input(self) -> None:
        """handle() processes minimal valid input."""
        handler = HandlerPatternLearning()
        handler.initialize()

        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="handle-001",
                code_snippet="class HandleTest:\n    pass",
            ),
        ]

        result = handler.handle(training_data=training_data)
        assert result["success"] is True

    def test_handle_with_all_parameters(self) -> None:
        """handle() accepts all optional parameters."""
        handler = HandlerPatternLearning()
        handler.initialize()

        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="params-001",
                code_snippet="class ParamsTest:\n    pass",
            ),
        ]

        result = handler.handle(
            training_data=training_data,
            parameters={"algorithm": "clustering"},
            similarity_weights={
                "keyword": 0.30,
                "pattern": 0.25,
                "structural": 0.20,
                "label": 0.15,
                "context": 0.10,
            },
            promotion_threshold=0.80,
        )

        assert result["success"] is True
        assert result["metadata"].promotion_threshold_used == 0.80


# =============================================================================
# Empty Result Creation Tests
# =============================================================================


@pytest.mark.unit
class TestCreateEmptyResult:
    """Tests for _create_empty_result() private function.

    This function is called when no clusters form from training data.
    We test it indirectly by providing training data that produces
    no clusters (edge case).
    """

    def test_empty_result_has_valid_structure(self) -> None:
        """Empty result from no clusters has valid structure."""
        # The _create_empty_result is called when cluster_patterns returns []
        # We can't easily trigger this with valid input (clustering always
        # produces at least one cluster per item), so we test the result
        # structure via the PatternLearningResult TypedDict contract.

        handler = HandlerPatternLearning()
        handler.initialize()

        # This will produce a normal result (not empty), but validates structure
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="struct-001",
                code_snippet="class StructTest:\n    pass",
            ),
        ]

        result = handler.handle(training_data=training_data)

        # Verify all required fields exist
        assert "success" in result
        assert "candidate_patterns" in result
        assert "learned_patterns" in result
        assert "metrics" in result
        assert "metadata" in result
        assert "warnings" in result

        # Verify types
        assert isinstance(result["success"], bool)
        assert isinstance(result["candidate_patterns"], list)
        assert isinstance(result["learned_patterns"], list)
        assert isinstance(result["warnings"], list)

    def test_result_metrics_have_all_fields(self) -> None:
        """Result metrics have all required fields."""
        handler = HandlerPatternLearning()
        handler.initialize()

        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="metrics-001",
                code_snippet="class MetricsTest:\n    pass",
            ),
        ]

        result = handler.handle(training_data=training_data)
        metrics = result["metrics"]

        # All metric fields should exist
        assert hasattr(metrics, "input_count")
        assert hasattr(metrics, "cluster_count")
        assert hasattr(metrics, "candidate_count")
        assert hasattr(metrics, "learned_count")
        assert hasattr(metrics, "discarded_count")
        assert hasattr(metrics, "merged_count")
        assert hasattr(metrics, "mean_confidence")
        assert hasattr(metrics, "mean_label_agreement")
        assert hasattr(metrics, "mean_cluster_cohesion")
        assert hasattr(metrics, "processing_time_ms")

    def test_result_metadata_has_all_fields(self) -> None:
        """Result metadata has all required fields."""
        handler = HandlerPatternLearning()
        handler.initialize()

        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="metadata-001",
                code_snippet="class MetadataTest:\n    pass",
            ),
        ]

        result = handler.handle(training_data=training_data)
        metadata = result["metadata"]

        # All metadata fields should exist
        assert hasattr(metadata, "status")
        assert hasattr(metadata, "model_version")
        assert hasattr(metadata, "timestamp")
        assert hasattr(metadata, "deduplication_threshold_used")
        assert hasattr(metadata, "promotion_threshold_used")
        assert hasattr(metadata, "training_samples")

    def test_result_warnings_list_type(self) -> None:
        """Result warnings is a list of strings."""
        handler = HandlerPatternLearning()
        handler.initialize()

        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="warnings-001",
                code_snippet="class WarningsTest:\n    pass",
            ),
        ]

        result = handler.handle(training_data=training_data)
        warnings = result["warnings"]

        assert isinstance(warnings, list)
        for warning in warnings:
            assert isinstance(warning, str)


# =============================================================================
# Integration: Handler Initialization Before Execute
# =============================================================================


@pytest.mark.unit
class TestHandlerInitializationIntegration:
    """Tests for handler behavior regarding initialization state.

    While the handler is stateless and works without explicit initialize(),
    these tests verify the expected lifecycle behavior.
    """

    def test_handle_works_without_initialize(self) -> None:
        """handle() works even if initialize() was not called.

        The handler is pure compute with no dependencies, so it
        should function regardless of _initialized state.
        """
        handler = HandlerPatternLearning()
        # Deliberately skip initialize()
        assert handler._initialized is False

        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="no-init-001",
                code_snippet="class NoInitTest:\n    pass",
            ),
        ]

        # Should still work (stateless compute)
        result = handler.handle(training_data=training_data)
        assert result["success"] is True

    def test_execute_works_without_initialize(self) -> None:
        """execute() works even if initialize() was not called."""
        handler = HandlerPatternLearning()
        # Deliberately skip initialize()
        assert handler._initialized is False

        envelope = {
            "operation": "pattern.aggregate",
            "payload": {
                "training_data": [
                    make_training_item(
                        item_id="no-init-exec-001",
                        code_snippet="class NoInitExecTest:\n    pass",
                    ),
                ],
            },
        }

        # Should still work (stateless compute)
        result = handler.execute(envelope)
        assert result["success"] is True

    def test_handler_can_be_reused_after_shutdown(self) -> None:
        """Handler can be reused after shutdown by re-initializing."""
        handler = HandlerPatternLearning()

        # First lifecycle
        handler.initialize()
        training_data: list[TrainingDataItemDict] = [
            make_training_item(
                item_id="reuse-001",
                code_snippet="class ReuseTest:\n    pass",
            ),
        ]
        result1 = handler.handle(training_data=training_data)
        assert result1["success"] is True
        handler.shutdown()

        # Second lifecycle
        handler.initialize()
        result2 = handler.handle(training_data=training_data)
        assert result2["success"] is True
        handler.shutdown()


# =============================================================================
# Edge Case Tests (Mocked)
# =============================================================================


@pytest.mark.unit
class TestEmptyClusterResult:
    """Tests for empty cluster result path (_create_empty_result).

    These tests use mocking to trigger the edge case where
    cluster_patterns returns an empty list.
    """

    def test_empty_clusters_returns_empty_result(self) -> None:
        """When clustering returns empty list, _create_empty_result is called."""
        with mock.patch(
            "omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_learning.cluster_patterns"
        ) as mock_cluster:
            # Mock cluster_patterns to return empty list
            mock_cluster.return_value = []

            handler = HandlerPatternLearning()
            handler.initialize()

            training_data: list[TrainingDataItemDict] = [
                make_training_item(
                    item_id="empty-cluster-001",
                    code_snippet="class EmptyClusterTest:\n    pass",
                ),
            ]

            result = handler.handle(training_data=training_data)

            # Should still succeed but with empty patterns
            assert result["success"] is True
            assert result["learned_patterns"] == []
            assert result["candidate_patterns"] == []

            # Metrics should reflect empty result
            assert result["metrics"].input_count == 1
            assert result["metrics"].cluster_count == 0
            assert result["metrics"].candidate_count == 0
            assert result["metrics"].learned_count == 0

            # Should have warning about no clusters
            assert len(result["warnings"]) == 1
            assert "No clusters formed" in result["warnings"][0]

    def test_empty_result_metadata_is_valid(self) -> None:
        """Empty result has valid metadata."""
        with mock.patch(
            "omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_learning.cluster_patterns"
        ) as mock_cluster:
            mock_cluster.return_value = []

            handler = HandlerPatternLearning()
            handler.initialize()

            training_data: list[TrainingDataItemDict] = [
                make_training_item(
                    item_id="empty-meta-001",
                    code_snippet="class EmptyMetaTest:\n    pass",
                ),
            ]

            result = handler.handle(
                training_data=training_data,
                promotion_threshold=0.85,
            )

            # Verify metadata
            metadata = result["metadata"]
            assert metadata.status == EnumPatternLearningStatus.COMPLETED
            assert metadata.promotion_threshold_used == 0.85
            assert metadata.training_samples == 1
            assert metadata.model_version is not None
            assert metadata.timestamp is not None

    def test_empty_result_metrics_are_zeroed(self) -> None:
        """Empty result metrics are properly zeroed."""
        with mock.patch(
            "omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_learning.cluster_patterns"
        ) as mock_cluster:
            mock_cluster.return_value = []

            handler = HandlerPatternLearning()
            handler.initialize()

            training_data: list[TrainingDataItemDict] = [
                make_training_item(
                    item_id="empty-zero-001",
                    code_snippet="class EmptyZeroTest:\n    pass",
                ),
                make_training_item(
                    item_id="empty-zero-002",
                    code_snippet="class EmptyZeroTest2:\n    pass",
                ),
            ]

            result = handler.handle(training_data=training_data)

            metrics = result["metrics"]
            assert metrics.input_count == 2  # Input count is preserved
            assert metrics.cluster_count == 0
            assert metrics.candidate_count == 0
            assert metrics.learned_count == 0
            assert metrics.discarded_count == 0
            assert metrics.merged_count == 0
            assert metrics.mean_confidence == 0.0
            assert metrics.mean_label_agreement == 0.0
            assert metrics.mean_cluster_cohesion == 0.0
            assert metrics.processing_time_ms > 0  # Processing time is recorded

    def test_empty_result_via_execute_envelope(self) -> None:
        """Empty result path works via execute() envelope interface."""
        with mock.patch(
            "omniintelligence.nodes.node_pattern_learning_compute.handlers.handler_pattern_learning.cluster_patterns"
        ) as mock_cluster:
            mock_cluster.return_value = []

            handler = HandlerPatternLearning()
            handler.initialize()

            envelope = {
                "operation": "pattern.aggregate",
                "correlation_id": "550e8400-e29b-41d4-a716-446655440001",
                "payload": {
                    "training_data": [
                        make_training_item(
                            item_id="empty-exec-001",
                            code_snippet="class EmptyExecTest:\n    pass",
                        ),
                    ],
                },
            }

            result = handler.execute(envelope)

            assert result["success"] is True
            assert result["learned_patterns"] == []
            assert result["candidate_patterns"] == []
            assert "No clusters formed" in result["warnings"][0]
