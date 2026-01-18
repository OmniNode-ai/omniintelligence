"""Success Criteria Matcher Compute - Pure compute node for criteria matching."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeSuccessCriteriaMatcherCompute(NodeCompute):
    """Pure compute node for matching success criteria."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)


__all__ = ["NodeSuccessCriteriaMatcherCompute"]
