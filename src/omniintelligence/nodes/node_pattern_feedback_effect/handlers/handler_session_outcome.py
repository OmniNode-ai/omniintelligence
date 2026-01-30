# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for session outcome recording with rolling window metrics.

This module implements the pattern feedback loop: when a Claude Code session
completes (success or failure), we update the rolling metrics for all patterns
that were injected during that session.

Rolling Window Decay Approximation:
-----------------------------------
We maintain rolling_20 counters that approximate the last ROLLING_WINDOW_SIZE
injections. Since true sliding windows require storing per-injection timestamps,
we use a decay approximation:

- When adding a success: increment success_count, decrement failure_count if at cap
- When adding a failure: increment failure_count, decrement success_count if at cap

This ensures:
1. Counters never exceed ROLLING_WINDOW_SIZE (the window size)
2. The ratio reflects recent performance, not all-time performance
3. Old outcomes are "forgotten" as new ones arrive

Reference:
    - OMN-1678: Implement rolling window metric updates with decay approximation
    - OMN-1677: Pattern feedback effect node foundation

Design Principles:
    - Pure handler functions with injected repository
    - Protocol-based dependency injection for testability
    - asyncpg-style positional parameters ($1, $2, etc.)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
    ModelSessionOutcomeResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

ROLLING_WINDOW_SIZE: int = 20
"""The number of recent injections tracked for rolling window metrics.

This constant defines the size of the rolling window used for pattern
performance metrics. The rolling window approximates tracking the last
N injections per pattern using a decay algorithm rather than storing
individual timestamps.

When metrics reach this cap:
- New outcomes increment their respective counter (success/failure)
- The opposite counter is decremented to approximate "forgetting" old data
- Total injection count is capped at this value

Database columns (injection_count_rolling_20, success_count_rolling_20,
failure_count_rolling_20) use this value in their naming convention.
Changing this constant requires a corresponding database migration.
"""


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    This protocol defines the minimal interface required for database operations
    in the session outcome handler. It is intentionally generic to support both
    asyncpg connections and mock implementations for testing.

    The methods mirror asyncpg.Connection semantics:
        - fetch: Execute query and return list of Records
        - execute: Execute query and return status string (e.g., "UPDATE 5")

    Note:
        Parameters use asyncpg-style positional placeholders ($1, $2, etc.)
        rather than named parameters.
    """

    async def fetch(self, query: str, *args: Any) -> list[Mapping[str, Any]]:
        """Execute a query and return all results as Records.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            List of record objects with dict-like access to columns.
        """
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status string.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            Status string from PostgreSQL (e.g., "UPDATE 5", "INSERT 0 1").
        """
        ...


# =============================================================================
# SQL Queries
# =============================================================================

# Query to find pattern injections for a session that haven't had outcomes recorded
SQL_FIND_UNRECORDED_INJECTIONS = """
SELECT injection_id, pattern_ids
FROM pattern_injections
WHERE session_id = $1
  AND outcome_recorded = FALSE
"""

# Query to mark injections as having their outcome recorded
SQL_MARK_INJECTIONS_RECORDED = """
UPDATE pattern_injections
SET
    outcome_recorded = TRUE,
    outcome_success = $2,
    outcome_failure_reason = $3,
    outcome_recorded_at = NOW()
WHERE session_id = $1
  AND outcome_recorded = FALSE
"""

# SQL for updating rolling metrics on SUCCESS
# - Increment injection_count (cap at ROLLING_WINDOW_SIZE)
# - Increment success_count (cap at ROLLING_WINDOW_SIZE)
# - Decay failure_count if at cap (approximates sliding window)
# - Reset failure_streak to 0
SQL_UPDATE_METRICS_SUCCESS = f"""
UPDATE learned_patterns
SET
    injection_count_rolling_20 = LEAST(injection_count_rolling_20 + 1, {ROLLING_WINDOW_SIZE}),
    success_count_rolling_20 = LEAST(success_count_rolling_20 + 1, {ROLLING_WINDOW_SIZE}),
    failure_count_rolling_20 = CASE
        WHEN injection_count_rolling_20 >= {ROLLING_WINDOW_SIZE} AND failure_count_rolling_20 > 0
        THEN failure_count_rolling_20 - 1
        ELSE failure_count_rolling_20
    END,
    failure_streak = 0,
    updated_at = NOW()
WHERE id = ANY($1)
"""

# SQL for updating rolling metrics on FAILURE
# - Increment injection_count (cap at ROLLING_WINDOW_SIZE)
# - Increment failure_count (cap at ROLLING_WINDOW_SIZE)
# - Decay success_count if at cap (approximates sliding window)
# - Increment failure_streak
SQL_UPDATE_METRICS_FAILURE = f"""
UPDATE learned_patterns
SET
    injection_count_rolling_20 = LEAST(injection_count_rolling_20 + 1, {ROLLING_WINDOW_SIZE}),
    failure_count_rolling_20 = LEAST(failure_count_rolling_20 + 1, {ROLLING_WINDOW_SIZE}),
    success_count_rolling_20 = CASE
        WHEN injection_count_rolling_20 >= {ROLLING_WINDOW_SIZE} AND success_count_rolling_20 > 0
        THEN success_count_rolling_20 - 1
        ELSE success_count_rolling_20
    END,
    failure_streak = failure_streak + 1,
    updated_at = NOW()
WHERE id = ANY($1)
"""


# =============================================================================
# Handler Functions
# =============================================================================


async def record_session_outcome(
    session_id: UUID,
    success: bool,
    failure_reason: str | None = None,
    *,
    repository: ProtocolPatternRepository,
    correlation_id: UUID | None = None,
) -> ModelSessionOutcomeResult:
    """Record the outcome of a Claude Code session and update pattern metrics.

    This is the main entry point for the pattern feedback loop. When a session
    completes, we:
    1. Find all pattern_injections for this session that haven't been processed
    2. Mark them as processed with the outcome
    3. Update rolling metrics for all unique patterns involved

    Args:
        session_id: The Claude Code session ID.
        success: Whether the session succeeded.
        failure_reason: Optional reason for failure (ignored if success=True).
        repository: Database repository implementing ProtocolPatternRepository.
        correlation_id: Optional correlation ID for distributed tracing.

    Returns:
        ModelSessionOutcomeResult with status and counts of updated records.

    Raises:
        Exception: Propagates database errors for caller to handle.

    Note:
        Transaction Handling: This function executes multiple queries (fetch,
        then two updates) without explicit transaction management. If atomicity
        is required, the caller must provide a repository/connection that is
        already within a transaction context. Without a transaction, if a query
        fails mid-execution (e.g., the second update fails after the first
        succeeds), data may be left in an inconsistent state where injections
        are marked as recorded but pattern metrics are not updated.
    """
    logger.info(
        "Recording session outcome",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "success": success,
        },
    )

    # Step 1: Find unrecorded injections for this session
    injection_rows = await repository.fetch(
        SQL_FIND_UNRECORDED_INJECTIONS,
        session_id,
    )

    # Handle edge cases
    if not injection_rows:
        # No injections found - could be already recorded or no patterns were injected
        # Check if there are any injections at all for this session
        check_result = await repository.fetch(
            "SELECT COUNT(*) as count FROM pattern_injections WHERE session_id = $1",
            session_id,
        )
        has_any = check_result[0]["count"] > 0 if check_result else False

        if has_any:
            # Injections exist but all already recorded
            logger.info(
                "Session outcome already recorded",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "session_id": str(session_id),
                },
            )
            return ModelSessionOutcomeResult(
                status=EnumOutcomeRecordingStatus.ALREADY_RECORDED,
                session_id=session_id,
                injections_updated=0,
                patterns_updated=0,
                pattern_ids=[],
                recorded_at=None,
                error_message=None,
            )
        else:
            # No injections for this session at all
            logger.info(
                "No pattern injections found for session",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "session_id": str(session_id),
                },
            )
            return ModelSessionOutcomeResult(
                status=EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND,
                session_id=session_id,
                injections_updated=0,
                patterns_updated=0,
                pattern_ids=[],
                recorded_at=None,
                error_message=None,
            )

    # Step 2: Collect unique pattern IDs (flatten arrays from all injections)
    pattern_ids: list[UUID] = list(
        {pid for row in injection_rows for pid in (row["pattern_ids"] or [])}
    )

    # Step 3: Mark injections as recorded
    # Clear failure_reason if success (don't store stale error messages)
    effective_failure_reason = failure_reason if not success else None

    update_status = await repository.execute(
        SQL_MARK_INJECTIONS_RECORDED,
        session_id,
        success,
        effective_failure_reason,
    )

    # Parse number of updated rows from status string (e.g., "UPDATE 5")
    injections_updated = _parse_update_count(update_status)

    logger.debug(
        "Marked injections as recorded",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "injections_updated": injections_updated,
            "pattern_count": len(pattern_ids),
        },
    )

    # Step 4: Update rolling metrics for all patterns
    patterns_updated = 0
    if pattern_ids:
        patterns_updated = await update_pattern_rolling_metrics(
            pattern_ids=pattern_ids,
            success=success,
            repository=repository,
        )

    logger.debug(
        "Updated pattern rolling metrics",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "patterns_updated": patterns_updated,
            "success": success,
        },
    )

    return ModelSessionOutcomeResult(
        status=EnumOutcomeRecordingStatus.SUCCESS,
        session_id=session_id,
        injections_updated=injections_updated,
        patterns_updated=patterns_updated,
        pattern_ids=pattern_ids,
        recorded_at=datetime.now(UTC),
        error_message=None,
    )


async def update_pattern_rolling_metrics(
    pattern_ids: list[UUID],
    success: bool,
    *,
    repository: ProtocolPatternRepository,
) -> int:
    """Update rolling window metrics for a list of patterns.

    This function implements the decay approximation for rolling windows.
    Instead of tracking per-injection timestamps, we maintain counters that
    decay the opposite bucket when at capacity (ROLLING_WINDOW_SIZE).

    For SUCCESS:
        - injection_count_rolling_20 = min(current + 1, ROLLING_WINDOW_SIZE)
        - success_count_rolling_20 = min(current + 1, ROLLING_WINDOW_SIZE)
        - failure_count_rolling_20 = current - 1 (if at cap and > 0)
        - failure_streak = 0

    For FAILURE:
        - injection_count_rolling_20 = min(current + 1, ROLLING_WINDOW_SIZE)
        - failure_count_rolling_20 = min(current + 1, ROLLING_WINDOW_SIZE)
        - success_count_rolling_20 = current - 1 (if at cap and > 0)
        - failure_streak = current + 1

    Args:
        pattern_ids: List of pattern UUIDs to update.
        success: Whether this was a successful outcome.
        repository: Database repository implementing ProtocolPatternRepository.

    Returns:
        Number of patterns updated (from SQL UPDATE count).
    """
    if not pattern_ids:
        return 0

    # Select appropriate SQL based on outcome
    sql = SQL_UPDATE_METRICS_SUCCESS if success else SQL_UPDATE_METRICS_FAILURE

    # Execute update
    status = await repository.execute(sql, pattern_ids)

    return _parse_update_count(status)


def _parse_update_count(status: str | None) -> int:
    """Parse the row count from a PostgreSQL status string.

    PostgreSQL returns status strings like:
        - "UPDATE 5" (5 rows updated)
        - "INSERT 0 1" (1 row inserted)
        - "DELETE 3" (3 rows deleted)

    Args:
        status: PostgreSQL status string from execute(), or None.

    Returns:
        Number of affected rows, or 0 if status is None or parsing fails.

    Examples:
        >>> _parse_update_count("UPDATE 5")
        5
        >>> _parse_update_count("INSERT 0 1")
        1
        >>> _parse_update_count("DELETE 0")
        0
        >>> _parse_update_count(None)
        0
    """
    if not status:
        return 0

    parts = status.split()
    if len(parts) >= 2:
        try:
            # For UPDATE/DELETE, count is second part
            # For INSERT, count is third part (INSERT oid count)
            return int(parts[-1])
        except ValueError:
            return 0
    return 0


__all__ = [
    "ROLLING_WINDOW_SIZE",
    "ProtocolPatternRepository",
    "record_session_outcome",
    "update_pattern_rolling_metrics",
]
