# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for DecisionRecordRepository.

Tests storage, idempotency, querying, pagination, layer separation,
and correlation_id threading.

Ticket: OMN-2467 - V1: Storage unit tests
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.decision_store.models import (
    DecisionRecordRow,
    DecisionScoreRow,
)
from omniintelligence.decision_store.protocols import ProtocolDecisionRecordRepository
from omniintelligence.decision_store.repository import (
    DecisionRecordRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    decision_id: str = "test-id-001",
    decision_type: str = "model_select",
    selected_candidate: str = "claude-3-opus",
    agent_rationale: str | None = None,
    stored_at_offset_seconds: int = 0,
) -> DecisionRecordRow:
    """Build a minimal DecisionRecordRow for testing."""
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return DecisionRecordRow(
        decision_id=decision_id,
        decision_type=decision_type,
        timestamp=base_time,
        candidates_considered=["claude-3-opus", "gpt-4o", "llama-3-70b"],
        constraints_applied={"cost_limit": "max $0.01/call"},
        scoring_breakdown=[
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
        ],
        tie_breaker=None,
        selected_candidate=selected_candidate,
        agent_rationale=agent_rationale,
        reproducibility_snapshot={
            "model_registry_version": "v2.1.0",
            "scoring_weights": '{"quality": 0.6, "cost": 0.4}',
            "selected_candidate": selected_candidate,
        },
        stored_at=base_time + timedelta(seconds=stored_at_offset_seconds),
    )


# ---------------------------------------------------------------------------
# Protocol compliance test
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProtocolCompliance:
    """Verify DecisionRecordRepository satisfies ProtocolDecisionRecordRepository."""

    def test_repository_satisfies_protocol(self) -> None:
        repo = DecisionRecordRepository()
        assert isinstance(repo, ProtocolDecisionRecordRepository)


# ---------------------------------------------------------------------------
# Store / Idempotency Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecisionRecordRepositoryStore:
    """Tests for store() and idempotency."""

    def test_store_returns_true_for_new_record(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record()
        result = repo.store(record)
        assert result is True

    def test_store_duplicate_returns_false(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(decision_id="dup-001")
        repo.store(record)
        result = repo.store(record)
        assert result is False

    def test_store_duplicate_does_not_overwrite(self) -> None:
        repo = DecisionRecordRepository()
        original = _make_record(
            decision_id="dup-002", selected_candidate="claude-3-opus"
        )
        repo.store(original)

        # Attempt to overwrite with different data using same ID
        duplicate = _make_record(decision_id="dup-002", selected_candidate="gpt-4o")
        repo.store(duplicate)

        retrieved = repo.get_record("dup-002")
        assert retrieved is not None
        assert retrieved["selected_candidate"] == "claude-3-opus"

    def test_store_with_correlation_id(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(decision_id="corr-001")
        result = repo.store(record, correlation_id="test-corr-id")
        assert result is True

    def test_store_duplicate_with_correlation_id(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(decision_id="corr-dup-001")
        repo.store(record, correlation_id="corr-1")
        result = repo.store(record, correlation_id="corr-2")
        assert result is False

    def test_count_increments_on_new_records(self) -> None:
        repo = DecisionRecordRepository()
        assert repo.count() == 0
        repo.store(_make_record(decision_id="c-001"))
        assert repo.count() == 1
        repo.store(_make_record(decision_id="c-002"))
        assert repo.count() == 2

    def test_count_unchanged_on_duplicate(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(decision_id="cnt-dup")
        repo.store(record)
        repo.store(record)
        assert repo.count() == 1


# ---------------------------------------------------------------------------
# get_record Tests (Layer Separation)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecisionRecordRepositoryGetRecord:
    """Tests for get_record() including Layer 1 / Layer 2 separation."""

    def test_get_record_returns_none_for_unknown_id(self) -> None:
        repo = DecisionRecordRepository()
        result = repo.get_record("nonexistent-id")
        assert result is None

    def test_get_record_layer1_only_by_default(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(agent_rationale="I chose claude because it's best")
        repo.store(record)

        result = repo.get_record(record.decision_id)
        assert result is not None
        assert "agent_rationale" not in result

    def test_get_record_layer1_explicit(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(agent_rationale="test rationale")
        repo.store(record)

        result = repo.get_record(record.decision_id, include_rationale=False)
        assert result is not None
        assert "agent_rationale" not in result

    def test_get_record_layer2_when_requested(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(agent_rationale="I chose claude for quality reasons")
        repo.store(record)

        result = repo.get_record(record.decision_id, include_rationale=True)
        assert result is not None
        assert "agent_rationale" in result
        assert result["agent_rationale"] == "I chose claude for quality reasons"

    def test_get_record_layer2_null_rationale(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(agent_rationale=None)
        repo.store(record)

        result = repo.get_record(record.decision_id, include_rationale=True)
        assert result is not None
        assert result["agent_rationale"] is None

    def test_get_record_with_correlation_id(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(decision_id="corr-get-001")
        repo.store(record)

        result = repo.get_record("corr-get-001", correlation_id="trace-123")
        assert result is not None

    def test_get_record_contains_expected_layer1_fields(self) -> None:
        repo = DecisionRecordRepository()
        record = _make_record(decision_id="fields-test")
        repo.store(record)

        result = repo.get_record("fields-test")
        assert result is not None
        for field_name in (
            "decision_id",
            "decision_type",
            "timestamp",
            "candidates_considered",
            "constraints_applied",
            "scoring_breakdown",
            "tie_breaker",
            "selected_candidate",
            "reproducibility_snapshot",
            "stored_at",
        ):
            assert field_name in result, f"Missing field: {field_name}"


# ---------------------------------------------------------------------------
# query_by_type Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecisionRecordRepositoryQueryByType:
    """Tests for query_by_type() filtering and pagination."""

    def test_query_by_type_returns_matching(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(_make_record(decision_id="ms-001", decision_type="model_select"))
        repo.store(_make_record(decision_id="ms-002", decision_type="model_select"))
        repo.store(_make_record(decision_id="wr-001", decision_type="workflow_route"))

        results, _ = repo.query_by_type("model_select")
        assert len(results) == 2
        assert all(r["decision_type"] == "model_select" for r in results)

    def test_query_by_type_empty_when_no_match(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(_make_record(decision_id="only-one", decision_type="model_select"))

        results, _ = repo.query_by_type("nonexistent_type")
        assert results == []

    def test_query_by_type_time_range_since(self) -> None:
        repo = DecisionRecordRepository()
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        repo.store(_make_record(decision_id="early", stored_at_offset_seconds=0))
        repo.store(_make_record(decision_id="late", stored_at_offset_seconds=3600))

        results, _ = repo.query_by_type(
            "model_select",
            since=base + timedelta(seconds=1800),
        )
        assert len(results) == 1
        assert results[0]["decision_id"] == "late"

    def test_query_by_type_time_range_until(self) -> None:
        repo = DecisionRecordRepository()
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        repo.store(_make_record(decision_id="early2", stored_at_offset_seconds=0))
        repo.store(_make_record(decision_id="late2", stored_at_offset_seconds=3600))

        results, _ = repo.query_by_type(
            "model_select",
            until=base + timedelta(seconds=1800),
        )
        assert len(results) == 1
        assert results[0]["decision_id"] == "early2"

    def test_query_by_type_pagination_returns_cursor(self) -> None:
        repo = DecisionRecordRepository()
        for i in range(5):
            repo.store(
                _make_record(
                    decision_id=f"page-{i:03d}",
                    stored_at_offset_seconds=i,
                )
            )

        results, cursor = repo.query_by_type("model_select", limit=3)
        assert len(results) == 3
        assert cursor is not None

    def test_query_by_type_pagination_second_page(self) -> None:
        repo = DecisionRecordRepository()
        for i in range(5):
            repo.store(
                _make_record(
                    decision_id=f"pg2-{i:03d}",
                    stored_at_offset_seconds=i,
                )
            )

        _, cursor = repo.query_by_type("model_select", limit=3)
        assert cursor is not None

        results2, cursor2 = repo.query_by_type("model_select", limit=3, cursor=cursor)
        assert len(results2) == 2
        assert cursor2 is None

    def test_query_by_type_no_next_cursor_on_last_page(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(_make_record(decision_id="solo"))

        results, cursor = repo.query_by_type("model_select", limit=10)
        assert len(results) == 1
        assert cursor is None

    def test_query_by_type_with_correlation_id(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(_make_record(decision_id="corr-q-001"))
        results, _ = repo.query_by_type("model_select", correlation_id="trace-abc")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# query_by_candidate Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecisionRecordRepositoryQueryByCandidate:
    """Tests for query_by_candidate()."""

    def test_query_by_candidate_returns_matching(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(
            _make_record(decision_id="cand-001", selected_candidate="claude-3-opus")
        )
        repo.store(
            _make_record(decision_id="cand-002", selected_candidate="claude-3-opus")
        )
        repo.store(_make_record(decision_id="cand-003", selected_candidate="gpt-4o"))

        results, _ = repo.query_by_candidate("claude-3-opus")
        assert len(results) == 2
        assert all(r["selected_candidate"] == "claude-3-opus" for r in results)

    def test_query_by_candidate_empty_when_no_match(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(_make_record(selected_candidate="claude-3-opus"))

        results, _ = repo.query_by_candidate("nonexistent-model")
        assert results == []

    def test_query_by_candidate_with_correlation_id(self) -> None:
        repo = DecisionRecordRepository()
        repo.store(_make_record(decision_id="cand-corr-001"))
        results, _ = repo.query_by_candidate(
            "claude-3-opus", correlation_id="trace-xyz"
        )
        assert len(results) == 1
