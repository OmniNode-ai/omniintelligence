# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for NodeScoringReducerCompute (OMN-2545).

Tests cover:
  - Gate-fail path: any single gate failure returns failed result
  - Gate-pass path: all gates passing returns correct ScoreVector
  - Mixed shaped terms: maximize and minimize directions
  - Attribution refs: non-empty when shaped terms contribute
  - Replay invariant: identical inputs → bit-identical outputs
  - ScoreVector.zero(): all-passing gates with no shaped terms
  - Property-based matrix: gate failures dominate shaped term values
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_scoring_reducer_compute.handlers.handler_scoring import (
    evaluate_run,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_gate_type import (
    EnumGateType,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evidence_bundle import (
    ModelEvidenceBundle,
    ModelEvidenceItem,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
    ModelGateSpec,
    ModelObjectiveSpec,
    ModelShapedTermSpec,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_score_vector import (
    ModelScoreVector,
)

# =============================================================================
# Helpers / fixtures
# =============================================================================


def _make_item(item_id: str, source: str, value: float) -> ModelEvidenceItem:
    return ModelEvidenceItem(item_id=item_id, source=source, value=value)


def _make_bundle(run_id: str, items: list[ModelEvidenceItem]) -> ModelEvidenceBundle:
    t = tuple(items)
    fingerprint = ModelEvidenceBundle.fingerprint(t)
    return ModelEvidenceBundle(
        run_id=run_id,
        bundle_fingerprint=fingerprint,
        items=t,
        collected_at_utc="2026-02-24T00:00:00Z",
    )


def _threshold_gate(
    gate_id: str, evidence_source: str, threshold: float
) -> ModelGateSpec:
    return ModelGateSpec(
        id=gate_id,
        gate_type=EnumGateType.THRESHOLD,
        threshold=threshold,
        evidence_source=evidence_source,
    )


def _shaped_term(
    term_id: str,
    evidence_source: str,
    direction: str,
    score_dimension: str,
    weight: float = 1.0,
) -> ModelShapedTermSpec:
    return ModelShapedTermSpec(
        id=term_id,
        weight=weight,
        direction=direction,  # type: ignore[arg-type]
        evidence_source=evidence_source,
        score_dimension=score_dimension,
    )


def _make_spec(
    gates: list[ModelGateSpec] | None = None,
    shaped_terms: list[ModelShapedTermSpec] | None = None,
    objective_id: str = "test-objective",
) -> ModelObjectiveSpec:
    return ModelObjectiveSpec(
        objective_id=objective_id,
        version="1.0.0",
        gates=tuple(gates or []),
        shaped_terms=tuple(shaped_terms or []),
    )


# =============================================================================
# Tests: ScoreVector.zero()
# =============================================================================


@pytest.mark.unit
class TestScoreVectorZero:
    def test_zero_returns_all_zeros(self) -> None:
        z = ModelScoreVector.zero()
        assert z.correctness == 0.0
        assert z.safety == 0.0
        assert z.cost == 0.0
        assert z.latency == 0.0
        assert z.maintainability == 0.0
        assert z.human_time == 0.0

    def test_zero_is_frozen(self) -> None:
        from pydantic import ValidationError

        z = ModelScoreVector.zero()
        with pytest.raises(ValidationError):
            z.correctness = 1.0


# =============================================================================
# Tests: Gate-fail path
# =============================================================================


@pytest.mark.unit
class TestGateFailPath:
    def test_single_gate_failure_returns_failed(self) -> None:
        """Any gate failure → passed=False, ScoreVector.zero(), failures non-empty."""
        bundle = _make_bundle(
            "run-001",
            [_make_item("i1", "test_result", 0.3)],  # below threshold
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is False
        assert result.score_vector == ModelScoreVector.zero()
        assert "g1" in result.failures
        assert result.attribution_refs == ()

    def test_first_gate_fails_others_also_checked(self) -> None:
        """All failing gates are collected, not just the first."""
        bundle = _make_bundle(
            "run-002",
            [
                _make_item("i1", "test_result", 0.1),
                _make_item("i2", "lint_result", 0.2),
            ],
        )
        spec = _make_spec(
            gates=[
                _threshold_gate("g1", "test_result", 0.5),
                _threshold_gate("g2", "lint_result", 0.5),
            ],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is False
        assert "g1" in result.failures
        assert "g2" in result.failures

    def test_gate_failure_ignores_shaped_terms(self) -> None:
        """Even high shaped term values cannot rescue a gate failure."""
        bundle = _make_bundle(
            "run-003",
            [
                _make_item("i1", "test_result", 0.1),  # gate fails
                _make_item("i2", "coverage_report", 0.99),  # shaped term
            ],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "coverage_report", "maximize", "correctness")
            ],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is False
        assert result.score_vector == ModelScoreVector.zero()

    def test_missing_evidence_counts_as_gate_failure(self) -> None:
        """A gate referencing missing evidence source → gate fails."""
        bundle = _make_bundle("run-004", [])  # empty evidence
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.0)],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is False
        assert "g1" in result.failures


# =============================================================================
# Tests: Gate-pass path
# =============================================================================


@pytest.mark.unit
class TestGatePassPath:
    def test_all_gates_pass_no_shaped_terms(self) -> None:
        """All gates pass + no shaped terms → passed=True, ScoreVector.zero()."""
        bundle = _make_bundle(
            "run-010",
            [_make_item("i1", "test_result", 0.9)],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert result.score_vector == ModelScoreVector.zero()
        assert result.failures == ()

    def test_no_gates_no_terms_passes(self) -> None:
        """Spec with no gates and no terms → trivially passes."""
        bundle = _make_bundle("run-011", [])
        spec = _make_spec()
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert result.score_vector == ModelScoreVector.zero()

    def test_threshold_gate_at_exact_boundary_passes(self) -> None:
        """Evidence value == threshold → gate passes (>= semantics)."""
        bundle = _make_bundle(
            "run-012",
            [_make_item("i1", "test_result", 0.5)],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
        )
        result = evaluate_run(bundle, spec)
        assert result.passed is True

    def test_threshold_gate_just_below_fails(self) -> None:
        """Evidence value just below threshold → gate fails."""
        bundle = _make_bundle(
            "run-013",
            [_make_item("i1", "test_result", 0.4999)],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
        )
        result = evaluate_run(bundle, spec)
        assert result.passed is False


# =============================================================================
# Tests: Shaped reward terms
# =============================================================================


@pytest.mark.unit
class TestShapedRewardTerms:
    def test_maximize_direction_contributes_raw_value(self) -> None:
        """maximize: evidence value contributes directly to ScoreVector."""
        bundle = _make_bundle(
            "run-020",
            [
                _make_item("i1", "test_result", 1.0),  # gate
                _make_item("i2", "coverage_report", 0.8),
            ],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "coverage_report", "maximize", "correctness")
            ],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert abs(result.score_vector.correctness - 0.8) < 1e-6

    def test_minimize_direction_inverts_value(self) -> None:
        """minimize: evidence value is inverted (1.0 - value)."""
        bundle = _make_bundle(
            "run-021",
            [
                _make_item("i1", "test_result", 1.0),  # gate
                _make_item("i2", "cost_measurement", 0.3),  # cost=0.3 → inverted=0.7
            ],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[_shaped_term("t1", "cost_measurement", "minimize", "cost")],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert abs(result.score_vector.cost - 0.7) < 1e-6

    def test_weighted_terms_sum_correctly(self) -> None:
        """Two weighted maximize terms sum to expected weighted total."""
        bundle = _make_bundle(
            "run-022",
            [
                _make_item("i1", "test_result", 1.0),
                _make_item("i2", "lint_result", 0.6),
                _make_item("i3", "coverage_report", 0.8),
            ],
        )
        # Two terms for correctness dimension with weights summing to 1.0
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term(
                    "t1", "lint_result", "maximize", "correctness", weight=0.4
                ),
                _shaped_term(
                    "t2", "coverage_report", "maximize", "correctness", weight=0.6
                ),
            ],
        )
        result = evaluate_run(bundle, spec)

        # 0.4 * 0.6 + 0.6 * 0.8 = 0.24 + 0.48 = 0.72
        assert result.passed is True
        assert abs(result.score_vector.correctness - 0.72) < 1e-6

    def test_attribution_refs_non_empty_on_contribution(self) -> None:
        """Attribution refs include item_ids that contributed to ScoreVector."""
        bundle = _make_bundle(
            "run-023",
            [
                _make_item("i1", "test_result", 1.0),
                _make_item("i2", "coverage_report", 0.9),
            ],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "coverage_report", "maximize", "correctness")
            ],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert "i2" in result.attribution_refs

    def test_missing_shaped_term_evidence_contributes_zero(self) -> None:
        """Missing evidence for a shaped term → 0 contribution, no error."""
        bundle = _make_bundle(
            "run-024",
            [_make_item("i1", "test_result", 1.0)],  # gate evidence only
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "coverage_report", "maximize", "correctness")
            ],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert result.score_vector.correctness == 0.0
        assert result.attribution_refs == ()

    def test_multiple_score_dimensions(self) -> None:
        """Shaped terms for different dimensions fill correct ScoreVector fields."""
        bundle = _make_bundle(
            "run-025",
            [
                _make_item("i1", "test_result", 1.0),
                _make_item("i2", "lint_result", 0.9),
                _make_item("i3", "benchmark_result", 0.5),
            ],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "lint_result", "maximize", "safety"),
                _shaped_term("t2", "benchmark_result", "minimize", "latency"),
            ],
        )
        result = evaluate_run(bundle, spec)

        assert result.passed is True
        assert abs(result.score_vector.safety - 0.9) < 1e-6
        assert abs(result.score_vector.latency - 0.5) < 1e-6  # 1.0 - 0.5 = 0.5
        assert result.score_vector.correctness == 0.0  # no term for correctness


# =============================================================================
# Tests: Replay invariant
# =============================================================================


@pytest.mark.unit
class TestReplayInvariant:
    def test_identical_inputs_produce_identical_outputs(self) -> None:
        """Calling evaluate_run twice with identical args returns bit-identical results."""
        items = (
            _make_item("i1", "test_result", 0.9),
            _make_item("i2", "coverage_report", 0.75),
        )
        bundle = _make_bundle("run-replay", list(items))
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "coverage_report", "maximize", "correctness")
            ],
        )

        result1 = evaluate_run(bundle, spec)
        result2 = evaluate_run(bundle, spec)

        assert result1 == result2
        assert result1.score_vector == result2.score_vector
        assert result1.attribution_refs == result2.attribution_refs

    def test_replay_invariant_with_gate_failure(self) -> None:
        """Replay invariant holds for gate-failure path."""
        bundle = _make_bundle(
            "run-replay-fail",
            [_make_item("i1", "test_result", 0.1)],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
        )

        result1 = evaluate_run(bundle, spec)
        result2 = evaluate_run(bundle, spec)

        assert result1 == result2
        assert result1.failures == result2.failures


# =============================================================================
# Tests: Property-based matrix (gates dominate)
# =============================================================================


@pytest.mark.unit
class TestGatesDominateMatrix:
    """Matrix tests verifying that gate failures always dominate shaped terms."""

    @pytest.mark.parametrize(
        "gate_value,shaped_value,should_pass",
        [
            (0.0, 1.0, False),  # gate fails, high shaped → still fail
            (0.1, 0.99, False),  # gate fails, very high shaped → still fail
            (0.49, 0.99, False),  # just below threshold → fail
            (0.5, 0.0, True),  # gate passes, zero shaped → pass
            (0.5, 1.0, True),  # gate passes, max shaped → pass
            (1.0, 0.5, True),  # perfect gate, mid shaped → pass
        ],
    )
    def test_gate_dominance(
        self, gate_value: float, shaped_value: float, should_pass: bool
    ) -> None:
        bundle = _make_bundle(
            f"run-matrix-{gate_value}-{shaped_value}",
            [
                _make_item("i1", "test_result", gate_value),
                _make_item("i2", "coverage_report", shaped_value),
            ],
        )
        spec = _make_spec(
            gates=[_threshold_gate("g1", "test_result", 0.5)],
            shaped_terms=[
                _shaped_term("t1", "coverage_report", "maximize", "correctness")
            ],
        )
        result = evaluate_run(bundle, spec)
        assert result.passed is should_pass
        if not should_pass:
            assert result.score_vector == ModelScoreVector.zero()


# =============================================================================
# Tests: EvidenceBundle fingerprint
# =============================================================================


@pytest.mark.unit
class TestEvidenceBundleFingerprint:
    def test_same_items_produce_same_fingerprint(self) -> None:
        items1 = (
            _make_item("a", "test_result", 0.8),
            _make_item("b", "lint_result", 0.9),
        )
        items2 = (
            _make_item("a", "test_result", 0.8),
            _make_item("b", "lint_result", 0.9),
        )
        assert ModelEvidenceBundle.fingerprint(
            items1
        ) == ModelEvidenceBundle.fingerprint(items2)

    def test_different_values_produce_different_fingerprint(self) -> None:
        items1 = (_make_item("a", "test_result", 0.8),)
        items2 = (_make_item("a", "test_result", 0.9),)
        assert ModelEvidenceBundle.fingerprint(
            items1
        ) != ModelEvidenceBundle.fingerprint(items2)

    def test_different_order_produces_different_fingerprint(self) -> None:
        items1 = (
            _make_item("a", "test_result", 0.8),
            _make_item("b", "lint_result", 0.9),
        )
        items2 = (
            _make_item("b", "lint_result", 0.9),
            _make_item("a", "test_result", 0.8),
        )
        # Order matters — different order → different fingerprint
        assert ModelEvidenceBundle.fingerprint(
            items1
        ) != ModelEvidenceBundle.fingerprint(items2)

    def test_fingerprint_is_64_char_hex(self) -> None:
        items = (_make_item("a", "test_result", 0.5),)
        fp = ModelEvidenceBundle.fingerprint(items)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)
