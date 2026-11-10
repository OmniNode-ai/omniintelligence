# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity of the contract-bound bloom eval handler with ``run_bloom_eval``.

OMN-23422: ``HandlerBloomEvalRun.handle`` must behave exactly like the
preserved module function ``run_bloom_eval`` for the same command and the same
dependencies. ``run_bloom_eval`` returns ``None``; its observable behavior is
the sequence of LLM client calls, contract-node inputs and Kafka publishes, so
those recorded calls are compared in addition to the (``None``) results.
"""

import asyncio
import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

import omniintelligence.nodes.node_bloom_eval_orchestrator.handlers.handler_bloom_eval_effect as handler_mod
from omniintelligence.nodes.node_bloom_eval_orchestrator.handlers.handler_bloom_eval_effect import (
    ModelBloomEvalRunCommand,
    run_bloom_eval,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalResult,
)
from omniintelligence.nodes.node_contract_eval_compute.models import (
    ModelContractEvalInput,
)

MODULE = (
    "omniintelligence.nodes.node_bloom_eval_orchestrator.handlers."
    "handler_bloom_eval_effect"
)

_FIXED_NOW = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
_JUDGMENT: dict[str, Any] = {
    "metamorphic_stability_score": 0.9,
    "compliance_theater_risk": 0.1,
    "ambiguity_flags": [],
    "invented_requirements": [],
    "missing_acceptance_criteria": [],
    "schema_pass": True,
}


class _FixedDatetime(datetime):
    """``datetime`` whose ``now`` is deterministic (masks ``emitted_at``)."""

    @classmethod
    def now(cls, tz: Any = None) -> "_FixedDatetime":
        return cls.fromtimestamp(_FIXED_NOW.timestamp(), tz=tz)


class _FakeProducer:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("publish failed")


class _FakeLLMClient:
    def __init__(self, scenarios: list[str] | None = None, fail: bool = False) -> None:
        self.scenarios = (
            ["scenario text 0", "scenario text 1"] if scenarios is None else scenarios
        )
        self.fail = fail
        self.generate_calls: list[tuple[Any, ...]] = []
        self.judge_calls: list[dict[str, Any]] = []

    async def generate_scenarios(self, *args: Any, **kwargs: Any) -> list[str]:
        self.generate_calls.append((args, kwargs))
        if self.fail:
            raise RuntimeError("llm unavailable")
        return list(self.scenarios)

    async def judge_output(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.judge_calls.append({"args": args, "kwargs": kwargs})
        return dict(_JUDGMENT)


class _RecordingContractEvalNode:
    def __init__(self, passed: bool = True) -> None:
        self.passed = passed
        self.inputs: list[dict[str, Any]] = []

    async def compute(self, input_data: ModelContractEvalInput) -> ModelEvalResult:
        self.inputs.append(
            {
                "contract_dict": input_data.contract_dict,
                "failure_mode": input_data.scenario.failure_mode,
                "input_text": input_data.scenario.input_text,
                "ticket_requirements": input_data.ticket_requirements,
            }
        )
        return ModelEvalResult(
            schema_pass=self.passed,
            trace_coverage_pct=1.0 if self.passed else 0.0,
            missing_acceptance_criteria=[] if self.passed else ["criterion"],
            invented_requirements=[],
            ambiguity_flags=[],
            reference_integrity_pass=True,
            metamorphic_stability_score=0.9 if self.passed else 0.1,
            compliance_theater_risk=0.1,
            failure_mode=input_data.scenario.failure_mode,
            scenario_id=input_data.scenario.scenario_id,
        )


def _command(
    failure_mode: EnumFailureMode,
    *,
    scenarios_per_spec: int = 2,
    publish_topic: str | None = None,
    memory_output: str = "",
    memory_context: dict[str, Any] | None = None,
) -> ModelBloomEvalRunCommand:
    extra: dict[str, Any] = {}
    if publish_topic is not None:
        extra["publish_topic"] = publish_topic
    return ModelBloomEvalRunCommand(
        command_id=UUID("00000000-0000-0000-0000-0000000000a1"),
        failure_mode=failure_mode,
        suite_id=UUID("00000000-0000-0000-0000-0000000000b2"),
        correlation_id="corr-omn23422",
        scenarios_per_spec=scenarios_per_spec,
        memory_output=memory_output,
        memory_context=memory_context or {},
        **extra,
    )


def _contract_deps() -> dict[str, Any]:
    return {
        "producer": _FakeProducer(),
        "llm_client": _FakeLLMClient(),
        "contract_eval_node": _RecordingContractEvalNode(),
    }


PARITY_CASES: list[
    tuple[
        str, str, Callable[[], BaseModel | dict[str, Any]], Callable[[], dict[str, Any]]
    ]
] = [
    (
        "contract-published",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.REQUIREMENT_OMISSION),
        _contract_deps,
    ),
    (
        "contract-no-producer",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.COMPLIANCE_THEATER, scenarios_per_spec=3),
        lambda: {
            "producer": None,
            "llm_client": _FakeLLMClient(["a", "b", "c"]),
            "contract_eval_node": _RecordingContractEvalNode(passed=False),
        },
    ),
    (
        "contract-default-node",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.TRACEABILITY_FAILURE),
        lambda: {"producer": _FakeProducer(), "llm_client": _FakeLLMClient()},
    ),
    (
        "agent-path",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.UNSAFE_TOOL_SEQUENCING),
        lambda: {"producer": _FakeProducer(), "llm_client": _FakeLLMClient()},
    ),
    (
        "memory-path",
        "HandlerBloomEvalRun",
        lambda: _command(
            EnumFailureMode.REGRESSION_AMNESIA,
            memory_output="the memory said X",
            memory_context={"session": "s1"},
        ),
        lambda: {"producer": _FakeProducer(), "llm_client": _FakeLLMClient()},
    ),
    (
        "custom-publish-topic",
        "HandlerBloomEvalRun",
        lambda: _command(
            EnumFailureMode.INVENTED_REQUIREMENTS,
            publish_topic="onex.evt.test.custom-topic.v1",
        ),
        _contract_deps,
    ),
    (
        "empty-scenarios",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.REQUIREMENT_OMISSION, scenarios_per_spec=0),
        lambda: {
            "producer": _FakeProducer(),
            "llm_client": _FakeLLMClient([]),
            "contract_eval_node": _RecordingContractEvalNode(),
        },
    ),
    (
        "publish-failure-swallowed",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.PARAPHRASE_INSTABILITY),
        lambda: {
            "producer": _FakeProducer(fail=True),
            "llm_client": _FakeLLMClient(),
            "contract_eval_node": _RecordingContractEvalNode(),
        },
    ),
    (
        "llm-error",
        "HandlerBloomEvalRun",
        lambda: _command(EnumFailureMode.REQUIREMENT_OMISSION),
        lambda: {
            "producer": _FakeProducer(),
            "llm_client": _FakeLLMClient(fail=True),
            "contract_eval_node": _RecordingContractEvalNode(),
        },
    ),
]


def _request_json(request: BaseModel | dict[str, Any]) -> Any:
    raw = request.model_dump(mode="json") if isinstance(request, BaseModel) else request
    return json.loads(json.dumps(raw, default=str))


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {"case": case_id, "wrapper": class_name, "request": _request_json(build())}
        for case_id, class_name, build, _ in PARITY_CASES
    ]


async def _drain_background_publishes() -> None:
    pending = list(handler_mod._background_tasks)
    if pending:
        await asyncio.gather(*pending)


def _snapshot(deps: dict[str, Any]) -> dict[str, Any]:
    producer = deps.get("producer")
    llm = deps["llm_client"]
    node = deps.get("contract_eval_node")
    return {
        "publish": None if producer is None else producer.calls,
        "generate": llm.generate_calls,
        "judge": llm.judge_calls,
        "contract_inputs": None if node is None else node.inputs,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], BaseModel | dict[str, Any]],
    deps_builder: Callable[[], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wrapper and the preserved function agree on result, raise and calls."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"
    monkeypatch.setattr(handler_mod, "datetime", _FixedDatetime)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    wrapper_result: Any = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    await _drain_background_publishes()

    function_error: Exception | None = None
    function_result: Any = None
    try:
        function_result = await run_bloom_eval(request_b, **deps_b)
    except Exception as exc:
        function_error = exc
    await _drain_background_publishes()

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    assert _snapshot(deps_a) == _snapshot(deps_b)
