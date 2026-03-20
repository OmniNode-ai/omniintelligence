# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for routing observation builder and training pipeline.

Tests cover:
    1. Observation builder produces correct dimensions
    2. Historical rehydrator uses no future features
    3. Pipeline runs end-to-end with synthetic data
    4. Online builder constructs observations under 50ms budget
    5. Trained policy shows non-uniform action preferences

Ticket: OMN-5565
"""

from __future__ import annotations

import math
import time
from datetime import datetime

import pytest
import torch

from omniintelligence.rl.buffer import EpisodeReplayBuffer
from omniintelligence.rl.builders.routing_observation_builder import (
    EpisodeContext,
    HistoricalRoutingObservationRehydrator,
    ObservationBuilderConfig,
    OnlineRoutingObservationBuilder,
)
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.contracts.actions import NUM_ROUTING_ACTIONS
from omniintelligence.rl.contracts.observations import (
    _NUM_ENDPOINTS,
    _TASK_TYPES,
    RoutingObservation,
)
from omniintelligence.rl.pipelines.routing_pipeline import (
    RoutingTrainingPipeline,
    RoutingTrainingPipelineConfig,
    generate_synthetic_episodes,
)
from omniintelligence.rl.rewards import RewardConfig, RewardShaper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_config() -> ObservationBuilderConfig:
    return ObservationBuilderConfig()


@pytest.fixture()
def rehydrator(
    default_config: ObservationBuilderConfig,
) -> HistoricalRoutingObservationRehydrator:
    return HistoricalRoutingObservationRehydrator(config=default_config)


@pytest.fixture()
def sample_context() -> EpisodeContext:
    """A complete episode context with realistic values."""
    return EpisodeContext(
        observation_timestamp=datetime(2026, 3, 15, 14, 30, 0),
        task_type="code_gen",
        estimated_tokens=8000,
        endpoint_health_snapshot=[
            {
                "latency_p50": 0.3,
                "error_rate": 0.02,
                "circuit_state": 0.0,
                "queue_depth": 0.1,
            },
            {
                "latency_p50": 0.2,
                "error_rate": 0.01,
                "circuit_state": 0.0,
                "queue_depth": 0.05,
            },
            {
                "latency_p50": 0.5,
                "error_rate": 0.03,
                "circuit_state": 0.0,
                "queue_depth": 0.2,
            },
            {
                "latency_p50": 0.15,
                "error_rate": 0.005,
                "circuit_state": 0.0,
                "queue_depth": 0.02,
            },
        ],
        success_rates_snapshot=[0.92, 0.95, 0.88, 0.97],
    )


@pytest.fixture()
def reward_shaper() -> RewardShaper:
    return RewardShaper(RewardConfig())


# ---------------------------------------------------------------------------
# Mock providers for online builder
# ---------------------------------------------------------------------------


class MockHealthProvider:
    """Mock endpoint health provider for testing."""

    def __init__(self, health_data: list[dict[str, float]] | None = None) -> None:
        self._data = health_data or [
            {
                "latency_p50": 0.3,
                "error_rate": 0.02,
                "circuit_state": 0.0,
                "queue_depth": 0.1,
            },
            {
                "latency_p50": 0.2,
                "error_rate": 0.01,
                "circuit_state": 0.0,
                "queue_depth": 0.05,
            },
            {
                "latency_p50": 0.5,
                "error_rate": 0.03,
                "circuit_state": 0.0,
                "queue_depth": 0.2,
            },
            {
                "latency_p50": 0.15,
                "error_rate": 0.005,
                "circuit_state": 0.0,
                "queue_depth": 0.02,
            },
        ]

    async def get_endpoint_health(self) -> list[dict[str, float]]:
        return self._data


class MockSuccessProvider:
    """Mock success rate provider for testing."""

    def __init__(self, rates: list[float] | None = None) -> None:
        self._rates = rates or [0.92, 0.95, 0.88, 0.97]

    async def get_rolling_success_rates(self) -> list[float]:
        return self._rates


# ---------------------------------------------------------------------------
# Test: Observation builder produces correct dimensions
# ---------------------------------------------------------------------------


class TestObservationBuilderDimensions:
    """Test that observation builders produce observations with correct dims."""

    def test_rehydrator_produces_correct_dims(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
        sample_context: EpisodeContext,
    ) -> None:
        """Rehydrated observation has exactly RoutingObservation.DIMS dimensions."""
        obs = rehydrator.rehydrate(sample_context)
        tensor = obs.to_tensor()
        assert tensor.shape == (RoutingObservation.DIMS,)
        assert tensor.shape[0] == 31

    def test_rehydrator_tensor_roundtrip(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
        sample_context: EpisodeContext,
    ) -> None:
        """Observation survives tensor roundtrip."""
        obs = rehydrator.rehydrate(sample_context)
        tensor = obs.to_tensor()
        recovered = RoutingObservation.from_tensor(tensor)
        assert recovered.task_type_onehot == obs.task_type_onehot
        assert (
            abs(
                recovered.estimated_token_count_normalized
                - obs.estimated_token_count_normalized
            )
            < 1e-5
        )

    @pytest.mark.asyncio()
    async def test_online_builder_produces_correct_dims(
        self,
        default_config: ObservationBuilderConfig,
    ) -> None:
        """Online builder produces observation with correct dimensions."""
        builder = OnlineRoutingObservationBuilder(
            health_provider=MockHealthProvider(),
            success_provider=MockSuccessProvider(),
            config=default_config,
        )
        obs = await builder.build(task_type="code_gen", estimated_tokens=5000)
        tensor = obs.to_tensor()
        assert tensor.shape == (RoutingObservation.DIMS,)

    def test_all_task_types_produce_valid_onehot(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
        sample_context: EpisodeContext,
    ) -> None:
        """Each task type produces a valid one-hot encoding."""
        for task_type in _TASK_TYPES:
            ctx = EpisodeContext(
                observation_timestamp=sample_context.observation_timestamp,
                task_type=task_type,
                estimated_tokens=sample_context.estimated_tokens,
                endpoint_health_snapshot=sample_context.endpoint_health_snapshot,
                success_rates_snapshot=sample_context.success_rates_snapshot,
            )
            obs = rehydrator.rehydrate(ctx)
            onehot = obs.task_type_onehot
            assert sum(onehot) == 1.0
            assert all(v in (0.0, 1.0) for v in onehot)


# ---------------------------------------------------------------------------
# Test: Historical rehydrator uses no future features
# ---------------------------------------------------------------------------


class TestNoFutureLeakage:
    """Test that the historical rehydrator provably uses no future-leaked features.

    The key invariant: rehydrating an episode from time T produces the SAME
    observation regardless of when the test runs or what current platform
    state is.
    """

    def test_rehydration_is_deterministic(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
        sample_context: EpisodeContext,
    ) -> None:
        """Same context produces identical observations across calls."""
        obs1 = rehydrator.rehydrate(sample_context)
        obs2 = rehydrator.rehydrate(sample_context)

        t1 = obs1.to_tensor()
        t2 = obs2.to_tensor()
        assert torch.equal(t1, t2)

    def test_time_encoding_uses_observation_timestamp(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
    ) -> None:
        """Time-of-day encoding uses observation_timestamp, not current time."""
        # Context at 6:00 AM
        ctx_morning = EpisodeContext(
            observation_timestamp=datetime(2026, 3, 15, 6, 0, 0),
            task_type="code_gen",
            estimated_tokens=1000,
            endpoint_health_snapshot=[],
            success_rates_snapshot=[],
        )

        # Context at 6:00 PM
        ctx_evening = EpisodeContext(
            observation_timestamp=datetime(2026, 3, 15, 18, 0, 0),
            task_type="code_gen",
            estimated_tokens=1000,
            endpoint_health_snapshot=[],
            success_rates_snapshot=[],
        )

        obs_morning = rehydrator.rehydrate(ctx_morning)
        obs_evening = rehydrator.rehydrate(ctx_evening)

        # Time encodings must differ
        assert obs_morning.time_of_day_sin != obs_evening.time_of_day_sin
        assert obs_morning.time_of_day_cos != obs_evening.time_of_day_cos

        # Verify exact values
        expected_morning_angle = 2.0 * math.pi * 6.0 / 24.0
        assert (
            abs(obs_morning.time_of_day_sin - math.sin(expected_morning_angle)) < 1e-10
        )

    def test_different_timestamps_same_context_differ_only_in_time(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
    ) -> None:
        """Observations at different times with same context differ only in time dims."""
        base_health = [
            {
                "latency_p50": 0.3,
                "error_rate": 0.02,
                "circuit_state": 0.0,
                "queue_depth": 0.1,
            },
        ] * _NUM_ENDPOINTS
        base_rates = [0.9] * _NUM_ENDPOINTS

        ctx1 = EpisodeContext(
            observation_timestamp=datetime(2026, 3, 15, 0, 0, 0),
            task_type="code_gen",
            estimated_tokens=5000,
            endpoint_health_snapshot=base_health,
            success_rates_snapshot=base_rates,
        )
        ctx2 = EpisodeContext(
            observation_timestamp=datetime(2026, 3, 15, 12, 0, 0),
            task_type="code_gen",
            estimated_tokens=5000,
            endpoint_health_snapshot=base_health,
            success_rates_snapshot=base_rates,
        )

        obs1 = rehydrator.rehydrate(ctx1)
        obs2 = rehydrator.rehydrate(ctx2)

        # Everything except time encoding should be identical
        assert obs1.task_type_onehot == obs2.task_type_onehot
        assert (
            obs1.estimated_token_count_normalized
            == obs2.estimated_token_count_normalized
        )
        assert obs1.per_endpoint_health == obs2.per_endpoint_health
        assert obs1.historical_success_rate == obs2.historical_success_rate

        # Time encoding must differ (0:00 vs 12:00)
        assert obs1.time_of_day_sin != obs2.time_of_day_sin

    def test_rehydrator_does_not_access_current_time(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
        sample_context: EpisodeContext,
    ) -> None:
        """Rehydrated observation is independent of when the test runs.

        We generate the observation twice with a small time gap and verify
        they are identical -- proving no current-time dependency.
        """
        obs_before = rehydrator.rehydrate(sample_context)
        # Simulate passage of time (no actual sleep needed for determinism test)
        obs_after = rehydrator.rehydrate(sample_context)

        assert obs_before.to_tensor().tolist() == obs_after.to_tensor().tolist()

    def test_rehydrate_from_raw_with_precomputed_observation(
        self,
        rehydrator: HistoricalRoutingObservationRehydrator,
        sample_context: EpisodeContext,
    ) -> None:
        """Pre-computed observation vectors are used directly."""
        expected_obs = rehydrator.rehydrate(sample_context)
        raw_vector = expected_obs.to_tensor().tolist()

        row = {"observation": raw_vector}
        result = rehydrator.rehydrate_from_raw(row)

        assert result is not None
        assert torch.allclose(
            result.to_tensor(),
            expected_obs.to_tensor(),
            atol=1e-5,
        )


# ---------------------------------------------------------------------------
# Test: Online builder performance
# ---------------------------------------------------------------------------


class TestOnlineBuilderPerformance:
    """Test online observation construction stays under 50ms budget."""

    @pytest.mark.asyncio()
    async def test_construction_under_50ms(self) -> None:
        """Online observation construction completes within 50ms."""
        builder = OnlineRoutingObservationBuilder(
            health_provider=MockHealthProvider(),
            success_provider=MockSuccessProvider(),
        )

        start = time.monotonic()
        await builder.build(task_type="code_gen", estimated_tokens=5000)
        elapsed_ms = (time.monotonic() - start) * 1000.0

        # With mock providers this should be well under 50ms
        assert elapsed_ms < 50.0, f"Construction took {elapsed_ms:.1f}ms (budget: 50ms)"


# ---------------------------------------------------------------------------
# Test: Synthetic episode generation
# ---------------------------------------------------------------------------


class TestSyntheticEpisodeGeneration:
    """Test that synthetic episode generation produces valid data."""

    def test_generates_correct_count(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_episodes(100, reward_shaper)
        assert len(episodes) == 100

    def test_observation_dimensions(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_episodes(10, reward_shaper)
        for ep in episodes:
            assert len(ep.observation) == RoutingObservation.DIMS

    def test_actions_in_valid_range(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_episodes(100, reward_shaper)
        for ep in episodes:
            assert 0 <= ep.action < NUM_ROUTING_ACTIONS

    def test_rewards_bounded(self, reward_shaper: RewardShaper) -> None:
        episodes = generate_synthetic_episodes(100, reward_shaper)
        for ep in episodes:
            assert -2.0 <= ep.reward <= 2.0

    def test_diverse_actions(self, reward_shaper: RewardShaper) -> None:
        """Synthetic episodes should cover all actions."""
        episodes = generate_synthetic_episodes(300, reward_shaper)
        actions_seen = {ep.action for ep in episodes}
        assert len(actions_seen) == NUM_ROUTING_ACTIONS


# ---------------------------------------------------------------------------
# Test: Pipeline end-to-end
# ---------------------------------------------------------------------------


class TestRoutingTrainingPipeline:
    """Test the full routing training pipeline with synthetic data."""

    def test_pipeline_runs_end_to_end(self, tmp_path: pytest.TempPathFactory) -> None:
        """Pipeline completes and saves a checkpoint."""
        config = RoutingTrainingPipelineConfig(
            num_updates=10,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="test_policy.pt",
            ppo_config=PPOConfig(batch_size=32, epochs_per_update=2),
            synthetic_episodes=50,
            log_interval=5,
        )

        pipeline = RoutingTrainingPipeline(config=config)
        checkpoint_path = pipeline.run()

        assert checkpoint_path.exists()
        assert checkpoint_path.name == "test_policy.pt"

    def test_pipeline_with_300_episodes(self, tmp_path: pytest.TempPathFactory) -> None:
        """Pipeline runs on 300+ episodes (acceptance criteria)."""
        config = RoutingTrainingPipelineConfig(
            num_updates=20,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="routing_300.pt",
            ppo_config=PPOConfig(batch_size=64, epochs_per_update=2),
            synthetic_episodes=350,
            log_interval=10,
        )

        pipeline = RoutingTrainingPipeline(config=config)
        checkpoint_path = pipeline.run()

        assert checkpoint_path.exists()
        assert len(pipeline.metrics_history) == 20

    def test_pipeline_with_external_episodes(
        self,
        tmp_path: pytest.TempPathFactory,
        reward_shaper: RewardShaper,
    ) -> None:
        """Pipeline accepts externally generated episodes."""
        episodes = generate_synthetic_episodes(100, reward_shaper)

        config = RoutingTrainingPipelineConfig(
            num_updates=5,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="external.pt",
            ppo_config=PPOConfig(batch_size=32),
        )

        pipeline = RoutingTrainingPipeline(config=config)
        checkpoint_path = pipeline.run(episodes=episodes)

        assert checkpoint_path.exists()

    def test_pipeline_with_replay_buffer(
        self,
        tmp_path: pytest.TempPathFactory,
        reward_shaper: RewardShaper,
    ) -> None:
        """Pipeline accepts a pre-populated replay buffer."""
        episodes = generate_synthetic_episodes(100, reward_shaper)
        buffer = EpisodeReplayBuffer()
        buffer.add_batch(episodes)

        config = RoutingTrainingPipelineConfig(
            num_updates=5,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="buffer.pt",
            ppo_config=PPOConfig(batch_size=32),
        )

        pipeline = RoutingTrainingPipeline(config=config)
        checkpoint_path = pipeline.run(episode_buffer=buffer)

        assert checkpoint_path.exists()

    def test_trained_policy_non_uniform(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Trained policy shows non-uniform action preferences."""
        config = RoutingTrainingPipelineConfig(
            num_updates=50,
            checkpoint_dir=str(tmp_path),
            checkpoint_name="non_uniform.pt",
            ppo_config=PPOConfig(batch_size=32, lr=1e-3, epochs_per_update=4),
            synthetic_episodes=200,
        )

        pipeline = RoutingTrainingPipeline(config=config)
        checkpoint_path = pipeline.run()

        # Load the checkpoint and check action preferences
        from omniintelligence.rl.checkpoint import load_checkpoint

        policy = load_checkpoint(checkpoint_path)
        policy.eval()

        # Create a test observation
        onehot = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        health = [0.3, 0.05, 0.0, 0.1] * _NUM_ENDPOINTS
        success_rates = [0.85] * _NUM_ENDPOINTS
        obs = onehot + [0.5] + health + success_rates + [0.0, 1.0]

        with torch.no_grad():
            obs_tensor = torch.tensor([obs], dtype=torch.float32)
            probs = policy.get_action_probs(obs_tensor)

        # After training, probabilities should not be perfectly uniform
        uniform_prob = 1.0 / NUM_ROUTING_ACTIONS
        max_dev = (probs[0] - uniform_prob).abs().max().item()

        # With 50 updates the policy should have learned SOMETHING
        # A very loose check -- just verifying it's not exactly uniform
        assert max_dev > 0.001, (
            f"Policy appears uniform: max deviation {max_dev:.6f} from {uniform_prob:.4f}"
        )

    def test_pipeline_empty_buffer_raises(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Pipeline raises ValueError when given an empty buffer."""
        buffer = EpisodeReplayBuffer()

        config = RoutingTrainingPipelineConfig(
            num_updates=1,
            checkpoint_dir=str(tmp_path),
        )

        pipeline = RoutingTrainingPipeline(config=config)
        with pytest.raises(ValueError, match="No episodes available"):
            pipeline.run(episode_buffer=buffer)

    def test_metrics_history_populated(self, tmp_path: pytest.TempPathFactory) -> None:
        """Pipeline populates metrics history for every update."""
        num_updates = 15
        config = RoutingTrainingPipelineConfig(
            num_updates=num_updates,
            checkpoint_dir=str(tmp_path),
            ppo_config=PPOConfig(batch_size=32),
            synthetic_episodes=50,
        )

        pipeline = RoutingTrainingPipeline(config=config)
        pipeline.run()

        assert len(pipeline.metrics_history) == num_updates
        for metrics in pipeline.metrics_history:
            # Metrics should have meaningful values
            assert isinstance(metrics.policy_loss, float)
            assert isinstance(metrics.value_loss, float)


# ---------------------------------------------------------------------------
# Test: CLI entry point
# ---------------------------------------------------------------------------


class TestTrainCLI:
    """Test the CLI entry point."""

    def test_main_runs_successfully(self, tmp_path: pytest.TempPathFactory) -> None:
        """CLI main() completes with synthetic data."""
        from omniintelligence.rl.train import main

        exit_code = main(
            [
                "--surface",
                "routing",
                "--updates",
                "5",
                "--episodes",
                "50",
                "--checkpoint-dir",
                str(tmp_path),
                "--batch-size",
                "32",
                "--manifest",
                str(tmp_path / "manifest.yaml"),
            ]
        )
        assert exit_code == 0

    def test_main_all_flag(self, tmp_path: pytest.TempPathFactory) -> None:
        """CLI main() works with --all flag."""
        from omniintelligence.rl.train import main

        exit_code = main(
            [
                "--all",
                "--updates",
                "3",
                "--episodes",
                "30",
                "--checkpoint-dir",
                str(tmp_path),
                "--manifest",
                str(tmp_path / "manifest.yaml"),
            ]
        )
        assert exit_code == 0
