# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/10
# Status: Interface defined, implementation pending
"""Pattern Matching Compute - STUB compute node for pattern matching."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/10"


class NodePatternMatchingCompute(NodeCompute):
    """STUB: Pure compute node for matching code patterns.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Match code against learned patterns
        - Return similarity scores and matches
        - Integrate with pattern learning pipeline
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodePatternMatchingCompute is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"pattern matching. See {_STUB_TRACKING_URL} for implementation progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute pattern matching (STUB - returns empty result).

        Args:
            _input_data: Input data for pattern matching (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodePatternMatchingCompute.compute() is a stub that returns empty "
            f"results. No actual pattern matching is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodePatternMatchingCompute is not yet implemented",
            "matches": [],
            "similarity_scores": [],
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodePatternMatchingCompute"]
