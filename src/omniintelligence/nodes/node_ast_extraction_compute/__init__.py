# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST Extraction Compute Node.

This node extracts structural code entities from Python source files using
AST parsing. It detects classes, protocols, Pydantic models, functions,
imports, and module-level constants, producing typed entity and relationship
models for downstream knowledge-graph ingestion.

The node is a pure compute node - it performs deterministic computation
without external I/O or side effects.
"""

from omniintelligence.nodes.node_ast_extraction_compute.node import (
    NodeAstExtractionCompute,
)

__all__ = ["NodeAstExtractionCompute"]
