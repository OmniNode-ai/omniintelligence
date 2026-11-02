# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute — thin shell delegating to handle_retrieval_eval.

Runs the offline retrieval eval harness (replay scenarios, ranking metrics and
the scorecard) over the frozen code-projection fixtures.
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.handlers import (
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
    ModelRetrievalEvalResult,
)


class NodeRetrievalEvalCompute(
    NodeCompute[ModelRetrievalEvalInput, ModelRetrievalEvalResult]
):
    """Compute node for the offline retrieval eval harness.

    Thin shell following the ONEX declarative pattern.
    All logic is delegated to handle_retrieval_eval.
    """

    async def compute(
        self, input_data: ModelRetrievalEvalInput
    ) -> ModelRetrievalEvalResult:
        """Delegate to handle_retrieval_eval."""
        return await handle_retrieval_eval(input_data)


__all__ = ["NodeRetrievalEvalCompute"]
