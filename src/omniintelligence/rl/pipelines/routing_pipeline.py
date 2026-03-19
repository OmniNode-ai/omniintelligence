# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""End-to-end routing training pipeline.

Orchestrates the full offline training loop:
    1. Load episodes from PostgresEpisodeSource (or synthetic data)
    2. Build observations via HistoricalRoutingObservationRehydrator
    3. Compute rewards via RewardShaper
    4. Fill the PPO trainer's EpisodeReplayBuffer
    5. Run PPO updates
    6. Save checkpoint

Acceptance criteria:
    - Runs end-to-end on 300+ backfilled episodes
    - Completes in under 5 minutes for 500 updates on CPU
    - Trained policy shows non-uniform action preferences

Ticket: OMN-5565
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import torch

from omniintelligence.rl.buffer import Episode, EpisodeReplayBuffer
from omniintelligence.rl.checkpoint import save_checkpoint
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.contracts.actions import NUM_ROUTING_ACTIONS
from omniintelligence.rl.contracts.observations import (
    _NUM_ENDPOINTS,
    _TASK_TYPES,
    RoutingObservation,
)
from omniintelligence.rl.policy import PPOPolicy
from omniintelligence.rl.rewards import RewardConfig, RewardShaper
from omniintelligence.rl.trainer import EpisodeReplayBuffer as TrainerBuffer
from omniintelligence.rl.trainer import PPOTrainer, TrainingMetrics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------


@dataclass
class RoutingTrainingPipelineConfig:
    """Configuration for the routing training pipeline.

    Attributes:
        num_updates: Number of PPO update iterations to run.
        checkpoint_dir: Directory to save model checkpoints.
        checkpoint_name: Filename for the checkpoint.
        ppo_config: PPO hyperparameter configuration.
        reward_config: Reward shaping configuration.
        synthetic_episodes: Number of synthetic episodes to generate
            if no database source is available.
        log_interval: Log training metrics every N updates.
    """

    num_updates: int = 500
    checkpoint_dir: str = "checkpoints"
    checkpoint_name: str = "routing_policy.pt"
    ppo_config: PPOConfig = field(default_factory=PPOConfig)
    reward_config: RewardConfig = field(default_factory=RewardConfig)
    synthetic_episodes: int = 350
    log_interval: int = 50


# ---------------------------------------------------------------------------
# Synthetic episode generation
# ---------------------------------------------------------------------------


def generate_synthetic_episodes(
    count: int,
    reward_shaper: RewardShaper,
) -> list[Episode]:
    """Generate synthetic routing episodes for offline training.

    Creates episodes with realistic distributions across task types,
    endpoints, and outcomes. Rewards are computed via the RewardShaper
    to ensure consistency with the actual reward function.

    Args:
        count: Number of episodes to generate.
        reward_shaper: Reward shaper for computing scalar rewards.

    Returns:
        List of Episode instances with computed observations and rewards.
    """
    episodes: list[Episode] = []

    for i in range(count):
        # Random task type
        task_type = random.choice(_TASK_TYPES)

        # Random token count (biased towards smaller requests)
        estimated_tokens = int(random.lognormvariate(8.0, 1.5))
        estimated_tokens = min(estimated_tokens, 65_536)

        # Random endpoint selection (action)
        action = random.randint(0, NUM_ROUTING_ACTIONS - 1)

        # Generate outcome metrics that vary by endpoint
        # Endpoints have different latency / success profiles
        endpoint_profiles = {
            0: {"base_latency": 300.0, "success_prob": 0.92},  # Qwen3-30B
            1: {"base_latency": 200.0, "success_prob": 0.95},  # Qwen3-14B
            2: {"base_latency": 500.0, "success_prob": 0.88},  # DeepSeek-R1
            3: {"base_latency": 150.0, "success_prob": 0.97},  # Embedding
        }

        profile = endpoint_profiles[action]
        latency_ms = max(50.0, profile["base_latency"] + random.gauss(0, 100))
        success = random.random() < profile["success_prob"]
        token_count = float(estimated_tokens)
        cost_per_token = [0.00003, 0.00002, 0.00004, 0.00001][action]

        outcome_metrics: dict[str, object] = {
            "latency_ms": latency_ms,
            "success": success,
            "token_count": token_count,
            "cost_per_token": cost_per_token,
        }

        # Compute reward
        signal = reward_shaper.compute(outcome_metrics)

        # Build observation vector
        onehot = [1.0 if t == task_type else 0.0 for t in _TASK_TYPES]
        token_norm = min(estimated_tokens / 65_536, 1.0)

        # Synthetic endpoint health (varies per episode for diversity)
        health_features: list[float] = []
        for ep_idx in range(_NUM_ENDPOINTS):
            health_features.extend(
                [
                    max(0.0, 0.3 + random.gauss(0, 0.1)),  # latency_p50
                    max(0.0, min(1.0, 0.05 + random.gauss(0, 0.02))),  # error_rate
                    random.choice([0.0, 0.0, 0.0, 0.5, 1.0]),  # circuit_state
                    max(0.0, random.gauss(0.1, 0.05)),  # queue_depth
                ]
            )

        # Success rates
        success_rates = [
            max(0.0, min(1.0, 0.85 + random.gauss(0, 0.05)))
            for _ in range(_NUM_ENDPOINTS)
        ]

        # Time encoding
        hour = random.uniform(0, 24)
        angle = 2.0 * math.pi * hour / 24.0
        time_sin = math.sin(angle)
        time_cos = math.cos(angle)

        observation = (
            onehot
            + [token_norm]
            + health_features
            + success_rates
            + [time_sin, time_cos]
        )

        assert len(observation) == RoutingObservation.DIMS, (
            f"Expected {RoutingObservation.DIMS} dims, got {len(observation)}"
        )

        episodes.append(
            Episode(
                observation=observation,
                action=action,
                reward=signal.scalar,
                value_estimate=0.0,
                log_prob=0.0,
                episode_id=f"synthetic-{i:06d}",
            )
        )

    return episodes


# ---------------------------------------------------------------------------
# RoutingTrainingPipeline
# ---------------------------------------------------------------------------


class RoutingTrainingPipeline:
    """End-to-end offline training pipeline for routing policy.

    Orchestrates:
        1. Episode loading (from buffer or synthetic generation)
        2. Reward computation
        3. PPO training loop
        4. Checkpoint saving

    Args:
        config: Pipeline configuration.
    """

    def __init__(
        self,
        config: RoutingTrainingPipelineConfig | None = None,
    ) -> None:
        self._config = config or RoutingTrainingPipelineConfig()
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
    ) -> Path:
        """Run the full training pipeline.

        Args:
            episodes: Pre-loaded episodes. If None, generates synthetic data.
            episode_buffer: Pre-populated replay buffer. If None, creates one.

        Returns:
            Path to the saved checkpoint file.
        """
        start_time = time.monotonic()

        # Step 1: Load or generate episodes
        if episodes is None and episode_buffer is None:
            logger.info(
                "No episodes provided, generating %d synthetic episodes",
                self._config.synthetic_episodes,
            )
            episodes = generate_synthetic_episodes(
                self._config.synthetic_episodes,
                self._reward_shaper,
            )

        # Step 2: Populate replay buffer if we have raw episodes
        if episode_buffer is None:
            episode_buffer = EpisodeReplayBuffer()
            if episodes is not None:
                episode_buffer.add_batch(episodes)

        episode_count = len(episode_buffer)
        logger.info("Training with %d episodes in replay buffer", episode_count)

        if episode_count == 0:
            msg = "No episodes available for training"
            raise ValueError(msg)

        # Step 3: Initialize PPO components
        obs_dim = RoutingObservation.DIMS
        action_dim = NUM_ROUTING_ACTIONS
        ppo_config = self._config.ppo_config

        policy = PPOPolicy(
            obs_dim=obs_dim,
            action_dim=action_dim,
            config=ppo_config,
        )

        # The PPO trainer uses its own buffer format (transition-based)
        trainer_buffer = TrainerBuffer()

        # Convert episode buffer to trainer buffer format
        # For one-step routing episodes, next_obs = obs (terminal) and done = True
        batch = episode_buffer.sample_all()
        for i in range(batch.observations.shape[0]):
            obs_list = batch.observations[i].tolist()
            trainer_buffer.add(
                obs=obs_list,
                action=int(batch.actions[i].item()),
                reward=float(batch.rewards[i].item()),
                next_obs=obs_list,  # Terminal state = same obs
                done=True,  # One-step episodes are always terminal
            )

        trainer = PPOTrainer(
            policy=policy,
            buffer=trainer_buffer,
            config=ppo_config,
        )

        # Step 4: Training loop
        logger.info(
            "Starting PPO training: %d updates, batch_size=%d",
            self._config.num_updates,
            ppo_config.batch_size,
        )

        for update_idx in range(self._config.num_updates):
            metrics = trainer.update()
            self._metrics_history.append(metrics)

            if (update_idx + 1) % self._config.log_interval == 0:
                logger.info(
                    "Update %d/%d: policy_loss=%.4f value_loss=%.4f entropy=%.4f",
                    update_idx + 1,
                    self._config.num_updates,
                    metrics.policy_loss,
                    metrics.value_loss,
                    metrics.entropy,
                )

        # Step 5: Save checkpoint
        checkpoint_dir = Path(self._config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / self._config.checkpoint_name

        save_checkpoint(policy, checkpoint_path)

        elapsed = time.monotonic() - start_time
        logger.info(
            "Training complete: %d updates in %.1fs, checkpoint saved to %s",
            self._config.num_updates,
            elapsed,
            checkpoint_path,
        )

        # Step 6: Verify non-uniform action preferences
        self._verify_policy_quality(policy)

        return checkpoint_path

    def _verify_policy_quality(self, policy: PPOPolicy) -> None:
        """Verify the trained policy shows non-uniform action preferences.

        Generates a set of representative observations and checks that
        the policy does not assign uniform probability to all actions.
        """
        policy.eval()

        # Generate representative observations
        test_obs: list[list[float]] = []
        for task_type in _TASK_TYPES[:4]:  # Sample 4 task types
            onehot = [1.0 if t == task_type else 0.0 for t in _TASK_TYPES]
            # Use default health/success values
            health = [0.3, 0.05, 0.0, 0.1] * _NUM_ENDPOINTS
            success_rates = [0.85] * _NUM_ENDPOINTS
            obs = onehot + [0.5] + health + success_rates + [0.0, 1.0]
            test_obs.append(obs)

        with torch.no_grad():
            obs_tensor = torch.tensor(test_obs, dtype=torch.float32)
            probs = policy.get_action_probs(obs_tensor)

        # Check that at least one observation has non-uniform preferences
        uniform_threshold = 0.01  # Max deviation from uniform to still count as uniform
        uniform_prob = 1.0 / NUM_ROUTING_ACTIONS
        has_non_uniform = False

        for i in range(probs.shape[0]):
            max_dev = (probs[i] - uniform_prob).abs().max().item()
            if max_dev > uniform_threshold:
                has_non_uniform = True
                break

        if has_non_uniform:
            logger.info("Policy quality check PASSED: non-uniform action preferences")
        else:
            logger.warning(
                "Policy quality check WARNING: action preferences appear uniform. "
                "Policy may need more training updates or diverse episodes."
            )
