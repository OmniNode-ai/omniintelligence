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

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from omnibase_core.models.container import ModelONEXContainer
from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.clients.eval_llm_client import EvalLLMClient
from omniintelligence.constants import TOPIC_BLOOM_EVAL_COMPLETED_V1
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
from omniintelligence.nodes.node_contract_eval_compute.models import (
    ModelContractEvalInput,
)
from omniintelligence.nodes.node_contract_eval_compute.node import (
    NodeContractEvalCompute,
)
from omniintelligence.nodes.node_memory_eval_compute.models import ModelMemoryEvalInput
from omniintelligence.nodes.node_memory_eval_compute.node import NodeMemoryEvalCompute
from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

_BLOOM_COMPLETED_TOPIC = TOPIC_BLOOM_EVAL_COMPLETED_V1
_DEFAULT_SCENARIOS_PER_SPEC = 5
_PASS_SCORE_THRESHOLD = 0.5

# Module-level set keeps strong references to background publish tasks so the
# event loop cannot GC them before they complete. Tasks remove themselves on done.
_background_tasks: set[asyncio.Task[None]] = set()


class ProtocolContractEvalCompute(Protocol):
    async def compute(self, input_data: ModelContractEvalInput) -> ModelEvalResult: ...


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
    memory_output: str = ""
    memory_context: dict[str, Any] = Field(default_factory=dict)


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
    *,
    contract_eval_node: ProtocolContractEvalCompute | None = None,
) -> list[ModelEvalResult]:
    """Run CONTRACT_CREATION domain assessment."""
    spec = get_spec(command.failure_mode)
    raw_scenarios = await llm_client.generate_scenarios(
        spec.scenario_prompt_template,
        n=command.scenarios_per_spec,
    )
    node = contract_eval_node or NodeContractEvalCompute(
        ModelONEXContainer(enable_service_registry=False)
    )
    results: list[ModelEvalResult] = []
    for raw in raw_scenarios:
        scenario = ModelEvalScenario(
            spec_id=spec.spec_id,
            failure_mode=command.failure_mode,
            input_text=raw,
            context={},
        )
        result = await node.compute(
            ModelContractEvalInput(
                contract_dict=_contract_dict_from_generated_text(
                    raw,
                    expected_behavior=spec.expected_behavior,
                ),
                scenario=scenario,
                ticket_requirements=[spec.expected_behavior],
                judge_caller=llm_client.judge_output,
            )
        )
        results.append(result)
    return results


def _contract_dict_from_generated_text(
    generated_text: str,
    *,
    expected_behavior: str,
) -> dict[str, Any]:
    """Materialize generated contract text into the hard-validator input shape."""
    return {
        "node_type": "COMPUTE_GENERIC",
        "contract_id": "bloom-contract-eval",
        "title": "Bloom Contract Evaluation Candidate",
        "description": f"{generated_text}\n\nExpected behavior: {expected_behavior}",
        "io": {"input_fields": [], "output_fields": []},
        "environment_variables": [],
        "acceptance_criteria": expected_behavior,
    }


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

    Generates memory-domain scenarios, then delegates judgment and aggregation
    to NodeMemoryEvalCompute so MEMORY_SYSTEM behavior uses its dedicated
    compute node instead of the generic contract path.
    """
    spec = get_spec(command.failure_mode)
    raw_scenarios = await llm_client.generate_scenarios(
        spec.scenario_prompt_template,
        n=command.scenarios_per_spec,
    )
    scenarios = [
        ModelEvalScenario(
            spec_id=spec.spec_id,
            failure_mode=command.failure_mode,
            input_text=raw,
            context=dict(command.memory_context),
        )
        for raw in raw_scenarios
    ]

    async def _judge_caller(
        system_prompt: str,
        user_prompt: str,
        criteria: list[str],
    ) -> dict[str, Any]:
        return await llm_client.judge_output(
            prompt=system_prompt,
            output=user_prompt,
            failure_indicators=criteria,
        )

    memory_node = NodeMemoryEvalCompute(ModelONEXContainer())
    suite_result = await memory_node.compute(
        ModelMemoryEvalInput(
            scenarios=scenarios,
            memory_output=command.memory_output,
            memory_context=command.memory_context,
            judge_caller=_judge_caller,
        )
    )
    return suite_result.results


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
    producer: ProtocolKafkaPublisher | None = None,
    llm_client: EvalLLMClient,
    contract_eval_node: ProtocolContractEvalCompute | None = None,
) -> None:
    """Orchestrate a bloom assessment suite and publish the result.

    Routes to the correct domain handler based on command.failure_mode.domain,
    then fire-and-forgets the ModelEvalSuiteResult payload to Kafka when a
    producer is available. The handler completes successfully even when no
    producer is injected (Kafka is optional for effect nodes).

    Args:
        command: Bloom run command specifying failure_mode and parameters.
        producer: Optional Kafka publisher for emitting bloom-eval-completed
            events. When None, the publish step is skipped.
        llm_client: LLM client for scenario generation and judgment.
    """
    correlation_id = command.correlation_id
    domain = FAILURE_MODE_DOMAIN[command.failure_mode]
    domain_handler = _DOMAIN_DISPATCH[domain]

    logger.info(
        "bloom_eval: starting suite=%s failure_mode=%s domain=%s",
        command.suite_id,
        command.failure_mode.value,
        domain.value,
        extra={"correlation_id": correlation_id},
    )

    if domain is EnumEvalDomain.CONTRACT_CREATION:
        results = await _run_contract_path(
            command,
            llm_client,
            contract_eval_node=contract_eval_node,
        )
    else:
        results = await domain_handler(command, llm_client)
    suite_result = _build_suite_result(
        suite_id=command.suite_id,
        failure_mode=command.failure_mode,
        results=results,
    )

    logger.info(
        "bloom_eval: completed suite=%s failure_rate=%.2f passed_threshold=%s",
        command.suite_id,
        suite_result.failure_rate,
        suite_result.passed_threshold,
        extra={"correlation_id": correlation_id},
    )

    if producer is not None:
        payload: dict[str, object] = {
            "event_type": "BloomEvalCompleted",
            "suite_id": str(suite_result.suite_id),
            "spec_id": str(suite_result.spec_id),
            "failure_mode": suite_result.failure_mode.value,
            "total_scenarios": suite_result.total_scenarios,
            "passed_count": suite_result.passed_count,
            "failure_rate": suite_result.failure_rate,
            "passed_threshold": suite_result.passed_threshold,
            "correlation_id": correlation_id,
            "emitted_at": datetime.now(UTC).isoformat(),
        }

        async def _publish() -> None:
            try:
                await producer.publish(
                    topic=command.publish_topic,
                    key=str(command.suite_id),
                    value=payload,
                )
            except Exception:
                logger.exception(
                    "bloom_eval: publish failed suite=%s",
                    command.suite_id,
                    extra={"correlation_id": correlation_id},
                )

        _task = asyncio.create_task(_publish())
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)


__all__ = [
    "ModelBloomEvalRunCommand",
    "run_bloom_eval",
]
