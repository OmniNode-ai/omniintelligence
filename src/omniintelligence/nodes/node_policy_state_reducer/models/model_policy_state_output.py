# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for PolicyStateReducer node (OMN-2557)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)
from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_type import (
    EnumPolicyType,
)


class ModelPolicyStateOutput(BaseModel):
    """Output from the PolicyStateReducer node.

    Contains the audit trail of the state mutation: old state, new state,
    whether a lifecycle transition occurred, and whether an alert was emitted.
    """

    model_config = ConfigDict(frozen=True)

    policy_id: str = Field(description="The policy entity that was updated.")
    policy_type: EnumPolicyType = Field(description="Policy type that was updated.")
    old_lifecycle_state: EnumPolicyLifecycleState = Field(
        description="Lifecycle state before this update."
    )
    new_lifecycle_state: EnumPolicyLifecycleState = Field(
        description="Lifecycle state after this update."
    )
    transition_occurred: bool = Field(
        description="True if a lifecycle state transition happened."
    )
    blacklisted: bool = Field(
        default=False,
        description="True if the tool was auto-blacklisted in this update.",
    )
    alert_emitted: bool = Field(
        default=False,
        description="True if system.alert.tool_degraded was emitted.",
    )
    idempotency_key: str = Field(
        description="Idempotency key from the input event (for dedup tracking)."
    )
    was_duplicate: bool = Field(
        default=False,
        description="True if this event was a duplicate and was skipped (idempotent).",
    )
    updated_at_utc: str = Field(description="ISO-8601 UTC timestamp of this update.")


__all__ = ["ModelPolicyStateOutput"]
