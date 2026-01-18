# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/7
# Status: Interface defined, implementation pending
"""Intelligence API Effect - STUB effect node for API calls."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/7"


class NodeIntelligenceApiEffect(NodeEffect):
    """STUB: Declarative effect node for intelligence API operations.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Make HTTP calls to intelligence API endpoints
        - Handle authentication and rate limiting
        - Support async batch operations
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeIntelligenceApiEffect is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"API operations. See {_STUB_TRACKING_URL} for implementation progress.",
            category=UserWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def process(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Process API request (STUB - returns empty result).

        Args:
            _input_data: Input data for API operation (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeIntelligenceApiEffect.process() is a stub that returns empty "
            f"results. No actual API calls are made. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=UserWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeIntelligenceApiEffect is not yet implemented",
            "response": None,
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeIntelligenceApiEffect"]
