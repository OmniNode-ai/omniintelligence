# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CI Error Classifier Compute Node — thin shell, delegates to handler.

Ticket: OMN-3556
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_ci_error_classifier_compute.handlers.handler_classifier import (
    _parse_llm_response,
)
from omniintelligence.nodes.node_ci_error_classifier_compute.models.model_input import (
    ModelCiErrorClassifierInput,
)
from omniintelligence.nodes.node_ci_error_classifier_compute.models.model_output import (
    ModelCiErrorClassifierOutput,
)


class NodeCiErrorClassifierCompute(
    NodeCompute[ModelCiErrorClassifierInput, ModelCiErrorClassifierOutput]
):
    """Pure compute node for LLM-assisted CI error classification.

    This node is a thin shell following the ONEX declarative pattern.
    All computation logic is delegated to the handler function.
    The LLM call itself is injected at the effect layer — this node
    only normalizes and validates the response.
    """

    async def compute(
        self, input_data: ModelCiErrorClassifierInput
    ) -> ModelCiErrorClassifierOutput:
        """Normalize a raw LLM classification response via handler function."""
        parsed = _parse_llm_response(
            {
                "classification": input_data.failure_output,
                "confidence": 0.0,
                "evidence": [],
                "unknowns": [],
            }
        )
        return ModelCiErrorClassifierOutput(**parsed)


__all__ = ["NodeCiErrorClassifierCompute"]
