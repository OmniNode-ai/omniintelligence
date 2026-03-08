# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeMemoryEvalCompute — thin shell delegating to handler.

Evaluates MEMORY_SYSTEM failure modes via LLM judge.
All computation is delegated to handle_memory_evaluation.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_bloom_eval_orchestrator.models.model_eval_result import (
    ModelEvalSuiteResult,
)
from omniintelligence.nodes.node_memory_eval_compute.handlers import (
    handle_memory_evaluation,
)
from omniintelligence.nodes.node_memory_eval_compute.models import (
    ModelMemoryEvalInput,
)


class NodeMemoryEvalCompute(NodeCompute[ModelMemoryEvalInput, ModelEvalSuiteResult]):
    """Compute node that evaluates MEMORY_SYSTEM failure modes via LLM judge.

    Thin shell following the ONEX declarative pattern.
    All logic is delegated to handle_memory_evaluation.
    """

    async def compute(self, input_data: ModelMemoryEvalInput) -> ModelEvalSuiteResult:
        """Delegate to handle_memory_evaluation."""
        return await handle_memory_evaluation(
            scenarios=input_data.scenarios,
            memory_output=input_data.memory_output,
            memory_context=input_data.memory_context,
            judge_caller=input_data.judge_caller,
        )


__all__ = ["NodeMemoryEvalCompute"]
