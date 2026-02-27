# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Protocols for PolicyStateReducer external dependencies (OMN-2557)."""

from __future__ import annotations

from typing import Protocol

from omniintelligence.nodes.node_policy_state_reducer.models.enum_policy_type import (
    EnumPolicyType,
)


class ProtocolPolicyStateRepository(Protocol):
    """Protocol for persisting and reading policy state."""

    async def get_current_state_json(
        self, policy_id: str, policy_type: EnumPolicyType
    ) -> str | None:
        """Return the current state_json for a policy entry, or None if not found."""
        ...

    async def get_run_counts(
        self, policy_id: str, policy_type: EnumPolicyType
    ) -> tuple[int, int]:
        """Return (run_count, failure_count) for a policy entry. Returns (0, 0) if new."""
        ...

    async def upsert_state(
        self,
        *,
        policy_id: str,
        policy_type: EnumPolicyType,
        lifecycle_state_value: str,
        state_json: str,
        run_count: int,
        failure_count: int,
        blacklisted: bool,
        updated_at_utc: str,
    ) -> None:
        """Upsert the current policy state."""
        ...

    async def write_audit_entry(
        self,
        *,
        policy_id: str,
        policy_type: EnumPolicyType,
        event_id: str,
        idempotency_key: str,
        old_lifecycle_state: str,
        new_lifecycle_state: str,
        transition_occurred: bool,
        old_state_json: str,
        new_state_json: str,
        reward_delta: float,
        run_id: str,
        objective_id: str,
        blacklisted: bool,
        alert_emitted: bool,
        occurred_at_utc: str,
    ) -> None:
        """Append an audit log entry for this state mutation."""
        ...

    async def is_duplicate_event(self, idempotency_key: str) -> bool:
        """Return True if this idempotency_key has already been processed."""
        ...

    async def mark_event_processed(self, idempotency_key: str) -> None:
        """Mark an idempotency_key as processed."""
        ...


class ProtocolAlertPublisher(Protocol):
    """Protocol for publishing system alerts."""

    async def publish_tool_degraded(
        self, *, tool_id: str, reliability_0_1: float, occurred_at_utc: str
    ) -> None:
        """Publish system.alert.tool_degraded event."""
        ...

    async def publish_policy_state_updated(
        self,
        *,
        policy_id: str,
        policy_type: str,
        old_lifecycle_state: str,
        new_lifecycle_state: str,
        occurred_at_utc: str,
    ) -> None:
        """Publish PolicyStateUpdatedEvent with old_state + new_state snapshots."""
        ...


__all__ = ["ProtocolAlertPublisher", "ProtocolPolicyStateRepository"]
