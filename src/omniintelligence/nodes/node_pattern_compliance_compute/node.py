"""Pattern Compliance Compute Node - Thin shell delegating to handler.

Evaluates code against applicable patterns using Coder-14B (via ProtocolLlmClient).
This node follows the ONEX declarative pattern where the node class is a thin
shell that delegates all logic to handler functions.

The LLM client is injected via constructor, following the registry pattern
used by effect nodes (see NodePatternPromotionEffect for precedent).

Ticket: OMN-2256
"""

from __future__ import annotations

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_pattern_compliance_compute.handlers import (
    DEFAULT_MODEL,
    ProtocolLlmClient,
    handle_pattern_compliance_compute,
)
from omniintelligence.nodes.node_pattern_compliance_compute.models import (
    ModelComplianceRequest,
    ModelComplianceResult,
)


class NodePatternComplianceCompute(
    NodeCompute[ModelComplianceRequest, ModelComplianceResult]
):
    """Compute node for evaluating code compliance against patterns.

    Delegates all logic to the handler function. The LLM client is
    injected via constructor to allow testing with mocks.

    This node is a thin shell following the ONEX declarative pattern.
    """

    def __init__(
        self,
        *args: object,
        llm_client: ProtocolLlmClient,
        model: str = DEFAULT_MODEL,
        **kwargs: object,
    ) -> None:
        """Initialize with LLM client dependency.

        Args:
            llm_client: LLM client for inference calls.
            model: Model identifier (default: Coder-14B).
            *args: Passed to NodeCompute.
            **kwargs: Passed to NodeCompute.
        """
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._llm_client = llm_client
        self._model = model

    async def compute(
        self, input_data: ModelComplianceRequest
    ) -> ModelComplianceResult:
        """Evaluate code compliance by delegating to handler function."""
        return await handle_pattern_compliance_compute(
            input_data,
            llm_client=self._llm_client,
            model=self._model,
        )


__all__ = ["NodePatternComplianceCompute"]
