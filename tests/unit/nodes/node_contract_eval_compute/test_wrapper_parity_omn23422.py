# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Parity: the contract-bound contract-evaluation wrapper matches the preserved function.

``HandlerContractEvaluation.handle`` splats a request mapping into
``handle_contract_evaluation``. Both are driven with identical requests and
fresh, recording judge fakes; results (or raised errors) and the recorded
judge calls must be identical.

Ticket: OMN-23422
"""

import importlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)
from omniintelligence.nodes.node_contract_eval_compute.handlers.handler_contract_eval import (
    handle_contract_evaluation,
)

MODULE = (
    "omniintelligence.nodes.node_contract_eval_compute.handlers.handler_contract_eval"
)
CLASS_NAME = "HandlerContractEvaluation"

_SCENARIO_ID = UUID("00000000-0000-0000-0000-0000000000a1")
_SPEC_ID = UUID("00000000-0000-0000-0000-0000000000b2")
_GENERATED_AT = datetime(2025, 1, 1, tzinfo=UTC)


def _valid_contract(**overrides: Any) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "node_type": "compute",
        "contract_id": "test-contract-001",
        "title": "Test Contract",
        "description": "Validates input and emits an audit record.",
        "io": {"input": "ModelFoo", "output": "ModelBar"},
        "environment_variables": {},
    }
    contract.update(overrides)
    return contract


def _scenario(mode: EnumFailureMode) -> ModelEvalScenario:
    return ModelEvalScenario(
        scenario_id=_SCENARIO_ID,
        spec_id=_SPEC_ID,
        failure_mode=mode,
        input_text="Write a contract for the audit node.",
        context={"source": "unit"},
        generated_at=_GENERATED_AT,
    )


def _request(
    mode: EnumFailureMode = EnumFailureMode.REQUIREMENT_OMISSION,
    contract: dict[str, Any] | None = None,
    requirements: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "contract_dict": _valid_contract() if contract is None else contract,
        "scenario": _scenario(mode),
        "ticket_requirements": [] if requirements is None else requirements,
    }


class RecordingJudge:
    """Async judge fake that records its calls and returns or raises on demand."""

    def __init__(
        self,
        output: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.output = output if output is not None else {}
        self.error = error
        self.calls: list[tuple[str, str, list[str]]] = []

    async def __call__(
        self, prompt: str, output: str, failure_indicators: list[str]
    ) -> dict[str, Any]:
        self.calls.append((prompt, output, list(failure_indicators)))
        if self.error is not None:
            raise self.error
        return dict(self.output)


def _judge_deps(
    output: dict[str, Any] | None = None, error: Exception | None = None
) -> Callable[[], dict[str, Any]]:
    return lambda: {"judge_caller": RecordingJudge(output=output, error=error)}


_FULL_JUDGE_OUTPUT: dict[str, Any] = {
    "metamorphic_stability_score": 0.9,
    "compliance_theater_risk": 0.1,
    "ambiguity_flags": ["vague term"],
    "invented_requirements": ["extra"],
    "missing_acceptance_criteria": ["ac-1", "ac-2"],
}

PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], dict[str, Any]],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "normal-full-judge",
        CLASS_NAME,
        lambda: _request(requirements=["validates input", "emits an audit record"]),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "partial-trace-coverage",
        CLASS_NAME,
        lambda: _request(requirements=["validates input", "encrypts payload"]),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "acceptance-criteria-trace",
        CLASS_NAME,
        lambda: _request(
            contract=_valid_contract(acceptance_criteria="must retry on timeout"),
            requirements=["retry on timeout"],
        ),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "invented-requirements-mode",
        CLASS_NAME,
        lambda: _request(mode=EnumFailureMode.INVENTED_REQUIREMENTS),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "traceability-mode",
        CLASS_NAME,
        lambda: _request(mode=EnumFailureMode.TRACEABILITY_FAILURE),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "paraphrase-mode",
        CLASS_NAME,
        lambda: _request(mode=EnumFailureMode.PARAPHRASE_INSTABILITY),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "compliance-theater-mode",
        CLASS_NAME,
        lambda: _request(mode=EnumFailureMode.COMPLIANCE_THEATER),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "unmapped-mode-default-indicators",
        CLASS_NAME,
        lambda: _request(mode=EnumFailureMode.REFUSAL_DRIFT),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "empty-contract-schema-fails",
        CLASS_NAME,
        lambda: _request(contract={}, requirements=["anything"]),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "dangling-reference",
        CLASS_NAME,
        lambda: _request(contract=_valid_contract(references=["missing_field"])),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "resolved-reference",
        CLASS_NAME,
        lambda: _request(contract=_valid_contract(references=["input"])),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "non-dict-io-with-references",
        CLASS_NAME,
        lambda: _request(contract=_valid_contract(io="ModelFoo", references=["x"])),
        _judge_deps(_FULL_JUDGE_OUTPUT),
    ),
    (
        "judge-output-coercions",
        CLASS_NAME,
        lambda: _request(),
        _judge_deps(
            {
                "metamorphic_stability_score": "0.75",
                "compliance_theater_risk": "not-a-number",
                "ambiguity_flags": "single flag",
                "invented_requirements": 42,
                "missing_acceptance_criteria": [1, "two", None],
            }
        ),
    ),
    (
        "judge-output-empty",
        CLASS_NAME,
        lambda: _request(),
        _judge_deps({}),
    ),
    (
        "judge-output-none-values",
        CLASS_NAME,
        lambda: _request(),
        _judge_deps(
            {
                "metamorphic_stability_score": None,
                "compliance_theater_risk": [1],
                "ambiguity_flags": None,
            }
        ),
    ),
    (
        "judge-raises",
        CLASS_NAME,
        lambda: _request(),
        _judge_deps(error=ValueError("model offline")),
    ),
]


def _describe(request: dict[str, Any]) -> dict[str, Any]:
    described = dict(request)
    described["scenario"] = request["scenario"].model_dump(mode="json")
    return described


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(_describe(request_builder()), default=str)
            ),
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
) -> None:
    """The wrapper returns (or raises) exactly what the preserved function does."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

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
        function_result = await handle_contract_evaluation(**request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
        assert wrapper_result is not None
        assert wrapper_result.model_dump(mode="json") == function_result.model_dump(
            mode="json"
        )
    assert deps_a["judge_caller"].calls == deps_b["judge_caller"].calls
    assert len(deps_a["judge_caller"].calls) == 1
    if case_id == "judge-raises":
        assert function_error is not None
