# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Lifecycle state after evaluating transition thresholds."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)


class ModelComputeNextLifecycleStateResponse(BaseModel):
    """Lifecycle state after evaluating transition thresholds."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    lifecycle_state: EnumPolicyLifecycleState
