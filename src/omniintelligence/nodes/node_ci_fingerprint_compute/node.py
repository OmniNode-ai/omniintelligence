# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CI Fingerprint Compute Node — thin shell, delegates to handler.

Ticket: OMN-3556
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_ci_fingerprint_compute.container.container_ci_fingerprint import (
    resolve_ci_fingerprint_handler,
)
from omniintelligence.nodes.node_ci_fingerprint_compute.models.model_input import (
    ModelCiFingerprintInput,
)
from omniintelligence.nodes.node_ci_fingerprint_compute.models.model_output import (
    ModelCiFingerprintOutput,
)


class NodeCiFingerprintCompute(
    NodeCompute[ModelCiFingerprintInput, ModelCiFingerprintOutput]
):
    """Pure compute node for CI failure fingerprinting.

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    """

    async def compute(
        self, input_data: ModelCiFingerprintInput
    ) -> ModelCiFingerprintOutput:
        """Compute error fingerprint by delegating to handler function."""
        return resolve_ci_fingerprint_handler().handle(input_data)


__all__ = ["NodeCiFingerprintCompute"]
