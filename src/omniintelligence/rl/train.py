# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unified CLI entry point for offline RL training across all decision surfaces.

Usage::

    # Train a specific surface
    uv run python -m omniintelligence.rl.train --surface routing --updates 500

    # Train all surfaces with sufficient data
    uv run python -m omniintelligence.rl.train --all

    # Skip surfaces with fewer than 100 episodes
    uv run python -m omniintelligence.rl.train --all --min-episodes 100

    # Idempotent scheduled mode (no new checkpoints without new data)
    uv run python -m omniintelligence.rl.train --all --schedule

Exit codes:
    0 - At least one surface trained successfully
    1 - Error during training
    2 - All surfaces skipped (insufficient data)

Tickets: OMN-5565, OMN-5576
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
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

ALL_SURFACES: list[str] = ["routing", "pipeline", "team"]

# Default manifest path (relative to cwd; overridable via --manifest)
_DEFAULT_MANIFEST_PATH = "configs/rl_training_manifest.yaml"


# ---------------------------------------------------------------------------
# Per-surface result tracking
# ---------------------------------------------------------------------------


@dataclass
class SurfaceResult:
    """Outcome of a single surface training attempt."""

    surface: str
    status: str  # "trained", "skipped", "failed"
    maturity_class: MaturityClass
    checkpoint_path: Path | None = None
    episode_count: int = 0
    reason: str = ""


# ---------------------------------------------------------------------------
# Surface training dispatch
# ---------------------------------------------------------------------------


def _train_routing(
    args: argparse.Namespace,
    ppo_config: PPOConfig,
) -> SurfaceResult:
    """Train the routing decision surface."""
    maturity = SURFACE_MATURITY["routing"]
    config = RoutingTrainingPipelineConfig(
        num_updates=args.updates,
        checkpoint_dir=args.checkpoint_dir,
        ppo_config=ppo_config,
        reward_config=RewardConfig(),
        synthetic_episodes=args.episodes,
        log_interval=args.log_interval,
    )

    pipeline = RoutingTrainingPipeline(config=config)
    episode_count = args.episodes  # synthetic fallback

    if args.min_episodes > 0 and episode_count < args.min_episodes:
        return SurfaceResult(
            surface="routing",
            status="skipped",
            maturity_class=maturity,
            episode_count=episode_count,
            reason=f"Insufficient data: {episode_count} episodes (minimum: {args.min_episodes})",
        )

    try:
        checkpoint_path = pipeline.run()
        return SurfaceResult(
            surface="routing",
            status="trained",
            maturity_class=maturity,
            checkpoint_path=checkpoint_path,
            episode_count=episode_count,
        )
    except Exception as exc:
        return SurfaceResult(
            surface="routing",
            status="failed",
            maturity_class=maturity,
            reason=str(exc),
        )


def _train_pipeline(
    args: argparse.Namespace,
    ppo_config: PPOConfig,
) -> SurfaceResult:
    """Train the pipeline decision surface (exploratory)."""
    maturity = SURFACE_MATURITY["pipeline"]
    config = PipelineTrainingPipelineConfig(
        num_updates=args.updates,
        checkpoint_dir=args.checkpoint_dir,
        ppo_config=ppo_config,
        reward_config=RewardConfig(),
        synthetic_episodes=args.episodes,
        log_interval=args.log_interval,
        min_episodes=args.min_episodes if args.min_episodes > 0 else 50,
    )

    pipeline = PipelineTrainingPipeline(config=config)

    try:
        result = pipeline.run()
        if result.skipped:
            return SurfaceResult(
                surface="pipeline",
                status="skipped",
                maturity_class=maturity,
                reason=result.skip_reason,
            )
        return SurfaceResult(
            surface="pipeline",
            status="trained",
            maturity_class=maturity,
            checkpoint_path=result.checkpoint_path,
            episode_count=config.synthetic_episodes,
        )
    except Exception as exc:
        return SurfaceResult(
            surface="pipeline",
            status="failed",
            maturity_class=maturity,
            reason=str(exc),
        )


def _train_team(
    args: argparse.Namespace,
    ppo_config: PPOConfig,
) -> SurfaceResult:
    """Train the team decision surface (exploratory)."""
    maturity = SURFACE_MATURITY["team"]
    config = TeamTrainingPipelineConfig(
        num_updates=args.updates,
        checkpoint_dir=args.checkpoint_dir,
        ppo_config=ppo_config,
        reward_config=RewardConfig(),
        synthetic_episodes=args.episodes,
        log_interval=args.log_interval,
        min_episodes=args.min_episodes if args.min_episodes > 0 else 50,
    )

    pipeline = TeamTrainingPipeline(config=config)

    try:
        result = pipeline.run()
        if result.skipped:
            return SurfaceResult(
                surface="team",
                status="skipped",
                maturity_class=maturity,
                reason=result.skip_reason,
            )
        return SurfaceResult(
            surface="team",
            status="trained",
            maturity_class=maturity,
            checkpoint_path=result.checkpoint_path,
            episode_count=config.synthetic_episodes,
        )
    except Exception as exc:
        return SurfaceResult(
            surface="team",
            status="failed",
            maturity_class=maturity,
            reason=str(exc),
        )


_SURFACE_TRAINERS: dict[
    str,
    type[object],
] = {
    "routing": type(None),  # placeholder; dispatch is via functions
    "pipeline": type(None),
    "team": type(None),
}


def _dispatch_surface(
    surface: str,
    args: argparse.Namespace,
    ppo_config: PPOConfig,
) -> SurfaceResult:
    """Dispatch training for a single surface."""
    if surface == "routing":
        return _train_routing(args, ppo_config)
    elif surface == "pipeline":
        return _train_pipeline(args, ppo_config)
    elif surface == "team":
        return _train_team(args, ppo_config)
    else:
        return SurfaceResult(
            surface=surface,
            status="failed",
            maturity_class=MaturityClass.exploratory,
            reason=f"Unknown surface: {surface}",
        )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_STATUS_ICONS: dict[str, str] = {
    "trained": "OK",
    "skipped": "SKIP",
    "failed": "FAIL",
}


def _print_result(result: SurfaceResult) -> None:
    """Print a single surface result line."""
    icon = _STATUS_ICONS.get(result.status, "??")
    line = f"  [{icon}] {result.surface} ({result.maturity_class.value})"

    if result.status == "trained" and result.checkpoint_path:
        line += f" -> {result.checkpoint_path}"
    elif result.status == "skipped":
        line += f" -- {result.reason}"
    elif result.status == "failed":
        line += f" -- ERROR: {result.reason}"

    print(line)  # noqa: T201

    # Exploratory disclaimer
    if (
        result.maturity_class == MaturityClass.exploratory
        and result.status == "trained"
    ):
        print(  # noqa: T201
            "        NOTE: Successful execution does not imply "
            "policy validity or deployment readiness"
        )


# ---------------------------------------------------------------------------
# Schedule mode: idempotent check
# ---------------------------------------------------------------------------


def _should_skip_schedule(
    surface: str,
    manifest: TrainingManifest,
    episode_count: int,
) -> bool:
    """Check whether schedule mode should skip this surface.

    Returns True if the manifest already has a training record for this
    surface with the same or higher episode count (no new data).
    """
    entry = manifest.get_entry(surface)
    if entry is None:
        return False
    if entry.last_trained_at is None:
        return False
    # Skip if episode count has not increased since last training
    return entry.episode_count >= episode_count


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run the unified offline RL training CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 (success), 1 (error), 2 (all skipped).
    """
    parser = argparse.ArgumentParser(
        description="Unified offline RL training for ONEX decision surfaces",
        prog="omniintelligence.rl.train",
    )

    # Surface selection (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Train all surfaces with sufficient data",
    )
    group.add_argument(
        "--surface",
        type=str,
        choices=ALL_SURFACES,
        help="Train a specific surface (routing, pipeline, team)",
    )

    # Training parameters
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
        help="Skip surfaces with fewer episodes than this threshold (default: 0 = no skip)",
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

    # Schedule mode
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Idempotent mode: skip surfaces with no new data since last training",
    )

    # Manifest
    parser.add_argument(
        "--manifest",
        type=str,
        default=_DEFAULT_MANIFEST_PATH,
        help=f"Path to training manifest YAML (default: {_DEFAULT_MANIFEST_PATH})",
    )

    # Logging
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

    # Determine surfaces to train
    surfaces = ALL_SURFACES if args.all else [args.surface]

    # Load manifest
    manifest = TrainingManifest.load(args.manifest)

    # Build shared PPO config
    ppo_config = PPOConfig(
        lr=args.lr,
        batch_size=args.batch_size,
    )

    # Train each surface
    results: list[SurfaceResult] = []

    for surface in surfaces:
        # Schedule mode: check idempotency
        if args.schedule and _should_skip_schedule(surface, manifest, args.episodes):
            maturity = SURFACE_MATURITY.get(surface, MaturityClass.exploratory)
            results.append(
                SurfaceResult(
                    surface=surface,
                    status="skipped",
                    maturity_class=maturity,
                    reason="Schedule mode: no new data since last training",
                )
            )
            continue

        logger.info("Training surface: %s", surface)
        result = _dispatch_surface(surface, args, ppo_config)
        results.append(result)

        # Update manifest on success
        if result.status == "trained" and result.checkpoint_path is not None:
            manifest.record_training(
                surface=surface,
                episode_count=result.episode_count,
                checkpoint_path=result.checkpoint_path,
            )

    # Save manifest
    manifest.save(args.manifest)

    # Print summary
    print("\n--- Training Summary ---")  # noqa: T201
    trained = 0
    skipped = 0
    failed = 0
    for r in results:
        _print_result(r)
        if r.status == "trained":
            trained += 1
        elif r.status == "skipped":
            skipped += 1
        else:
            failed += 1

    print(  # noqa: T201
        f"\nTotal: {trained} trained, {skipped} skipped, {failed} failed"
    )

    # Exit codes
    if failed > 0:
        return 1
    if trained == 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
