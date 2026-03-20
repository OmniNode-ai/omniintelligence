# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Training manifest for tracking per-surface training state.

The manifest records the last successful training run for each decision
surface, including episode count, policy version, maturity class,
timestamp, and checkpoint path. It is persisted as YAML and updated
after each successful training.

Ticket: OMN-5576
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class MaturityClass(str, enum.Enum):
    """Maturity classification for a decision surface.

    Determines how much trust to place in trained policies.

    Values:
        production_candidate: Sufficient validated data; policy may be
            deployed behind a canary/shadow gate.
        experimental: Some validated data; policy useful for offline
            evaluation but not deployment.
        exploratory: Minimal or no validated data; successful training
            does NOT imply policy validity or deployment readiness.
    """

    production_candidate = "production_candidate"
    experimental = "experimental"
    exploratory = "exploratory"


# Default maturity classes per surface, as specified in the ticket.
SURFACE_MATURITY: dict[str, MaturityClass] = {
    "routing": MaturityClass.production_candidate,
    "pipeline": MaturityClass.experimental,
    "team": MaturityClass.exploratory,
}


class SurfaceEntry(BaseModel):
    """Per-surface training state in the manifest."""

    surface: str = Field(description="Decision surface name")
    episode_count: int = Field(default=0, description="Episodes used in last training")
    policy_version: int = Field(
        default=0, description="Monotonically increasing version"
    )
    maturity_class: MaturityClass = Field(
        default=MaturityClass.exploratory,
        description="Maturity classification",
    )
    last_trained_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of last successful training",
    )
    checkpoint_path: str | None = Field(
        default=None,
        description="Path to the latest checkpoint file",
    )


class TrainingManifest(BaseModel):
    """Root manifest tracking all decision surfaces.

    Load from and save to YAML for human-readable persistence.
    """

    surfaces: dict[str, SurfaceEntry] = Field(
        default_factory=dict,
        description="Per-surface training entries keyed by surface name",
    )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> TrainingManifest:
        """Load manifest from a YAML file.

        If the file does not exist, returns an empty manifest.

        Args:
            path: Path to the YAML file.

        Returns:
            Loaded (or empty) TrainingManifest.
        """
        p = Path(path)
        if not p.exists():
            return cls()

        with p.open("r") as fh:
            raw = yaml.safe_load(fh)

        if raw is None:
            return cls()

        surfaces: dict[str, SurfaceEntry] = {}
        for name, data in (raw.get("surfaces") or {}).items():
            surfaces[name] = SurfaceEntry(**data)
        return cls(surfaces=surfaces)

    def save(self, path: str | Path) -> None:
        """Save manifest to a YAML file.

        Creates parent directories if they do not exist.

        Args:
            path: Destination file path.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, object] = {
            "surfaces": {
                name: entry.model_dump(mode="json")
                for name, entry in self.surfaces.items()
            },
        }

        with p.open("w") as fh:
            yaml.safe_dump(payload, fh, default_flow_style=False, sort_keys=False)

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def record_training(
        self,
        surface: str,
        episode_count: int,
        checkpoint_path: str | Path,
    ) -> None:
        """Record a successful training run for a surface.

        Increments the policy version, updates episode count, timestamp,
        checkpoint path, and maturity class (from SURFACE_MATURITY).

        Args:
            surface: Decision surface name.
            episode_count: Number of episodes used.
            checkpoint_path: Path to the saved checkpoint.
        """
        existing = self.surfaces.get(surface)
        prev_version = existing.policy_version if existing else 0

        self.surfaces[surface] = SurfaceEntry(
            surface=surface,
            episode_count=episode_count,
            policy_version=prev_version + 1,
            maturity_class=SURFACE_MATURITY.get(surface, MaturityClass.exploratory),
            last_trained_at=datetime.now(tz=timezone.utc).isoformat(),
            checkpoint_path=str(checkpoint_path),
        )

    def get_entry(self, surface: str) -> SurfaceEntry | None:
        """Return the entry for a surface, or None if not present."""
        return self.surfaces.get(surface)
