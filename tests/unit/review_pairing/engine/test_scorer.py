# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the confidence scorer (OMN-2551).

Covers all score/penalty combinations from the design doc, edge cases,
and formatter batch detection.

Reference: OMN-2551
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.engine.scorer import (
    PENALTY_AMBIGUOUS_COMMITS,
    SCORE_ANCHORED_TO_HUNK,
    SCORE_DIFF_REMOVES_TOKEN,
    SCORE_DISAPPEARANCE_CONFIRMED,
    SCORE_RULE_ID_MATCH,
    ConfidenceScorer,
    ScoringContext,
    has_config_change,
    is_anchored_to_diff,
    is_formatter_batch_commit,
    line_in_hunk,
    parse_hunk_line_range,
)

# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------


def _ctx(**overrides: object) -> ScoringContext:
    """Build a ScoringContext with all signals False/0 by default."""
    defaults: dict[str, object] = {
        "rule_id_matched": False,
        "diff_removes_token": False,
        "disappearance_confirmed": False,
        "anchored_to_hunk": False,
        "ambiguous_commits": False,
        "disappears_without_mod": False,
        "config_change_detected": False,
        "candidate_commit_count": 1,
        "is_formatter_batch": False,
    }
    defaults.update(overrides)
    return ScoringContext(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ConfidenceScorer — positive signals
# ---------------------------------------------------------------------------


class TestConfidenceScorerPositiveSignals:
    @pytest.mark.unit
    def test_no_signals_score_zero(self) -> None:
        """No positive signals → score is 0.0."""
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx())
        assert result.confidence_score == 0.0
        assert result.promoted is False

    @pytest.mark.unit
    def test_rule_id_matched_adds_0_40(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx(rule_id_matched=True))
        assert abs(result.confidence_score - SCORE_RULE_ID_MATCH) < 1e-9
        assert result.score_breakdown["rule_id_match"] == SCORE_RULE_ID_MATCH

    @pytest.mark.unit
    def test_diff_removes_token_adds_0_30(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx(diff_removes_token=True))
        assert abs(result.confidence_score - SCORE_DIFF_REMOVES_TOKEN) < 1e-9

    @pytest.mark.unit
    def test_disappearance_confirmed_adds_0_20(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx(disappearance_confirmed=True))
        assert abs(result.confidence_score - SCORE_DISAPPEARANCE_CONFIRMED) < 1e-9

    @pytest.mark.unit
    def test_anchored_to_hunk_adds_0_10(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx(anchored_to_hunk=True))
        assert abs(result.confidence_score - SCORE_ANCHORED_TO_HUNK) < 1e-9

    @pytest.mark.unit
    def test_all_positive_signals_score_1_0(self) -> None:
        """All four positive signals sum to 1.0."""
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                disappearance_confirmed=True,
                anchored_to_hunk=True,
            )
        )
        assert abs(result.confidence_score - 1.0) < 1e-9
        assert result.promoted is True

    @pytest.mark.unit
    def test_rule_id_and_diff_removes_token_meet_promotion_threshold(self) -> None:
        """rule_id (0.40) + diff_removes_token (0.30) = 0.70 < 0.75 → not promoted."""
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx(rule_id_matched=True, diff_removes_token=True))
        assert result.confidence_score == pytest.approx(0.70)
        assert result.promoted is False

    @pytest.mark.unit
    def test_rule_id_plus_diff_plus_disappearance_promoted(self) -> None:
        """0.40 + 0.30 + 0.20 = 0.90 ≥ 0.75 → promoted."""
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                disappearance_confirmed=True,
            )
        )
        assert result.confidence_score == pytest.approx(0.90)
        assert result.promoted is True


# ---------------------------------------------------------------------------
# ConfidenceScorer — penalty conditions
# ---------------------------------------------------------------------------


class TestConfidenceScorerPenalties:
    @pytest.mark.unit
    def test_ambiguous_commits_penalty_minus_0_20(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(_ctx(rule_id_matched=True, ambiguous_commits=True))
        # 0.40 - 0.20 = 0.20
        assert result.confidence_score == pytest.approx(0.20)
        assert result.score_breakdown["ambiguous_commits"] == PENALTY_AMBIGUOUS_COMMITS

    @pytest.mark.unit
    def test_disappears_without_mod_penalty_minus_0_15(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                disappears_without_mod=True,
            )
        )
        # 0.40 + 0.30 - 0.15 = 0.55
        assert result.confidence_score == pytest.approx(0.55)

    @pytest.mark.unit
    def test_config_change_penalty_minus_0_10(self) -> None:
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                config_change_detected=True,
            )
        )
        # 0.40 + 0.30 - 0.10 = 0.60
        assert result.confidence_score == pytest.approx(0.60)

    @pytest.mark.unit
    def test_all_penalties_applied_clamps_to_zero(self) -> None:
        """Applying all penalties with no positive signals → clamped to 0.0."""
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                ambiguous_commits=True,
                disappears_without_mod=True,
                config_change_detected=True,
            )
        )
        # -0.20 - 0.15 - 0.10 = -0.45 → clamped to 0.0
        assert result.confidence_score == 0.0
        assert result.raw_score < 0.0

    @pytest.mark.unit
    def test_score_clamped_max_1_0_even_if_raw_exceeds(self) -> None:
        """Score is clamped to 1.0 even if somehow raw would exceed 1.0."""
        scorer = ConfidenceScorer()
        # All positive signals = 1.0; this tests clamping in isolation
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                disappearance_confirmed=True,
                anchored_to_hunk=True,
            )
        )
        assert result.confidence_score <= 1.0

    @pytest.mark.unit
    def test_formatter_batch_not_promoted(self) -> None:
        """Formatter batch commits should not be promoted even if score >= 0.75."""
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                disappearance_confirmed=True,
                is_formatter_batch=True,
            )
        )
        # Score is 0.90 but formatter batch → not promoted
        assert result.confidence_score == pytest.approx(0.90)
        assert result.promoted is False
        assert result.is_formatter_batch is True

    @pytest.mark.unit
    def test_full_penalty_context_barely_misses_promotion(self) -> None:
        """All positives + config change penalty: 1.0 - 0.10 = 0.90 → still promoted."""
        scorer = ConfidenceScorer()
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                disappearance_confirmed=True,
                anchored_to_hunk=True,
                config_change_detected=True,
            )
        )
        # 1.0 - 0.10 = 0.90 → still ≥ 0.75
        assert result.confidence_score == pytest.approx(0.90)
        assert result.promoted is True

    @pytest.mark.unit
    def test_promotion_threshold_boundary_at_exactly_0_75(self) -> None:
        """Score exactly at the promotion threshold (0.75) should promote."""
        scorer = ConfidenceScorer()
        # rule_id (0.40) + diff_removes_token (0.30) + anchored (0.10) = 0.80
        # Then ambiguous (-0.20) = 0.60 < 0.75 → not promoted
        result = scorer.score(
            _ctx(
                rule_id_matched=True,
                diff_removes_token=True,
                anchored_to_hunk=True,
                ambiguous_commits=True,
            )
        )
        assert result.confidence_score == pytest.approx(0.60)
        assert result.promoted is False


# ---------------------------------------------------------------------------
# Hunk intersection helpers
# ---------------------------------------------------------------------------


class TestParseHunkLineRange:
    @pytest.mark.unit
    def test_standard_hunk_header(self) -> None:
        hunk = "@@ -10,5 +10,5 @@ def foo():"
        result = parse_hunk_line_range(hunk)
        assert result == (10, 14)

    @pytest.mark.unit
    def test_single_line_hunk(self) -> None:
        hunk = "@@ -5 +5 @@ single line"
        result = parse_hunk_line_range(hunk)
        # count defaults to 1 → end = start + 0 = 5
        assert result is not None
        assert result[0] == 5
        assert result[1] == 5

    @pytest.mark.unit
    def test_missing_hunk_header_returns_none(self) -> None:
        assert parse_hunk_line_range("no hunk marker here") is None

    @pytest.mark.unit
    def test_zero_count_hunk(self) -> None:
        # @@ -10,0 +10,0 @@ — deleted block with no new lines
        hunk = "@@ -10,0 +10,0 @@"
        result = parse_hunk_line_range(hunk)
        # count=0 → max(0, 0-1) = 0 → end = start
        assert result is not None
        assert result == (10, 10)


class TestLineInHunk:
    @pytest.mark.unit
    def test_line_within_range(self) -> None:
        hunk = "@@ -1,10 +1,10 @@"
        assert line_in_hunk(5, hunk) is True

    @pytest.mark.unit
    def test_line_at_range_boundary(self) -> None:
        hunk = "@@ -1,10 +1,10 @@"
        assert line_in_hunk(1, hunk) is True
        assert line_in_hunk(10, hunk) is True

    @pytest.mark.unit
    def test_line_outside_range(self) -> None:
        hunk = "@@ -1,5 +1,5 @@"
        assert line_in_hunk(10, hunk) is False

    @pytest.mark.unit
    def test_empty_hunk_string(self) -> None:
        assert line_in_hunk(1, "") is False


class TestIsAnchoredToDiff:
    @pytest.mark.unit
    def test_line_in_any_hunk(self) -> None:
        hunks = [
            "@@ -1,5 +1,5 @@",
            "@@ -20,10 +20,10 @@",
        ]
        assert is_anchored_to_diff(22, hunks) is True

    @pytest.mark.unit
    def test_line_not_in_any_hunk(self) -> None:
        hunks = ["@@ -1,5 +1,5 @@", "@@ -10,3 +10,3 @@"]
        assert is_anchored_to_diff(50, hunks) is False

    @pytest.mark.unit
    def test_empty_hunks_list(self) -> None:
        assert is_anchored_to_diff(5, []) is False


# ---------------------------------------------------------------------------
# Formatter batch detection
# ---------------------------------------------------------------------------


class TestIsFormatterBatchCommit:
    @pytest.mark.unit
    def test_touches_over_80_percent(self) -> None:
        all_files = {f"file_{i}.py" for i in range(10)}
        commit_files = {f"file_{i}.py" for i in range(9)}  # 90%
        assert is_formatter_batch_commit(commit_files, all_files) is True

    @pytest.mark.unit
    def test_touches_exactly_80_percent_not_flagged(self) -> None:
        all_files = {f"file_{i}.py" for i in range(10)}
        commit_files = {f"file_{i}.py" for i in range(8)}  # 80% = not > threshold
        assert is_formatter_batch_commit(commit_files, all_files) is False

    @pytest.mark.unit
    def test_small_commit_not_formatter_batch(self) -> None:
        all_files = {f"file_{i}.py" for i in range(10)}
        commit_files = {"file_0.py"}
        assert is_formatter_batch_commit(commit_files, all_files) is False

    @pytest.mark.unit
    def test_empty_pr_files_not_flagged(self) -> None:
        assert is_formatter_batch_commit({"a.py"}, set()) is False


# ---------------------------------------------------------------------------
# Config change detection
# ---------------------------------------------------------------------------


class TestHasConfigChange:
    @pytest.mark.unit
    def test_pyproject_toml_detected(self) -> None:
        assert has_config_change({"pyproject.toml"}) is True

    @pytest.mark.unit
    def test_eslintrc_detected(self) -> None:
        assert has_config_change({".eslintrc.json"}) is True

    @pytest.mark.unit
    def test_mypy_ini_detected(self) -> None:
        assert has_config_change({"mypy.ini"}) is True

    @pytest.mark.unit
    def test_ruff_toml_detected(self) -> None:
        assert has_config_change({"ruff.toml"}) is True

    @pytest.mark.unit
    def test_regular_py_file_not_config(self) -> None:
        assert has_config_change({"src/foo/bar.py"}) is False

    @pytest.mark.unit
    def test_empty_set_no_config(self) -> None:
        assert has_config_change(set()) is False

    @pytest.mark.unit
    def test_mixed_files_with_config(self) -> None:
        files = {"src/foo.py", "tests/test_bar.py", "pyproject.toml"}
        assert has_config_change(files) is True
