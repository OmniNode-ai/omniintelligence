# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Actor-critic PPO policy network."""

from __future__ import annotations

import torch
from torch import nn

from omniintelligence.rl.config import PPOConfig


class PPOPolicy(nn.Module):
    """Actor-critic MLP for PPO.

    The actor head maps observations to action logits (softmax over discrete
    actions). The critic head maps observations to a scalar state value.

    Args:
        obs_dim: Dimensionality of the observation space.
        action_dim: Number of discrete actions.
        config: PPO configuration (used for hidden_dims).
    """

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        config: PPOConfig | None = None,
    ) -> None:
        super().__init__()
        self.obs_dim = obs_dim
        self.action_dim = action_dim
        self.config = config or PPOConfig()

        hidden_dims = self.config.hidden_dims

        # Build shared trunk
        trunk_layers: list[nn.Module] = []
        prev_dim = obs_dim
        for h_dim in hidden_dims:
            trunk_layers.append(nn.Linear(prev_dim, h_dim))
            trunk_layers.append(nn.Tanh())
            prev_dim = h_dim
        self.trunk = nn.Sequential(*trunk_layers)

        # Actor head: logits over actions
        self.actor_head = nn.Linear(prev_dim, action_dim)

        # Critic head: scalar state value
        self.critic_head = nn.Linear(prev_dim, 1)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass returning action logits and state value.

        Args:
            obs: Observation tensor of shape ``(batch, obs_dim)``.

        Returns:
            Tuple of ``(action_logits, state_value)`` where
            ``action_logits`` has shape ``(batch, action_dim)`` and
            ``state_value`` has shape ``(batch, 1)``.
        """
        features = self.trunk(obs)
        action_logits: torch.Tensor = self.actor_head(features)
        state_value: torch.Tensor = self.critic_head(features)
        return action_logits, state_value

    def get_action_probs(self, obs: torch.Tensor) -> torch.Tensor:
        """Return action probabilities (softmax of logits).

        Args:
            obs: Observation tensor of shape ``(batch, obs_dim)``.

        Returns:
            Action probability tensor of shape ``(batch, action_dim)``.
        """
        logits, _ = self.forward(obs)
        return torch.softmax(logits, dim=-1)
