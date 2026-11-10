# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity checks for the HandlerDispatchOutcome wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved module
function ``handle_dispatch_outcome`` returns for the same event. The wall
clock (``datetime.now``) and ``time.perf_counter`` are patched on the handler
module so both runs are deterministic. Artifact paths are relative; the test
runs inside a temporary directory holding the artifact fixtures.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers import (
    handler_dispatch_outcome as handler_module,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers.handler_dispatch_outcome import (
    handle_dispatch_outcome,
)
from omniintelligence.nodes.node_dispatch_outcome_eval_effect.models import (
    EnumUsageSource,
    ModelCallRecord,
    ModelCostProvenance,
    ModelInput,
)
from omniintelligence.nodes.node_quality_scoring_compute.models import (
    ModelQualityScoringInput,
    ModelQualityScoringOutput,
)

MODULE = (
    "omniintelligence.nodes.node_dispatch_outcome_eval_effect.handlers."
    "handler_dispatch_outcome"
)
WRAPPER_CLASS = "HandlerDispatchOutcome"

_FIXED_NOW = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

# Relative artifact fixtures written into the temporary working directory.
ARTIFACT_FILES: dict[str, str] = {
    "dispatch_artifact.py": "class DispatchArtifact:\n    pass\n",
    "dispatch_artifact.ts": "export const value = 1;\n",
}

# How the quality scorer behaves per case: "real" uses the real compute
# handler, "fixed" returns a canned score, "raises" raises RuntimeError.
SCORER_MODE: dict[str, str] = {
    "completed-python-real-scorer": "real",
    "success-padded-fixed-score": "fixed",
    "scorer-raises-runtime-error": "raises",
}


def _event(
    status: str = "completed",
    artifact_path: str | None = None,
    measured: bool = False,
) -> ModelInput:
    rollup = (
        ModelCostProvenance(
            usage_source=EnumUsageSource.MEASURED, source_payload_hash="sha-abc"
        )
        if measured
        else ModelCostProvenance(
            usage_source=EnumUsageSource.ESTIMATED,
            estimation_method="model_call_rollup",
        )
    )
    return ModelInput(
        task_id="task-123",
        dispatch_id="dispatch-456",
        ticket_id="OMN-10385",
        status=status,
        artifact_path=artifact_path,
        model_calls=[
            ModelCallRecord(
                provider="claude_code",
                model="claude_subprocess",
                input_tokens=700,
                output_tokens=300,
                latency_ms=25,
                cost_dollars=0.25,
                cost_provenance=ModelCostProvenance(
                    usage_source=EnumUsageSource.ESTIMATED,
                    estimation_method="test_estimate",
                ),
            )
        ],
        token_cost=1000,
        dollars_cost=0.25,
        cost_provenance=rollup,
    )


def _no_deps() -> dict[str, Any]:
    """The preserved function takes no dependencies; fresh empty dict per run."""
    return {}


PARITY_CASES: list[
    tuple[str, str, Callable[[], BaseModel], Callable[[], dict[str, Any]]]
] = [
    (
        "completed-no-artifact",
        WRAPPER_CLASS,
        lambda: _event("completed"),
        _no_deps,
    ),
    (
        "completed-python-real-scorer",
        WRAPPER_CLASS,
        lambda: _event("completed", "dispatch_artifact.py"),
        _no_deps,
    ),
    (
        "success-padded-fixed-score",
        WRAPPER_CLASS,
        lambda: _event("  Success ", "dispatch_artifact.py", measured=True),
        _no_deps,
    ),
    (
        "failed-unsupported-language",
        WRAPPER_CLASS,
        lambda: _event("failed", "dispatch_artifact.ts"),
        _no_deps,
    ),
    (
        "error-status",
        WRAPPER_CLASS,
        lambda: _event("error"),
        _no_deps,
    ),
    (
        "unknown-status-falls-to-error",
        WRAPPER_CLASS,
        lambda: _event("cancelled"),
        _no_deps,
    ),
    (
        "python-artifact-missing",
        WRAPPER_CLASS,
        lambda: _event("completed", "missing_artifact.py"),
        _no_deps,
    ),
    (
        "scorer-raises-runtime-error",
        WRAPPER_CLASS,
        lambda: _event("failed", "dispatch_artifact.py"),
        _no_deps,
    ),
]


def _make_scorer(mode: str) -> tuple[type[Any], list[ModelQualityScoringInput]]:
    """Fake quality scorer class plus the list of inputs it received."""
    seen: list[ModelQualityScoringInput] = []

    class _FakeScorer:
        def handle(
            self, request: ModelQualityScoringInput
        ) -> ModelQualityScoringOutput:
            seen.append(request)
            if mode == "raises":
                raise RuntimeError("scoring failed")
            return ModelQualityScoringOutput(success=True, quality_score=0.875)

    return _FakeScorer, seen


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
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Wrapper and preserved function return or raise alike."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    for name, content in ARTIFACT_FILES.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, _tz: Any = None) -> datetime:
            return _FIXED_NOW

    monkeypatch.setattr(handler_module, "datetime", _FixedDatetime)
    monkeypatch.setattr(
        handler_module, "time", SimpleNamespace(perf_counter=lambda: 1.0)
    )

    mode = SCORER_MODE.get(case_id, "real")

    def run_scorer_patch() -> list[ModelQualityScoringInput] | None:
        if mode == "real":
            return None
        scorer_cls, seen = _make_scorer(mode)
        monkeypatch.setattr(handler_module, "HandlerQualityScoringCompute", scorer_cls)
        return seen

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None

    seen_wrapper = run_scorer_patch()
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    seen_function = run_scorer_patch()
    try:
        function_result = await handle_dispatch_outcome(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None, "wrapper must raise like the function"
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result

    if mode != "real":
        assert seen_wrapper is not None
        assert seen_function is not None
        assert seen_wrapper == seen_function
        assert len(seen_wrapper) == 1
