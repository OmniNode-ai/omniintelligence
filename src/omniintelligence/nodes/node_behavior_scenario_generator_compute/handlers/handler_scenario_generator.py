# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler: scenario generation for NodeBehaviorScenarioGeneratorCompute.

Pure async handler — no I/O, no logging, no container access.
LLM calls are delegated to the injected llm_caller.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from omniintelligence.nodes.node_behavior_scenario_generator_compute.models import (
    ModelScenarioGenerationRequest,
    ModelScenarioGenerationResponse,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_behavior_spec import (
    ModelBehaviorSpec,
)
from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_scenario import (
    ModelEvalScenario,
)


async def handle_scenario_generation(
    spec: ModelBehaviorSpec,
    n: int,
    *,
    llm_caller: Callable[[str, int], Awaitable[list[str]]],
) -> list[ModelEvalScenario]:
    """Generate exactly n ModelEvalScenario objects from a BehaviorSpec.

    Args:
        spec: The behavior specification defining failure mode and prompt template.
        n: Number of scenarios to generate.
        llm_caller: Async callable that accepts (prompt_template, n) and returns
            a list of exactly n raw scenario text strings.

    Returns:
        List of exactly n ModelEvalScenario objects with spec_id and failure_mode
        propagated from spec.
    """
    raw_texts: list[str] = await llm_caller(spec.scenario_prompt_template, n)
    return [
        ModelEvalScenario(
            spec_id=spec.spec_id,
            failure_mode=spec.failure_mode,
            input_text=text,
            context={},
        )
        for text in raw_texts
    ]


class HandlerScenarioGeneration:
    """Generate behavior scenarios using an injected LLM caller.

    ``handle`` is the typed entry point; the generation core stays the
    git-preserved ``handle_scenario_generation`` above, so the shape change moves
    only the request/response boundary.
    """

    def __init__(
        self,
        *,
        llm_caller: Callable[[str, int], Awaitable[list[str]]],
    ) -> None:
        """Initialize the scenario generation handler.

        Args:
            llm_caller: Async callable that accepts (prompt_template, n) and returns
                a list of exactly n raw scenario text strings.
        """
        self._llm_caller = llm_caller

    async def handle(
        self, request: ModelScenarioGenerationRequest
    ) -> ModelScenarioGenerationResponse:
        """Generate exactly n ModelEvalScenario objects from a BehaviorSpec.

        Args:
            request: Behavior specification and number of scenarios to generate.

        Returns:
            Response containing exactly n ModelEvalScenario objects with spec_id
            and failure_mode propagated from spec.
        """
        scenarios = await handle_scenario_generation(
            request.spec, request.n, llm_caller=self._llm_caller
        )
        return ModelScenarioGenerationResponse(scenarios=scenarios)


__all__ = ["HandlerScenarioGeneration", "handle_scenario_generation"]
