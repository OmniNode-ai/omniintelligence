"""Unit tests for over-flagging detector.

Tests cover OMN-2499 acceptance criteria:
- R1: Finding acceptance/rejection stored in OmniMemory
- R3: Over-flagging rules automatically suppressed
"""

from __future__ import annotations

from omniintelligence.review_bot.learning.detector_overflagging import (
    OVERFLAGGING_THRESHOLD,
    OVERFLAGGING_WINDOW,
    DetectorOverflagging,
)
from omniintelligence.review_bot.learning.handler_finding_feedback import (
    HandlerFindingFeedback,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_handler(*decisions: str, rule_id: str = "formatter") -> HandlerFindingFeedback:
    """Build a handler pre-populated with decisions."""
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
# R1: Feedback storage
# ---------------------------------------------------------------------------


class TestFeedbackStorage:
    def test_accepted_signal_stored(self) -> None:
        """R1: remediation_accepted signal creates an 'accepted' record."""
        handler = HandlerFindingFeedback()
        record = handler.handle_signal(
            {
                "signal_type": "remediation_accepted",
                "finding_id": "abc-123",
                "rule_id": "formatter",
                "confidence": 0.9,
            }
        )

        assert record is not None
        assert record.decision == "accepted"
        assert record.rule_id == "formatter"

    def test_rejected_signal_stored(self) -> None:
        """R1: remediation_rejected signal creates a 'rejected' record."""
        handler = HandlerFindingFeedback()
        record = handler.handle_signal(
            {
                "signal_type": "remediation_rejected",
                "finding_id": "def-456",
                "rule_id": "import_sort",
                "confidence": 0.7,
            }
        )

        assert record is not None
        assert record.decision == "rejected"

    def test_records_keyed_by_rule_id(self) -> None:
        """R1: Records retrievable by rule_id for per-rule aggregation."""
        handler = make_handler("accepted", "rejected", "accepted", rule_id="formatter")

        records = handler.get_records_for_rule("formatter")

        assert len(records) == 3
        assert all(r.rule_id == "formatter" for r in records)

    def test_different_rules_isolated(self) -> None:
        """R1: Records for different rules are isolated."""
        handler = HandlerFindingFeedback()
        handler.handle_signal(
            {
                "signal_type": "remediation_accepted",
                "finding_id": "1",
                "rule_id": "formatter",
                "confidence": 0.8,
            }
        )
        handler.handle_signal(
            {
                "signal_type": "remediation_rejected",
                "finding_id": "2",
                "rule_id": "import_sort",
                "confidence": 0.6,
            }
        )

        assert len(handler.get_records_for_rule("formatter")) == 1
        assert len(handler.get_records_for_rule("import_sort")) == 1

    def test_unknown_signal_type_returns_none(self) -> None:
        handler = HandlerFindingFeedback()
        result = handler.handle_signal(
            {
                "signal_type": "unknown",
                "rule_id": "r",
                "finding_id": "1",
                "confidence": 0.5,
            }
        )
        assert result is None

    def test_missing_finding_id_returns_none(self) -> None:
        handler = HandlerFindingFeedback()
        result = handler.handle_signal(
            {"signal_type": "remediation_accepted", "rule_id": "r", "confidence": 0.5}
        )
        assert result is None

    def test_get_all_rule_ids(self) -> None:
        handler = HandlerFindingFeedback()
        handler.handle_signal(
            {
                "signal_type": "remediation_accepted",
                "finding_id": "1",
                "rule_id": "b",
                "confidence": 0.8,
            }
        )
        handler.handle_signal(
            {
                "signal_type": "remediation_accepted",
                "finding_id": "2",
                "rule_id": "a",
                "confidence": 0.8,
            }
        )

        rule_ids = handler.get_all_rule_ids()

        assert rule_ids == ["a", "b"]  # sorted


# ---------------------------------------------------------------------------
# R3: Over-flagging detection
# ---------------------------------------------------------------------------


class TestOverflaggingDetection:
    def test_high_rejection_rate_flagged(self) -> None:
        """R3: Rule with >70% rejection rate flagged as over-flagging."""
        # 8 rejected, 2 accepted = 80% rejection rate
        decisions = ["rejected"] * 8 + ["accepted"] * 2
        handler = make_handler(*decisions, rule_id="bad_rule")
        detector = DetectorOverflagging(handler=handler)

        result = detector.detect()

        assert "bad_rule" in result.overflagging_rule_ids

    def test_low_rejection_rate_not_flagged(self) -> None:
        """R3: Rule with <=70% rejection rate is not flagged."""
        # 3 rejected, 7 accepted = 30% rejection rate
        decisions = ["rejected"] * 3 + ["accepted"] * 7
        handler = make_handler(*decisions, rule_id="good_rule")
        detector = DetectorOverflagging(handler=handler)

        result = detector.detect()

        assert "good_rule" not in result.overflagging_rule_ids

    def test_exactly_at_threshold_not_flagged(self) -> None:
        """R3: Rule at exactly threshold is not flagged (> not >=)."""
        # 7 rejected, 3 accepted = 70% rejection rate = exactly threshold
        decisions = ["rejected"] * 7 + ["accepted"] * 3
        handler = make_handler(*decisions, rule_id="edge_rule")
        detector = DetectorOverflagging(handler=handler, threshold=0.7)

        result = detector.detect()

        # At exactly 0.7, rejection_rate > threshold is False
        assert "edge_rule" not in result.overflagging_rule_ids

    def test_window_limits_decisions_evaluated(self) -> None:
        """R3: Only the most recent `window` decisions count."""
        # First 10 are accepted, last 5 are rejected (window=5)
        # With window=5: only the 5 rejections count -> 100% rejection -> flagged
        decisions = ["accepted"] * 10 + ["rejected"] * 5
        handler = make_handler(*decisions, rule_id="windowed_rule")
        detector = DetectorOverflagging(handler=handler, window=5)

        result = detector.detect()

        assert "windowed_rule" in result.overflagging_rule_ids

    def test_window_prevents_old_rejections_from_flagging(self) -> None:
        """R3: Old rejections outside window don't trigger flag."""
        # First 20 are rejected, last 10 are accepted (window=10)
        # With window=10: only 10 acceptances -> 0% rejection rate -> not flagged
        decisions = ["rejected"] * 20 + ["accepted"] * 10
        handler = make_handler(*decisions, rule_id="improved_rule")
        detector = DetectorOverflagging(handler=handler, window=10)

        result = detector.detect()

        assert "improved_rule" not in result.overflagging_rule_ids

    def test_no_decisions_not_flagged(self) -> None:
        handler = HandlerFindingFeedback()
        detector = DetectorOverflagging(handler=handler)

        result = detector.detect()

        assert result.overflagging_rule_ids == []
        assert result.has_overflagging is False

    def test_multiple_rules_detected(self) -> None:
        """R3: Multiple over-flagging rules all reported."""
        handler = HandlerFindingFeedback()
        for rule in ["rule_a", "rule_b"]:
            for i in range(8):
                handler.handle_signal(
                    {
                        "signal_type": "remediation_rejected",
                        "finding_id": f"{rule}-{i}",
                        "rule_id": rule,
                        "confidence": 0.7,
                    }
                )
            for i in range(2):
                handler.handle_signal(
                    {
                        "signal_type": "remediation_accepted",
                        "finding_id": f"{rule}-acc-{i}",
                        "rule_id": rule,
                        "confidence": 0.7,
                    }
                )

        detector = DetectorOverflagging(handler=handler)
        result = detector.detect()

        assert "rule_a" in result.overflagging_rule_ids
        assert "rule_b" in result.overflagging_rule_ids

    def test_is_overflagging_method(self) -> None:
        """R3: is_overflagging() convenience method works."""
        decisions = ["rejected"] * 9 + ["accepted"] * 1
        handler = make_handler(*decisions, rule_id="bad")
        detector = DetectorOverflagging(handler=handler)

        assert detector.is_overflagging("bad") is True
        assert detector.is_overflagging("unknown_rule") is False

    def test_history_includes_counts(self) -> None:
        """R3: Detection result includes per-rule history."""
        decisions = ["rejected"] * 6 + ["accepted"] * 4
        handler = make_handler(*decisions, rule_id="r")
        detector = DetectorOverflagging(handler=handler)

        result = detector.detect()

        history = next(h for h in result.histories if h.rule_id == "r")
        assert history.rejected_count == 6
        assert history.accepted_count == 4
        assert history.total_decisions == 10
        assert abs(history.rejection_rate - 0.6) < 1e-6

    def test_overflagging_rule_ids_sorted(self) -> None:
        """R3: over-flagging rule IDs are returned sorted."""
        handler = HandlerFindingFeedback()
        for rule in ["z_rule", "a_rule", "m_rule"]:
            for i in range(10):
                handler.handle_signal(
                    {
                        "signal_type": "remediation_rejected",
                        "finding_id": f"{rule}-{i}",
                        "rule_id": rule,
                        "confidence": 0.8,
                    }
                )

        detector = DetectorOverflagging(handler=handler)
        result = detector.detect()

        assert result.overflagging_rule_ids == sorted(result.overflagging_rule_ids)


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


class TestDetectorConfiguration:
    def test_invalid_window_raises(self) -> None:
        import pytest

        handler = HandlerFindingFeedback()
        with pytest.raises(ValueError, match="window"):
            DetectorOverflagging(handler=handler, window=0)

    def test_invalid_threshold_zero_raises(self) -> None:
        import pytest

        handler = HandlerFindingFeedback()
        with pytest.raises(ValueError, match="threshold"):
            DetectorOverflagging(handler=handler, threshold=0.0)

    def test_invalid_threshold_above_one_raises(self) -> None:
        import pytest

        handler = HandlerFindingFeedback()
        with pytest.raises(ValueError, match="threshold"):
            DetectorOverflagging(handler=handler, threshold=1.1)

    def test_default_window_constant(self) -> None:
        assert OVERFLAGGING_WINDOW == 20

    def test_default_threshold_constant(self) -> None:
        assert OVERFLAGGING_THRESHOLD == 0.7
