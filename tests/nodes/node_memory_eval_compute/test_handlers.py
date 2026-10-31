# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for HandlerMemoryEvaluation handler.

Acceptance criteria verified:
- Handler name is exactly ``HandlerMemoryEvaluation``
- ``memory_context`` is passed to judge_caller (mock receives it as part of prompt)
- Returns ``ModelEvalSuiteResult`` with correct ``failure_mode``
- Node passes thin-shell audit (verified by test_node_purity.py suite)
- contract.yaml declares node_type: COMPUTE_GENERIC
- pytest tests/nodes/node_memory_eval_compute/test_handlers.py -v passes
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from omnibase_core.types import JsonType

import omniintelligence.nodes.node_memory_eval_compute.handlers.handler_memory_evaluation as handler_module
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalSuiteResult,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)
from omniintelligence.nodes.node_memory_eval_compute.models import (
    ModelMemoryEvalRequest,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MEMORY_FAILURE_MODES = [
    EnumFailureMode.REGRESSION_AMNESIA,
    EnumFailureMode.OVER_TRUST_PRIOR_CONTEXT,
    EnumFailureMode.CROSS_TASK_CONTAMINATION,
    EnumFailureMode.FAILURE_TO_SURFACE_MEMORY,
    EnumFailureMode.INCORRECT_SUPPRESSION,
]


def _make_scenario(failure_mode: EnumFailureMode) -> ModelEvalScenario:
    spec_id = uuid4()
    return ModelEvalScenario(
        spec_id=spec_id,
        failure_mode=failure_mode,
        input_text=f"Test scenario for {failure_mode.value}",
        context={"key": "value"},
    )


def _passing_judge_response() -> dict[str, Any]:
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


def _failing_judge_response() -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_returns_suite_result() -> None:
    """Handler returns a ModelEvalSuiteResult."""
    scenario = _make_scenario(EnumFailureMode.REGRESSION_AMNESIA)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
        ModelMemoryEvalRequest(
            scenarios=[scenario],
            memory_output="Agent recalled prior context correctly.",
            memory_context={"session": "abc"},
        )
    )

    assert isinstance(result, ModelEvalSuiteResult)
    assert result.total_scenarios == 1
    assert result.passed_count == 1
    assert result.failure_mode == EnumFailureMode.REGRESSION_AMNESIA


@pytest.mark.asyncio
async def test_failure_mode_propagated_to_suite_result() -> None:
    """Suite result failure_mode matches the first scenario's failure_mode."""
    for mode in MEMORY_FAILURE_MODES:
        scenario = _make_scenario(mode)

        async def judge(
            _system_prompt: str, _user_prompt: str, _criteria: list[str]
        ) -> dict[str, Any]:
            return _passing_judge_response()

        result = await handler_module.HandlerMemoryEvaluation(
            judge_caller=judge
        ).handle(
            ModelMemoryEvalRequest(
                scenarios=[scenario], memory_output="output", memory_context={}
            )
        )

        assert result.failure_mode == mode, (
            f"Expected failure_mode={mode.value} on suite result"
        )


@pytest.mark.asyncio
async def test_memory_context_passed_to_judge_caller() -> None:
    """memory_context is passed to judge_caller as part of the user_prompt."""
    received_prompts: list[str] = []
    expected_context = {"session_id": "xyz", "prior_tasks": ["task_a", "task_b"]}

    async def judge(
        system_prompt: str, user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        received_prompts.append(system_prompt)
        received_prompts.append(user_prompt)
        return _passing_judge_response()

    scenario = _make_scenario(EnumFailureMode.OVER_TRUST_PRIOR_CONTEXT)

    await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
        ModelMemoryEvalRequest(
            scenarios=[scenario],
            memory_output="some output",
            memory_context=expected_context,
        )
    )

    # memory_context must appear in at least one of the prompts sent to judge
    combined = " ".join(received_prompts)
    assert "session_id" in combined or "xyz" in combined, (
        "memory_context keys/values must be visible in the prompts sent to judge_caller"
    )


@pytest.mark.asyncio
async def test_multiple_scenarios_aggregated() -> None:
    """All 5 MEMORY_SYSTEM failure modes processed; counts aggregated correctly."""
    scenarios = [_make_scenario(mode) for mode in MEMORY_FAILURE_MODES]
    call_count = 0

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return _passing_judge_response()

    result = await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
        ModelMemoryEvalRequest(
            scenarios=scenarios,
            memory_output="Memory output covering all 5 failure modes.",
            memory_context={"run_id": "test-run"},
        )
    )

    assert result.total_scenarios == 5
    assert result.passed_count == 5
    assert call_count == 5
    assert len(result.results) == 5


@pytest.mark.asyncio
async def test_failing_scenarios_counted_correctly() -> None:
    """Failing judge responses reduce passed_count."""
    scenario = _make_scenario(EnumFailureMode.CROSS_TASK_CONTAMINATION)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _failing_judge_response()

    result = await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
        ModelMemoryEvalRequest(
            scenarios=[scenario],
            memory_output="Agent contaminated output with prior task state.",
            memory_context={},
        )
    )

    assert result.total_scenarios == 1
    assert result.passed_count == 0
    assert result.results[0].eval_passed is False


@pytest.mark.asyncio
async def test_scenario_id_preserved_in_result() -> None:
    """Each ModelEvalResult carries the scenario_id of its source scenario."""
    scenario = _make_scenario(EnumFailureMode.FAILURE_TO_SURFACE_MEMORY)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
        ModelMemoryEvalRequest(
            scenarios=[scenario], memory_output="output", memory_context={}
        )
    )

    assert result.results[0].scenario_id == scenario.scenario_id


@pytest.mark.asyncio
async def test_empty_scenarios_raises_value_error() -> None:
    """Empty scenarios list must raise ValueError."""

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    with pytest.raises(ValueError, match="scenarios must not be empty"):
        await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
            ModelMemoryEvalRequest(
                scenarios=[], memory_output="output", memory_context={}
            )
        )


@pytest.mark.asyncio
async def test_incorrect_suppression_failure_mode() -> None:
    """INCORRECT_SUPPRESSION failure mode is correctly propagated."""
    scenario = _make_scenario(EnumFailureMode.INCORRECT_SUPPRESSION)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
        ModelMemoryEvalRequest(
            scenarios=[scenario],
            memory_output="Agent incorrectly suppressed relevant memory.",
            memory_context={"suppression_context": "task_b_overrides"},
        )
    )

    assert result.failure_mode == EnumFailureMode.INCORRECT_SUPPRESSION
    assert result.results[0].failure_mode == EnumFailureMode.INCORRECT_SUPPRESSION


def _parity_request(
    *cases: tuple[EnumFailureMode, dict[str, JsonType]],
    memory_output: str = "Memory output for parity evaluation.",
    memory_context: dict[str, JsonType] | None = None,
) -> ModelMemoryEvalRequest:
    """Create stable scenarios with raw judge fixtures carried in context."""
    return ModelMemoryEvalRequest(
        scenarios=[
            ModelEvalScenario(
                scenario_id=UUID(int=index),
                spec_id=UUID(int=100 + index),
                failure_mode=mode,
                input_text=f"Parity scenario {index}: {mode.value}",
                context={"judge_response": raw},
                generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            for index, (mode, raw) in enumerate(cases, start=1)
        ],
        memory_output=memory_output,
        memory_context={} if memory_context is None else memory_context,
    )


CANONICAL_PARITY_CASES: list[tuple[str, ModelMemoryEvalRequest]] = [
    *[
        (
            mode.value,
            _parity_request(
                (mode, _passing_judge_response()),
                memory_context={
                    "session_id": "parity-session",
                    "prior_tasks": ["task_a", "task_b"],
                    "nested": {"enabled": True, "weight": 0.5},
                },
            ),
        )
        for mode in MEMORY_FAILURE_MODES
    ],
    (
        "missing_response_keys",
        _parity_request((EnumFailureMode.REGRESSION_AMNESIA, {}), memory_output=""),
    ),
    (
        "malformed_response_values",
        _parity_request(
            (
                EnumFailureMode.OVER_TRUST_PRIOR_CONTEXT,
                {
                    "schema_pass": [],
                    "reference_integrity_pass": "",
                    "trace_coverage_pct": "not_a_number",
                    "metamorphic_stability_score": None,
                    "compliance_theater_risk": {"bad": "type"},
                    "missing_acceptance_criteria": None,
                    "invented_requirements": "not_a_list",
                    "ambiguity_flags": {"not": "a_list"},
                },
            )
        ),
    ),
    (
        "boolean_scores_mixed_lists",
        _parity_request(
            (
                EnumFailureMode.CROSS_TASK_CONTAMINATION,
                {
                    "schema_pass": 1,
                    "reference_integrity_pass": "true",
                    "trace_coverage_pct": True,
                    "metamorphic_stability_score": False,
                    "compliance_theater_risk": True,
                    "missing_acceptance_criteria": ["criterion", 1, None, True],
                    "invented_requirements": [{"key": "value"}],
                    "ambiguity_flags": [["nested"]],
                },
            )
        ),
    ),
    (
        "string_number_scores",
        _parity_request(
            (
                EnumFailureMode.FAILURE_TO_SURFACE_MEMORY,
                {
                    **_passing_judge_response(),
                    "trace_coverage_pct": "0.8",
                    "metamorphic_stability_score": "0.75",
                    "compliance_theater_risk": "0.25",
                },
            )
        ),
    ),
    (
        "integer_scores_low_coverage",
        _parity_request(
            (
                EnumFailureMode.INCORRECT_SUPPRESSION,
                {
                    **_passing_judge_response(),
                    "trace_coverage_pct": 0,
                    "metamorphic_stability_score": 1,
                    "compliance_theater_risk": 0,
                },
            )
        ),
    ),
    (
        "reference_failure",
        _parity_request(
            (
                EnumFailureMode.REGRESSION_AMNESIA,
                {**_passing_judge_response(), "reference_integrity_pass": False},
            )
        ),
    ),
    (
        "mixed_scenario_results",
        _parity_request(
            (EnumFailureMode.INCORRECT_SUPPRESSION, _failing_judge_response()),
            (EnumFailureMode.REGRESSION_AMNESIA, _passing_judge_response()),
            (EnumFailureMode.CROSS_TASK_CONTAMINATION, {}),
            memory_context={"prior_tasks": [], "suppressed": False},
        ),
    ),
]


def parity_call(parity_request: ModelMemoryEvalRequest) -> object:
    """Run canonical dispatch with deterministic, ordered judge responses."""
    scenarios = iter(parity_request.scenarios)
    calls: list[tuple[str, str, list[str]]] = []

    async def judge(
        system_prompt: str, user_prompt: str, criteria: list[str]
    ) -> dict[str, JsonType]:
        scenario = next(scenarios)
        call = (system_prompt, user_prompt, criteria)
        assert call == (
            handler_module._build_system_prompt(
                scenario, parity_request.memory_context
            ),
            handler_module._build_user_prompt(
                scenario, parity_request.memory_output, parity_request.memory_context
            ),
            handler_module._build_criteria(scenario),
        )
        calls.append(call)
        return scenario.context["judge_response"]

    result = asyncio.run(
        handler_module.HandlerMemoryEvaluation(judge_caller=judge).handle(
            parity_request
        )
    )
    assert len(calls) == len(parity_request.scenarios)
    return result.model_dump(exclude={"suite_id"})


@pytest.mark.unit
@pytest.mark.parametrize(
    "case_id,parity_request",
    CANONICAL_PARITY_CASES,
    ids=[case_id for case_id, _ in CANONICAL_PARITY_CASES],
)
def test_canonical_dispatch_matches_preserved_core(
    case_id: str, parity_request: ModelMemoryEvalRequest
) -> None:
    handler_class = getattr(handler_module, "HandlerMemoryEvaluation", None)
    assert handler_class is not None

    responses = {
        (
            handler_module._build_system_prompt(
                scenario, parity_request.memory_context
            ),
            handler_module._build_user_prompt(
                scenario, parity_request.memory_output, parity_request.memory_context
            ),
            tuple(handler_module._build_criteria(scenario)),
        ): scenario.context["judge_response"]
        for scenario in parity_request.scenarios
    }
    results = []
    for scenario in parity_request.scenarios:
        system_prompt = handler_module._build_system_prompt(
            scenario, parity_request.memory_context
        )
        user_prompt = handler_module._build_user_prompt(
            scenario, parity_request.memory_output, parity_request.memory_context
        )
        criteria = handler_module._build_criteria(scenario)
        raw = responses[(system_prompt, user_prompt, tuple(criteria))]
        # _build_eval_result delegates parsing to the preserved _response_bool,
        # _response_float and _response_str_list helpers.
        results.append(handler_module._build_eval_result(scenario, raw))

    expected = ModelEvalSuiteResult(
        suite_id=UUID(int=0),
        spec_id=parity_request.scenarios[0].spec_id,
        failure_mode=parity_request.scenarios[0].failure_mode,
        results=results,
        total_scenarios=len(results),
        passed_count=sum(1 for result in results if result.eval_passed),
    ).model_dump(exclude={"suite_id"})
    assert parity_call(parity_request) == expected, case_id
