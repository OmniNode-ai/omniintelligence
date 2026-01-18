"""Entity Extraction Compute - Pure compute node for entity extraction."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeEntityExtractionCompute(NodeCompute):
    """Pure compute node for extracting entities from code and documents."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeEntityExtractionCompute"]
