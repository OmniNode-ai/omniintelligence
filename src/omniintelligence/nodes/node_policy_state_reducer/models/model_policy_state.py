# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Policy state models for the four PolicyType variants (OMN-2557).

Each variant carries typed fields as specified in the design doc:
  - tool_reliability: { tool_id, reliability_0_1, run_count, failure_count }
  - pattern_effectiveness: { pattern_id, effectiveness_0_1, promotion_tier }
  - model_routing_confidence: { model_id, task_class, confidence_0_1, cost_per_token }
  - retry_threshold: { context_class, max_retries, escalation_after }
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)
from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_type import (
    EnumPolicyType,
)


class ModelToolReliabilityState(BaseModel):
    """State for a tool_reliability policy entry."""

    model_config = ConfigDict(frozen=True)

    tool_id: str = Field(description="Unique tool identifier.")
    reliability_0_1: float = Field(
        ge=0.0, le=1.0, description="Current reliability score [0.0, 1.0]."
    )
    run_count: int = Field(ge=0, description="Total number of runs observed.")
    failure_count: int = Field(ge=0, description="Total number of failures observed.")
    lifecycle_state: EnumPolicyLifecycleState = Field(
        default=EnumPolicyLifecycleState.CANDIDATE,
        description="Current lifecycle state.",
    )
    blacklisted: bool = Field(
        default=False,
        description="True if the tool has been auto-blacklisted due to reliability floor breach.",
    )
    updated_at_utc: str = Field(description="ISO-8601 UTC timestamp of last update.")


class ModelPatternEffectivenessState(BaseModel):
    """State for a pattern_effectiveness policy entry."""

    model_config = ConfigDict(frozen=True)

    pattern_id: str = Field(description="Unique pattern identifier.")
    effectiveness_0_1: float = Field(
        ge=0.0, le=1.0, description="Current effectiveness score [0.0, 1.0]."
    )
    promotion_tier: str = Field(
        default="CANDIDATE",
        description="Promotion tier (e.g., CANDIDATE, VALIDATED, SHARED).",
    )
    lifecycle_state: EnumPolicyLifecycleState = Field(
        default=EnumPolicyLifecycleState.CANDIDATE,
        description="Current lifecycle state.",
    )
    run_count: int = Field(ge=0, description="Total number of runs observed.")
    updated_at_utc: str = Field(description="ISO-8601 UTC timestamp of last update.")


class ModelModelRoutingConfidenceState(BaseModel):
    """State for a model_routing_confidence policy entry."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(description="Unique model identifier.")
    task_class: str = Field(
        description="Task classification this confidence applies to."
    )
    confidence_0_1: float = Field(
        ge=0.0, le=1.0, description="Current routing confidence score [0.0, 1.0]."
    )
    cost_per_token: float = Field(ge=0.0, description="Observed cost per token in USD.")
    lifecycle_state: EnumPolicyLifecycleState = Field(
        default=EnumPolicyLifecycleState.CANDIDATE,
        description="Current lifecycle state.",
    )
    run_count: int = Field(ge=0, description="Total number of runs observed.")
    updated_at_utc: str = Field(description="ISO-8601 UTC timestamp of last update.")


class ModelRetryThresholdState(BaseModel):
    """State for a retry_threshold policy entry."""

    model_config = ConfigDict(frozen=True)

    context_class: str = Field(
        description="Context classification this threshold applies to."
    )
    max_retries: int = Field(
        ge=0, description="Maximum number of retries before escalation."
    )
    escalation_after: int = Field(
        ge=0, description="Number of failures after which to escalate."
    )
    lifecycle_state: EnumPolicyLifecycleState = Field(
        default=EnumPolicyLifecycleState.CANDIDATE,
        description="Current lifecycle state.",
    )
    run_count: int = Field(ge=0, description="Total number of runs observed.")
    updated_at_utc: str = Field(description="ISO-8601 UTC timestamp of last update.")


class ModelPolicyState(BaseModel):
    """Envelope for a typed policy state entry.

    Carries one of the four typed state variants identified by policy_type.
    Used for audit log snapshots (old_state, new_state).
    """

    model_config = ConfigDict(frozen=True)

    policy_id: str = Field(
        description="Unique policy identifier (e.g., tool_id or pattern_id)."
    )
    policy_type: EnumPolicyType = Field(
        description="Which policy type this state represents."
    )
    state_json: str = Field(
        description=(
            "JSON-serialized typed state payload. "
            "Use policy_type to determine which model to deserialize into."
        )
    )
    lifecycle_state: EnumPolicyLifecycleState = Field(
        description="Current lifecycle state at time of snapshot."
    )
    snapshot_at_utc: str = Field(description="ISO-8601 UTC timestamp of this snapshot.")


__all__ = [
    "ModelModelRoutingConfidenceState",
    "ModelPatternEffectivenessState",
    "ModelPolicyState",
    "ModelRetryThresholdState",
    "ModelToolReliabilityState",
]
