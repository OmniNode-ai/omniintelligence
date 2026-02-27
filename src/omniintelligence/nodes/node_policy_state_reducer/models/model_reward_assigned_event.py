# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""RewardAssignedEvent model consumed from Kafka by PolicyStateReducer (OMN-2557).

Topic: {env}.onex.evt.omnimemory.reward-assigned.v1
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_type import (
    EnumPolicyType,
)


class ModelRewardAssignedEvent(BaseModel):
    """Event emitted when a reward has been assigned to a policy entity.

    Consumed from Kafka topic:
        {env}.onex.evt.omnimemory.reward-assigned.v1
    """

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(description="Unique event identifier (UUID).")
    policy_id: str = Field(
        description="The policy entity ID receiving the reward (e.g., tool_id, pattern_id)."
    )
    policy_type: EnumPolicyType = Field(
        description="Which policy type this reward applies to."
    )
    reward_delta: float = Field(
        description=(
            "Signed reward delta [-1.0, +1.0]. Positive = improvement, negative = degradation."
        )
    )
    run_id: str = Field(description="The execution run that produced this reward.")
    objective_id: str = Field(
        description="The ObjectiveSpec ID used to compute this reward."
    )
    occurred_at_utc: str = Field(
        description="ISO-8601 UTC timestamp when the event occurred."
    )
    idempotency_key: str = Field(
        description=(
            "Hash of (event_id, policy_id, run_id) used for idempotency. "
            "Replaying the same event must produce no double-update."
        )
    )


__all__ = ["ModelRewardAssignedEvent"]
