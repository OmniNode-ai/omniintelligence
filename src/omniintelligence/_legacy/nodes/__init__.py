"""Legacy ONEX Intelligence Nodes.

.. deprecated:: 0.1.0
    This module is deprecated. Use :mod:`omniintelligence.nodes` instead.
    Legacy nodes will be removed in v2.0.0.

This module provides legacy node implementations migrated from omniarchon.
These implementations use older, more verbose patterns that have been
superseded by canonical ONEX declarative nodes.

Migration Guide:
    # DEPRECATED - legacy import:
    from omniintelligence._legacy.nodes import NodeIntelligenceAdapterEffect

    # RECOMMENDED - canonical import:
    from omniintelligence.nodes import NodeIntelligenceAdapterEffect

See _legacy/DEPRECATION.md for complete migration guidance and timeline.
"""

import warnings

warnings.warn(
    "The omniintelligence._legacy.nodes module is deprecated as of v0.1.0 and "
    "will be removed in v2.0.0. Use omniintelligence.nodes instead. "
    "See _legacy/DEPRECATION.md for migration guidance.",
    DeprecationWarning,
    stacklevel=2,
)

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


def __getattr__(name: str) -> object:
    """Lazy import for module attributes."""
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Type checking imports for IDE support
if TYPE_CHECKING:
    from omniintelligence.nodes.intelligence_adapter import (
        NodeIntelligenceAdapterEffect,
    )
    from omniintelligence.nodes.pattern_extraction import (
        NodeContextKeywordExtractorCompute,
        NodeExecutionTraceParserCompute,
        NodeIntentClassifierCompute,
        NodePatternAssemblerOrchestrator,
        NodeSuccessCriteriaMatcherCompute,
    )
