# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Episode replay buffer for offline RL training.

Stores routing decision episodes and provides batched tensor sampling
for policy gradient training. Supports GAE advantage computation.

Memory budget: under 500MB for 10K episodes.

Ticket: OMN-5562
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime

import torch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Episode dataclass -- one routing decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Episode:
    """A single routing decision episode.

    Attributes:
        observation: Feature vector observed at decision time.
        action: Index of the selected endpoint/model.
        reward: Scalar reward signal (e.g. success=1, failure=0, with latency penalty).
        value_estimate: Baseline value estimate for advantage computation.
        log_prob: Log-probability of the action under the policy that collected it.
        timestamp: When the observation was recorded.
        episode_id: Optional unique identifier for provenance tracking.
    """

    observation: list[float]
    action: int
    reward: float
    value_estimate: float = 0.0
    log_prob: float = 0.0
    timestamp: datetime | None = None
    episode_id: str | None = None


# ---------------------------------------------------------------------------
# Batch dataclass -- tensors ready for training
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Batch:
    """A batch of episodes as tensors for training.

    All tensors have batch dimension as dim 0.

    Attributes:
        observations: (batch_size, obs_dim) float tensor.
        actions: (batch_size,) long tensor of action indices.
        rewards: (batch_size,) float tensor of rewards.
        advantages: (batch_size,) float tensor of GAE advantages.
        log_probs: (batch_size,) float tensor of log-probabilities.
    """

    observations: torch.Tensor
    actions: torch.Tensor
    rewards: torch.Tensor
    advantages: torch.Tensor
    log_probs: torch.Tensor


# ---------------------------------------------------------------------------
# EpisodeReplayBuffer
# ---------------------------------------------------------------------------


class EpisodeReplayBuffer:
    """Memory-efficient replay buffer for offline RL training.

    Episodes are stored as Python objects and converted to tensors only
    on sample(). This keeps memory usage proportional to episode count
    rather than tensor allocation overhead.

    GAE advantage computation is trivial for one-step routing decisions:
        advantage = reward - value_estimate

    Attributes:
        max_episodes: Maximum buffer capacity. Oldest episodes are evicted
            when capacity is exceeded.
        gamma: Discount factor for GAE computation.
        gae_lambda: Lambda parameter for GAE computation.
    """

    def __init__(
        self,
        max_episodes: int = 100_000,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
    ) -> None:
        self._episodes: list[Episode] = []
        self._max_episodes = max_episodes
        self._gamma = gamma
        self._gae_lambda = gae_lambda

    def add(self, episode: Episode) -> None:
        """Add an episode to the buffer.

        If the buffer is at capacity, the oldest episode is evicted.

        Args:
            episode: A single routing decision episode.
        """
        if len(self._episodes) >= self._max_episodes:
            self._episodes.pop(0)
        self._episodes.append(episode)

    def add_batch(self, episodes: list[Episode]) -> None:
        """Add multiple episodes to the buffer.

        Args:
            episodes: List of episodes to add.
        """
        for ep in episodes:
            self.add(ep)

    def sample(self, batch_size: int) -> Batch:
        """Sample a random batch of episodes as tensors.

        Args:
            batch_size: Number of episodes to sample. Clamped to buffer size.

        Returns:
            Batch with correctly shaped tensors.

        Raises:
            ValueError: If the buffer is empty.
        """
        if not self._episodes:
            msg = "Cannot sample from an empty buffer"
            raise ValueError(msg)

        actual_size = min(batch_size, len(self._episodes))
        sampled = random.sample(self._episodes, actual_size)
        return self._to_batch(sampled)

    def sample_all(self) -> Batch:
        """Return all episodes as a single batch.

        Returns:
            Batch containing all buffered episodes.

        Raises:
            ValueError: If the buffer is empty.
        """
        if not self._episodes:
            msg = "Cannot sample from an empty buffer"
            raise ValueError(msg)
        return self._to_batch(self._episodes)

    def clear(self) -> None:
        """Remove all episodes from the buffer."""
        self._episodes.clear()

    def __len__(self) -> int:
        """Return the number of episodes in the buffer."""
        return len(self._episodes)

    @property
    def observation_dim(self) -> int | None:
        """Return the observation dimension, or None if buffer is empty."""
        if not self._episodes:
            return None
        return len(self._episodes[0].observation)

    def _to_batch(self, episodes: list[Episode]) -> Batch:
        """Convert a list of episodes to a Batch of tensors.

        Computes GAE advantages for one-step episodes:
            advantage = reward - value_estimate

        Args:
            episodes: Episodes to convert.

        Returns:
            Batch with correctly shaped tensors.
        """
        observations = torch.tensor(
            [ep.observation for ep in episodes],
            dtype=torch.float32,
        )
        actions = torch.tensor(
            [ep.action for ep in episodes],
            dtype=torch.long,
        )
        rewards = torch.tensor(
            [ep.reward for ep in episodes],
            dtype=torch.float32,
        )
        log_probs = torch.tensor(
            [ep.log_prob for ep in episodes],
            dtype=torch.float32,
        )

        # GAE for one-step routing: advantage = reward - value_estimate
        advantages = torch.tensor(
            [ep.reward - ep.value_estimate for ep in episodes],
            dtype=torch.float32,
        )

        return Batch(
            observations=observations,
            actions=actions,
            rewards=rewards,
            advantages=advantages,
            log_probs=log_probs,
        )

    def memory_estimate_bytes(self) -> int:
        """Estimate current memory usage in bytes."""
        if not self._episodes:
            return 0

        obs_dim = len(self._episodes[0].observation) if self._episodes else 0
        per_episode = (
            obs_dim * 8  # observation floats
            + 8  # action int
            + 8  # reward float
            + 8  # value_estimate float
            + 8  # log_prob float
            + 200  # Python object overhead estimate
        )
        return per_episode * len(self._episodes)
