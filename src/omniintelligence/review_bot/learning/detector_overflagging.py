# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Over-flagging detector for the Code Intelligence Review Bot.

Detects rules with high rejection rates and marks them for automatic
severity downgrade (BLOCKER -> WARNING). Suppression is advisory;
humans can override via policy YAML.

OMN-2499: Implement OmniMemory learning loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omniintelligence.review_bot.learning.handler_finding_feedback import (
    FeedbackRecord,
    HandlerFindingFeedback,
)

# Default window of recent decisions to evaluate.
OVERFLAGGING_WINDOW: int = 20

# Default rejection rate threshold above which a rule is over-flagging.
OVERFLAGGING_THRESHOLD: float = 0.7


@dataclass
class RuleDecisionHistory:
    """Aggregated decision history for a single rule.

    Attributes:
        rule_id: The rule identifier.
        total_decisions: Total decisions evaluated (up to window size).
        accepted_count: Number of accepted decisions.
        rejected_count: Number of rejected decisions.
        rejection_rate: Fraction of decisions that were rejections.
    """

    rule_id: str
    total_decisions: int
    accepted_count: int
    rejected_count: int
    rejection_rate: float


@dataclass
class OverflaggingResult:
    """Result of over-flagging detection across all rules.

    Attributes:
        overflagging_rule_ids: Rule IDs whose rejection rate exceeds threshold.
        histories: Per-rule decision history for all rules evaluated.
    """

    overflagging_rule_ids: list[str] = field(default_factory=list)
    histories: list[RuleDecisionHistory] = field(default_factory=list)

    @property
    def has_overflagging(self) -> bool:
        """True if any rule is over-flagging."""
        return len(self.overflagging_rule_ids) > 0


class DetectorOverflagging:
    """Detects rules with abnormally high rejection rates.

    A rule is considered over-flagging when:
    - It has at least ``window`` recent decisions (or all available if fewer)
    - More than ``threshold`` fraction of those decisions were rejections

    Over-flagging rules should have their findings downgraded from
    BLOCKER -> WARNING automatically. This is advisory; the human
    can re-enable via policy YAML.

    Usage::

        handler = HandlerFindingFeedback()
        # ... populate with feedback records ...

        detector = DetectorOverflagging(handler=handler)
        result = detector.detect()
        if result.has_overflagging:
            print(f"Over-flagging rules: {result.overflagging_rule_ids}")
    """

    def __init__(
        self,
        handler: HandlerFindingFeedback,
        window: int = OVERFLAGGING_WINDOW,
        threshold: float = OVERFLAGGING_THRESHOLD,
    ) -> None:
        """Initialise the detector.

        Args:
            handler: Feedback handler providing decision history.
            window: Number of recent decisions to evaluate per rule.
            threshold: Rejection rate above which a rule is over-flagging.
        """
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        if not 0 < threshold <= 1:
            raise ValueError(f"threshold must be in (0, 1], got {threshold}")

        self._handler = handler
        self._window = window
        self._threshold = threshold

    def detect(self) -> OverflaggingResult:
        """Detect over-flagging rules across all rules with feedback.

        Returns:
            OverflaggingResult with over-flagging rule IDs and per-rule history.
        """
        result = OverflaggingResult()

        for rule_id in self._handler.get_all_rule_ids():
            history = self._build_history(rule_id)
            result.histories.append(history)

            if history.rejection_rate > self._threshold:
                result.overflagging_rule_ids.append(rule_id)

        result.overflagging_rule_ids.sort()
        return result

    def is_overflagging(self, rule_id: str) -> bool:
        """Check whether a specific rule is currently over-flagging.

        Args:
            rule_id: The rule to check.

        Returns:
            True if the rule's rejection rate exceeds the threshold.
        """
        records = self._handler.get_records_for_rule(rule_id)
        if not records:
            return False
        history = self._compute_history(rule_id, records)
        return history.rejection_rate > self._threshold

    def _build_history(self, rule_id: str) -> RuleDecisionHistory:
        records = self._handler.get_records_for_rule(rule_id)
        return self._compute_history(rule_id, records)

    def _compute_history(
        self,
        rule_id: str,
        records: list[FeedbackRecord],
    ) -> RuleDecisionHistory:
        # Use only the most recent `window` decisions
        recent = records[-self._window :] if len(records) > self._window else records
        total = len(recent)
        if total == 0:
            return RuleDecisionHistory(
                rule_id=rule_id,
                total_decisions=0,
                accepted_count=0,
                rejected_count=0,
                rejection_rate=0.0,
            )

        rejected = sum(1 for r in recent if r.decision == "rejected")
        accepted = total - rejected
        rejection_rate = rejected / total

        return RuleDecisionHistory(
            rule_id=rule_id,
            total_decisions=total,
            accepted_count=accepted,
            rejected_count=rejected,
            rejection_rate=rejection_rate,
        )


__all__ = [
    "OVERFLAGGING_THRESHOLD",
    "OVERFLAGGING_WINDOW",
    "DetectorOverflagging",
    "OverflaggingResult",
    "RuleDecisionHistory",
]
