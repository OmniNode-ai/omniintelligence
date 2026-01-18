# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/13
# Status: Interface defined, implementation pending
"""Quality Scoring Compute - STUB compute node for quality scoring."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/13"


class NodeQualityScoringCompute(NodeCompute):
    """STUB: Pure compute node for scoring code quality.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Score code quality based on multiple dimensions
        - Check ONEX compliance
        - Generate quality recommendations
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeQualityScoringCompute is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"quality scoring. See {_STUB_TRACKING_URL} for implementation progress.",
            category=UserWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute quality score (STUB - returns empty result).

        Args:
            _input_data: Input data for quality scoring (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeQualityScoringCompute.compute() is a stub that returns empty "
            f"results. No actual quality scoring is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=UserWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeQualityScoringCompute is not yet implemented",
            "quality_score": 0.0,
            "recommendations": [],
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeQualityScoringCompute"]
