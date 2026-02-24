# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for PolicyStateReducer node (OMN-2557)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_policy_state_reducer.models.model_reward_assigned_event import (
    ModelRewardAssignedEvent,
)
from omniintelligence.nodes.node_policy_state_reducer.models.model_transition_thresholds import (
    ModelTransitionThresholds,
)


class ModelPolicyStateInput(BaseModel):
    """Input to the PolicyStateReducer node."""

    model_config = ConfigDict(frozen=True)

    event: ModelRewardAssignedEvent = Field(
        description="The RewardAssignedEvent to process."
    )
    thresholds: ModelTransitionThresholds = Field(
        default_factory=ModelTransitionThresholds,
        description="Lifecycle transition thresholds (sourced from ObjectiveSpec).",
    )


__all__ = ["ModelPolicyStateInput"]
