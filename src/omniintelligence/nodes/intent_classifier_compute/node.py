"""Intent Classifier Compute - Pure compute node for intent classification."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeIntentClassifierCompute(NodeCompute):
    """Pure compute node for classifying user intents."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeIntentClassifierCompute"]
