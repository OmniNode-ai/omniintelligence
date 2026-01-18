"""Vectorization Compute - Pure compute node for embedding generation.

This node follows the ONEX declarative pattern:
    - DECLARATIVE compute driven by contract.yaml
    - Pure function: input -> output, no side effects
    - Lightweight shell that delegates to NodeCompute base class
    - Pattern: "Contract-driven, deterministic computation"

Extends NodeCompute from omnibase_core for pure data processing.
All operation definitions are 100% driven by contract.yaml.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_compute import NodeCompute

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeVectorizationCompute(NodeCompute):
    """Pure compute node for embedding generation.

    This compute node generates embeddings from code and documents:
    - Single content vectorization
    - Batch vectorization for multiple contents
    - Support for multiple embedding models

    All operation logic is driven by contract.yaml operations section.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the compute node.

        Args:
            container: ONEX dependency injection container
        """
        super().__init__(container)


__all__ = ["NodeVectorizationCompute"]
