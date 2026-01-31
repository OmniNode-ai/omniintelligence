"""Semantic Analysis Compute - Pure compute node for AST-based semantic analysis.

This node performs deterministic semantic analysis on Python source code using
the built-in ast module. It extracts entities (functions, classes, imports,
constants) and relationships (calls, imports, inherits, defines).

Key characteristics:
    - Pure computation: no HTTP calls, no LLM, no side effects
    - Deterministic: same input always produces same output
    - Never throws: parse errors return parse_ok=False with warnings
    - Python-only: other languages return empty results with warning

This node follows the declarative thin shell pattern - all business logic
is delegated to the handler.
"""

from __future__ import annotations

from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_semantic_analysis_compute.handlers import (
    compute_semantic_analysis,
)
from omniintelligence.nodes.node_semantic_analysis_compute.models import (
    ModelSemanticAnalysisInput,
    ModelSemanticAnalysisOutput,
)


class NodeSemanticAnalysisCompute(
    NodeCompute[ModelSemanticAnalysisInput, ModelSemanticAnalysisOutput]
):
    """Pure compute node for semantic analysis of code.

    This is a thin shell that delegates all business logic to the handler.
    No error handling, logging, or business logic belongs in this class.
    """

    is_stub: ClassVar[bool] = False

    async def compute(
        self, input_data: ModelSemanticAnalysisInput
    ) -> ModelSemanticAnalysisOutput:
        """Compute semantic analysis on source code.

        Delegates to compute_semantic_analysis handler.

        Args:
            input_data: Typed input model containing code snippet and context.

        Returns:
            ModelSemanticAnalysisOutput with extracted entities, relations,
            semantic features, and metadata.
        """
        return compute_semantic_analysis(input_data)


__all__ = ["NodeSemanticAnalysisCompute"]
