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
    FindingFixPair,
    FindingSeverity,
    PairingType,
    ReviewFindingObserved,
    ReviewFindingResolved,
    ReviewFixApplied,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(tz=UTC)


def _finding_observed_kwargs() -> dict:
    """Minimal valid kwargs for ReviewFindingObserved."""
    return {
        "finding_id": uuid4(),
        "repo": "OmniNode-ai/omniintelligence",
        "pr_id": 42,
        "rule_id": "ruff:E501",
        "severity": FindingSeverity.ERROR,
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
    """Minimal valid kwargs for ReviewFixApplied."""
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
    """Minimal valid kwargs for ReviewFindingResolved."""
    return {
        "resolution_id": uuid4(),
        "finding_id": finding_id or uuid4(),
        "fix_commit_sha": "def5678",
        "verified_at_commit_sha": "ghi9012",
        "ci_run_id": "12345678",
        "resolved_at": _utcnow(),
    }


def _finding_fix_pair_kwargs(finding_id: UUID | None = None) -> dict:
    """Minimal valid kwargs for FindingFixPair."""
    return {
        "pair_id": uuid4(),
        "finding_id": finding_id or uuid4(),
        "fix_commit_sha": "def5678",
        "diff_hunks": ["@@ -10,1 +10,1 @@ -old line\n+new line"],
        "confidence_score": 0.85,
        "disappearance_confirmed": True,
        "pairing_type": PairingType.AUTOFIX,
        "created_at": _utcnow(),
    }


# ---------------------------------------------------------------------------
# ReviewFindingObserved tests
# ---------------------------------------------------------------------------


class TestReviewFindingObserved:
    """Tests for ReviewFindingObserved model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ReviewFindingObserved(**_finding_observed_kwargs())
        assert isinstance(model.finding_id, UUID)
        assert model.repo == "OmniNode-ai/omniintelligence"
        assert model.pr_id == 42
        assert model.severity == FindingSeverity.ERROR

    @pytest.mark.unit
    def test_line_end_optional(self) -> None:
        """line_end should be None by default (single-line finding)."""
        model = ReviewFindingObserved(**_finding_observed_kwargs())
        assert model.line_end is None

    @pytest.mark.unit
    def test_line_end_set(self) -> None:
        """line_end should accept valid values >= line_start."""
        kwargs = _finding_observed_kwargs()
        kwargs["line_start"] = 10
        kwargs["line_end"] = 15
        model = ReviewFindingObserved(**kwargs)
        assert model.line_end == 15

    @pytest.mark.unit
    def test_pr_id_must_be_positive(self) -> None:
        """pr_id <= 0 should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["pr_id"] = 0
        with pytest.raises(ValidationError):
            ReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_line_start_must_be_positive(self) -> None:
        """line_start <= 0 should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["line_start"] = 0
        with pytest.raises(ValidationError):
            ReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_invalid_severity_raises(self) -> None:
        """Invalid severity string should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["severity"] = "critical"
        with pytest.raises(ValidationError):
            ReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_commit_sha_min_length(self) -> None:
        """commit_sha_observed shorter than 7 chars should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["commit_sha_observed"] = "abc"
        with pytest.raises(ValidationError):
            ReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_commit_sha_max_length(self) -> None:
        """commit_sha_observed longer than 40 chars should fail validation."""
        kwargs = _finding_observed_kwargs()
        kwargs["commit_sha_observed"] = "a" * 41
        with pytest.raises(ValidationError):
            ReviewFindingObserved(**kwargs)

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ReviewFindingObserved(**_finding_observed_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.pr_id = 99  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ReviewFindingObserved(**_finding_observed_kwargs())
        dumped = original.model_dump()
        reconstructed = ReviewFindingObserved(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_model_dump_json(self) -> None:
        """model_dump_json() should produce valid JSON."""
        model = ReviewFindingObserved(**_finding_observed_kwargs())
        json_str = model.model_dump_json()
        data = json.loads(json_str)
        assert data["repo"] == "OmniNode-ai/omniintelligence"
        assert data["pr_id"] == 42

    @pytest.mark.unit
    def test_all_severity_values_valid(self) -> None:
        """All FindingSeverity enum values should be accepted."""
        for severity in FindingSeverity:
            kwargs = _finding_observed_kwargs()
            kwargs["severity"] = severity
            model = ReviewFindingObserved(**kwargs)
            assert model.severity == severity


# ---------------------------------------------------------------------------
# ReviewFixApplied tests
# ---------------------------------------------------------------------------


class TestReviewFixApplied:
    """Tests for ReviewFixApplied model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ReviewFixApplied(**_fix_applied_kwargs())
        assert isinstance(model.fix_id, UUID)
        assert model.tool_autofix is True

    @pytest.mark.unit
    def test_diff_hunks_default_empty(self) -> None:
        """diff_hunks should default to empty list."""
        kwargs = _fix_applied_kwargs()
        del kwargs["diff_hunks"]
        model = ReviewFixApplied(**kwargs)
        assert model.diff_hunks == []

    @pytest.mark.unit
    def test_touched_line_range_tuple(self) -> None:
        """touched_line_range should be a tuple of two ints."""
        model = ReviewFixApplied(**_fix_applied_kwargs())
        assert isinstance(model.touched_line_range, tuple)
        assert len(model.touched_line_range) == 2

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ReviewFixApplied(**_fix_applied_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.tool_autofix = False  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ReviewFixApplied(**_fix_applied_kwargs())
        dumped = original.model_dump()
        reconstructed = ReviewFixApplied(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_fix_commit_sha_min_length(self) -> None:
        """fix_commit_sha shorter than 7 chars should fail validation."""
        kwargs = _fix_applied_kwargs()
        kwargs["fix_commit_sha"] = "abc"
        with pytest.raises(ValidationError):
            ReviewFixApplied(**kwargs)


# ---------------------------------------------------------------------------
# ReviewFindingResolved tests
# ---------------------------------------------------------------------------


class TestReviewFindingResolved:
    """Tests for ReviewFindingResolved model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = ReviewFindingResolved(**_finding_resolved_kwargs())
        assert isinstance(model.resolution_id, UUID)
        assert model.ci_run_id == "12345678"

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = ReviewFindingResolved(**_finding_resolved_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.ci_run_id = "other"  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = ReviewFindingResolved(**_finding_resolved_kwargs())
        dumped = original.model_dump()
        reconstructed = ReviewFindingResolved(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_verified_at_commit_sha_min_length(self) -> None:
        """verified_at_commit_sha shorter than 7 chars should fail validation."""
        kwargs = _finding_resolved_kwargs()
        kwargs["verified_at_commit_sha"] = "ab"
        with pytest.raises(ValidationError):
            ReviewFindingResolved(**kwargs)


# ---------------------------------------------------------------------------
# FindingFixPair tests
# ---------------------------------------------------------------------------


class TestFindingFixPair:
    """Tests for FindingFixPair model."""

    @pytest.mark.unit
    def test_instantiation_with_valid_data(self) -> None:
        """Should instantiate successfully with all required fields."""
        model = FindingFixPair(**_finding_fix_pair_kwargs())
        assert isinstance(model.pair_id, UUID)
        assert model.confidence_score == 0.85
        assert model.disappearance_confirmed is True

    @pytest.mark.unit
    def test_confidence_score_lower_bound(self) -> None:
        """confidence_score < 0.0 should fail validation."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = -0.1
        with pytest.raises(ValidationError):
            FindingFixPair(**kwargs)

    @pytest.mark.unit
    def test_confidence_score_upper_bound(self) -> None:
        """confidence_score > 1.0 should fail validation."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = 1.1
        with pytest.raises(ValidationError):
            FindingFixPair(**kwargs)

    @pytest.mark.unit
    def test_confidence_score_boundary_zero(self) -> None:
        """confidence_score = 0.0 should be valid."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = 0.0
        model = FindingFixPair(**kwargs)
        assert model.confidence_score == 0.0

    @pytest.mark.unit
    def test_confidence_score_boundary_one(self) -> None:
        """confidence_score = 1.0 should be valid."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["confidence_score"] = 1.0
        model = FindingFixPair(**kwargs)
        assert model.confidence_score == 1.0

    @pytest.mark.unit
    def test_all_pairing_types_valid(self) -> None:
        """All PairingType enum values should be accepted."""
        for pt in PairingType:
            kwargs = _finding_fix_pair_kwargs()
            kwargs["pairing_type"] = pt
            model = FindingFixPair(**kwargs)
            assert model.pairing_type == pt

    @pytest.mark.unit
    def test_invalid_pairing_type_raises(self) -> None:
        """Invalid pairing_type string should fail validation."""
        kwargs = _finding_fix_pair_kwargs()
        kwargs["pairing_type"] = "unknown"
        with pytest.raises(ValidationError):
            FindingFixPair(**kwargs)

    @pytest.mark.unit
    def test_frozen_immutability(self) -> None:
        """Setting an attribute on a frozen model should raise."""
        model = FindingFixPair(**_finding_fix_pair_kwargs())
        with pytest.raises((TypeError, ValueError)):
            model.confidence_score = 0.5  # type: ignore[misc]

    @pytest.mark.unit
    def test_model_dump_round_trip(self) -> None:
        """model_dump() output should reconstruct an equal model."""
        original = FindingFixPair(**_finding_fix_pair_kwargs())
        dumped = original.model_dump()
        reconstructed = FindingFixPair(**dumped)
        assert original == reconstructed

    @pytest.mark.unit
    def test_model_dump_json(self) -> None:
        """model_dump_json() should produce valid JSON."""
        model = FindingFixPair(**_finding_fix_pair_kwargs())
        json_str = model.model_dump_json()
        data = json.loads(json_str)
        assert data["confidence_score"] == 0.85
        assert data["disappearance_confirmed"] is True

    @pytest.mark.unit
    def test_diff_hunks_default_empty(self) -> None:
        """diff_hunks should default to empty list."""
        kwargs = _finding_fix_pair_kwargs()
        del kwargs["diff_hunks"]
        model = FindingFixPair(**kwargs)
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

        assert hasattr(_m, "ReviewFindingObserved")
        assert hasattr(_m, "ReviewFixApplied")
        assert hasattr(_m, "ReviewFindingResolved")
        assert hasattr(_m, "FindingFixPair")
        assert _m.ReviewFindingObserved is ReviewFindingObserved
        assert _m.ReviewFixApplied is ReviewFixApplied
        assert _m.ReviewFindingResolved is ReviewFindingResolved
        assert _m.FindingFixPair is FindingFixPair

    @pytest.mark.unit
    def test_import_from_package_init(self) -> None:
        """All four models should be importable from review_pairing package."""
        import omniintelligence.review_pairing as _pkg

        assert hasattr(_pkg, "ReviewFindingObserved")
        assert hasattr(_pkg, "ReviewFixApplied")
        assert hasattr(_pkg, "ReviewFindingResolved")
        assert hasattr(_pkg, "FindingFixPair")
        assert _pkg.ReviewFindingObserved is ReviewFindingObserved
        assert _pkg.ReviewFixApplied is ReviewFixApplied
        assert _pkg.ReviewFindingResolved is ReviewFindingResolved
        assert _pkg.FindingFixPair is FindingFixPair
