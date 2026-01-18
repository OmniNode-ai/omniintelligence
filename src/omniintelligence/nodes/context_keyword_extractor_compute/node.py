# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/3
# Status: Interface defined, implementation pending
"""Context Keyword Extractor Compute - STUB compute node for keyword extraction."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/3"


class NodeContextKeywordExtractorCompute(NodeCompute):
    """STUB: Pure compute node for extracting contextual keywords.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Extract contextual keywords from code and documents
        - Support weighted keyword scoring
        - Integrate with semantic analysis pipeline
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeContextKeywordExtractorCompute is a stub implementation and does not "
            f"provide full functionality. The node accepts inputs but performs no actual "
            f"keyword extraction. See {_STUB_TRACKING_URL} for implementation progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute keyword extraction (STUB - returns empty result).

        Args:
            _input_data: Input data for keyword extraction (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeContextKeywordExtractorCompute.compute() is a stub that returns empty "
            f"results. No actual keyword extraction is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeContextKeywordExtractorCompute is not yet implemented",
            "keywords": [],
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeContextKeywordExtractorCompute"]
