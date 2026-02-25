# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ObjectiveABFrameworkCompute (OMN-2571).

Tests cover:
  - Traffic splitting determinism (same run_id → same variant)
  - Divergence detection (passed mismatch, score delta)
  - Statistical significance / upgrade-ready signal
  - Shadow variant never drives policy state
  - run_ab_evaluation end-to-end
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_objective_ab_framework_compute.handlers.handler_ab_framework import (
    check_upgrade_ready,
    compute_score_delta,
    detect_divergence,
    route_to_variant,
    run_ab_evaluation,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.enum_variant_role import (
    EnumVariantRole,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_input import (
    ModelABEvaluationInput,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_output import (
    ModelVariantEvaluationResult,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariant,
    ModelObjectiveVariantRegistry,
)

# =============================================================================
# Helpers
# =============================================================================


def _variant(
    variant_id: str,
    role: EnumVariantRole = EnumVariantRole.ACTIVE,
    weight: float = 1.0,
    version: str = "1.0.0",
) -> ModelObjectiveVariant:
    return ModelObjectiveVariant(
        variant_id=variant_id,
        objective_id="test-objective",
        objective_version=version,
        role=role,
        traffic_weight=weight,
    )


def _registry(
    variants: list[ModelObjectiveVariant],
    significance_threshold: float = 0.05,
    min_runs: int = 10,
    divergence_threshold: float = 0.1,
) -> ModelObjectiveVariantRegistry:
    return ModelObjectiveVariantRegistry(
        registry_id="test-registry",
        variants=tuple(variants),
        significance_threshold=significance_threshold,
        min_runs_for_significance=min_runs,
        divergence_threshold=divergence_threshold,
    )


def _result(
    variant_id: str,
    role: EnumVariantRole = EnumVariantRole.ACTIVE,
    passed: bool = True,
    correctness: float = 0.5,
    safety: float = 0.5,
) -> ModelVariantEvaluationResult:
    return ModelVariantEvaluationResult(
        variant_id=variant_id,
        objective_id="obj",
        objective_version="1.0",
        role=role,
        passed=passed,
        score_correctness=correctness,
        score_safety=safety,
        score_cost=0.5,
        score_latency=0.5,
        score_maintainability=0.5,
        score_human_time=0.5,
        drives_policy_state=(role == EnumVariantRole.ACTIVE),
    )


# =============================================================================
# Tests: Traffic splitting determinism
# =============================================================================


@pytest.mark.unit
class TestTrafficSplitting:
    def test_same_run_id_always_routes_same_variant(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE, weight=0.9),
                _variant("v2", EnumVariantRole.SHADOW, weight=0.1),
            ]
        )
        route1 = route_to_variant("run-abc-123", reg)
        route2 = route_to_variant("run-abc-123", reg)
        assert route1.variant_id == route2.variant_id

    def test_different_run_ids_may_route_differently(self) -> None:
        """Not guaranteed, but different run_ids should produce different routes."""
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE, weight=0.5),
                _variant("v2", EnumVariantRole.SHADOW, weight=0.5),
            ]
        )
        # With 50/50 split and many run_ids, some should route to v2
        routes = set()
        for i in range(100):
            v = route_to_variant(f"run-{i:04d}", reg)
            routes.add(v.variant_id)

        assert len(routes) == 2  # Both variants got traffic

    def test_100_percent_active_always_routes_to_active(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE, weight=1.0),
            ]
        )
        for i in range(20):
            v = route_to_variant(f"run-{i}", reg)
            assert v.variant_id == "v1"

    def test_routing_is_consistent_across_calls(self) -> None:
        """Same run_id, same registry → same result every time."""
        reg = _registry(
            [
                _variant("active", EnumVariantRole.ACTIVE, weight=0.7),
                _variant("shadow", EnumVariantRole.SHADOW, weight=0.3),
            ]
        )
        results = [route_to_variant("stable-run-id", reg).variant_id for _ in range(10)]
        assert len(set(results)) == 1  # All same


# =============================================================================
# Tests: Divergence detection
# =============================================================================


@pytest.mark.unit
class TestDivergenceDetection:
    def test_no_divergence_when_identical(self) -> None:
        r1 = _result("v1", EnumVariantRole.ACTIVE, passed=True, correctness=0.8)
        r2 = _result("v2", EnumVariantRole.SHADOW, passed=True, correctness=0.8)
        assert detect_divergence(r1, r2, threshold=0.1) is False

    def test_divergence_when_passed_mismatch(self) -> None:
        r1 = _result("v1", EnumVariantRole.ACTIVE, passed=True)
        r2 = _result("v2", EnumVariantRole.SHADOW, passed=False)
        assert detect_divergence(r1, r2, threshold=0.1) is True

    def test_divergence_when_score_delta_exceeds_threshold(self) -> None:
        r1 = _result("v1", EnumVariantRole.ACTIVE, correctness=0.9, safety=0.9)
        r2 = _result("v2", EnumVariantRole.SHADOW, correctness=0.3, safety=0.3)
        delta = compute_score_delta(r1, r2)
        assert delta > 0.1
        assert detect_divergence(r1, r2, threshold=0.1) is True

    def test_no_divergence_when_delta_below_threshold(self) -> None:
        r1 = _result("v1", EnumVariantRole.ACTIVE, correctness=0.5)
        r2 = _result("v2", EnumVariantRole.SHADOW, correctness=0.51)
        delta = compute_score_delta(r1, r2)
        assert delta < 0.1
        assert detect_divergence(r1, r2, threshold=0.1) is False


# =============================================================================
# Tests: Score delta computation
# =============================================================================


@pytest.mark.unit
class TestScoreDelta:
    def test_identical_scores_produce_zero_delta(self) -> None:
        r1 = _result("v1", correctness=0.7)
        r2 = _result("v2", correctness=0.7)
        assert compute_score_delta(r1, r2) < 1e-9

    def test_max_possible_delta(self) -> None:
        """Max delta: all zeros vs all ones = sqrt(6)."""
        r1 = ModelVariantEvaluationResult(
            variant_id="v1",
            objective_id="o",
            objective_version="1",
            role=EnumVariantRole.ACTIVE,
            passed=True,
            score_correctness=0.0,
            score_safety=0.0,
            score_cost=0.0,
            score_latency=0.0,
            score_maintainability=0.0,
            score_human_time=0.0,
            drives_policy_state=True,
        )
        r2 = ModelVariantEvaluationResult(
            variant_id="v2",
            objective_id="o",
            objective_version="2",
            role=EnumVariantRole.SHADOW,
            passed=True,
            score_correctness=1.0,
            score_safety=1.0,
            score_cost=1.0,
            score_latency=1.0,
            score_maintainability=1.0,
            score_human_time=1.0,
            drives_policy_state=False,
        )
        import math

        assert abs(compute_score_delta(r1, r2) - math.sqrt(6)) < 1e-6


# =============================================================================
# Tests: Upgrade-ready signal
# =============================================================================


@pytest.mark.unit
class TestUpgradeReady:
    def test_not_ready_below_min_runs(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE),
                _variant("v2", EnumVariantRole.SHADOW),
            ],
            min_runs=100,
            significance_threshold=0.05,
        )
        result = check_upgrade_ready("v2", run_count=50, shadow_wins=49, registry=reg)
        assert result is False

    def test_ready_when_significance_threshold_met(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE),
                _variant("v2", EnumVariantRole.SHADOW),
            ],
            min_runs=10,
            significance_threshold=0.05,  # need win_rate >= 0.95
        )
        result = check_upgrade_ready("v2", run_count=100, shadow_wins=96, registry=reg)
        assert result is True

    def test_not_ready_when_win_rate_low(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE),
                _variant("v2", EnumVariantRole.SHADOW),
            ],
            min_runs=10,
            significance_threshold=0.05,
        )
        result = check_upgrade_ready("v2", run_count=100, shadow_wins=50, registry=reg)
        assert result is False

    def test_exact_threshold_boundary(self) -> None:
        """Win rate exactly at threshold → ready."""
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE),
                _variant("v2", EnumVariantRole.SHADOW),
            ],
            min_runs=10,
            significance_threshold=0.1,  # need win_rate >= 0.9
        )
        # 90/100 = 0.9 exactly
        result = check_upgrade_ready("v2", run_count=100, shadow_wins=90, registry=reg)
        assert result is True


# =============================================================================
# Tests: run_ab_evaluation end-to-end
# =============================================================================


@pytest.mark.unit
class TestRunABEvaluation:
    def test_both_variants_evaluated(self) -> None:
        reg = _registry(
            [
                _variant("active", EnumVariantRole.ACTIVE, weight=0.9),
                _variant("shadow", EnumVariantRole.SHADOW, weight=0.1),
            ]
        )
        inp = ModelABEvaluationInput(
            run_id="run-001",
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
        )
        output = run_ab_evaluation(inp)
        assert len(output.variant_results) == 2

    def test_active_variant_drives_policy_state(self) -> None:
        reg = _registry(
            [
                _variant("active", EnumVariantRole.ACTIVE, weight=0.9),
                _variant("shadow", EnumVariantRole.SHADOW, weight=0.1),
            ]
        )
        inp = ModelABEvaluationInput(
            run_id="run-002",
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
        )
        output = run_ab_evaluation(inp)
        active_results = [
            r for r in output.variant_results if r.role == EnumVariantRole.ACTIVE
        ]
        shadow_results = [
            r for r in output.variant_results if r.role == EnumVariantRole.SHADOW
        ]
        assert all(r.drives_policy_state for r in active_results)
        assert all(not r.drives_policy_state for r in shadow_results)

    def test_upgrade_ready_signal_when_significant(self) -> None:
        """Upgrade signal fires when shadow has sufficient wins."""
        reg = _registry(
            [
                _variant("active", EnumVariantRole.ACTIVE, weight=0.9),
                _variant("shadow", EnumVariantRole.SHADOW, weight=0.1),
            ],
            min_runs=10,
            significance_threshold=0.1,
        )
        inp = ModelABEvaluationInput(
            run_id="run-003",
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
            run_count_by_variant={"shadow": 100},
            shadow_win_count_by_variant={"shadow": 95},  # 95% win rate > 90%
        )
        output = run_ab_evaluation(inp)
        assert output.upgrade_ready is True
        assert output.upgrade_ready_variant_id == "shadow"

    def test_no_upgrade_ready_below_significance(self) -> None:
        reg = _registry(
            [
                _variant("active", EnumVariantRole.ACTIVE, weight=0.9),
                _variant("shadow", EnumVariantRole.SHADOW, weight=0.1),
            ],
            min_runs=100,
            significance_threshold=0.05,
        )
        inp = ModelABEvaluationInput(
            run_id="run-004",
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
            run_count_by_variant={"shadow": 50},  # below min_runs=100
            shadow_win_count_by_variant={"shadow": 48},
        )
        output = run_ab_evaluation(inp)
        assert output.upgrade_ready is False

    def test_single_active_variant_no_divergence(self) -> None:
        """Single active variant: no divergence possible."""
        reg = _registry([_variant("active", EnumVariantRole.ACTIVE, weight=1.0)])
        inp = ModelABEvaluationInput(
            run_id="run-005",
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
        )
        output = run_ab_evaluation(inp)
        assert output.divergence_detected is False
        assert len(output.variant_results) == 1

    @pytest.mark.parametrize(
        "run_id",
        [
            "run-aaa",
            "run-bbb",
            "run-ccc",
            "run-xyz-999",
        ],
    )
    def test_deterministic_routing_per_run_id(self, run_id: str) -> None:
        """Each run_id routes deterministically across repeated calls."""
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE, weight=0.5),
                _variant("v2", EnumVariantRole.SHADOW, weight=0.5),
            ]
        )
        inp = ModelABEvaluationInput(
            run_id=run_id,
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
        )
        # Two evaluations should produce identical routing
        out1 = run_ab_evaluation(inp)
        out2 = run_ab_evaluation(inp)
        assert out1.variant_results == out2.variant_results


# =============================================================================
# Tests: ObjectiveVariantRegistry validation
# =============================================================================


@pytest.mark.unit
class TestRegistryValidation:
    def test_registry_requires_exactly_one_active(self) -> None:
        """Registry with no active variant should raise."""
        with pytest.raises(ValidationError):
            _registry(
                [
                    _variant("v1", EnumVariantRole.SHADOW, weight=0.5),
                    _variant("v2", EnumVariantRole.SHADOW, weight=0.5),
                ]
            )

    def test_registry_with_one_active_is_valid(self) -> None:
        reg = _registry([_variant("v1", EnumVariantRole.ACTIVE, weight=1.0)])
        assert reg.registry_id == "test-registry"

    def test_registry_with_active_and_shadow_is_valid(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE, weight=0.9),
                _variant("v2", EnumVariantRole.SHADOW, weight=0.1),
            ]
        )
        assert len(reg.variants) == 2
