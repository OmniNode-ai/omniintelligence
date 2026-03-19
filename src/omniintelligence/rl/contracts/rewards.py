# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Typed reward signals for RL training.

``RewardSignal`` is a channel-based reward container. Each channel captures
a distinct quality dimension. ``to_scalar()`` produces a deterministic
weighted sum suitable for policy gradient updates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RewardSignal(BaseModel, frozen=True):
    """Multi-channel reward signal with deterministic scalar reduction.

    Channels
    --------
    latency_reward : float
        Reward for response latency. Higher = faster. Typically in [-1, 1].
    success_reward : float
        Reward for task success (1.0 = success, -1.0 = failure).
    cost_reward : float
        Reward for cost efficiency. Higher = cheaper. Typically in [-1, 1].
    quality_reward : float
        Reward for output quality. Higher = better. Typically in [-1, 1].

    Weights
    -------
    Default weights are equal (0.25 each). Override ``weight_*`` fields
    to adjust the importance of each channel.
    """

    latency_reward: float = Field(description="Latency reward channel")
    success_reward: float = Field(description="Success reward channel")
    cost_reward: float = Field(description="Cost efficiency reward channel")
    quality_reward: float = Field(description="Output quality reward channel")

    weight_latency: float = Field(
        default=0.25, description="Weight for latency channel"
    )
    weight_success: float = Field(
        default=0.25, description="Weight for success channel"
    )
    weight_cost: float = Field(default=0.25, description="Weight for cost channel")
    weight_quality: float = Field(
        default=0.25, description="Weight for quality channel"
    )

    def to_scalar(self) -> float:
        """Deterministic weighted sum of all reward channels.

        Returns a single scalar suitable for policy-gradient updates.
        The computation is a pure linear combination with no randomness.
        """
        return (
            self.weight_latency * self.latency_reward
            + self.weight_success * self.success_reward
            + self.weight_cost * self.cost_reward
            + self.weight_quality * self.quality_reward
        )
