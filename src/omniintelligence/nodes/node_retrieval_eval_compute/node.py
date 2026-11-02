# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute -- thin shell delegating to handle_retrieval_eval.

Runs the offline retrieval-quality eval harness from the frozen replay
fixtures. All computation is delegated to handle_retrieval_eval.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.handlers import (
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.runner import (
    ModelEvalResult,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
)


class NodeRetrievalEvalCompute(NodeCompute[ModelRetrievalEvalInput, ModelEvalResult]):
    """Compute node that runs the offline retrieval-quality eval harness.

    Thin shell following the ONEX declarative pattern.
    All logic is delegated to handle_retrieval_eval.
    """

    async def compute(self, input_data: ModelRetrievalEvalInput) -> ModelEvalResult:
        """Delegate to handle_retrieval_eval."""
        return await handle_retrieval_eval(input_data)


__all__ = ["NodeRetrievalEvalCompute"]
