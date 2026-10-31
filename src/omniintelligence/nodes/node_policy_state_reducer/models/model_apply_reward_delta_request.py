# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reliability, reward delta, and counts for a policy update."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelApplyRewardDeltaRequest(BaseModel):
    """Reliability, reward delta, and counts for a policy update."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    current_reliability: float
    reward_delta: float
    run_count: int
    failure_count: int
