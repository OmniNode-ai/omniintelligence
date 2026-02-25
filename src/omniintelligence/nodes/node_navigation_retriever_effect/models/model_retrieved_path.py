# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""RetrievedPath model — a ranked prior navigation path from OmniMemory.

Ticket: OMN-2579
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_navigation_retriever_effect.models.enum_navigation_outcome import (
    EnumNavigationOutcome,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_goal_condition import (
    GoalCondition,
)
from omniintelligence.nodes.node_navigation_retriever_effect.models.model_plan_step import (
    PlanStep,
)


class RetrievedPath(BaseModel):
    """A prior navigation path retrieved from OmniMemory.

    Carries the prior navigation path (as a sequence of PlanStep),
    the goal it was solving, similarity score, and success/failure outcome.

    Staleness filtering has already been applied: steps that are no
    longer in the current graph have been removed.

    Attributes:
        path_id: Qdrant point ID for this path entry.
        steps: Filtered sequence of plan steps from the prior path.
        original_step_count: Total steps before staleness filtering.
        goal: The goal condition this path was solving.
        similarity_score: Cosine similarity score (0.0-1.0).
        outcome: Whether the prior path succeeded or failed.
        graph_fingerprint: Fingerprint of the graph at time of recording.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    path_id: str = Field(
        description="Qdrant point ID for this path entry.",
    )
    steps: tuple[PlanStep, ...] = Field(
        description="Filtered sequence of plan steps (staleness-filtered).",
    )
    original_step_count: int = Field(
        description="Total steps before staleness filtering.",
        ge=0,
    )
    goal: GoalCondition = Field(
        description="The goal condition this path was solving.",
    )
    similarity_score: float = Field(
        description="Cosine similarity score in range [0.0, 1.0].",
        ge=0.0,
        le=1.0,
    )
    outcome: EnumNavigationOutcome = Field(
        description="Whether the prior path succeeded or failed.",
    )
    graph_fingerprint: str = Field(
        description="Fingerprint of the contract graph at time of recording.",
    )


__all__ = ["RetrievedPath"]
