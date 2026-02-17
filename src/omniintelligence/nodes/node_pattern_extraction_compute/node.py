"""Pattern Extraction Compute - Thin declarative COMPUTE node shell.

This node follows the ONEX declarative pattern where the node is a thin shell
that delegates ALL business logic to handler functions. The node contains
no custom routing, iteration, or computation logic.

Pattern: "Thin shell, fat handler"

All extraction logic is implemented in:
    handlers/handler_extract_all_patterns.py  (local models)
    handlers/handler_core_models.py           (core models - OMN-1594)

Tickets: OMN-1402, OMN-1594
"""

from __future__ import annotations

from omnibase_core.models.container import ModelONEXContainer
from omnibase_core.models.intelligence.model_pattern_extraction_input import (
    ModelPatternExtractionInput as CorePatternInput,
)
from omnibase_core.models.intelligence.model_pattern_extraction_output import (
    ModelPatternExtractionOutput as CorePatternOutput,
)
from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    extract_all_patterns,
    handle_pattern_extraction_core,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelPatternExtractionInput,
    ModelPatternExtractionOutput,
)


class NodePatternExtractionCompute(
    NodeCompute[ModelPatternExtractionInput, ModelPatternExtractionOutput]
):
    """Thin declarative shell for pattern extraction.

    All business logic is delegated to handler functions.
    This node only provides the ONEX container interface.

    Two compute paths are available:
        - ``compute()``: Uses local models (ModelPatternExtractionInput/Output)
        - ``compute_core()``: Uses canonical core models from omnibase_core
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the compute node with ONEX container."""
        super().__init__(container)

    async def compute(
        self, input_data: ModelPatternExtractionInput
    ) -> ModelPatternExtractionOutput:
        """Extract patterns using local models by delegating to handler."""
        return extract_all_patterns(input_data)

    async def compute_core(self, input_data: CorePatternInput) -> CorePatternOutput:
        """Extract patterns using core models by delegating to handler.

        **Design note -- secondary entry point outside NodeCompute[I, O] contract**:

        This method intentionally exists outside the generic ``compute()`` contract.
        ``RuntimeHostProcess`` discovers and invokes only the primary ``compute()``
        method (which uses local models).  ``compute_core()`` is a direct-call entry
        point for callers that already hold a reference to this node instance and need
        to work with the canonical ``omnibase_core`` pattern extraction models
        (e.g., orchestrators, integration tests, or the pattern assembler pipeline).

        It is NOT discovered or routed by ``RuntimeHostProcess``; that is intentional.

        This method uses the canonical ``ModelPatternExtractionInput`` and
        ``ModelPatternExtractionOutput`` from ``omnibase_core``, bridging
        to the existing local extraction pipeline.

        Args:
            input_data: Core input with session_ids and/or raw_events.

        Returns:
            Core output with patterns_by_kind structure.
        """
        return handle_pattern_extraction_core(input_data)


__all__ = ["NodePatternExtractionCompute"]
