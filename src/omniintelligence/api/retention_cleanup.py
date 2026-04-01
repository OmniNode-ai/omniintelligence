# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Periodic retention cleanup for omniintelligence tables.

Deletes rows older than retention_days from:
- agent_actions (tool_use logs, ~97K rows unbounded)
- learned_patterns where status = 'candidate' and older than 14 days

OMN-7013: Prevents unbounded table growth by running batched DELETEs
on a configurable interval.
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

RETENTION_DAYS = int(os.environ.get("OMNIINTELLIGENCE_RETENTION_DAYS", "30"))
CLEANUP_INTERVAL_SECONDS = int(
    os.environ.get("OMNIINTELLIGENCE_CLEANUP_INTERVAL_SECONDS", "600"),
)

_CLEANUP_SQL_AGENT_ACTIONS = """
DELETE FROM agent_actions
WHERE ctid IN (
    SELECT ctid FROM agent_actions
    WHERE created_at < NOW() - MAKE_INTERVAL(days => $1)
    LIMIT 5000
)
"""

_CLEANUP_SQL_STALE_CANDIDATES = """
DELETE FROM learned_patterns
WHERE ctid IN (
    SELECT ctid FROM learned_patterns
    WHERE status = 'candidate'
      AND created_at < NOW() - INTERVAL '14 days'
    LIMIT 1000
)
"""


async def run_retention_cleanup(pool: asyncpg.Pool) -> dict[str, int]:
    """Run one cleanup pass. Returns counts of deleted rows per table.

    Uses asyncpg's conn.execute() which returns a status string like "DELETE 50".
    We parse the row count from the status string.
    """
    counts: dict[str, int] = {}

    def _parse_row_count(status: str) -> int:
        """Parse row count from asyncpg status string (e.g. 'DELETE 50')."""
        try:
            return int(status.split()[-1])
        except (ValueError, IndexError):
            return 0

    async with pool.acquire() as conn:
        result = await conn.execute(_CLEANUP_SQL_AGENT_ACTIONS, RETENTION_DAYS)
        counts["agent_actions"] = _parse_row_count(result)

        result = await conn.execute(_CLEANUP_SQL_STALE_CANDIDATES)
        counts["learned_patterns_candidates"] = _parse_row_count(result)

    total = sum(counts.values())
    if total > 0:
        logger.info("retention-cleanup deleted %d rows: %s", total, counts)

    return counts


async def start_retention_loop(pool: asyncpg.Pool) -> None:
    """Run cleanup in a loop. Call via asyncio.create_task()."""
    logger.info(
        "retention-cleanup starting: retention=%dd, interval=%ds",
        RETENTION_DAYS,
        CLEANUP_INTERVAL_SECONDS,
    )
    while True:
        try:
            await run_retention_cleanup(pool)
        except Exception:
            logger.exception("retention-cleanup failed")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
