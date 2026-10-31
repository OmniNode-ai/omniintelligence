# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reliability, thresholds, and existing blacklist status."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_policy_state_reducer.models.model_transition_thresholds import (
    ModelTransitionThresholds,
)


class ModelShouldBlacklistRequest(BaseModel):
    """Reliability, thresholds, and existing blacklist status."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    reliability_0_1: float
    thresholds: ModelTransitionThresholds
    already_blacklisted: bool
