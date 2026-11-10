# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity for the objective A/B framework handlers (OMN-2571 / OMN-23422).

Each contract-bound wrapper (``HandlerRouteToVariant``,
``HandlerCheckUpgradeReady``, ``HandlerRunAbEvaluation``) must return exactly
what the preserved module function returns for the same request, or raise the
same exception.
"""

import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_objective_ab_framework_compute.handlers.handler_ab_framework import (
    check_upgrade_ready,
    route_to_variant,
    run_ab_evaluation,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.enum_variant_role import (
    EnumVariantRole,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_input import (
    ModelABEvaluationInput,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariant,
    ModelObjectiveVariantRegistry,
)

MODULE = (
    "omniintelligence.nodes.node_objective_ab_framework_compute"
    ".handlers.handler_ab_framework"
)

# class name -> (preserved function, request is splatted as keyword arguments)
_PRESERVED: dict[str, tuple[Callable[..., Any], bool]] = {
    "HandlerRouteToVariant": (route_to_variant, True),
    "HandlerCheckUpgradeReady": (check_upgrade_ready, True),
    "HandlerRunAbEvaluation": (run_ab_evaluation, False),
}

_ACTIVE = EnumVariantRole.ACTIVE
_SHADOW = EnumVariantRole.SHADOW


def _variant(
    variant_id: str,
    role: EnumVariantRole = _ACTIVE,
    weight: float = 1.0,
    is_active: bool = True,
) -> ModelObjectiveVariant:
    return ModelObjectiveVariant(
        variant_id=variant_id,
        objective_id="test-objective",
        objective_version="1.0.0",
        role=role,
        traffic_weight=weight,
        is_active=is_active,
    )


def _registry(
    *variants: ModelObjectiveVariant,
    significance_threshold: float = 0.05,
    min_runs: int = 10,
    divergence_threshold: float = 0.1,
) -> ModelObjectiveVariantRegistry:
    return ModelObjectiveVariantRegistry(
        registry_id="test-registry",
        variants=variants,
        significance_threshold=significance_threshold,
        min_runs_for_significance=min_runs,
        divergence_threshold=divergence_threshold,
    )


def _split() -> ModelObjectiveVariantRegistry:
    return _registry(_variant("v1", _ACTIVE, 0.5), _variant("v2", _SHADOW, 0.5))


def _unvalidated_registry(
    *variants: ModelObjectiveVariant,
) -> ModelObjectiveVariantRegistry:
    """Registry built without the exactly-one-ACTIVE validator."""
    return ModelObjectiveVariantRegistry.model_construct(
        registry_id="test-registry",
        variants=variants,
        significance_threshold=0.05,
        min_runs_for_significance=10,
        divergence_threshold=0.1,
    )


def _route(
    run_id: str, registry: Callable[[], ModelObjectiveVariantRegistry]
) -> Callable[[], dict[str, Any]]:
    return lambda: {"run_id": run_id, "registry": registry()}


def _upgrade(
    run_count: int,
    shadow_wins: int,
    registry: Callable[[], Any] = _split,
) -> Callable[[], dict[str, Any]]:
    return lambda: {
        "_shadow_variant_id": "v2",
        "run_count": run_count,
        "shadow_wins": shadow_wins,
        "registry": registry(),
    }


def _evaluation(
    registry: Callable[[], Any],
    bundle: dict[str, Any],
    run_counts: dict[str, int] | None = None,
    wins: dict[str, int] | None = None,
) -> Callable[[], ModelABEvaluationInput]:
    def build() -> ModelABEvaluationInput:
        fields: dict[str, Any] = {
            "run_id": "run-eval",
            "evidence_bundle": bundle,
            "registry": registry(),
            "run_count_by_variant": run_counts or {},
            "shadow_win_count_by_variant": wins or {},
        }
        if isinstance(fields["registry"], ModelObjectiveVariantRegistry) and (
            sum(1 for v in fields["registry"].variants if v.role == _ACTIVE) != 1
        ):
            return ModelABEvaluationInput.model_construct(**fields)
        return ModelABEvaluationInput(**fields)

    return build


def _two_variants() -> ModelObjectiveVariantRegistry:
    return _registry(_variant("v1", _ACTIVE, 0.8), _variant("v2", _SHADOW, 0.2))


def _three_variants() -> ModelObjectiveVariantRegistry:
    return _registry(
        _variant("v1", _ACTIVE, 0.6),
        _variant("v2", _SHADOW, 0.2),
        _variant("v3", _SHADOW, 0.2),
    )


def _active_only() -> ModelObjectiveVariantRegistry:
    return _registry(_variant("v1", _ACTIVE, 1.0))


_SCORED = {
    "metadata": {
        "precomputed_scores": {
            "correctness": 0.9,
            "safety": 0.8,
            "cost": 0.7,
            "latency": 0.6,
            "maintainability": 0.5,
            "human_time": 0.4,
        },
        "passed": False,
    }
}

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], Any],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "route-first-bucket",
        "HandlerRouteToVariant",
        _route("run-1", _split),
        dict,
    ),
    (
        "route-second-bucket",
        "HandlerRouteToVariant",
        _route("run-0", _split),
        dict,
    ),
    (
        "route-skips-inactive-variant",
        "HandlerRouteToVariant",
        _route(
            "run-1",
            lambda: _registry(
                _variant("v1", _ACTIVE, 0.3, is_active=False),
                _variant("v2", _SHADOW, 1.0),
            ),
        ),
        dict,
    ),
    (
        "route-weights-short-falls-back-to-active",
        "HandlerRouteToVariant",
        _route(
            "run-2",
            lambda: _registry(
                _variant("v1", _SHADOW, 0.1), _variant("v2", _ACTIVE, 0.1)
            ),
        ),
        dict,
    ),
    (
        "route-no-active-role-returns-first",
        "HandlerRouteToVariant",
        _route(
            "run-2",
            lambda: _unvalidated_registry(
                _variant("v1", _SHADOW, 0.1), _variant("v2", _SHADOW, 0.1)
            ),
        ),
        dict,
    ),
    (
        "route-empty-registry-raises",
        "HandlerRouteToVariant",
        _route("run-2", _unvalidated_registry),
        dict,
    ),
    (
        "upgrade-below-min-runs",
        "HandlerCheckUpgradeReady",
        _upgrade(run_count=5, shadow_wins=5),
        dict,
    ),
    (
        "upgrade-win-rate-at-threshold",
        "HandlerCheckUpgradeReady",
        _upgrade(run_count=20, shadow_wins=19),
        dict,
    ),
    (
        "upgrade-win-rate-too-low",
        "HandlerCheckUpgradeReady",
        _upgrade(run_count=20, shadow_wins=10),
        dict,
    ),
    (
        "upgrade-registry-none-raises",
        "HandlerCheckUpgradeReady",
        _upgrade(run_count=20, shadow_wins=20, registry=lambda: None),
        dict,
    ),
    (
        "evaluate-scored-bundle-upgrade-ready",
        "HandlerRunAbEvaluation",
        _evaluation(_two_variants, _SCORED, {"v2": 50}, {"v2": 50}),
        dict,
    ),
    (
        "evaluate-not-enough-runs",
        "HandlerRunAbEvaluation",
        _evaluation(_two_variants, _SCORED, {"v2": 3}, {"v2": 3}),
        dict,
    ),
    (
        "evaluate-active-only-no-shadows",
        "HandlerRunAbEvaluation",
        _evaluation(_active_only, {}),
        dict,
    ),
    (
        "evaluate-two-shadows-last-ready-wins",
        "HandlerRunAbEvaluation",
        _evaluation(
            _three_variants, _SCORED, {"v2": 100, "v3": 100}, {"v2": 100, "v3": 99}
        ),
        dict,
    ),
    (
        "evaluate-non-dict-metadata",
        "HandlerRunAbEvaluation",
        _evaluation(_two_variants, {"metadata": "unreadable"}),
        dict,
    ),
    (
        "evaluate-no-active-variant",
        "HandlerRunAbEvaluation",
        _evaluation(
            lambda: _unvalidated_registry(
                _variant("v1", _SHADOW, 0.5), _variant("v2", _SHADOW, 0.5)
            ),
            _SCORED,
        ),
        dict,
    ),
    (
        "evaluate-non-numeric-score-raises",
        "HandlerRunAbEvaluation",
        _evaluation(
            _two_variants,
            {"metadata": {"precomputed_scores": {"correctness": "high"}}},
        ),
        dict,
    ),
]


def _describe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    out: list[dict[str, Any]] = []
    for case_id, class_name, request_builder, _ in PARITY_CASES:
        request = request_builder()
        described = (
            {key: _describe(val) for key, val in request.items()}
            if isinstance(request, dict)
            else _describe(request)
        )
        out.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(described, default=str)),
            }
        )
    return out


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], Any],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper and preserved function return (or raise) exactly alike."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"
    preserved, splat_request = _PRESERVED[class_name]

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = None
    function_result = None
    try:
        wrapper_result = wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = (
            preserved(**request_b, **deps_b)
            if splat_request
            else preserved(request_b, **deps_b)
        )
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
