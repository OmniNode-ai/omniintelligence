# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""NodePolicyStateReducer — durable policy lifecycle state management.

This node implements the policy state machine from OMN-2361 design doc Section 8.

It is a REDUCER node: consumes RewardAssignedEvent from Kafka, updates
PostgreSQL policy_state, and emits PolicyStateUpdatedEvent.

Lifecycle transitions (table-driven from ObjectiveSpec thresholds):
    CANDIDATE → VALIDATED  when N positive-signal runs observed
    VALIDATED → PROMOTED   when statistical significance threshold met
    PROMOTED  → DEPRECATED when reliability falls below hard floor

Auto-blacklist:
    When tool reliability_0_1 < blacklist_floor:
    - Tool is marked blacklisted in policy_state
    - system.alert.tool_degraded event is emitted

Idempotency:
    Replaying the same RewardAssignedEvent (same idempotency_key) produces
    no double-update. The processed_events table tracks seen keys.

Does NOT:
    - Compute rewards (that's ScoringReducerCompute)
    - Score evidence (that's NodeScoringReducerCompute)
    - Own Kafka consumer lifecycle (injected via protocol)

Related:
    - OMN-2537: Core data models
    - OMN-2545: ScoringReducerCompute (upstream)
    - OMN-2361: Objective Functions epic
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from omniintelligence.nodes.node_policy_state_reducer.handlers.handler_lifecycle import (
    apply_reward_delta,
    compute_next_lifecycle_state,
    should_blacklist,
)
from omniintelligence.nodes.node_policy_state_reducer.handlers.protocols import (
    ProtocolAlertPublisher,
    ProtocolPolicyStateRepository,
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
from omniintelligence.nodes.node_policy_state_reducer.models.model_policy_state_output import (
    ModelPolicyStateOutput,
)

logger = logging.getLogger(__name__)


class NodePolicyStateReducer:
    """REDUCER node for durable policy lifecycle state management.

    Processes RewardAssignedEvents and applies lifecycle transitions to
    policy entries in PostgreSQL.

    This class implements the reduction logic directly rather than extending
    NodeReducer, to allow clean dependency injection for testing.
    Dependencies are injected via constructor (testable without DB/Kafka):
        - repository: ProtocolPolicyStateRepository (DB operations)
        - alert_publisher: ProtocolAlertPublisher (Kafka alerts)

    Example:
        ```python
        reducer = NodePolicyStateReducer(
            repository=repository,
            alert_publisher=publisher,
        )
        output = await reducer.reduce(input_data)
        ```
    """

    def __init__(
        self,
        *args: object,
        repository: ProtocolPolicyStateRepository,
        alert_publisher: ProtocolAlertPublisher,
        **kwargs: object,
    ) -> None:
        self._repository = repository
        self._alert_publisher = alert_publisher

    async def reduce(
        self, input_data: ModelPolicyStateInput
    ) -> ModelPolicyStateOutput:
        """Process a RewardAssignedEvent and apply policy lifecycle transitions.

        Args:
            input_data: Input containing the reward event and transition thresholds.

        Returns:
            Output with old/new lifecycle states, transition flag, and alert status.
        """
        event = input_data.event
        thresholds = input_data.thresholds
        now_utc = datetime.now(tz=timezone.utc).isoformat()

        # Idempotency check — skip if already processed
        if await self._repository.is_duplicate_event(event.idempotency_key):
            logger.info(
                "Skipping duplicate event (idempotency_key=%s, policy_id=%s)",
                event.idempotency_key,
                event.policy_id,
            )
            # Return a no-op output without reading old state
            return ModelPolicyStateOutput(
                policy_id=event.policy_id,
                policy_type=event.policy_type,
                old_lifecycle_state=EnumPolicyLifecycleState.CANDIDATE,
                new_lifecycle_state=EnumPolicyLifecycleState.CANDIDATE,
                transition_occurred=False,
                blacklisted=False,
                alert_emitted=False,
                idempotency_key=event.idempotency_key,
                was_duplicate=True,
                updated_at_utc=now_utc,
            )

        # Read current state
        old_state_json = await self._repository.get_current_state_json(
            event.policy_id, event.policy_type
        )
        run_count, failure_count = await self._repository.get_run_counts(
            event.policy_id, event.policy_type
        )

        # Compute initial state from existing state or defaults
        old_state = self._parse_state(old_state_json, event.policy_type)
        old_lifecycle = old_state.get("lifecycle_state", EnumPolicyLifecycleState.CANDIDATE.value)
        old_lifecycle_enum = EnumPolicyLifecycleState(old_lifecycle)
        raw_reliability = old_state.get("reliability_0_1", 1.0)
        old_reliability = float(raw_reliability)  # type: ignore[arg-type]
        already_blacklisted = bool(old_state.get("blacklisted", False))

        # Apply reward delta to compute new reliability and counts
        new_reliability, new_run_count, new_failure_count = apply_reward_delta(
            current_reliability=old_reliability,
            reward_delta=event.reward_delta,
            run_count=run_count,
            failure_count=failure_count,
        )

        # Compute positive signal ratio for CANDIDATE → VALIDATED check
        positive_runs = new_run_count - new_failure_count
        positive_signal_ratio = positive_runs / max(new_run_count, 1)

        # Compute next lifecycle state (table-driven, no hardcoded chains)
        new_lifecycle_enum = compute_next_lifecycle_state(
            current_state=old_lifecycle_enum,
            reliability_0_1=new_reliability,
            run_count=new_run_count,
            positive_signal_ratio=positive_signal_ratio,
            thresholds=thresholds,
        )
        transition_occurred = new_lifecycle_enum != old_lifecycle_enum

        # Check auto-blacklist (tool_reliability only)
        blacklisted = False
        alert_emitted = False
        if event.policy_type == EnumPolicyType.TOOL_RELIABILITY:
            if should_blacklist(new_reliability, thresholds, already_blacklisted):
                blacklisted = True
                alert_emitted = True
                logger.warning(
                    "Auto-blacklisting tool '%s': reliability=%.3f < floor=%.3f",
                    event.policy_id,
                    new_reliability,
                    thresholds.blacklist_floor,
                )
                await self._alert_publisher.publish_tool_degraded(
                    tool_id=event.policy_id,
                    reliability_0_1=new_reliability,
                    occurred_at_utc=now_utc,
                )
            elif already_blacklisted:
                blacklisted = True  # preserve existing blacklist

        # Build new state JSON
        new_state = self._build_state_json(
            old_state=old_state,
            policy_type=event.policy_type,
            new_reliability=new_reliability,
            new_run_count=new_run_count,
            new_failure_count=new_failure_count,
            new_lifecycle=new_lifecycle_enum,
            blacklisted=blacklisted,
            updated_at_utc=now_utc,
        )
        new_state_json = json.dumps(new_state, sort_keys=True)
        old_state_json_str = json.dumps(old_state, sort_keys=True)

        # Persist updated state
        await self._repository.upsert_state(
            policy_id=event.policy_id,
            policy_type=event.policy_type,
            lifecycle_state_value=new_lifecycle_enum.value,
            state_json=new_state_json,
            run_count=new_run_count,
            failure_count=new_failure_count,
            blacklisted=blacklisted,
            updated_at_utc=now_utc,
        )

        # Write audit entry
        await self._repository.write_audit_entry(
            policy_id=event.policy_id,
            policy_type=event.policy_type,
            event_id=event.event_id,
            idempotency_key=event.idempotency_key,
            old_lifecycle_state=old_lifecycle_enum.value,
            new_lifecycle_state=new_lifecycle_enum.value,
            transition_occurred=transition_occurred,
            old_state_json=old_state_json_str,
            new_state_json=new_state_json,
            reward_delta=event.reward_delta,
            run_id=event.run_id,
            objective_id=event.objective_id,
            blacklisted=blacklisted,
            alert_emitted=alert_emitted,
            occurred_at_utc=event.occurred_at_utc,
        )

        # Mark event as processed (idempotency)
        await self._repository.mark_event_processed(event.idempotency_key)

        # Emit PolicyStateUpdatedEvent if transition occurred
        if transition_occurred:
            await self._alert_publisher.publish_policy_state_updated(
                policy_id=event.policy_id,
                policy_type=event.policy_type.value,
                old_lifecycle_state=old_lifecycle_enum.value,
                new_lifecycle_state=new_lifecycle_enum.value,
                occurred_at_utc=now_utc,
            )

        logger.info(
            "PolicyState updated: policy_id=%s type=%s %s→%s "
            "reliability=%.3f runs=%d blacklisted=%s",
            event.policy_id,
            event.policy_type.value,
            old_lifecycle_enum.value,
            new_lifecycle_enum.value,
            new_reliability,
            new_run_count,
            blacklisted,
        )

        return ModelPolicyStateOutput(
            policy_id=event.policy_id,
            policy_type=event.policy_type,
            old_lifecycle_state=old_lifecycle_enum,
            new_lifecycle_state=new_lifecycle_enum,
            transition_occurred=transition_occurred,
            blacklisted=blacklisted,
            alert_emitted=alert_emitted,
            idempotency_key=event.idempotency_key,
            was_duplicate=False,
            updated_at_utc=now_utc,
        )

    def _parse_state(
        self, state_json: str | None, policy_type: EnumPolicyType
    ) -> dict[str, object]:
        """Parse existing state JSON or return defaults for a new policy entry."""
        if state_json is None:
            return self._default_state(policy_type)
        try:
            parsed = json.loads(state_json)
            if isinstance(parsed, dict):
                return parsed
            return self._default_state(policy_type)
        except json.JSONDecodeError:
            logger.warning("Failed to parse state_json for policy, using defaults.")
            return self._default_state(policy_type)

    def _default_state(self, policy_type: EnumPolicyType) -> dict[str, object]:
        """Return default state for a new policy entry."""
        return {
            "lifecycle_state": EnumPolicyLifecycleState.CANDIDATE.value,
            "reliability_0_1": 1.0,
            "run_count": 0,
            "failure_count": 0,
            "blacklisted": False,
        }

    def _build_state_json(
        self,
        old_state: dict[str, object],
        policy_type: EnumPolicyType,
        new_reliability: float,
        new_run_count: int,
        new_failure_count: int,
        new_lifecycle: EnumPolicyLifecycleState,
        blacklisted: bool,
        updated_at_utc: str,
    ) -> dict[str, object]:
        """Build updated state dict from old state + new computed values."""
        updated = dict(old_state)
        updated["lifecycle_state"] = new_lifecycle.value
        updated["run_count"] = new_run_count
        updated["failure_count"] = new_failure_count
        updated["blacklisted"] = blacklisted
        updated["updated_at_utc"] = updated_at_utc
        if policy_type == EnumPolicyType.TOOL_RELIABILITY:
            updated["reliability_0_1"] = new_reliability
        return updated


__all__ = ["NodePolicyStateReducer"]
