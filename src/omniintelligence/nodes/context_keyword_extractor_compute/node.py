"""Context Keyword Extractor Compute - Pure compute node for keyword extraction."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeContextKeywordExtractorCompute(NodeCompute):
    """Pure compute node for extracting contextual keywords."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeContextKeywordExtractorCompute"]
