# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Confidence updater using exponential moving average (EMA).

Updates rule confidence scores based on accumulated acceptance/rejection
decisions. Requires a minimum number of decisions before adjusting
confidence (cold start protection).

OMN-2499: Implement OmniMemory learning loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from omniintelligence.review_bot.learning.handler_finding_feedback import (
    FeedbackRecord,
    HandlerFindingFeedback,
)

# Default EMA smoothing factor (alpha). Higher = faster adaptation.
DEFAULT_EMA_ALPHA: float = 0.1

# Minimum decisions required before confidence adjustment begins.
COLD_START_MIN_DECISIONS: int = 5


@dataclass
class ConfidenceUpdate:
    """Result of a confidence update calculation.

    Attributes:
        rule_id: Rule whose confidence was updated.
        previous_confidence: Confidence before this update.
        new_confidence: Confidence after applying EMA.
        decision_count: Total decisions used for the update.
        was_adjusted: False if cold start protection prevented adjustment.
    """

    rule_id: str
    previous_confidence: float
    new_confidence: float
    decision_count: int
    was_adjusted: bool


class UpdaterConfidence:
    """Calculates updated rule confidence using exponential moving average.

    EMA formula:
        new_confidence = alpha * signal + (1 - alpha) * previous_confidence

    where signal = 1.0 for accepted, 0.0 for rejected.

    Cold start protection: If fewer than ``min_decisions`` records exist
    for a rule, confidence is returned unchanged (``was_adjusted=False``).

    Usage::

        handler = HandlerFindingFeedback()
        # ... populate with feedback records ...

        updater = UpdaterConfidence(handler=handler)
        update = updater.compute_update("formatter", previous_confidence=0.8)
        print(update.new_confidence)
    """

    def __init__(
        self,
        handler: HandlerFindingFeedback,
        alpha: float = DEFAULT_EMA_ALPHA,
        min_decisions: int = COLD_START_MIN_DECISIONS,
    ) -> None:
        """Initialise the updater.

        Args:
            handler: Feedback handler providing decision history.
            alpha: EMA smoothing factor (0 < alpha <= 1).
            min_decisions: Minimum decisions before adjusting confidence.
        """
        if not 0 < alpha <= 1:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        if min_decisions < 1:
            raise ValueError(f"min_decisions must be >= 1, got {min_decisions}")

        self._handler = handler
        self._alpha = alpha
        self._min_decisions = min_decisions

    def compute_update(
        self,
        rule_id: str,
        previous_confidence: float,
    ) -> ConfidenceUpdate:
        """Compute a new confidence for ``rule_id`` using EMA.

        Args:
            rule_id: The rule to update.
            previous_confidence: Current confidence value (0.0-1.0).

        Returns:
            ConfidenceUpdate with the new confidence and metadata.
        """
        records = self._handler.get_records_for_rule(rule_id)
        decision_count = len(records)

        if decision_count < self._min_decisions:
            return ConfidenceUpdate(
                rule_id=rule_id,
                previous_confidence=previous_confidence,
                new_confidence=previous_confidence,
                decision_count=decision_count,
                was_adjusted=False,
            )

        new_confidence = self._apply_ema(records, previous_confidence)
        # Clamp to [0.0, 1.0]
        new_confidence = max(0.0, min(1.0, new_confidence))

        return ConfidenceUpdate(
            rule_id=rule_id,
            previous_confidence=previous_confidence,
            new_confidence=new_confidence,
            decision_count=decision_count,
            was_adjusted=True,
        )

    def _apply_ema(
        self,
        records: list[FeedbackRecord],
        initial: float,
    ) -> float:
        """Apply EMA over all historical records in chronological order.

        Args:
            records: Feedback records in insertion order.
            initial: Starting confidence value.

        Returns:
            Final EMA-smoothed confidence.
        """
        confidence = initial
        for record in records:
            signal = 1.0 if record.decision == "accepted" else 0.0
            confidence = self._alpha * signal + (1 - self._alpha) * confidence
        return confidence


__all__ = [
    "COLD_START_MIN_DECISIONS",
    "DEFAULT_EMA_ALPHA",
    "ConfidenceUpdate",
    "UpdaterConfidence",
]
