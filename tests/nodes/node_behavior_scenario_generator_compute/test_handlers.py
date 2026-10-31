# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for HandlerScenarioGeneration.

Acceptance criteria verified:
- Handler returns exactly n ModelEvalScenario objects
- scenario.spec_id == spec.spec_id for all returned scenarios
- scenario.failure_mode == spec.failure_mode for all returned scenarios
- Mock llm_caller returns ["scenario text"] * n; test asserts len(result.scenarios) == n
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

import omniintelligence.nodes.node_behavior_scenario_generator_compute.handlers.handler_scenario_generator as handler_module
from omniintelligence.nodes.node_behavior_scenario_generator_compute.models import (
    ModelScenarioGenerationRequest,
    ModelScenarioGenerationResponse,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    FAILURE_MODE_DOMAIN,
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
    result = await handler_module.HandlerScenarioGeneration(
        llm_caller=_mock_llm_caller
    ).handle(ModelScenarioGenerationRequest(spec=spec, n=5))
    assert len(result.scenarios) == 5


@pytest.mark.unit
async def test_all_scenarios_have_correct_spec_id() -> None:
    spec = _make_spec()
    result = await handler_module.HandlerScenarioGeneration(
        llm_caller=_mock_llm_caller
    ).handle(ModelScenarioGenerationRequest(spec=spec, n=3))
    for scenario in result.scenarios:
        assert scenario.spec_id == spec.spec_id


@pytest.mark.unit
async def test_all_scenarios_have_correct_failure_mode() -> None:
    spec = _make_spec(failure_mode=EnumFailureMode.STALE_MEMORY_OBEDIENCE)
    result = await handler_module.HandlerScenarioGeneration(
        llm_caller=_mock_llm_caller
    ).handle(ModelScenarioGenerationRequest(spec=spec, n=3))
    for scenario in result.scenarios:
        assert scenario.failure_mode == EnumFailureMode.STALE_MEMORY_OBEDIENCE


@pytest.mark.unit
async def test_returns_model_eval_scenario_instances() -> None:
    spec = _make_spec()
    result = await handler_module.HandlerScenarioGeneration(
        llm_caller=_mock_llm_caller
    ).handle(ModelScenarioGenerationRequest(spec=spec, n=2))
    for scenario in result.scenarios:
        assert isinstance(scenario, ModelEvalScenario)


@pytest.mark.unit
async def test_single_scenario() -> None:
    spec = _make_spec()
    result = await handler_module.HandlerScenarioGeneration(
        llm_caller=_mock_llm_caller
    ).handle(ModelScenarioGenerationRequest(spec=spec, n=1))
    assert len(result.scenarios) == 1
    assert result.scenarios[0].spec_id == spec.spec_id


@pytest.mark.unit
async def test_input_text_populated_from_llm_caller() -> None:
    spec = _make_spec()

    async def custom_caller(_prompt: str, n: int) -> list[str]:
        return [f"custom scenario {i}" for i in range(n)]

    result = await handler_module.HandlerScenarioGeneration(
        llm_caller=custom_caller
    ).handle(ModelScenarioGenerationRequest(spec=spec, n=3))
    input_texts = [s.input_text for s in result.scenarios]
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

    await handler_module.HandlerScenarioGeneration(llm_caller=capturing_caller).handle(
        ModelScenarioGenerationRequest(spec=spec, n=4)
    )
    assert len(captured) == 1
    assert captured[0] == (spec.scenario_prompt_template, 4)


def _parity_request(
    prompt: str,
    n: int,
    failure_mode: EnumFailureMode = EnumFailureMode.REQUIREMENT_OMISSION,
) -> ModelScenarioGenerationRequest:
    return ModelScenarioGenerationRequest(
        spec=ModelBehaviorSpec(
            spec_id=UUID(int=101),
            failure_mode=failure_mode,
            domain=FAILURE_MODE_DOMAIN[failure_mode],
            description="Deterministic parity spec",
            scenario_prompt_template=prompt,
            expected_behavior="Preserve the specification and generated text.",
            failure_indicators=[],
        ),
        n=n,
    )


CANONICAL_PARITY_CASES: list[tuple[str, ModelScenarioGenerationRequest]] = [
    ("contract_single", _parity_request("Contract scenario", 1)),
    (
        "agent_multiple",
        _parity_request("Agent scenario", 3, EnumFailureMode.UNSAFE_TOOL_SEQUENCING),
    ),
    (
        "memory_multiple",
        _parity_request("Memory scenario", 2, EnumFailureMode.REGRESSION_AMNESIA),
    ),
    ("zero_requested", _parity_request("No scenarios requested", 0)),
    ("negative_requested", _parity_request("Negative count", -1)),
    ("many_scenarios", _parity_request("Many scenarios", 8)),
    ("empty_prompt", _parity_request("", 1)),
    ("unicode_multiline", _parity_request("Scénario: 記憶\n{context}", 2)),
    ("empty_llm_response", _parity_request("empty_response", 3)),
    ("short_llm_response", _parity_request("short_response", 3)),
    ("extra_llm_response", _parity_request("extra_response", 1)),
    ("empty_scenario_text", _parity_request("empty_text", 2)),
]


def _parity_llm_texts(prompt: str, n: int) -> list[str]:
    """Script edge responses without clocks, randomness, or external calls."""
    if prompt == "empty_response":
        return []
    if prompt == "short_response":
        return [f"Scenario {index}" for index in range(max(0, n - 1))]
    if prompt == "extra_response":
        return [f"Scenario {index}" for index in range(n + 1)]
    if prompt == "empty_text":
        return [""] * n
    return [f"{prompt}\nScenario {index}" for index in range(n)]


def parity_call(parity_request: ModelScenarioGenerationRequest) -> object:
    """Run dispatch and omit only per-scenario generated IDs and timestamps."""
    calls: list[tuple[str, int]] = []

    async def llm_caller(prompt: str, n: int) -> list[str]:
        calls.append((prompt, n))
        return _parity_llm_texts(prompt, n)

    result = asyncio.run(
        handler_module.HandlerScenarioGeneration(llm_caller=llm_caller).handle(
            parity_request
        )
    )
    assert calls == [(parity_request.spec.scenario_prompt_template, parity_request.n)]
    return result.model_dump(
        exclude={"scenarios": {"__all__": {"scenario_id", "generated_at"}}}
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "case_id,parity_request",
    CANONICAL_PARITY_CASES,
    ids=[case_id for case_id, _ in CANONICAL_PARITY_CASES],
)
def test_canonical_dispatch_matches_preserved_core(
    case_id: str, parity_request: ModelScenarioGenerationRequest
) -> None:
    handler_class = getattr(handler_module, "HandlerScenarioGeneration", None)
    assert handler_class is not None

    async def llm_caller(prompt: str, n: int) -> list[str]:
        return _parity_llm_texts(prompt, n)

    expected = ModelScenarioGenerationResponse(
        scenarios=asyncio.run(
            handler_module.handle_scenario_generation(
                parity_request.spec, parity_request.n, llm_caller=llm_caller
            )
        )
    ).model_dump(exclude={"scenarios": {"__all__": {"scenario_id", "generated_at"}}})
    assert parity_call(parity_request) == expected, case_id
