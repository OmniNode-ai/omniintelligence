# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration test: full DecisionRecord flow.

Covers the end-to-end flow:
    model selection emits DecisionRecord
    → stored via consumer
    → queryable by decision_id
    → verifiable via replay

This test does NOT require a live Kafka broker or database. It uses
in-memory implementations and simulates the Kafka message path by
encoding a DecisionRecord payload as bytes, passing it through the
consumer, and verifying that:
    1. The record is stored with correct fields.
    2. It is queryable by decision_id (Layer 1 and Layer 2 separation).
    3. Replay verification succeeds (snapshot re-derives original decision).

Ticket: OMN-2467
Epic: OMN-2350 (Decision Provenance System)
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from omniintelligence.decision_store.consumer import DecisionRecordConsumer
from omniintelligence.decision_store.replay import replay_decision
from omniintelligence.decision_store.repository import DecisionRecordRepository
from omniintelligence.decision_store.topics import DecisionTopics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_kafka_payload(
    *,
    decision_id: str | None = None,
    selected_candidate: str = "claude-3-opus",
    with_rationale: bool = False,
) -> bytes:
    """Build a JSON-encoded Kafka DecisionRecord payload.

    Simulates what the model selector would publish to
    ``DecisionTopics.DECISION_RECORDED``.
    """
    did = decision_id or str(uuid.uuid4())
    scoring = [
        {
            "candidate": "claude-3-opus",
            "score": 0.92,
            "breakdown": {"quality": 0.95, "cost": 0.89},
        },
        {
            "candidate": "gpt-4o",
            "score": 0.85,
            "breakdown": {"quality": 0.88, "cost": 0.82},
        },
        {
            "candidate": "llama-3-70b",
            "score": 0.78,
            "breakdown": {"quality": 0.80, "cost": 0.75},
        },
    ]
    snapshot = {
        "model_registry_version": "v2.1.0",
        "scoring_breakdown": json.dumps(
            [{"candidate": s["candidate"], "score": s["score"]} for s in scoring]
        ),
        "tie_breaker": "alphabetical",
        "scoring_weights": json.dumps({"quality": 0.6, "cost": 0.4}),
    }
    payload: dict = {
        "decision_id": did,
        "decision_type": "model_select",
        "timestamp": datetime.now(UTC).isoformat(),
        "selected_candidate": selected_candidate,
        "candidates_considered": [s["candidate"] for s in scoring],
        "constraints_applied": {
            "cost_limit": "max $0.01 per call",
            "context_window": "minimum 128k tokens",
        },
        "scoring_breakdown": scoring,
        "tie_breaker": None,
        "agent_rationale": (
            "Selected claude-3-opus for its superior quality score. "
            "The cost_limit constraint was applied — all candidates passed. "
            "context_window constraint filtered llama-3-70b variants."
            if with_rationale
            else None
        ),
        "reproducibility_snapshot": snapshot,
    }
    return json.dumps(payload).encode("utf-8")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDecisionRecordEndToEndFlow:
    """Full integration flow: emit → store → query → replay."""

    def test_full_flow_store_and_retrieve(self) -> None:
        """Model selection emits a DecisionRecord, consumer stores it,
        and it is queryable by decision_id."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        decision_id = "flow-test-001"
        raw_message = _make_kafka_payload(
            decision_id=decision_id,
            selected_candidate="claude-3-opus",
        )

        # Step 1: Consumer processes the Kafka message
        stored = consumer.handle_message(raw_message, correlation_id="flow-corr-001")
        assert stored is True, "Consumer must store the first message"
        assert repo.count() == 1

        # Step 2: Record is queryable by decision_id (Layer 1 only — default)
        record_l1 = repo.get_record(decision_id)
        assert record_l1 is not None
        assert record_l1["decision_id"] == decision_id
        assert record_l1["selected_candidate"] == "claude-3-opus"
        assert record_l1["decision_type"] == "model_select"
        assert "agent_rationale" not in record_l1  # Layer 1 excludes rationale

        # Step 3: Topic is the correct enum value
        assert consumer.topic == DecisionTopics.DECISION_RECORDED

    def test_full_flow_layer2_rationale_separation(self) -> None:
        """Layer 2 (agent_rationale) is stored but excluded from Layer 1 reads."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        decision_id = "flow-rationale-001"
        raw_message = _make_kafka_payload(
            decision_id=decision_id,
            selected_candidate="claude-3-opus",
            with_rationale=True,
        )

        consumer.handle_message(raw_message)

        # Layer 1 — no rationale
        l1 = repo.get_record(decision_id, include_rationale=False)
        assert l1 is not None
        assert "agent_rationale" not in l1

        # Layer 2 — with rationale
        l2 = repo.get_record(decision_id, include_rationale=True)
        assert l2 is not None
        assert "agent_rationale" in l2
        assert l2["agent_rationale"] is not None
        assert "claude-3-opus" in l2["agent_rationale"]

    def test_full_flow_idempotency(self) -> None:
        """Duplicate Kafka messages are deduplicated — only one record stored."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        decision_id = "flow-idempotent-001"
        raw_message = _make_kafka_payload(decision_id=decision_id)

        first = consumer.handle_message(raw_message, correlation_id="corr-a")
        second = consumer.handle_message(raw_message, correlation_id="corr-b")

        assert first is True
        assert second is False
        assert repo.count() == 1

    def test_full_flow_replay_verification_matches(self) -> None:
        """Stored record can be replayed and result matches original decision."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        decision_id = "flow-replay-match-001"
        raw_message = _make_kafka_payload(
            decision_id=decision_id,
            selected_candidate="claude-3-opus",
        )

        consumer.handle_message(raw_message, correlation_id="replay-corr-001")

        # Retrieve the stored row (full record for replay access)
        from omniintelligence.decision_store.models import DecisionRecordRow

        full_data = repo.get_record(decision_id, include_rationale=True)
        assert full_data is not None

        # Reconstruct the row to pass to replay_decision
        row = DecisionRecordRow.from_dict(full_data)
        result = replay_decision(row, correlation_id="replay-corr-001")

        assert result.match is True
        assert result.original_candidate == "claude-3-opus"
        assert result.replayed_candidate == "claude-3-opus"

    def test_full_flow_query_by_type(self) -> None:
        """Records are queryable by decision_type."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        # Store 3 records
        for i in range(3):
            consumer.handle_message(
                _make_kafka_payload(decision_id=f"type-query-{i:03d}")
            )

        results, cursor = repo.query_by_type(
            "model_select",
            correlation_id="type-query-corr",
        )
        assert len(results) == 3
        assert all(r["decision_type"] == "model_select" for r in results)
        assert cursor is None  # All fit in one page

    def test_full_flow_query_by_candidate(self) -> None:
        """Records are queryable by selected_candidate."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        consumer.handle_message(
            _make_kafka_payload(
                decision_id="cand-q-001", selected_candidate="claude-3-opus"
            )
        )
        consumer.handle_message(
            _make_kafka_payload(
                decision_id="cand-q-002", selected_candidate="claude-3-opus"
            )
        )
        consumer.handle_message(
            _make_kafka_payload(decision_id="cand-q-003", selected_candidate="gpt-4o")
        )

        claude_results, _ = repo.query_by_candidate("claude-3-opus")
        gpt_results, _ = repo.query_by_candidate("gpt-4o")

        assert len(claude_results) == 2
        assert len(gpt_results) == 1
        assert all(r["selected_candidate"] == "claude-3-opus" for r in claude_results)

    def test_consumer_topic_is_decision_recorded(self) -> None:
        """Consumer subscribes to the correct Kafka topic."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        assert consumer.topic == "onex.cmd.omniintelligence.decision-recorded.v1"
        assert consumer.topic == DecisionTopics.DECISION_RECORDED

    def test_multiple_correlation_ids_tracked_through_flow(self) -> None:
        """Different correlation IDs for each message — all stored correctly."""
        repo = DecisionRecordRepository()
        consumer = DecisionRecordConsumer(repository=repo)

        correlation_ids = ["corr-a-001", "corr-b-002", "corr-c-003"]
        decision_ids = [f"multi-corr-{i:03d}" for i in range(3)]

        for did, cid in zip(decision_ids, correlation_ids, strict=True):
            stored = consumer.handle_message(
                _make_kafka_payload(decision_id=did),
                correlation_id=cid,
            )
            assert stored is True

        assert repo.count() == 3

        for did in decision_ids:
            record = repo.get_record(did)
            assert record is not None
            assert record["decision_id"] == did
