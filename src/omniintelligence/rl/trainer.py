# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""PPO trainer with GAE advantage estimation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import torch
import torch.nn.functional as F

from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.policy import PPOPolicy

logger = logging.getLogger(__name__)


@dataclass
class EpisodeReplayBuffer:
    """Simple replay buffer storing episode transitions.

    Each transition consists of (observation, action, reward, next_observation,
    done). All stored as lists and converted to tensors at training time.
    """

    observations: list[list[float]] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    next_observations: list[list[float]] = field(default_factory=list)
    dones: list[bool] = field(default_factory=list)

    def add(
        self,
        obs: list[float],
        action: int,
        reward: float,
        next_obs: list[float],
        done: bool,
    ) -> None:
        """Add a transition to the buffer."""
        self.observations.append(obs)
        self.actions.append(action)
        self.rewards.append(reward)
        self.next_observations.append(next_obs)
        self.dones.append(done)

    def clear(self) -> None:
        """Clear all stored transitions."""
        self.observations.clear()
        self.actions.clear()
        self.rewards.clear()
        self.next_observations.clear()
        self.dones.clear()

    def __len__(self) -> int:
        return len(self.observations)


@dataclass
class TrainingMetrics:
    """Metrics logged per PPO update step."""

    policy_loss: float = 0.0
    value_loss: float = 0.0
    entropy: float = 0.0
    kl_divergence: float = 0.0


class PPOTrainer:
    """Proximal Policy Optimization trainer.

    Implements standard PPO with clipped surrogate objective, GAE advantage
    estimation, and entropy bonus.

    Args:
        policy: The actor-critic policy network.
        buffer: Episode replay buffer containing transitions.
        config: PPO hyperparameters.
    """

    def __init__(
        self,
        policy: PPOPolicy,
        buffer: EpisodeReplayBuffer,
        config: PPOConfig | None = None,
    ) -> None:
        self.policy = policy
        self.buffer = buffer
        self.config = config or PPOConfig()
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=self.config.lr)
        self.metrics_history: list[TrainingMetrics] = []

    def compute_gae(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        next_values: torch.Tensor,
        dones: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute Generalized Advantage Estimation.

        Args:
            rewards: Reward tensor of shape ``(T,)``.
            values: State value predictions of shape ``(T,)``.
            next_values: Next-state value predictions of shape ``(T,)``.
            dones: Done flags of shape ``(T,)``.

        Returns:
            Tuple of ``(advantages, returns)`` each of shape ``(T,)``.
        """
        gamma = self.config.gamma
        gae_lambda = self.config.gae_lambda
        n = len(rewards)

        advantages = torch.zeros(n)
        gae = torch.tensor(0.0)

        for t in reversed(range(n)):
            mask = 1.0 - dones[t].float()
            delta = rewards[t] + gamma * next_values[t] * mask - values[t]
            gae = delta + gamma * gae_lambda * mask * gae
            advantages[t] = gae

        returns = advantages + values
        return advantages, returns

    def update(self) -> TrainingMetrics:
        """Run one PPO update using all data in the buffer.

        Collects the buffer contents, computes GAE advantages, then runs
        multiple epochs of clipped policy gradient updates.

        Returns:
            Aggregated training metrics for this update.
        """
        if len(self.buffer) == 0:
            return TrainingMetrics()

        # Convert buffer to tensors
        obs_t = torch.tensor(self.buffer.observations, dtype=torch.float32)
        actions_t = torch.tensor(self.buffer.actions, dtype=torch.long)
        rewards_t = torch.tensor(self.buffer.rewards, dtype=torch.float32)
        next_obs_t = torch.tensor(self.buffer.next_observations, dtype=torch.float32)
        dones_t = torch.tensor(self.buffer.dones, dtype=torch.float32)

        # Compute old log probs and values (detached)
        with torch.no_grad():
            old_logits, old_values = self.policy(obs_t)
            old_log_probs = F.log_softmax(old_logits, dim=-1)
            old_action_log_probs = old_log_probs.gather(
                1, actions_t.unsqueeze(1)
            ).squeeze(1)

            _, next_values = self.policy(next_obs_t)
            next_values_squeezed = next_values.squeeze(-1)
            old_values_squeezed = old_values.squeeze(-1)

        # Compute GAE
        advantages, returns = self.compute_gae(
            rewards_t, old_values_squeezed, next_values_squeezed, dones_t
        )

        # Normalize advantages
        if len(advantages) > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO epochs
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_kl = 0.0
        num_updates = 0

        n = len(obs_t)
        batch_size = min(self.config.batch_size, n)

        for _epoch in range(self.config.epochs_per_update):
            # Shuffle indices
            indices = torch.randperm(n)

            for start in range(0, n, batch_size):
                end = min(start + batch_size, n)
                batch_idx = indices[start:end]

                batch_obs = obs_t[batch_idx]
                batch_actions = actions_t[batch_idx]
                batch_old_log_probs = old_action_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]

                # Forward pass
                logits, values = self.policy(batch_obs)
                log_probs = F.log_softmax(logits, dim=-1)
                action_log_probs = log_probs.gather(
                    1, batch_actions.unsqueeze(1)
                ).squeeze(1)

                # Policy loss (clipped surrogate)
                ratio = torch.exp(action_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = (
                    torch.clamp(
                        ratio,
                        1.0 - self.config.clip_epsilon,
                        1.0 + self.config.clip_epsilon,
                    )
                    * batch_advantages
                )
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = F.mse_loss(values.squeeze(-1), batch_returns)

                # Entropy bonus
                probs = torch.softmax(logits, dim=-1)
                entropy = -(probs * log_probs).sum(dim=-1).mean()

                # Total loss
                loss = (
                    policy_loss
                    + self.config.value_coeff * value_loss
                    - self.config.entropy_coeff * entropy
                )

                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                # KL divergence approximation
                with torch.no_grad():
                    kl = (batch_old_log_probs - action_log_probs).mean().item()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                total_kl += kl
                num_updates += 1

        # Average metrics
        metrics = TrainingMetrics(
            policy_loss=total_policy_loss / max(num_updates, 1),
            value_loss=total_value_loss / max(num_updates, 1),
            entropy=total_entropy / max(num_updates, 1),
            kl_divergence=total_kl / max(num_updates, 1),
        )

        logger.info(
            "PPO update: policy_loss=%.4f value_loss=%.4f entropy=%.4f kl=%.4f",
            metrics.policy_loss,
            metrics.value_loss,
            metrics.entropy,
            metrics.kl_divergence,
        )

        self.metrics_history.append(metrics)
        return metrics
