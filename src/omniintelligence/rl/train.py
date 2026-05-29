# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI entry point for offline RL training.

Usage::

    uv run python -m omniintelligence.rl.train --surface routing --updates 500
    uv run python -m omniintelligence.rl.train --all --episodes 350
    uv run python -m omniintelligence.rl.train --all --schedule

Tickets: OMN-5565, OMN-5576
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.manifest import (
    SURFACE_MATURITY,
    MaturityClass,
    TrainingManifest,
)
from omniintelligence.rl.pipelines.pipeline_pipeline import (
    PipelineTrainingPipeline,
    PipelineTrainingPipelineConfig,
)
from omniintelligence.rl.pipelines.routing_pipeline import (
    RoutingTrainingPipeline,
    RoutingTrainingPipelineConfig,
)
from omniintelligence.rl.pipelines.team_pipeline import (
    TeamTrainingPipeline,
    TeamTrainingPipelineConfig,
)
from omniintelligence.rl.rewards import RewardConfig

logger = logging.getLogger(__name__)

_ALL_SURFACES: list[str] = ["routing", "pipeline", "team"]


def _train_surface(
    surface: str,
    *,
    updates: int,
    episodes: int,
    checkpoint_dir: str,
    batch_size: int,
    lr: float,
    log_interval: int,
    manifest: TrainingManifest,
    min_episodes: int,
    schedule: bool,
) -> bool:
    """Train a single surface. Returns True if training ran, False if skipped."""
    if episodes < min_episodes:
        logger.info(
            "Skipping %s: episodes=%d < min_episodes=%d",
            surface,
            episodes,
            min_episodes,
        )
        return False

    if schedule:
        entry = manifest.get_entry(surface)
        if entry is not None and entry.episode_count >= episodes:
            logger.info(
                "Skipping %s: schedule mode, no new data (manifest=%d, current=%d)",
                surface,
                entry.episode_count,
                episodes,
            )
            return False

    ppo_config = PPOConfig(lr=lr, batch_size=batch_size)

    if surface == "routing":
        routing_config = RoutingTrainingPipelineConfig(
            num_updates=updates,
            checkpoint_dir=checkpoint_dir,
            ppo_config=ppo_config,
            reward_config=RewardConfig(),
            synthetic_episodes=episodes,
            log_interval=log_interval,
        )
        checkpoint_path = RoutingTrainingPipeline(config=routing_config).run()

    elif surface == "pipeline":
        pipeline_config = PipelineTrainingPipelineConfig(
            num_updates=updates,
            checkpoint_dir=checkpoint_dir,
            ppo_config=ppo_config,
            reward_config=RewardConfig(),
            synthetic_episodes=episodes,
            log_interval=log_interval,
        )
        checkpoint_path = PipelineTrainingPipeline(config=pipeline_config).run()

    elif surface == "team":
        team_config = TeamTrainingPipelineConfig(
            num_updates=updates,
            checkpoint_dir=checkpoint_dir,
            ppo_config=ppo_config,
            reward_config=RewardConfig(),
            synthetic_episodes=episodes,
            log_interval=log_interval,
        )
        checkpoint_path = TeamTrainingPipeline(config=team_config).run()

    else:
        logger.error("Unknown surface: %s", surface)
        return False

    manifest.record_training(surface, episodes, checkpoint_path)

    maturity = SURFACE_MATURITY.get(surface, MaturityClass.exploratory)
    print(f"  {surface} [{maturity.value}]: checkpoint saved to {checkpoint_path}")

    if maturity == MaturityClass.exploratory:
        print(
            f"  WARNING: {surface} is exploratory — "
            "successful training does not imply policy validity or deployment readiness"
        )

    return True


def main(argv: list[str] | None = None) -> int:
    """Run the offline RL training pipeline.

    Returns:
        0 if at least one surface trained successfully.
        1 if training failed.
        2 if all surfaces were skipped (min-episodes or schedule gate).
    """
    parser = argparse.ArgumentParser(
        description="Offline RL training for ONEX routing policy",
        prog="omniintelligence.rl.train",
    )
    surface_group = parser.add_mutually_exclusive_group()
    surface_group.add_argument(
        "--surface",
        type=str,
        choices=_ALL_SURFACES,
        help="Decision surface to train (routing, pipeline, or team)",
    )
    surface_group.add_argument(
        "--all",
        action="store_true",
        help="Train all surfaces (routing, pipeline, team)",
    )
    parser.add_argument(
        "--updates",
        type=int,
        default=500,
        help="Number of PPO update iterations (default: 500)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=350,
        help="Number of synthetic episodes if no DB source (default: 350)",
    )
    parser.add_argument(
        "--min-episodes",
        type=int,
        default=0,
        dest="min_episodes",
        help="Minimum episode count required to train a surface (default: 0)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default="checkpoints",
        help="Directory for model checkpoints (default: checkpoints)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Mini-batch size for PPO updates (default: 64)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=3e-4,
        help="Learning rate (default: 3e-4)",
    )
    parser.add_argument(
        "--log-interval",
        type=int,
        default=50,
        help="Log metrics every N updates (default: 50)",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="training_manifest.yaml",
        help="Path to training manifest YAML (default: training_manifest.yaml)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Skip surfaces where manifest episode count >= current episodes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args(argv)

    if not args.all and args.surface is None:
        args.surface = "routing"

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    manifest = TrainingManifest.load(Path(args.manifest))
    surfaces_to_train = _ALL_SURFACES if args.all else [args.surface]

    trained_count = 0
    skipped_count = 0

    for surface in surfaces_to_train:
        logger.info(
            "Starting %s training: %d updates, %d episodes",
            surface,
            args.updates,
            args.episodes,
        )
        try:
            trained = _train_surface(
                surface,
                updates=args.updates,
                episodes=args.episodes,
                checkpoint_dir=args.checkpoint_dir,
                batch_size=args.batch_size,
                lr=args.lr,
                log_interval=args.log_interval,
                manifest=manifest,
                min_episodes=args.min_episodes,
                schedule=args.schedule,
            )
            if trained:
                trained_count += 1
            else:
                skipped_count += 1
        except Exception:
            logger.exception("Training failed for surface: %s", surface)
            return 1

    manifest.save(Path(args.manifest))

    if args.all or len(surfaces_to_train) > 1:
        print(f"\nTraining complete: {trained_count} trained, {skipped_count} skipped")
        for name, entry in manifest.surfaces.items():
            print(f"  {name} [{entry.maturity_class.value}]: v{entry.policy_version}")

    if trained_count == 0:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
