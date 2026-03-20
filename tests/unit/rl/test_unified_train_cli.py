# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the unified training CLI and manifest.

Covers:
    1. --all trains routing (has data), skips pipeline/team (no data via --min-episodes)
    2. --min-episodes correctly skips below threshold
    3. Manifest is updated after training
    4. Schedule mode is idempotent
    5. Exit codes: 0 (success), 1 (error), 2 (skipped)
    6. Maturity class displayed in output
    7. Exploratory disclaimer emitted

Ticket: OMN-5576
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.rl.manifest import (
    MaturityClass,
    TrainingManifest,
)
from omniintelligence.rl.train import main

# ---------------------------------------------------------------------------
# Manifest model tests
# ---------------------------------------------------------------------------


class TestTrainingManifest:
    """Test TrainingManifest load/save/update."""

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        """Loading from a nonexistent path returns an empty manifest."""
        manifest = TrainingManifest.load(tmp_path / "does_not_exist.yaml")
        assert manifest.surfaces == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Manifest survives a save/load roundtrip."""
        path = tmp_path / "manifest.yaml"
        manifest = TrainingManifest()
        manifest.record_training(
            "routing", episode_count=350, checkpoint_path="/tmp/cp.pt"
        )
        manifest.save(path)

        loaded = TrainingManifest.load(path)
        assert "routing" in loaded.surfaces
        entry = loaded.surfaces["routing"]
        assert entry.episode_count == 350
        assert entry.policy_version == 1
        assert entry.maturity_class == MaturityClass.production_candidate
        assert entry.last_trained_at is not None
        assert entry.checkpoint_path == "/tmp/cp.pt"

    def test_record_training_increments_version(self, tmp_path: Path) -> None:
        """Each record_training call increments the policy version."""
        manifest = TrainingManifest()
        manifest.record_training("routing", 100, "/v1.pt")
        assert manifest.surfaces["routing"].policy_version == 1

        manifest.record_training("routing", 200, "/v2.pt")
        assert manifest.surfaces["routing"].policy_version == 2

    def test_maturity_classes_assigned_correctly(self) -> None:
        """Maturity classes match the spec for each surface."""
        manifest = TrainingManifest()
        manifest.record_training("routing", 100, "/r.pt")
        manifest.record_training("pipeline", 100, "/p.pt")
        manifest.record_training("team", 100, "/t.pt")

        assert (
            manifest.surfaces["routing"].maturity_class
            == MaturityClass.production_candidate
        )
        assert (
            manifest.surfaces["pipeline"].maturity_class == MaturityClass.experimental
        )
        assert manifest.surfaces["team"].maturity_class == MaturityClass.exploratory

    def test_get_entry_returns_none_for_unknown(self) -> None:
        """get_entry returns None for unknown surfaces."""
        manifest = TrainingManifest()
        assert manifest.get_entry("nonexistent") is None

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        """Loading an empty YAML file returns an empty manifest."""
        path = tmp_path / "empty.yaml"
        path.write_text("")
        manifest = TrainingManifest.load(path)
        assert manifest.surfaces == {}


# ---------------------------------------------------------------------------
# CLI: --all flag
# ---------------------------------------------------------------------------


class TestAllFlag:
    """Test --all flag trains surfaces with sufficient data."""

    def test_all_trains_routing_with_synthetic(self, tmp_path: Path) -> None:
        """--all with default episodes trains routing successfully."""
        manifest_path = tmp_path / "manifest.yaml"
        exit_code = main(
            [
                "--all",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )
        assert exit_code == 0

        # Manifest should have entries for all three surfaces
        manifest = TrainingManifest.load(manifest_path)
        assert "routing" in manifest.surfaces
        assert manifest.surfaces["routing"].policy_version >= 1

    def test_all_with_high_min_episodes_skips_all(self, tmp_path: Path) -> None:
        """--all with --min-episodes higher than available skips all surfaces."""
        manifest_path = tmp_path / "manifest.yaml"
        exit_code = main(
            [
                "--all",
                "--updates",
                "3",
                "--episodes",
                "10",
                "--min-episodes",
                "9999",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )
        # All skipped -> exit code 2
        assert exit_code == 2


# ---------------------------------------------------------------------------
# CLI: --min-episodes
# ---------------------------------------------------------------------------


class TestMinEpisodes:
    """Test --min-episodes correctly skips below threshold."""

    def test_min_episodes_skips_routing(self, tmp_path: Path) -> None:
        """--min-episodes above episode count skips routing."""
        manifest_path = tmp_path / "manifest.yaml"
        exit_code = main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--min-episodes",
                "100",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )
        assert exit_code == 2  # skipped

    def test_min_episodes_allows_training(self, tmp_path: Path) -> None:
        """--min-episodes below episode count allows training."""
        manifest_path = tmp_path / "manifest.yaml"
        exit_code = main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--min-episodes",
                "10",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )
        assert exit_code == 0


# ---------------------------------------------------------------------------
# CLI: manifest update
# ---------------------------------------------------------------------------


class TestManifestUpdate:
    """Test that manifest is updated after training."""

    def test_manifest_updated_after_training(self, tmp_path: Path) -> None:
        """Manifest contains updated entry after successful training."""
        manifest_path = tmp_path / "manifest.yaml"
        main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )

        manifest = TrainingManifest.load(manifest_path)
        entry = manifest.get_entry("routing")
        assert entry is not None
        assert entry.episode_count == 50
        assert entry.policy_version == 1
        assert entry.maturity_class == MaturityClass.production_candidate
        assert entry.last_trained_at is not None
        assert entry.checkpoint_path is not None

    def test_manifest_version_increments_on_retrain(self, tmp_path: Path) -> None:
        """Policy version increments on second training run."""
        manifest_path = tmp_path / "manifest.yaml"
        common_args = [
            "--surface",
            "routing",
            "--updates",
            "3",
            "--episodes",
            "50",
            "--checkpoint-dir",
            str(tmp_path / "ckpt"),
            "--batch-size",
            "32",
            "--manifest",
            str(manifest_path),
        ]

        main(common_args)
        main(common_args)

        manifest = TrainingManifest.load(manifest_path)
        entry = manifest.get_entry("routing")
        assert entry is not None
        assert entry.policy_version == 2


# ---------------------------------------------------------------------------
# CLI: schedule mode
# ---------------------------------------------------------------------------


class TestScheduleMode:
    """Test schedule mode idempotency."""

    def test_schedule_skips_when_no_new_data(self, tmp_path: Path) -> None:
        """Schedule mode skips if manifest already has same episode count."""
        manifest_path = tmp_path / "manifest.yaml"
        common_args = [
            "--surface",
            "routing",
            "--updates",
            "3",
            "--episodes",
            "50",
            "--checkpoint-dir",
            str(tmp_path / "ckpt"),
            "--batch-size",
            "32",
            "--manifest",
            str(manifest_path),
        ]

        # First run: trains
        exit_code = main(common_args)
        assert exit_code == 0

        manifest = TrainingManifest.load(manifest_path)
        assert manifest.get_entry("routing") is not None
        assert manifest.get_entry("routing").policy_version == 1  # type: ignore[union-attr]

        # Second run with --schedule: should skip (no new data)
        exit_code = main([*common_args, "--schedule"])
        assert exit_code == 2  # all skipped

        # Version should not have changed
        manifest = TrainingManifest.load(manifest_path)
        assert manifest.get_entry("routing").policy_version == 1  # type: ignore[union-attr]

    def test_schedule_trains_when_more_episodes(self, tmp_path: Path) -> None:
        """Schedule mode trains if episode count has increased."""
        manifest_path = tmp_path / "manifest.yaml"

        # First run with 50 episodes
        main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )

        # Second run with 100 episodes + --schedule: should train
        exit_code = main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "100",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
                "--schedule",
            ]
        )
        assert exit_code == 0

        manifest = TrainingManifest.load(manifest_path)
        assert manifest.get_entry("routing").policy_version == 2  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# CLI: exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    """Test CLI exit codes."""

    def test_exit_0_on_success(self, tmp_path: Path) -> None:
        """Exit code 0 when at least one surface trains."""
        exit_code = main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(tmp_path / "manifest.yaml"),
            ]
        )
        assert exit_code == 0

    def test_exit_2_when_all_skipped(self, tmp_path: Path) -> None:
        """Exit code 2 when all surfaces are skipped."""
        exit_code = main(
            [
                "--surface",
                "routing",
                "--updates",
                "3",
                "--episodes",
                "10",
                "--min-episodes",
                "9999",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(tmp_path / "manifest.yaml"),
            ]
        )
        assert exit_code == 2


# ---------------------------------------------------------------------------
# CLI: surface-specific training
# ---------------------------------------------------------------------------


class TestSurfaceSpecific:
    """Test training specific surfaces."""

    def test_train_pipeline_surface(self, tmp_path: Path) -> None:
        """--surface pipeline trains the pipeline surface."""
        manifest_path = tmp_path / "manifest.yaml"
        exit_code = main(
            [
                "--surface",
                "pipeline",
                "--updates",
                "3",
                "--episodes",
                "100",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )
        assert exit_code == 0

        manifest = TrainingManifest.load(manifest_path)
        entry = manifest.get_entry("pipeline")
        assert entry is not None
        assert entry.maturity_class == MaturityClass.experimental

    def test_train_team_surface(self, tmp_path: Path) -> None:
        """--surface team trains the team surface."""
        manifest_path = tmp_path / "manifest.yaml"
        exit_code = main(
            [
                "--surface",
                "team",
                "--updates",
                "3",
                "--episodes",
                "100",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(manifest_path),
            ]
        )
        assert exit_code == 0

        manifest = TrainingManifest.load(manifest_path)
        entry = manifest.get_entry("team")
        assert entry is not None
        assert entry.maturity_class == MaturityClass.exploratory


# ---------------------------------------------------------------------------
# CLI: output format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Test CLI output includes maturity class and disclaimers."""

    def test_output_shows_maturity_class(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """CLI output shows maturity class next to each surface."""
        main(
            [
                "--all",
                "--updates",
                "3",
                "--episodes",
                "50",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(tmp_path / "manifest.yaml"),
            ]
        )
        captured = capsys.readouterr()
        assert "production_candidate" in captured.out
        assert "experimental" in captured.out
        assert "exploratory" in captured.out

    def test_exploratory_disclaimer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Exploratory surfaces emit a visible disclaimer on success."""
        main(
            [
                "--surface",
                "team",
                "--updates",
                "3",
                "--episodes",
                "100",
                "--checkpoint-dir",
                str(tmp_path / "ckpt"),
                "--batch-size",
                "32",
                "--manifest",
                str(tmp_path / "manifest.yaml"),
            ]
        )
        captured = capsys.readouterr()
        assert "does not imply policy validity or deployment readiness" in captured.out
