# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Updated reliability and run/failure counts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelApplyRewardDeltaResponse(BaseModel):
    """Updated reliability and run/failure counts."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    new_reliability: float
    new_run_count: int
    new_failure_count: int
