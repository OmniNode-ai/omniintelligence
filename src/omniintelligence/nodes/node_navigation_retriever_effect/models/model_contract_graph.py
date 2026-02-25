# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Local ContractGraph model for navigation retriever.

NOTE: This is a local definition that will be replaced by the canonical
ContractGraph from omnibase_core once OMN-2540 lands.
The field names and semantics are designed to be forward-compatible.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContractGraph(BaseModel):
    """The contract graph for graph navigation.

    Represents the available nodes and transitions in the contract graph.
    Used for staleness filtering: steps in retrieved paths are validated
    against the current graph before surfacing to the model.

    Attributes:
        graph_id: Unique identifier for this graph instance.
        fingerprint: Hash of the graph structure (matches ContractState.graph_fingerprint).
        valid_transitions: Set of valid (from_node_id, action) transition pairs.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    graph_id: str = Field(
        description="Unique identifier for this graph instance.",
    )
    fingerprint: str = Field(
        description="Hash of the graph structure.",
    )
    valid_transitions: frozenset[tuple[str, str]] = Field(
        default_factory=frozenset,
        description="Set of valid (from_node_id, action) transition pairs.",
    )


__all__ = ["ContractGraph"]
