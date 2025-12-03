"""ONEX Intelligence Nodes.

This module provides lazy imports to allow individual nodes to be imported
without loading all dependencies. Use explicit imports from submodules for
production use.

Example:
    # Recommended - direct import from specific node:
    from omniintelligence.nodes.vectorization_compute.v1_0_0.compute import VectorizationCompute

    # For convenience imports (loads dependencies):
    from omniintelligence.nodes import NodeIntelligenceAdapterEffect
"""

from typing import TYPE_CHECKING

# Lazy imports for runtime - only loaded when accessed
_lazy_imports = {
    "NodeIntelligenceAdapterEffect": "omniintelligence.nodes.intelligence_adapter",
    "NodeExecutionTraceParserCompute": "omniintelligence.nodes.pattern_extraction",
    "NodeContextKeywordExtractorCompute": "omniintelligence.nodes.pattern_extraction",
    "NodeIntentClassifierCompute": "omniintelligence.nodes.pattern_extraction",
    "NodeSuccessCriteriaMatcherCompute": "omniintelligence.nodes.pattern_extraction",
    "NodePatternAssemblerOrchestrator": "omniintelligence.nodes.pattern_extraction",
}

__all__ = [
    "NodeContextKeywordExtractorCompute",
    "NodeExecutionTraceParserCompute",
    "NodeIntelligenceAdapterEffect",
    "NodeIntentClassifierCompute",
    "NodePatternAssemblerOrchestrator",
    "NodeSuccessCriteriaMatcherCompute",
]


def __getattr__(name: str):
    """Lazy import for module attributes."""
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Type checking imports for IDE support
if TYPE_CHECKING:
    from omniintelligence.nodes.intelligence_adapter import NodeIntelligenceAdapterEffect
    from omniintelligence.nodes.pattern_extraction import (
        NodeContextKeywordExtractorCompute,
        NodeExecutionTraceParserCompute,
        NodeIntentClassifierCompute,
        NodePatternAssemblerOrchestrator,
        NodeSuccessCriteriaMatcherCompute,
    )
