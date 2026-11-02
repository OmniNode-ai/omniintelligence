# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Node RetrievalEvalCompute -- offline retrieval-quality eval harness.

Runs the code-projection retrieval eval entirely from the frozen replay
fixtures (no Postgres, Memgraph, Qdrant, network or model calls) and returns
the scorecard.  A thin declarative shell: all behaviour lives in
``handlers.handler_retrieval_eval.handle_retrieval_eval``.

Related:
    - OMN-16522: the retrieval eval harness and its gate
    - OMN-21945: harness bound into this node
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_retrieval_eval_compute.handlers.handler_retrieval_eval import (
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
    ModelRetrievalEvalOutput,
)


class NodeRetrievalEvalCompute(
    NodeCompute[ModelRetrievalEvalInput, ModelRetrievalEvalOutput]
):
    """Thin compute shell delegating to ``handle_retrieval_eval``."""

    async def compute(
        self, input_data: ModelRetrievalEvalInput
    ) -> ModelRetrievalEvalOutput:
        """Run the retrieval eval by delegating to the handler."""
        return await handle_retrieval_eval(input_data)


__all__ = ["NodeRetrievalEvalCompute"]
