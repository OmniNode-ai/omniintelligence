"""Pattern Extraction Compute - Thin declarative COMPUTE node shell.

This node follows the ONEX declarative pattern where the node is a thin shell
that delegates ALL business logic to handler functions. The node contains
no custom routing, iteration, or computation logic.

Pattern: "Thin shell, fat handler"

All extraction logic is implemented in:
    handlers/handler_extract_all_patterns.py

Ticket: OMN-1402
"""

from __future__ import annotations

from omnibase_core.models.container import ModelONEXContainer
from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    extract_all_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelPatternExtractionInput,
    ModelPatternExtractionOutput,
)


class NodePatternExtractionCompute(
    NodeCompute[ModelPatternExtractionInput, ModelPatternExtractionOutput]
):
    """Thin declarative shell for pattern extraction.

    All business logic is delegated to the extract_all_patterns handler.
    This node only provides the ONEX container interface.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the compute node with ONEX container."""
        super().__init__(container)

    async def compute(
        self, input_data: ModelPatternExtractionInput
    ) -> ModelPatternExtractionOutput:
        """Extract patterns by delegating to handler."""
        return extract_all_patterns(input_data)


__all__ = ["NodePatternExtractionCompute"]
