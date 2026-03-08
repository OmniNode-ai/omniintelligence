# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Protocol definitions for the debug intelligence store.

Ticket: OMN-3556
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProtocolDebugStore(Protocol):
    """Protocol for the debug intelligence data store.

    Provides the 9 operations declared in debug_store.repository.yaml.
    All methods are async. No connection parameter — the adapter manages
    its own connection pool via PostgresRepositoryRuntime.

    Structural typing: adapters do NOT inherit from this protocol.
    isinstance(adapter, ProtocolDebugStore) works at runtime due to
    @runtime_checkable.
    """

    async def upsert_streak(
        self,
        *,
        repo: str,
        branch: str,
        sha: str,
    ) -> dict[str, Any]:
        """Increment (or insert) the streak count for (repo, branch).

        Returns the updated failure_streaks row as a dict.
        """
        ...

    async def reset_streak(
        self,
        *,
        repo: str,
        branch: str,
    ) -> None:
        """Reset streak_count to 0 for (repo, branch) on CI recovery."""
        ...

    async def get_streak(
        self,
        *,
        repo: str,
        branch: str,
    ) -> dict[str, Any] | None:
        """Return the current streak row for (repo, branch), or None if absent."""
        ...

    async def insert_ci_failure_event(
        self,
        *,
        repo: str,
        branch: str,
        sha: str,
        failure_fingerprint: str,
        error_classification: str,
        streak_snapshot: int,
        pr_number: int | None = None,
    ) -> dict[str, Any]:
        """Insert a CI failure event log entry.

        streak_snapshot must be copied from failure_streaks.streak_count.
        Returns the inserted row.
        """
        ...

    async def insert_trigger_record(
        self,
        *,
        repo: str,
        branch: str,
        failure_fingerprint: str,
        error_classification: str,
        observed_bad_sha: str,
        streak_count_at_trigger: int,
    ) -> dict[str, Any]:
        """Create a TriggerRecord when streak threshold is crossed.

        Returns the inserted row.
        """
        ...

    async def find_open_trigger_record(
        self,
        *,
        repo: str,
        branch: str,
    ) -> dict[str, Any] | None:
        """Find the most recent unresolved TriggerRecord for (repo, branch).

        Returns None if no open trigger exists.
        """
        ...

    async def try_mark_trigger_resolved(
        self,
        *,
        trigger_record_id: str,
        fix_record_id: str,
    ) -> bool:
        """Atomically mark trigger as resolved and link fix record.

        Returns True if the update succeeded (we won the race).
        Returns False if the trigger was already resolved (race lost).
        """
        ...

    async def insert_fix_record(
        self,
        *,
        trigger_record_id: str,
        repo: str,
        sha: str,
        regression_test_added: bool,
        pr_number: int | None = None,
    ) -> dict[str, Any]:
        """Create a FixRecord when CI recovers.

        Returns the inserted row.
        """
        ...

    async def query_fix_records(
        self,
        *,
        failure_fingerprint: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query fix records for a fingerprint, ordered by recency (newest first).

        Only returns fix records that are confirmed by the trigger_record join
        (guards against orphaned fix records from race conditions).
        """
        ...


__all__ = ["ProtocolDebugStore"]
