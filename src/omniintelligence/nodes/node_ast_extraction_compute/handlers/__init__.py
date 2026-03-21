# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST Extraction Compute Handlers.

Pure handler functions for extracting code entities from Python source files
using the ``ast`` module. Follows the ONEX "thin shell, fat handler" pattern.
"""

from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_ast_extract import (
    handle_ast_extract,
)
from omniintelligence.nodes.node_ast_extraction_compute.handlers.handler_relationship_detect import (
    detect_relationships,
)

__all__ = [
    "detect_relationships",
    "handle_ast_extract",
]
