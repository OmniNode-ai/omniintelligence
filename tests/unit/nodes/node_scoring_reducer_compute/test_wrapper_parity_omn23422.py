# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity checks for the HandlerEvaluateRun wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved module
function ``evaluate_run`` returns for the same request. The function is pure
(no I/O, no clock, no uuid), so results are compared directly with pydantic
model equality.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

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

MODULE = "omniintelligence.nodes.node_scoring_reducer_compute.handlers.handler_scoring"
WRAPPER_CLASS = "HandlerEvaluateRun"


def _bundle(run_id: str, items: list[tuple[str, str, float]]) -> ModelEvidenceBundle:
    """Evidence bundle from (item_id, source, value) triples."""
    built = tuple(
        ModelEvidenceItem(item_id=item_id, source=source, value=value)
        for item_id, source, value in items
    )
    return ModelEvidenceBundle(
        run_id=run_id,
        bundle_fingerprint=ModelEvidenceBundle.fingerprint(built),
        items=built,
        collected_at_utc="2026-02-24T00:00:00Z",
    )


def _gate(
    gate_id: str,
    source: str,
    gate_type: EnumGateType = EnumGateType.THRESHOLD,
    threshold: float = 0.5,
    range_max: float | None = None,
) -> ModelGateSpec:
    return ModelGateSpec(
        id=gate_id,
        gate_type=gate_type,
        threshold=threshold,
        evidence_source=source,
        range_max=range_max,
    )


def _term(
    term_id: str,
    source: str,
    direction: str,
    dimension: str,
    weight: float = 1.0,
) -> ModelShapedTermSpec:
    return ModelShapedTermSpec(
        id=term_id,
        weight=weight,
        # Why: Literal narrowing is validated at runtime by pydantic.
        direction=direction,
        evidence_source=source,
        score_dimension=dimension,
    )


def _spec(
    gates: list[ModelGateSpec] | None = None,
    terms: list[ModelShapedTermSpec] | None = None,
) -> ModelObjectiveSpec:
    return ModelObjectiveSpec(
        objective_id="obj-parity",
        version="1.0.0",
        gates=tuple(gates or []),
        shaped_terms=tuple(terms or []),
    )


def _no_deps() -> dict[str, Any]:
    """The preserved function takes no dependencies; fresh empty dict per run."""
    return {}


PARITY_CASES: list[tuple[str, str, Callable[[], Any], Callable[[], dict[str, Any]]]] = [
    (
        "gates-pass-shaped-terms",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle(
                "run-1",
                [
                    ("i1", "test_result", 0.9),
                    ("i2", "lint_result", 0.8),
                    ("i3", "latency_measurement", 0.25),
                ],
            ),
            "spec": _spec(
                gates=[_gate("g-tests", "test_result", threshold=0.5)],
                terms=[
                    _term("t-correct", "test_result", "maximize", "correctness", 0.6),
                    _term("t-lint", "lint_result", "maximize", "correctness", 0.4),
                    _term("t-latency", "latency_measurement", "minimize", "latency"),
                ],
            ),
        },
        _no_deps,
    ),
    (
        "threshold-gate-fails",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle("run-2", [("i1", "test_result", 0.3)]),
            "spec": _spec(
                gates=[_gate("g-tests", "test_result", threshold=0.5)],
                terms=[_term("t-correct", "test_result", "maximize", "correctness")],
            ),
        },
        _no_deps,
    ),
    (
        "missing-evidence-fails-gate",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle("run-3", [("i1", "lint_result", 1.0)]),
            "spec": _spec(
                gates=[
                    _gate("g-missing", "test_result"),
                    _gate("g-lint", "lint_result", EnumGateType.BOOLEAN),
                ],
            ),
        },
        _no_deps,
    ),
    (
        "boolean-and-range-gates",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle(
                "run-4",
                [
                    ("i1", "safety_check", 1.0),
                    ("i2", "coverage_report", 0.6),
                    ("i3", "benchmark_result", 0.95),
                ],
            ),
            "spec": _spec(
                gates=[
                    _gate("g-flag", "safety_check", EnumGateType.BOOLEAN),
                    _gate(
                        "g-range-ok",
                        "coverage_report",
                        EnumGateType.RANGE,
                        threshold=0.5,
                        range_max=0.7,
                    ),
                    _gate(
                        "g-range-open",
                        "benchmark_result",
                        EnumGateType.RANGE,
                        threshold=0.5,
                    ),
                    _gate(
                        "g-regex", "benchmark_result", EnumGateType.REGEX, threshold=0.9
                    ),
                ],
                terms=[_term("t-cost", "coverage_report", "minimize", "cost")],
            ),
        },
        _no_deps,
    ),
    (
        "range-gate-above-upper-bound-fails",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle("run-5", [("i1", "coverage_report", 0.9)]),
            "spec": _spec(
                gates=[
                    _gate(
                        "g-range",
                        "coverage_report",
                        EnumGateType.RANGE,
                        threshold=0.2,
                        range_max=0.5,
                    ),
                    _gate("g-bool", "coverage_report", EnumGateType.BOOLEAN),
                ],
            ),
        },
        _no_deps,
    ),
    (
        "boolean-gate-zero-fails",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle("run-6", [("i1", "safety_check", 0.0)]),
            "spec": _spec(
                gates=[_gate("g-flag", "safety_check", EnumGateType.BOOLEAN)]
            ),
        },
        _no_deps,
    ),
    (
        "shaped-terms-missing-evidence-and-zero-contribution",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle(
                "run-7",
                [
                    ("i1", "test_result", 0.0),
                    ("i2", "code_review", 0.4),
                    ("i3", "code_review", 0.6),
                ],
            ),
            "spec": _spec(
                terms=[
                    _term("t-missing", "mypy_report", "maximize", "safety"),
                    _term("t-zero", "test_result", "maximize", "correctness"),
                    _term("t-dup-a", "code_review", "maximize", "maintainability"),
                    _term("t-dup-b", "code_review", "maximize", "human_time"),
                ]
            ),
        },
        _no_deps,
    ),
    (
        "dimension-scores-accumulate",
        WRAPPER_CLASS,
        lambda: {
            "evidence": _bundle(
                "run-8", [("i1", "test_result", 1.0), ("i2", "lint_result", 1.0)]
            ),
            "spec": _spec(
                terms=[
                    _term("t-a", "test_result", "maximize", "correctness", 0.7),
                    _term("t-b", "lint_result", "maximize", "correctness", 0.3),
                ]
            ),
        },
        _no_deps,
    ),
    (
        "no-gates-no-terms",
        WRAPPER_CLASS,
        lambda: {"evidence": _bundle("run-9", []), "spec": _spec()},
        _no_deps,
    ),
    (
        "missing-spec-argument-raises",
        WRAPPER_CLASS,
        lambda: {"evidence": _bundle("run-10", [("i1", "test_result", 0.5)])},
        _no_deps,
    ),
    (
        "invalid-evidence-type-raises",
        WRAPPER_CLASS,
        lambda: {"evidence": None, "spec": _spec()},
        _no_deps,
    ),
]


def _to_json(value: Any) -> Any:
    def default(obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return str(obj)

    return json.loads(json.dumps(value, default=default))


def corpus_inputs() -> list[dict[str, Any]]:
    """JSON-describable request per parity case, in PARITY_CASES order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": _to_json(request_builder()),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper and preserved function return or raise alike."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    try:
        wrapper_result = wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = evaluate_run(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None, "wrapper must raise like the function"
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
