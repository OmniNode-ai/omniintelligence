# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for ModelSelector DecisionRecord emission.

Tests that every model selection emits a DecisionRecord with correct
scoring breakdown, candidates, constraints, and reproducibility snapshot.

Ticket: OMN-2466 - V1: Unit tests with mocked emitter
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from omniintelligence.model_selector.decision_emitter import MockDecisionEmitter
from omniintelligence.model_selector.selector import (
    CandidateScore,
    ModelSelector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TIMESTAMP = datetime(2026, 2, 21, 10, 0, 0, tzinfo=UTC)

SAMPLE_CANDIDATES = ["claude-3-opus", "gpt-4o", "llama-3-70b"]
SAMPLE_SCORES = {
    "claude-3-opus": {"quality": 0.95, "cost": 0.85},
    "gpt-4o": {"quality": 0.90, "cost": 0.80},
    "llama-3-70b": {"quality": 0.80, "cost": 0.95},
}
SAMPLE_WEIGHTS = {"quality": 0.6, "cost": 0.4}


def _make_selector(
    emitter: MockDecisionEmitter | None = None,
    weights: dict | None = None,
    constraints: dict | None = None,
    registry_version: str = "v1.0.0",
) -> tuple[ModelSelector, MockDecisionEmitter]:
    """Build a ModelSelector with a MockDecisionEmitter."""
    mock = emitter or MockDecisionEmitter()
    selector = ModelSelector(
        scoring_weights=weights or SAMPLE_WEIGHTS,
        constraints=constraints or {"cost_limit": "max $0.01/call"},
        model_registry_version=registry_version,
        emitter=mock,
    )
    return selector, mock


# ---------------------------------------------------------------------------
# R1: Every model selection emits a DecisionRecord
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecisionRecordEmission:
    """Tests for R1: every selection emits a DecisionRecord."""

    def test_select_emits_exactly_once(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES,
            scores=SAMPLE_SCORES,
            timestamp=FIXED_TIMESTAMP,
        )
        assert mock.emit_count == 1

    def test_multiple_selections_emit_multiple_records(self) -> None:
        selector, mock = _make_selector()
        for _ in range(3):
            selector.select(
                SAMPLE_CANDIDATES,
                scores=SAMPLE_SCORES,
                timestamp=FIXED_TIMESTAMP,
            )
        assert mock.emit_count == 3

    def test_emitted_record_has_decision_id(self) -> None:
        selector, mock = _make_selector()
        result = selector.select(
            SAMPLE_CANDIDATES,
            scores=SAMPLE_SCORES,
            timestamp=FIXED_TIMESTAMP,
        )
        record = mock.last_record()
        assert record is not None
        assert "decision_id" in record
        assert record["decision_id"] == result.decision_id

    def test_decision_id_is_uuid4(self) -> None:
        import re

        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
        assert uuid_re.match(record["decision_id"]), (
            f"Not a UUID4: {record['decision_id']}"
        )

    def test_decision_type_is_model_select(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        assert record["decision_type"] == "model_select"

    def test_timestamp_is_injected_not_internal(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES,
            scores=SAMPLE_SCORES,
            timestamp=FIXED_TIMESTAMP,
        )
        record = mock.last_record()
        assert record is not None
        assert FIXED_TIMESTAMP.isoformat() == record["timestamp"]

    def test_selected_candidate_in_emitted_record(self) -> None:
        selector, mock = _make_selector()
        result = selector.select(
            SAMPLE_CANDIDATES,
            scores=SAMPLE_SCORES,
            timestamp=FIXED_TIMESTAMP,
        )
        record = mock.last_record()
        assert record is not None
        assert record["selected_candidate"] == result.selected_candidate


# ---------------------------------------------------------------------------
# R2: Scoring breakdown is complete and verifiable
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScoringBreakdown:
    """Tests for R2: complete scoring breakdown."""

    def test_all_candidates_listed(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        assert set(record["candidates_considered"]) == set(SAMPLE_CANDIDATES)

    def test_scoring_breakdown_has_all_candidates(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        breakdown = record["scoring_breakdown"]
        scored_candidates = {s["candidate"] for s in breakdown}
        assert scored_candidates == set(SAMPLE_CANDIDATES)

    def test_scoring_breakdown_has_metric_breakdown(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        for entry in record["scoring_breakdown"]:
            assert "breakdown" in entry
            assert isinstance(entry["breakdown"], dict)

    def test_constraints_applied_matches_constructor(self) -> None:
        constraints = {"cost_limit": "max $0.01/call", "latency_limit": "p99 < 2s"}
        selector, mock = _make_selector(constraints=constraints)
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        assert record["constraints_applied"] == constraints

    def test_winner_has_highest_score(self) -> None:
        weights = {"quality": 0.6, "cost": 0.4}
        # claude: 0.95*0.6 + 0.85*0.4 = 0.57 + 0.34 = 0.91
        # gpt-4o: 0.90*0.6 + 0.80*0.4 = 0.54 + 0.32 = 0.86
        # llama:  0.80*0.6 + 0.95*0.4 = 0.48 + 0.38 = 0.86
        selector, _mock = _make_selector(weights=weights)
        result = selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        assert result.selected_candidate == "claude-3-opus"

    def test_tie_breaker_populated_on_tie(self) -> None:
        # Equal scores for all candidates
        equal_scores = {
            "model-a": {"quality": 0.80},
            "model-b": {"quality": 0.80},
        }
        selector, _mock = _make_selector(weights={"quality": 1.0})
        result = selector.select(
            ["model-a", "model-b"],
            scores=equal_scores,
            timestamp=FIXED_TIMESTAMP,
        )
        assert result.tie_breaker is not None
        assert result.tie_breaker == "alphabetical"
        # Alphabetical: model-a before model-b
        assert result.selected_candidate == "model-a"

    def test_tie_breaker_none_when_clear_winner(self) -> None:
        selector, _mock = _make_selector()
        result = selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        assert result.tie_breaker is None


# ---------------------------------------------------------------------------
# R3: Emission is non-blocking
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNonBlockingEmission:
    """Tests for R3: emission failure does not block selection."""

    def test_selection_succeeds_when_emitter_fails(self) -> None:
        failing_emitter = MockDecisionEmitter(should_fail=True)
        selector = ModelSelector(
            scoring_weights=SAMPLE_WEIGHTS,
            emitter=failing_emitter,
        )
        # Should not raise even though emitter fails
        result = selector.select(
            SAMPLE_CANDIDATES,
            scores=SAMPLE_SCORES,
            timestamp=FIXED_TIMESTAMP,
        )
        # Selection result is still valid
        assert result.selected_candidate in SAMPLE_CANDIDATES

    def test_selection_result_is_correct_despite_emission_failure(self) -> None:
        failing_emitter = MockDecisionEmitter(should_fail=True)
        selector = ModelSelector(
            scoring_weights=SAMPLE_WEIGHTS,
            constraints={"cost_limit": "budget"},
            emitter=failing_emitter,
        )
        result = selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        # The highest-scoring candidate should still win
        assert result.selected_candidate == "claude-3-opus"


# ---------------------------------------------------------------------------
# R4: reproducibility_snapshot captures runtime state
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReproducibilitySnapshot:
    """Tests for R4: snapshot is complete and re-derivable."""

    def test_snapshot_contains_model_registry_version(self) -> None:
        selector, mock = _make_selector(registry_version="v2.3.1")
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        snap = record["reproducibility_snapshot"]
        assert snap.get("model_registry_version") == "v2.3.1"

    def test_snapshot_contains_scoring_weights(self) -> None:
        weights = {"quality": 0.7, "cost": 0.3}
        selector, mock = _make_selector(weights=weights)
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        snap = record["reproducibility_snapshot"]
        stored_weights = json.loads(snap["scoring_weights"])
        assert stored_weights == weights

    def test_snapshot_contains_active_constraints(self) -> None:
        constraints = {"latency": "p99 < 2s", "cost": "budget limit"}
        selector, mock = _make_selector(constraints=constraints)
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        snap = record["reproducibility_snapshot"]
        stored_constraints = json.loads(snap["active_constraints"])
        assert set(stored_constraints) == set(constraints.keys())

    def test_snapshot_contains_scoring_breakdown(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        snap = record["reproducibility_snapshot"]
        scoring_from_snap = json.loads(snap["scoring_breakdown"])
        assert len(scoring_from_snap) == len(SAMPLE_CANDIDATES)
        snap_candidates = {e["candidate"] for e in scoring_from_snap}
        assert snap_candidates == set(SAMPLE_CANDIDATES)

    def test_snapshot_contains_selected_candidate(self) -> None:
        selector, mock = _make_selector()
        result = selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        snap = record["reproducibility_snapshot"]
        assert snap["selected_candidate"] == result.selected_candidate

    def test_snapshot_is_serializable_to_dict_str_str(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        snap = record["reproducibility_snapshot"]
        assert isinstance(snap, dict)
        for k, v in snap.items():
            assert isinstance(k, str), f"Key not str: {k!r}"
            assert isinstance(v, str), f"Value not str: {v!r}"


# ---------------------------------------------------------------------------
# Agent rationale (optional Layer 2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAgentRationale:
    """Tests for optional agent_rationale (Layer 2)."""

    def test_agent_rationale_included_when_provided(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES,
            scores=SAMPLE_SCORES,
            timestamp=FIXED_TIMESTAMP,
            agent_rationale="Chose claude-3-opus for superior code quality scores.",
        )
        record = mock.last_record()
        assert record is not None
        assert (
            record["agent_rationale"]
            == "Chose claude-3-opus for superior code quality scores."
        )

    def test_agent_rationale_is_none_by_default(self) -> None:
        selector, mock = _make_selector()
        selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        record = mock.last_record()
        assert record is not None
        assert record["agent_rationale"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for ModelSelector."""

    def test_raises_on_empty_candidates(self) -> None:
        selector, _ = _make_selector()
        with pytest.raises(ValueError, match="at least one candidate"):
            selector.select([], scores={}, timestamp=FIXED_TIMESTAMP)

    def test_single_candidate_is_selected(self) -> None:
        selector, mock = _make_selector()
        result = selector.select(
            ["only-model"],
            scores={"only-model": {"quality": 0.5}},
            timestamp=FIXED_TIMESTAMP,
        )
        assert result.selected_candidate == "only-model"
        assert mock.emit_count == 1

    def test_candidate_with_no_scores_gets_zero_aggregate(self) -> None:
        selector, _mock = _make_selector()
        result = selector.select(
            ["no-scores-model", "scored-model"],
            scores={"scored-model": {"quality": 0.9, "cost": 0.8}},
            timestamp=FIXED_TIMESTAMP,
        )
        assert result.selected_candidate == "scored-model"

    def test_result_is_frozen_dataclass(self) -> None:
        selector, _ = _make_selector()
        result = selector.select(
            SAMPLE_CANDIDATES, scores=SAMPLE_SCORES, timestamp=FIXED_TIMESTAMP
        )
        with pytest.raises((AttributeError, TypeError)):
            result.selected_candidate = "modified"  # type: ignore[misc]

    def test_candidate_score_is_frozen(self) -> None:
        score = CandidateScore(candidate="test", score=0.5, breakdown={})
        with pytest.raises((AttributeError, TypeError)):
            score.score = 0.9  # type: ignore[misc]
