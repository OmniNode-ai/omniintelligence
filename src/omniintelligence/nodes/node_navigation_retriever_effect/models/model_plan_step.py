# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Local PlanStep model for navigation retriever.

NOTE: This is a local definition that will be replaced by the canonical
PlanStep from omnibase_core once OMN-2540 and OMN-2561 land.
The field names and semantics are designed to be forward-compatible.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """A single step in a navigation plan.

    Represents a transition from one contract state to another
    via a named action.

    Attributes:
        from_node_id: Identifier of the source node in the contract graph.
        to_node_id: Identifier of the target node in the contract graph.
        action: Name of the transition/action taken.
        component_type: Component type at this transition point.
        datasource_class: Datasource class at this transition point.
        policy_tier: Policy tier active during this transition.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    from_node_id: str = Field(
        description="Identifier of the source node in the contract graph.",
    )
    to_node_id: str = Field(
        description="Identifier of the target node in the contract graph.",
    )
    action: str = Field(
        description="Name of the transition/action taken.",
    )
    component_type: str = Field(
        description="Component type at this transition point.",
    )
    datasource_class: str = Field(
        description="Datasource class at this transition point.",
    )
    policy_tier: str = Field(
        description="Policy tier active during this transition.",
    )


__all__ = ["PlanStep"]
