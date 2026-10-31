# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Current lifecycle state, metrics, and transition thresholds."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)
from omniintelligence.nodes.node_policy_state_reducer.models.model_transition_thresholds import (
    ModelTransitionThresholds,
)


class ModelComputeNextLifecycleStateRequest(BaseModel):
    """Current lifecycle state, metrics, and transition thresholds."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    current_state: EnumPolicyLifecycleState
    reliability_0_1: float
    run_count: int
    positive_signal_ratio: float
    thresholds: ModelTransitionThresholds
