# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for replay verification logic.

Tests all replay scenarios including match, mismatch, empty snapshot,
tie-breaker resolution, malformed snapshot handling, and correlation_id
threading.

Ticket: OMN-2467 - V2: Replay verification test
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from omniintelligence.decision_store.models import (
    DecisionRecordRow,
    DecisionScoreRow,
)
from omniintelligence.decision_store.replay import (
    ReplayResult,
    replay_decision,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    decision_id: str = "replay-001",
    selected_candidate: str = "claude-3-opus",
    scoring_breakdown: list[DecisionScoreRow] | None = None,
    tie_breaker: str | None = None,
    agent_rationale: str | None = None,
    reproducibility_snapshot: dict[str, str] | None = None,
) -> DecisionRecordRow:
    """Build a DecisionRecordRow for replay testing."""
    ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
    if scoring_breakdown is None:
        scoring_breakdown = [
            DecisionScoreRow(
                candidate="claude-3-opus",
                score=0.92,
                breakdown={"quality": 0.95, "cost": 0.89},
            ),
            DecisionScoreRow(
                candidate="gpt-4o",
                score=0.85,
                breakdown={"quality": 0.88, "cost": 0.82},
            ),
        ]
    if reproducibility_snapshot is None:
        # Build snapshot from scoring_breakdown
        snapshot_scoring = [
            {"candidate": s.candidate, "score": s.score} for s in scoring_breakdown
        ]
        reproducibility_snapshot = {
            "model_registry_version": "v2.1.0",
            "scoring_breakdown": json.dumps(snapshot_scoring),
            "selected_candidate": selected_candidate,
        }
        if tie_breaker:
            reproducibility_snapshot["tie_breaker"] = tie_breaker

    return DecisionRecordRow(
        decision_id=decision_id,
        decision_type="model_select",
        timestamp=ts,
        candidates_considered=[s.candidate for s in scoring_breakdown],
        constraints_applied={"cost": "budget limit"},
        scoring_breakdown=scoring_breakdown,
        tie_breaker=tie_breaker,
        selected_candidate=selected_candidate,
        agent_rationale=agent_rationale,
        reproducibility_snapshot=reproducibility_snapshot,
        stored_at=ts,
    )


# ---------------------------------------------------------------------------
# Match Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReplayMatch:
    """Tests where replay correctly re-derives the original decision."""

    def test_replay_simple_match(self) -> None:
        record = _make_record(
            selected_candidate="claude-3-opus",
        )
        result = replay_decision(record)

        assert isinstance(result, ReplayResult)
        assert result.match is True
        assert result.original_candidate == "claude-3-opus"
        assert result.replayed_candidate == "claude-3-opus"
        assert result.reason == ""

    def test_replay_match_with_second_highest_candidate(self) -> None:
        scoring = [
            DecisionScoreRow(candidate="gpt-4o", score=0.95, breakdown={}),
            DecisionScoreRow(candidate="claude-3-opus", score=0.88, breakdown={}),
        ]
        record = _make_record(
            selected_candidate="gpt-4o",
            scoring_breakdown=scoring,
        )
        result = replay_decision(record)

        assert result.match is True
        assert result.replayed_candidate == "gpt-4o"

    def test_replay_with_correlation_id(self) -> None:
        record = _make_record(selected_candidate="claude-3-opus")
        result = replay_decision(record, correlation_id="test-trace-id")

        assert result.match is True

    def test_replay_str_representation(self) -> None:
        record = _make_record(selected_candidate="claude-3-opus")
        result = replay_decision(record)

        assert "MATCH" in str(result)
        assert "claude-3-opus" in str(result)


# ---------------------------------------------------------------------------
# Mismatch Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReplayMismatch:
    """Tests where replay produces a different winner than recorded."""

    def test_replay_mismatch_when_snapshot_has_different_scores(self) -> None:
        # Original record says claude-3-opus won
        # But snapshot scoring says gpt-4o has higher score
        snapshot_scoring = [
            {"candidate": "gpt-4o", "score": 0.99},
            {"candidate": "claude-3-opus", "score": 0.80},
        ]
        record = _make_record(
            selected_candidate="claude-3-opus",
            reproducibility_snapshot={
                "model_registry_version": "v2.0.0",
                "scoring_breakdown": json.dumps(snapshot_scoring),
                "selected_candidate": "claude-3-opus",
            },
        )
        result = replay_decision(record)

        assert result.match is False
        assert result.replayed_candidate == "gpt-4o"
        assert result.original_candidate == "claude-3-opus"
        assert "Provenance integrity check FAILED" in result.reason

    def test_replay_mismatch_with_correlation_id(self) -> None:
        snapshot_scoring = [{"candidate": "gpt-4o", "score": 0.99}]
        record = _make_record(
            selected_candidate="claude-3-opus",
            reproducibility_snapshot={
                "scoring_breakdown": json.dumps(snapshot_scoring),
            },
        )
        result = replay_decision(record, correlation_id="mismatch-trace-001")

        assert result.match is False

    def test_replay_mismatch_str_representation(self) -> None:
        snapshot_scoring = [{"candidate": "gpt-4o", "score": 0.99}]
        record = _make_record(
            selected_candidate="claude-3-opus",
            reproducibility_snapshot={
                "scoring_breakdown": json.dumps(snapshot_scoring),
            },
        )
        result = replay_decision(record)

        assert "MISMATCH" in str(result)


# ---------------------------------------------------------------------------
# Tie-breaker Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReplayTieBreaker:
    """Tests for tie-breaker resolution during replay."""

    def test_replay_tie_alphabetical(self) -> None:
        snapshot_scoring = [
            {"candidate": "model-b", "score": 0.90},
            {"candidate": "model-a", "score": 0.90},
        ]
        record = _make_record(
            selected_candidate="model-a",
            tie_breaker="alphabetical",
            reproducibility_snapshot={
                "scoring_breakdown": json.dumps(snapshot_scoring),
                "tie_breaker": "alphabetical",
                "selected_candidate": "model-a",
            },
        )
        result = replay_decision(record)

        assert result.match is True
        assert result.replayed_candidate == "model-a"  # alphabetically first

    def test_replay_tie_first(self) -> None:
        snapshot_scoring = [
            {"candidate": "model-x", "score": 0.75},
            {"candidate": "model-y", "score": 0.75},
        ]
        record = _make_record(
            selected_candidate="model-x",
            tie_breaker="first",
            reproducibility_snapshot={
                "scoring_breakdown": json.dumps(snapshot_scoring),
                "tie_breaker": "first",
                "selected_candidate": "model-x",
            },
        )
        result = replay_decision(record)

        assert result.match is True
        assert result.replayed_candidate == "model-x"

    def test_replay_tie_no_tiebreaker_defaults_to_first(self) -> None:
        snapshot_scoring = [
            {"candidate": "z-model", "score": 0.80},
            {"candidate": "a-model", "score": 0.80},
        ]
        record = _make_record(
            selected_candidate="z-model",
            tie_breaker=None,
            reproducibility_snapshot={
                "scoring_breakdown": json.dumps(snapshot_scoring),
                "selected_candidate": "z-model",
            },
        )
        # Without tie-breaker, first in list wins
        result = replay_decision(record)
        assert result.replayed_candidate == "z-model"


# ---------------------------------------------------------------------------
# Error / Edge Case Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReplayErrorCases:
    """Tests for malformed snapshots and edge cases."""

    def test_replay_empty_snapshot_falls_back_to_record_scoring(self) -> None:
        scoring = [
            DecisionScoreRow(candidate="claude-3-opus", score=0.95, breakdown={}),
            DecisionScoreRow(candidate="gpt-4o", score=0.80, breakdown={}),
        ]
        record = _make_record(
            selected_candidate="claude-3-opus",
            scoring_breakdown=scoring,
            reproducibility_snapshot={},  # empty snapshot
        )
        result = replay_decision(record)

        # Should fall back to record's own scoring_breakdown
        assert result.match is True
        assert result.replayed_candidate == "claude-3-opus"

    def test_replay_empty_snapshot_and_empty_scoring_returns_mismatch(self) -> None:
        scoring: list[DecisionScoreRow] = []
        record = _make_record(
            selected_candidate="claude-3-opus",
            scoring_breakdown=scoring,
            reproducibility_snapshot={},
        )
        result = replay_decision(record)

        assert result.match is False
        assert result.replayed_candidate is None
        assert "Cannot replay" in result.reason

    def test_replay_malformed_json_in_snapshot(self) -> None:
        record = _make_record(
            selected_candidate="claude-3-opus",
            reproducibility_snapshot={
                "scoring_breakdown": "not valid json {{{",
            },
        )
        result = replay_decision(record)

        # Falls back: tries to parse JSON, fails, then uses record scoring
        # Since record has scoring, it should still resolve
        assert isinstance(result, ReplayResult)

    def test_replay_snapshot_empty_scoring_array(self) -> None:
        record = _make_record(
            selected_candidate="claude-3-opus",
            reproducibility_snapshot={
                "scoring_breakdown": json.dumps([]),
            },
        )
        # Empty snapshot scoring → fall back to record's scoring
        result = replay_decision(record)
        assert isinstance(result, ReplayResult)

    def test_replay_result_is_frozen(self) -> None:
        record = _make_record(selected_candidate="claude-3-opus")
        result = replay_decision(record)

        with pytest.raises((AttributeError, TypeError)):
            result.match = False  # type: ignore[misc]

    def test_replay_error_with_correlation_id(self) -> None:
        scoring: list[DecisionScoreRow] = []
        record = _make_record(
            selected_candidate="claude-3-opus",
            scoring_breakdown=scoring,
            reproducibility_snapshot={},
        )
        result = replay_decision(record, correlation_id="error-trace-001")

        assert result.match is False
        assert result.replayed_candidate is None


# ---------------------------------------------------------------------------
# Consumer Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecisionRecordConsumer:
    """Tests for the Kafka consumer that writes to the repository."""

    def test_consumer_handles_valid_message(self) -> None:
        import json
        from datetime import UTC, datetime

        from omniintelligence.decision_store.consumer import DecisionRecordConsumer
        from omniintelligence.decision_store.repository import DecisionRecordRepository

        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        payload = {
            "decision_id": "msg-001",
            "decision_type": "model_select",
            "timestamp": datetime.now(UTC).isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": ["claude-3-opus", "gpt-4o"],
            "constraints_applied": {},
            "scoring_breakdown": [],
            "tie_breaker": None,
            "agent_rationale": None,
            "reproducibility_snapshot": {},
        }
        raw = json.dumps(payload).encode("utf-8")

        result = consumer.handle_message(raw)
        assert result is True
        assert repo.count() == 1

    def test_consumer_with_correlation_id(self) -> None:
        import json
        from datetime import UTC, datetime

        from omniintelligence.decision_store.consumer import DecisionRecordConsumer
        from omniintelligence.decision_store.repository import DecisionRecordRepository

        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        payload = {
            "decision_id": "msg-corr-001",
            "decision_type": "model_select",
            "timestamp": datetime.now(UTC).isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": [],
            "constraints_applied": {},
            "scoring_breakdown": [],
            "tie_breaker": None,
            "agent_rationale": None,
            "reproducibility_snapshot": {},
        }
        raw = json.dumps(payload).encode("utf-8")

        result = consumer.handle_message(raw, correlation_id="trace-001")
        assert result is True

    def test_consumer_idempotent_on_duplicate(self) -> None:
        import json
        from datetime import UTC, datetime

        from omniintelligence.decision_store.consumer import DecisionRecordConsumer
        from omniintelligence.decision_store.repository import DecisionRecordRepository

        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        payload = {
            "decision_id": "dup-msg-001",
            "decision_type": "model_select",
            "timestamp": datetime.now(UTC).isoformat(),
            "selected_candidate": "claude-3-opus",
            "candidates_considered": [],
            "constraints_applied": {},
            "scoring_breakdown": [],
            "tie_breaker": None,
            "agent_rationale": None,
            "reproducibility_snapshot": {},
        }
        raw = json.dumps(payload).encode("utf-8")

        consumer.handle_message(raw)
        result = consumer.handle_message(raw)

        assert result is False
        assert repo.count() == 1

    def test_consumer_skips_malformed_json(self) -> None:
        from omniintelligence.decision_store.consumer import DecisionRecordConsumer
        from omniintelligence.decision_store.repository import DecisionRecordRepository

        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        result = consumer.handle_message(b"not valid json")
        assert result is False
        assert repo.count() == 0

    def test_consumer_skips_missing_required_fields(self) -> None:
        import json

        from omniintelligence.decision_store.consumer import DecisionRecordConsumer
        from omniintelligence.decision_store.repository import DecisionRecordRepository

        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        # Missing decision_type and timestamp
        payload = {"decision_id": "incomplete-001"}
        raw = json.dumps(payload).encode("utf-8")

        result = consumer.handle_message(raw)
        assert result is False
        assert repo.count() == 0

    def test_consumer_topic_uses_decision_topics_enum(self) -> None:
        from omniintelligence.decision_store.consumer import DecisionRecordConsumer
        from omniintelligence.decision_store.repository import DecisionRecordRepository
        from omniintelligence.decision_store.topics import DecisionTopics

        consumer = DecisionRecordConsumer(repository=DecisionRecordRepository())
        assert consumer.topic == DecisionTopics.DECISION_RECORDED
        assert "decision-recorded" in consumer.topic
