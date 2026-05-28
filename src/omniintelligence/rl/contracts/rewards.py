# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Per-channel reward contract used by RL training loops.

This model is distinct from the shaper-based RewardSignal in rl.rewards,
which uses aggregate scalar/breakdown fields. The contract model exposes
individual channels directly so RL pipelines can compute weighted sums
with configurable weights at training time.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Default weights matching RewardConfig defaults
_DEFAULT_LATENCY_WEIGHT: float = 0.3
_DEFAULT_SUCCESS_WEIGHT: float = 0.4
_DEFAULT_COST_WEIGHT: float = 0.2
_DEFAULT_QUALITY_WEIGHT: float = 0.1


class RewardSignal(BaseModel):
    """Per-channel reward signal for RL training contracts.

    Attributes:
        latency_reward: Reward from the latency channel.
        success_reward: Reward from the success channel.
        cost_reward: Reward from the cost channel.
        quality_reward: Reward from the quality channel.
        weight_latency: Weight applied to the latency channel.
        weight_success: Weight applied to the success channel.
        weight_cost: Weight applied to the cost channel.
        weight_quality: Weight applied to the quality channel.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    latency_reward: float
    success_reward: float
    cost_reward: float
    quality_reward: float

    weight_latency: float = Field(default=_DEFAULT_LATENCY_WEIGHT, ge=0.0, le=1.0)
    weight_success: float = Field(default=_DEFAULT_SUCCESS_WEIGHT, ge=0.0, le=1.0)
    weight_cost: float = Field(default=_DEFAULT_COST_WEIGHT, ge=0.0, le=1.0)
    weight_quality: float = Field(default=_DEFAULT_QUALITY_WEIGHT, ge=0.0, le=1.0)

    def to_scalar(self) -> float:
        """Return weighted sum of all channels."""
        return (
            self.latency_reward * self.weight_latency
            + self.success_reward * self.weight_success
            + self.cost_reward * self.weight_cost
            + self.quality_reward * self.weight_quality
        )


__all__ = ["RewardSignal"]
