# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/13
# Status: Interface defined, implementation pending
"""Quality Scoring Compute - STUB compute node for quality scoring."""
from __future__ import annotations

import warnings
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.quality_scoring_compute.models import (
    ModelQualityScoringInput,
    ModelQualityScoringOutput,
)

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

    async def compute(
        self, input_data: ModelQualityScoringInput
    ) -> ModelQualityScoringOutput:
        """Compute quality score (STUB - returns empty result).

        Args:
            input_data: Typed input model for quality scoring (unused in stub).

        Returns:
            Typed ModelQualityScoringOutput with success=True but default values.
        """
        warnings.warn(
            f"NodeQualityScoringCompute.compute() is a stub that returns empty "
            f"results. No actual quality scoring is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return ModelQualityScoringOutput(
            success=True,
            quality_score=0.0,
            dimensions={},
            onex_compliant=False,
            recommendations=[],
            metadata={
                "status": "stub",
                "message": "NodeQualityScoringCompute is not yet implemented",
                "tracking_url": _STUB_TRACKING_URL,
            },
        )


__all__ = ["NodeQualityScoringCompute"]
