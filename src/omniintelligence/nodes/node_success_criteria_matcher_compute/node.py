# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/16
# Status: Interface defined, implementation pending
"""Success Criteria Matcher Compute - STUB compute node for criteria matching."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/16"


class NodeSuccessCriteriaMatcherCompute(NodeCompute[dict[str, Any], dict[str, Any]]):
    """STUB: Pure compute node for matching success criteria.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Match execution results against success criteria
        - Support pattern-based criteria matching
        - Generate success/failure analysis
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeSuccessCriteriaMatcherCompute is a stub implementation and does not "
            f"provide full functionality. The node accepts inputs but performs no actual "
            f"criteria matching. See {_STUB_TRACKING_URL} for implementation progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute criteria matching (STUB - returns empty result).

        Args:
            _input_data: Input data for criteria matching (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeSuccessCriteriaMatcherCompute.compute() is a stub that returns empty "
            f"results. No actual criteria matching is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeSuccessCriteriaMatcherCompute is not yet implemented",
            "criteria_matched": [],
            "success_rate": 0.0,
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeSuccessCriteriaMatcherCompute"]
