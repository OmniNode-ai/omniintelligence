# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for team training pipeline (exploratory).

Tests cover:
    1. Pipeline runs end-to-end with synthetic data
    2. Pipeline skips gracefully with insufficient data
    3. Pipeline accepts external episodes
    4. Pipeline accepts pre-populated replay buffer
    5. Synthetic episode generation produces valid data
    6. Results are marked as exploratory baseline

Ticket: OMN-5572
"""

from __future__ import annotations

import pytest

from omniintelligence.rl.buffer import EpisodeReplayBuffer
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.contracts.observations import TeamObservation
from omniintelligence.rl.pipelines.team_pipeline import (
    NUM_TEAM_ACTIONS,
    TeamTrainingPipeline,
    TeamTrainingPipelineConfig,
    generate_synthetic_team_episodes,
)
from omniintelligence.rl.rewards import RewardConfig, RewardShaper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def reward_shaper() -> RewardShaper:
    return RewardShaper(RewardConfig())


# ---------------------------------------------------------------------------
# Test: Synthetic episode generation
# ---------------------------------------------------------------------------


class TestSyntheticTeamEpisodes:
    """Test synthetic team episode generation."""

    def test_generates_correct_count(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_team_episodes(100, reward_shaper)
        assert len(episodes) == 100

    def test_observation_dimensions(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_team_episodes(10, reward_shaper)
        for ep in episodes:
            assert len(ep.observation) == TeamObservation.DIMS

    def test_actions_in_valid_range(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_team_episodes(100, reward_shaper)
        for ep in episodes:
            assert 0 <= ep.action < NUM_TEAM_ACTIONS

    def test_rewards_bounded(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_team_episodes(100, reward_shaper)
        for ep in episodes:
            assert -2.0 <= ep.reward <= 2.0

    def test_diverse_actions(self, reward_shaper: RewardShaper) -> None:
        """Synthetic episodes should cover all actions."""
        episodes = generate_synthetic_team_episodes(300, reward_shaper)
        actions_seen = {ep.action for ep in episodes}
        assert len(actions_seen) == NUM_TEAM_ACTIONS


# ---------------------------------------------------------------------------
# Test: Pipeline end-to-end
# ---------------------------------------------------------------------------


class TestTeamTrainingPipeline:
    """Test the full team training pipeline with synthetic data."""

    def test_pipeline_runs_end_to_end(self, tmp_path: pytest.TempPathFactory) -> None:
        """Pipeline completes and saves a checkpoint."""
        config = TeamTrainingPipelineConfig(
            num_updates=10,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="test_team_policy.pt",
            ppo_config=PPOConfig(batch_size=32, epochs_per_update=2),
            synthetic_episodes=80,
            log_interval=5,
        )

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run()

        assert not result.skipped
        assert result.checkpoint_path is not None
        assert result.checkpoint_path.exists()
        assert result.is_exploratory_baseline is True

    def test_pipeline_skips_gracefully_insufficient_data(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Pipeline skips when insufficient episodes are provided."""
        config = TeamTrainingPipelineConfig(
            num_updates=10,
            checkpoint_dir=str(tmp_path),
            min_episodes=100,
        )

        # Provide fewer episodes than min_episodes
        shaper = RewardShaper(RewardConfig())
        episodes = generate_synthetic_team_episodes(20, shaper)

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run(episodes=episodes)

        assert result.skipped is True
        assert "Insufficient data" in result.skip_reason
        assert result.checkpoint_path is None

    def test_pipeline_with_external_episodes(
        self,
        tmp_path: pytest.TempPathFactory,
        reward_shaper: RewardShaper,
    ) -> None:
        """Pipeline accepts externally generated episodes."""
        episodes = generate_synthetic_team_episodes(100, reward_shaper)

        config = TeamTrainingPipelineConfig(
            num_updates=5,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="external_team.pt",
            ppo_config=PPOConfig(batch_size=32),
        )

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run(episodes=episodes)

        assert not result.skipped
        assert result.checkpoint_path is not None
        assert result.checkpoint_path.exists()

    def test_pipeline_with_replay_buffer(
        self,
        tmp_path: pytest.TempPathFactory,
        reward_shaper: RewardShaper,
    ) -> None:
        """Pipeline accepts a pre-populated replay buffer."""
        episodes = generate_synthetic_team_episodes(100, reward_shaper)
        buffer = EpisodeReplayBuffer()
        buffer.add_batch(episodes)

        config = TeamTrainingPipelineConfig(
            num_updates=5,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="buffer_team.pt",
            ppo_config=PPOConfig(batch_size=32),
        )

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run(episode_buffer=buffer)

        assert not result.skipped
        assert result.checkpoint_path is not None

    def test_metrics_history_populated(self, tmp_path: pytest.TempPathFactory) -> None:
        """Pipeline populates metrics history for every update."""
        num_updates = 15
        config = TeamTrainingPipelineConfig(
            num_updates=num_updates,
            checkpoint_dir=str(tmp_path),
            ppo_config=PPOConfig(batch_size=32),
            synthetic_episodes=80,
        )

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run()

        assert len(result.metrics_history) == num_updates
        for metrics in result.metrics_history:
            assert isinstance(metrics.policy_loss, float)
            assert isinstance(metrics.value_loss, float)

    def test_result_always_exploratory(self, tmp_path: pytest.TempPathFactory) -> None:
        """Result is always marked as exploratory baseline."""
        config = TeamTrainingPipelineConfig(
            num_updates=5,
            checkpoint_dir=str(tmp_path),
            ppo_config=PPOConfig(batch_size=32),
            synthetic_episodes=80,
        )

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run()
        assert result.is_exploratory_baseline is True

    def test_empty_buffer_skips(self, tmp_path: pytest.TempPathFactory) -> None:
        """Pipeline skips gracefully when given an empty buffer."""
        buffer = EpisodeReplayBuffer()

        config = TeamTrainingPipelineConfig(
            num_updates=1,
            checkpoint_dir=str(tmp_path),
            min_episodes=1,
        )

        pipeline = TeamTrainingPipeline(config=config)
        result = pipeline.run(episode_buffer=buffer)
        assert result.skipped is True
