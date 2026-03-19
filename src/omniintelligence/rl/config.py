# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""PPO configuration model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PPOConfig(BaseModel):
    """Configuration for Proximal Policy Optimization training."""

    lr: float = Field(default=3e-4, description="Learning rate for the optimizer")
    gamma: float = Field(default=0.99, description="Discount factor for future rewards")
    gae_lambda: float = Field(
        default=0.95, description="Lambda for Generalized Advantage Estimation"
    )
    clip_epsilon: float = Field(
        default=0.2, description="PPO clipping parameter for policy ratio"
    )
    entropy_coeff: float = Field(
        default=0.01, description="Coefficient for entropy bonus in the loss"
    )
    value_coeff: float = Field(
        default=0.5, description="Coefficient for the value function loss"
    )
    epochs_per_update: int = Field(
        default=4, description="Number of optimization epochs per PPO update"
    )
    batch_size: int = Field(default=64, description="Mini-batch size for PPO updates")
    hidden_dims: list[int] = Field(
        default=[64, 64],
        description="Hidden layer dimensions for the actor-critic MLP",
    )
