# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model for RL routing decision telemetry.

Published when the RL routing system makes a shadow-mode routing decision,
allowing comparison between RL-recommended and actual agent selection.
Consumed by omnidash /rl-routing page.

Shadow mode: the RL policy recommends an agent but the actual routing
uses the existing heuristic. Both selections are recorded for comparison.

Reference: OMN-6126 (Dashboard Data Pipeline Gaps)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelRlRoutingAlternative(BaseModel):
    """A single routing alternative with its RL score."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    agent: str = Field(min_length=1, description="Agent/backend identifier")
    score: float = Field(description="RL policy score for this agent")


class ModelRlRoutingDecisionEvent(BaseModel):
    """Frozen event model for RL routing decision telemetry.

    Emitted when the RL routing system evaluates a routing decision
    (shadow mode or live). Contains the selected agent, confidence,
    and all alternatives for dashboard visualization.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    decision_id: str = Field(
        min_length=1, description="Unique ID for this routing decision"
    )
    correlation_id: str = Field(
        min_length=1, description="Distributed tracing correlation ID"
    )
    agent_selected: str = Field(
        min_length=1, description="Agent/backend selected by the RL policy"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="RL policy confidence in the selection"
    )
    shadow_mode: bool = Field(
        description="True = shadow comparison (not live), False = live routing"
    )
    alternatives: list[ModelRlRoutingAlternative] = Field(
        default_factory=list,
        description="All routing alternatives with their scores",
    )
    decided_at: datetime = Field(
        description="UTC timestamp of when the decision was made"
    )

    @field_validator("decided_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        """Validate that decided_at is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware")
        return v


__all__ = ["ModelRlRoutingAlternative", "ModelRlRoutingDecisionEvent"]
