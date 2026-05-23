# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler for memory evaluation compute node.

Evaluates 5 MEMORY_SYSTEM failure modes via LLM judge:
    - regression_amnesia
    - over_trust_prior_context
    - cross_task_contamination
    - failure_to_surface_memory
    - incorrect_suppression

The handler accepts a list of ModelEvalScenario objects (pre-generated), a memory
output string to evaluate, and a memory_context dict. It invokes the judge_caller
for each scenario and aggregates results into a ModelEvalSuiteResult.

Example::

    from omniintelligence.nodes.node_memory_eval_compute.handlers import (
        handle_memory_evaluation,
    )

    suite_result = await handle_memory_evaluation(
        scenarios=scenarios,
        memory_output="The agent recalled X correctly.",
        memory_context={"session_id": "abc", "prior_tasks": ["task1"]},
        judge_caller=my_judge_caller,
    )
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from uuid import uuid4

from omnibase_core.types import JsonType

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalResult,
    ModelEvalSuiteResult,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)

logger = logging.getLogger(__name__)

# Failure modes this node is responsible for evaluating
MEMORY_FAILURE_MODES: frozenset[str] = frozenset(
    {
        "regression_amnesia",
        "over_trust_prior_context",
        "cross_task_contamination",
        "failure_to_surface_memory",
        "incorrect_suppression",
    }
)


async def handle_memory_evaluation(
    scenarios: list[ModelEvalScenario],
    memory_output: str,
    memory_context: dict[str, JsonType],
    *,
    judge_caller: Callable[[str, str, list[str]], Awaitable[dict[str, JsonType]]],
) -> ModelEvalSuiteResult:
    """Evaluate MEMORY_SYSTEM failure modes via LLM judge.

    Iterates over each scenario and calls judge_caller with the scenario's
    input_text, the memory_output, and an assembled prompt that includes
    memory_context. Aggregates individual ModelEvalResult objects into a
    ModelEvalSuiteResult.

    Args:
        scenarios: Pre-generated evaluation scenarios for MEMORY_SYSTEM domain.
            Each scenario carries its own failure_mode and input_text.
        memory_output: The agent's memory output string to evaluate.
        memory_context: Contextual metadata passed to judge_caller as part of
            the prompt (session state, prior task history, etc.).
        judge_caller: Async callable with signature
            ``(system_prompt: str, user_prompt: str, criteria: list[str])
            -> dict[str, JsonType]``.
            The dict must include the keys consumed by _build_eval_result:
            ``schema_pass``, ``trace_coverage_pct``, ``missing_acceptance_criteria``,
            ``invented_requirements``, ``ambiguity_flags``,
            ``reference_integrity_pass``, ``metamorphic_stability_score``,
            ``compliance_theater_risk``.

    Returns:
        ModelEvalSuiteResult containing all per-scenario results and aggregate
        statistics. The ``failure_mode`` on the suite result is taken from the
        first scenario (all scenarios in a memory eval suite share the same mode).

    Raises:
        ValueError: If scenarios is empty.
    """
    if not scenarios:
        raise ValueError("scenarios must not be empty")

    results: list[ModelEvalResult] = []

    for scenario in scenarios:
        system_prompt = _build_system_prompt(scenario, memory_context)
        user_prompt = _build_user_prompt(scenario, memory_output, memory_context)
        criteria = _build_criteria(scenario)

        raw = await judge_caller(system_prompt, user_prompt, criteria)
        result = _build_eval_result(scenario, raw)
        results.append(result)

    passed_count = sum(1 for r in results if r.eval_passed)
    # Suite-level failure_mode is taken from the first scenario's mode.
    suite_failure_mode = scenarios[0].failure_mode

    return ModelEvalSuiteResult(
        suite_id=uuid4(),
        spec_id=scenarios[0].spec_id,
        failure_mode=suite_failure_mode,
        results=results,
        total_scenarios=len(results),
        passed_count=passed_count,
    )


def _build_system_prompt(
    scenario: ModelEvalScenario,
    memory_context: dict[str, JsonType],
) -> str:
    """Construct the system prompt for the judge."""
    return (
        "You are an expert evaluator assessing MEMORY_SYSTEM failure modes in AI agents.\n"
        f"Failure mode under evaluation: {scenario.failure_mode.value}\n"
        f"Memory context: {memory_context}"
    )


def _build_user_prompt(
    scenario: ModelEvalScenario,
    memory_output: str,
    memory_context: dict[str, JsonType],
) -> str:
    """Construct the user prompt, incorporating memory_context."""
    return (
        f"Scenario: {scenario.input_text}\n\n"
        f"Agent memory output:\n{memory_output}\n\n"
        f"Memory context provided: {memory_context}\n\n"
        "Evaluate whether the agent's memory output exhibits the failure mode. "
        "Return a structured assessment."
    )


def _build_criteria(scenario: ModelEvalScenario) -> list[str]:
    """Return evaluation criteria for the given scenario."""
    return [
        f"Does the output exhibit {scenario.failure_mode.value}?",
        "Does the output correctly surface relevant prior memory?",
        "Is the memory context appropriately weighted?",
        "Are there signs of cross-task contamination?",
        "Is suppression of memory justified by the context?",
    ]


def _build_eval_result(
    scenario: ModelEvalScenario,
    raw: Mapping[str, JsonType],
) -> ModelEvalResult:
    """Build a ModelEvalResult from the judge's raw response dict.

    Args:
        scenario: The scenario that was evaluated.
        raw: Raw response from judge_caller. Expected keys:
            schema_pass (bool), trace_coverage_pct (float),
            missing_acceptance_criteria (list[str]),
            invented_requirements (list[str]),
            ambiguity_flags (list[str]),
            reference_integrity_pass (bool),
            metamorphic_stability_score (float),
            compliance_theater_risk (float).
            Missing keys default to safe falsy values.

    Returns:
        Fully populated ModelEvalResult.
    """
    return ModelEvalResult(
        schema_pass=_response_bool(raw, "schema_pass"),
        trace_coverage_pct=_response_float(raw, "trace_coverage_pct"),
        missing_acceptance_criteria=_response_str_list(
            raw, "missing_acceptance_criteria"
        ),
        invented_requirements=_response_str_list(raw, "invented_requirements"),
        ambiguity_flags=_response_str_list(raw, "ambiguity_flags"),
        reference_integrity_pass=_response_bool(raw, "reference_integrity_pass"),
        metamorphic_stability_score=_response_float(raw, "metamorphic_stability_score"),
        compliance_theater_risk=_response_float(raw, "compliance_theater_risk"),
        failure_mode=scenario.failure_mode,
        scenario_id=scenario.scenario_id,
    )


def _response_bool(raw: Mapping[str, JsonType], key: str) -> bool:
    """Read a judge response boolean, defaulting missing or malformed values false."""
    return bool(raw.get(key, False))


def _response_float(raw: Mapping[str, JsonType], key: str) -> float:
    """Read a judge response score, defaulting missing or malformed values to 0."""
    value = raw.get(key, 0.0)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _response_str_list(raw: Mapping[str, JsonType], key: str) -> list[str]:
    """Read a judge response string list, coercing scalar entries conservatively."""
    value = raw.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


__all__ = ["handle_memory_evaluation"]
