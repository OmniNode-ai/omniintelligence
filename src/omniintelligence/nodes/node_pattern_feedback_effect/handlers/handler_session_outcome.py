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

Contribution Heuristics (OMN-1679):
-----------------------------------
When recording outcomes, we compute contribution heuristics to attribute
the outcome to individual patterns. This is explicitly a HEURISTIC, not
causal attribution - multi-injection sessions make true attribution impossible.

Three methods are supported:
- EQUAL_SPLIT: Each pattern gets 1/N credit
- RECENCY_WEIGHTED: Later patterns get more credit (linear ramp)
- FIRST_MATCH: All credit to the first pattern

Idempotency: Heuristics are only computed for injections where
contribution_heuristic IS NULL, preventing retry overwrites.

Reference:
    - OMN-1679: FEEDBACK-004 contribution heuristic for outcome attribution
    - OMN-1678: Implement rolling window metric updates with decay approximation
    - OMN-1677: Pattern feedback effect node foundation

Design Principles:
    - Pure handler functions with injected repository
    - Protocol-based dependency injection for testability
    - asyncpg-style positional parameters ($1, $2, etc.)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, TypedDict, runtime_checkable
from uuid import UUID

from omnibase_core.integrations.claude_code import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
)

from omniintelligence.enums import EnumHeuristicMethod
from omniintelligence.nodes.node_pattern_feedback_effect.handlers.heuristics import (
    apply_heuristic,
)
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
# ORDER BY (injected_at, injection_id) is canonical for deterministic ordering
SQL_FIND_UNRECORDED_INJECTIONS = """
SELECT injection_id, pattern_ids
FROM pattern_injections
WHERE session_id = $1
  AND outcome_recorded = FALSE
ORDER BY injected_at ASC, injection_id ASC
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

# SQL for updating contribution heuristics on a single injection
# Idempotency: only update if contribution_heuristic IS NULL
# This prevents retry overwrites and preserves debugging history
SQL_UPDATE_INJECTION_HEURISTIC = """
UPDATE pattern_injections
SET
    contribution_heuristic = $2,
    heuristic_method = $3,
    heuristic_confidence = $4,
    updated_at = NOW()
WHERE injection_id = $1
  AND contribution_heuristic IS NULL
"""

# SQL for recomputing effectiveness score (quality_score) from rolling metrics
# Runs AFTER rolling metrics are updated so it reads the new values.
# Formula: success_count / injection_count (pure success ratio)
# Default: 0.5 when no injections recorded (neutral prior)
# Returns the updated scores for inclusion in handler result.
SQL_UPDATE_EFFECTIVENESS_SCORE = """
UPDATE learned_patterns
SET
    quality_score = CASE
        WHEN injection_count_rolling_20 > 0
        THEN success_count_rolling_20::FLOAT / injection_count_rolling_20::FLOAT
        ELSE 0.5
    END,
    updated_at = NOW()
WHERE id = ANY($1)
"""

# SQL for fetching effectiveness scores after update
SQL_FETCH_EFFECTIVENESS_SCORES = """
SELECT id, quality_score
FROM learned_patterns
WHERE id = ANY($1)
"""


# =============================================================================
# Type Definitions
# =============================================================================


class HandlerArgs(TypedDict):
    """Typed dictionary for session outcome handler arguments.

    This provides type safety for the boundary mapping from
    ClaudeSessionOutcome events to handler function parameters.
    """

    session_id: UUID
    success: bool
    failure_reason: str | None
    correlation_id: UUID | None


# =============================================================================
# Boundary Mapping Functions
# =============================================================================


def _outcome_to_success(outcome: ClaudeCodeSessionOutcome) -> bool:
    """Map outcome enum to success boolean for metrics.

    Deterministic mapping:
    - SUCCESS -> True
    - FAILED, ABANDONED, UNKNOWN -> False
    """
    return bool(outcome == ClaudeCodeSessionOutcome.SUCCESS)


def _extract_failure_reason(event: ClaudeSessionOutcome) -> str | None:
    """Extract failure reason from event error details.

    Returns None if no error, otherwise a stable summary string.
    """
    if event.error is None:
        return None
    # Prefer message, fallback to code
    message = getattr(event.error, "message", None)
    if message:
        return str(message)
    code = getattr(event.error, "code", None)
    if code:
        return str(code)
    return "Unknown error"


def event_to_handler_args(event: ClaudeSessionOutcome) -> HandlerArgs:
    """Convert ClaudeSessionOutcome event to handler arguments.

    This is the boundary mapping that keeps the handler stable
    while accepting the new enum-based input model.
    """
    return {
        "session_id": event.session_id,
        "success": _outcome_to_success(event.outcome),
        "failure_reason": _extract_failure_reason(event),
        "correlation_id": event.correlation_id,
    }


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
    heuristic_method: EnumHeuristicMethod = EnumHeuristicMethod.EQUAL_SPLIT,
) -> ModelSessionOutcomeResult:
    """Record the outcome of a Claude Code session and update pattern metrics.

    This is the main entry point for the pattern feedback loop. When a session
    completes, we:
    1. Find all pattern_injections for this session that haven't been processed
    2. Mark them as processed with the outcome
    3. Compute and store contribution heuristics for each injection
    4. Update rolling metrics for all unique patterns involved
    5. Recompute effectiveness scores (quality_score) from updated rolling metrics
    6. Return result with status, counts, pattern_ids, and effectiveness scores

    Args:
        session_id: The Claude Code session ID.
        success: Whether the session succeeded.
        failure_reason: Optional reason for failure (ignored if success=True).
        repository: Database repository implementing ProtocolPatternRepository.
        correlation_id: Optional correlation ID for distributed tracing.
        heuristic_method: Method for computing contribution attribution.
            Defaults to EQUAL_SPLIT. See EnumHeuristicMethod for options.

    Returns:
        ModelSessionOutcomeResult with status, counts, and effectiveness scores.

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

        Heuristic Idempotency: Contribution heuristics are only written for
        injections where contribution_heuristic IS NULL. This prevents retries
        from overwriting previously computed attributions.
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

    # Step 4: Compute and store contribution heuristics
    await compute_and_store_heuristics(
        injection_rows=injection_rows,
        heuristic_method=heuristic_method,
        repository=repository,
    )

    logger.debug(
        "Computed contribution heuristics",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "heuristic_method": heuristic_method.value,
            "injection_count": len(injection_rows),
        },
    )

    # Step 5: Update rolling metrics for all patterns
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

    # Step 6: Recompute effectiveness scores from updated rolling metrics
    # Graceful degradation: if scoring fails, the critical operations
    # (marking injections recorded + updating rolling metrics) already
    # succeeded. Log and continue with empty scores.
    effectiveness_scores: dict[UUID, float] = {}
    if pattern_ids:
        try:
            effectiveness_scores = await update_effectiveness_scores(
                pattern_ids=pattern_ids,
                repository=repository,
            )
        except Exception:
            logger.exception(
                "Failed to update effectiveness scores (non-critical)",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "session_id": str(session_id),
                    "pattern_count": len(pattern_ids),
                },
            )

    logger.debug(
        "Updated effectiveness scores",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "session_id": str(session_id),
            "scores": {str(k): v for k, v in effectiveness_scores.items()},
        },
    )

    return ModelSessionOutcomeResult(
        status=EnumOutcomeRecordingStatus.SUCCESS,
        session_id=session_id,
        injections_updated=injections_updated,
        patterns_updated=patterns_updated,
        pattern_ids=pattern_ids,
        effectiveness_scores=effectiveness_scores,
        recorded_at=datetime.now(UTC),
        error_message=None,
    )


async def compute_and_store_heuristics(
    injection_rows: list[Mapping[str, Any]],
    heuristic_method: EnumHeuristicMethod,
    *,
    repository: ProtocolPatternRepository,
) -> int:
    """Compute and store contribution heuristics for session injections.

    This function computes the contribution weights using the specified heuristic
    method and stores them on each injection record. The computation considers
    all patterns across all injections in canonical order.

    Duplicate Pattern Handling:
        If the same pattern appears in multiple injections, weights are accumulated
        across all occurrences (respecting order for RECENCY_WEIGHTED) and then
        normalized. Each injection row gets the same final weights dictionary.

    Idempotency:
        Only writes to injection rows where contribution_heuristic IS NULL.
        This prevents retry overwrites.

    Args:
        injection_rows: List of injection records from SQL query, each containing:
            - injection_id (UUID)
            - pattern_ids (list[UUID])
        heuristic_method: Method for computing contribution attribution.
        repository: Database repository implementing ProtocolPatternRepository.

    Returns:
        Number of injection rows updated with heuristics.
    """
    if not injection_rows:
        return 0

    # Collect all pattern_ids in canonical order (rows already ordered by injected_at, injection_id)
    ordered_pattern_ids: list[UUID] = []
    for row in injection_rows:
        pattern_ids = row.get("pattern_ids") or []
        ordered_pattern_ids.extend(pattern_ids)

    if not ordered_pattern_ids:
        return 0

    # Compute the heuristic once for the entire session
    weights, confidence = apply_heuristic(
        method=heuristic_method,
        ordered_pattern_ids=ordered_pattern_ids,
    )

    # Serialize weights to JSON string for PostgreSQL
    weights_json = json.dumps(weights)

    # Update each injection row with the heuristic
    # Each injection gets the same session-level weights (the contribution is
    # at the session level, not per-injection)
    updated_count = 0
    for row in injection_rows:
        injection_id = row["injection_id"]
        status = await repository.execute(
            SQL_UPDATE_INJECTION_HEURISTIC,
            injection_id,
            weights_json,
            heuristic_method.value,
            confidence,
        )
        # Check if row was actually updated (idempotency check may skip it)
        if _parse_update_count(status) > 0:
            updated_count += 1

    return updated_count


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


async def update_effectiveness_scores(
    pattern_ids: list[UUID],
    *,
    repository: ProtocolPatternRepository,
) -> dict[UUID, float]:
    """Recompute effectiveness scores from rolling metrics and return updated values.

    This function recalculates the quality_score for each pattern based on
    current rolling window metrics. It should be called AFTER rolling metrics
    have been updated so the computation reflects the latest outcome.

    Formula:
        quality_score = success_count_rolling_20 / injection_count_rolling_20
        Falls back to 0.5 (neutral prior) when injection_count is 0.

    The 0.5 default is a deliberate neutral prior: new patterns with no
    injection history are treated as neither good nor bad. This prevents
    cold-start bias in pattern ranking and promotion decisions.

    Score range: 0.0 (all failures) to 1.0 (all successes).

    Args:
        pattern_ids: List of pattern UUIDs to update.
        repository: Database repository implementing ProtocolPatternRepository.

    Returns:
        Dictionary mapping pattern UUID to updated effectiveness score.
        Empty dict if no patterns provided.
    """
    if not pattern_ids:
        return {}

    # Step 1: Recompute quality_score in the database
    await repository.execute(SQL_UPDATE_EFFECTIVENESS_SCORE, pattern_ids)

    # Step 2: Fetch updated scores
    rows = await repository.fetch(SQL_FETCH_EFFECTIVENESS_SCORES, pattern_ids)

    return {row["id"]: float(row["quality_score"]) for row in rows}


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
    "HandlerArgs",
    "ProtocolPatternRepository",
    "compute_and_store_heuristics",
    "event_to_handler_args",
    "record_session_outcome",
    "update_effectiveness_scores",
    "update_pattern_rolling_metrics",
]
