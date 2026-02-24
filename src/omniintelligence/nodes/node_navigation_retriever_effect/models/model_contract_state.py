# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Local ContractState model for navigation retriever.

NOTE: This is a local definition that will be replaced by the canonical
ContractState from omnibase_core once OMN-2540 lands.
The field names and semantics are designed to be forward-compatible.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContractState(BaseModel):
    """Current state of the contract graph during navigation.

    Captures the relevant structural properties of the current position
    in the contract graph, used for hard filtering and similarity ranking.

    Attributes:
        node_id: Current node identifier in the contract graph.
        component_type: Component type of the current state.
        datasource_class: Datasource class of the current state.
        policy_tier: Active policy tier at the current state.
        graph_fingerprint: Hash of the contract graph structure (for staleness checks).
        available_transitions: Set of transition action names currently available.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    node_id: str = Field(
        description="Current node identifier in the contract graph.",
    )
    component_type: str = Field(
        description="Component type of the current state.",
    )
    datasource_class: str = Field(
        description="Datasource class of the current state.",
    )
    policy_tier: str = Field(
        description="Active policy tier at the current state.",
    )
    graph_fingerprint: str = Field(
        description="Hash of the contract graph structure for staleness checks.",
    )
    available_transitions: frozenset[str] = Field(
        default_factory=frozenset,
        description="Set of transition action names currently available.",
    )


__all__ = ["ContractState"]
