# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute: thin shell delegating to handle_retrieval_eval."""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.handler_retrieval_eval import (
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelEvalResult,
    ModelRetrievalEvalInput,
)


class NodeRetrievalEvalCompute(NodeCompute[ModelRetrievalEvalInput, ModelEvalResult]):
    """Compute node that runs the offline retrieval eval.

    Thin shell following the ONEX declarative pattern.
    All logic is delegated to handle_retrieval_eval.
    """

    async def compute(self, input_data: ModelRetrievalEvalInput) -> ModelEvalResult:
        """Delegate to handle_retrieval_eval."""
        return await handle_retrieval_eval(input_data)


__all__ = ["NodeRetrievalEvalCompute"]
