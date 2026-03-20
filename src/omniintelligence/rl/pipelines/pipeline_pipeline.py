# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""End-to-end exploratory training pipeline for the pipeline surface.

Orchestrates the full offline training loop for pipeline orchestration
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
from omniintelligence.rl.builders.pipeline_observation_builder import (
    _NUM_STAGES,
    PipelineDataQualityReport,
)
from omniintelligence.rl.checkpoint import save_checkpoint
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.contracts.observations import PipelineObservation
from omniintelligence.rl.policy import PPOPolicy
from omniintelligence.rl.rewards import RewardConfig, RewardShaper
from omniintelligence.rl.trainer import EpisodeReplayBuffer as TrainerBuffer
from omniintelligence.rl.trainer import PPOTrainer, TrainingMetrics

logger = logging.getLogger(__name__)

# Pipeline actions: which stage to prioritize / how to allocate resources
# Exploratory: 5 discrete actions (one per stage)
NUM_PIPELINE_ACTIONS: int = _NUM_STAGES


# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------


@dataclass
class PipelineTrainingPipelineConfig:
    """Configuration for the pipeline training pipeline.

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
    checkpoint_name: str = "pipeline_policy_exploratory.pt"
    ppo_config: PPOConfig = field(default_factory=PPOConfig)
    reward_config: RewardConfig = field(default_factory=RewardConfig)
    synthetic_episodes: int = 200
    log_interval: int = 50
    min_episodes: int = 50


# ---------------------------------------------------------------------------
# Synthetic episode generation
# ---------------------------------------------------------------------------


def generate_synthetic_pipeline_episodes(
    count: int,
    reward_shaper: RewardShaper,
) -> list[Episode]:
    """Generate synthetic pipeline episodes for exploratory training.

    Creates episodes with realistic distributions across pipeline stages
    and outcomes. These are for exploratory baseline only.

    Args:
        count: Number of episodes to generate.
        reward_shaper: Reward shaper for computing scalar rewards.

    Returns:
        List of Episode instances with computed observations and rewards.
    """
    episodes: list[Episode] = []

    for i in range(count):
        # Random stage progress (some stages further along than others)
        stage_progress = [
            max(0.0, min(1.0, random.gauss(0.5, 0.25))) for _ in range(_NUM_STAGES)
        ]

        # Random queue lengths (normalized)
        queue_lengths = [
            max(0.0, min(1.0, random.gauss(0.2, 0.15))) for _ in range(_NUM_STAGES)
        ]

        # Random error counts (normalized, usually low)
        error_counts = [
            max(0.0, min(1.0, random.expovariate(5.0))) for _ in range(_NUM_STAGES)
        ]

        # Action: which stage to prioritize
        action = random.randint(0, NUM_PIPELINE_ACTIONS - 1)

        # Simulate outcome: prioritizing a stage with high queue / low progress
        # tends to produce better outcomes
        stage_need = queue_lengths[action] + (1.0 - stage_progress[action])
        base_success_prob = 0.5 + 0.3 * stage_need
        success = random.random() < min(base_success_prob, 0.95)
        latency_ms = max(50.0, 200.0 + random.gauss(0, 80))

        outcome_metrics: dict[str, object] = {
            "latency_ms": latency_ms,
            "success": success,
            "token_count": 0.0,
            "cost_per_token": 0.0,
        }

        signal = reward_shaper.compute(outcome_metrics)

        observation = stage_progress + queue_lengths + error_counts
        assert len(observation) == PipelineObservation.DIMS, (
            f"Expected {PipelineObservation.DIMS} dims, got {len(observation)}"
        )

        episodes.append(
            Episode(
                observation=observation,
                action=action,
                reward=signal.scalar,
                value_estimate=0.0,
                log_prob=0.0,
                episode_id=f"pipeline-synthetic-{i:06d}",
            )
        )

    return episodes


# ---------------------------------------------------------------------------
# PipelineTrainingPipeline
# ---------------------------------------------------------------------------


@dataclass
class PipelineTrainingResult:
    """Result of a pipeline training run.

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
    data_quality_report: PipelineDataQualityReport | None = None
    is_exploratory_baseline: bool = True


class PipelineTrainingPipeline:
    """End-to-end exploratory training pipeline for pipeline decisions.

    Results are explicitly framed as "exploratory baseline" -- not
    production policy. Skips gracefully if insufficient data exists.

    Args:
        config: Pipeline configuration.
    """

    def __init__(
        self,
        config: PipelineTrainingPipelineConfig | None = None,
    ) -> None:
        self._config = config or PipelineTrainingPipelineConfig()
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
        data_quality_report: PipelineDataQualityReport | None = None,
    ) -> PipelineTrainingResult:
        """Run the full exploratory training pipeline.

        Args:
            episodes: Pre-loaded episodes. If None, generates synthetic data.
            episode_buffer: Pre-populated replay buffer. If None, creates one.
            data_quality_report: Pre-generated quality report for provenance.

        Returns:
            PipelineTrainingResult with checkpoint path and metadata.
        """
        start_time = time.monotonic()
        result = PipelineTrainingResult(data_quality_report=data_quality_report)

        # Step 1: Load or generate episodes
        if episodes is None and episode_buffer is None:
            logger.info(
                "[EXPLORATORY] No pipeline episodes provided, "
                "generating %d synthetic episodes",
                self._config.synthetic_episodes,
            )
            episodes = generate_synthetic_pipeline_episodes(
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
                "Pipeline training skipped gracefully."
            )
            logger.info("[EXPLORATORY] %s", result.skip_reason)
            return result

        logger.info("[EXPLORATORY] Pipeline training with %d episodes", episode_count)

        # Step 3: Initialize PPO components
        obs_dim = PipelineObservation.DIMS
        action_dim = NUM_PIPELINE_ACTIONS
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
            "[EXPLORATORY BASELINE] Pipeline training complete: "
            "%d updates in %.1fs, checkpoint saved to %s. "
            "NOTE: This is an exploratory baseline, NOT a production policy.",
            self._config.num_updates,
            elapsed,
            checkpoint_path,
        )

        return result
