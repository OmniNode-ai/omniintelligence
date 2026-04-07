# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for omniintelligence.review_pairing.models.

Covers:
- Model instantiation with valid data
- Field validation (required fields, constraints)
- Serialization (model_dump / model_dump_json round-trip)
- Immutability (frozen=True)
- UTC datetime enforcement
- Enum validation for severity and pairing_type

Reference: OMN-2535
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.review_pairing.models import (
    ModelFindingFixPair,
    EnumFindingSeverity,
    EnumPairingType,
    ModelReviewFindingObserved,
    ModelReviewFindingResolved,
    ModelReviewFixApplied,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(tz=UTC)


def _finding_observed_kwargs() -> dict:
    """Minimal valid kwargs for ModelReviewFindingObserved."""
    return {
        "finding_id": uuid4(),
        "repo": "OmniNode-ai/omniintelligence",
        "pr_id": 42,
        "rule_id": "ruff:E501",
        "severity": EnumFindingSeverity.ERROR,
        "file_path": "src/foo/bar.py",
        "line_start": 10,
        "tool_name": "ruff",
        "tool_version": "0.12.5",
        "normalized_message": "Line too long",
        "raw_message": "E501 line too long (95 > 88 characters)",
        "commit_sha_observed": "abc1234",
        "observed_at": _utcnow(),
    }


def _fix_applied_kwargs(finding_id: UUID | None = None) -> dict:
    """Minimal valid kwargs for ModelReviewFixApplied."""
    return {
        "fix_id": uuid4(),
        "finding_id": finding_id or uuid4(),
        "fix_commit_sha": "def5678",
        "file_path": "src/foo/bar.py",
        "diff_hunks": ["@@ -10,1 +10,1 @@ -old line\n+new line"],
        "touched_line_range": (10, 10),
        "tool_autofix": True,
        "applied_at": _utcnow(),
    }


def _finding_resolved_kwargs(finding_id: UUID | None = None) -> dict:
    """Minimal valid kwargs for ModelReviewFindingResolved."""
    return {
        "resolution_id": uuid4(),
        "finding_id": finding_id or uuid4(),
        "fix_commit_sha": "def5678",
        "verified_at_commit_sha": "ghi9012",
        "ci_run_id": "12345678",
        "resolved_at": _utcnow(),
    }


def _finding_fix_pair_kwargs(finding_id: UUID | None = None) -> dict:
    """Minimal valid kwargs for ModelFindingFixPair."""
    return {
        "pair_id": uuid4(),
        "finding_id": finding_id or uuid4(),
        "fix_commit_sha": "def5678",
        "diff_hunks": ["@@ -10,1 +10,1 @@ -old line\n+new line"],
        "confidence_score": 0.85,
        "disappearance_confirmed": True,
        "pairing_type": EnumPairingType.AUTOFIX,
        "created_at": _utcnow(),
    }


# ---------------------------------------------------------------------------
# ModelReviewFindingObserved tests
# ---------------------------------------------------------------------------


class TestReviewFindingObserved:
    """Tests for ModelReviewFindingObserved model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ModelReviewFindingObserved(**_finding_observed_kwargs())
        assert isinstance(model.finding_id, UUID)
        assert model.repo == "OmniNode-ai/omniintelligence"
        assert model.pr_id == 42
        assert model.severity == EnumFindingSeverity.ERROR

    @pytest.mark.unit
    def test_line_end_optional(self) -> None:
        """line_end should be None by default (single-line finding)."""
        model = ModelReviewFindingObserved(**_finding_observed_kwargs())
        assert model.line_end is None

    @pytest.mark.unit
    def test_line_end_set(self) -> None:
        """line_end should accept valid values >= line_start."""
        kwargs = _finding_observed_kwargs()
        kwargs["line_start"] = 10
        kwargs["line_end"] = 15
        model = ModelReviewFindingObserved(**kwargs)
        assert model.line_end == 15

    @pytest.mark.unit
    def test_pr_id_must_be_positive(self) -> None:
        """pr_id <= 0 should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["pr_id"] = 0
        with pytest.raises(ValidationError):
            ModelReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_line_start_must_be_positive(self) -> None:
        """line_start <= 0 should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["line_start"] = 0
        with pytest.raises(ValidationError):
            ModelReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_invalid_severity_raises(self) -> None:
        """Invalid severity string should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["severity"] = "nonexistent_severity"
        with pytest.raises(ValidationError):
            ModelReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_commit_sha_min_length(self) -> None:
        """commit_sha_observed shorter than 7 chars should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["commit_sha_observed"] = "abc"
        with pytest.raises(ValidationError):
            ModelReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_commit_sha_max_length(self) -> None:
        """commit_sha_observed longer than 40 chars should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["commit_sha_observed"] = "a" * 41
        with pytest.raises(ValidationError):
            ModelReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ModelReviewFindingObserved(**_finding_observed_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.pr_id = 99  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ModelReviewFindingObserved(**_finding_observed_kwargs())
        dumped = original.model_dump()
        reconstructed = ModelReviewFindingObserved(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_model_dump_json(self) -> None:
        """model_dump_json() should produce valid JSON."""
        model = ModelReviewFindingObserved(**_finding_observed_kwargs())
        json_str = model.model_dump_json()
        data = json.loads(json_str)
        assert data["repo"] == "OmniNode-ai/omniintelligence"
        assert data["pr_id"] == 42

    @pytest.mark.unit
    def test_all_severity_values_valid(self) -> None:
        """All EnumFindingSeverity enum values should be accepted."""
        for severity in EnumFindingSeverity:
            kwargs = _finding_observed_kwargs()
            kwargs["severity"] = severity
            model = ModelReviewFindingObserved(**kwargs)
            assert model.severity == severity


# ---------------------------------------------------------------------------
# ModelReviewFixApplied tests
# ---------------------------------------------------------------------------


class TestReviewFixApplied:
    """Tests for ModelReviewFixApplied model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ModelReviewFixApplied(**_fix_applied_kwargs())
        assert isinstance(model.fix_id, UUID)
        assert model.tool_autofix is True

    @pytest.mark.unit
    def test_diff_hunks_default_empty(self) -> None:
        """diff_hunks should default to empty list."""
        kwargs = _fix_applied_kwargs()
        del kwargs["diff_hunks"]
        model = ModelReviewFixApplied(**kwargs)
        assert model.diff_hunks == []

    @pytest.mark.unit
    def test_touched_line_range_tuple(self) -> None:
        """touched_line_range should be a tuple of two ints."""
        model = ModelReviewFixApplied(**_fix_applied_kwargs())
        assert isinstance(model.touched_line_range, tuple)
        assert len(model.touched_line_range) == 2

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ModelReviewFixApplied(**_fix_applied_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.tool_autofix = False  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ModelReviewFixApplied(**_fix_applied_kwargs())
        dumped = original.model_dump()
        reconstructed = ModelReviewFixApplied(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_fix_commit_sha_min_length(self) -> None:
        """fix_commit_sha shorter than 7 chars should fail validation."""
        kwargs = _fix_applied_kwargs()
        kwargs["fix_commit_sha"] = "abc"
        with pytest.raises(ValidationError):
            ModelReviewFixApplied(**kwargs)


# ---------------------------------------------------------------------------
# ModelReviewFindingResolved tests
# ---------------------------------------------------------------------------


class TestReviewFindingResolved:
    """Tests for ModelReviewFindingResolved model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ModelReviewFindingResolved(**_finding_resolved_kwargs())
        assert isinstance(model.resolution_id, UUID)
        assert model.ci_run_id == "12345678"

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ModelReviewFindingResolved(**_finding_resolved_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.ci_run_id = "other"  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ModelReviewFindingResolved(**_finding_resolved_kwargs())
        dumped = original.model_dump()
        reconstructed = ModelReviewFindingResolved(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_verified_at_commit_sha_min_length(self) -> None:
        """verified_at_commit_sha shorter than 7 chars should fail validation."""
        kwargs = _finding_resolved_kwargs()
        kwargs["verified_at_commit_sha"] = "ab"
        with pytest.raises(ValidationError):
            ModelReviewFindingResolved(**kwargs)


# ---------------------------------------------------------------------------
# ModelFindingFixPair tests
# ---------------------------------------------------------------------------


class TestFindingFixPair:
    """Tests for ModelFindingFixPair model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ModelFindingFixPair(**_finding_fix_pair_kwargs())
        assert isinstance(model.pair_id, UUID)
        assert model.confidence_score == 0.85
        assert model.disappearance_confirmed is True

    @pytest.mark.unit
    def test_confidence_score_lower_bound(self) -> None:
        """confidence_score < 0.0 should fail validation."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = -0.1
        with pytest.raises(ValidationError):
            ModelFindingFixPair(**kwargs)

    @pytest.mark.unit
    def test_confidence_score_upper_bound(self) -> None:
        """confidence_score > 1.0 should fail validation."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = 1.1
        with pytest.raises(ValidationError):
            ModelFindingFixPair(**kwargs)

    @pytest.mark.unit
    def test_confidence_score_boundary_zero(self) -> None:
        """confidence_score = 0.0 should be valid."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = 0.0
        model = ModelFindingFixPair(**kwargs)
        assert model.confidence_score == 0.0

    @pytest.mark.unit
    def test_confidence_score_boundary_one(self) -> None:
        """confidence_score = 1.0 should be valid."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = 1.0
        model = ModelFindingFixPair(**kwargs)
        assert model.confidence_score == 1.0

    @pytest.mark.unit
    def test_all_pairing_types_valid(self) -> None:
        """All EnumPairingType enum values should be accepted."""
        for pt in EnumPairingType:
            kwargs = _finding_fix_pair_kwargs()
            kwargs["pairing_type"] = pt
            model = ModelFindingFixPair(**kwargs)
            assert model.pairing_type == pt

    @pytest.mark.unit
    def test_invalid_pairing_type_raises(self) -> None:
        """Invalid pairing_type string should fail validation."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["pairing_type"] = "unknown"
        with pytest.raises(ValidationError):
            ModelFindingFixPair(**kwargs)

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ModelFindingFixPair(**_finding_fix_pair_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.confidence_score = 0.5  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ModelFindingFixPair(**_finding_fix_pair_kwargs())
        dumped = original.model_dump()
        reconstructed = ModelFindingFixPair(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_model_dump_json(self) -> None:
        """model_dump_json() should produce valid JSON."""
        model = ModelFindingFixPair(**_finding_fix_pair_kwargs())
        json_str = model.model_dump_json()
        data = json.loads(json_str)
        assert data["confidence_score"] == 0.85
        assert data["disappearance_confirmed"] is True

    @pytest.mark.unit
    def test_diff_hunks_default_empty(self) -> None:
        """diff_hunks should default to empty list."""
        kwargs = _finding_fix_pair_kwargs()
        del kwargs["diff_hunks"]
        model = ModelFindingFixPair(**kwargs)
        assert model.diff_hunks == []


# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestPackageImport:
    """Tests that models are importable from the canonical module path."""

    @pytest.mark.unit
    def test_import_from_models_module(self) -> None:
        """All four models should be importable from review_pairing.models."""
        import omniintelligence.review_pairing.models as _m

        assert hasattr(_m, "ModelReviewFindingObserved")
        assert hasattr(_m, "ModelReviewFixApplied")
        assert hasattr(_m, "ModelReviewFindingResolved")
        assert hasattr(_m, "ModelFindingFixPair")
        assert _m.ModelReviewFindingObserved is ModelReviewFindingObserved
        assert _m.ModelReviewFixApplied is ModelReviewFixApplied
        assert _m.ModelReviewFindingResolved is ModelReviewFindingResolved
        assert _m.ModelFindingFixPair is ModelFindingFixPair

    @pytest.mark.unit
    def test_import_from_package_init(self) -> None:
        """All four models should be importable from review_pairing package."""
        import omniintelligence.review_pairing as _pkg

        assert hasattr(_pkg, "ModelReviewFindingObserved")
        assert hasattr(_pkg, "ModelReviewFixApplied")
        assert hasattr(_pkg, "ModelReviewFindingResolved")
        assert hasattr(_pkg, "ModelFindingFixPair")
        assert _pkg.ModelReviewFindingObserved is ModelReviewFindingObserved
        assert _pkg.ModelReviewFixApplied is ModelReviewFixApplied
        assert _pkg.ModelReviewFindingResolved is ModelReviewFindingResolved
        assert _pkg.ModelFindingFixPair is ModelFindingFixPair
