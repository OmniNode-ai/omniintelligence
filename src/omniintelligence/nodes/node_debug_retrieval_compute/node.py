# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Debug Retrieval Compute Node — thin shell, delegates to handler.

Ticket: OMN-3556
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_debug_retrieval_compute.models.model_input import (
    ModelDebugRetrievalInput,
)
from omniintelligence.nodes.node_debug_retrieval_compute.models.model_output import (
    ModelDebugRetrievalOutput,
)


class NodeDebugRetrievalCompute(
    NodeCompute[ModelDebugRetrievalInput, ModelDebugRetrievalOutput]
):
    """Compute node for time-decayed retrieval of past CI fixes.

    This node is a thin shell following the ONEX declarative pattern.
    The store dependency is injected by the caller at invocation time.
    """

    async def compute(
        self, input_data: ModelDebugRetrievalInput
    ) -> ModelDebugRetrievalOutput:
        """Return an empty result — store injection happens at effect layer."""
        # Note: actual retrieval with store injection is done at the effect layer.
        # This node exposes the compute interface for pure unit testing of
        # the time-decay logic via handler_retrieval directly.
        return ModelDebugRetrievalOutput(fix_records=[])


__all__ = ["NodeDebugRetrievalCompute"]
