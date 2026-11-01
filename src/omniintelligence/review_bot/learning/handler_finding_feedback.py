# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Feedback handler for the Code Intelligence Review Bot learning loop.

Consumes remediation_accepted / remediation_rejected signals and stores
positive/negative finding records in OmniMemory for per-rule aggregation.

OMN-2499: Implement OmniMemory learning loop.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from omniintelligence.models.review.model_finding_feedback_signal import (
    ModelFindingFeedbackSignal,
)


@dataclass
class FeedbackRecord:
    """A single acceptance or rejection decision for a finding.

    Attributes:
        finding_id: UUID string of the finding.
        rule_id: Rule that produced the finding.
        decision: "accepted" if the remediation was merged; "rejected" if closed.
        confidence: Confidence at time the finding was created.
    """

    finding_id: str
    rule_id: str
    decision: Literal["accepted", "rejected"]
    confidence: float


class HandlerFindingFeedback:
    """Processes remediation signals and stores feedback records.

    Records are stored in an in-memory registry keyed by rule_id.
    In production, this would emit to Kafka / persist in OmniMemory.
    The in-memory store is useful for testing and local feedback cycles.

    Usage::

        handler = HandlerFindingFeedback()
        handler.handle(signal)
        records = handler.get_records_for_rule("formatter")
    """

    def __init__(self) -> None:
        # rule_id -> list of FeedbackRecord
        self._records: dict[str, list[FeedbackRecord]] = {}

    def handle(self, request: ModelFindingFeedbackSignal) -> FeedbackRecord | None:
        """Process a remediation signal and store a feedback record.

        Accepts the signal fields emitted by RemediationPipeline:
            {
                "signal_type": "remediation_accepted" | "remediation_rejected",
                "finding_id": str,
                "rule_id": str,
                "confidence": float,
            }

        Args:
            request: Signal from RemediationPipeline.

        Returns:
            The stored FeedbackRecord, or None if the signal is malformed.
        """
        signal_type = request.signal_type
        if signal_type not in ("remediation_accepted", "remediation_rejected"):
            print(
                f"WARNING: Unknown signal type: {signal_type!r}",
                file=sys.stderr,
            )
            return None

        finding_id = request.finding_id
        rule_id = request.rule_id
        confidence = request.confidence

        if not isinstance(finding_id, str) or not isinstance(rule_id, str):
            print("WARNING: Signal missing finding_id or rule_id", file=sys.stderr)
            return None

        if not isinstance(confidence, float | int):
            print("WARNING: Signal missing numeric confidence", file=sys.stderr)
            return None

        decision: Literal["accepted", "rejected"] = (
            "accepted" if signal_type == "remediation_accepted" else "rejected"
        )

        record = FeedbackRecord(
            finding_id=str(finding_id),
            rule_id=str(rule_id),
            decision=decision,
            confidence=float(confidence),
        )

        if rule_id not in self._records:
            self._records[rule_id] = []
        self._records[rule_id].append(record)

        return record

    def get_records_for_rule(self, rule_id: str) -> list[FeedbackRecord]:
        """Return all feedback records for a given rule.

        Args:
            rule_id: The rule identifier.

        Returns:
            List of FeedbackRecord (may be empty).
        """
        return list(self._records.get(rule_id, []))

    def get_all_rule_ids(self) -> list[str]:
        """Return all rule IDs that have at least one feedback record.

        Returns:
            Sorted list of rule IDs.
        """
        return sorted(self._records.keys())


__all__ = ["FeedbackRecord", "HandlerFindingFeedback"]
