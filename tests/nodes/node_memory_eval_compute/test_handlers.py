# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for handle_memory_evaluation handler.

Acceptance criteria verified:
- Handler name is exactly ``handle_memory_evaluation``
- ``memory_context`` is passed to judge_caller (mock receives it as part of prompt)
- Returns ``ModelEvalSuiteResult`` with correct ``failure_mode``
- Node passes thin-shell audit (verified by test_node_purity.py suite)
- contract.yaml declares node_type: COMPUTE_GENERIC
- pytest tests/nodes/node_memory_eval_compute/test_handlers.py -v passes
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalSuiteResult,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)
from omniintelligence.nodes.node_memory_eval_compute.handlers.handler_memory_evaluation import (
    handle_memory_evaluation,
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
async def test_handle_memory_evaluation_returns_suite_result() -> None:
    """Handler returns a ModelEvalSuiteResult."""
    scenario = _make_scenario(EnumFailureMode.REGRESSION_AMNESIA)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handle_memory_evaluation(
        scenarios=[scenario],
        memory_output="Agent recalled prior context correctly.",
        memory_context={"session": "abc"},
        judge_caller=judge,
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

        result = await handle_memory_evaluation(
            scenarios=[scenario],
            memory_output="output",
            memory_context={},
            judge_caller=judge,
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

    await handle_memory_evaluation(
        scenarios=[scenario],
        memory_output="some output",
        memory_context=expected_context,
        judge_caller=judge,
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

    result = await handle_memory_evaluation(
        scenarios=scenarios,
        memory_output="Memory output covering all 5 failure modes.",
        memory_context={"run_id": "test-run"},
        judge_caller=judge,
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

    result = await handle_memory_evaluation(
        scenarios=[scenario],
        memory_output="Agent contaminated output with prior task state.",
        memory_context={},
        judge_caller=judge,
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

    result = await handle_memory_evaluation(
        scenarios=[scenario],
        memory_output="output",
        memory_context={},
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
        await handle_memory_evaluation(
            scenarios=[],
            memory_output="output",
            memory_context={},
            judge_caller=judge,
        )


@pytest.mark.asyncio
async def test_incorrect_suppression_failure_mode() -> None:
    """INCORRECT_SUPPRESSION failure mode is correctly propagated."""
    scenario = _make_scenario(EnumFailureMode.INCORRECT_SUPPRESSION)

    async def judge(
        _system_prompt: str, _user_prompt: str, _criteria: list[str]
    ) -> dict[str, Any]:
        return _passing_judge_response()

    result = await handle_memory_evaluation(
        scenarios=[scenario],
        memory_output="Agent incorrectly suppressed relevant memory.",
        memory_context={"suppression_context": "task_b_overrides"},
        judge_caller=judge,
    )

    assert result.failure_mode == EnumFailureMode.INCORRECT_SUPPRESSION
    assert result.results[0].failure_mode == EnumFailureMode.INCORRECT_SUPPRESSION
