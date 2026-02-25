# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Local GoalCondition model for navigation retriever.

NOTE: This is a local definition that will be replaced by the canonical
GoalCondition from omnibase_core once OMN-2540 lands.
The field names and semantics are designed to be forward-compatible.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoalCondition(BaseModel):
    """A goal condition for graph navigation.

    Represents the desired end-state that a navigation session is
    attempting to reach in the contract graph.

    Attributes:
        goal_id: Unique identifier for this goal condition.
        target_component_type: The desired component type at the goal.
        target_datasource_class: The desired datasource class at the goal.
        target_policy_tier: The desired policy tier at the goal.
        description: Human-readable description of the goal.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    goal_id: str = Field(
        description="Unique identifier for this goal condition.",
    )
    target_component_type: str = Field(
        description="The desired component type at the goal.",
    )
    target_datasource_class: str = Field(
        description="The desired datasource class at the goal.",
    )
    target_policy_tier: str = Field(
        description="The desired policy tier at the goal.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the goal.",
    )


__all__ = ["GoalCondition"]
