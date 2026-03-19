# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the episode replay buffer.

Validates:
- Add/sample roundtrip with synthetic data
- Tensor shapes are correct
- Memory stays reasonable for large episode counts
- GAE advantage computation
- Edge cases (empty buffer, oversized sample)

Ticket: OMN-5562
"""

from __future__ import annotations

import pytest
import torch

from omniintelligence.rl.buffer import Batch, Episode, EpisodeReplayBuffer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OBS_DIM = 12  # Matches expected feature vector dimension for routing


def _make_episode(
    obs_dim: int = OBS_DIM,
    action: int = 0,
    reward: float = 1.0,
    value_estimate: float = 0.5,
    log_prob: float = -0.7,
) -> Episode:
    """Create a synthetic episode with the given parameters."""
    return Episode(
        observation=[float(i) for i in range(obs_dim)],
        action=action,
        reward=reward,
        value_estimate=value_estimate,
        log_prob=log_prob,
        episode_id="test-ep",
    )


def _make_buffer(n: int = 100, obs_dim: int = OBS_DIM) -> EpisodeReplayBuffer:
    """Create a buffer pre-loaded with n synthetic episodes."""
    buf = EpisodeReplayBuffer()
    for i in range(n):
        buf.add(
            Episode(
                observation=[float(x + i * 0.01) for x in range(obs_dim)],
                action=i % 4,
                reward=1.0 if i % 3 == 0 else 0.0,
                value_estimate=0.5,
                log_prob=-0.5 - (i * 0.001),
                episode_id=f"ep-{i}",
            )
        )
    return buf


# ---------------------------------------------------------------------------
# Test: basic add and length
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBufferBasics:
    """Test basic buffer operations."""

    def test_empty_buffer_length(self) -> None:
        buf = EpisodeReplayBuffer()
        assert len(buf) == 0

    def test_add_single_episode(self) -> None:
        buf = EpisodeReplayBuffer()
        buf.add(_make_episode())
        assert len(buf) == 1

    def test_add_batch(self) -> None:
        buf = EpisodeReplayBuffer()
        episodes = [_make_episode(action=i) for i in range(10)]
        buf.add_batch(episodes)
        assert len(buf) == 10

    def test_max_capacity_eviction(self) -> None:
        buf = EpisodeReplayBuffer(max_episodes=5)
        for i in range(10):
            buf.add(_make_episode(action=i))
        assert len(buf) == 5

    def test_clear(self) -> None:
        buf = _make_buffer(50)
        buf.clear()
        assert len(buf) == 0

    def test_observation_dim(self) -> None:
        buf = EpisodeReplayBuffer()
        assert buf.observation_dim is None
        buf.add(_make_episode(obs_dim=8))
        assert buf.observation_dim == 8


# ---------------------------------------------------------------------------
# Test: sampling and tensor shapes
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBufferSampling:
    """Test sampling and tensor shape correctness."""

    def test_sample_returns_batch(self) -> None:
        buf = _make_buffer(100)
        batch = buf.sample(32)
        assert isinstance(batch, Batch)

    def test_sample_tensor_shapes(self) -> None:
        buf = _make_buffer(100)
        batch = buf.sample(32)

        assert batch.observations.shape == (32, OBS_DIM)
        assert batch.actions.shape == (32,)
        assert batch.rewards.shape == (32,)
        assert batch.advantages.shape == (32,)
        assert batch.log_probs.shape == (32,)

    def test_sample_tensor_dtypes(self) -> None:
        buf = _make_buffer(100)
        batch = buf.sample(16)

        assert batch.observations.dtype == torch.float32
        assert batch.actions.dtype == torch.long
        assert batch.rewards.dtype == torch.float32
        assert batch.advantages.dtype == torch.float32
        assert batch.log_probs.dtype == torch.float32

    def test_sample_clamped_to_buffer_size(self) -> None:
        buf = _make_buffer(10)
        batch = buf.sample(100)
        assert batch.observations.shape[0] == 10

    def test_sample_all(self) -> None:
        buf = _make_buffer(50)
        batch = buf.sample_all()
        assert batch.observations.shape[0] == 50

    def test_sample_empty_raises(self) -> None:
        buf = EpisodeReplayBuffer()
        with pytest.raises(ValueError, match="empty buffer"):
            buf.sample(10)

    def test_sample_all_empty_raises(self) -> None:
        buf = EpisodeReplayBuffer()
        with pytest.raises(ValueError, match="empty buffer"):
            buf.sample_all()


# ---------------------------------------------------------------------------
# Test: GAE advantage computation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGAEAdvantage:
    """Test GAE advantage computation for one-step routing episodes."""

    def test_advantage_equals_reward_minus_value(self) -> None:
        """For one-step episodes, advantage = reward - value_estimate."""
        buf = EpisodeReplayBuffer()
        buf.add(
            Episode(
                observation=[1.0, 2.0, 3.0],
                action=0,
                reward=1.0,
                value_estimate=0.3,
            )
        )
        batch = buf.sample(1)
        expected_advantage = 1.0 - 0.3
        assert abs(batch.advantages[0].item() - expected_advantage) < 1e-6

    def test_negative_advantage(self) -> None:
        """Advantage is negative when value_estimate > reward."""
        buf = EpisodeReplayBuffer()
        buf.add(
            Episode(
                observation=[1.0, 2.0],
                action=0,
                reward=0.0,
                value_estimate=0.8,
            )
        )
        batch = buf.sample(1)
        assert batch.advantages[0].item() < 0

    def test_zero_advantage(self) -> None:
        """Advantage is zero when reward == value_estimate."""
        buf = EpisodeReplayBuffer()
        buf.add(
            Episode(
                observation=[1.0],
                action=0,
                reward=0.5,
                value_estimate=0.5,
            )
        )
        batch = buf.sample(1)
        assert abs(batch.advantages[0].item()) < 1e-6


# ---------------------------------------------------------------------------
# Test: memory usage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMemoryUsage:
    """Test that memory stays reasonable for large episode counts."""

    def test_memory_estimate_empty(self) -> None:
        buf = EpisodeReplayBuffer()
        assert buf.memory_estimate_bytes() == 0

    def test_memory_estimate_reasonable(self) -> None:
        buf = _make_buffer(100)
        mem = buf.memory_estimate_bytes()
        # 100 episodes with 12-dim observations should be well under 1MB
        assert mem < 1_000_000

    @pytest.mark.slow
    def test_memory_under_500mb_for_10k_episodes(self) -> None:
        """Acceptance criterion: under 500MB for 10K episodes."""
        buf = EpisodeReplayBuffer()
        obs_dim = 20  # generous observation dimension
        for i in range(10_000):
            buf.add(
                Episode(
                    observation=[float(x) for x in range(obs_dim)],
                    action=i % 5,
                    reward=float(i % 2),
                    value_estimate=0.5,
                    log_prob=-0.5,
                )
            )
        mem = buf.memory_estimate_bytes()
        # 500MB = 500 * 1024 * 1024
        assert mem < 500 * 1024 * 1024
        assert len(buf) == 10_000
