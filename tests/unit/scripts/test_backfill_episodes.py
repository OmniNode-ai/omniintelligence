# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for scripts/backfill_episodes.py."""

from __future__ import annotations

import datetime

# Import the module under test — functions are pure, no DB needed.
# We add the scripts dir to sys.path so the import works.
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from backfill_episodes import (  # noqa: E402
    SURFACE_AGENT_ROUTING,
    SURFACE_LLM_ROUTING,
    BackfillReport,
    RejectionStats,
    filter_agent_routing_row,
    filter_llm_routing_row,
    make_episode_id,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent_row(**overrides: object) -> dict[str, object]:
    """Build a valid agent_routing_decisions row dict."""
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "correlation_id": uuid.uuid4(),
        "session_id": "sess-1",
        "user_request": "deploy the service",
        "user_request_hash": "abc123",
        "context_snapshot": {"repo": "omniintelligence"},
        "selected_agent": "agent-devops-infrastructure",
        "confidence_score": 0.85,
        "routing_strategy": "hybrid",
        "trigger_confidence": 0.9,
        "context_confidence": 0.8,
        "capability_confidence": 0.7,
        "historical_confidence": 0.6,
        "alternatives": [{"agent": "agent-testing", "score": 0.4}],
        "reasoning": "Best match for deploy tasks",
        "routing_time_ms": 42,
        "cache_hit": False,
        "selection_validated": True,
        "actual_success": None,
        "execution_succeeded": None,
        "actual_quality_score": None,
        "created_at": datetime.datetime(2026, 3, 1, 12, 0, 0),
        "projected_at": datetime.datetime(2026, 3, 1, 12, 0, 0),
    }
    base.update(overrides)
    return base


def _make_llm_row(**overrides: object) -> dict[str, object]:
    """Build a valid llm_routing_decisions row dict."""
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "correlation_id": uuid.uuid4(),
        "session_id": "sess-2",
        "llm_agent": "agent-pr-ticket-writer",
        "fuzzy_agent": "agent-pr-review",
        "agreement": False,
        "llm_confidence": 0.6257,
        "fuzzy_confidence": 0.45,
        "llm_latency_ms": 120,
        "fuzzy_latency_ms": 5,
        "used_fallback": False,
        "routing_prompt_version": "v3",
        "intent": "create ticket",
        "model": "claude-3-haiku",
        "cost_usd": 0.00012,
        "created_at": datetime.datetime(
            2026, 3, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
        ),
        "projected_at": datetime.datetime(
            2026, 3, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
        ),
        "prompt_tokens": 150,
        "completion_tokens": 30,
        "total_tokens": 180,
        "omninode_enabled": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests — make_episode_id
# ---------------------------------------------------------------------------


class TestMakeEpisodeId:
    def test_deterministic(self) -> None:
        """Same inputs produce same UUID."""
        id1 = make_episode_id("agent_routing", "abc-123")
        id2 = make_episode_id("agent_routing", "abc-123")
        assert id1 == id2

    def test_different_surface_different_id(self) -> None:
        """Different surfaces produce different UUIDs."""
        id1 = make_episode_id("agent_routing", "abc-123")
        id2 = make_episode_id("llm_routing", "abc-123")
        assert id1 != id2

    def test_different_source_different_id(self) -> None:
        """Different source IDs produce different UUIDs."""
        id1 = make_episode_id("agent_routing", "abc-123")
        id2 = make_episode_id("agent_routing", "def-456")
        assert id1 != id2

    def test_is_uuid5(self) -> None:
        """Result is a UUID version 5."""
        result = make_episode_id("test", "key")
        assert result.version == 5


# ---------------------------------------------------------------------------
# Tests — filter_agent_routing_row
# ---------------------------------------------------------------------------


class TestFilterAgentRoutingRow:
    def test_valid_row_accepted(self) -> None:
        """A fully valid row produces an episode dict."""
        row = _make_agent_row()
        episode, rejection = filter_agent_routing_row(row)
        assert rejection is None
        assert episode is not None
        assert episode["surface"] == SURFACE_AGENT_ROUTING
        assert episode["backfilled"] is True
        assert episode["source_table"] == "agent_routing_decisions"

    def test_null_created_at_rejected(self) -> None:
        row = _make_agent_row(created_at=None)
        episode, rejection = filter_agent_routing_row(row)
        assert episode is None
        assert rejection == "null_created_at"

    def test_unknown_agent_rejected(self) -> None:
        row = _make_agent_row(selected_agent="unknown")
        episode, rejection = filter_agent_routing_row(row)
        assert episode is None
        assert rejection == "unknown_agent"

    def test_empty_agent_rejected(self) -> None:
        row = _make_agent_row(selected_agent="")
        episode, rejection = filter_agent_routing_row(row)
        assert episode is None
        assert rejection == "unknown_agent"

    def test_zero_confidence_rejected(self) -> None:
        row = _make_agent_row(confidence_score=0.0)
        episode, rejection = filter_agent_routing_row(row)
        assert episode is None
        assert rejection == "zero_confidence"

    def test_null_confidence_rejected(self) -> None:
        row = _make_agent_row(confidence_score=None)
        episode, rejection = filter_agent_routing_row(row)
        assert episode is None
        assert rejection == "zero_confidence"

    def test_no_observation_features_rejected(self) -> None:
        row = _make_agent_row(
            context_snapshot=None,
            reasoning=None,
            user_request=None,
        )
        episode, rejection = filter_agent_routing_row(row)
        assert episode is None
        assert rejection == "no_observation_features"

    def test_reasoning_only_accepted(self) -> None:
        """Row with only reasoning (no context/request) is still valid."""
        row = _make_agent_row(
            context_snapshot=None,
            user_request=None,
            reasoning="Selected based on keyword match",
        )
        episode, rejection = filter_agent_routing_row(row)
        assert rejection is None
        assert episode is not None

    def test_episode_id_deterministic(self) -> None:
        """Same row produces same episode_id."""
        row = _make_agent_row()
        ep1, _ = filter_agent_routing_row(row)
        ep2, _ = filter_agent_routing_row(row)
        assert ep1 is not None and ep2 is not None
        assert ep1["episode_id"] == ep2["episode_id"]

    def test_decision_snapshot_contains_context(self) -> None:
        import json

        row = _make_agent_row()
        episode, _ = filter_agent_routing_row(row)
        assert episode is not None
        snapshot = json.loads(episode["decision_snapshot"])
        assert "context_snapshot" in snapshot
        assert "user_request" in snapshot

    def test_action_taken_contains_agent(self) -> None:
        import json

        row = _make_agent_row()
        episode, _ = filter_agent_routing_row(row)
        assert episode is not None
        action = json.loads(episode["action_taken"])
        assert action["selected_agent"] == "agent-devops-infrastructure"
        assert action["confidence_score"] == 0.85


# ---------------------------------------------------------------------------
# Tests — filter_llm_routing_row
# ---------------------------------------------------------------------------


class TestFilterLlmRoutingRow:
    def test_valid_row_accepted(self) -> None:
        row = _make_llm_row()
        episode, rejection = filter_llm_routing_row(row)
        assert rejection is None
        assert episode is not None
        assert episode["surface"] == SURFACE_LLM_ROUTING
        assert episode["backfilled"] is True

    def test_null_created_at_rejected(self) -> None:
        row = _make_llm_row(created_at=None)
        episode, rejection = filter_llm_routing_row(row)
        assert episode is None
        assert rejection == "null_created_at"

    def test_unknown_agent_rejected(self) -> None:
        row = _make_llm_row(llm_agent="unknown")
        episode, rejection = filter_llm_routing_row(row)
        assert episode is None
        assert rejection == "unknown_agent"

    def test_zero_confidence_rejected(self) -> None:
        row = _make_llm_row(llm_confidence=0.0)
        episode, rejection = filter_llm_routing_row(row)
        assert episode is None
        assert rejection == "zero_confidence"

    def test_null_agreement_rejected(self) -> None:
        row = _make_llm_row(agreement=None)
        episode, rejection = filter_llm_routing_row(row)
        assert episode is None
        assert rejection == "no_terminal_outcome"

    def test_outcome_metrics_contain_agreement(self) -> None:
        import json

        row = _make_llm_row(agreement=True)
        episode, _ = filter_llm_routing_row(row)
        assert episode is not None
        metrics = json.loads(episode["outcome_metrics"])
        assert metrics["agreement"] is True

    def test_action_taken_contains_llm_agent(self) -> None:
        import json

        row = _make_llm_row()
        episode, _ = filter_llm_routing_row(row)
        assert episode is not None
        action = json.loads(episode["action_taken"])
        assert action["llm_agent"] == "agent-pr-ticket-writer"
        assert action["llm_confidence"] == 0.6257

    def test_episode_id_deterministic(self) -> None:
        row = _make_llm_row()
        ep1, _ = filter_llm_routing_row(row)
        ep2, _ = filter_llm_routing_row(row)
        assert ep1 is not None and ep2 is not None
        assert ep1["episode_id"] == ep2["episode_id"]


# ---------------------------------------------------------------------------
# Tests — BackfillReport
# ---------------------------------------------------------------------------


class TestBackfillReport:
    def test_empty_report(self) -> None:
        report = BackfillReport()
        assert report.accepted == 0
        assert report.duplicates == 0
        assert report.rejections.total == 0

    def test_rejection_counting(self) -> None:
        stats = RejectionStats()
        stats.reject("unknown_agent")
        stats.reject("unknown_agent")
        stats.reject("zero_confidence")
        assert stats.total == 3
        assert stats.counts["unknown_agent"] == 2
        assert stats.counts["zero_confidence"] == 1

    def test_report_print(self, capsys: pytest.CaptureFixture[str]) -> None:
        report = BackfillReport(accepted=10, duplicates=3)
        report.rejections.reject("unknown_agent")
        report.rejections.reject("zero_confidence")
        report.print_report()
        captured = capsys.readouterr()
        assert "Accepted (inserted):  10" in captured.out
        assert "Duplicates (skipped): 3" in captured.out
        assert "Rejected (filtered):  2" in captured.out
        assert "unknown_agent: 1" in captured.out


# ---------------------------------------------------------------------------
# Tests — Idempotency (unit-level)
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Verify that deterministic episode_id generation guarantees idempotency."""

    def test_same_row_same_id_agent(self) -> None:
        """Processing the same agent row twice yields the same episode_id."""
        row = _make_agent_row()
        ep1, _ = filter_agent_routing_row(row)
        ep2, _ = filter_agent_routing_row(row)
        assert ep1 is not None and ep2 is not None
        assert ep1["episode_id"] == ep2["episode_id"]

    def test_same_row_same_id_llm(self) -> None:
        """Processing the same LLM row twice yields the same episode_id."""
        row = _make_llm_row()
        ep1, _ = filter_llm_routing_row(row)
        ep2, _ = filter_llm_routing_row(row)
        assert ep1 is not None and ep2 is not None
        assert ep1["episode_id"] == ep2["episode_id"]

    def test_different_rows_different_ids(self) -> None:
        """Different source rows produce different episode_ids."""
        row1 = _make_agent_row(id=uuid.UUID("11111111-1111-1111-1111-111111111111"))
        row2 = _make_agent_row(id=uuid.UUID("22222222-2222-2222-2222-222222222222"))
        ep1, _ = filter_agent_routing_row(row1)
        ep2, _ = filter_agent_routing_row(row2)
        assert ep1 is not None and ep2 is not None
        assert ep1["episode_id"] != ep2["episode_id"]
