# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ObjectiveABFrameworkCompute (OMN-2571).

Tests cover:
  - Traffic splitting determinism (same run_id → same variant)
  - Divergence detection (passed mismatch, score delta)
  - Statistical significance / upgrade-ready signal
  - Shadow variant never drives policy state
  - HandlerRunAbEvaluation end-to-end
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_objective_ab_framework_compute.handlers import (
    handler_ab_framework as handler_module,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.handlers.handler_ab_framework import (
    compute_score_delta,
    detect_divergence,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.enum_variant_role import (
    EnumVariantRole,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_input import (
    ModelABEvaluationInput,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_output import (
    ModelABEvaluationOutput,
    ModelVariantEvaluationResult,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_check_upgrade_ready_request import (
    ModelCheckUpgradeReadyRequest,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariant,
    ModelObjectiveVariantRegistry,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_route_to_variant_request import (
    ModelRouteToVariantRequest,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_upgrade_ready_response import (
    ModelUpgradeReadyResponse,
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
        route1 = handler_module.HandlerRouteToVariant().handle(
            ModelRouteToVariantRequest(run_id="run-abc-123", registry=reg)
        )
        route2 = handler_module.HandlerRouteToVariant().handle(
            ModelRouteToVariantRequest(run_id="run-abc-123", registry=reg)
        )
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
            v = handler_module.HandlerRouteToVariant().handle(
                ModelRouteToVariantRequest(run_id=f"run-{i:04d}", registry=reg)
            )
            routes.add(v.variant_id)

        assert len(routes) == 2  # Both variants got traffic

    def test_100_percent_active_always_routes_to_active(self) -> None:
        reg = _registry(
            [
                _variant("v1", EnumVariantRole.ACTIVE, weight=1.0),
            ]
        )
        for i in range(20):
            v = handler_module.HandlerRouteToVariant().handle(
                ModelRouteToVariantRequest(run_id=f"run-{i}", registry=reg)
            )
            assert v.variant_id == "v1"

    def test_routing_is_consistent_across_calls(self) -> None:
        """Same run_id, same registry → same result every time."""
        reg = _registry(
            [
                _variant("active", EnumVariantRole.ACTIVE, weight=0.7),
                _variant("shadow", EnumVariantRole.SHADOW, weight=0.3),
            ]
        )
        results = [
            handler_module.HandlerRouteToVariant()
            .handle(ModelRouteToVariantRequest(run_id="stable-run-id", registry=reg))
            .variant_id
            for _ in range(10)
        ]
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
        result = (
            handler_module.HandlerCheckUpgradeReady()
            .handle(
                ModelCheckUpgradeReadyRequest(
                    shadow_variant_id="v2", run_count=50, shadow_wins=49, registry=reg
                )
            )
            .ready
        )
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
        result = (
            handler_module.HandlerCheckUpgradeReady()
            .handle(
                ModelCheckUpgradeReadyRequest(
                    shadow_variant_id="v2", run_count=100, shadow_wins=96, registry=reg
                )
            )
            .ready
        )
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
        result = (
            handler_module.HandlerCheckUpgradeReady()
            .handle(
                ModelCheckUpgradeReadyRequest(
                    shadow_variant_id="v2", run_count=100, shadow_wins=50, registry=reg
                )
            )
            .ready
        )
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
        result = (
            handler_module.HandlerCheckUpgradeReady()
            .handle(
                ModelCheckUpgradeReadyRequest(
                    shadow_variant_id="v2", run_count=100, shadow_wins=90, registry=reg
                )
            )
            .ready
        )
        assert result is True


# =============================================================================
# Tests: HandlerRunAbEvaluation end-to-end
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
        output = handler_module.HandlerRunAbEvaluation().handle(inp)
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
        output = handler_module.HandlerRunAbEvaluation().handle(inp)
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
        output = handler_module.HandlerRunAbEvaluation().handle(inp)
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
        output = handler_module.HandlerRunAbEvaluation().handle(inp)
        assert output.upgrade_ready is False

    def test_single_active_variant_no_divergence(self) -> None:
        """Single active variant: no divergence possible."""
        reg = _registry([_variant("active", EnumVariantRole.ACTIVE, weight=1.0)])
        inp = ModelABEvaluationInput(
            run_id="run-005",
            evidence_bundle={"metadata": {"passed": True}},
            registry=reg,
        )
        output = handler_module.HandlerRunAbEvaluation().handle(inp)
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
        out1 = handler_module.HandlerRunAbEvaluation().handle(inp)
        out2 = handler_module.HandlerRunAbEvaluation().handle(inp)
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


# Shared immutable registries make the receipt corpus deterministic.
_PARITY_SINGLE_REGISTRY = _registry([_variant("active")])
_PARITY_SPLIT_REGISTRY = _registry(
    [
        _variant("active", weight=0.5),
        _variant("shadow", EnumVariantRole.SHADOW, weight=0.5, version="2.0.0"),
    ],
    significance_threshold=0.1,
)
_PARITY_MULTI_REGISTRY = _registry(
    [
        _variant("active", weight=0.5),
        _variant("shadow", EnumVariantRole.SHADOW, weight=0.25),
        _variant("shadow_second", EnumVariantRole.SHADOW, weight=0.25),
    ],
    significance_threshold=0.1,
)

CANONICAL_PARITY_CASES: list[tuple[str, ModelABEvaluationInput]] = [
    (
        "empty_bundle_single_active",
        ModelABEvaluationInput(
            run_id="empty_bundle", evidence_bundle={}, registry=_PARITY_SINGLE_REGISTRY
        ),
    ),
    (
        "nonmapping_metadata",
        ModelABEvaluationInput(
            run_id="nonmapping",
            evidence_bundle={"metadata": None},
            registry=_PARITY_SPLIT_REGISTRY,
        ),
    ),
    (
        "failed_partial_scores",
        ModelABEvaluationInput(
            run_id="failed",
            evidence_bundle={
                "metadata": {
                    "passed": False,
                    "precomputed_scores": {"correctness": "0.25", "safety": 0.5},
                }
            },
            registry=_PARITY_SPLIT_REGISTRY,
        ),
    ),
    (
        "all_score_dimensions",
        ModelABEvaluationInput(
            run_id="all_scores",
            evidence_bundle={
                "metadata": {
                    "passed": True,
                    "precomputed_scores": {
                        "correctness": 1.0,
                        "safety": 0.9,
                        "cost": 0.8,
                        "latency": 0.7,
                        "maintainability": 0.6,
                        "human_time": 0.5,
                    },
                }
            },
            registry=_PARITY_SPLIT_REGISTRY,
        ),
    ),
    (
        "below_minimum_runs",
        ModelABEvaluationInput(
            run_id="below_minimum",
            evidence_bundle={},
            registry=_PARITY_SPLIT_REGISTRY,
            run_count_by_variant={"shadow": 9},
            shadow_win_count_by_variant={"shadow": 9},
        ),
    ),
    (
        "below_win_threshold",
        ModelABEvaluationInput(
            run_id="below_rate",
            evidence_bundle={},
            registry=_PARITY_SPLIT_REGISTRY,
            run_count_by_variant={"shadow": 10},
            shadow_win_count_by_variant={"shadow": 8},
        ),
    ),
    (
        "at_win_threshold",
        ModelABEvaluationInput(
            run_id="at_rate",
            evidence_bundle={},
            registry=_PARITY_SPLIT_REGISTRY,
            run_count_by_variant={"shadow": 10},
            shadow_win_count_by_variant={"shadow": 9},
        ),
    ),
    (
        "above_win_threshold",
        ModelABEvaluationInput(
            run_id="above_rate",
            evidence_bundle={},
            registry=_PARITY_SPLIT_REGISTRY,
            run_count_by_variant={"shadow": 10},
            shadow_win_count_by_variant={"shadow": 10},
        ),
    ),
    (
        "last_ready_shadow_wins",
        ModelABEvaluationInput(
            run_id="multiple_ready",
            evidence_bundle={},
            registry=_PARITY_MULTI_REGISTRY,
            run_count_by_variant={"shadow": 10, "shadow_second": 20},
            shadow_win_count_by_variant={"shadow": 9, "shadow_second": 20},
        ),
    ),
    (
        "inactive_shadow_evaluated",
        ModelABEvaluationInput(
            run_id="inactive_shadow",
            evidence_bundle={},
            registry=_registry(
                [
                    _variant("active"),
                    _variant("shadow", EnumVariantRole.SHADOW, weight=0.0).model_copy(
                        update={"is_active": False}
                    ),
                ]
            ),
        ),
    ),
    # All variants receive identical scores and passed values from the current
    # stub. A synthetic negative threshold reaches the divergence dispatch arm;
    # ordinary validated registries above cover the non-divergent path.
    (
        "synthetic_divergence",
        ModelABEvaluationInput(
            run_id="divergent",
            evidence_bundle={},
            registry=_PARITY_SPLIT_REGISTRY.model_copy(
                update={"divergence_threshold": -0.1}
            ),
        ),
    ),
    # Bypass registry validation only to exercise the defensive no-active arm.
    (
        "synthetic_no_active",
        ModelABEvaluationInput.model_construct(
            run_id="no_active",
            evidence_bundle={},
            registry=_PARITY_SPLIT_REGISTRY.model_copy(
                update={"variants": (_variant("shadow", EnumVariantRole.SHADOW),)}
            ),
        ),
    ),
]

ROUTE_PARITY_CASES: list[tuple[str, ModelRouteToVariantRequest]] = [
    (
        "single_active",
        ModelRouteToVariantRequest(run_id="run-0000", registry=_PARITY_SINGLE_REGISTRY),
    ),
    (
        "split_active",
        ModelRouteToVariantRequest(run_id="run-0001", registry=_PARITY_SPLIT_REGISTRY),
    ),
    (
        "split_shadow",
        ModelRouteToVariantRequest(run_id="run-0000", registry=_PARITY_SPLIT_REGISTRY),
    ),
    (
        "empty_run_id",
        ModelRouteToVariantRequest(run_id="", registry=_PARITY_SPLIT_REGISTRY),
    ),
    (
        "inactive_shadow_skipped",
        ModelRouteToVariantRequest(
            run_id="run-0001",
            registry=_registry(
                [
                    _variant("disabled", EnumVariantRole.SHADOW).model_copy(
                        update={"is_active": False}
                    ),
                    _variant("active"),
                ]
            ),
        ),
    ),
    (
        "inactive_active_skipped",
        ModelRouteToVariantRequest(
            run_id="run-0001",
            registry=_registry(
                [
                    _variant("active", weight=0.0).model_copy(
                        update={"is_active": False}
                    ),
                    _variant("shadow", EnumVariantRole.SHADOW),
                ]
            ),
        ),
    ),
    (
        "zero_weights_role_fallback",
        ModelRouteToVariantRequest(
            run_id="run-0001",
            registry=_registry(
                [
                    _variant("shadow", EnumVariantRole.SHADOW, weight=0.0),
                    _variant("active", weight=0.0),
                ]
            ),
        ),
    ),
    # Exactly one ACTIVE is normally validated; bypass it to cover the final
    # defensive fallback to the first variant when no bucket or role matches.
    (
        "synthetic_first_variant_fallback",
        ModelRouteToVariantRequest.model_construct(
            run_id="run-0001",
            registry=_PARITY_SPLIT_REGISTRY.model_copy(
                update={
                    "variants": (
                        _variant("shadow", EnumVariantRole.SHADOW, weight=0.0),
                    )
                }
            ),
        ),
    ),
]

UPGRADE_PARITY_CASES: list[tuple[str, ModelCheckUpgradeReadyRequest]] = [
    (
        case_id,
        ModelCheckUpgradeReadyRequest(
            shadow_variant_id="shadow",
            run_count=run_count,
            shadow_wins=shadow_wins,
            registry=registry,
        ),
    )
    for case_id, run_count, shadow_wins, registry in [
        ("zero_runs", 0, 0, _PARITY_SPLIT_REGISTRY),
        ("below_minimum_runs", 9, 9, _PARITY_SPLIT_REGISTRY),
        ("below_win_threshold", 10, 8, _PARITY_SPLIT_REGISTRY),
        ("at_win_threshold", 10, 9, _PARITY_SPLIT_REGISTRY),
        ("above_win_threshold", 10, 10, _PARITY_SPLIT_REGISTRY),
        (
            "significance_one_zero_wins",
            10,
            0,
            _PARITY_SPLIT_REGISTRY.model_copy(update={"significance_threshold": 1.0}),
        ),
    ]
]


def parity_call(parity_request: ModelABEvaluationInput) -> object:
    """Replay evaluation without calling any external services."""
    return handler_module.HandlerRunAbEvaluation().handle(parity_request)


def route_parity_call(parity_request: ModelRouteToVariantRequest) -> object:
    """Replay deterministic traffic routing."""
    return handler_module.HandlerRouteToVariant().handle(parity_request)


def upgrade_parity_call(parity_request: ModelCheckUpgradeReadyRequest) -> object:
    """Replay the significance decision."""
    return handler_module.HandlerCheckUpgradeReady().handle(parity_request)


@pytest.mark.unit
@pytest.mark.parametrize(
    "case_id,parity_request",
    CANONICAL_PARITY_CASES,
    ids=[case_id for case_id, _ in CANONICAL_PARITY_CASES],
)
def test_canonical_dispatch_matches_preserved_core(
    case_id: str, parity_request: ModelABEvaluationInput
) -> None:
    """Recompose the old evaluation body using only preserved core helpers."""
    handler_cls = getattr(handler_module, "HandlerRunAbEvaluation", None)
    assert handler_cls is not None, case_id

    registry = parity_request.registry
    variant_results = [
        handler_module._evaluate_variant_against_bundle(
            variant, parity_request.evidence_bundle
        )
        for variant in registry.variants
    ]
    active_result = next(
        (result for result in variant_results if result.role == EnumVariantRole.ACTIVE),
        None,
    )
    shadow_results = [
        result for result in variant_results if result.role == EnumVariantRole.SHADOW
    ]
    divergence_detected = False
    upgrade_ready = False
    upgrade_ready_variant_id: str | None = None
    if active_result is not None:
        for shadow_result in shadow_results:
            if detect_divergence(
                active_result, shadow_result, registry.divergence_threshold
            ):
                divergence_detected = True

            # Inline the preserved check_upgrade_ready body, never the new
            # handler, so a dispatch regression cannot contaminate the oracle.
            run_count = parity_request.run_count_by_variant.get(
                shadow_result.variant_id, 0
            )
            shadow_wins = parity_request.shadow_win_count_by_variant.get(
                shadow_result.variant_id, 0
            )
            if run_count < registry.min_runs_for_significance:
                continue
            win_rate = shadow_wins / max(run_count, 1)
            if win_rate >= (1.0 - registry.significance_threshold):
                upgrade_ready = True
                upgrade_ready_variant_id = shadow_result.variant_id

    expected = ModelABEvaluationOutput(
        run_id=parity_request.run_id,
        variant_results=tuple(variant_results),
        divergence_detected=divergence_detected,
        upgrade_ready=upgrade_ready,
        upgrade_ready_variant_id=upgrade_ready_variant_id,
    )
    assert parity_call(parity_request) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "case_id,parity_request",
    ROUTE_PARITY_CASES,
    ids=[case_id for case_id, _ in ROUTE_PARITY_CASES],
)
def test_canonical_route_matches_preserved_core(
    case_id: str, parity_request: ModelRouteToVariantRequest
) -> None:
    """Recompose the preserved hash, bucket scan, and fallback routing body."""
    handler_cls = getattr(handler_module, "HandlerRouteToVariant", None)
    assert handler_cls is not None, case_id

    hash_bytes = hashlib.sha256(parity_request.run_id.encode("utf-8")).digest()
    hash_frac = int.from_bytes(hash_bytes[:8], "big") / (2**64)
    cumulative = 0.0
    expected = None
    for variant in parity_request.registry.variants:
        if not variant.is_active:
            continue
        cumulative += variant.traffic_weight
        if hash_frac < cumulative:
            expected = variant
            break
    if expected is None:
        expected = next(
            (
                variant
                for variant in parity_request.registry.variants
                if variant.role == EnumVariantRole.ACTIVE
            ),
            parity_request.registry.variants[0],
        )

    assert route_parity_call(parity_request) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "case_id,parity_request",
    UPGRADE_PARITY_CASES,
    ids=[case_id for case_id, _ in UPGRADE_PARITY_CASES],
)
def test_canonical_upgrade_ready_matches_preserved_core(
    case_id: str, parity_request: ModelCheckUpgradeReadyRequest
) -> None:
    """Recompose the preserved minimum-runs and inclusive win-rate checks."""
    handler_cls = getattr(handler_module, "HandlerCheckUpgradeReady", None)
    assert handler_cls is not None, case_id

    if parity_request.run_count < parity_request.registry.min_runs_for_significance:
        ready = False
    else:
        win_rate = parity_request.shadow_wins / max(parity_request.run_count, 1)
        ready = win_rate >= (1.0 - parity_request.registry.significance_threshold)
    expected = ModelUpgradeReadyResponse(ready=ready)

    assert upgrade_parity_call(parity_request) == expected
