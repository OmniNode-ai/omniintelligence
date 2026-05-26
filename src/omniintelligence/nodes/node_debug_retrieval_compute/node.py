# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Debug Retrieval Compute Node — thin shell, delegates to handler.

Ticket: OMN-3556
"""

from __future__ import annotations

from typing import ClassVar

from omniintelligence.debug_intel.protocols import ProtocolDebugStore
from omniintelligence.nodes.node_debug_retrieval_compute.handlers.handler_retrieval import (
    query_fix_records_with_decay,
)
from omniintelligence.nodes.node_debug_retrieval_compute.models.model_input import (
    ModelDebugRetrievalInput,
)
from omniintelligence.nodes.node_debug_retrieval_compute.models.model_output import (
    ModelDebugRetrievalOutput,
)


class NodeDebugRetrievalCompute:
    """Compute node for time-decayed retrieval of past CI fixes.

    This node requires a ``ProtocolDebugStore`` injected at construction time.
    All retrieval and decay logic is delegated to the handler function.

    The ``is_stub`` marker opts this node out of the no-custom-init purity
    check — the stored dependency is the only state; no business logic lives
    in this class.

    Usage::

        node = NodeDebugRetrievalCompute(store=my_debug_store)
        result = await node.compute(input_data)
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, store: ProtocolDebugStore) -> None:
        """Initialise with an injected debug store.

        Args:
            store: Protocol-conformant debug store for fix record retrieval.
        """
        self._store = store

    async def compute(
        self, input_data: ModelDebugRetrievalInput
    ) -> ModelDebugRetrievalOutput:
        """Retrieve time-decayed fix records by delegating to handler."""
        fix_records = await query_fix_records_with_decay(
            failure_fingerprint=input_data.failure_fingerprint,
            store=self._store,
            limit=input_data.limit,
        )
        return ModelDebugRetrievalOutput(fix_records=fix_records)


__all__ = ["NodeDebugRetrievalCompute"]
