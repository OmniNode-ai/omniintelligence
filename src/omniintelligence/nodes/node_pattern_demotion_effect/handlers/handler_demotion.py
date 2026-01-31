# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern demotion from validated to deprecated status.

This module implements the pattern demotion logic: checking validated patterns
against demotion gates and deprecating those that meet failure criteria. Demotion
decisions are based on rolling window metrics from the pattern feedback loop.

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
   - Sets deprecation_reason = "manual_disable"

2. Failure Streak Gate:
   - failure_streak >= MIN_FAILURE_STREAK (5)
   - Pattern is in a persistent failure spiral
   - Sets deprecation_reason = "failure_streak: N consecutive failures"

3. Low Success Rate Gate (requires sufficient data):
   - success_rate < MAX_SUCCESS_RATE (0.40)
   - AND injection_count_rolling_20 >= MIN_INJECTION_COUNT (10)
   - Sets deprecation_reason = "low_success_rate: X%"

Eligibility Checks (applied before demotion gates 2 & 3):
---------------------------------------------------------
1. Cooldown Period: Must wait DEFAULT_COOLDOWN_HOURS (24) since promotion
   - Prevents oscillation between promotion and demotion
   - Manual disable BYPASSES this check

2. Status Check: Pattern must be in 'validated' status
   - Already filtered in SQL query (WHERE status = 'validated')

Kafka Publisher Optionality:
----------------------------
The ``kafka_producer`` dependency is OPTIONAL (contract marks it as ``required: false``).
When the Kafka publisher is unavailable (None), demotions still occur in the database,
but ``PatternDeprecated`` events are NOT emitted to Kafka.

**Implications of running without Kafka:**

1. **Downstream Cache Staleness**: Services that cache validated patterns and rely on
   Kafka events for cache invalidation will NOT receive deprecation notifications.
   They may continue serving deprecated patterns until refreshed.

2. **Event Audit Trail**: The Kafka event stream serves as an audit log of demotions.
   Without Kafka, this audit trail is incomplete. Database ``deprecated_at`` timestamps
   remain the only demotion record.

3. **Real-time Consumers**: Any real-time consumers subscribed to the
   ``{env}.pattern-deprecated.v1`` topic will not receive deprecation events.

**Reconciliation Strategy**: When Kafka becomes available after running in
degraded mode, consumers should query the ``learned_patterns`` table for patterns
where ``status = 'deprecated'`` and ``deprecated_at > last_known_event_timestamp``
to reconcile any missed demotions.

Design Principles:
    - Pure functions for criteria evaluation (no I/O)
    - Protocol-based dependency injection for testability
    - Per-pattern transactions (not batch) for reliability
    - Kafka event emission for downstream cache invalidation (when available)
    - Graceful degradation when Kafka is unavailable
    - asyncpg-style positional parameters ($1, $2, etc.)
    - Stricter thresholds than promotion to prevent oscillation

Reference:
    - OMN-1681: Auto-demote logic for patterns
    - OMN-1680: Auto-promote logic (reference implementation)
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.constants import TOPIC_SUFFIX_PATTERN_DEPRECATED_V1
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

A pattern with success rate AT OR BELOW this threshold is eligible for demotion.
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

# Query to demote a single pattern
SQL_DEMOTE_PATTERN = """
UPDATE learned_patterns
SET status = 'deprecated',
    deprecated_at = NOW(),
    deprecation_reason = $2,
    updated_at = NOW()
WHERE id = $1
  AND status = 'validated'
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
    pattern: Mapping[str, Any],
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
    pattern: Mapping[str, Any],
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


def build_gate_snapshot(pattern: Mapping[str, Any]) -> ModelDemotionGateSnapshot:
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
    topic_env_prefix: str = "dev",
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
            Only used when producer is not None.

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
    repository: ProtocolPatternRepository,
    producer: ProtocolKafkaPublisher | None,
    pattern_id: UUID,
    pattern_data: Mapping[str, Any],
    reason: str,
    thresholds: ModelEffectiveThresholds,
    correlation_id: UUID | None = None,
    *,
    topic_env_prefix: str = "dev",
) -> ModelDemotionResult:
    """Demote a single pattern from validated to deprecated.

    This function:
    1. Updates the pattern status in the database
    2. Emits a pattern-deprecated event to Kafka (if producer available)
    3. Returns the demotion result with gate snapshot

    The database update and Kafka event are NOT transactionally coupled.
    The database update succeeds independently of Kafka availability.

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        producer: Kafka producer implementing ProtocolKafkaPublisher, or None.
            When None, the demotion succeeds in the database but no Kafka event
            is emitted.
        pattern_id: The pattern ID to demote.
        pattern_data: Pattern record from SQL query (for gate snapshot).
        reason: The demotion reason string (e.g., "manual_disable",
            "failure_streak: 5 consecutive failures", "low_success_rate: 35.0%").
        thresholds: Effective thresholds used for this demotion.
        correlation_id: Optional correlation ID for tracing.
        topic_env_prefix: Environment prefix for Kafka topic. Only used when
            producer is not None.

    Returns:
        ModelDemotionResult with demotion details and gate snapshot.
        The ``deprecated_at`` field is set regardless of Kafka availability.
        Returns ``deprecated_at=None`` if the pattern was already demoted
        (concurrent demotion detected).

    Note:
        Transaction handling is the caller's responsibility. This function
        executes a single UPDATE statement.
    """
    pattern_signature = pattern_data.get("pattern_signature", "")
    deprecated_at = datetime.now(UTC)

    logger.debug(
        "Demoting pattern",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
            "reason": reason,
        },
    )

    # Step 1: Update database
    status = await repository.execute(SQL_DEMOTE_PATTERN, pattern_id, reason)
    rows_updated = _parse_update_count(status)

    if rows_updated == 0:
        logger.warning(
            "Pattern not updated - may have been demoted already or changed status",
            extra={
                "correlation_id": str(correlation_id) if correlation_id else None,
                "pattern_id": str(pattern_id),
            },
        )
        # Return early without emitting event - pattern wasn't actually demoted
        return ModelDemotionResult(
            pattern_id=pattern_id,
            pattern_signature=pattern_signature,
            from_status="validated",
            to_status="deprecated",
            deprecated_at=None,  # None indicates no actual demotion occurred
            reason="already_demoted_or_status_changed",
            gate_snapshot=build_gate_snapshot(pattern_data),
            effective_thresholds=thresholds,
            dry_run=False,
        )

    # Step 2: Build gate snapshot
    gate_snapshot = build_gate_snapshot(pattern_data)

    # Step 3: Emit Kafka event (if producer available)
    if producer is not None:
        await _emit_deprecation_event(
            producer=producer,
            pattern_id=pattern_id,
            pattern_signature=pattern_signature,
            reason=reason,
            gate_snapshot=gate_snapshot,
            thresholds=thresholds,
            deprecated_at=deprecated_at,
            correlation_id=correlation_id,
            topic_env_prefix=topic_env_prefix,
        )

    logger.info(
        "Pattern demoted",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_id": str(pattern_id),
            "pattern_signature": pattern_signature,
            "reason": reason,
            "success_rate": gate_snapshot.success_rate_rolling_20,
            "failure_streak": gate_snapshot.failure_streak,
        },
    )

    return ModelDemotionResult(
        pattern_id=pattern_id,
        pattern_signature=pattern_signature,
        from_status="validated",
        to_status="deprecated",
        deprecated_at=deprecated_at,
        reason=reason,
        gate_snapshot=gate_snapshot,
        effective_thresholds=thresholds,
        dry_run=False,
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
    topic_env_prefix: str = "dev",
) -> None:
    """Emit a pattern-deprecated event to Kafka.

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The deprecated pattern ID.
        pattern_signature: The pattern signature.
        reason: The demotion reason.
        gate_snapshot: Gate values at demotion time.
        thresholds: Effective thresholds used for this demotion.
        deprecated_at: Demotion timestamp.
        correlation_id: Correlation ID for tracing.
        topic_env_prefix: Environment prefix for topic.
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


__all__ = [
    # Constants
    "DEFAULT_COOLDOWN_HOURS",
    "FAILURE_STREAK_THRESHOLD_MAX",
    "FAILURE_STREAK_THRESHOLD_MIN",
    "MAX_SUCCESS_RATE_FOR_DEMOTION",
    "MIN_FAILURE_STREAK_FOR_DEMOTION",
    "MIN_INJECTION_COUNT_FOR_DEMOTION",
    "SUCCESS_RATE_THRESHOLD_MAX",
    "SUCCESS_RATE_THRESHOLD_MIN",
    # Protocols
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    # Pure functions
    "build_effective_thresholds",
    "build_gate_snapshot",
    "calculate_hours_since_promotion",
    "calculate_success_rate",
    # Handler functions
    "check_and_demote_patterns",
    "demote_pattern",
    "get_demotion_reason",
    "is_cooldown_active",
    "validate_threshold_overrides",
]
