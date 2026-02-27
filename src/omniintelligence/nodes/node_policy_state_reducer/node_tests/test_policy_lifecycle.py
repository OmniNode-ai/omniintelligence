# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for PolicyStateReducer lifecycle transitions (OMN-2557).

Tests cover:
  - Pure lifecycle handler: all four transitions
  - apply_reward_delta: reliability update and count tracking
  - should_blacklist: auto-blacklist conditions
  - Idempotency: duplicate events return was_duplicate=True
  - Node integration with mock repository and publisher
"""

from __future__ import annotations

import uuid

import pytest

from omniintelligence.nodes.node_policy_state_reducer.handlers.handler_lifecycle import (
    apply_reward_delta,
    compute_next_lifecycle_state,
    should_blacklist,
)
from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_lifecycle_state import (
    EnumPolicyLifecycleState,
)
from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_type import (
    EnumPolicyType,
)
from omniintelligence.nodes.node_policy_state_reducer.models.model_policy_state_input import (
    ModelPolicyStateInput,
)
from omniintelligence.nodes.node_policy_state_reducer.models.model_reward_assigned_event import (
    ModelRewardAssignedEvent,
)
from omniintelligence.nodes.node_policy_state_reducer.models.model_transition_thresholds import (
    ModelTransitionThresholds,
)
from omniintelligence.nodes.node_policy_state_reducer.node import (
    NodePolicyStateReducer,
)

# Default thresholds for testing
_THRESHOLDS = ModelTransitionThresholds(
    validated_min_runs=5,
    validated_positive_signal_floor=0.6,
    promoted_significance_threshold=0.8,
    promoted_min_runs=10,
    reliability_floor=0.4,
    blacklist_floor=0.3,
)


# =============================================================================
# Tests: compute_next_lifecycle_state
# =============================================================================


@pytest.mark.unit
class TestComputeNextLifecycleState:
    def test_candidate_stays_candidate_insufficient_runs(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.CANDIDATE,
            reliability_0_1=0.9,
            run_count=3,  # below validated_min_runs=5
            positive_signal_ratio=0.8,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.CANDIDATE

    def test_candidate_stays_candidate_low_signal(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.CANDIDATE,
            reliability_0_1=0.9,
            run_count=10,
            positive_signal_ratio=0.4,  # below floor=0.6
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.CANDIDATE

    def test_candidate_transitions_to_validated(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.CANDIDATE,
            reliability_0_1=0.9,
            run_count=5,  # meets min_runs=5
            positive_signal_ratio=0.7,  # meets floor=0.6
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.VALIDATED

    def test_validated_stays_validated_insufficient_runs(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.VALIDATED,
            reliability_0_1=0.9,
            run_count=8,  # below promoted_min_runs=10
            positive_signal_ratio=0.8,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.VALIDATED

    def test_validated_transitions_to_promoted(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.VALIDATED,
            reliability_0_1=0.85,  # meets significance=0.8
            run_count=10,  # meets min_runs=10
            positive_signal_ratio=0.9,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.PROMOTED

    def test_promoted_transitions_to_deprecated_on_floor_breach(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.PROMOTED,
            reliability_0_1=0.35,  # below floor=0.4
            run_count=100,
            positive_signal_ratio=0.3,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.DEPRECATED

    def test_validated_transitions_to_deprecated_on_floor_breach(self) -> None:
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.VALIDATED,
            reliability_0_1=0.3,  # below floor=0.4
            run_count=20,
            positive_signal_ratio=0.3,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.DEPRECATED

    def test_deprecated_is_terminal(self) -> None:
        """DEPRECATED state is terminal — no further transitions."""
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.DEPRECATED,
            reliability_0_1=0.99,
            run_count=1000,
            positive_signal_ratio=0.99,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.DEPRECATED

    def test_degradation_takes_priority_over_promotion(self) -> None:
        """If reliability falls below floor, degradation takes priority over promotion."""
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.VALIDATED,
            reliability_0_1=0.35,  # below floor — degradation fires
            run_count=50,  # would also qualify for promotion
            positive_signal_ratio=0.9,
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.DEPRECATED

    def test_exact_boundary_candidate_to_validated(self) -> None:
        """Exact boundary values produce expected transitions."""
        result = compute_next_lifecycle_state(
            current_state=EnumPolicyLifecycleState.CANDIDATE,
            reliability_0_1=0.9,
            run_count=5,  # exactly validated_min_runs
            positive_signal_ratio=0.6,  # exactly floor
            thresholds=_THRESHOLDS,
        )
        assert result == EnumPolicyLifecycleState.VALIDATED


# =============================================================================
# Tests: apply_reward_delta
# =============================================================================


@pytest.mark.unit
class TestApplyRewardDelta:
    def test_positive_delta_improves_reliability(self) -> None:
        new_rel, new_runs, new_failures = apply_reward_delta(
            current_reliability=0.5,
            reward_delta=0.8,
            run_count=10,
            failure_count=2,
        )
        assert new_rel > 0.5
        assert new_runs == 11
        assert new_failures == 2

    def test_negative_delta_degrades_reliability(self) -> None:
        new_rel, new_runs, new_failures = apply_reward_delta(
            current_reliability=0.8,
            reward_delta=-0.5,
            run_count=10,
            failure_count=2,
        )
        assert new_rel < 0.8
        assert new_runs == 11
        assert new_failures == 3

    def test_reliability_clamped_to_zero(self) -> None:
        new_rel, _, _ = apply_reward_delta(
            current_reliability=0.01,
            reward_delta=-1.0,
            run_count=100,
            failure_count=0,
        )
        assert new_rel >= 0.0

    def test_reliability_clamped_to_one(self) -> None:
        new_rel, _, _ = apply_reward_delta(
            current_reliability=0.99,
            reward_delta=1.0,
            run_count=100,
            failure_count=0,
        )
        assert new_rel <= 1.0

    def test_run_count_increments_by_one(self) -> None:
        _, new_runs, _ = apply_reward_delta(0.5, 0.5, 42, 5)
        assert new_runs == 43

    def test_failure_count_increments_only_on_negative_delta(self) -> None:
        _, _, new_failures_pos = apply_reward_delta(0.5, 0.1, 10, 2)
        _, _, new_failures_neg = apply_reward_delta(0.5, -0.1, 10, 2)
        assert new_failures_pos == 2  # positive delta: no failure
        assert new_failures_neg == 3  # negative delta: +1 failure


# =============================================================================
# Tests: should_blacklist
# =============================================================================


@pytest.mark.unit
class TestShouldBlacklist:
    def test_blacklist_fires_below_floor(self) -> None:
        result = should_blacklist(0.25, _THRESHOLDS, already_blacklisted=False)
        assert result is True

    def test_blacklist_does_not_fire_at_floor(self) -> None:
        result = should_blacklist(0.3, _THRESHOLDS, already_blacklisted=False)
        assert result is False

    def test_blacklist_does_not_fire_above_floor(self) -> None:
        result = should_blacklist(0.8, _THRESHOLDS, already_blacklisted=False)
        assert result is False

    def test_already_blacklisted_does_not_re_blacklist(self) -> None:
        result = should_blacklist(0.1, _THRESHOLDS, already_blacklisted=True)
        assert result is False


# =============================================================================
# Tests: Node integration with mock repository and publisher
# =============================================================================


class MockRepository:
    """In-memory mock for ProtocolPolicyStateRepository."""

    def __init__(self) -> None:
        self._state: dict[tuple[str, str], str] = {}
        self._counts: dict[tuple[str, str], tuple[int, int]] = {}
        self._processed: set[str] = set()
        self.audit_log: list[dict[str, object]] = []

    async def get_current_state_json(
        self, policy_id: str, policy_type: object
    ) -> str | None:
        return self._state.get((policy_id, str(policy_type)))

    async def get_run_counts(
        self, policy_id: str, policy_type: object
    ) -> tuple[int, int]:
        return self._counts.get((policy_id, str(policy_type)), (0, 0))

    async def upsert_state(
        self,
        *,
        policy_id: str,
        policy_type: object,
        lifecycle_state_value: str,
        state_json: str,
        run_count: int,
        failure_count: int,
        blacklisted: bool,
        updated_at_utc: str,
    ) -> None:
        self._state[(policy_id, str(policy_type))] = state_json
        self._counts[(policy_id, str(policy_type))] = (run_count, failure_count)

    async def write_audit_entry(self, **kwargs: object) -> None:
        self.audit_log.append(kwargs)

    async def is_duplicate_event(self, idempotency_key: str) -> bool:
        return idempotency_key in self._processed

    async def mark_event_processed(self, idempotency_key: str) -> None:
        self._processed.add(idempotency_key)


class MockAlertPublisher:
    """In-memory mock for ProtocolAlertPublisher."""

    def __init__(self) -> None:
        self.tool_degraded_calls: list[dict[str, object]] = []
        self.state_updated_calls: list[dict[str, object]] = []

    async def publish_tool_degraded(
        self, *, tool_id: str, reliability_0_1: float, occurred_at_utc: str
    ) -> None:
        self.tool_degraded_calls.append(
            {"tool_id": tool_id, "reliability_0_1": reliability_0_1}
        )

    async def publish_policy_state_updated(self, **kwargs: object) -> None:
        self.state_updated_calls.append(kwargs)


@pytest.mark.unit
class TestNodePolicyStateReducer:
    """Integration tests using mock repository and publisher."""

    def _make_reducer(
        self,
    ) -> tuple[NodePolicyStateReducer, MockRepository, MockAlertPublisher]:
        repo = MockRepository()
        publisher = MockAlertPublisher()
        reducer = NodePolicyStateReducer(
            repository=repo,
            alert_publisher=publisher,
        )
        return reducer, repo, publisher

    # Fixed UUIDs for deterministic tests
    _POLICY_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    _POLICY_ID_BAD = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    _OBJECTIVE_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    def _make_event(
        self,
        event_id: uuid.UUID | None = None,
        policy_id: uuid.UUID | None = None,
        policy_type: str = "tool_reliability",
        reward_delta: float = 0.5,
    ) -> ModelRewardAssignedEvent:
        eid = event_id or uuid.uuid4()
        pid = policy_id or self._POLICY_ID
        return ModelRewardAssignedEvent(
            event_id=eid,
            policy_id=pid,
            policy_type=EnumPolicyType(policy_type),
            reward_delta=reward_delta,
            run_id=uuid.uuid4(),
            objective_id=self._OBJECTIVE_ID,
            occurred_at_utc="2026-02-24T00:00:00Z",
            idempotency_key=f"key-{eid.hex}",
            correctness=0.8,
            safety=0.9,
            cost=0.7,
            latency=0.75,
            maintainability=0.85,
            human_time=0.6,
        )

    @pytest.mark.asyncio
    async def test_first_event_creates_candidate_state(self) -> None:
        reducer, _repo, _ = self._make_reducer()
        event = self._make_event()
        output = await reducer.reduce(ModelPolicyStateInput(event=event))

        # policy_id is returned as str(UUID) by the node
        assert output.policy_id == str(self._POLICY_ID)
        assert output.was_duplicate is False
        assert not output.transition_occurred  # First event: candidate stays candidate

    @pytest.mark.asyncio
    async def test_duplicate_event_returns_was_duplicate(self) -> None:
        reducer, _repo, _ = self._make_reducer()
        eid = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
        event = self._make_event(event_id=eid)
        inp = ModelPolicyStateInput(event=event)

        # First call
        await reducer.reduce(inp)
        # Second call with same idempotency_key
        output2 = await reducer.reduce(inp)

        assert output2.was_duplicate is True
        assert output2.transition_occurred is False

    @pytest.mark.asyncio
    async def test_audit_entry_written_on_first_event(self) -> None:
        reducer, repo, _ = self._make_reducer()
        event = self._make_event()
        await reducer.reduce(ModelPolicyStateInput(event=event))

        assert len(repo.audit_log) == 1
        assert repo.audit_log[0]["policy_id"] == str(self._POLICY_ID)

    @pytest.mark.asyncio
    async def test_auto_blacklist_fires_when_reliability_below_floor(self) -> None:
        """Tool auto-blacklists when reliability drops below blacklist_floor."""
        import json

        reducer, repo, publisher = self._make_reducer()

        bad_pid = self._POLICY_ID_BAD
        bad_pid_str = str(bad_pid)

        # Set up initial state with very low reliability (keyed by str UUID)
        repo._state[(bad_pid_str, "tool_reliability")] = json.dumps(
            {
                "lifecycle_state": "promoted",
                "reliability_0_1": 0.35,
                "blacklisted": False,
            }
        )
        repo._counts[(bad_pid_str, "tool_reliability")] = (100, 70)

        event = self._make_event(
            policy_id=bad_pid,
            reward_delta=-0.9,  # large negative delta
        )
        thresholds = ModelTransitionThresholds(
            blacklist_floor=0.4,  # tool reliability will fall below this
            reliability_floor=0.3,
        )
        output = await reducer.reduce(
            ModelPolicyStateInput(event=event, thresholds=thresholds)
        )

        assert output.blacklisted is True
        assert output.alert_emitted is True
        assert len(publisher.tool_degraded_calls) == 1
        assert publisher.tool_degraded_calls[0]["tool_id"] == bad_pid_str


@pytest.mark.unit
class TestModelRewardAssignedEvent:
    def test_model_construction(self) -> None:
        eid = uuid.uuid4()
        pid = uuid.uuid4()
        event = ModelRewardAssignedEvent(
            event_id=eid,
            policy_id=pid,
            policy_type=EnumPolicyType.TOOL_RELIABILITY,
            reward_delta=0.3,
            run_id=uuid.uuid4(),
            objective_id=uuid.uuid4(),
            occurred_at_utc="2026-02-24T00:00:00Z",
            idempotency_key="key-e1",
            correctness=0.8,
            safety=0.9,
            cost=0.7,
            latency=0.75,
            maintainability=0.85,
            human_time=0.6,
        )
        assert event.policy_type == EnumPolicyType.TOOL_RELIABILITY
        assert event.reward_delta == 0.3
