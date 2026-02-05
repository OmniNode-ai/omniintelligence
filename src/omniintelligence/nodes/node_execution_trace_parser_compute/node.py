"""Execution Trace Parser Compute Node.

Thin shell compute node for parsing execution traces. All logic is
delegated to the handler function following ONEX declarative pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers import (
    handle_trace_parsing_compute,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
    ModelTraceParsingInput,
    ModelTraceParsingOutput,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeExecutionTraceParserCompute(
    NodeCompute[ModelTraceParsingInput, ModelTraceParsingOutput]
):
    """Pure compute node for parsing execution traces.

    This node parses agent execution traces to extract:
    - Span lifecycle events (start, end)
    - Error events from status and log levels
    - Timing metrics and latency breakdown

    The node is a thin shell following the ONEX declarative pattern.
    All parsing logic is delegated to the handler function.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the compute node.

        Args:
            container: ONEX container with node configuration.
        """
        super().__init__(container)

    async def compute(
        self, input_data: ModelTraceParsingInput
    ) -> ModelTraceParsingOutput:
        """Parse execution traces by delegating to handler function.

        Args:
            input_data: Input containing trace data and parsing options.

        Returns:
            ModelTraceParsingOutput with parsed events, errors, and timing.
        """
        return handle_trace_parsing_compute(input_data)


__all__ = ["NodeExecutionTraceParserCompute"]
