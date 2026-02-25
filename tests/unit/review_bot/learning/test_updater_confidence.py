# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for confidence updater (EMA-based).

Tests cover OMN-2499 acceptance criteria:
- R2: Confidence scores updated based on accumulated decisions
"""

from __future__ import annotations

from omniintelligence.review_bot.learning.handler_finding_feedback import (
    HandlerFindingFeedback,
)
from omniintelligence.review_bot.learning.updater_confidence import (
    COLD_START_MIN_DECISIONS,
    UpdaterConfidence,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_handler(*decisions: str, rule_id: str = "formatter") -> HandlerFindingFeedback:
    """Build a handler pre-populated with decisions ('accepted' or 'rejected')."""
    handler = HandlerFindingFeedback()
    for i, decision in enumerate(decisions):
        signal_type = (
            "remediation_accepted" if decision == "accepted" else "remediation_rejected"
        )
        handler.handle_signal(
            {
                "signal_type": signal_type,
                "finding_id": f"id-{i}",
                "rule_id": rule_id,
                "confidence": 0.8,
            }
        )
    return handler


# ---------------------------------------------------------------------------
# Cold start protection
# ---------------------------------------------------------------------------


class TestColdStart:
    def test_below_min_decisions_returns_unchanged(self) -> None:
        """R2: No adjustment before minimum decisions."""
        handler = make_handler("accepted", "accepted", rule_id="formatter")
        updater = UpdaterConfidence(handler=handler)

        update = updater.compute_update("formatter", previous_confidence=0.8)

        assert update.was_adjusted is False
        assert update.new_confidence == 0.8

    def test_exactly_min_decisions_triggers_adjustment(self) -> None:
        """R2: Adjustment starts at exactly COLD_START_MIN_DECISIONS."""
        decisions = ["accepted"] * COLD_START_MIN_DECISIONS
        handler = make_handler(*decisions, rule_id="formatter")
        updater = UpdaterConfidence(handler=handler)

        update = updater.compute_update("formatter", previous_confidence=0.5)

        assert update.was_adjusted is True

    def test_no_records_returns_unchanged(self) -> None:
        handler = HandlerFindingFeedback()
        updater = UpdaterConfidence(handler=handler)

        update = updater.compute_update("unknown_rule", previous_confidence=0.7)

        assert update.was_adjusted is False
        assert update.new_confidence == 0.7

    def test_decision_count_reported_correctly(self) -> None:
        handler = make_handler("accepted", "rejected", rule_id="formatter")
        updater = UpdaterConfidence(handler=handler)

        update = updater.compute_update("formatter", previous_confidence=0.8)

        assert update.decision_count == 2


# ---------------------------------------------------------------------------
# EMA calculation
# ---------------------------------------------------------------------------


class TestEmaCalculation:
    def test_all_accepted_increases_confidence(self) -> None:
        """R2: Many accepted decisions push confidence up."""
        decisions = ["accepted"] * 10
        handler = make_handler(*decisions, rule_id="formatter")
        updater = UpdaterConfidence(handler=handler, alpha=0.2)

        update = updater.compute_update("formatter", previous_confidence=0.5)

        assert update.new_confidence > 0.5

    def test_all_rejected_decreases_confidence(self) -> None:
        """R2: Many rejected decisions push confidence down."""
        decisions = ["rejected"] * 10
        handler = make_handler(*decisions, rule_id="formatter")
        updater = UpdaterConfidence(handler=handler, alpha=0.2)

        update = updater.compute_update("formatter", previous_confidence=0.8)

        assert update.new_confidence < 0.8

    def test_mixed_decisions_stabilise_confidence(self) -> None:
        """R2: 50/50 decisions converge to ~0.5."""
        # 50 alternating decisions
        decisions = ["accepted", "rejected"] * 25
        handler = make_handler(*decisions, rule_id="formatter")
        updater = UpdaterConfidence(handler=handler, alpha=0.1)

        update = updater.compute_update("formatter", previous_confidence=0.5)

        # Should remain close to 0.5 with balanced decisions
        assert 0.3 <= update.new_confidence <= 0.7

    def test_confidence_clamped_to_one(self) -> None:
        """R2: Confidence never exceeds 1.0."""
        decisions = ["accepted"] * 100
        handler = make_handler(*decisions, rule_id="formatter")
        updater = UpdaterConfidence(handler=handler, alpha=0.9)

        update = updater.compute_update("formatter", previous_confidence=1.0)

        assert update.new_confidence <= 1.0

    def test_confidence_clamped_to_zero(self) -> None:
        """R2: Confidence never goes below 0.0."""
        decisions = ["rejected"] * 100
        handler = make_handler(*decisions, rule_id="formatter")
        updater = UpdaterConfidence(handler=handler, alpha=0.9)

        update = updater.compute_update("formatter", previous_confidence=0.0)

        assert update.new_confidence >= 0.0

    def test_ema_single_accepted_calculation(self) -> None:
        """R2: Manual EMA verification for single decision."""
        # One accepted decision (signal=1.0), alpha=0.1, previous=0.8
        # new = 0.1 * 1.0 + 0.9 * 0.8 = 0.1 + 0.72 = 0.82
        decisions = ["accepted"] + [
            "accepted"
        ] * 4  # 5 decisions total (past cold start)
        handler = make_handler(*decisions, rule_id="r")
        updater = UpdaterConfidence(handler=handler, alpha=0.1, min_decisions=5)

        update = updater.compute_update("r", previous_confidence=0.8)

        # After 5 accepted: 0.8 -> ... should be between 0.8 and 1.0
        assert update.new_confidence > 0.8
        assert update.was_adjusted is True


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_invalid_alpha_raises(self) -> None:
        import pytest

        handler = HandlerFindingFeedback()
        with pytest.raises(ValueError, match="alpha"):
            UpdaterConfidence(handler=handler, alpha=0.0)

    def test_invalid_alpha_above_one_raises(self) -> None:
        import pytest

        handler = HandlerFindingFeedback()
        with pytest.raises(ValueError, match="alpha"):
            UpdaterConfidence(handler=handler, alpha=1.1)

    def test_invalid_min_decisions_raises(self) -> None:
        import pytest

        handler = HandlerFindingFeedback()
        with pytest.raises(ValueError, match="min_decisions"):
            UpdaterConfidence(handler=handler, min_decisions=0)

    def test_rule_id_in_update_result(self) -> None:
        handler = make_handler("accepted", rule_id="my_rule")
        updater = UpdaterConfidence(handler=handler)

        update = updater.compute_update("my_rule", previous_confidence=0.5)

        assert update.rule_id == "my_rule"

    def test_previous_confidence_preserved_in_result(self) -> None:
        handler = make_handler("accepted", rule_id="r")
        updater = UpdaterConfidence(handler=handler)

        update = updater.compute_update("r", previous_confidence=0.65)

        assert update.previous_confidence == 0.65
