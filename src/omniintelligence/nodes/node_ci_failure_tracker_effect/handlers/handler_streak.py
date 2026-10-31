# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Streak management — all reads/writes go through failure_streaks table.

INVARIANT: Never compute consecutive count by querying ci_failure_events.
           failure_streaks.streak_count is the ONLY source of truth.

Ticket: OMN-3556
"""

from __future__ import annotations

from typing import Any

from omniintelligence.debug_intel.protocols import ProtocolDebugStore
from omniintelligence.nodes.node_ci_failure_tracker_effect.models import (
    ModelStreakIncrementRequest,
    ModelStreakQueryRequest,
    ModelStreakResetRequest,
)


async def increment_streak(
    repo: str,
    branch: str,
    sha: str,
    store: ProtocolDebugStore,
) -> dict[str, Any]:
    """Increment streak count in failure_streaks and return updated row."""
    return await store.upsert_streak(repo=repo, branch=branch, sha=sha)


async def reset_streak(
    repo: str,
    branch: str,
    store: ProtocolDebugStore,
) -> None:
    """Reset streak to 0 on CI recovery."""
    await store.reset_streak(repo=repo, branch=branch)


async def get_current_streak(
    repo: str,
    branch: str,
    store: ProtocolDebugStore,
) -> int:
    """Return current streak_count from failure_streaks. Returns 0 if no row exists."""
    row = await store.get_streak(repo=repo, branch=branch)
    if row is None:
        return 0
    return int(row["streak_count"])


class HandlerStreak:
    """Typed entry points for the preserved streak management functions."""

    def __init__(self, store: ProtocolDebugStore) -> None:
        self._store = store

    async def handle(self, request: ModelStreakIncrementRequest) -> dict[str, Any]:
        """Increment the failure streak using the injected store."""
        return await increment_streak(
            repo=request.repo,
            branch=request.branch,
            sha=request.sha,
            store=self._store,
        )

    async def reset(self, request: ModelStreakResetRequest) -> None:
        """Reset the failure streak on recovery."""
        await reset_streak(repo=request.repo, branch=request.branch, store=self._store)

    async def current(self, request: ModelStreakQueryRequest) -> int:
        """Read the current failure streak."""
        return await get_current_streak(
            repo=request.repo, branch=request.branch, store=self._store
        )


__all__ = [
    "HandlerStreak",
    "get_current_streak",
    "increment_streak",
    "reset_streak",
]
