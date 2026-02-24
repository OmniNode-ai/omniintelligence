# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for reward signal scoring and pairing metrics.

Tests cover:
- All five reward outcome types with correct reward values
- RewardScorer.score() metadata fields
- RewardScorer.score_batch() with mixed outcomes
- RewardScorer.reward_for() static lookup
- PairingMetricsCalculator: paired finding rate, avg confidence, p50 resolution
- PairingMetricsCalculator: reintroduction rate, autofix pct, preemptive avoidance
- Repo filtering in metrics computation
- Cumulative reward computation with filters
- Edge cases: empty inputs, zero division

Reference: OMN-2589
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.review_pairing.metrics import (
    PairingMetricsCalculator,
    RewardOutcome,
    RewardScorer,
)
from omniintelligence.review_pairing.metrics.scorer import (
    _REWARD_MAP,
    FindingRecord,
    InjectionRecord,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    *,
    repo: str = "OmniNode-ai/omniintelligence",
    rule_id: str = "ruff:E501",
    has_confirmed_pair: bool = True,
    tool_autofix: bool = False,
    confidence_score: float = 0.80,
    resolved_seconds_after: float | None = 300.0,
) -> FindingRecord:
    now = datetime.now(tz=UTC)
    resolved_at = (
        now + timedelta(seconds=resolved_seconds_after)
        if resolved_seconds_after is not None
        else None
    )
    return FindingRecord(
        finding_id=uuid.uuid4(),
        repo=repo,
        rule_id=rule_id,
        observed_at=now,
        has_confirmed_pair=has_confirmed_pair,
        tool_autofix=tool_autofix,
        confidence_score=confidence_score,
        resolved_at=resolved_at,
    )


def _injection(
    *, repo: str = "OmniNode-ai/omniintelligence", had_avoidance: bool = False
) -> InjectionRecord:
    return InjectionRecord(
        injection_id=uuid.uuid4(), repo=repo, had_avoidance=had_avoidance
    )


# ---------------------------------------------------------------------------
# RewardScorer: reward values
# ---------------------------------------------------------------------------


class TestRewardValues:
    @pytest.mark.parametrize(
        "outcome, expected",
        [
            (RewardOutcome.PREEMPTIVE_AVOIDANCE, 1.0),
            (RewardOutcome.CODEMOD_FIX, 0.8),
            (RewardOutcome.MANUAL_RESOLUTION, 0.5),
            (RewardOutcome.REINTRODUCED, -1.0),
            (RewardOutcome.REPEATED_VIOLATION, -2.0),
        ],
    )
    def test_reward_value_correct(
        self, outcome: RewardOutcome, expected: float
    ) -> None:
        scorer = RewardScorer()
        result = scorer.score(outcome=outcome)
        assert result.reward_value == expected

    def test_reward_for_static_lookup(self) -> None:
        for outcome, expected in _REWARD_MAP.items():
            assert RewardScorer.reward_for(outcome) == expected

    def test_all_five_outcomes_covered(self) -> None:
        assert len(RewardOutcome) == 5


# ---------------------------------------------------------------------------
# RewardScorer: metadata
# ---------------------------------------------------------------------------


class TestRewardScorerMetadata:
    def test_signal_id_is_uuid(self) -> None:
        scorer = RewardScorer()
        result = scorer.score(outcome=RewardOutcome.MANUAL_RESOLUTION)
        assert isinstance(result.signal_id, uuid.UUID)

    def test_agent_id_stored(self) -> None:
        scorer = RewardScorer()
        result = scorer.score(
            outcome=RewardOutcome.PREEMPTIVE_AVOIDANCE,
            agent_id="claude-sonnet-4",
        )
        assert result.agent_id == "claude-sonnet-4"

    def test_repo_stored(self) -> None:
        scorer = RewardScorer()
        result = scorer.score(
            outcome=RewardOutcome.PREEMPTIVE_AVOIDANCE,
            repo="OmniNode-ai/omniintelligence",
        )
        assert result.repo == "OmniNode-ai/omniintelligence"

    def test_rule_id_stored(self) -> None:
        scorer = RewardScorer()
        result = scorer.score(
            outcome=RewardOutcome.PREEMPTIVE_AVOIDANCE,
            rule_id="ruff:E501",
        )
        assert result.rule_id == "ruff:E501"

    def test_scored_at_is_utc(self) -> None:
        scorer = RewardScorer()
        result = scorer.score(outcome=RewardOutcome.MANUAL_RESOLUTION)
        assert result.scored_at.tzinfo is not None

    def test_custom_signal_id_preserved(self) -> None:
        scorer = RewardScorer()
        pid = uuid.uuid4()
        result = scorer.score(
            outcome=RewardOutcome.REPEATED_VIOLATION,
            signal_id=pid,
        )
        assert result.signal_id == pid


# ---------------------------------------------------------------------------
# RewardScorer: score_batch
# ---------------------------------------------------------------------------


class TestRewardScorerBatch:
    def test_batch_scores_all_events(self) -> None:
        scorer = RewardScorer()
        events = [
            {"outcome": RewardOutcome.PREEMPTIVE_AVOIDANCE, "rule_id": "ruff:E501"},
            {"outcome": "codemod_fix", "rule_id": "mypy:return-value"},
            {"outcome": RewardOutcome.REPEATED_VIOLATION, "rule_id": "ruff:E501"},
        ]
        results = scorer.score_batch(events)
        assert len(results) == 3

    def test_batch_skips_invalid_outcomes(self) -> None:
        scorer = RewardScorer()
        events = [
            {"outcome": RewardOutcome.MANUAL_RESOLUTION},
            {"outcome": "invalid_outcome"},
        ]
        results = scorer.score_batch(events)
        assert len(results) == 1

    def test_batch_string_outcome_parsed(self) -> None:
        scorer = RewardScorer()
        results = scorer.score_batch([{"outcome": "preemptive_avoidance"}])
        assert len(results) == 1
        assert results[0].reward_value == 1.0

    def test_batch_empty_returns_empty(self) -> None:
        scorer = RewardScorer()
        results = scorer.score_batch([])
        assert results == []


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: paired finding rate
# ---------------------------------------------------------------------------


class TestPairedFindingRate:
    def test_all_confirmed_rate_is_one(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [_finding(has_confirmed_pair=True) for _ in range(5)]
        snap = calc.compute(findings, [])
        assert snap.paired_finding_rate == 1.0

    def test_no_confirmed_rate_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [_finding(has_confirmed_pair=False) for _ in range(5)]
        snap = calc.compute(findings, [])
        assert snap.paired_finding_rate == 0.0

    def test_half_confirmed_rate_is_half(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [_finding(has_confirmed_pair=True) for _ in range(5)] + [
            _finding(has_confirmed_pair=False) for _ in range(5)
        ]
        snap = calc.compute(findings, [])
        assert snap.paired_finding_rate == pytest.approx(0.5, abs=1e-6)

    def test_empty_findings_rate_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        snap = calc.compute([], [])
        assert snap.paired_finding_rate == 0.0


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: avg confidence
# ---------------------------------------------------------------------------


class TestAvgConfidence:
    def test_avg_confidence_correct(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [
            _finding(confidence_score=0.80),
            _finding(confidence_score=0.90),
        ]
        snap = calc.compute(findings, [])
        assert snap.avg_confidence_score == pytest.approx(0.85, abs=1e-6)

    def test_no_pairs_avg_confidence_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [_finding(has_confirmed_pair=False)]
        snap = calc.compute(findings, [])
        assert snap.avg_confidence_score == 0.0


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: p50 resolution
# ---------------------------------------------------------------------------


class TestP50Resolution:
    def test_p50_resolution_correct(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [
            _finding(resolved_seconds_after=100.0),
            _finding(resolved_seconds_after=200.0),
            _finding(resolved_seconds_after=300.0),
        ]
        snap = calc.compute(findings, [])
        assert snap.p50_resolution_seconds == pytest.approx(200.0, abs=1.0)

    def test_unresolved_findings_excluded_from_p50(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [
            _finding(resolved_seconds_after=100.0),
            _finding(resolved_seconds_after=None),  # unresolved
        ]
        snap = calc.compute(findings, [])
        assert snap.p50_resolution_seconds == pytest.approx(100.0, abs=1.0)

    def test_no_resolved_p50_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [_finding(resolved_seconds_after=None)]
        snap = calc.compute(findings, [])
        assert snap.p50_resolution_seconds == 0.0


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: reintroduction rate
# ---------------------------------------------------------------------------


class TestReintroductionRate:
    def test_reintroduction_rate_correct(self) -> None:
        calc = PairingMetricsCalculator()
        snap = calc.compute([], [], promoted_patterns=10, reintroduced_patterns=2)
        assert snap.reintroduction_rate == pytest.approx(0.2, abs=1e-6)

    def test_no_promotions_rate_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        snap = calc.compute([], [], promoted_patterns=0, reintroduced_patterns=0)
        assert snap.reintroduction_rate == 0.0


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: autofix pct
# ---------------------------------------------------------------------------


class TestAutofixPct:
    def test_autofix_pct_correct(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [
            _finding(tool_autofix=True),
            _finding(tool_autofix=True),
            _finding(tool_autofix=False),
        ]
        snap = calc.compute(findings, [])
        assert snap.autofix_pct == pytest.approx(2 / 3, abs=1e-6)

    def test_no_pairs_autofix_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        snap = calc.compute([_finding(has_confirmed_pair=False)], [])
        assert snap.autofix_pct == 0.0


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: preemptive avoidance rate
# ---------------------------------------------------------------------------


class TestPreemptiveAvoidanceRate:
    def test_avoidance_rate_correct(self) -> None:
        calc = PairingMetricsCalculator()
        injections = [
            _injection(had_avoidance=True),
            _injection(had_avoidance=True),
            _injection(had_avoidance=False),
        ]
        snap = calc.compute([], injections)
        assert snap.preemptive_avoidance_rate == pytest.approx(2 / 3, abs=1e-6)

    def test_no_injections_avoidance_rate_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        snap = calc.compute([], [])
        assert snap.preemptive_avoidance_rate == 0.0


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: repo filtering
# ---------------------------------------------------------------------------


class TestRepoFiltering:
    def test_filters_to_requested_repo(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [
            _finding(repo="OmniNode-ai/omniintelligence", has_confirmed_pair=True),
            _finding(repo="OmniNode-ai/other-repo", has_confirmed_pair=False),
        ]
        snap = calc.compute(findings, [], repo="OmniNode-ai/omniintelligence")
        assert snap.total_findings == 1
        assert snap.paired_finding_rate == 1.0

    def test_all_repos_no_filter(self) -> None:
        calc = PairingMetricsCalculator()
        findings = [
            _finding(repo="OmniNode-ai/omniintelligence"),
            _finding(repo="OmniNode-ai/other-repo"),
        ]
        snap = calc.compute(findings, [], repo="__all__")
        assert snap.total_findings == 2


# ---------------------------------------------------------------------------
# PairingMetricsCalculator: cumulative reward
# ---------------------------------------------------------------------------


class TestCumulativeReward:
    def test_cumulative_reward_all(self) -> None:
        calc = PairingMetricsCalculator()
        scorer = RewardScorer()
        results = [
            scorer.score(outcome=RewardOutcome.PREEMPTIVE_AVOIDANCE),  # +1.0
            scorer.score(outcome=RewardOutcome.CODEMOD_FIX),  # +0.8
            scorer.score(outcome=RewardOutcome.REPEATED_VIOLATION),  # -2.0
        ]
        total = calc.cumulative_reward(results)
        assert total == pytest.approx(-0.2, abs=1e-6)

    def test_cumulative_reward_filtered_by_rule(self) -> None:
        calc = PairingMetricsCalculator()
        scorer = RewardScorer()
        results = [
            scorer.score(
                outcome=RewardOutcome.PREEMPTIVE_AVOIDANCE, rule_id="ruff:E501"
            ),
            scorer.score(
                outcome=RewardOutcome.REPEATED_VIOLATION, rule_id="mypy:return-value"
            ),
        ]
        total = calc.cumulative_reward(results, rule_id="ruff:E501")
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_cumulative_reward_no_matches_is_zero(self) -> None:
        calc = PairingMetricsCalculator()
        total = calc.cumulative_reward([], agent_id="nobody")
        assert total == 0.0
