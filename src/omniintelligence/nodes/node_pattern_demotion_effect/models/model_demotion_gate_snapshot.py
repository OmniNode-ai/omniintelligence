# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Demotion gate snapshot model for pattern_demotion_effect."""

from pydantic import BaseModel, ConfigDict, Field


class ModelDemotionGateSnapshot(BaseModel):
    """Snapshot of gate values at demotion time.

    Captures the demotion criteria values at the moment a pattern
    was evaluated for demotion, providing audit trail for why
    a pattern was demoted.
    """

    model_config = ConfigDict(frozen=True)

    success_rate_rolling_20: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Success rate over the rolling window of last 20 injections",
    )
    injection_count_rolling_20: int = Field(
        ...,
        ge=0,
        description="Number of injections in the rolling window",
    )
    failure_streak: int = Field(
        ...,
        ge=0,
        description="Current consecutive failure count",
    )
    disabled: bool = Field(
        default=False,
        description="Whether the pattern is currently disabled",
    )
    hours_since_promotion: float | None = Field(
        default=None,
        ge=0.0,
        description="Hours elapsed since pattern was promoted to validated status. "
        "Used to enforce cooldown periods. None if promotion timestamp unavailable.",
    )


__all__ = ["ModelDemotionGateSnapshot"]
