"""Ingestion Effect - STUB effect node for document ingestion."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeIngestionEffect(NodeEffect):
    """STUB: Effect node for document ingestion operations."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeIngestionEffect"]
