# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for HandlerAgentBehaviorEvaluation handler.

Acceptance criteria verified:
- Handler name is exactly ``HandlerAgentBehaviorEvaluation``
- Returns ``ModelEvalSuiteResult`` with ``failure_mode`` from first scenario
- ``judge_caller`` called once per scenario (mock asserts ``call_count == len(scenarios)``)
- Node passes thin-shell audit (verified by test_node_purity.py suite)
- contract.yaml declares node_type: COMPUTE_GENERIC
- pytest tests/nodes/node_agent_behavior_eval_compute/test_handlers.py -v passes
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

import omniintelligence.nodes.node_agent_behavior_eval_compute.handlers.handler_agent_behavior_evaluation as handler_module
from omniintelligence.nodes.node_agent_behavior_eval_compute.models import (
    ModelAgentBehaviorEvalRequest,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalSuiteResult,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

AGENT_FAILURE_MODES = [
    EnumFailureMode.UNSAFE_TOOL_SEQUENCING,
    EnumFailureMode.FALSE_COMPLETION_CLAIMS,
    EnumFailureMode.STALE_MEMORY_OBEDIENCE,
    EnumFailureMode.REFUSAL_DRIFT,
    EnumFailureMode.SPEC_REWRITING,
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
    scenario = _make_scenario(EnumFailureMode.UNSAFE_TOOL_SEQUENCING)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerAgentBehaviorEvaluation(
        judge_caller=judge
    ).handle(
        ModelAgentBehaviorEvalRequest(
            scenarios=[scenario],
            agent_output="The agent executed tools in the correct order.",
        )
    )

    assert isinstance(result, ModelEvalSuiteResult)
    assert result.total_scenarios == 1
    assert result.passed_count == 1
    assert result.failure_mode == EnumFailureMode.UNSAFE_TOOL_SEQUENCING


@pytest.mark.asyncio
async def test_failure_mode_from_first_scenario() -> None:
    """Suite result failure_mode matches the first scenario's failure_mode."""
    for mode in AGENT_FAILURE_MODES:
        scenario = _make_scenario(mode)

        async def judge(
            _system_prompt: str, _user_prompt: str, _criteria: list[str]
        ) -> dict[str, Any]:
            return _passing_judge_response()

        result = await handler_module.HandlerAgentBehaviorEvaluation(
            judge_caller=judge
        ).handle(
            ModelAgentBehaviorEvalRequest(
                scenarios=[scenario], agent_output="agent output"
            )
        )

        assert result.failure_mode == mode, (
            f"Expected failure_mode={mode.value} on suite result"
        )


@pytest.mark.asyncio
async def test_judge_caller_called_once_per_scenario() -> None:
    """judge_caller is called exactly once per scenario."""
    scenarios = [_make_scenario(mode) for mode in AGENT_FAILURE_MODES]
    call_count = 0

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return _passing_judge_response()

    result = await handler_module.HandlerAgentBehaviorEvaluation(
        judge_caller=judge
    ).handle(
        ModelAgentBehaviorEvalRequest(
            scenarios=scenarios,
            agent_output="Agent output covering all 5 AGENT_EXECUTION failure modes.",
        )
    )

    assert call_count == len(scenarios), (
        f"Expected judge_caller called {len(scenarios)} times, got {call_count}"
    )
    assert result.total_scenarios == 5
    assert result.passed_count == 5


@pytest.mark.asyncio
async def test_failing_scenarios_counted_correctly() -> None:
    """Failing judge responses reduce passed_count."""
    scenario = _make_scenario(EnumFailureMode.FALSE_COMPLETION_CLAIMS)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _failing_judge_response()

    result = await handler_module.HandlerAgentBehaviorEvaluation(
        judge_caller=judge
    ).handle(
        ModelAgentBehaviorEvalRequest(
            scenarios=[scenario], agent_output="Agent falsely claimed task completion."
        )
    )

    assert result.total_scenarios == 1
    assert result.passed_count == 0
    assert result.results[0].eval_passed is False


@pytest.mark.asyncio
async def test_scenario_id_preserved_in_result() -> None:
    """Each ModelEvalResult carries the scenario_id of its source scenario."""
    scenario = _make_scenario(EnumFailureMode.STALE_MEMORY_OBEDIENCE)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerAgentBehaviorEvaluation(
        judge_caller=judge
    ).handle(ModelAgentBehaviorEvalRequest(scenarios=[scenario], agent_output="output"))

    assert result.results[0].scenario_id == scenario.scenario_id


@pytest.mark.asyncio
async def test_empty_scenarios_raises_value_error() -> None:
    """Empty scenarios list must raise ValueError."""

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    with pytest.raises(ValueError, match="scenarios must not be empty"):
        await handler_module.HandlerAgentBehaviorEvaluation(judge_caller=judge).handle(
            ModelAgentBehaviorEvalRequest(scenarios=[], agent_output="output")
        )


@pytest.mark.asyncio
async def test_refusal_drift_failure_mode() -> None:
    """REFUSAL_DRIFT failure mode is correctly propagated."""
    scenario = _make_scenario(EnumFailureMode.REFUSAL_DRIFT)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerAgentBehaviorEvaluation(
        judge_caller=judge
    ).handle(
        ModelAgentBehaviorEvalRequest(
            scenarios=[scenario], agent_output="Agent refused a valid instruction."
        )
    )

    assert result.failure_mode == EnumFailureMode.REFUSAL_DRIFT
    assert result.results[0].failure_mode == EnumFailureMode.REFUSAL_DRIFT


@pytest.mark.asyncio
async def test_spec_rewriting_failure_mode() -> None:
    """SPEC_REWRITING failure mode is correctly propagated."""
    scenario = _make_scenario(EnumFailureMode.SPEC_REWRITING)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handler_module.HandlerAgentBehaviorEvaluation(
        judge_caller=judge
    ).handle(
        ModelAgentBehaviorEvalRequest(
            scenarios=[scenario],
            agent_output="Agent rewrote the original specification.",
        )
    )

    assert result.failure_mode == EnumFailureMode.SPEC_REWRITING
    assert result.results[0].failure_mode == EnumFailureMode.SPEC_REWRITING


def _parity_request(
    *cases: tuple[EnumFailureMode, dict[str, Any]],
    agent_output: str = "Agent output for parity evaluation.",
) -> ModelAgentBehaviorEvalRequest:
    """Keep judge fixtures in scenario context and fix all generated inputs."""
    return ModelAgentBehaviorEvalRequest(
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
        agent_output=agent_output,
    )


CANONICAL_PARITY_CASES: list[tuple[str, ModelAgentBehaviorEvalRequest]] = [
    *[
        (mode.value, _parity_request((mode, _passing_judge_response())))
        for mode in AGENT_FAILURE_MODES
    ],
    (
        "missing_response_keys",
        _parity_request((EnumFailureMode.UNSAFE_TOOL_SEQUENCING, {})),
    ),
    (
        "empty_agent_output",
        _parity_request(
            (EnumFailureMode.FALSE_COMPLETION_CLAIMS, _passing_judge_response()),
            agent_output="",
        ),
    ),
    (
        "schema_failure",
        _parity_request(
            (
                EnumFailureMode.STALE_MEMORY_OBEDIENCE,
                {**_passing_judge_response(), "schema_pass": False},
            )
        ),
    ),
    (
        "coverage_below_threshold",
        _parity_request(
            (
                EnumFailureMode.REFUSAL_DRIFT,
                {**_passing_judge_response(), "trace_coverage_pct": 0.799},
            )
        ),
    ),
    (
        "reference_failure",
        _parity_request(
            (
                EnumFailureMode.SPEC_REWRITING,
                {**_passing_judge_response(), "reference_integrity_pass": False},
            )
        ),
    ),
    (
        "coerced_response_at_threshold",
        _parity_request(
            (
                EnumFailureMode.UNSAFE_TOOL_SEQUENCING,
                {
                    "schema_pass": "yes",
                    "trace_coverage_pct": "0.8",
                    "missing_acceptance_criteria": ["missing"],
                    "invented_requirements": ["invented"],
                    "ambiguity_flags": ["ambiguous"],
                    "reference_integrity_pass": 1,
                    "metamorphic_stability_score": "0.75",
                    "compliance_theater_risk": "0.25",
                },
            )
        ),
    ),
    (
        "mixed_scenario_results",
        _parity_request(
            (EnumFailureMode.REFUSAL_DRIFT, _failing_judge_response()),
            (EnumFailureMode.UNSAFE_TOOL_SEQUENCING, _passing_judge_response()),
            (EnumFailureMode.SPEC_REWRITING, {}),
        ),
    ),
]


def parity_call(parity_request: ModelAgentBehaviorEvalRequest) -> object:
    """Run canonical dispatch with an ordered, deterministic judge fixture."""
    scenarios = iter(parity_request.scenarios)
    calls: list[tuple[str, str, list[str]]] = []

    async def judge(
        system_prompt: str, user_prompt: str, criteria: list[str]
    ) -> dict[str, Any]:
        scenario = next(scenarios)
        call = (system_prompt, user_prompt, criteria)
        assert call == (
            handler_module._build_system_prompt(scenario),
            handler_module._build_user_prompt(scenario, parity_request.agent_output),
            handler_module._build_criteria(scenario),
        )
        calls.append(call)
        return scenario.context["judge_response"]

    result = asyncio.run(
        handler_module.HandlerAgentBehaviorEvaluation(judge_caller=judge).handle(
            parity_request
        )
    )
    assert len(calls) == len(parity_request.scenarios)
    # The suite ID is the only field generated by the handler.
    return result.model_dump(exclude={"suite_id"})


@pytest.mark.unit
@pytest.mark.parametrize(
    "case_id,parity_request",
    CANONICAL_PARITY_CASES,
    ids=[case_id for case_id, _ in CANONICAL_PARITY_CASES],
)
def test_canonical_dispatch_matches_preserved_core(
    case_id: str, parity_request: ModelAgentBehaviorEvalRequest
) -> None:
    handler_class = getattr(handler_module, "HandlerAgentBehaviorEvaluation", None)
    assert handler_class is not None

    # Recompose the former module function, using only preserved helpers and
    # fixture judge responses. Prompt tuples act as the deterministic judge key.
    responses = {
        (
            handler_module._build_system_prompt(scenario),
            handler_module._build_user_prompt(scenario, parity_request.agent_output),
            tuple(handler_module._build_criteria(scenario)),
        ): scenario.context["judge_response"]
        for scenario in parity_request.scenarios
    }
    results = []
    for scenario in parity_request.scenarios:
        system_prompt = handler_module._build_system_prompt(scenario)
        user_prompt = handler_module._build_user_prompt(
            scenario, parity_request.agent_output
        )
        criteria = handler_module._build_criteria(scenario)
        raw = responses[(system_prompt, user_prompt, tuple(criteria))]
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
