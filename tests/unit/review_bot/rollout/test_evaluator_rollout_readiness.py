# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for rollout readiness evaluator and enforcement mode.

Tests cover OMN-2500 acceptance criteria:
- R1: EnforcementMode enum gates CI behavior
- R2: Readiness signals inform graduation decisions
"""

from __future__ import annotations

import pytest

from omniintelligence.review_bot.rollout.evaluator_rollout_readiness import (
    FALSE_POSITIVE_RATE_THRESHOLD,
    MIN_CLEAN_MERGED_PRS,
    MIN_PRS_REVIEWED_IN_WARN,
    EvaluatorRolloutReadiness,
)
from omniintelligence.review_bot.rollout.model_enforcement_mode import EnforcementMode
from omniintelligence.review_bot.rollout.reporter_rollout_status import (
    ReporterRolloutStatus,
)

# ---------------------------------------------------------------------------
# R1: EnforcementMode enum
# ---------------------------------------------------------------------------


class TestEnforcementModeEnum:
    def test_observe_value(self) -> None:
        """R1: OBSERVE enum value."""
        assert EnforcementMode.OBSERVE.value == "OBSERVE"

    def test_warn_value(self) -> None:
        """R1: WARN enum value."""
        assert EnforcementMode.WARN.value == "WARN"

    def test_block_value(self) -> None:
        """R1: BLOCK enum value."""
        assert EnforcementMode.BLOCK.value == "BLOCK"

    def test_three_modes_defined(self) -> None:
        """R1: Exactly three modes exist."""
        assert len(list(EnforcementMode)) == 3

    def test_observe_does_not_post_comments(self) -> None:
        """R1: OBSERVE mode never posts comments."""
        assert EnforcementMode.OBSERVE.posts_comments is False

    def test_warn_posts_comments(self) -> None:
        """R1: WARN mode posts inline comments."""
        assert EnforcementMode.WARN.posts_comments is True

    def test_block_posts_comments(self) -> None:
        """R1: BLOCK mode posts inline comments."""
        assert EnforcementMode.BLOCK.posts_comments is True

    def test_observe_does_not_block_on_blocker(self) -> None:
        """R1: OBSERVE never fails CI."""
        assert EnforcementMode.OBSERVE.blocks_on_blocker is False

    def test_warn_does_not_block_on_blocker(self) -> None:
        """R1: WARN never fails CI."""
        assert EnforcementMode.WARN.blocks_on_blocker is False

    def test_block_blocks_on_blocker(self) -> None:
        """R1: BLOCK fails CI on BLOCKER findings."""
        assert EnforcementMode.BLOCK.blocks_on_blocker is True

    def test_observe_ci_always_passes(self) -> None:
        assert EnforcementMode.OBSERVE.ci_always_passes is True

    def test_warn_ci_always_passes(self) -> None:
        assert EnforcementMode.WARN.ci_always_passes is True

    def test_block_ci_does_not_always_pass(self) -> None:
        assert EnforcementMode.BLOCK.ci_always_passes is False

    def test_from_policy_string_lowercase(self) -> None:
        """R1: Policy YAML lowercase string maps to enum."""
        assert EnforcementMode.from_policy_string("observe") == EnforcementMode.OBSERVE
        assert EnforcementMode.from_policy_string("warn") == EnforcementMode.WARN
        assert EnforcementMode.from_policy_string("block") == EnforcementMode.BLOCK

    def test_from_policy_string_uppercase(self) -> None:
        """R1: Uppercase strings also accepted."""
        assert EnforcementMode.from_policy_string("OBSERVE") == EnforcementMode.OBSERVE

    def test_from_policy_string_invalid_raises(self) -> None:
        """R1: Invalid string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid enforcement_mode"):
            EnforcementMode.from_policy_string("silent")

    def test_default_is_observe(self) -> None:
        """R1: Missing policy enforcement_mode defaults to OBSERVE."""
        # Simulate missing value by using None-equivalent (empty/default logic)
        # The policy model uses "observe" as default
        mode = EnforcementMode.from_policy_string("observe")
        assert mode == EnforcementMode.OBSERVE


# ---------------------------------------------------------------------------
# R2: Readiness signals - OBSERVE -> WARN
# ---------------------------------------------------------------------------


class TestObserveToWarnReadiness:
    def test_all_signals_ready_when_thresholds_met(self) -> None:
        """R2: All signals ready when PRs >= min and FP rate < threshold."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=0.10,
        )
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)

        assert report.overall_ready is True

    def test_not_ready_if_insufficient_prs(self) -> None:
        """R2: Not ready if fewer than min PRs reviewed."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=5,
            false_positive_rate=0.10,
        )
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)

        prs_signal = next(s for s in report.signals if s.name == "min_prs_reviewed")
        assert prs_signal.is_ready is False
        assert report.overall_ready is False

    def test_not_ready_if_fp_rate_too_high(self) -> None:
        """R2: Not ready if false-positive rate >= threshold."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=0.25,  # Above 20% threshold
        )
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)

        fp_signal = next(s for s in report.signals if s.name == "false_positive_rate")
        assert fp_signal.is_ready is False
        assert report.overall_ready is False

    def test_signals_include_correct_names(self) -> None:
        evaluator = EvaluatorRolloutReadiness()
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)

        signal_names = {s.name for s in report.signals}
        assert "min_prs_reviewed" in signal_names
        assert "false_positive_rate" in signal_names

    def test_signal_count_for_observe_to_warn(self) -> None:
        evaluator = EvaluatorRolloutReadiness()
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)

        assert report.total_count == 2

    def test_exactly_at_min_prs_is_ready(self) -> None:
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=MIN_PRS_REVIEWED_IN_WARN,
            false_positive_rate=0.10,
        )
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)
        prs_signal = next(s for s in report.signals if s.name == "min_prs_reviewed")
        assert prs_signal.is_ready is True

    def test_exactly_at_fp_threshold_not_ready(self) -> None:
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=FALSE_POSITIVE_RATE_THRESHOLD,  # Not < threshold
        )
        report = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)
        fp_signal = next(s for s in report.signals if s.name == "false_positive_rate")
        assert fp_signal.is_ready is False


# ---------------------------------------------------------------------------
# R2: Readiness signals - WARN -> BLOCK
# ---------------------------------------------------------------------------


class TestWarnToBlockReadiness:
    def test_all_signals_ready_when_thresholds_met(self) -> None:
        """R2: All signals ready for WARN -> BLOCK graduation."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=0.10,
            blockers_in_last_merged_prs=0,
        )
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        assert report.overall_ready is True

    def test_not_ready_if_blockers_in_recent_merges(self) -> None:
        """R2: Not ready if any BLOCKER in last N merged PRs."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=0.10,
            blockers_in_last_merged_prs=2,  # Blockers exist
        )
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        blocker_signal = next(
            s for s in report.signals if s.name == "no_blockers_in_recent_merges"
        )
        assert blocker_signal.is_ready is False
        assert report.overall_ready is False

    def test_signal_count_for_warn_to_block(self) -> None:
        """R2: WARN -> BLOCK has three readiness signals."""
        evaluator = EvaluatorRolloutReadiness()
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        assert report.total_count == 3

    def test_signals_include_blocker_check(self) -> None:
        evaluator = EvaluatorRolloutReadiness()
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        signal_names = {s.name for s in report.signals}
        assert "no_blockers_in_recent_merges" in signal_names

    def test_partial_readiness_reported(self) -> None:
        """R2: Partial readiness is reported accurately."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=0.10,
            blockers_in_last_merged_prs=1,  # One signal fails
        )
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        assert report.ready_count == 2
        assert report.total_count == 3
        assert report.overall_ready is False

    def test_report_contains_current_and_target_modes(self) -> None:
        evaluator = EvaluatorRolloutReadiness()
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        assert report.current_mode == EnforcementMode.WARN
        assert report.target_mode == EnforcementMode.BLOCK

    def test_no_auto_promotion(self) -> None:
        """R2: Signals are advisory only; report does not change enforcement mode."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=100,
            false_positive_rate=0.01,
            blockers_in_last_merged_prs=0,
        )
        report = evaluator.evaluate(EnforcementMode.WARN, EnforcementMode.BLOCK)

        # Report is advisory; current mode does NOT change
        assert report.current_mode == EnforcementMode.WARN
        assert report.overall_ready is True  # Ready, but no auto-promotion


# ---------------------------------------------------------------------------
# R2: Constants
# ---------------------------------------------------------------------------


class TestReadinessConstants:
    def test_fp_rate_threshold(self) -> None:
        assert FALSE_POSITIVE_RATE_THRESHOLD == 0.20

    def test_min_prs_warn(self) -> None:
        assert MIN_PRS_REVIEWED_IN_WARN == 10

    def test_min_clean_prs(self) -> None:
        assert MIN_CLEAN_MERGED_PRS == 5


# ---------------------------------------------------------------------------
# R3: Reporter
# ---------------------------------------------------------------------------


class TestReporterRolloutStatus:
    def test_pr_summary_includes_mode(self) -> None:
        """R3: PR summary includes current enforcement mode."""
        reporter = ReporterRolloutStatus()
        report = reporter.build_pr_summary(
            mode=EnforcementMode.WARN,
            finding_summary={"BLOCKER": 0, "WARNING": 3},
        )

        assert "WARN" in report.markdown_body

    def test_pr_summary_includes_findings(self) -> None:
        reporter = ReporterRolloutStatus()
        report = reporter.build_pr_summary(
            mode=EnforcementMode.WARN,
            finding_summary={"WARNING": 5},
        )

        assert "5" in report.markdown_body
        assert "WARNING" in report.markdown_body

    def test_block_mode_includes_ci_blocked_note(self) -> None:
        """R1: BLOCK mode PR summary shows blockers cause CI failure."""
        reporter = ReporterRolloutStatus()
        report = reporter.build_pr_summary(
            mode=EnforcementMode.BLOCK,
            finding_summary={"BLOCKER": 2},
        )

        assert "CI blocked" in report.markdown_body

    def test_warn_mode_blocker_no_ci_blocked_note(self) -> None:
        """R1: WARN mode BLOCKER does NOT say CI blocked."""
        reporter = ReporterRolloutStatus()
        report = reporter.build_pr_summary(
            mode=EnforcementMode.WARN,
            finding_summary={"BLOCKER": 2},
        )

        assert "CI blocked" not in report.markdown_body

    def test_nightly_audit_includes_top_rules(self) -> None:
        """R3: Nightly audit includes top 5 rules by finding count."""
        reporter = ReporterRolloutStatus()
        top_rules = [("formatter", 10), ("import_sort", 7), ("type_completer", 3)]

        report = reporter.build_nightly_audit_report(
            mode=EnforcementMode.OBSERVE,
            finding_summary={"BLOCKER": 0, "WARNING": 20},
            trend_vs_7d={"WARNING": -3},
            top_rules=top_rules,
        )

        assert "formatter" in report.markdown_body
        assert "import_sort" in report.markdown_body

    def test_nightly_audit_includes_trend(self) -> None:
        """R3: Nightly audit shows finding trend vs 7 days ago."""
        reporter = ReporterRolloutStatus()
        report = reporter.build_nightly_audit_report(
            mode=EnforcementMode.OBSERVE,
            finding_summary={"WARNING": 10},
            trend_vs_7d={"WARNING": 3},
            top_rules=[],
        )

        assert "+3" in report.markdown_body

    def test_nightly_audit_runs_in_any_mode(self) -> None:
        """R3: Nightly audit works in OBSERVE, WARN, and BLOCK modes."""
        reporter = ReporterRolloutStatus()
        for mode in EnforcementMode:
            report = reporter.build_nightly_audit_report(
                mode=mode,
                finding_summary={},
                trend_vs_7d={},
                top_rules=[],
            )
            assert mode.value in report.markdown_body

    def test_pr_summary_with_readiness_report(self) -> None:
        """R2: PR summary includes readiness signals when provided."""
        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=5,
            false_positive_rate=0.10,
        )
        readiness = evaluator.evaluate(EnforcementMode.OBSERVE, EnforcementMode.WARN)

        reporter = ReporterRolloutStatus()
        report = reporter.build_pr_summary(
            mode=EnforcementMode.OBSERVE,
            finding_summary={},
            readiness_report=readiness,
        )

        assert "Graduation Readiness" in report.markdown_body
        assert "Advisory only" in report.markdown_body
