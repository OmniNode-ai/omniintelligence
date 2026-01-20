# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/4
# Status: Interface defined, implementation pending
"""Entity Extraction Compute - STUB compute node for entity extraction."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/4"


class NodeEntityExtractionCompute(NodeCompute):
    """STUB: Pure compute node for extracting entities from code and documents.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Extract named entities (classes, functions, variables, etc.)
        - Support multiple language parsers
        - Generate entity relationship graphs
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeEntityExtractionCompute is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"entity extraction. See {_STUB_TRACKING_URL} for implementation progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute entity extraction (STUB - returns empty result).

        Args:
            _input_data: Input data for entity extraction (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeEntityExtractionCompute.compute() is a stub that returns empty "
            f"results. No actual entity extraction is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeEntityExtractionCompute is not yet implemented",
            "entities": [],
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeEntityExtractionCompute"]
