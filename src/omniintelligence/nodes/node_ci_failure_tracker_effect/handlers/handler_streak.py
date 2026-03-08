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


__all__ = [
    "get_current_streak",
    "increment_streak",
    "reset_streak",
]
