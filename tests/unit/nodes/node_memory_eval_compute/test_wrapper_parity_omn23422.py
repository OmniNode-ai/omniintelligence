# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity checks for HandlerMemoryEvaluation (OMN-23422).

The contract-bound handler ``HandlerMemoryEvaluation.handle`` splats the request
mapping into ``handle_memory_evaluation`` exactly like the preserved function is
called, so both must return the same suite result for the same request and the
same judge, and must call the judge with identical prompts and criteria.
``uuid4`` in the handler module is replaced by a deterministic sequence so the
suite id is comparable. Cases cover pass and fail judgements, multi-scenario
suites, malformed judge responses, and error paths.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic_core import to_jsonable_python

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)
from omniintelligence.nodes.node_memory_eval_compute.handlers import (
    handler_memory_evaluation,
)
from omniintelligence.nodes.node_memory_eval_compute.handlers.handler_memory_evaluation import (
    handle_memory_evaluation,
)

_MODULE = (
    "omniintelligence.nodes.node_memory_eval_compute.handlers.handler_memory_evaluation"
)
_WRAPPER_CLASS = "HandlerMemoryEvaluation"
_SPEC_ID = UUID("00000000-0000-0000-0000-00000000f001")


class FakeJudge:
    """In-memory judge caller returning queued responses and recording calls."""

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._error = error
        self.calls: list[tuple[str, str, list[str]]] = []

    async def __call__(
        self, system_prompt: str, user_prompt: str, criteria: list[str]
    ) -> dict[str, Any]:
        self.calls.append((system_prompt, user_prompt, list(criteria)))
        if self._error is not None:
            raise self._error
        index = len(self.calls) - 1
        return self._responses[min(index, len(self._responses) - 1)]


def _passing() -> dict[str, Any]:
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


def _failing() -> dict[str, Any]:
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


def _scenario(
    index: int, failure_mode: EnumFailureMode = EnumFailureMode.REGRESSION_AMNESIA
) -> ModelEvalScenario:
    return ModelEvalScenario(
        scenario_id=UUID(int=0x100 + index),
        spec_id=_SPEC_ID,
        failure_mode=failure_mode,
        input_text=f"Scenario {index} for {failure_mode.value}",
        context={"key": "value"},
        generated_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


def _build_request(
    scenarios: list[ModelEvalScenario] | None = None,
    memory_output: str = "The agent recalled the prior migration correctly.",
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "scenarios": [_scenario(1)] if scenarios is None else scenarios,
        "memory_output": memory_output,
        "memory_context": (
            {"session_id": "abc", "prior_tasks": ["task1"]}
            if memory_context is None
            else memory_context
        ),
    }


PARITY_CASES: list[
    tuple[str, str, Callable[[], dict[str, Any]], Callable[[], dict[str, Any]]]
] = [
    # Normal path: one scenario, passing judgement.
    (
        "single-passing",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {"judge_caller": FakeJudge([_passing()])},
    ),
    # Second branch: failing judgement lowers the passed count.
    (
        "single-failing",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {"judge_caller": FakeJudge([_failing()])},
    ),
    # Multi-scenario suite with mixed outcomes; suite mode comes from the first scenario.
    (
        "mixed-multi-scenario",
        _WRAPPER_CLASS,
        lambda: _build_request(
            [
                _scenario(1, EnumFailureMode.OVER_TRUST_PRIOR_CONTEXT),
                _scenario(2, EnumFailureMode.CROSS_TASK_CONTAMINATION),
                _scenario(3, EnumFailureMode.INCORRECT_SUPPRESSION),
            ],
            memory_context={"session_id": "xyz", "prior_tasks": []},
        ),
        lambda: {"judge_caller": FakeJudge([_passing(), _failing(), _passing()])},
    ),
    # Judge response with missing keys falls back to safe defaults.
    (
        "judge-empty-response",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {"judge_caller": FakeJudge([{}])},
    ),
    # Judge response with loosely typed values is coerced conservatively.
    (
        "judge-loose-types",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {
            "judge_caller": FakeJudge(
                [
                    {
                        "schema_pass": 1,
                        "trace_coverage_pct": "0.85",
                        "missing_acceptance_criteria": [1, "two", None],
                        "invented_requirements": "not-a-list",
                        "ambiguity_flags": ["a"],
                        "reference_integrity_pass": "yes",
                        "metamorphic_stability_score": True,
                        "compliance_theater_risk": "not-a-number",
                    }
                ]
            )
        },
    ),
    # Judge response with non-numeric container values for float fields.
    (
        "judge-container-scores",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {
            "judge_caller": FakeJudge(
                [
                    {
                        "schema_pass": True,
                        "trace_coverage_pct": [0.9],
                        "reference_integrity_pass": True,
                        "metamorphic_stability_score": None,
                        "compliance_theater_risk": {"v": 1},
                    }
                ]
            )
        },
    ),
    # Edge: an empty memory output and context still reach the judge.
    (
        "empty-memory-output",
        _WRAPPER_CLASS,
        lambda: _build_request(memory_output="", memory_context={}),
        lambda: {"judge_caller": FakeJudge([_passing()])},
    ),
    # Error path: no scenarios raises ValueError before the judge is called.
    (
        "empty-scenarios",
        _WRAPPER_CLASS,
        lambda: _build_request(scenarios=[]),
        lambda: {"judge_caller": FakeJudge([_passing()])},
    ),
    # Error path: the judge raises and the error propagates.
    (
        "judge-raises",
        _WRAPPER_CLASS,
        lambda: _build_request(
            [_scenario(1), _scenario(2, EnumFailureMode.INCORRECT_SUPPRESSION)]
        ),
        lambda: {"judge_caller": FakeJudge(error=RuntimeError("judge unavailable"))},
    ),
    # Error path: the required judge dependency is missing.
    (
        "missing-judge-caller",
        _WRAPPER_CLASS,
        _build_request,
        lambda: {},
    ),
]


def _deterministic_uuid4() -> Callable[[], UUID]:
    """Return a ``uuid4`` replacement yielding a fresh predictable sequence."""
    counter = iter(range(0x9000, 0x9100))

    def _next() -> UUID:
        return UUID(int=next(counter))

    return _next


async def _invoke_preserved(
    request: dict[str, Any], dependencies: dict[str, Any]
) -> Any:
    """Call the preserved function exactly as the wrapper's forwarding line does."""
    return await handle_memory_evaluation(**request, **dependencies)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case_id for case_id, _cls, _req, _deps in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper handle() and the preserved handle_memory_evaluation() agree."""
    module = importlib.import_module(_MODULE)
    wrapper_cls = getattr(module, class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_for_wrapper = request_builder()
    request_for_function = request_builder()
    deps_for_wrapper = deps_builder()
    deps_for_function = deps_builder()

    wrapper_result: Any = None
    wrapper_error: Exception | None = None
    monkeypatch.setattr(handler_memory_evaluation, "uuid4", _deterministic_uuid4())
    try:
        wrapper_result = await wrapper_cls(**deps_for_wrapper).handle(
            request_for_wrapper
        )
    except Exception as exc:  # captured deliberately for parity comparison
        wrapper_error = exc

    function_result: Any = None
    function_error: Exception | None = None
    monkeypatch.setattr(handler_memory_evaluation, "uuid4", _deterministic_uuid4())
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
        payload = to_jsonable_python(request_builder())
        rows.append(
            {
                "case": case_id,
                "wrapper": class_name,
                "request": json.loads(json.dumps(payload, default=str)),
            }
        )
    return rows
