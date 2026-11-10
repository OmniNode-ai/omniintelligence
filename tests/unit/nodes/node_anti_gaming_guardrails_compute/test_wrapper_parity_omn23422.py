# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerRunAllGuardrails (OMN-23422).

The contract-bound handler ``HandlerRunAllGuardrails.handle`` must return exactly
what the preserved function ``run_all_guardrails`` returns for the same request
and the same dependencies. The module clock is pinned so the alert timestamps
are deterministic. Cases cover the first-run path, each of the four guardrails,
a run that raises every alert, and error paths.
"""

import importlib
import json
from collections.abc import Callable
from datetime import datetime as real_datetime
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.handlers import (
    handler_guardrails,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.handlers.handler_guardrails import (
    run_all_guardrails,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_config import (
    ModelCorrelationPair,
    ModelGuardrailConfig,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_input import (
    ModelGuardrailInput,
    ModelScoreVectorSnapshot,
)

_MODULE = (
    "omniintelligence.nodes.node_anti_gaming_guardrails_compute.handlers."
    "handler_guardrails"
)
_WRAPPER_CLASS = "HandlerRunAllGuardrails"
_RUN_ID = "run-omn-23422"
_OBJECTIVE_ID = "obj-001"


class _FrozenDatetime(real_datetime):
    """``datetime`` whose ``now`` is fixed so alert timestamps are stable."""

    @classmethod
    def now(cls, tz: Any = None) -> "_FrozenDatetime":
        return cls(2025, 1, 1, 0, 0, 0, tzinfo=tz)


@pytest.fixture(autouse=True)
def _pin_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the handler module's clock for both the wrapper and function runs."""
    monkeypatch.setattr(handler_guardrails, "datetime", _FrozenDatetime)


def _config(**overrides: Any) -> ModelGuardrailConfig:
    values: dict[str, Any] = {
        "objective_id": _OBJECTIVE_ID,
        "correlation_pairs": (
            ModelCorrelationPair(
                metric_a="correctness",
                metric_b="safety",
                divergence_threshold=0.2,
            ),
        ),
        "reward_hacking_score_threshold": 0.1,
        "reward_hacking_acceptance_floor": 0.0,
        "drift_threshold": 0.3,
        "min_evidence_sources": 2,
    }
    values.update(overrides)
    return ModelGuardrailConfig(**values)


def _build_request(**overrides: Any) -> ModelGuardrailInput:
    values: dict[str, Any] = {
        "run_id": _RUN_ID,
        "current_score": ModelScoreVectorSnapshot(correctness=0.5, safety=0.5),
        "previous_score": None,
        "evidence_sources": ("unit_tests", "static_analysis"),
        "config": _config(),
    }
    values.update(overrides)
    return ModelGuardrailInput(**values)


def _no_deps() -> dict[str, Any]:
    return {}


PARITY_CASES: list[
    tuple[str, str, Callable[[], ModelGuardrailInput], Callable[[], dict[str, Any]]]
] = [
    # Normal path: first run (no previous score), diverse evidence, no drift data.
    ("first-run-clean", _WRAPPER_CLASS, _build_request, _no_deps),
    # Goodhart branch: correctness up while safety drops past the pair threshold.
    (
        "goodhart-alert",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.9, safety=0.3),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.6),
        ),
        _no_deps,
    ),
    # Goodhart branch: opposite movement stays under the divergence threshold.
    (
        "goodhart-below-threshold",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.55, safety=0.45),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.5),
        ),
        _no_deps,
    ),
    # Reward-hacking branch: correctness improves, acceptance rate falls.
    (
        "reward-hacking-alert",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.8, safety=0.5),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.5),
            human_acceptance_rate=0.4,
            previous_acceptance_rate=0.6,
            config=_config(correlation_pairs=()),
        ),
        _no_deps,
    ),
    # Reward-hacking branch: acceptance rate improves, so no alert.
    (
        "reward-hacking-accepted",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.8, safety=0.5),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.5),
            human_acceptance_rate=0.9,
            previous_acceptance_rate=0.6,
            config=_config(correlation_pairs=()),
        ),
        _no_deps,
    ),
    # Reward-hacking branch: acceptance data absent, check is skipped.
    (
        "reward-hacking-no-acceptance-data",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.8, safety=0.5),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.5),
            human_acceptance_rate=None,
            previous_acceptance_rate=0.6,
        ),
        _no_deps,
    ),
    # Reward-hacking branch: improvement too small to trigger the check.
    (
        "reward-hacking-small-improvement",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.55, safety=0.5),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.5),
            human_acceptance_rate=0.2,
            previous_acceptance_rate=0.6,
        ),
        _no_deps,
    ),
    # Distributional shift: large drift with a source absent from the baseline.
    (
        "drift-alert-new-source",
        _WRAPPER_CLASS,
        lambda: _build_request(
            baseline_source_distribution={"unit_tests": 0.9, "static_analysis": 0.1},
            current_source_distribution={
                "unit_tests": 0.1,
                "static_analysis": 0.2,
                "manual_review": 0.7,
            },
        ),
        _no_deps,
    ),
    # Distributional shift: identical distributions stay under the threshold.
    (
        "drift-below-threshold",
        _WRAPPER_CLASS,
        lambda: _build_request(
            baseline_source_distribution={"unit_tests": 0.5, "static_analysis": 0.5},
            current_source_distribution={"unit_tests": 0.5, "static_analysis": 0.5},
        ),
        _no_deps,
    ),
    # Distributional shift: empty baseline means nothing to compare against.
    (
        "drift-empty-baseline",
        _WRAPPER_CLASS,
        lambda: _build_request(
            baseline_source_distribution={},
            current_source_distribution={"unit_tests": 1.0},
        ),
        _no_deps,
    ),
    # Diversity veto: a single evidence source type with duplicates.
    (
        "diversity-violation",
        _WRAPPER_CLASS,
        lambda: _build_request(evidence_sources=("unit_tests", "unit_tests")),
        _no_deps,
    ),
    # Diversity veto edge: no evidence sources at all.
    (
        "diversity-empty-sources",
        _WRAPPER_CLASS,
        lambda: _build_request(evidence_sources=()),
        _no_deps,
    ),
    # Every guardrail fires in the same run.
    (
        "all-guardrails-fire",
        _WRAPPER_CLASS,
        lambda: _build_request(
            current_score=ModelScoreVectorSnapshot(correctness=0.9, safety=0.3),
            previous_score=ModelScoreVectorSnapshot(correctness=0.5, safety=0.6),
            evidence_sources=("unit_tests",),
            human_acceptance_rate=0.3,
            previous_acceptance_rate=0.6,
            baseline_source_distribution={"unit_tests": 0.9, "static_analysis": 0.1},
            current_source_distribution={"unit_tests": 0.1, "manual_review": 0.9},
        ),
        _no_deps,
    ),
    # Error path: an unexpected dependency keyword reaches the function and raises.
    (
        "unexpected-dependency",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {"unknown_dependency": object},
    ),
]


async def _invoke_preserved(
    request: ModelGuardrailInput, dependencies: dict[str, Any]
) -> Any:
    """Call the preserved function exactly as the wrapper's forwarding line does."""
    return run_all_guardrails(request, **dependencies)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelGuardrailInput],
    deps_builder: Callable[[], dict[str, Any]],
) -> None:
    """Wrapper handle() and the preserved run_all_guardrails() agree."""
    module = importlib.import_module(_MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    try:
        wrapper_result = wrapper_cls(**deps_for_wrapper).handle(request_for_wrapper)
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    try:
        function_result = await _invoke_preserved(
            request_for_function, deps_for_function
        )
    except Exception as exc:  # captured deliberately for parity comparison
        function_error = exc

    if function_error is not None or wrapper_error is not None:
        assert wrapper_error is not None, (
            f"wrapper succeeded but function raised {function_error!r}"
        )
        assert function_error is not None, (
            f"function succeeded but wrapper raised {wrapper_error!r}"
        )
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_result == function_result

    for dep_name, function_dep in deps_for_function.items():
        function_calls = getattr(function_dep, "calls", None)
        if function_calls is not None:
            assert (
                getattr(deps_for_wrapper[dep_name], "calls", None) == function_calls
            ), f"dependency {dep_name} recorded different calls"


def corpus_inputs() -> list[dict[str, Any]]:
    """Return every PARITY_CASES request as a JSON-describable dict, in order."""
    rows: list[dict[str, Any]] = []
    for case_id, class_name, request_builder, _deps_builder in PARITY_CASES:
        request = request_builder()
        payload = (
            request.model_dump(mode="json")
            if isinstance(request, BaseModel)
            else request
        )
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
