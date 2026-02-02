"""Pattern Learning Compute - Thin declarative COMPUTE node shell.

This node follows the ONEX declarative pattern:
    - 100% Contract-Driven: All capabilities in YAML, not Python
    - Zero Custom Methods: Base class handles everything
    - Declarative Execution: Handler wired externally via registry

Core Principle:
    "I'm interested in what you do, not what you are"

All aggregation logic is implemented in handlers and declared in contract.yaml.
The node shell contains NO business logic - it is purely a type anchor for the
ONEX node registry.

SEMANTIC NOTE:
    This node AGGREGATES and SUMMARIZES observed patterns.
    It does NOT perform statistical learning or weight updates.
    See handler docstrings for the semantic framing.

Ticket: OMN-1663
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodePatternLearningCompute(NodeCompute):
    """Thin declarative shell for pattern aggregation.

    Capability: pattern_learning.compute

    Provides a capability-oriented interface for pattern learning operations.
    This node aggregates and summarizes observed patterns into candidate and
    learned pattern sets.

    This node is declarative - all behavior is defined in contract.yaml and
    implemented through the handler. No custom computation logic exists in
    this class.

    Attributes:
        container: ONEX dependency injection container

    Example:
        >>> from omnibase_core.models.container import ModelONEXContainer
        >>> container = ModelONEXContainer()
        >>> node = NodePatternLearningCompute(container)
        >>> # Handler must be wired externally via registry
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the pattern learning compute node.

        Args:
            container: ONEX dependency injection container for resolving
                dependencies defined in contract.yaml.
        """
        super().__init__(container)


__all__ = ["NodePatternLearningCompute"]
