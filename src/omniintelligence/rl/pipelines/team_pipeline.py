# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""End-to-end exploratory training pipeline for the team surface.

Orchestrates the full offline training loop for team/agent coordination
decisions. Results are explicitly framed as "exploratory baseline" --
not production policy. Skips gracefully if insufficient data exists.

Ticket: OMN-5572
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from omniintelligence.rl.buffer import Episode, EpisodeReplayBuffer
from omniintelligence.rl.builders.team_observation_builder import (
    _NUM_AGENT_SLOTS,
    TeamDataQualityReport,
)
from omniintelligence.rl.checkpoint import save_checkpoint
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.contracts.observations import TeamObservation
from omniintelligence.rl.policy import PPOPolicy
from omniintelligence.rl.rewards import RewardConfig, RewardShaper
from omniintelligence.rl.trainer import EpisodeReplayBuffer as TrainerBuffer
from omniintelligence.rl.trainer import PPOTrainer, TrainingMetrics

logger = logging.getLogger(__name__)

# Team actions: which agent to assign next task to
# Exploratory: 5 discrete actions (one per agent slot)
NUM_TEAM_ACTIONS: int = _NUM_AGENT_SLOTS


# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------


@dataclass
class TeamTrainingPipelineConfig:
    """Configuration for the team training pipeline.

    Attributes:
        num_updates: Number of PPO update iterations to run.
        checkpoint_dir: Directory to save model checkpoints.
        checkpoint_name: Filename for the checkpoint.
        ppo_config: PPO hyperparameter configuration.
        reward_config: Reward shaping configuration.
        synthetic_episodes: Number of synthetic episodes to generate
            if no database source is available.
        log_interval: Log training metrics every N updates.
        min_episodes: Minimum episodes required to attempt training.
            Below this threshold, training is skipped gracefully.
    """

    num_updates: int = 200
    checkpoint_dir: str = "checkpoints"
    checkpoint_name: str = "team_policy_exploratory.pt"
    ppo_config: PPOConfig = field(default_factory=PPOConfig)
    reward_config: RewardConfig = field(default_factory=RewardConfig)
    synthetic_episodes: int = 200
    log_interval: int = 50
    min_episodes: int = 50


# ---------------------------------------------------------------------------
# Synthetic episode generation
# ---------------------------------------------------------------------------


def generate_synthetic_team_episodes(
    count: int,
    reward_shaper: RewardShaper,
) -> list[Episode]:
    """Generate synthetic team episodes for exploratory training.

    Creates episodes with realistic distributions across agent utilization,
    task complexity, and coordination outcomes. These are for exploratory
    baseline only.

    Args:
        count: Number of episodes to generate.
        reward_shaper: Reward shaper for computing scalar rewards.

    Returns:
        List of Episode instances with computed observations and rewards.
    """
    episodes: list[Episode] = []

    for i in range(count):
        # Random agent utilization (some agents busier than others)
        agent_utilization = [
            max(0.0, min(1.0, random.gauss(0.5, 0.3))) for _ in range(_NUM_AGENT_SLOTS)
        ]

        # Scalar features
        task_complexity = max(0.0, min(1.0, random.gauss(0.5, 0.25)))
        pending_tasks = max(0.0, min(1.0, random.gauss(0.3, 0.2)))
        time_pressure = max(0.0, min(1.0, random.gauss(0.4, 0.3)))
        success_rate = max(0.0, min(1.0, random.gauss(0.8, 0.1)))
        coordination_overhead = max(0.0, min(1.0, random.expovariate(3.0)))

        # Action: which agent to assign the task to
        action = random.randint(0, NUM_TEAM_ACTIONS - 1)

        # Simulate outcome: assigning to less utilized agents tends to succeed
        utilization_of_chosen = agent_utilization[action]
        base_success_prob = 0.9 - 0.4 * utilization_of_chosen
        base_success_prob = max(0.3, min(0.95, base_success_prob))
        success = random.random() < base_success_prob
        latency_ms = max(
            50.0, 150.0 + 200.0 * utilization_of_chosen + random.gauss(0, 50)
        )

        outcome_metrics: dict[str, object] = {
            "latency_ms": latency_ms,
            "success": success,
            "token_count": 0.0,
            "cost_per_token": 0.0,
        }

        signal = reward_shaper.compute(outcome_metrics)

        observation = agent_utilization + [
            task_complexity,
            pending_tasks,
            time_pressure,
            success_rate,
            coordination_overhead,
        ]
        assert len(observation) == TeamObservation.DIMS, (
            f"Expected {TeamObservation.DIMS} dims, got {len(observation)}"
        )

        episodes.append(
            Episode(
                observation=observation,
                action=action,
                reward=signal.scalar,
                value_estimate=0.0,
                log_prob=0.0,
                episode_id=f"team-synthetic-{i:06d}",
            )
        )

    return episodes


# ---------------------------------------------------------------------------
# TeamTrainingPipeline
# ---------------------------------------------------------------------------


@dataclass
class TeamTrainingResult:
    """Result of a team training run.

    Attributes:
        checkpoint_path: Path to saved checkpoint, or None if training skipped.
        skipped: Whether training was skipped due to insufficient data.
        skip_reason: Human-readable reason for skipping.
        metrics_history: Training metrics for each update step.
        data_quality_report: Data quality report if available.
        is_exploratory_baseline: Always True -- results are exploratory.
    """

    checkpoint_path: Path | None = None
    skipped: bool = False
    skip_reason: str = ""
    metrics_history: list[TrainingMetrics] = field(default_factory=list)
    data_quality_report: TeamDataQualityReport | None = None
    is_exploratory_baseline: bool = True


class TeamTrainingPipeline:
    """End-to-end exploratory training pipeline for team decisions.

    Results are explicitly framed as "exploratory baseline" -- not
    production policy. Skips gracefully if insufficient data exists.

    Args:
        config: Pipeline configuration.
    """

    def __init__(
        self,
        config: TeamTrainingPipelineConfig | None = None,
    ) -> None:
        self._config = config or TeamTrainingPipelineConfig()
        self._reward_shaper = RewardShaper(self._config.reward_config)
        self._metrics_history: list[TrainingMetrics] = []

    @property
    def metrics_history(self) -> list[TrainingMetrics]:
        """Return the full training metrics history."""
        return self._metrics_history

    def run(
        self,
        *,
        episodes: list[Episode] | None = None,
        episode_buffer: EpisodeReplayBuffer | None = None,
        data_quality_report: TeamDataQualityReport | None = None,
    ) -> TeamTrainingResult:
        """Run the full exploratory training pipeline.

        Args:
            episodes: Pre-loaded episodes. If None, generates synthetic data.
            episode_buffer: Pre-populated replay buffer. If None, creates one.
            data_quality_report: Pre-generated quality report for provenance.

        Returns:
            TeamTrainingResult with checkpoint path and metadata.
        """
        start_time = time.monotonic()
        result = TeamTrainingResult(data_quality_report=data_quality_report)

        # Step 1: Load or generate episodes
        if episodes is None and episode_buffer is None:
            logger.info(
                "[EXPLORATORY] No team episodes provided, "
                "generating %d synthetic episodes",
                self._config.synthetic_episodes,
            )
            episodes = generate_synthetic_team_episodes(
                self._config.synthetic_episodes,
                self._reward_shaper,
            )

        # Step 2: Populate replay buffer
        if episode_buffer is None:
            episode_buffer = EpisodeReplayBuffer()
            if episodes is not None:
                episode_buffer.add_batch(episodes)

        episode_count = len(episode_buffer)

        # Graceful skip if insufficient data
        if episode_count < self._config.min_episodes:
            result.skipped = True
            result.skip_reason = (
                f"Insufficient data: {episode_count} episodes "
                f"(minimum: {self._config.min_episodes}). "
                "Team training skipped gracefully."
            )
            logger.info("[EXPLORATORY] %s", result.skip_reason)
            return result

        logger.info("[EXPLORATORY] Team training with %d episodes", episode_count)

        # Step 3: Initialize PPO components
        obs_dim = TeamObservation.DIMS
        action_dim = NUM_TEAM_ACTIONS
        ppo_config = self._config.ppo_config

        policy = PPOPolicy(
            obs_dim=obs_dim,
            action_dim=action_dim,
            config=ppo_config,
        )

        trainer_buffer = TrainerBuffer()

        batch = episode_buffer.sample_all()
        for i in range(batch.observations.shape[0]):
            obs_list = batch.observations[i].tolist()
            trainer_buffer.add(
                obs=obs_list,
                action=int(batch.actions[i].item()),
                reward=float(batch.rewards[i].item()),
                next_obs=obs_list,
                done=True,
            )

        trainer = PPOTrainer(
            policy=policy,
            buffer=trainer_buffer,
            config=ppo_config,
        )

        # Step 4: Training loop
        logger.info(
            "[EXPLORATORY] Starting PPO training: %d updates, batch_size=%d",
            self._config.num_updates,
            ppo_config.batch_size,
        )

        for update_idx in range(self._config.num_updates):
            metrics = trainer.update()
            self._metrics_history.append(metrics)

            if (update_idx + 1) % self._config.log_interval == 0:
                logger.info(
                    "[EXPLORATORY] Update %d/%d: "
                    "policy_loss=%.4f value_loss=%.4f entropy=%.4f",
                    update_idx + 1,
                    self._config.num_updates,
                    metrics.policy_loss,
                    metrics.value_loss,
                    metrics.entropy,
                )

        result.metrics_history = self._metrics_history

        # Step 5: Save checkpoint
        checkpoint_dir = Path(self._config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / self._config.checkpoint_name

        save_checkpoint(policy, checkpoint_path)
        result.checkpoint_path = checkpoint_path

        elapsed = time.monotonic() - start_time
        logger.info(
            "[EXPLORATORY BASELINE] Team training complete: "
            "%d updates in %.1fs, checkpoint saved to %s. "
            "NOTE: This is an exploratory baseline, NOT a production policy.",
            self._config.num_updates,
            elapsed,
            checkpoint_path,
        )

        return result
