# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute -- thin shell delegating to the retrieval eval handler.

Runs the offline retrieval-quality harness over the frozen replay fixtures and
returns the scorecard plus the loose latency report.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.handler_retrieval_eval import (
    ModelEvalResult,
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
)


class NodeRetrievalEvalCompute(NodeCompute[ModelRetrievalEvalInput, ModelEvalResult]):
    """Compute node that runs the offline retrieval eval harness.

    Thin shell following the ONEX declarative pattern.
    All logic is delegated to handle_retrieval_eval.
    """

    async def compute(self, input_data: ModelRetrievalEvalInput) -> ModelEvalResult:
        """Delegate to handle_retrieval_eval."""
        return await handle_retrieval_eval(input_data)


__all__ = ["NodeRetrievalEvalCompute"]
