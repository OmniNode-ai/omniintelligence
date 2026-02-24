# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for Pattern Candidate Reducer and lifecycle state machine.

Tests cover:
- Cluster key creation and equality
- Ingestion gate (disappearance_confirmed required)
- Promotion gates: min_occurrences, transform_convergence, reintroduction_rate,
  tool_version_stability, disappearance_confirmed
- All state transitions: CANDIDATE→VALIDATED→PROMOTED→STABLE→DECAYING→DEPRECATED
- Fast-path deprecation: oscillation threshold, acceptance failure, replay failure
- Decay scoring
- Idempotency: tick on DEPRECATED is no-op
- Integration: full lifecycle from CANDIDATE to STABLE

Reference: OMN-2568
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from omniintelligence.review_pairing.models import FindingFixPair, PairingType
from omniintelligence.review_pairing.reducer import (
    PatternCandidate,
    PatternCandidateReducer,
    PatternClusterKey,
    PatternLifecycleState,
    PromotionGateResult,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_pair(
    *,
    disappearance_confirmed: bool = True,
    diff_hunks: list[str] | None = None,
) -> FindingFixPair:
    """Create a minimal FindingFixPair for testing."""
    return FindingFixPair(
        pair_id=uuid.uuid4(),
        finding_id=uuid.uuid4(),
        fix_commit_sha="abc1234",
        diff_hunks=diff_hunks or ["@@ -1,3 +1,3 @@\n-bad_code()\n+good_code()"],
        confidence_score=0.80,
        disappearance_confirmed=disappearance_confirmed,
        pairing_type=PairingType.SAME_PR,
        created_at=datetime.now(tz=UTC),
    )


def _make_candidate_with_pairs(n: int = 3) -> PatternCandidate:
    """Create a PatternCandidate with n confirmed pairs."""
    reducer = PatternCandidateReducer()
    key = PatternClusterKey(rule_id="ruff:E501", node_type="Call")
    candidate = PatternCandidateReducer.new_candidate(key)
    for _ in range(n):
        pair = _make_pair()
        candidate = reducer.ingest_pair(candidate, pair, cluster_key=key)
    return candidate


# ---------------------------------------------------------------------------
# PatternClusterKey
# ---------------------------------------------------------------------------


class TestPatternClusterKey:
    def test_equality_same_fields(self) -> None:
        a = PatternClusterKey("ruff:E501", "Call", "Module")
        b = PatternClusterKey("ruff:E501", "Call", "Module")
        assert a == b

    def test_inequality_different_rule(self) -> None:
        a = PatternClusterKey("ruff:E501")
        b = PatternClusterKey("ruff:F401")
        assert a != b

    def test_str_representation(self) -> None:
        key = PatternClusterKey("ruff:E501", "Call", "Module")
        assert str(key) == "ruff:E501|Call|Module"

    def test_defaults(self) -> None:
        key = PatternClusterKey(rule_id="ruff:E501")
        assert key.node_type == "unknown"
        assert key.parent_node_type == "unknown"

    def test_hashable(self) -> None:
        key = PatternClusterKey("ruff:E501", "Call")
        d = {key: "value"}
        assert d[key] == "value"


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


class TestIngestion:
    def test_ingest_confirmed_pair_adds_to_list(self) -> None:
        reducer = PatternCandidateReducer()
        key = PatternClusterKey("ruff:E501")
        candidate = PatternCandidateReducer.new_candidate(key)
        pair = _make_pair()

        candidate = reducer.ingest_pair(candidate, pair)
        assert len(candidate.confirmed_pairs) == 1
        assert candidate.confirmed_pairs[0] is pair

    def test_ingest_unconfirmed_pair_raises(self) -> None:
        reducer = PatternCandidateReducer()
        key = PatternClusterKey("ruff:E501")
        candidate = PatternCandidateReducer.new_candidate(key)
        pair = _make_pair(disappearance_confirmed=False)

        with pytest.raises(ValueError, match="disappearance_confirmed=True"):
            reducer.ingest_pair(candidate, pair)

    def test_ingest_updates_last_recurrence(self) -> None:
        reducer = PatternCandidateReducer()
        key = PatternClusterKey("ruff:E501")
        candidate = PatternCandidateReducer.new_candidate(key)
        before = candidate.last_recurrence_at
        pair = _make_pair()

        candidate = reducer.ingest_pair(candidate, pair)
        assert candidate.last_recurrence_at >= before

    def test_new_candidate_with_initial_pair(self) -> None:
        pair = _make_pair()
        candidate = PatternCandidateReducer.new_candidate(
            PatternClusterKey("mypy:return-value"),
            initial_pair=pair,
        )
        assert len(candidate.confirmed_pairs) == 1

    def test_new_candidate_unconfirmed_initial_pair_raises(self) -> None:
        pair = _make_pair(disappearance_confirmed=False)
        with pytest.raises(ValueError):
            PatternCandidateReducer.new_candidate(
                PatternClusterKey("mypy:return-value"),
                initial_pair=pair,
            )

    def test_new_candidate_initial_state_is_candidate(self) -> None:
        candidate = PatternCandidateReducer.new_candidate(
            PatternClusterKey("ruff:E501")
        )
        assert candidate.state == PatternLifecycleState.CANDIDATE

    def test_state_history_has_created_entry(self) -> None:
        candidate = PatternCandidateReducer.new_candidate(
            PatternClusterKey("ruff:E501")
        )
        assert len(candidate.state_history) == 1
        state, _, reason = candidate.state_history[0]
        assert state == PatternLifecycleState.CANDIDATE
        assert "created" in reason


# ---------------------------------------------------------------------------
# Promotion Gates
# ---------------------------------------------------------------------------


class TestPromotionGates:
    def test_gate_fails_min_occurrences(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=2)  # need 3

        result = reducer.evaluate_promotion_gates(candidate)
        assert not result.passed
        assert result.gate_name == "min_occurrences"

    def test_gate_passes_with_enough_pairs(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        result = reducer.evaluate_promotion_gates(candidate)
        assert result.passed

    def test_gate_fails_reintroduction_rate(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        # Mark 1 of 3 as reintroduced → rate = 0.33 > 0.20
        candidate.reintroduced_pair_ids.add(candidate.confirmed_pairs[0].pair_id)

        result = reducer.evaluate_promotion_gates(candidate)
        assert not result.passed
        assert result.gate_name == "reintroduction_rate"

    def test_gate_passes_low_reintroduction(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=5)
        # 0 reintroductions → rate = 0.0
        result = reducer.evaluate_promotion_gates(candidate)
        assert result.passed
        assert result.reintroduction_rate == 0.0

    def test_gate_fails_transform_convergence(self) -> None:
        reducer = PatternCandidateReducer()
        key = PatternClusterKey("ruff:E501")
        candidate = PatternCandidateReducer.new_candidate(key)

        # Add pairs with completely different diffs
        for i in range(3):
            pair = _make_pair(
                diff_hunks=[f"@@ -{i},3 +{i},3 @@\n-{'x' * 100}\n+{'y' * 100}"]
            )
            candidate = reducer.ingest_pair(candidate, pair)

        # Patch similarity to return low value
        with patch(
            "omniintelligence.review_pairing.reducer.reducer._transform_similarity",
            return_value=0.50,
        ):
            result = reducer.evaluate_promotion_gates(candidate)

        assert not result.passed
        assert result.gate_name == "transform_convergence"

    def test_gate_fails_tool_version_stability(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        # Create version map where only 33% share the majority version
        version_map = {
            candidate.confirmed_pairs[0].pair_id: "v1.0.0",
            candidate.confirmed_pairs[1].pair_id: "v2.0.0",
            candidate.confirmed_pairs[2].pair_id: "v3.0.0",
        }
        result = reducer.evaluate_promotion_gates(
            candidate, tool_version_map=version_map
        )
        assert not result.passed
        assert result.gate_name == "tool_version_stability"

    def test_gate_passes_stable_tool_version(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        version_map = {p.pair_id: "v1.0.0" for p in candidate.confirmed_pairs}
        result = reducer.evaluate_promotion_gates(
            candidate, tool_version_map=version_map
        )
        assert result.passed

    def test_gate_occurrence_count_in_result(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        result = reducer.evaluate_promotion_gates(candidate)
        assert result.occurrence_count == 3


# ---------------------------------------------------------------------------
# CANDIDATE → VALIDATED
# ---------------------------------------------------------------------------


class TestCandidateToValidated:
    def test_try_validate_succeeds_with_enough_pairs(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        candidate, result = reducer.try_validate(candidate)
        assert result.passed
        assert candidate.state == PatternLifecycleState.VALIDATED

    def test_try_validate_fails_wrong_state(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        candidate.state = PatternLifecycleState.PROMOTED  # wrong state

        candidate, result = reducer.try_validate(candidate)
        assert not result.passed
        assert result.gate_name == "wrong_state"

    def test_try_validate_sets_transform_signature(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        candidate, result = reducer.try_validate(candidate)
        assert result.passed
        assert candidate.transform_signature != ""

    def test_try_validate_sets_validated_at(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        candidate, result = reducer.try_validate(candidate)
        assert candidate.validated_at is not None

    def test_try_validate_records_state_history(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        candidate, _ = reducer.try_validate(candidate)
        states = [h[0] for h in candidate.state_history]
        assert PatternLifecycleState.VALIDATED in states

    def test_try_validate_fails_insufficient_pairs(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=1)

        candidate, result = reducer.try_validate(candidate)
        assert not result.passed
        assert candidate.state == PatternLifecycleState.CANDIDATE


# ---------------------------------------------------------------------------
# VALIDATED → PROMOTED
# ---------------------------------------------------------------------------


class TestValidatedToPromoted:
    def _validated_candidate(self) -> PatternCandidate:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        candidate, _ = reducer.try_validate(candidate)
        return candidate

    def test_promote_succeeds_when_acceptance_and_replay_pass(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._validated_candidate()

        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=True
        )
        assert candidate.state == PatternLifecycleState.PROMOTED

    def test_promote_fails_acceptance_deprecates(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._validated_candidate()

        candidate = reducer.promote(
            candidate, acceptance_passed=False, replay_clean=True
        )
        assert candidate.state == PatternLifecycleState.DEPRECATED

    def test_promote_fails_replay_deprecates(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._validated_candidate()

        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=False
        )
        assert candidate.state == PatternLifecycleState.DEPRECATED

    def test_promote_sets_promoted_at(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._validated_candidate()

        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=True
        )
        assert candidate.promoted_at is not None

    def test_promote_wrong_state_is_no_op(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)  # CANDIDATE state
        original_state = candidate.state

        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=True
        )
        assert candidate.state == original_state  # unchanged


# ---------------------------------------------------------------------------
# PROMOTED → STABLE
# ---------------------------------------------------------------------------


class TestPromotedToStable:
    def _promoted_candidate(self) -> PatternCandidate:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        candidate, _ = reducer.try_validate(candidate)
        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=True
        )
        return candidate

    def test_stabilize_before_window_is_no_op(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._promoted_candidate()
        # promoted_at is just set, window not elapsed

        candidate = reducer.stabilize(candidate)
        assert candidate.state == PatternLifecycleState.PROMOTED

    def test_stabilize_after_window_transitions_to_stable(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._promoted_candidate()

        # Wind back promoted_at by STABLE_WINDOW_DAYS + 1
        candidate.promoted_at = datetime.now(tz=UTC) - timedelta(days=31)

        candidate = reducer.stabilize(candidate)
        assert candidate.state == PatternLifecycleState.STABLE

    def test_stabilize_with_reintroductions_stays_promoted(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._promoted_candidate()
        candidate.promoted_at = datetime.now(tz=UTC) - timedelta(days=31)
        candidate.reintroduced_pair_ids.add(uuid.uuid4())

        candidate = reducer.stabilize(candidate)
        assert candidate.state == PatternLifecycleState.PROMOTED


# ---------------------------------------------------------------------------
# STABLE → DECAYING → DEPRECATED
# ---------------------------------------------------------------------------


class TestDecay:
    def _stable_candidate(self) -> PatternCandidate:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        candidate, _ = reducer.try_validate(candidate)
        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=True
        )
        candidate.promoted_at = datetime.now(tz=UTC) - timedelta(days=31)
        candidate = reducer.stabilize(candidate)
        return candidate

    def test_decay_transitions_stable_to_decaying(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._stable_candidate()

        candidate = reducer.apply_decay(candidate, recurrence_observed=False)
        assert candidate.state == PatternLifecycleState.DECAYING

    def test_decay_reduces_score(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._stable_candidate()
        original_score = candidate.pattern_score

        candidate = reducer.apply_decay(candidate, recurrence_observed=False)
        assert candidate.pattern_score < original_score

    def test_recurrence_prevents_decay(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._stable_candidate()
        original_score = candidate.pattern_score

        candidate = reducer.apply_decay(candidate, recurrence_observed=True)
        assert candidate.state == PatternLifecycleState.STABLE
        assert candidate.pattern_score == original_score

    def test_repeated_decay_reaches_deprecated(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._stable_candidate()

        # Apply decay many times until deprecated
        for _ in range(100):
            if candidate.state == PatternLifecycleState.DEPRECATED:
                break
            candidate = reducer.apply_decay(candidate, recurrence_observed=False)

        assert candidate.state == PatternLifecycleState.DEPRECATED

    def test_score_clamps_at_zero_on_deprecation(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = self._stable_candidate()

        for _ in range(100):
            if candidate.state == PatternLifecycleState.DEPRECATED:
                break
            candidate = reducer.apply_decay(candidate, recurrence_observed=False)

        assert candidate.pattern_score >= 0.0


# ---------------------------------------------------------------------------
# Fast-path deprecation
# ---------------------------------------------------------------------------


class TestFastPathDeprecation:
    def test_oscillation_threshold_deprecates(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        from omniintelligence.review_pairing.reducer.reducer import MAX_OSCILLATIONS

        candidate.oscillation_count = MAX_OSCILLATIONS

        candidate = reducer.tick(candidate)
        assert candidate.state == PatternLifecycleState.DEPRECATED

    def test_mark_reintroduced_increments_oscillation(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = PatternCandidateReducer.new_candidate(
            PatternClusterKey("ruff:E501")
        )
        pair_id = uuid.uuid4()

        candidate = reducer.mark_reintroduced(candidate, pair_id)
        assert candidate.oscillation_count == 1
        assert pair_id in candidate.reintroduced_pair_ids

    def test_deprecate_from_any_state(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        for state in PatternLifecycleState:
            if state == PatternLifecycleState.DEPRECATED:
                continue
            candidate.state = state
            result = reducer.deprecate(candidate, "manual test deprecation")
            assert result.state == PatternLifecycleState.DEPRECATED
            assert result.deprecated_at is not None


# ---------------------------------------------------------------------------
# Tick (unified driver)
# ---------------------------------------------------------------------------


class TestTick:
    def test_tick_candidate_to_validated_with_enough_pairs(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)

        candidate = reducer.tick(candidate)
        assert candidate.state == PatternLifecycleState.VALIDATED

    def test_tick_deprecated_is_noop(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=3)
        candidate.state = PatternLifecycleState.DEPRECATED

        result = reducer.tick(candidate)
        assert result.state == PatternLifecycleState.DEPRECATED
        # State history should not grow
        initial_history_len = len(candidate.state_history)
        result = reducer.tick(candidate)
        assert len(result.state_history) == initial_history_len

    def test_tick_candidate_stays_candidate_with_few_pairs(self) -> None:
        reducer = PatternCandidateReducer()
        candidate = _make_candidate_with_pairs(n=1)

        candidate = reducer.tick(candidate)
        assert candidate.state == PatternLifecycleState.CANDIDATE


# ---------------------------------------------------------------------------
# Integration: full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    def test_candidate_to_stable_full_path(self) -> None:
        """Drive a cluster through the full happy-path lifecycle."""
        reducer = PatternCandidateReducer()
        key = PatternClusterKey("ruff:E501", "Call", "Module")
        candidate = PatternCandidateReducer.new_candidate(key)

        # Phase 1: Ingest enough confirmed pairs
        for _ in range(3):
            candidate = reducer.ingest_pair(candidate, _make_pair(), cluster_key=key)

        assert candidate.state == PatternLifecycleState.CANDIDATE

        # Phase 2: Validate
        candidate, gate_result = reducer.try_validate(candidate)
        assert gate_result.passed
        assert candidate.state == PatternLifecycleState.VALIDATED

        # Phase 3: Promote
        candidate = reducer.promote(
            candidate, acceptance_passed=True, replay_clean=True
        )
        assert candidate.state == PatternLifecycleState.PROMOTED

        # Phase 4: Stabilize (simulate time passing)
        candidate.promoted_at = datetime.now(tz=UTC) - timedelta(days=31)
        candidate = reducer.stabilize(candidate)
        assert candidate.state == PatternLifecycleState.STABLE

        # Verify state history completeness
        states_seen = [h[0] for h in candidate.state_history]
        assert PatternLifecycleState.CANDIDATE in states_seen
        assert PatternLifecycleState.VALIDATED in states_seen
        assert PatternLifecycleState.PROMOTED in states_seen
        assert PatternLifecycleState.STABLE in states_seen

    def test_candidate_id_is_stable_uuid(self) -> None:
        candidate = PatternCandidateReducer.new_candidate(
            PatternClusterKey("ruff:E501")
        )
        original_id = candidate.candidate_id
        # Tick should not change candidate_id
        reducer = PatternCandidateReducer()
        candidate = reducer.tick(candidate)
        assert candidate.candidate_id == original_id
