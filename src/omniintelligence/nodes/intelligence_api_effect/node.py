"""Intelligence API Effect - Declarative effect node for API calls."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeIntelligenceApiEffect(NodeEffect):
    """Declarative effect node for intelligence API operations."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeIntelligenceApiEffect"]
