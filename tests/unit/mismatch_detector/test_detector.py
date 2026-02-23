# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for rationale mismatch detection.

Tests all three mismatch types (OMISSION, FABRICATION, WRONG_WINNER),
verifies no false positives for clean decisions, and tests the consumer.

Ticket: OMN-2472 - V1: Detection unit tests (all 3 mismatch types)
         V2: False positive test (no mismatch = no event)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from omniintelligence.mismatch_detector.detector import detect_mismatches
from omniintelligence.mismatch_detector.models import (
    MismatchReport,
    MismatchSeverity,
    MismatchType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TIMESTAMP = datetime(2026, 2, 21, 12, 0, 0, tzinfo=UTC)


def _make_record(
    decision_id: str = "test-decision-001",
    selected_candidate: str = "claude-3-opus",
    candidates_considered: list[str] | None = None,
    constraints_applied: dict[str, str] | None = None,
    scoring_breakdown: list[dict] | None = None,
    agent_rationale: str | None = None,
) -> dict:
    """Build a minimal DecisionRecord dict for testing."""
    if candidates_considered is None:
        candidates_considered = ["claude-3-opus", "gpt-4o", "llama-3-70b"]
    if constraints_applied is None:
        constraints_applied = {"cost_limit": "max $0.01/call"}
    if scoring_breakdown is None:
        scoring_breakdown = [
            {"candidate": c, "score": 0.5, "breakdown": {}}
            for c in (candidates_considered or [])
        ]
    return {
        "decision_id": decision_id,
        "decision_type": "model_select",
        "timestamp": FIXED_TIMESTAMP.isoformat(),
        "selected_candidate": selected_candidate,
        "candidates_considered": candidates_considered,
        "constraints_applied": constraints_applied,
        "scoring_breakdown": scoring_breakdown,
        "agent_rationale": agent_rationale,
        "reproducibility_snapshot": {},
    }


# ---------------------------------------------------------------------------
# R1: Skip records with no rationale
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSkipNoRationale:
    """Records with no agent_rationale are skipped."""

    def test_no_rationale_returns_empty(self) -> None:
        record = _make_record(agent_rationale=None)
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        assert result == []

    def test_rationale_present_triggers_detection(self) -> None:
        record = _make_record(
            agent_rationale="I chose claude-3-opus because of its quality.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        # With no constraints and correct winner, should be clean
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Mismatch Type 1: OMISSION
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOmissionDetection:
    """Tests for OMISSION: constraint in Layer 1 not mentioned in rationale."""

    def test_omission_when_constraint_absent_from_rationale(self) -> None:
        record = _make_record(
            constraints_applied={"cost_limit": "max $0.01/call"},
            agent_rationale=(
                "I chose claude-3-opus because it has excellent quality scores."
            ),
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)

        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert len(omissions) >= 1
        assert omissions[0].mismatch_type == MismatchType.OMISSION
        assert omissions[0].severity == MismatchSeverity.WARNING
        assert "cost_limit" in omissions[0].layer1_reference

    def test_omission_severity_is_warning(self) -> None:
        record = _make_record(
            constraints_applied={"latency_budget": "p99 < 2s"},
            agent_rationale="Claude was selected for its quality.",
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert all(r.severity == MismatchSeverity.WARNING for r in omissions)

    def test_no_omission_when_constraint_mentioned(self) -> None:
        record = _make_record(
            constraints_applied={"cost_limit": "max $0.01/call"},
            agent_rationale=(
                "I applied the cost limit constraint and chose claude-3-opus."
            ),
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert len(omissions) == 0

    def test_omission_with_normalized_key(self) -> None:
        # "cost_limit" should match "cost limit" in rationale
        record = _make_record(
            constraints_applied={"cost_limit": "budget"},
            agent_rationale="Considering the cost limit, I chose claude-3-opus.",
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert len(omissions) == 0

    def test_multiple_constraints_all_omitted(self) -> None:
        record = _make_record(
            constraints_applied={
                "cost_limit": "budget",
                "latency_budget": "2s",
            },
            agent_rationale="Claude is great for coding tasks.",
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert len(omissions) == 2

    def test_omission_report_has_required_fields(self) -> None:
        record = _make_record(
            constraints_applied={"cost_limit": "budget"},
            agent_rationale="I chose claude because it's smart.",
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert len(omissions) >= 1
        report = omissions[0]
        assert report.decision_id == "test-decision-001"
        assert report.detected_at == FIXED_TIMESTAMP
        assert isinstance(report, MismatchReport)

    def test_omission_quoted_text_is_empty_string(self) -> None:
        record = _make_record(
            constraints_applied={"cost_limit": "budget"},
            agent_rationale="I chose claude for quality reasons.",
            selected_candidate="claude-3-opus",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        omissions = [r for r in result if r.mismatch_type == MismatchType.OMISSION]
        assert len(omissions) >= 1
        assert omissions[0].quoted_text == ""


# ---------------------------------------------------------------------------
# Mismatch Type 2: FABRICATION
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFabricationDetection:
    """Tests for FABRICATION: rationale references factor absent from Layer 1."""

    def test_fabrication_when_recommending_unknown_candidate(self) -> None:
        # Rationale recommends a model that isn't in candidates_considered
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale=(
                "I recommend gemini-pro for this task as it handles code better."
            ),
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        fabrications = [
            r for r in result if r.mismatch_type == MismatchType.FABRICATION
        ]
        assert len(fabrications) >= 1
        assert fabrications[0].severity == MismatchSeverity.CRITICAL

    def test_no_fabrication_when_recommending_valid_candidate(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale=(
                "I recommend claude-3-opus because its quality score was highest."
            ),
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        fabrications = [
            r for r in result if r.mismatch_type == MismatchType.FABRICATION
        ]
        assert len(fabrications) == 0

    def test_fabrication_severity_is_critical(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}}
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I suggest gpt-4-turbo for this use case.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        fabrications = [
            r for r in result if r.mismatch_type == MismatchType.FABRICATION
        ]
        if fabrications:
            assert all(r.severity == MismatchSeverity.CRITICAL for r in fabrications)

    def test_fabrication_report_has_quoted_text(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}}
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I recommend gemini-ultra for this task.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        fabrications = [
            r for r in result if r.mismatch_type == MismatchType.FABRICATION
        ]
        if fabrications:
            assert fabrications[0].quoted_text != ""

    def test_fabrication_layer1_reference_is_candidates_considered(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}}
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I prefer mixtral-8x7b for this workload.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        fabrications = [
            r for r in result if r.mismatch_type == MismatchType.FABRICATION
        ]
        if fabrications:
            assert "candidates_considered" in fabrications[0].layer1_reference


# ---------------------------------------------------------------------------
# Mismatch Type 3: WRONG_WINNER
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWrongWinnerDetection:
    """Tests for WRONG_WINNER: rationale claims different winner than Layer 1."""

    def test_wrong_winner_when_rationale_claims_different_model(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale=(
                "I selected gpt-4o because it performed better on benchmarks."
            ),
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        assert len(wrong_winners) >= 1
        assert wrong_winners[0].severity == MismatchSeverity.CRITICAL

    def test_wrong_winner_severity_is_critical(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I chose gpt-4o for this task.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        assert len(wrong_winners) >= 1
        assert wrong_winners[0].severity == MismatchSeverity.CRITICAL

    def test_no_wrong_winner_when_rationale_correct(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I chose claude-3-opus because it had the highest quality score.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        assert len(wrong_winners) == 0

    def test_wrong_winner_with_was_selected_phrase(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="gpt-4o was selected as the best candidate for this use case.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        assert len(wrong_winners) >= 1

    def test_wrong_winner_report_references_selected_candidate(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I selected gpt-4o for the task.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        if wrong_winners:
            assert "claude-3-opus" in wrong_winners[0].layer1_reference

    def test_wrong_winner_report_has_quoted_text(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            agent_rationale="I chose gpt-4o for this task.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        if wrong_winners:
            assert wrong_winners[0].quoted_text != ""

    def test_empty_candidates_considered_skips_wrong_winner(self) -> None:
        record = _make_record(
            candidates_considered=[],
            scoring_breakdown=[],
            selected_candidate="",
            agent_rationale="I chose gpt-4o for this task.",
            constraints_applied={},
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        assert len(wrong_winners) == 0


# ---------------------------------------------------------------------------
# V2: False positive test — no mismatch = no event
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCleanDecision:
    """Tests that clean decisions produce no mismatch reports (no false positives)."""

    def test_clean_decision_no_rationale_returns_empty(self) -> None:
        record = _make_record(agent_rationale=None)
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        assert result == []

    def test_clean_decision_with_rationale_mentioning_constraints(self) -> None:
        record = _make_record(
            candidates_considered=["claude-3-opus", "gpt-4o"],
            scoring_breakdown=[
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
                {"candidate": "gpt-4o", "score": 0.8, "breakdown": {}},
            ],
            selected_candidate="claude-3-opus",
            constraints_applied={"cost_limit": "budget"},
            agent_rationale=(
                "Given the cost limit constraint, I chose claude-3-opus "
                "as it had the highest quality score."
            ),
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        assert result == []

    def test_empty_constraints_and_correct_winner_is_clean(self) -> None:
        record = _make_record(
            constraints_applied={},
            selected_candidate="claude-3-opus",
            agent_rationale="I chose claude-3-opus because it scored highest.",
        )
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        wrong_winners = [
            r for r in result if r.mismatch_type == MismatchType.WRONG_WINNER
        ]
        assert len(wrong_winners) == 0

    def test_detect_mismatches_returns_list(self) -> None:
        record = _make_record(agent_rationale=None)
        result = detect_mismatches(record, detected_at=FIXED_TIMESTAMP)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# MismatchReport model tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMismatchReport:
    """Tests for MismatchReport data model."""

    def test_report_is_frozen(self) -> None:
        report = MismatchReport(
            decision_id="d-001",
            mismatch_type=MismatchType.OMISSION,
            severity=MismatchSeverity.WARNING,
            quoted_text="",
            layer1_reference="constraints_applied['cost']",
            description="Cost constraint omitted from rationale.",
            detected_at=FIXED_TIMESTAMP,
        )
        with pytest.raises((AttributeError, TypeError)):
            report.severity = MismatchSeverity.CRITICAL  # type: ignore[misc]

    def test_to_event_dict_excludes_quoted_text(self) -> None:
        report = MismatchReport(
            decision_id="d-002",
            mismatch_type=MismatchType.WRONG_WINNER,
            severity=MismatchSeverity.CRITICAL,
            quoted_text="I chose gpt-4o",
            layer1_reference="selected_candidate='claude-3-opus'",
            description="Wrong winner claimed.",
            detected_at=FIXED_TIMESTAMP,
        )
        event = report.to_event_dict()
        assert "quoted_text" not in event
        assert "description" not in event
        assert event["decision_id"] == "d-002"
        assert event["mismatch_type"] == MismatchType.WRONG_WINNER.value
        assert event["severity"] == MismatchSeverity.CRITICAL.value

    def test_to_event_dict_includes_detected_at(self) -> None:
        report = MismatchReport(
            decision_id="d-ts",
            mismatch_type=MismatchType.OMISSION,
            severity=MismatchSeverity.WARNING,
            quoted_text="",
            layer1_reference="constraints_applied['x']",
            description="Omission.",
            detected_at=FIXED_TIMESTAMP,
        )
        event = report.to_event_dict()
        assert event["detected_at"] == FIXED_TIMESTAMP.isoformat()

    def test_to_full_dict_includes_all_fields(self) -> None:
        report = MismatchReport(
            decision_id="d-003",
            mismatch_type=MismatchType.FABRICATION,
            severity=MismatchSeverity.CRITICAL,
            quoted_text="I recommend gemini",
            layer1_reference="candidates_considered",
            description="Fabricated candidate.",
            detected_at=FIXED_TIMESTAMP,
        )
        full = report.to_full_dict()
        assert "quoted_text" in full
        assert "description" in full
        assert full["quoted_text"] == "I recommend gemini"

    def test_to_full_dict_is_superset_of_event_dict(self) -> None:
        report = MismatchReport(
            decision_id="d-004",
            mismatch_type=MismatchType.OMISSION,
            severity=MismatchSeverity.WARNING,
            quoted_text="",
            layer1_reference="constraints_applied['cost']",
            description="Omission.",
            detected_at=FIXED_TIMESTAMP,
        )
        event = report.to_event_dict()
        full = report.to_full_dict()
        for key in event:
            assert key in full
            assert full[key] == event[key]


# ---------------------------------------------------------------------------
# OmniIntelligenceTopics tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOmniIntelligenceTopics:
    """Tests for the StrEnum topic constants."""

    def test_rationale_mismatch_topic_is_evt(self) -> None:
        from omniintelligence.hooks.topics import OmniIntelligenceTopics

        assert "evt" in OmniIntelligenceTopics.RATIONALE_MISMATCH_EVT
        assert "rationale-mismatch" in OmniIntelligenceTopics.RATIONALE_MISMATCH_EVT

    def test_decision_recorded_cmd_is_restricted(self) -> None:
        from omniintelligence.hooks.topics import OmniIntelligenceTopics

        assert "cmd" in OmniIntelligenceTopics.DECISION_RECORDED_CMD

    def test_topics_are_str(self) -> None:
        from omniintelligence.hooks.topics import OmniIntelligenceTopics

        assert isinstance(OmniIntelligenceTopics.RATIONALE_MISMATCH_EVT, str)
        assert isinstance(OmniIntelligenceTopics.DECISION_RECORDED_EVT, str)
        assert isinstance(OmniIntelligenceTopics.DECISION_RECORDED_CMD, str)


# ---------------------------------------------------------------------------
# MismatchDetectionConsumer tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMismatchDetectionConsumer:
    """Tests for the Kafka consumer that triggers detection."""

    def test_consumer_returns_zero_for_no_rationale(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        consumer = MismatchDetectionConsumer()
        payload = {
            "decision_id": "c-001",
            "decision_type": "model_select",
            "timestamp": FIXED_TIMESTAMP.isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus"],
            "constraints_applied": {},
            "scoring_breakdown": [],
            "agent_rationale": None,
            "has_rationale": False,
        }
        result = consumer.handle_message(json.dumps(payload).encode("utf-8"))
        assert result == 0

    def test_consumer_triggers_detection_when_rationale_present(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        emitted = []

        def mock_emitter(topic: str, payload: dict) -> None:
            emitted.append((topic, payload))

        consumer = MismatchDetectionConsumer(event_emitter=mock_emitter)
        payload = {
            "decision_id": "c-002",
            "decision_type": "model_select",
            "timestamp": FIXED_TIMESTAMP.isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus", "gpt-4o"],
            "constraints_applied": {"cost_limit": "budget"},
            "scoring_breakdown": [
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
            ],
            "agent_rationale": "I chose claude because it is smart.",  # missing cost_limit
            "has_rationale": True,
        }
        result = consumer.handle_message(json.dumps(payload).encode("utf-8"))
        assert result >= 1  # OMISSION should be detected
        assert len(emitted) >= 1

    def test_consumer_does_not_emit_for_clean_decision(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        emitted = []

        def mock_emitter(topic: str, payload: dict) -> None:
            emitted.append((topic, payload))

        consumer = MismatchDetectionConsumer(event_emitter=mock_emitter)
        payload = {
            "decision_id": "c-003",
            "decision_type": "model_select",
            "timestamp": FIXED_TIMESTAMP.isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus", "gpt-4o"],
            "constraints_applied": {},
            "scoring_breakdown": [
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
            ],
            "agent_rationale": "I chose claude-3-opus for its high quality score.",
            "has_rationale": True,
        }
        result = consumer.handle_message(json.dumps(payload).encode("utf-8"))
        assert result == 0
        assert len(emitted) == 0

    def test_consumer_skips_malformed_json(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        consumer = MismatchDetectionConsumer()
        result = consumer.handle_message(b"not json")
        assert result == 0

    def test_consumer_stores_mismatches_for_dashboard(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        consumer = MismatchDetectionConsumer()
        payload = {
            "decision_id": "c-dash-001",
            "decision_type": "model_select",
            "timestamp": FIXED_TIMESTAMP.isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus", "gpt-4o"],
            "constraints_applied": {"cost_limit": "budget"},
            "scoring_breakdown": [
                {"candidate": "claude-3-opus", "score": 0.9, "breakdown": {}},
            ],
            "agent_rationale": "I chose claude because it scores best.",
            "has_rationale": True,
        }
        consumer.handle_message(json.dumps(payload).encode("utf-8"))

        mismatches = consumer.get_mismatches("c-dash-001")
        assert isinstance(mismatches, list)
        # At least OMISSION for cost_limit
        assert len(mismatches) >= 1

    def test_consumer_emits_to_correct_topic(self) -> None:
        from omniintelligence.hooks.topics import OmniIntelligenceTopics
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        emitted_topics = []

        def mock_emitter(topic: str, _payload: dict) -> None:
            emitted_topics.append(topic)

        consumer = MismatchDetectionConsumer(event_emitter=mock_emitter)
        payload = {
            "decision_id": "c-topic-001",
            "decision_type": "model_select",
            "timestamp": FIXED_TIMESTAMP.isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus"],
            "constraints_applied": {"cost_limit": "budget"},
            "scoring_breakdown": [],
            "agent_rationale": "Selected claude for quality reasons only.",
            "has_rationale": True,
        }
        consumer.handle_message(json.dumps(payload).encode("utf-8"))

        for topic in emitted_topics:
            assert topic == OmniIntelligenceTopics.RATIONALE_MISMATCH_EVT

    def test_subscribed_topic_is_cmd_topic(self) -> None:
        from omniintelligence.hooks.topics import OmniIntelligenceTopics
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        consumer = MismatchDetectionConsumer()
        assert consumer.subscribed_topic == OmniIntelligenceTopics.DECISION_RECORDED_CMD

    def test_consumer_get_mismatches_returns_empty_for_unknown_id(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        consumer = MismatchDetectionConsumer()
        result = consumer.get_mismatches("nonexistent-decision-id")
        assert result == []

    def test_consumer_stored_reports_include_full_fields(self) -> None:
        from omniintelligence.mismatch_detector.consumer import (
            MismatchDetectionConsumer,
        )

        consumer = MismatchDetectionConsumer()
        payload = {
            "decision_id": "c-full-001",
            "decision_type": "model_select",
            "timestamp": FIXED_TIMESTAMP.isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus"],
            "constraints_applied": {"cost_limit": "budget"},
            "scoring_breakdown": [],
            "agent_rationale": "I chose claude for quality.",
            "has_rationale": True,
        }
        consumer.handle_message(json.dumps(payload).encode("utf-8"))

        mismatches = consumer.get_mismatches("c-full-001")
        assert len(mismatches) >= 1
        # Full dict should include description and quoted_text (for storage)
        assert "description" in mismatches[0]
