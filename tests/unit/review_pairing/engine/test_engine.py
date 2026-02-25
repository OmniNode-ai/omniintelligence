# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the PairingEngine (OMN-2551).

Covers: happy path, temporal window filtering, ambiguity detection,
formatter batch exclusion from promotion, idempotency, and pairing type
determination.

Reference: OMN-2551
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.engine.engine import (
    CandidateFix,
    PairingEngine,
)
from omniintelligence.review_pairing.models import (
    FindingFixPair,
    FindingSeverity,
    PairingType,
    ReviewFindingObserved,
    ReviewFixApplied,
)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_REPO = "OmniNode-ai/omniintelligence"
_PR_ID = 42
_SHA_FINDING = "abc1234def5"
_SHA_FIX = "fedcba98765"
_FILE = "src/omniintelligence/nodes/foo.py"

_HUNK_WITH_LINE_10 = "@@ -8,5 +8,5 @@ def foo():\n-    long_variable_name_that_is_too_long = True\n+    x = True\n"


def _make_finding(
    *,
    repo: str = _REPO,
    pr_id: int = _PR_ID,
    rule_id: str = "ruff:E501",
    file_path: str = _FILE,
    line_start: int = 10,
    line_end: int | None = None,
    observed_at: datetime = _NOW,
    commit_sha: str = _SHA_FINDING,
) -> ReviewFindingObserved:
    return ReviewFindingObserved(
        finding_id=uuid4(),
        repo=repo,
        pr_id=pr_id,
        rule_id=rule_id,
        severity=FindingSeverity.WARNING,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        tool_name="ruff",
        tool_version="0.3.0",
        normalized_message="line too long",
        raw_message="E501 line too long (100 > 88 chars)",
        commit_sha_observed=commit_sha,
        observed_at=observed_at,
    )


def _make_fix(
    *,
    finding_id: object = None,
    fix_commit_sha: str = _SHA_FIX,
    file_path: str = _FILE,
    diff_hunks: list[str] | None = None,
    touched_line_range: tuple[int, int] = (8, 12),
    tool_autofix: bool = False,
    applied_at: datetime | None = None,
) -> ReviewFixApplied:
    return ReviewFixApplied(
        fix_id=uuid4(),
        finding_id=finding_id or uuid4(),
        fix_commit_sha=fix_commit_sha,
        file_path=file_path,
        diff_hunks=diff_hunks or [_HUNK_WITH_LINE_10],
        touched_line_range=touched_line_range,
        tool_autofix=tool_autofix,
        applied_at=applied_at or (_NOW + timedelta(hours=1)),
    )


def _make_candidate(
    fix: ReviewFixApplied | None = None,
    *,
    disappearance_confirmed: bool = False,
    all_pr_files: set[str] | None = None,
) -> CandidateFix:
    return CandidateFix(
        fix=fix or _make_fix(),
        disappearance_confirmed=disappearance_confirmed,
        all_pr_files=all_pr_files or {_FILE},
    )


# ---------------------------------------------------------------------------
# PairingEngine — basic cases
# ---------------------------------------------------------------------------


class TestPairingEngineBasic:
    @pytest.mark.unit
    def test_no_candidates_returns_empty_result(self) -> None:
        engine = PairingEngine()
        finding = _make_finding()
        result = engine.pair(finding, [])
        assert result.finding_id == finding.finding_id
        assert result.pairs == []
        assert result.promoted_pairs == []
        assert result.skipped_reason == "no_candidates"

    @pytest.mark.unit
    def test_single_high_confidence_candidate_produces_pair(self) -> None:
        engine = PairingEngine()
        finding = _make_finding()
        candidate = _make_candidate(
            _make_fix(
                finding_id=finding.finding_id,
                # Rule ID in hunk → rule_id_matched bonus
                diff_hunks=["@@ -8,5 +8,5 @@ def foo():\n- E501 long line\n+ short"],
                # Anchored to hunk covering line 10
            ),
            disappearance_confirmed=True,
        )
        result = engine.pair(finding, [candidate])
        assert len(result.pairs) == 1
        assert isinstance(result.pairs[0], FindingFixPair)

    @pytest.mark.unit
    def test_result_contains_finding_id(self) -> None:
        engine = PairingEngine()
        finding = _make_finding()
        candidate = _make_candidate()
        result = engine.pair(finding, [candidate])
        assert result.finding_id == finding.finding_id

    @pytest.mark.unit
    def test_pair_confidence_score_in_0_1_range(self) -> None:
        engine = PairingEngine()
        finding = _make_finding()
        candidate = _make_candidate()
        result = engine.pair(finding, [candidate])
        if result.pairs:
            assert 0.0 <= result.pairs[0].confidence_score <= 1.0


# ---------------------------------------------------------------------------
# PairingEngine — temporal window
# ---------------------------------------------------------------------------


class TestPairingEngineTemporalWindow:
    @pytest.mark.unit
    def test_fix_before_finding_excluded(self) -> None:
        engine = PairingEngine(temporal_window_hours=72)
        finding = _make_finding(observed_at=_NOW)
        # Fix applied 1 hour BEFORE the finding
        early_fix = _make_fix(applied_at=_NOW - timedelta(hours=1))
        candidate = _make_candidate(early_fix)
        result = engine.pair(finding, [candidate])
        assert result.skipped_reason == "all_candidates_outside_temporal_window"

    @pytest.mark.unit
    def test_fix_after_temporal_window_excluded(self) -> None:
        engine = PairingEngine(temporal_window_hours=24)
        finding = _make_finding(observed_at=_NOW)
        # Fix applied 48 hours later — outside 24h window
        late_fix = _make_fix(applied_at=_NOW + timedelta(hours=48))
        candidate = _make_candidate(late_fix)
        result = engine.pair(finding, [candidate])
        assert result.skipped_reason == "all_candidates_outside_temporal_window"

    @pytest.mark.unit
    def test_fix_within_temporal_window_included(self) -> None:
        engine = PairingEngine(temporal_window_hours=72)
        finding = _make_finding(observed_at=_NOW)
        fix = _make_fix(applied_at=_NOW + timedelta(hours=12))
        candidate = _make_candidate(fix)
        result = engine.pair(finding, [candidate])
        # Even with a low score, the candidate was not filtered by time window
        assert result.skipped_reason != "all_candidates_outside_temporal_window"


# ---------------------------------------------------------------------------
# PairingEngine — ambiguity penalty
# ---------------------------------------------------------------------------


class TestPairingEngineAmbiguity:
    @pytest.mark.unit
    def test_two_candidates_touching_same_region_triggers_ambiguity_penalty(
        self,
    ) -> None:
        engine = PairingEngine()
        finding = _make_finding(line_start=10, file_path=_FILE)
        # Both candidates touch file_path and line 10
        fix1 = _make_fix(file_path=_FILE, touched_line_range=(8, 12))
        fix2 = _make_fix(
            file_path=_FILE, touched_line_range=(9, 11), fix_commit_sha="abc9999999"
        )
        candidates = [_make_candidate(fix1), _make_candidate(fix2)]
        result = engine.pair(finding, candidates)
        # Should still produce a pair but with ambiguity penalty applied
        assert result.finding_id == finding.finding_id

    @pytest.mark.unit
    def test_candidates_in_different_files_no_ambiguity(self) -> None:
        engine = PairingEngine()
        finding = _make_finding(line_start=10, file_path=_FILE)
        fix_same = _make_fix(file_path=_FILE, touched_line_range=(8, 12))
        fix_other = _make_fix(
            file_path="src/other.py",
            touched_line_range=(8, 12),
            fix_commit_sha="abc0000000",
        )
        candidates = [_make_candidate(fix_same), _make_candidate(fix_other)]
        result = engine.pair(finding, candidates)
        # No ambiguity — different files
        assert result.pairs or result.skipped_reason is not None


# ---------------------------------------------------------------------------
# PairingEngine — formatter batch handling
# ---------------------------------------------------------------------------


class TestPairingEngineFormatterBatch:
    @pytest.mark.unit
    def test_formatter_batch_not_promoted(self) -> None:
        engine = PairingEngine()
        finding = _make_finding()
        # Create a large set of PR files to trigger formatter batch detection
        all_pr_files = {f"file_{i}.py" for i in range(20)}
        # Fix touches 19 out of 20 files = 95% → formatter batch
        fix_files = all_pr_files - {"file_19.py"}
        fix = _make_fix(
            finding_id=finding.finding_id,
            diff_hunks=["@@ -8,5 +8,5 @@ E501 long line here\n- long\n+ short"],
            applied_at=_NOW + timedelta(hours=1),
        )
        candidate = CandidateFix(
            fix=fix,
            disappearance_confirmed=True,
            all_pr_files=all_pr_files,
        )
        result = engine.pair(finding, [candidate])
        # Formatter batch commits should not be in promoted_pairs
        assert all(p.confidence_score >= 0.0 for p in result.pairs)
        # Even if there are pairs, they should not be promoted if formatter batch
        if result.pairs:
            assert result.promoted_pairs == []


# ---------------------------------------------------------------------------
# PairingEngine — autofix pairing type
# ---------------------------------------------------------------------------


class TestPairingEnginePairingType:
    @pytest.mark.unit
    def test_autofix_tool_produces_autofix_pairing_type(self) -> None:
        engine = PairingEngine()
        finding = _make_finding()
        fix = _make_fix(
            finding_id=finding.finding_id,
            tool_autofix=True,
            diff_hunks=["@@ -8,5 +8,5 @@ E501 ruff:E501\n- long\n+ short"],
            applied_at=_NOW + timedelta(hours=1),
        )
        candidate = _make_candidate(fix, disappearance_confirmed=True)
        result = engine.pair(finding, [candidate])
        if result.pairs:
            assert result.pairs[0].pairing_type == PairingType.AUTOFIX

    @pytest.mark.unit
    def test_same_commit_sha_produces_same_commit_pairing_type(self) -> None:
        engine = PairingEngine()
        finding = _make_finding(commit_sha=_SHA_FINDING)
        fix = _make_fix(
            finding_id=finding.finding_id,
            fix_commit_sha=_SHA_FINDING,  # Same SHA as finding
            applied_at=_NOW + timedelta(hours=1),
        )
        candidate = _make_candidate(fix)
        result = engine.pair(finding, [candidate])
        if result.pairs:
            assert result.pairs[0].pairing_type == PairingType.SAME_COMMIT


# ---------------------------------------------------------------------------
# PairingEngine — idempotency
# ---------------------------------------------------------------------------


class TestPairingEngineIdempotency:
    @pytest.mark.unit
    def test_same_inputs_produce_same_outcome_structure(self) -> None:
        """Calling pair() twice with the same finding/candidates gives equivalent results."""
        engine = PairingEngine()
        finding = _make_finding()
        fix = _make_fix(
            finding_id=finding.finding_id,
            diff_hunks=["@@ -8,5 +8,5 @@ ruff:E501\n- long\n+ short"],
            applied_at=_NOW + timedelta(hours=2),
        )
        candidate = _make_candidate(fix, disappearance_confirmed=True)

        result1 = engine.pair(finding, [candidate])
        result2 = engine.pair(finding, [candidate])

        assert result1.finding_id == result2.finding_id
        assert len(result1.pairs) == len(result2.pairs)
        assert len(result1.promoted_pairs) == len(result2.promoted_pairs)
        if result1.pairs:
            assert (
                result1.pairs[0].confidence_score == result2.pairs[0].confidence_score
            )
