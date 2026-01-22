# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/15
# Status: Interface defined, implementation pending
"""Semantic Analysis Compute - STUB compute node for semantic analysis.

WARNING: This is a STUB implementation. The node interface is defined but actual
semantic analysis operations are not yet implemented. All method calls return stub
responses. See tracking issue for implementation progress.
"""
from __future__ import annotations

import warnings
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.semantic_analysis_compute.models import (
    ModelSemanticAnalysisInput,
    ModelSemanticAnalysisOutput,
    SemanticAnalysisMetadataDict,
)

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/15"


class NodeSemanticAnalysisCompute(NodeCompute[ModelSemanticAnalysisInput, ModelSemanticAnalysisOutput]):
    """STUB: Pure compute node for semantic analysis of code.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Analyze semantic meaning of code constructs
        - Generate semantic embeddings
        - Support code similarity computations

    Note:
        This node follows the declarative node pattern - no custom __init__ is needed.
        The base NodeCompute class handles initialization. Stub warnings are emitted
        only when the compute() method is called, not on instantiation.
    """

    is_stub: ClassVar[bool] = True

    async def compute(
        self, _input_data: ModelSemanticAnalysisInput
    ) -> ModelSemanticAnalysisOutput:
        """Compute semantic analysis (STUB - returns empty result).

        Args:
            _input_data: Typed input model for semantic analysis (unused in stub).

        Returns:
            Typed ModelSemanticAnalysisOutput with success=True but empty results.
        """
        warnings.warn(
            f"NodeSemanticAnalysisCompute.compute() is a stub that returns empty "
            f"results. No actual semantic analysis is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        # Explicitly type metadata for type safety and contract compliance
        stub_metadata: SemanticAnalysisMetadataDict = {
            "status": "stub",
            "message": "NodeSemanticAnalysisCompute is not yet implemented",
            "tracking_url": _STUB_TRACKING_URL,
        }
        return ModelSemanticAnalysisOutput(
            success=True,
            semantic_features={},
            embeddings=[],
            similarity_scores={},
            metadata=stub_metadata,
        )


__all__ = ["NodeSemanticAnalysisCompute"]
