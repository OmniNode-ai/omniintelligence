# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ReviewScore Pydantic model for Code Intelligence Review Bot.

ReviewScore is a deterministic aggregate of review findings. Given the same
list of ReviewFinding objects and policy_version, ReviewScore.from_findings()
always returns the same score.

Score rules:
- Blocker findings cap the score at <= 50
- Zero blockers required for score > 80
- Score is computed from finding counts by severity

OMN-2495: Implement ReviewFinding and ReviewScore Pydantic models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity

# Score thresholds
_MAX_SCORE_WITH_BLOCKERS = 50

# Per-finding deductions
_BLOCKER_DEDUCTION = 25
_WARNING_DEDUCTION = 5
_INFO_DEDUCTION = 1


class ModelReviewScore(BaseModel):
    """A deterministic aggregate score derived from a set of ReviewFindings.

    ReviewScore is always computed from findings — it is never hand-crafted.
    Use the factory method :meth:`from_findings` to create instances.

    Score range: 0-100 (higher is better, 100 = no findings).

    Score rules (deterministic):
    - Start at 100
    - Deduct 25 per BLOCKER finding
    - Deduct 5 per WARNING finding
    - Deduct 1 per INFO finding
    - Floor at 0 (never negative)
    - Hard cap: if any BLOCKER findings exist, score is capped at <= 50
    - Score > 80 requires zero BLOCKER findings

    Attributes:
        score: Overall score in range 0-100.
        policy_version: Version of the policy used to produce this score.
        correlation_id: Optional trace correlation ID for end-to-end tracking.
        finding_count_by_severity: Mapping of severity name to finding count.
        category_breakdown: Mapping of rule_id to finding count for that rule.

    Example::

        findings = [
            ModelReviewFinding(
                rule_id="no-bare-except",
                severity=ReviewSeverity.BLOCKER,
                confidence=0.9,
                rationale="...",
                suggested_fix="...",
                file_path="src/handler.py",
            )
        ]
        score = ModelReviewScore.from_findings(findings, policy_version="1.0")
        assert score.score <= 50  # blocker present
    """

    score: int = Field(
        ...,
        description="Overall review score in range 0-100",
        ge=0,
        le=100,
    )
    policy_version: str = Field(
        ...,
        description="Policy version used to produce this score",
        min_length=1,
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional trace correlation ID for end-to-end tracking",
    )
    finding_count_by_severity: dict[str, int] = Field(
        ...,
        description="Mapping of severity name to finding count",
    )
    category_breakdown: dict[str, int] = Field(
        ...,
        description="Mapping of rule_id to finding count for that rule",
    )

    @classmethod
    def from_findings(
        cls,
        findings: list[ModelReviewFinding],
        policy_version: str,
        correlation_id: str | None = None,
    ) -> ModelReviewScore:
        """Deterministically compute a ReviewScore from a list of findings.

        Given the same inputs, this method always returns the same score.
        The score is computed as:
        1. Start at 100
        2. Deduct per-severity points for each finding
        3. Floor at 0
        4. Apply blocker cap: if any BLOCKER findings, cap at 50

        Args:
            findings: List of review findings to score.
            policy_version: Policy version string to embed in score.
            correlation_id: Optional correlation ID for end-to-end tracing.

        Returns:
            A frozen ModelReviewScore instance.
        """
        # Count findings by severity
        severity_counts: dict[str, int] = {
            ReviewSeverity.BLOCKER.value: 0,
            ReviewSeverity.WARNING.value: 0,
            ReviewSeverity.INFO.value: 0,
        }
        category_counts: dict[str, int] = {}

        for finding in findings:
            severity_counts[finding.severity.value] += 1
            category_counts[finding.rule_id] = (
                category_counts.get(finding.rule_id, 0) + 1
            )

        # Compute score
        blocker_count = severity_counts[ReviewSeverity.BLOCKER.value]
        warning_count = severity_counts[ReviewSeverity.WARNING.value]
        info_count = severity_counts[ReviewSeverity.INFO.value]

        raw_score = (
            100
            - (blocker_count * _BLOCKER_DEDUCTION)
            - (warning_count * _WARNING_DEDUCTION)
            - (info_count * _INFO_DEDUCTION)
        )

        # Floor at 0
        raw_score = max(0, raw_score)

        # Cap at 50 if any blockers
        if blocker_count > 0:
            raw_score = min(raw_score, _MAX_SCORE_WITH_BLOCKERS)

        return cls(
            score=raw_score,
            policy_version=policy_version,
            correlation_id=correlation_id,
            finding_count_by_severity=severity_counts,
            category_breakdown=category_counts,
        )

    @property
    def has_blockers(self) -> bool:
        """Return True if any BLOCKER findings are present."""
        return self.finding_count_by_severity.get(ReviewSeverity.BLOCKER.value, 0) > 0

    @property
    def total_findings(self) -> int:
        """Return total number of findings across all severities."""
        return sum(self.finding_count_by_severity.values())

    model_config = {"frozen": True, "extra": "ignore", "from_attributes": True}


__all__ = ["ModelReviewScore"]
