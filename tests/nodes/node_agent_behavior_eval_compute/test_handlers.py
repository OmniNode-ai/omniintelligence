# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for handle_agent_behavior_evaluation handler.

Acceptance criteria verified:
- Handler name is exactly ``handle_agent_behavior_evaluation``
- Returns ``ModelEvalSuiteResult`` with ``failure_mode`` from first scenario
- ``judge_caller`` called once per scenario (mock asserts ``call_count == len(scenarios)``)
- Node passes thin-shell audit (verified by test_node_purity.py suite)
- contract.yaml declares node_type: COMPUTE_GENERIC
- pytest tests/nodes/node_agent_behavior_eval_compute/test_handlers.py -v passes
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_agent_behavior_eval_compute.handlers.handler_agent_behavior_evaluation import (
    handle_agent_behavior_evaluation,
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
async def test_handle_agent_behavior_evaluation_returns_suite_result() -> None:
    """Handler returns a ModelEvalSuiteResult."""
    scenario = _make_scenario(EnumFailureMode.UNSAFE_TOOL_SEQUENCING)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handle_agent_behavior_evaluation(
        scenarios=[scenario],
        agent_output="The agent executed tools in the correct order.",
        judge_caller=judge,
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

        result = await handle_agent_behavior_evaluation(
            scenarios=[scenario],
            agent_output="agent output",
            judge_caller=judge,
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

    result = await handle_agent_behavior_evaluation(
        scenarios=scenarios,
        agent_output="Agent output covering all 5 AGENT_EXECUTION failure modes.",
        judge_caller=judge,
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

    result = await handle_agent_behavior_evaluation(
        scenarios=[scenario],
        agent_output="Agent falsely claimed task completion.",
        judge_caller=judge,
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

    result = await handle_agent_behavior_evaluation(
        scenarios=[scenario],
        agent_output="output",
        judge_caller=judge,
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
        await handle_agent_behavior_evaluation(
            scenarios=[],
            agent_output="output",
            judge_caller=judge,
        )


@pytest.mark.asyncio
async def test_refusal_drift_failure_mode() -> None:
    """REFUSAL_DRIFT failure mode is correctly propagated."""
    scenario = _make_scenario(EnumFailureMode.REFUSAL_DRIFT)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handle_agent_behavior_evaluation(
        scenarios=[scenario],
        agent_output="Agent refused a valid instruction.",
        judge_caller=judge,
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

    result = await handle_agent_behavior_evaluation(
        scenarios=[scenario],
        agent_output="Agent rewrote the original specification.",
        judge_caller=judge,
    )

    assert result.failure_mode == EnumFailureMode.SPEC_REWRITING
    assert result.results[0].failure_mode == EnumFailureMode.SPEC_REWRITING
