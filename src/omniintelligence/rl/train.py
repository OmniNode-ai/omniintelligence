# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI entry point for offline RL training.

Usage::

    uv run python -m omniintelligence.rl.train --surface routing --updates 500

Ticket: OMN-5565
"""

from __future__ import annotations

import argparse
import logging
import sys

from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.pipelines.routing_pipeline import (
    RoutingTrainingPipeline,
    RoutingTrainingPipelineConfig,
)
from omniintelligence.rl.rewards import RewardConfig

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run the offline RL training pipeline.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(
        description="Offline RL training for ONEX routing policy",
        prog="omniintelligence.rl.train",
    )
    parser.add_argument(
        "--surface",
        type=str,
        default="routing",
        choices=["routing"],
        help="Decision surface to train (default: routing)",
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
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info(
        "Starting %s training: %d updates, %d episodes",
        args.surface,
        args.updates,
        args.episodes,
    )

    if args.surface == "routing":
        ppo_config = PPOConfig(
            lr=args.lr,
            batch_size=args.batch_size,
        )

        pipeline_config = RoutingTrainingPipelineConfig(
            num_updates=args.updates,
            checkpoint_dir=args.checkpoint_dir,
            ppo_config=ppo_config,
            reward_config=RewardConfig(),
            synthetic_episodes=args.episodes,
            log_interval=args.log_interval,
        )

        pipeline = RoutingTrainingPipeline(config=pipeline_config)

        try:
            checkpoint_path = pipeline.run()
            logger.info("Checkpoint saved: %s", checkpoint_path)
            return 0
        except Exception:
            logger.exception("Training failed")
            return 1
    else:
        logger.error("Unknown surface: %s", args.surface)
        return 1


if __name__ == "__main__":
    sys.exit(main())
