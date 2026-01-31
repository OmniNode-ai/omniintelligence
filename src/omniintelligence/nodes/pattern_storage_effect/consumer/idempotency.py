# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Idempotency gate for Kafka consumer event deduplication.

Uses INSERT ON CONFLICT DO NOTHING RETURNING pattern to atomically
check and mark events as processed. This avoids SELECT-then-INSERT
race conditions.

Reference: OMN-1669 (STORE-004)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from asyncpg import Connection as AsyncConnection

logger = logging.getLogger(__name__)


class IdempotencyGate:
    """Gate for checking and marking events as processed.

    Uses a single SQL statement with ON CONFLICT DO NOTHING RETURNING
    to atomically detect duplicates:
    - If RETURNING yields the event_id -> first time -> proceed
    - If RETURNING yields nothing -> duplicate -> skip
    """

    async def check_and_mark(
        self,
        conn: "AsyncConnection",
        event_id: UUID,
    ) -> bool:
        """Check if event is new and mark it as processed.

        Uses INSERT ON CONFLICT DO NOTHING RETURNING for atomic dedupe.

        Args:
            conn: Database connection (must be within caller's transaction)
            event_id: The event ID to check (idempotency key)

        Returns:
            True if event is new (first time seen), False if duplicate
        """
        result = await conn.fetchval(
            """
            INSERT INTO processed_events (event_id)
            VALUES ($1)
            ON CONFLICT DO NOTHING
            RETURNING event_id
            """,
            event_id,
        )

        is_new = result is not None

        if not is_new:
            logger.info(
                "dedupe.skip",
                extra={"event_id": str(event_id), "reason": "already_processed"},
            )

        return is_new


async def cleanup_processed_events(
    conn: "AsyncConnection",
    retention_days: int = 7,
) -> int:
    """Delete processed events older than retention period.

    Args:
        conn: Database connection
        retention_days: Number of days to retain events (default 7)

    Returns:
        Number of rows deleted
    """
    result = await conn.execute(
        """
        DELETE FROM processed_events
        WHERE processed_at < NOW() - INTERVAL '1 day' * $1
        """,
        retention_days,
    )
    # asyncpg returns "DELETE N" string
    deleted_count = int(result.split()[-1])

    logger.info(
        "processed_events.cleanup",
        extra={"deleted_count": deleted_count, "retention_days": retention_days},
    )

    return deleted_count
