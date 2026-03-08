# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for two-layer contract evaluation: hard validators + LLM judge.

Two-layer evaluation flow:
1. Hard validators always run first (schema, trace_coverage, reference_integrity)
2. LLM judge always runs second, regardless of hard validator results

Both layers always run independently. eval_passed requires schema_pass=True.

Reference: OMN-4024
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalResult,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)
from omniintelligence.nodes.node_contract_eval_compute.handlers.validators import (
    validate_reference_integrity,
    validate_schema,
    validate_trace_coverage,
)


async def handle_contract_evaluation(
    contract_dict: dict[str, Any],
    scenario: ModelEvalScenario,
    ticket_requirements: list[str],
    *,
    judge_caller: Callable[[str, str, list[str]], Awaitable[dict[str, Any]]],
) -> ModelEvalResult:
    """Orchestrate two-layer contract evaluation.

    Layer 1 — Hard validators (always run, synchronous, no I/O):
        - validate_schema: checks required keys and types
        - validate_trace_coverage: ratio of requirements matched
        - validate_reference_integrity: no dangling io references

    Layer 2 — LLM judge (always run, even when schema_pass is False):
        - judge_caller: async callable receiving (prompt, output, failure_indicators)
          Returns dict with: metamorphic_stability_score, compliance_theater_risk,
          ambiguity_flags, invented_requirements, missing_acceptance_criteria

    Args:
        contract_dict: Raw contract to evaluate.
        scenario: Evaluation scenario providing context, failure_mode, scenario_id.
        ticket_requirements: Requirements to verify trace coverage against.
        judge_caller: Async callable for LLM soft evaluation. Injected to keep
            this handler pure and testable without LLM infrastructure.

    Returns:
        ModelEvalResult populated from both hard validators and LLM judge output.
    """
    # Layer 1: hard validators — always run
    schema_pass = validate_schema(contract_dict)
    trace_coverage_pct = validate_trace_coverage(contract_dict, ticket_requirements)
    reference_integrity_pass = validate_reference_integrity(contract_dict)

    # Layer 2: LLM judge — always runs, even when schema_pass is False
    description = str(contract_dict.get("description", ""))
    failure_indicators = _get_failure_indicators(scenario.failure_mode)

    judge_output = await judge_caller(
        scenario.input_text,
        description,
        failure_indicators,
    )

    # Extract soft scores from judge output
    metamorphic_stability_score = float(
        judge_output.get("metamorphic_stability_score", 0.0)
    )
    compliance_theater_risk = float(judge_output.get("compliance_theater_risk", 0.0))
    ambiguity_flags: list[str] = list(judge_output.get("ambiguity_flags", []))
    invented_requirements: list[str] = list(
        judge_output.get("invented_requirements", [])
    )
    missing_acceptance_criteria: list[str] = list(
        judge_output.get("missing_acceptance_criteria", [])
    )

    return ModelEvalResult(
        schema_pass=schema_pass,
        trace_coverage_pct=trace_coverage_pct,
        missing_acceptance_criteria=missing_acceptance_criteria,
        invented_requirements=invented_requirements,
        ambiguity_flags=ambiguity_flags,
        reference_integrity_pass=reference_integrity_pass,
        metamorphic_stability_score=metamorphic_stability_score,
        compliance_theater_risk=compliance_theater_risk,
        failure_mode=scenario.failure_mode,
        scenario_id=scenario.scenario_id,
    )


def _get_failure_indicators(failure_mode: EnumFailureMode) -> list[str]:
    """Return canonical failure indicators for a given failure mode.

    Used as the hint list passed to the LLM judge.
    """
    _INDICATORS: dict[EnumFailureMode, list[str]] = {
        EnumFailureMode.REQUIREMENT_OMISSION: [
            "missing requirement",
            "incomplete specification",
            "omitted acceptance criteria",
        ],
        EnumFailureMode.INVENTED_REQUIREMENTS: [
            "invented requirement",
            "hallucinated constraint",
            "unsourced acceptance criteria",
        ],
        EnumFailureMode.TRACEABILITY_FAILURE: [
            "missing trace link",
            "untraced acceptance criteria",
            "broken traceability",
        ],
        EnumFailureMode.PARAPHRASE_INSTABILITY: [
            "structural inconsistency",
            "paraphrase divergence",
            "unstable output",
        ],
        EnumFailureMode.COMPLIANCE_THEATER: [
            "checkbox compliance",
            "superficial adherence",
            "compliance theater",
        ],
    }
    return _INDICATORS.get(failure_mode, ["evaluation failure", "unexpected output"])


__all__ = ["handle_contract_evaluation"]
