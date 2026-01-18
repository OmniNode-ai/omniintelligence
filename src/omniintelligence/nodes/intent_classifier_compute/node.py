# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/6
# Status: Interface defined, implementation pending
"""Intent Classifier Compute - STUB compute node for intent classification."""
from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/6"


class NodeIntentClassifierCompute(NodeCompute):
    """STUB: Pure compute node for classifying user intents.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Classify user intents from natural language
        - Support multi-label classification
        - Confidence scoring for classifications
    """

    is_stub: ClassVar[bool] = True

    def __init__(self, container: ModelONEXContainer) -> None:
        warnings.warn(
            f"NodeIntentClassifierCompute is a stub implementation and does not provide "
            f"full functionality. The node accepts inputs but performs no actual "
            f"intent classification. See {_STUB_TRACKING_URL} for implementation progress.",
            category=UserWarning,
            stacklevel=2,
        )
        super().__init__(container)

    async def compute(self, _input_data: dict[str, Any]) -> dict[str, Any]:
        """Compute intent classification (STUB - returns empty result).

        Args:
            _input_data: Input data for intent classification (unused in stub).

        Returns:
            Empty result dictionary indicating stub status.
        """
        warnings.warn(
            f"NodeIntentClassifierCompute.compute() is a stub that returns empty "
            f"results. No actual intent classification is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=UserWarning,
            stacklevel=2,
        )
        return {
            "status": "stub",
            "message": "NodeIntentClassifierCompute is not yet implemented",
            "intents": [],
            "confidence": 0.0,
            "tracking_url": _STUB_TRACKING_URL,
        }


__all__ = ["NodeIntentClassifierCompute"]
