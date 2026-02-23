"""Unit tests for ModelReviewScore.

Tests cover OMN-2495 acceptance criteria R2:
- Fields: score (0-100), policy_version, finding_count_by_severity, category_breakdown
- from_findings() is deterministic: same inputs -> same score
- Blocker findings cap score at <= 50
- Zero blockers required for score > 80
- frozen=True
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_score import ModelReviewScore
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity


def make_finding(
    rule_id: str = "test-rule",
    severity: ReviewSeverity = ReviewSeverity.WARNING,
    confidence: float = 0.8,
    file_path: str = "src/test.py",
) -> ModelReviewFinding:
    return ModelReviewFinding(
        rule_id=rule_id,
        severity=severity,
        confidence=confidence,
        rationale="Test rationale",
        suggested_fix="Test fix",
        file_path=file_path,
    )


class TestModelReviewScoreFields:
    def test_score_field_range(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        assert 0 <= score.score <= 100

    def test_policy_version_field(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        assert score.policy_version == "1.0"

    def test_finding_count_by_severity_field(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        assert isinstance(score.finding_count_by_severity, dict)
        assert ReviewSeverity.BLOCKER.value in score.finding_count_by_severity
        assert ReviewSeverity.WARNING.value in score.finding_count_by_severity
        assert ReviewSeverity.INFO.value in score.finding_count_by_severity

    def test_category_breakdown_field(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        assert isinstance(score.category_breakdown, dict)

    def test_score_is_frozen(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        with pytest.raises(ValidationError):
            score.score = 50  # type: ignore[misc]

    def test_score_range_validated_ge_0(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewScore(
                score=-1,
                policy_version="1.0",
                finding_count_by_severity={},
                category_breakdown={},
            )

    def test_score_range_validated_le_100(self) -> None:
        with pytest.raises(ValidationError):
            ModelReviewScore(
                score=101,
                policy_version="1.0",
                finding_count_by_severity={},
                category_breakdown={},
            )


class TestModelReviewScoreDeterminism:
    def test_empty_findings_always_100(self) -> None:
        s1 = ModelReviewScore.from_findings([], policy_version="1.0")
        s2 = ModelReviewScore.from_findings([], policy_version="1.0")
        assert s1.score == s2.score == 100

    def test_same_findings_same_score(self) -> None:
        findings = [
            make_finding(rule_id="rule-a", severity=ReviewSeverity.BLOCKER),
            make_finding(rule_id="rule-b", severity=ReviewSeverity.WARNING),
        ]
        s1 = ModelReviewScore.from_findings(findings, policy_version="1.0")
        s2 = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert s1.score == s2.score
        assert s1.finding_count_by_severity == s2.finding_count_by_severity
        assert s1.category_breakdown == s2.category_breakdown

    def test_order_independent(self) -> None:
        """Same findings in different order should produce same score."""
        f1 = make_finding(rule_id="rule-a", severity=ReviewSeverity.BLOCKER)
        f2 = make_finding(rule_id="rule-b", severity=ReviewSeverity.WARNING)
        s1 = ModelReviewScore.from_findings([f1, f2], policy_version="1.0")
        s2 = ModelReviewScore.from_findings([f2, f1], policy_version="1.0")
        assert s1.score == s2.score

    def test_policy_version_embedded(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="2.5")
        assert score.policy_version == "2.5"


class TestModelReviewScoreBlockerRules:
    def test_blockers_cap_at_50(self) -> None:
        """R2: Blocker findings cap score at <= 50."""
        findings = [make_finding(severity=ReviewSeverity.BLOCKER)]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score <= 50

    def test_many_blockers_still_capped_at_50(self) -> None:
        """Even with many blockers, score never exceeds 50."""
        findings = [
            make_finding(rule_id=f"rule-{i}", severity=ReviewSeverity.BLOCKER)
            for i in range(3)
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score <= 50

    def test_zero_blockers_allows_score_above_80(self) -> None:
        """R2: Zero blockers required for score > 80."""
        # No findings at all -> score is 100
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        assert score.score > 80

    def test_only_warnings_can_exceed_80(self) -> None:
        """A single warning deducts 5; score = 95 > 80 with no blockers."""
        findings = [make_finding(severity=ReviewSeverity.WARNING)]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score > 80
        assert score.has_blockers is False

    def test_one_blocker_prevents_score_above_80(self) -> None:
        """Any blocker finding means score <= 50 <= 80."""
        findings = [make_finding(severity=ReviewSeverity.BLOCKER)]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score <= 50

    def test_floor_at_zero_with_many_blockers(self) -> None:
        """Score never goes below 0."""
        findings = [
            make_finding(rule_id=f"rule-{i}", severity=ReviewSeverity.BLOCKER)
            for i in range(10)  # 10 blockers * 25 = 250 deductions
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score >= 0


class TestModelReviewScoreFromFindings:
    def test_only_info_findings(self) -> None:
        findings = [
            make_finding(rule_id="todo", severity=ReviewSeverity.INFO),
            make_finding(rule_id="long-line", severity=ReviewSeverity.INFO),
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score == 98  # 100 - 2*1
        assert score.finding_count_by_severity[ReviewSeverity.INFO.value] == 2
        assert score.finding_count_by_severity[ReviewSeverity.BLOCKER.value] == 0
        assert not score.has_blockers

    def test_only_warning_findings(self) -> None:
        findings = [
            make_finding(rule_id="no-print", severity=ReviewSeverity.WARNING),
            make_finding(rule_id="no-fixme", severity=ReviewSeverity.WARNING),
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score == 90  # 100 - 2*5
        assert score.finding_count_by_severity[ReviewSeverity.WARNING.value] == 2

    def test_mixed_findings(self) -> None:
        findings = [
            make_finding(rule_id="blocker-rule", severity=ReviewSeverity.BLOCKER),
            make_finding(rule_id="warning-rule", severity=ReviewSeverity.WARNING),
            make_finding(rule_id="info-rule", severity=ReviewSeverity.INFO),
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        # Raw: 100 - 25 - 5 - 1 = 69, but capped at 50 due to blocker
        assert score.score == 50  # capped at 50 because raw 69 > 50
        assert score.has_blockers

    def test_category_breakdown_aggregated(self) -> None:
        findings = [
            make_finding(rule_id="no-bare-except", severity=ReviewSeverity.WARNING),
            make_finding(rule_id="no-bare-except", severity=ReviewSeverity.WARNING),
            make_finding(rule_id="no-print", severity=ReviewSeverity.INFO),
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.category_breakdown["no-bare-except"] == 2
        assert score.category_breakdown["no-print"] == 1

    def test_has_blockers_false_no_blockers(self) -> None:
        findings = [make_finding(severity=ReviewSeverity.WARNING)]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.has_blockers is False

    def test_has_blockers_true_with_blocker(self) -> None:
        findings = [make_finding(severity=ReviewSeverity.BLOCKER)]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.has_blockers is True

    def test_total_findings_count(self) -> None:
        findings = [
            make_finding(rule_id="rule-1", severity=ReviewSeverity.BLOCKER),
            make_finding(rule_id="rule-2", severity=ReviewSeverity.WARNING),
            make_finding(rule_id="rule-3", severity=ReviewSeverity.INFO),
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.total_findings == 3

    def test_total_findings_empty(self) -> None:
        score = ModelReviewScore.from_findings([], policy_version="1.0")
        assert score.total_findings == 0

    def test_blocker_raw_below_50_not_further_reduced(self) -> None:
        """If raw score (after deductions) < 50 and there are blockers, use raw."""
        # 3 blockers: raw = 100 - 75 = 25, which is < 50, so cap doesn't apply
        findings = [
            make_finding(rule_id=f"rule-{i}", severity=ReviewSeverity.BLOCKER)
            for i in range(3)
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        # raw = 100 - 75 = 25, capped at min(25, 50) = 25
        assert score.score == 25


class TestReviewSeverityEnum:
    def test_blocker_value(self) -> None:
        assert ReviewSeverity.BLOCKER == "BLOCKER"

    def test_warning_value(self) -> None:
        assert ReviewSeverity.WARNING == "WARNING"

    def test_info_value(self) -> None:
        assert ReviewSeverity.INFO == "INFO"

    def test_follows_onex_casing(self) -> None:
        """R3: ReviewSeverity follows ONEX casing conventions (UPPER_CASE)."""
        for severity in ReviewSeverity:
            assert severity.value == severity.value.upper(), (
                f"ReviewSeverity.{severity.name} value should be UPPER_CASE: {severity.value!r}"
            )
