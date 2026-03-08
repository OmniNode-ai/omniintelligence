# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Tests for handler_scenario_generation.

Acceptance criteria verified:
- Handler returns exactly n ModelEvalScenario objects
- scenario.spec_id == spec.spec_id for all returned scenarios
- scenario.failure_mode == spec.failure_mode for all returned scenarios
- Mock llm_caller returns ["scenario text"] * n; test asserts len(result) == n
"""

from __future__ import annotations

import pytest

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


def _make_spec(
    failure_mode: EnumFailureMode = EnumFailureMode.REQUIREMENT_OMISSION,
) -> ModelBehaviorSpec:
    return ModelBehaviorSpec(
        failure_mode=failure_mode,
        domain=EnumEvalDomain.CONTRACT_CREATION,
        description="Test spec for scenario generation",
        scenario_prompt_template="Generate a scenario for requirement omission",
        expected_behavior="All requirements are captured",
        failure_indicators=["missing requirement", "omitted acceptance criteria"],
    )


async def _mock_llm_caller(_prompt_template: str, n: int) -> list[str]:
    return ["scenario text"] * n


@pytest.mark.unit
async def test_returns_exactly_n_scenarios() -> None:
    spec = _make_spec()
    result = await handle_scenario_generation(spec, n=5, llm_caller=_mock_llm_caller)
    assert len(result) == 5


@pytest.mark.unit
async def test_all_scenarios_have_correct_spec_id() -> None:
    spec = _make_spec()
    result = await handle_scenario_generation(spec, n=3, llm_caller=_mock_llm_caller)
    for scenario in result:
        assert scenario.spec_id == spec.spec_id


@pytest.mark.unit
async def test_all_scenarios_have_correct_failure_mode() -> None:
    spec = _make_spec(failure_mode=EnumFailureMode.STALE_MEMORY_OBEDIENCE)
    result = await handle_scenario_generation(spec, n=3, llm_caller=_mock_llm_caller)
    for scenario in result:
        assert scenario.failure_mode == EnumFailureMode.STALE_MEMORY_OBEDIENCE


@pytest.mark.unit
async def test_returns_model_eval_scenario_instances() -> None:
    spec = _make_spec()
    result = await handle_scenario_generation(spec, n=2, llm_caller=_mock_llm_caller)
    for scenario in result:
        assert isinstance(scenario, ModelEvalScenario)


@pytest.mark.unit
async def test_single_scenario() -> None:
    spec = _make_spec()
    result = await handle_scenario_generation(spec, n=1, llm_caller=_mock_llm_caller)
    assert len(result) == 1
    assert result[0].spec_id == spec.spec_id


@pytest.mark.unit
async def test_input_text_populated_from_llm_caller() -> None:
    spec = _make_spec()

    async def custom_caller(_prompt: str, n: int) -> list[str]:
        return [f"custom scenario {i}" for i in range(n)]

    result = await handle_scenario_generation(spec, n=3, llm_caller=custom_caller)
    input_texts = [s.input_text for s in result]
    assert input_texts == [
        "custom scenario 0",
        "custom scenario 1",
        "custom scenario 2",
    ]


@pytest.mark.unit
async def test_llm_caller_called_with_prompt_template() -> None:
    spec = _make_spec()
    captured: list[tuple[str, int]] = []

    async def capturing_caller(prompt: str, n: int) -> list[str]:
        captured.append((prompt, n))
        return ["scenario text"] * n

    await handle_scenario_generation(spec, n=4, llm_caller=capturing_caller)
    assert len(captured) == 1
    assert captured[0] == (spec.scenario_prompt_template, 4)
