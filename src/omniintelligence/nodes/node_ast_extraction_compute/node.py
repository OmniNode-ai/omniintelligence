# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST Extraction Compute - Thin declarative COMPUTE node shell.

This node follows the ONEX declarative pattern where the node is a thin shell
that delegates ALL business logic to the handler function. The node contains
no custom routing, iteration, or computation logic.

Pattern: "Thin shell, fat handler"

All extraction logic is implemented in:
    handlers/handler_ast_extract.py

Ticket: OMN-5659
"""

from __future__ import annotations

from omniintelligence.nodes.node_ast_extraction_compute.handlers import (
    handle_ast_extract,
)
from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract import (
    AstExtractInput,
)
from omniintelligence.nodes.node_ast_extraction_compute.models import (
    ModelCodeEntitiesExtractedEvent,
)


class NodeAstExtractionCompute:
    """Thin declarative shell for AST entity extraction.

    All business logic is delegated to the handler function.
    This node only provides the public interface for callers.

    Usage::

        node = NodeAstExtractionCompute()
        result = node.compute(input_data)
    """

    def compute(self, input_data: AstExtractInput) -> ModelCodeEntitiesExtractedEvent:
        """Extract entities from a Python source file by delegating to handler."""
        return handle_ast_extract(input_data)


__all__ = ["NodeAstExtractionCompute"]
