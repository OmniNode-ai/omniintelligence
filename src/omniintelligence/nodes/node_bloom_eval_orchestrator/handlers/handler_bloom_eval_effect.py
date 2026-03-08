# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler for Bloom assessment effect orchestration.

Orchestrates: ScenarioGenerator -> domain handler -> publish result.
Routes based on failure_mode.domain to CONTRACT_CREATION, AGENT_EXECUTION,
or MEMORY_SYSTEM assessment path.

This handler does NOT return a typed result. All output is published via
the injected Kafka producer to:
  onex.evt.omniintelligence.bloom-eval-completed.v1

ARCH-002 compliant: env vars not read directly. All config injected.

Reference: OMN-4027 - Task 11: Build NodeBloomEvalEffect + Kafka topics
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.clients.eval_llm_client import EvalLLMClient
from omniintelligence.nodes.node_bloom_eval_orchestrator.catalog import get_spec
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_eval_domain import (
    EnumEvalDomain,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.enum_failure_mode import (
    FAILURE_MODE_DOMAIN,
    EnumFailureMode,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalResult,
    ModelEvalSuiteResult,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)
from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

_BLOOM_COMPLETED_TOPIC = "onex.evt.omniintelligence.bloom-eval-completed.v1"
_DEFAULT_SCENARIOS_PER_SPEC = 5
_PASS_SCORE_THRESHOLD = 0.5


class ModelBloomEvalRunCommand(BaseModel):
    """Command to run a bloom assessment suite for a given failure mode.

    Published to onex.cmd.omniintelligence.bloom-eval-run.v1.
    """

    model_config = ConfigDict(frozen=True)

    command_id: UUID = Field(default_factory=uuid4)
    failure_mode: EnumFailureMode
    spec_id: UUID | None = None
    suite_id: UUID = Field(default_factory=uuid4)
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    scenarios_per_spec: int = _DEFAULT_SCENARIOS_PER_SPEC
    publish_topic: str = _BLOOM_COMPLETED_TOPIC


def _build_suite_result(
    suite_id: UUID,
    failure_mode: EnumFailureMode,
    results: list[ModelEvalResult],
) -> ModelEvalSuiteResult:
    spec = get_spec(failure_mode)
    passed = sum(1 for r in results if r.eval_passed)
    return ModelEvalSuiteResult(
        suite_id=suite_id,
        spec_id=spec.spec_id,
        failure_mode=failure_mode,
        results=results,
        total_scenarios=len(results),
        passed_count=passed,
    )


async def _run_contract_path(
    command: ModelBloomEvalRunCommand,
    llm_client: EvalLLMClient,
) -> list[ModelEvalResult]:
    """Run CONTRACT_CREATION domain assessment."""
    spec = get_spec(command.failure_mode)
    raw_scenarios = await llm_client.generate_scenarios(
        spec.scenario_prompt_template,
        n=command.scenarios_per_spec,
    )
    results: list[ModelEvalResult] = []
    for raw in raw_scenarios:
        scenario = ModelEvalScenario(
            spec_id=spec.spec_id,
            failure_mode=command.failure_mode,
            input_text=raw,
            context={},
        )
        judgment = await llm_client.judge_output(
            prompt=spec.scenario_prompt_template,
            output=raw,
            failure_indicators=spec.failure_indicators,
        )
        stability_score = float(judgment.get("metamorphic_stability_score", 0.8))
        results.append(
            ModelEvalResult(
                schema_pass=bool(judgment.get("schema_pass", True)),
                trace_coverage_pct=stability_score,
                missing_acceptance_criteria=list(
                    judgment.get("missing_acceptance_criteria", [])
                ),
                invented_requirements=list(judgment.get("invented_requirements", [])),
                ambiguity_flags=list(judgment.get("ambiguity_flags", [])),
                reference_integrity_pass=(stability_score >= _PASS_SCORE_THRESHOLD),
                metamorphic_stability_score=stability_score,
                compliance_theater_risk=float(
                    judgment.get("compliance_theater_risk", 0.2)
                ),
                failure_mode=command.failure_mode,
                scenario_id=scenario.scenario_id,
            )
        )
    return results


async def _run_agent_path(
    command: ModelBloomEvalRunCommand,
    llm_client: EvalLLMClient,
) -> list[ModelEvalResult]:
    """Run AGENT_EXECUTION domain assessment.

    Delegates to the same scenario-and-judgment loop as contract path.
    Domain-specific logic will be layered in when NodeAgentBehaviorEvalCompute
    (OMN-4025) is integrated.
    """
    return await _run_contract_path(command, llm_client)


async def _run_memory_path(
    command: ModelBloomEvalRunCommand,
    llm_client: EvalLLMClient,
) -> list[ModelEvalResult]:
    """Run MEMORY_SYSTEM domain assessment.

    Delegates to the same scenario-and-judgment loop as contract path.
    Domain-specific logic will be layered in when NodeMemoryEvalCompute
    (OMN-4026) is integrated.
    """
    return await _run_contract_path(command, llm_client)


_DomainHandler = Callable[
    [ModelBloomEvalRunCommand, EvalLLMClient],
    Coroutine[Any, Any, list[ModelEvalResult]],
]

_DOMAIN_DISPATCH: dict[EnumEvalDomain, _DomainHandler] = {
    EnumEvalDomain.CONTRACT_CREATION: _run_contract_path,
    EnumEvalDomain.AGENT_EXECUTION: _run_agent_path,
    EnumEvalDomain.MEMORY_SYSTEM: _run_memory_path,
}


async def run_bloom_eval(
    command: ModelBloomEvalRunCommand,
    *,
    producer: ProtocolKafkaPublisher,
    llm_client: EvalLLMClient,
) -> None:
    """Orchestrate a bloom assessment suite and publish the result.

    Routes to the correct domain handler based on command.failure_mode.domain,
    then publishes the ModelEvalSuiteResult payload to Kafka.

    Does NOT return a typed result - all output is published via producer.

    Args:
        command: Bloom run command specifying failure_mode and parameters.
        producer: Kafka publisher for emitting bloom-eval-completed events.
        llm_client: LLM client for scenario generation and judgment.
    """
    domain = FAILURE_MODE_DOMAIN[command.failure_mode]
    domain_handler = _DOMAIN_DISPATCH[domain]

    logger.info(
        "bloom_eval: starting suite=%s failure_mode=%s domain=%s",
        command.suite_id,
        command.failure_mode.value,
        domain.value,
    )

    results: list[ModelEvalResult] = await domain_handler(command, llm_client)
    suite_result = _build_suite_result(
        suite_id=command.suite_id,
        failure_mode=command.failure_mode,
        results=results,
    )

    payload: dict[str, object] = {
        "event_type": "BloomEvalCompleted",
        "suite_id": str(suite_result.suite_id),
        "spec_id": str(suite_result.spec_id),
        "failure_mode": suite_result.failure_mode.value,
        "total_scenarios": suite_result.total_scenarios,
        "passed_count": suite_result.passed_count,
        "failure_rate": suite_result.failure_rate,
        "passed_threshold": suite_result.passed_threshold,
        "correlation_id": command.correlation_id,
        "emitted_at": datetime.now(UTC).isoformat(),
    }

    await producer.publish(
        topic=command.publish_topic,
        key=str(command.suite_id),
        value=payload,
    )

    logger.info(
        "bloom_eval: completed suite=%s failure_rate=%.2f passed_threshold=%s",
        command.suite_id,
        suite_result.failure_rate,
        suite_result.passed_threshold,
    )


__all__ = [
    "ModelBloomEvalRunCommand",
    "run_bloom_eval",
]
