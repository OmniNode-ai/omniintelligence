# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern promotion from provisional to validated status.

This module implements the pattern promotion logic: checking provisional patterns
against promotion gates and promoting those that meet all criteria. Promotion
decisions are based on rolling window metrics from the pattern feedback loop.

Promotion Gates:
----------------
All four gates must pass for a pattern to be promoted:

1. Injection Count Gate: injection_count_rolling_20 >= MIN_INJECTION_COUNT (5)
   - Pattern must have been used enough times to have meaningful data

2. Success Rate Gate: success_rate >= MIN_SUCCESS_RATE (0.6 / 60%)
   - Calculated as: success_count / (success_count + failure_count)
   - Pattern must demonstrate consistent success

3. Failure Streak Gate: failure_streak < MAX_FAILURE_STREAK (3)
   - Pattern must not be in a recent failure spiral

4. Disabled Gate: Pattern must not be in disabled_patterns_current table
   - Already filtered in SQL query (LEFT JOIN ... IS NULL)

Kafka Publisher Optionality:
----------------------------
The ``kafka_producer`` dependency is OPTIONAL (contract marks it as ``required: false``).
When the Kafka publisher is unavailable (None), promotions still occur in the database,
but ``PatternPromoted`` events are NOT emitted to Kafka.

**Implications of running without Kafka:**

1. **Downstream Cache Staleness**: Services that cache validated patterns and rely on
   Kafka events for cache invalidation will NOT receive promotion notifications.
   Their caches may serve stale data until the next scheduled refresh or manual
   invalidation.

2. **Event Audit Trail**: The Kafka event stream serves as an audit log of promotions.
   Without Kafka, this audit trail is incomplete. Database ``promoted_at`` timestamps
   remain the only promotion record.

3. **Real-time Consumers**: Any real-time consumers subscribed to the
   ``{env}.pattern-promoted.v1`` topic will not receive promotion events.

**When to run without Kafka:**

- **Testing**: Unit and integration tests may skip Kafka for isolation and speed.
  Pass ``producer=None`` to test promotion logic without Kafka infrastructure.

- **Database-only migrations**: When migrating or backfilling promotion status,
  Kafka events may be intentionally skipped to avoid flooding consumers.

- **Degraded mode**: If Kafka is temporarily unavailable, the system can continue
  promoting patterns (database updates succeed) with eventual Kafka reconciliation.

- **Local development**: Developers may not have Kafka running locally. The
  promotion logic works correctly without it.

**Reconciliation Strategy**: When Kafka becomes available after running in
degraded mode, consumers should query the ``learned_patterns`` table for patterns
where ``status = 'validated'`` and ``promoted_at > last_known_event_timestamp``
to reconcile any missed promotions.

Design Principles:
    - Pure functions for criteria evaluation (no I/O)
    - Protocol-based dependency injection for testability
    - Per-pattern transactions (not batch) for reliability
    - Kafka event emission for downstream cache invalidation (when available)
    - Graceful degradation when Kafka is unavailable
    - asyncpg-style positional parameters ($1, $2, etc.)

Reference:
    - OMN-1680: Auto-promote logic for patterns
    - OMN-1678: Rolling window metrics (dependency)
    - OMN-1679: Contribution heuristics (dependency)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.constants import TOPIC_SUFFIX_PATTERN_PROMOTED_V1
from omniintelligence.nodes.node_pattern_promotion_effect.models import (
    ModelGateSnapshot,
    ModelPatternPromotedEvent,
    ModelPromotionCheckResult,
    ModelPromotionResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Promotion Threshold Constants
# =============================================================================

MIN_INJECTION_COUNT: int = 5
"""Minimum number of injections required for promotion eligibility.

A pattern must have been injected at least this many times (in the rolling
window) to have enough data for reliable promotion decisions. This prevents
promoting patterns based on insufficient sample size.

Database column: injection_count_rolling_20
"""

MIN_SUCCESS_RATE: float = 0.6
"""Minimum success rate required for promotion (60%).

Calculated as: success_count_rolling_20 / (success_count_rolling_20 + failure_count_rolling_20)

A pattern must demonstrate at least 60% success rate to be promoted from
provisional to validated status. This threshold balances allowing useful
patterns through while filtering out unreliable ones.
"""

MAX_FAILURE_STREAK: int = 3
"""Maximum consecutive failures allowed for promotion eligibility.

If a pattern has failed this many or more times in a row (failure_streak >= max),
it is NOT eligible for promotion regardless of overall success rate.
This prevents promoting patterns that are currently in a failure spiral.

Threshold Behavior:
    - 0 (zero-tolerance): ANY failure blocks promotion (failure_streak >= 0 always true
      if failure_streak > 0, so a single failure blocks)
    - 1: A single consecutive failure blocks promotion
    - 2: Two consecutive failures block promotion
    - 3 (default): Three consecutive failures block promotion

Note: The check is failure_streak < max_failure_streak, so with the default of 3,
exactly 3 consecutive failures BLOCKS promotion.
"""


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    This protocol defines the minimal interface required for database operations
    in the promotion handler. It is intentionally generic to support both
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


@runtime_checkable
class ProtocolKafkaPublisher(Protocol):
    """Protocol for Kafka event publishers.

    Defines a simplified interface for publishing events to Kafka topics.
    This protocol uses a dict-based value for flexibility, with serialization
    handled by the implementation.
    """

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish an event to a Kafka topic.

        Args:
            topic: Target Kafka topic name.
            key: Message key for partitioning.
            value: Event payload as a dictionary (serialized by implementation).
        """
        ...


# =============================================================================
# SQL Queries
# =============================================================================

# Query to find provisional patterns eligible for promotion check
# Filters out:
#   - Non-provisional patterns (only check provisional status)
#   - Non-current versions (is_current = TRUE)
#   - Disabled patterns (LEFT JOIN with disabled_patterns_current)
SQL_FETCH_PROVISIONAL_PATTERNS = """
SELECT lp.id, lp.pattern_signature,
       lp.injection_count_rolling_20,
       lp.success_count_rolling_20,
       lp.failure_count_rolling_20,
       lp.failure_streak
FROM learned_patterns lp
LEFT JOIN disabled_patterns_current dpc ON lp.id = dpc.pattern_id
WHERE lp.status = 'provisional'
  AND lp.is_current = TRUE
  AND dpc.pattern_id IS NULL
"""

# Query to promote a single pattern
SQL_PROMOTE_PATTERN = """
UPDATE learned_patterns
SET status = 'validated',
    promoted_at = NOW(),
    updated_at = NOW()
WHERE id = $1
  AND status = 'provisional'
"""


# =============================================================================
# Pure Functions
# =============================================================================


def meets_promotion_criteria(
    pattern: Mapping[str, Any],
    *,
    min_injection_count: int = MIN_INJECTION_COUNT,
    min_success_rate: float = MIN_SUCCESS_RATE,
    max_failure_streak: int = MAX_FAILURE_STREAK,
) -> bool:
    """Check if a pattern meets all promotion criteria.

    This is a PURE FUNCTION with no I/O - it only evaluates the pattern
    data against the promotion gates.

    Args:
        pattern: Pattern record from SQL query containing:
            - injection_count_rolling_20: int
            - success_count_rolling_20: int
            - failure_count_rolling_20: int
            - failure_streak: int
        min_injection_count: Minimum number of injections required for promotion.
            Defaults to MIN_INJECTION_COUNT (5).
        min_success_rate: Minimum success rate required for promotion (0.0-1.0).
            Defaults to MIN_SUCCESS_RATE (0.6).
        max_failure_streak: Maximum consecutive failures allowed for promotion.
            Defaults to MAX_FAILURE_STREAK (3). Set to 0 for zero-tolerance mode
            where any failure blocks promotion, or 1 to block on a single failure.

    Returns:
        True if pattern meets ALL four promotion gates:
            1. injection_count_rolling_20 >= min_injection_count
            2. success_rate >= min_success_rate
            3. failure_streak < max_failure_streak
            4. Not disabled (already filtered in query)

    Note:
        Gate 4 (disabled check) is handled in the SQL query via LEFT JOIN.
        This function only evaluates gates 1-3.
    """
    injection_count = pattern.get("injection_count_rolling_20", 0) or 0
    success_count = pattern.get("success_count_rolling_20", 0) or 0
    failure_count = pattern.get("failure_count_rolling_20", 0) or 0
    failure_streak = pattern.get("failure_streak", 0) or 0

    # Gate 1: Minimum injection count
    if injection_count < min_injection_count:
        return False

    # Gate 2: Minimum success rate
    total_outcomes = success_count + failure_count
    if total_outcomes == 0:
        # No outcomes recorded - cannot calculate success rate
        return False

    success_rate = success_count / total_outcomes
    if success_rate < min_success_rate:
        return False

    # Gate 3: Maximum failure streak
    if failure_streak >= max_failure_streak:
        return False

    # All gates passed
    return True


def calculate_success_rate(pattern: Mapping[str, Any]) -> float:
    """Calculate the success rate for a pattern.

    Args:
        pattern: Pattern record containing success_count_rolling_20
            and failure_count_rolling_20.

    Returns:
        Success rate as a float between 0.0 and 1.0.
        Returns 0.0 if no outcomes are recorded.
    """
    success_count = pattern.get("success_count_rolling_20", 0) or 0
    failure_count = pattern.get("failure_count_rolling_20", 0) or 0
    total = success_count + failure_count

    if total == 0:
        return 0.0

    return success_count / total


def build_gate_snapshot(pattern: Mapping[str, Any]) -> ModelGateSnapshot:
    """Build a gate snapshot from pattern data.

    Args:
        pattern: Pattern record from SQL query.

    Returns:
        ModelGateSnapshot capturing the gate values at evaluation time.
    """
    return ModelGateSnapshot(
        success_rate_rolling_20=calculate_success_rate(pattern),
        injection_count_rolling_20=pattern.get("injection_count_rolling_20", 0) or 0,
        failure_streak=pattern.get("failure_streak", 0) or 0,
        disabled=False,  # Already filtered in query
    )


# =============================================================================
# Handler Functions
# =============================================================================


async def check_and_promote_patterns(
    repository: ProtocolPatternRepository,
    producer: ProtocolKafkaPublisher | None = None,
    *,
    dry_run: bool = False,
    min_injection_count: int = MIN_INJECTION_COUNT,
    min_success_rate: float = MIN_SUCCESS_RATE,
    max_failure_streak: int = MAX_FAILURE_STREAK,
    correlation_id: UUID | None = None,
    topic_env_prefix: str = "dev",
) -> ModelPromotionCheckResult:
    """Check and promote eligible provisional patterns.

    This is the main entry point for the promotion workflow. It:
    1. Fetches all provisional patterns (not disabled, is_current)
    2. Evaluates each against promotion gates
    3. If not dry_run: promotes eligible patterns and emits events
    4. Returns aggregated result with all promotion details

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        producer: Optional Kafka producer implementing ProtocolKafkaPublisher.
            If None, Kafka events are not emitted but database promotions still
            occur. See "Kafka Optionality" section in module docstring for
            implications on downstream cache invalidation.
        dry_run: If True, return what WOULD be promoted without mutating.
        min_injection_count: Minimum number of injections required for promotion.
            Defaults to MIN_INJECTION_COUNT (5).
        min_success_rate: Minimum success rate required for promotion (0.0-1.0).
            Defaults to MIN_SUCCESS_RATE (0.6).
        max_failure_streak: Maximum consecutive failures allowed for promotion.
            Defaults to MAX_FAILURE_STREAK (3). Set to 0 for zero-tolerance mode
            where any failure blocks promotion, or 1 to block on a single failure.
        correlation_id: Optional correlation ID for distributed tracing.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").
            Only used when producer is not None.

    Returns:
        ModelPromotionCheckResult with counts and individual promotion results.

    Note:
        Each pattern is promoted in its own transaction (not batch).
        If one promotion fails, others can still succeed.

    Warning:
        When ``producer`` is None, downstream services relying on Kafka events
        for cache invalidation will not be notified. Their pattern caches may
        become stale until manually refreshed or until the next scheduled sync.
    """
    logger.info(
        "Starting promotion check",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "dry_run": dry_run,
        },
    )

    # Step 1: Fetch all provisional patterns
    patterns = await repository.fetch(SQL_FETCH_PROVISIONAL_PATTERNS)

    logger.debug(
        "Fetched provisional patterns",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_count": len(patterns),
        },
    )

    # Step 2: Evaluate each pattern against promotion gates
    eligible_patterns: list[Mapping[str, Any]] = []
    for pattern in patterns:
        if meets_promotion_criteria(
            pattern,
            min_injection_count=min_injection_count,
            min_success_rate=min_success_rate,
            max_failure_streak=max_failure_streak,
        ):
            eligible_patterns.append(pattern)
        else:
            # Check for data inconsistency edge case: pattern has injections but no outcomes
            injection_count = pattern.get("injection_count_rolling_20", 0) or 0
            success_count = pattern.get("success_count_rolling_20", 0) or 0
            failure_count = pattern.get("failure_count_rolling_20", 0) or 0
            total_outcomes = success_count + failure_count

            if injection_count >= min_injection_count and total_outcomes == 0:
                logger.debug(
                    "Pattern has injections but no outcomes - possible data inconsistency",
                    extra={
                        "correlation_id": str(correlation_id) if correlation_id else None,
                        "pattern_id": str(pattern["id"]),
                        "injection_count": injection_count,
                    },
                )

    logger.info(
        "Evaluated promotion criteria",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "patterns_checked": len(patterns),
            "patterns_eligible": len(eligible_patterns),
            "dry_run": dry_run,
        },
    )

    # Step 3: Promote eligible patterns (if not dry_run)
    # Each pattern is processed independently - one failure does not block others
    promotion_results: list[ModelPromotionResult] = []
    failed_count: int = 0
    skipped_noop_count: int = 0

    for pattern in eligible_patterns:
        pattern_id = pattern["id"]
        pattern_signature = pattern.get("pattern_signature", "")

        if dry_run:
            # Dry run: record what WOULD happen
            result = ModelPromotionResult(
                pattern_id=pattern_id,
                pattern_signature=pattern_signature,
                from_status="provisional",
                to_status="validated",
                promoted_at=None,
                reason="auto_promote_rolling_window",
                gate_snapshot=build_gate_snapshot(pattern),
                dry_run=True,
            )
            promotion_results.append(result)
        else:
            # Actual promotion - isolated per-pattern error handling
            try:
                result = await promote_pattern(
                    repository=repository,
                    producer=producer,
                    pattern_id=pattern_id,
                    pattern_data=pattern,
                    correlation_id=correlation_id,
                    topic_env_prefix=topic_env_prefix,
                )

                # Check for no-op (pattern was already promoted or status changed)
                if result.promoted_at is None and not result.dry_run:
                    skipped_noop_count += 1
                    logger.debug(
                        "Skipped no-op promotion",
                        extra={
                            "correlation_id": str(correlation_id) if correlation_id else None,
                            "pattern_id": str(pattern_id),
                            "pattern_signature": pattern_signature,
                            "reason": result.reason,
                        },
                    )

                promotion_results.append(result)

            except Exception as exc:
                # Isolate per-pattern failures - continue processing other patterns
                failed_count += 1
                logger.error(
                    "Failed to promote pattern - continuing with remaining patterns",
                    extra={
                        "correlation_id": str(correlation_id) if correlation_id else None,
                        "pattern_id": str(pattern_id),
                        "pattern_signature": pattern_signature,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                    exc_info=True,
                )
                # Record the failed promotion attempt with error reason
                failed_result = ModelPromotionResult(
                    pattern_id=pattern_id,
                    pattern_signature=pattern_signature,
                    from_status="provisional",
                    to_status="validated",
                    promoted_at=None,
                    reason=f"promotion_failed: {type(exc).__name__}: {exc!s}",
                    gate_snapshot=build_gate_snapshot(pattern),
                    dry_run=False,
                )
                promotion_results.append(failed_result)

    # Calculate actual promotions (excluding no-ops and failures)
    actual_promotions = sum(
        1 for r in promotion_results
        if r.promoted_at is not None and not r.dry_run
    )

    logger.info(
        "Promotion check complete",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "patterns_checked": len(patterns),
            "patterns_eligible": len(eligible_patterns),
            "patterns_promoted": actual_promotions,
            "patterns_skipped_noop": skipped_noop_count,
            "patterns_failed": failed_count,
            "dry_run": dry_run,
        },
    )

    return ModelPromotionCheckResult(
        dry_run=dry_run,
        patterns_checked=len(patterns),
        patterns_eligible=len(eligible_patterns),
        patterns_promoted=promotion_results,
        correlation_id=correlation_id,
    )


async def promote_pattern(
    repository: ProtocolPatternRepository,
    producer: ProtocolKafkaPublisher | None,
    pattern_id: UUID,
    pattern_data: Mapping[str, Any],
    correlation_id: UUID | None = None,
    *,
    topic_env_prefix: str = "dev",
) -> ModelPromotionResult:
    """Promote a single pattern from provisional to validated.

    This function:
    1. Updates the pattern status in the database
    2. Emits a pattern-promoted event to Kafka (if producer available)
    3. Returns the promotion result with gate snapshot

    The database update and Kafka event are NOT transactionally coupled.
    The database update succeeds independently of Kafka availability.

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        producer: Kafka producer implementing ProtocolKafkaPublisher, or None.
            When None, the promotion succeeds in the database but no Kafka event
            is emitted. This is intentional to support:
            - Testing without Kafka infrastructure
            - Degraded operation when Kafka is unavailable
            - Database-only migrations/backfills
            See module docstring "Kafka Publisher Optionality" for cache
            invalidation implications.
        pattern_id: The pattern ID to promote.
        pattern_data: Pattern record from SQL query (for gate snapshot).
        correlation_id: Optional correlation ID for tracing.
        topic_env_prefix: Environment prefix for Kafka topic. Only used when
            producer is not None.

    Returns:
        ModelPromotionResult with promotion details and gate snapshot.
        The ``promoted_at`` field is set regardless of Kafka availability.

    Note:
        Transaction handling is the caller's responsibility. This function
        executes a single UPDATE statement.

    Warning:
        When ``producer`` is None, downstream pattern caches will NOT receive
        invalidation events. The promotion is "silent" from the perspective
        of Kafka consumers. Services should implement periodic reconciliation
        by querying ``learned_patterns`` for recently promoted patterns.
    """
    pattern_signature = pattern_data.get("pattern_signature", "")
    promoted_at = datetime.now(UTC)

    logger.debug(
        "Promoting pattern",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
        },
    )

    # Step 1: Update database
    status = await repository.execute(SQL_PROMOTE_PATTERN, pattern_id)
    rows_updated = _parse_update_count(status)

    if rows_updated == 0:
        logger.warning(
            "Pattern not updated - may have been promoted already or changed status",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "pattern_id": str(pattern_id),
            },
        )
        # Return early without emitting event - pattern wasn't actually promoted
        # Build gate snapshot for diagnostic purposes only
        return ModelPromotionResult(
            pattern_id=pattern_id,
            pattern_signature=pattern_signature,
            from_status="provisional",
            to_status="validated",
            promoted_at=None,  # None indicates no actual promotion occurred
            reason="already_promoted_or_status_changed",
            gate_snapshot=build_gate_snapshot(pattern_data),
            dry_run=False,
        )

    # Step 2: Build gate snapshot
    gate_snapshot = build_gate_snapshot(pattern_data)

    # Step 3: Emit Kafka event (if producer available)
    # NOTE: Kafka is OPTIONAL (contract: required=false). When producer is None,
    # promotions succeed silently without notifying downstream caches. This is
    # intentional for testing, degraded mode, and database-only migrations.
    # See module docstring "Kafka Publisher Optionality" for implications.
    if producer is not None:
        await _emit_promotion_event(
            producer=producer,
            pattern_id=pattern_id,
            pattern_signature=pattern_signature,
            gate_snapshot=gate_snapshot,
            promoted_at=promoted_at,
            correlation_id=correlation_id,
            topic_env_prefix=topic_env_prefix,
        )

    logger.info(
        "Pattern promoted",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
            "success_rate": gate_snapshot.success_rate_rolling_20,
        },
    )

    return ModelPromotionResult(
        pattern_id=pattern_id,
        pattern_signature=pattern_signature,
        from_status="provisional",
        to_status="validated",
        promoted_at=promoted_at,
        reason="auto_promote_rolling_window",
        gate_snapshot=gate_snapshot,
        dry_run=False,
    )


async def _emit_promotion_event(
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    pattern_signature: str,
    gate_snapshot: ModelGateSnapshot,
    promoted_at: datetime,
    correlation_id: UUID | None,
    *,
    topic_env_prefix: str = "dev",
) -> None:
    """Emit a pattern-promoted event to Kafka.

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The promoted pattern ID.
        pattern_signature: The pattern signature.
        gate_snapshot: Gate values at promotion time.
        promoted_at: Promotion timestamp.
        correlation_id: Correlation ID for tracing.
        topic_env_prefix: Environment prefix for topic.
    """
    # Build topic name with environment prefix
    topic = f"{topic_env_prefix}.{TOPIC_SUFFIX_PATTERN_PROMOTED_V1}"

    # Build event payload using the model
    event = ModelPatternPromotedEvent(
        event_type="PatternPromoted",
        pattern_id=pattern_id,
        pattern_signature=pattern_signature,
        from_status="provisional",
        to_status="validated",
        success_rate_rolling_20=gate_snapshot.success_rate_rolling_20,
        promoted_at=promoted_at,
        correlation_id=correlation_id,
    )

    # Publish to Kafka
    await producer.publish(
        topic=topic,
        key=str(pattern_id),
        value=event.model_dump(mode="json"),
    )

    logger.debug(
        "Emitted pattern-promoted event",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "topic": topic,
        },
    )


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
    """
    if not status:
        return 0

    parts = status.split()
    if len(parts) >= 2:
        try:
            return int(parts[-1])
        except ValueError:
            return 0
    return 0


__all__ = [
    "MAX_FAILURE_STREAK",
    "MIN_INJECTION_COUNT",
    "MIN_SUCCESS_RATE",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "build_gate_snapshot",
    "calculate_success_rate",
    "check_and_promote_patterns",
    "meets_promotion_criteria",
    "promote_pattern",
]
