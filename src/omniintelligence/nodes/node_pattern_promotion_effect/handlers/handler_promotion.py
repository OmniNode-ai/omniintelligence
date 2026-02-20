# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern promotion from provisional to validated status.

This module implements the pattern promotion logic: checking provisional patterns
against promotion gates and emitting lifecycle events for those that meet all
criteria. Promotion decisions are based on rolling window metrics from the pattern
feedback loop.

**Event-Driven Architecture (OMN-1805):**
-----------------------------------------
This handler does NOT directly update pattern status in the database. Instead,
it evaluates promotion gates and emits a ``ModelPatternLifecycleEvent`` to Kafka.
The reducer consumes this event, validates the transition against contract.yaml,
and the effect node applies the actual database update.

Flow:
    1. Handler evaluates promotion gates (pure computation)
    2. If criteria met, emit ``ModelPatternLifecycleEvent`` to Kafka
    3. Reducer validates transition is allowed per contract FSM
    4. Effect node applies database UPDATE and emits transitioned event

This decoupling ensures:
    - Single source of truth for status transitions (reducer)
    - Full audit trail via Kafka events
    - Consistent FSM enforcement across all status changes
    - Eventual consistency (caller may return before status is updated)

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

Kafka Publisher Requirement:
----------------------------
The ``kafka_producer`` dependency is REQUIRED infrastructure per the ONEX
invariant: "Kafka is required infrastructure — there is NO fallback path".

All promotions go through the event-driven flow (Kafka -> reducer -> effect).
There is no direct database update fallback. Callers must supply a live
``ProtocolKafkaPublisher`` instance; passing None is a programming error.

Design Principles:
    - Pure functions for criteria evaluation (no I/O)
    - Protocol-based dependency injection for testability
    - Event-driven status changes via reducer (no direct SQL UPDATE)
    - Eventual consistency (status updated asynchronously)
    - asyncpg-style positional parameters ($1, $2, etc.)

Reference:
    - OMN-1805: Event-driven lifecycle transitions
    - OMN-1680: Auto-promote logic for patterns
    - OMN-1678: Rolling window metrics (dependency)
    - OMN-1679: Contribution heuristics (dependency)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from omniintelligence.constants import TOPIC_PATTERN_LIFECYCLE_CMD_V1
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.models.events import ModelPatternLifecycleEvent
from omniintelligence.nodes.node_pattern_promotion_effect.models import (
    ModelPromotionCheckResult,
    ModelPromotionResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

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
ORDER BY lp.created_at ASC
LIMIT 500
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
        Success rate as a float clamped to [0.0, 1.0].
        Returns 0.0 if no outcomes are recorded or if calculation
        would produce an invalid result.

    Note:
        Defensive bounds checking ensures invalid input data (negative
        counts) cannot produce rates outside [0.0, 1.0].
    """
    success_count = pattern.get("success_count_rolling_20", 0) or 0
    failure_count = pattern.get("failure_count_rolling_20", 0) or 0
    total = success_count + failure_count

    if total <= 0:
        return 0.0

    rate = success_count / total
    return max(0.0, min(1.0, rate))  # Clamp to [0.0, 1.0]


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
    producer: ProtocolKafkaPublisher,
    *,
    dry_run: bool = False,
    min_injection_count: int = MIN_INJECTION_COUNT,
    min_success_rate: float = MIN_SUCCESS_RATE,
    max_failure_streak: int = MAX_FAILURE_STREAK,
    correlation_id: UUID | None = None,
) -> ModelPromotionCheckResult:
    """Check and promote eligible provisional patterns.

    This is the main entry point for the promotion workflow. It:
    1. Fetches all provisional patterns (not disabled, is_current)
    2. Evaluates each against promotion gates
    3. If not dry_run: promotes eligible patterns and emits lifecycle events to Kafka
    4. Returns aggregated result with all promotion details

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        producer: Kafka producer implementing ProtocolKafkaPublisher. Required
            infrastructure — Kafka is the only promotion path.
        dry_run: If True, return what WOULD be promoted without mutating.
        min_injection_count: Minimum number of injections required for promotion.
            Defaults to MIN_INJECTION_COUNT (5).
        min_success_rate: Minimum success rate required for promotion (0.0-1.0).
            Defaults to MIN_SUCCESS_RATE (0.6).
        max_failure_streak: Maximum consecutive failures allowed for promotion.
            Defaults to MAX_FAILURE_STREAK (3). Set to 0 for zero-tolerance mode
            where any failure blocks promotion, or 1 to block on a single failure.
        correlation_id: Optional correlation ID for distributed tracing.

    Returns:
        ModelPromotionCheckResult with counts and individual promotion results.

    Note:
        Each pattern is promoted in its own transaction (not batch).
        If one promotion fails, others can still succeed.
    """
    logger.info(
        "Starting promotion check",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "dry_run": dry_run,
        },
    )

    # Step 1: Fetch all provisional patterns
    # Wrap the fetch in a try/except so a broken repository dependency (e.g.
    # None passed at construction) returns a structured error result rather
    # than propagating an AttributeError to the caller.
    try:
        patterns = await repository.fetch(SQL_FETCH_PROVISIONAL_PATTERNS)
    except Exception as exc:
        sanitized_err = get_log_sanitizer().sanitize(str(exc))
        logger.error(
            "Failed to fetch provisional patterns — returning empty result",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "error": sanitized_err,
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        return ModelPromotionCheckResult(
            dry_run=dry_run,
            patterns_checked=0,
            patterns_eligible=0,
            patterns_promoted=[],
            correlation_id=correlation_id,
            error_message=f"{type(exc).__name__}: {sanitized_err}",
        )

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
                        "correlation_id": str(correlation_id)
                        if correlation_id
                        else None,
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
    # Each pattern is processed independently - one failure does not block others.
    #
    # Note: The no-op path (skipped_noop_count) was removed. Pattern status is
    # checked asynchronously downstream by the reducer; this handler emits
    # lifecycle events optimistically. There is no synchronous "already promoted"
    # detection in the Kafka-only path.
    promotion_results: list[ModelPromotionResult] = []
    failed_count: int = 0

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
                    producer=producer,
                    pattern_id=pattern_id,
                    pattern_data=pattern,
                    correlation_id=correlation_id,
                )
                # Invariant: promote_pattern must set promoted_at on success (raises on
                # failure, so a None here means a silent no-return code path was added).
                assert result.promoted_at is not None, (
                    "promote_pattern contract violated: promoted_at must be set on success"
                )
                promotion_results.append(result)

            except Exception as exc:
                # Isolate per-pattern failures - continue processing other patterns
                failed_count += 1
                logger.error(
                    "Failed to promote pattern - continuing with remaining patterns",
                    extra={
                        "correlation_id": str(correlation_id)
                        if correlation_id
                        else None,
                        "pattern_id": str(pattern_id),
                        "pattern_signature": pattern_signature,
                        "error": get_log_sanitizer().sanitize(str(exc)),
                        "error_type": type(exc).__name__,
                    },
                    exc_info=True,
                )
                # Record the failed promotion attempt with error reason
                sanitized_err = get_log_sanitizer().sanitize(str(exc))
                failed_result = ModelPromotionResult(
                    pattern_id=pattern_id,
                    pattern_signature=pattern_signature,
                    from_status="provisional",
                    to_status="validated",
                    promoted_at=None,
                    reason=f"promotion_failed: {type(exc).__name__}: {sanitized_err}",
                    gate_snapshot=build_gate_snapshot(pattern),
                    dry_run=False,
                )
                promotion_results.append(failed_result)

    # Count results where promoted_at is set (i.e. the Kafka emit succeeded).
    # promote_pattern sets promoted_at=request_time on success and raises on
    # failure, so promoted_at is None only for dry-run entries and for failed
    # results that were caught above and constructed manually with promoted_at=None.
    actual_promotions = sum(
        1 for r in promotion_results if r.promoted_at is not None and not r.dry_run
    )

    logger.info(
        "Promotion check complete",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "patterns_checked": len(patterns),
            "patterns_eligible": len(eligible_patterns),
            "patterns_promoted": actual_promotions,
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
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    pattern_data: Mapping[str, Any],
    correlation_id: UUID | None = None,
) -> ModelPromotionResult:
    """Promote a single pattern from provisional to validated status.

    Emits a ``ModelPatternLifecycleEvent`` to Kafka for the reducer to process.
    The reducer validates the FSM transition and the effect node applies the
    database UPDATE. This function returns immediately after emitting the event
    (eventual consistency).

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher. Required
            infrastructure — there is no fallback path.
        pattern_id: The pattern ID to promote.
        pattern_data: Pattern record from SQL query (for gate snapshot).
        correlation_id: Optional correlation ID for tracing.

    Returns:
        ModelPromotionResult with promotion details and gate snapshot.

    Note:
        - The ``promoted_at`` field is set to request time
        - Actual status update happens asynchronously via reducer
        - The promotion may fail if reducer rejects the transition
        - Callers should not assume status has changed immediately
    """
    pattern_signature = pattern_data.get("pattern_signature", "")
    request_time = datetime.now(UTC)

    # Build gate snapshot capturing the metrics that triggered promotion
    gate_snapshot = build_gate_snapshot(pattern_data)

    logger.debug(
        "Requesting pattern promotion via lifecycle event",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
            "success_rate": gate_snapshot.success_rate_rolling_20,
            "injection_count": gate_snapshot.injection_count_rolling_20,
        },
    )

    # Emit lifecycle event to Kafka for reducer to process (required infrastructure)
    await _emit_lifecycle_event(
        producer=producer,
        pattern_id=pattern_id,
        gate_snapshot=gate_snapshot,
        request_time=request_time,
        correlation_id=correlation_id,
    )

    logger.info(
        "Pattern promotion requested via lifecycle event",
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
        promoted_at=request_time,  # Request time, actual update is async
        reason="auto_promote_rolling_window",
        gate_snapshot=gate_snapshot,
        dry_run=False,
    )


async def _emit_lifecycle_event(
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    gate_snapshot: ModelGateSnapshot,
    request_time: datetime,
    correlation_id: UUID | None,
) -> None:
    """Emit a pattern lifecycle event to Kafka for reducer processing.

    This emits a ``ModelPatternLifecycleEvent`` to the command topic, which
    the reducer consumes to validate and apply the status transition.

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The pattern ID to promote.
        gate_snapshot: Gate values at promotion decision time.
        request_time: When the promotion was requested.
        correlation_id: Correlation ID for distributed tracing.

    Reference:
        OMN-1805: Event-driven lifecycle transitions
    """
    # Use canonical topic constant directly
    topic = TOPIC_PATTERN_LIFECYCLE_CMD_V1

    # Generate idempotency key for this promotion attempt
    request_id = uuid4()

    # Build reason string with gate values
    reason = (
        f"Auto-promoted: success_rate={gate_snapshot.success_rate_rolling_20:.2%}, "
        f"injection_count={gate_snapshot.injection_count_rolling_20}, "
        f"failure_streak={gate_snapshot.failure_streak}"
    )

    # Build lifecycle event payload
    event = ModelPatternLifecycleEvent(
        request_id=request_id,
        pattern_id=pattern_id,
        from_status="provisional",
        to_status="validated",
        trigger="promote",
        correlation_id=correlation_id,
        actor="promotion_handler",
        actor_type="handler",
        reason=reason,
        gate_snapshot=gate_snapshot,
        occurred_at=request_time,
    )

    # Publish to Kafka command topic for reducer to process
    await producer.publish(
        topic=topic,
        key=str(pattern_id),
        value=event.model_dump(mode="json"),
    )

    logger.debug(
        "Emitted pattern-lifecycle event for promotion",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "request_id": str(request_id),
            "pattern_id": str(pattern_id),
            "topic": topic,
            "trigger": "promote",
        },
    )


__all__ = [
    "MAX_FAILURE_STREAK",
    "MIN_INJECTION_COUNT",
    "MIN_SUCCESS_RATE",
    "build_gate_snapshot",
    "calculate_success_rate",
    "check_and_promote_patterns",
    "meets_promotion_criteria",
    "promote_pattern",
]
