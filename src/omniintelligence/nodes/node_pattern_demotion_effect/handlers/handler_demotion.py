# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern demotion from validated to deprecated status.

This module implements the pattern demotion logic: checking validated patterns
against demotion gates and emitting lifecycle events for those that meet failure
criteria. Demotion decisions are based on rolling window metrics from the pattern
feedback loop.

Event-Driven Architecture (OMN-1805)
------------------------------------
This handler no longer performs direct SQL UPDATEs to change pattern status.
Instead, it emits ModelPatternLifecycleEvent to Kafka for the reducer to process:

    Handler → Kafka (pattern-lifecycle-transition.v1) → Reducer → Effect Node → DB

This architecture ensures:
    - Single source of truth: Reducer enforces ALL status transitions
    - Audit trail: All transitions logged with request_id for idempotency
    - Consistency: Same validation path for auto-demote and manual disable
    - FSM compliance: Reducer validates transitions against contract.yaml

Philosophy: Don't Demote on Noise
---------------------------------
Demotion is a STRONGER signal than promotion. While promotion gates are optimistic
("this pattern shows promise"), demotion gates are conservative ("this pattern is
definitively failing"). This asymmetry prevents patterns from oscillating between
validated and deprecated states due to temporary noise or variance.

Key differences from promotion:
    - Higher injection count requirement (10 vs 5): Need more data to demote
    - Cooldown period: Cannot demote recently promoted patterns
    - Multiple paths to demotion: Both low success AND high failure streak
    - Manual disable as hard override: Bypasses all gates

Demotion Gates:
---------------
Any ONE of the following triggers demotion (after passing eligibility checks):

1. Manual Disable Gate (HARD TRIGGER):
   - Pattern exists in disabled_patterns_current table
   - BYPASSES cooldown - always demotes immediately
   - Sets reason = "manual_disable", actor_type = "admin"

2. Failure Streak Gate:
   - failure_streak >= MIN_FAILURE_STREAK (5)
   - Pattern is in a persistent failure spiral
   - Sets reason = "failure_streak: N consecutive failures", actor_type = "handler"

3. Low Success Rate Gate (requires sufficient data):
   - success_rate < MAX_SUCCESS_RATE (0.40)
   - AND injection_count_rolling_20 >= MIN_INJECTION_COUNT (10)
   - Sets reason = "low_success_rate: X%", actor_type = "handler"

Eligibility Checks (applied before demotion gates 2 & 3):
---------------------------------------------------------
1. Cooldown Period: Must wait DEFAULT_COOLDOWN_HOURS (24) since promotion
   - Prevents oscillation between promotion and demotion
   - Manual disable BYPASSES this check

2. Status Check: Pattern must be in 'validated' status
   - Already filtered in SQL query (WHERE status = 'validated')

Kafka Publisher Requirement:
----------------------------
The ``kafka_producer`` dependency is REQUIRED for the event-driven architecture.
When the Kafka publisher is unavailable (None), demotions CANNOT be processed
and the handler returns early with reason="kafka_producer_unavailable".

**Implications of running without Kafka:**

1. **No Demotions**: Without Kafka, lifecycle events cannot be emitted, and
   demotions will not occur. This is intentional - the reducer is the single
   source of truth for status transitions.

2. **Degraded Mode Detection**: Callers can detect this by checking
   ``ModelDemotionResult.reason == "kafka_producer_unavailable"``.

3. **Retry Strategy**: When Kafka becomes available, re-run the demotion check
   to emit lifecycle events for patterns that met demotion criteria.

Design Principles:
    - Pure functions for criteria evaluation (no I/O)
    - Protocol-based dependency injection for testability
    - Event-driven status changes via Kafka (no direct SQL UPDATE)
    - Reducer as single source of truth for FSM transitions
    - asyncpg-style positional parameters ($1, $2, etc.)
    - Stricter thresholds than promotion to prevent oscillation

Reference:
    - OMN-1805: Reducer-based status transitions (this refactor)
    - OMN-1681: Auto-demote logic for patterns
    - OMN-1680: Auto-promote logic (reference implementation)
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from omniintelligence.constants import TOPIC_SUFFIX_PATTERN_DEPRECATED_V1
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.models.events import ModelPatternLifecycleEvent
from omniintelligence.nodes.node_pattern_demotion_effect.models import (
    ModelDemotionCheckRequest,
    ModelDemotionCheckResult,
    ModelDemotionGateSnapshot,
    ModelDemotionResult,
    ModelEffectiveThresholds,
    ModelPatternDeprecatedEvent,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Topic Constants
# =============================================================================

TOPIC_SUFFIX_PATTERN_LIFECYCLE_V1: str = (
    "onex.cmd.omniintelligence.pattern-lifecycle-transition.v1"
)
"""Topic suffix for pattern lifecycle transition commands (INPUT to reducer).

Handlers publish lifecycle events to this topic. The reducer consumes them,
validates the transition, and emits an intent for the effect node.

Full topic at runtime: {env}.onex.cmd.omniintelligence.pattern-lifecycle-transition.v1
"""


# =============================================================================
# Demotion Threshold Constants
# =============================================================================

MIN_INJECTION_COUNT_FOR_DEMOTION: int = 10
"""Minimum number of injections required for demotion eligibility.

A pattern must have been injected at least this many times (in the rolling
window) to have enough data for reliable demotion decisions. This is HIGHER
than the promotion threshold (5) because demotion is a stronger signal that
requires more evidence.

Database column: injection_count_rolling_20
"""

MAX_SUCCESS_RATE_FOR_DEMOTION: float = 0.40
"""Maximum success rate threshold for demotion (40%).

Calculated as: success_count_rolling_20 / (success_count_rolling_20 + failure_count_rolling_20)

A pattern with success rate BELOW this threshold is eligible for demotion.
This is significantly below the promotion threshold (60%) to create a buffer zone
that prevents oscillation.

The 20% gap between promotion (60%) and demotion (40%) ensures:
    - Patterns don't immediately demote after barely meeting promotion criteria
    - Random variance doesn't cause flip-flopping between states
    - Only definitively failing patterns get deprecated
"""

MIN_FAILURE_STREAK_FOR_DEMOTION: int = 5
"""Minimum consecutive failures required for demotion.

If a pattern has failed this many or more times in a row (failure_streak >= min),
it is eligible for demotion regardless of overall success rate.

This is HIGHER than promotion's max_failure_streak (3) because:
    - Promotion blocks on 3 consecutive failures (pattern is struggling)
    - Demotion requires 5 consecutive failures (pattern is definitively broken)
"""

DEFAULT_COOLDOWN_HOURS: int = 24
"""Default cooldown period in hours since promotion.

A pattern cannot be demoted until this many hours have passed since its
promotion to validated status. This prevents rapid oscillation and gives
patterns time to stabilize after promotion.

Can be overridden per-request if allow_threshold_override=True.
Manual disable BYPASSES this cooldown entirely.
"""

# Threshold bounds for validation
SUCCESS_RATE_THRESHOLD_MIN: float = 0.10
"""Minimum allowed value for max_success_rate override.

Prevents setting demotion threshold below 10% which would only catch
catastrophically failing patterns. Too permissive.
"""

SUCCESS_RATE_THRESHOLD_MAX: float = 0.60
"""Maximum allowed value for max_success_rate override.

Prevents setting demotion threshold at or above promotion threshold (60%)
which would cause immediate demotion of marginal patterns.
"""

FAILURE_STREAK_THRESHOLD_MIN: int = 3
"""Minimum allowed value for min_failure_streak override.

Prevents setting failure streak requirement below 3 which would demote
patterns too aggressively on small runs of bad luck.
"""

FAILURE_STREAK_THRESHOLD_MAX: int = 20
"""Maximum allowed value for min_failure_streak override.

Prevents setting failure streak requirement above 20 which would be
too permissive - 20 consecutive failures is definitive.
"""


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    This protocol defines the minimal interface required for database operations
    in the demotion handler. It is intentionally generic to support both
    asyncpg connections and mock implementations for testing.

    The methods mirror asyncpg.Connection semantics:
        - fetch: Execute query and return list of Records
        - execute: Execute query and return status string (e.g., "UPDATE 5")

    Note:
        Parameters use asyncpg-style positional placeholders ($1, $2, etc.)
        rather than named parameters.
    """

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, object]]:
        """Execute a query and return all results as Records.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            List of record objects with dict-like access to columns.
        """
        ...

    async def execute(self, query: str, *args: object) -> str:
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
        value: dict[str, object],
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

# Query to find validated patterns for demotion check
# Includes disabled status check via LEFT JOIN
SQL_FETCH_VALIDATED_PATTERNS = """
SELECT lp.id, lp.pattern_signature,
       lp.injection_count_rolling_20,
       lp.success_count_rolling_20,
       lp.failure_count_rolling_20,
       lp.failure_streak,
       lp.promoted_at,
       dpc.pattern_id IS NOT NULL as is_disabled
FROM learned_patterns lp
LEFT JOIN disabled_patterns_current dpc ON lp.id = dpc.pattern_id
WHERE lp.status = 'validated'
  AND lp.is_current = TRUE
"""


# =============================================================================
# Pure Functions
# =============================================================================


def validate_threshold_overrides(request: ModelDemotionCheckRequest) -> None:
    """Validate that threshold overrides are allowed and within bounds.

    This function enforces safety constraints on demotion thresholds:
    1. Non-default thresholds require explicit allow_threshold_override=True
    2. All threshold values must be within defined bounds

    Args:
        request: The demotion check request with threshold values.

    Raises:
        ValueError: If overrides are used without allow_threshold_override=True,
            or if any threshold value is outside the allowed bounds.

    Note:
        This is a pure validation function with no side effects.
    """
    # Check if any thresholds differ from defaults
    has_overrides = (
        request.max_success_rate != MAX_SUCCESS_RATE_FOR_DEMOTION
        or request.min_failure_streak != MIN_FAILURE_STREAK_FOR_DEMOTION
        or request.min_injection_count != MIN_INJECTION_COUNT_FOR_DEMOTION
        or request.cooldown_hours != DEFAULT_COOLDOWN_HOURS
    )

    if has_overrides and not request.allow_threshold_override:
        raise ValueError(
            "Threshold overrides detected but allow_threshold_override=False. "
            "Set allow_threshold_override=True to use non-default thresholds. "
            f"Detected: max_success_rate={request.max_success_rate}, "
            f"min_failure_streak={request.min_failure_streak}, "
            f"min_injection_count={request.min_injection_count}, "
            f"cooldown_hours={request.cooldown_hours}"
        )

    # Validate bounds (even if allow_threshold_override=True, bounds still apply)
    if not (
        SUCCESS_RATE_THRESHOLD_MIN
        <= request.max_success_rate
        <= SUCCESS_RATE_THRESHOLD_MAX
    ):
        raise ValueError(
            f"max_success_rate={request.max_success_rate} is outside allowed bounds "
            f"[{SUCCESS_RATE_THRESHOLD_MIN}, {SUCCESS_RATE_THRESHOLD_MAX}]"
        )

    if not (
        FAILURE_STREAK_THRESHOLD_MIN
        <= request.min_failure_streak
        <= FAILURE_STREAK_THRESHOLD_MAX
    ):
        raise ValueError(
            f"min_failure_streak={request.min_failure_streak} is outside allowed bounds "
            f"[{FAILURE_STREAK_THRESHOLD_MIN}, {FAILURE_STREAK_THRESHOLD_MAX}]"
        )

    # min_injection_count has no upper bound in spec, only lower bound >= 1
    if request.min_injection_count < 1:
        raise ValueError(
            f"min_injection_count={request.min_injection_count} must be >= 1"
        )

    # cooldown_hours has no upper bound in spec, only lower bound >= 0
    if request.cooldown_hours < 0:
        raise ValueError(f"cooldown_hours={request.cooldown_hours} must be >= 0")


def build_effective_thresholds(
    request: ModelDemotionCheckRequest,
) -> ModelEffectiveThresholds:
    """Build the effective thresholds model from the request.

    Args:
        request: The demotion check request with threshold values.

    Returns:
        ModelEffectiveThresholds capturing the actual thresholds used,
        including whether any overrides were applied.
    """
    has_overrides = (
        request.max_success_rate != MAX_SUCCESS_RATE_FOR_DEMOTION
        or request.min_failure_streak != MIN_FAILURE_STREAK_FOR_DEMOTION
        or request.min_injection_count != MIN_INJECTION_COUNT_FOR_DEMOTION
        or request.cooldown_hours != DEFAULT_COOLDOWN_HOURS
    )

    return ModelEffectiveThresholds(
        max_success_rate=request.max_success_rate,
        min_failure_streak=request.min_failure_streak,
        min_injection_count=request.min_injection_count,
        cooldown_hours=request.cooldown_hours,
        overrides_applied=has_overrides,
    )


def calculate_hours_since_promotion(promoted_at: datetime | None) -> float | None:
    """Calculate hours elapsed since pattern was promoted.

    Args:
        promoted_at: The timestamp when the pattern was promoted to validated
            status, or None if not available.

    Returns:
        Hours since promotion as a float, or None if promoted_at is None.
        Always returns non-negative values (clamped to 0.0 minimum).
    """
    if promoted_at is None:
        return None

    # Ensure promoted_at is timezone-aware
    if promoted_at.tzinfo is None:
        # Assume UTC for naive datetimes
        promoted_at = promoted_at.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    delta = now - promoted_at
    hours = delta.total_seconds() / 3600.0

    # Clamp to non-negative (handles edge cases with clock skew)
    return max(0.0, hours)


def is_cooldown_active(
    pattern: Mapping[str, object],
    cooldown_hours: int,
) -> bool:
    """Check if a pattern is still within its post-promotion cooldown period.

    The cooldown period prevents rapid oscillation between validated and
    deprecated states by requiring a minimum time between promotion and
    potential demotion.

    Args:
        pattern: Pattern record from SQL query containing 'promoted_at'.
        cooldown_hours: Minimum hours since promotion before demotion allowed.

    Returns:
        True if cooldown is ACTIVE (pattern should NOT be demoted yet),
        False if cooldown has elapsed or promoted_at is unavailable.
    """
    promoted_at = pattern.get("promoted_at")
    if promoted_at is None:
        # No promotion timestamp - cannot determine cooldown, allow demotion
        return False

    hours_since = calculate_hours_since_promotion(promoted_at)
    if hours_since is None:
        return False

    return hours_since < cooldown_hours


def get_demotion_reason(
    pattern: Mapping[str, object],
    thresholds: ModelEffectiveThresholds,
) -> str | None:
    """Determine the demotion reason for a pattern, if any.

    Evaluates the pattern against demotion gates in priority order:
    1. Manual disable (HARD TRIGGER - bypasses all other checks)
    2. Failure streak gate
    3. Low success rate gate (requires sufficient injection count)

    Args:
        pattern: Pattern record from SQL query containing:
            - is_disabled: bool (from LEFT JOIN with disabled_patterns_current)
            - failure_streak: int
            - success_count_rolling_20: int
            - failure_count_rolling_20: int
            - injection_count_rolling_20: int
        thresholds: Effective thresholds for this demotion check.

    Returns:
        String describing the demotion reason if pattern should be demoted:
            - "manual_disable"
            - "failure_streak: N consecutive failures"
            - "low_success_rate: X.X%"
        Returns None if pattern should NOT be demoted.

    Note:
        This function does NOT check cooldown - that is handled separately
        in the main handler flow, with manual_disable bypassing cooldown.
    """
    # Gate 1: Manual disable (HARD TRIGGER)
    is_disabled = pattern.get("is_disabled", False)
    if is_disabled:
        return "manual_disable"

    # Gate 2: Failure streak
    failure_streak = pattern.get("failure_streak", 0) or 0
    if failure_streak >= thresholds.min_failure_streak:
        return f"failure_streak: {failure_streak} consecutive failures"

    # Gate 3: Low success rate (requires sufficient data)
    injection_count = pattern.get("injection_count_rolling_20", 0) or 0
    if injection_count >= thresholds.min_injection_count:
        success_rate = calculate_success_rate(pattern)
        if success_rate < thresholds.max_success_rate:
            return f"low_success_rate: {success_rate:.1%}"

    # No demotion criteria met
    return None


def calculate_success_rate(pattern: Mapping[str, object]) -> float:
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


def build_gate_snapshot(pattern: Mapping[str, object]) -> ModelDemotionGateSnapshot:
    """Build a gate snapshot from pattern data.

    Captures the state of all demotion gates at evaluation time for
    audit trail and debugging purposes.

    Args:
        pattern: Pattern record from SQL query.

    Returns:
        ModelDemotionGateSnapshot capturing the gate values at evaluation time.
    """
    promoted_at = pattern.get("promoted_at")
    hours_since = calculate_hours_since_promotion(promoted_at)

    return ModelDemotionGateSnapshot(
        success_rate_rolling_20=calculate_success_rate(pattern),
        injection_count_rolling_20=pattern.get("injection_count_rolling_20", 0) or 0,
        failure_streak=pattern.get("failure_streak", 0) or 0,
        disabled=pattern.get("is_disabled", False),
        hours_since_promotion=hours_since,
    )


# =============================================================================
# Handler Functions
# =============================================================================


async def check_and_demote_patterns(
    repository: ProtocolPatternRepository,
    producer: ProtocolKafkaPublisher | None = None,
    *,
    request: ModelDemotionCheckRequest,
    topic_env_prefix: str | None = None,
) -> ModelDemotionCheckResult:
    """Check and demote validated patterns that meet demotion criteria.

    This is the main entry point for the demotion workflow. It:
    1. Validates threshold overrides (raises ValueError if invalid)
    2. Builds effective thresholds from request
    3. Fetches all validated patterns (with disabled status)
    4. For each pattern:
       a. Check for manual disable (bypasses cooldown)
       b. Check cooldown period (skips if active, unless manual disable)
       c. Evaluate demotion criteria
       d. If eligible and not dry_run: demote and emit event
    5. Returns aggregated result with all demotion details

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        producer: Optional Kafka producer implementing ProtocolKafkaPublisher.
            If None, Kafka events are not emitted but database demotions still
            occur. See "Kafka Optionality" section in module docstring.
        request: Demotion check request with threshold values and dry_run flag.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").
            Required when producer is not None. Ignored when producer is None.

    Returns:
        ModelDemotionCheckResult with counts, individual demotion results,
        and skipped_cooldown count.

    Raises:
        ValueError: If threshold overrides are used without allow_threshold_override=True,
            or if threshold values are outside allowed bounds.

    Note:
        Each pattern is demoted in its own transaction (not batch).
        If one demotion fails, others can still succeed.

    Warning:
        When ``producer`` is None, downstream services relying on Kafka events
        for cache invalidation will not be notified. Their pattern caches may
        serve deprecated patterns until manually refreshed.
    """
    correlation_id = request.correlation_id

    logger.info(
        "Starting demotion check",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "dry_run": request.dry_run,
        },
    )

    # Step 1: Validate threshold overrides
    try:
        validate_threshold_overrides(request)
    except ValueError as e:
        logger.error(
            "Threshold validation failed",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "error": str(e),
            },
        )
        raise

    # Step 2: Build effective thresholds
    thresholds = build_effective_thresholds(request)

    if thresholds.overrides_applied:
        logger.info(
            "Using non-default thresholds",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "max_success_rate": thresholds.max_success_rate,
                "min_failure_streak": thresholds.min_failure_streak,
                "min_injection_count": thresholds.min_injection_count,
                "cooldown_hours": thresholds.cooldown_hours,
            },
        )

    # Step 3: Fetch all validated patterns
    patterns = await repository.fetch(SQL_FETCH_VALIDATED_PATTERNS)

    logger.debug(
        "Fetched validated patterns",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_count": len(patterns),
        },
    )

    # Step 4: Evaluate each pattern
    demotion_results: list[ModelDemotionResult] = []
    skipped_cooldown_count: int = 0
    failed_count: int = 0
    skipped_noop_count: int = 0
    kafka_unavailable_count: int = 0
    eligible_count: int = 0

    for pattern in patterns:
        pattern_id = pattern["id"]
        pattern_signature = pattern.get("pattern_signature", "")
        is_disabled = pattern.get("is_disabled", False)

        # Get demotion reason (if any)
        reason = get_demotion_reason(pattern, thresholds)

        if reason is None:
            # Pattern does not meet demotion criteria
            continue

        eligible_count += 1

        # Check cooldown - but manual_disable BYPASSES cooldown
        if reason != "manual_disable" and is_cooldown_active(
            pattern, thresholds.cooldown_hours
        ):
            skipped_cooldown_count += 1
            hours_since = calculate_hours_since_promotion(pattern.get("promoted_at"))
            logger.debug(
                "Skipped pattern due to cooldown",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "pattern_id": str(pattern_id),
                    "pattern_signature": pattern_signature,
                    "hours_since_promotion": hours_since,
                    "cooldown_hours": thresholds.cooldown_hours,
                    "reason": reason,
                },
            )
            continue

        # Pattern is eligible for demotion
        if request.dry_run:
            # Dry run: record what WOULD happen
            result = ModelDemotionResult(
                pattern_id=pattern_id,
                pattern_signature=pattern_signature,
                from_status="validated",
                to_status="deprecated",
                deprecated_at=None,
                reason=reason,
                gate_snapshot=build_gate_snapshot(pattern),
                effective_thresholds=thresholds,
                dry_run=True,
            )
            demotion_results.append(result)
        else:
            # Actual demotion - isolated per-pattern error handling
            try:
                result = await demote_pattern(
                    repository=repository,
                    producer=producer,
                    pattern_id=pattern_id,
                    pattern_data=pattern,
                    reason=reason,
                    thresholds=thresholds,
                    correlation_id=correlation_id,
                    topic_env_prefix=topic_env_prefix,
                )

                # Check for kafka issues - track separately but still add result
                # Handles both "kafka_producer_unavailable" and "kafka_publish_failed:..."
                if (
                    result.reason == "kafka_producer_unavailable"
                    or result.reason.startswith("kafka_publish_failed:")
                ):
                    kafka_unavailable_count += 1
                    logger.warning(
                        "Pattern demotion skipped - Kafka issue",
                        extra={
                            "correlation_id": str(correlation_id)
                            if correlation_id
                            else None,
                            "pattern_id": str(pattern_id),
                            "pattern_signature": pattern_signature,
                            "reason": result.reason,
                        },
                    )
                    # Still add the result so caller knows demotion was attempted
                    demotion_results.append(result)
                    continue

                # Check for no-op (pattern was already demoted or status changed)
                if result.deprecated_at is None and not result.dry_run:
                    skipped_noop_count += 1
                    logger.debug(
                        "Skipped no-op demotion",
                        extra={
                            "correlation_id": str(correlation_id)
                            if correlation_id
                            else None,
                            "pattern_id": str(pattern_id),
                            "pattern_signature": pattern_signature,
                            "reason": result.reason,
                        },
                    )
                    continue

                demotion_results.append(result)

            except Exception as exc:
                # Isolate per-pattern failures - continue processing other patterns
                failed_count += 1
                logger.error(
                    "Failed to demote pattern - continuing with remaining patterns",
                    extra={
                        "correlation_id": str(correlation_id)
                        if correlation_id
                        else None,
                        "pattern_id": str(pattern_id),
                        "pattern_signature": pattern_signature,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                    exc_info=True,
                )
                # Record the failed demotion attempt with error reason
                failed_result = ModelDemotionResult(
                    pattern_id=pattern_id,
                    pattern_signature=pattern_signature,
                    from_status="validated",
                    to_status="deprecated",
                    deprecated_at=None,
                    reason=f"demotion_failed: {type(exc).__name__}: {exc!s}",
                    gate_snapshot=build_gate_snapshot(pattern),
                    effective_thresholds=thresholds,
                    dry_run=False,
                )
                demotion_results.append(failed_result)

    # Calculate actual demotions (excluding no-ops and failures)
    actual_demotions = sum(
        1 for r in demotion_results if r.deprecated_at is not None and not r.dry_run
    )

    logger.info(
        "Demotion check complete",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "patterns_checked": len(patterns),
            "patterns_eligible": eligible_count,
            "patterns_demoted": actual_demotions,
            "patterns_skipped_cooldown": skipped_cooldown_count,
            "patterns_skipped_noop": skipped_noop_count,
            "patterns_kafka_unavailable": kafka_unavailable_count,
            "patterns_failed": failed_count,
            "dry_run": request.dry_run,
        },
    )

    return ModelDemotionCheckResult(
        dry_run=request.dry_run,
        patterns_checked=len(patterns),
        patterns_eligible=eligible_count,
        patterns_demoted=demotion_results,
        patterns_skipped_cooldown=skipped_cooldown_count,
        correlation_id=correlation_id,
    )


async def demote_pattern(
    repository: ProtocolPatternRepository,  # noqa: ARG001 - kept for interface compat
    producer: ProtocolKafkaPublisher | None,
    pattern_id: UUID,
    pattern_data: Mapping[str, object],
    reason: str,
    thresholds: ModelEffectiveThresholds,
    correlation_id: UUID | None = None,
    *,
    topic_env_prefix: str | None = None,
) -> ModelDemotionResult:
    """Request demotion of a pattern by emitting a lifecycle event.

    This function emits a ModelPatternLifecycleEvent to Kafka for the reducer
    to process. The actual status update happens asynchronously via the
    reducer → effect node pipeline (OMN-1805 architecture).

    **Event-Driven Flow**:
    1. This handler evaluates demotion criteria and builds gate snapshot
    2. Emits ModelPatternLifecycleEvent to pattern-lifecycle-transition topic
    3. Reducer validates transition against FSM contract
    4. Effect node applies the actual database UPDATE

    **Why Events Instead of Direct SQL?**
    - Single source of truth: Reducer enforces all status transitions
    - Audit trail: All transitions logged with request_id for idempotency
    - Consistency: Same validation path for auto-demote and manual disable

    Args:
        repository: Database repository (unused in event-driven mode, kept for
            interface compatibility during migration).
        producer: Kafka producer implementing ProtocolKafkaPublisher.
            REQUIRED for event emission. If None, returns early with error.
        pattern_id: The pattern ID to demote.
        pattern_data: Pattern record from SQL query (for gate snapshot).
        reason: The demotion reason string (e.g., "manual_disable",
            "failure_streak: 5 consecutive failures", "low_success_rate: 35.0%").
        thresholds: Effective thresholds used for this demotion.
        correlation_id: Optional correlation ID for tracing.
        topic_env_prefix: Environment prefix for Kafka topic (e.g., "dev", "prod").
            Required when producer is not None. Ignored when producer is None.

    Returns:
        ModelDemotionResult with demotion details and gate snapshot.
        The ``deprecated_at`` field indicates when the demotion was REQUESTED
        (not when it completes - that happens asynchronously).
        Returns ``deprecated_at=None`` if producer is None (cannot emit event).

    Note:
        The actual database UPDATE is performed by NodePatternLifecycleEffect
        after the reducer validates the transition. This function only emits
        the lifecycle event.
    """
    pattern_signature = pattern_data.get("pattern_signature", "")
    requested_at = datetime.now(UTC)

    logger.debug(
        "Requesting pattern demotion via lifecycle event",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
            "reason": reason,
        },
    )

    # Build gate snapshot for audit trail
    gate_snapshot = build_gate_snapshot(pattern_data)

    # Check if producer is available - required for event-driven demotion
    if producer is None:
        logger.warning(
            "Cannot emit lifecycle event - Kafka producer unavailable",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "pattern_id": str(pattern_id),
                "pattern_signature": pattern_signature,
            },
        )
        return ModelDemotionResult(
            pattern_id=pattern_id,
            pattern_signature=pattern_signature,
            from_status="validated",
            to_status="deprecated",
            deprecated_at=None,  # None indicates event was NOT emitted
            reason="kafka_producer_unavailable",
            gate_snapshot=gate_snapshot,
            effective_thresholds=thresholds,
            dry_run=False,
        )

    # Validate topic_env_prefix is provided when using Kafka
    if topic_env_prefix is None:
        raise ValueError(
            "topic_env_prefix is required when Kafka producer is available. "
            "Provide environment prefix (e.g., 'dev', 'staging', 'prod')."
        )

    # Determine actor_type based on reason
    # Manual disable is an admin action; auto-demotion is a handler action
    is_manual_disable = reason == "manual_disable"
    actor_type: str = "admin" if is_manual_disable else "handler"
    actor = "demotion_handler"

    # Emit lifecycle event for reducer to process
    # Wrap in try/except to handle Kafka failures gracefully (non-blocking)
    try:
        await _emit_lifecycle_event(
            producer=producer,
            pattern_id=pattern_id,
            reason=reason,
            gate_snapshot=gate_snapshot,
            correlation_id=correlation_id,
            actor=actor,
            actor_type=actor_type,
            requested_at=requested_at,
            topic_env_prefix=topic_env_prefix,
        )
    except Exception as exc:
        # Log the error but don't fail - Kafka is optional for effect nodes
        logger.warning(
            "Failed to emit lifecycle event to Kafka - demotion not processed",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "pattern_id": str(pattern_id),
                "pattern_signature": pattern_signature,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return ModelDemotionResult(
            pattern_id=pattern_id,
            pattern_signature=pattern_signature,
            from_status="validated",
            to_status="deprecated",
            deprecated_at=None,  # None indicates event was NOT emitted
            reason=f"kafka_publish_failed: {type(exc).__name__}: {exc!s}",
            gate_snapshot=gate_snapshot,
            effective_thresholds=thresholds,
            dry_run=False,
        )

    logger.info(
        "Pattern demotion requested via lifecycle event",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
            "reason": reason,
            "actor_type": actor_type,
            "success_rate": gate_snapshot.success_rate_rolling_20,
            "failure_streak": gate_snapshot.failure_streak,
        },
    )

    return ModelDemotionResult(
        pattern_id=pattern_id,
        pattern_signature=pattern_signature,
        from_status="validated",
        to_status="deprecated",
        deprecated_at=requested_at,  # Indicates when demotion was REQUESTED
        reason=reason,
        gate_snapshot=gate_snapshot,
        effective_thresholds=thresholds,
        dry_run=False,
    )


async def _emit_lifecycle_event(
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    reason: str,
    gate_snapshot: ModelDemotionGateSnapshot,
    correlation_id: UUID | None,
    actor: str,
    actor_type: str,
    requested_at: datetime,
    *,
    topic_env_prefix: str,
) -> None:
    """Emit a pattern lifecycle event to Kafka for reducer processing.

    This function publishes a ModelPatternLifecycleEvent to the lifecycle
    transition command topic. The reducer consumes this event, validates
    the transition against the FSM contract, and emits an intent for the
    effect node to apply the actual database change.

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The pattern ID to transition.
        reason: The demotion reason (e.g., "manual_disable", "low_success_rate: 35.0%").
        gate_snapshot: Gate values at evaluation time for audit trail.
        correlation_id: Correlation ID for distributed tracing.
        actor: Who initiated the transition (e.g., "demotion_handler").
        actor_type: Actor classification ("handler" for auto-demote, "admin" for manual).
        requested_at: Timestamp when demotion was requested.
        topic_env_prefix: Environment prefix for topic (e.g., "dev", "prod").
            Required parameter - must be provided by caller from configuration.

    Note:
        The request_id is generated here as the idempotency key. It flows
        end-to-end: Event.request_id → Reducer → Intent → Audit table.
    """
    # Build topic name with environment prefix
    topic = f"{topic_env_prefix}.{TOPIC_SUFFIX_PATTERN_LIFECYCLE_V1}"

    # Generate idempotency key for this demotion attempt
    request_id = uuid4()

    # Convert ModelDemotionGateSnapshot to ModelGateSnapshot for the lifecycle event
    # ModelDemotionGateSnapshot has extra fields (hours_since_promotion) not in ModelGateSnapshot
    common_gate_snapshot = ModelGateSnapshot(
        success_rate_rolling_20=gate_snapshot.success_rate_rolling_20,
        injection_count_rolling_20=gate_snapshot.injection_count_rolling_20,
        failure_streak=gate_snapshot.failure_streak,
        disabled=gate_snapshot.disabled,
    )

    # Build lifecycle event for reducer
    event = ModelPatternLifecycleEvent(
        event_type="PatternLifecycleEvent",
        request_id=request_id,
        pattern_id=pattern_id,
        from_status="validated",
        to_status="deprecated",
        trigger="deprecate",
        correlation_id=correlation_id,
        actor=actor,
        actor_type=actor_type,  # type: ignore[arg-type]  # Literal type validation
        reason=reason,
        gate_snapshot=common_gate_snapshot,
        occurred_at=requested_at,
    )

    # Publish to Kafka for reducer to process
    await producer.publish(
        topic=topic,
        key=str(pattern_id),
        value=event.model_dump(mode="json"),
    )

    logger.debug(
        "Emitted pattern-lifecycle event for demotion",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "request_id": str(request_id),
            "actor_type": actor_type,
            "topic": topic,
        },
    )


async def _emit_deprecation_event(
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    pattern_signature: str,
    reason: str,
    gate_snapshot: ModelDemotionGateSnapshot,
    thresholds: ModelEffectiveThresholds,
    deprecated_at: datetime,
    correlation_id: UUID | None,
    *,
    topic_env_prefix: str,
) -> None:
    """Emit a pattern-deprecated event to Kafka.

    NOTE: This function is retained for downstream notification AFTER the
    reducer/effect node completes the actual transition. It is NOT used
    in the new event-driven demotion flow (see _emit_lifecycle_event).

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The deprecated pattern ID.
        pattern_signature: The pattern signature.
        reason: The demotion reason.
        gate_snapshot: Gate values at demotion time.
        thresholds: Effective thresholds used for this demotion.
        deprecated_at: Demotion timestamp.
        correlation_id: Correlation ID for tracing.
        topic_env_prefix: Environment prefix for topic (e.g., "dev", "prod").
            Required parameter - must be provided by caller from configuration.
    """
    # Build topic name with environment prefix
    topic = f"{topic_env_prefix}.{TOPIC_SUFFIX_PATTERN_DEPRECATED_V1}"

    # Build event payload using the model
    event = ModelPatternDeprecatedEvent(
        event_type="PatternDeprecated",
        pattern_id=pattern_id,
        pattern_signature=pattern_signature,
        from_status="validated",
        to_status="deprecated",
        reason=reason,
        gate_snapshot=gate_snapshot,
        effective_thresholds=thresholds,
        deprecated_at=deprecated_at,
        correlation_id=correlation_id,
    )

    # Publish to Kafka
    await producer.publish(
        topic=topic,
        key=str(pattern_id),
        value=event.model_dump(mode="json"),
    )

    logger.debug(
        "Emitted pattern-deprecated event",
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
