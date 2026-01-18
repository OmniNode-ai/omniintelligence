"""Memgraph Graph Effect - Declarative effect node for graph storage."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeMemgraphGraphEffect(NodeEffect):
    """Declarative effect node for Memgraph graph operations."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeMemgraphGraphEffect"]
