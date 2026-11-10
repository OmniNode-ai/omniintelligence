# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity for the scenario generator handler (OMN-23422).

``HandlerScenarioGeneration.handle`` must return exactly what the preserved
``handle_scenario_generation`` function returns for the same request and the
same dependencies, and must drive the injected ``llm_caller`` identically.
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_behavior_scenario_generator_compute.handlers.handler_scenario_generator import (
    handle_scenario_generation,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_behavior_spec import (
    ModelBehaviorSpec,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)

MODULE = (
    "omniintelligence.nodes.node_behavior_scenario_generator_compute"
    ".handlers.handler_scenario_generator"
)
CLASS_NAME = "HandlerScenarioGeneration"

_SPEC_ID = UUID("00000000-0000-0000-0000-0000000000a1")
_FIXED_ID = UUID("00000000-0000-0000-0000-0000000000ff")
_FIXED_TIME = datetime(2025, 1, 1, tzinfo=UTC)


class _RecordingCaller:
    """In-memory llm_caller that records every call."""

    def __init__(
        self,
        *,
        texts: Callable[[int], list[str]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[str, int]] = []
        self._texts = texts or (lambda n: ["scenario text"] * n)
        self._error = error

    async def __call__(self, prompt_template: str, n: int) -> list[str]:
        self.calls.append((prompt_template, n))
        if self._error is not None:
            raise self._error
        return self._texts(n)


def _spec(
    failure_mode: EnumFailureMode = EnumFailureMode.REQUIREMENT_OMISSION,
    template: str = "Generate a scenario for requirement omission",
) -> ModelBehaviorSpec:
    return ModelBehaviorSpec(
        spec_id=_SPEC_ID,
        failure_mode=failure_mode,
        domain=EnumEvalDomain.CONTRACT_CREATION,
        description="Test spec for scenario generation",
        scenario_prompt_template=template,
        expected_behavior="All requirements are captured",
        failure_indicators=["missing requirement"],
    )


def _deps(caller: Callable[[], _RecordingCaller]) -> dict[str, Any]:
    return {"llm_caller": caller()}


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "normal-three",
        CLASS_NAME,
        lambda: {"spec": _spec(), "n": 3},
        lambda: _deps(_RecordingCaller),
    ),
    (
        "alternate-failure-mode-custom-texts",
        CLASS_NAME,
        lambda: {
            "spec": _spec(EnumFailureMode.STALE_MEMORY_OBEDIENCE, "stale memory"),
            "n": 2,
        },
        lambda: _deps(
            lambda: _RecordingCaller(texts=lambda n: [f"custom {i}" for i in range(n)])
        ),
    ),
    (
        "single-scenario",
        CLASS_NAME,
        lambda: {"spec": _spec(), "n": 1},
        lambda: _deps(_RecordingCaller),
    ),
    (
        "zero-requested-empty-result",
        CLASS_NAME,
        lambda: {"spec": _spec(), "n": 0},
        lambda: _deps(_RecordingCaller),
    ),
    (
        "caller-returns-fewer-than-n",
        CLASS_NAME,
        lambda: {"spec": _spec(), "n": 4},
        lambda: _deps(lambda: _RecordingCaller(texts=lambda _n: ["only one"])),
    ),
    (
        "caller-raises",
        CLASS_NAME,
        lambda: {"spec": _spec(), "n": 2},
        lambda: _deps(lambda: _RecordingCaller(error=RuntimeError("llm unavailable"))),
    ),
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(
                    {key: _jsonable(val) for key, val in request_builder().items()},
                    default=str,
                )
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


def _stable(scenarios: list[ModelEvalScenario]) -> list[dict[str, Any]]:
    """Mask only the uuid4/now() defaults; every other field is compared."""
    return [
        s.model_copy(
            update={"scenario_id": _FIXED_ID, "generated_at": _FIXED_TIME}
        ).model_dump(mode="json")
        for s in scenarios
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
) -> None:
    """Wrapper and preserved function return/raise alike and call the LLM alike."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result: list[ModelEvalScenario] = []
    function_result: list[ModelEvalScenario] = []
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await handle_scenario_generation(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert len(wrapper_result) == len(function_result)
        if wrapper_result:
            assert _stable(wrapper_result) == _stable(function_result)
    assert deps_a["llm_caller"].calls == deps_b["llm_caller"].calls
    assert len(deps_a["llm_caller"].calls) == 1
