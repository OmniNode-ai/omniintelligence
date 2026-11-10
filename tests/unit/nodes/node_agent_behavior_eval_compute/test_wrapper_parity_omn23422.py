# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity checks for the HandlerAgentBehaviorEvaluation wrapper (OMN-23422).

The contract-bound wrapper must return exactly what the preserved module
function ``handle_agent_behavior_evaluation`` returns for the same request and
the same dependencies. The only non-deterministic input is ``uuid4`` (the suite
id), which is patched on the handler module for both runs.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_agent_behavior_eval_compute.handlers import (
    handler_agent_behavior_evaluation as handler_module,
)
from omniintelligence.nodes.node_agent_behavior_eval_compute.handlers.handler_agent_behavior_evaluation import (
    handle_agent_behavior_evaluation,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)

MODULE = (
    "omniintelligence.nodes.node_agent_behavior_eval_compute.handlers."
    "handler_agent_behavior_evaluation"
)
WRAPPER_CLASS = "HandlerAgentBehaviorEvaluation"

_FIXED_SUITE_ID = UUID("00000000-0000-0000-0000-0000000000aa")
_SPEC_ID = UUID("00000000-0000-0000-0000-000000000b01")
_GENERATED_AT = datetime(2025, 1, 1, tzinfo=UTC)


def _scenario(index: int, failure_mode: EnumFailureMode) -> ModelEvalScenario:
    """Deterministic scenario (fixed ids and timestamp)."""
    return ModelEvalScenario(
        scenario_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
        spec_id=_SPEC_ID,
        failure_mode=failure_mode,
        input_text=f"Scenario {index} for {failure_mode.value}",
        context={"key": "value", "index": index},
        generated_at=_GENERATED_AT,
    )


def _passing_response() -> dict[str, Any]:
    return {
        "schema_pass": True,
        "trace_coverage_pct": 0.9,
        "missing_acceptance_criteria": [],
        "invented_requirements": [],
        "ambiguity_flags": [],
        "reference_integrity_pass": True,
        "metamorphic_stability_score": 0.95,
        "compliance_theater_risk": 0.05,
    }


def _failing_response() -> dict[str, Any]:
    return {
        "schema_pass": False,
        "trace_coverage_pct": 0.5,
        "missing_acceptance_criteria": ["criterion_a"],
        "invented_requirements": ["invented_req"],
        "ambiguity_flags": ["ambiguous_field"],
        "reference_integrity_pass": False,
        "metamorphic_stability_score": 0.3,
        "compliance_theater_risk": 0.8,
    }


class _FakeJudge:
    """Async judge fake that records calls and replays canned responses."""

    def __init__(
        self,
        responses: list[dict[str, Any]],
        raises: Exception | None = None,
    ) -> None:
        self._responses = responses
        self._raises = raises
        self.calls: list[tuple[str, str, list[str]]] = []

    async def __call__(
        self, system_prompt: str, user_prompt: str, criteria: list[str]
    ) -> dict[str, Any]:
        self.calls.append((system_prompt, user_prompt, list(criteria)))
        if self._raises is not None:
            raise self._raises
        return self._responses[(len(self.calls) - 1) % len(self._responses)]


def _deps(
    responses: list[dict[str, Any]], raises: Exception | None = None
) -> Callable[[], dict[str, Any]]:
    def build() -> dict[str, Any]:
        return {"judge_caller": _FakeJudge(responses, raises)}

    return build


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "single-pass",
        WRAPPER_CLASS,
        lambda: {
            "scenarios": [_scenario(1, EnumFailureMode.UNSAFE_TOOL_SEQUENCING)],
            "agent_output": "The agent executed tools in the correct order.",
        },
        _deps([_passing_response()]),
    ),
    (
        "single-fail",
        WRAPPER_CLASS,
        lambda: {
            "scenarios": [_scenario(2, EnumFailureMode.FALSE_COMPLETION_CLAIMS)],
            "agent_output": "Done. Everything works, trust me.",
        },
        _deps([_failing_response()]),
    ),
    (
        "mixed-multi-scenario",
        WRAPPER_CLASS,
        lambda: {
            "scenarios": [
                _scenario(3, EnumFailureMode.REFUSAL_DRIFT),
                _scenario(4, EnumFailureMode.SPEC_REWRITING),
                _scenario(5, EnumFailureMode.STALE_MEMORY_OBEDIENCE),
            ],
            "agent_output": "I refused, then rewrote the spec.",
        },
        _deps([_passing_response(), _failing_response()]),
    ),
    (
        "sparse-judge-response-defaults",
        WRAPPER_CLASS,
        lambda: {
            "scenarios": [_scenario(6, EnumFailureMode.SPEC_REWRITING)],
            "agent_output": "",
        },
        _deps([{}]),
    ),
    (
        "empty-scenarios-raises",
        WRAPPER_CLASS,
        lambda: {"scenarios": [], "agent_output": "anything"},
        _deps([_passing_response()]),
    ),
    (
        "judge-raises",
        WRAPPER_CLASS,
        lambda: {
            "scenarios": [_scenario(7, EnumFailureMode.UNSAFE_TOOL_SEQUENCING)],
            "agent_output": "output",
        },
        _deps([_passing_response()], raises=RuntimeError("judge unavailable")),
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
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper and preserved function return or raise alike with equal calls."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    monkeypatch.setattr(handler_module, "uuid4", lambda: _FIXED_SUITE_ID)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await handle_agent_behavior_evaluation(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None, "wrapper must raise like the function"
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result

    assert deps_a["judge_caller"].calls == deps_b["judge_caller"].calls
