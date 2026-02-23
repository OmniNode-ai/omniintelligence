# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for evidence-gated automatic pattern promotion (L2 Lifecycle Controller).

This module implements the L2 Lifecycle Controller from OMN-2133. It extends the
existing promotion system with evidence tier gating:

    CANDIDATE -> PROVISIONAL: requires evidence_tier >= OBSERVED
    PROVISIONAL -> VALIDATED: requires evidence_tier >= MEASURED

Evidence Tier Gating:
    Unlike the existing ``handler_promotion.py`` which only handles
    PROVISIONAL -> VALIDATED, this handler manages both promotion stages
    with evidence tier as a required gate.

    The handler reads ``learned_patterns.evidence_tier`` directly (SD-3:
    denormalized column, no join to attribution table). This keeps the
    promotion check fast and avoids coupling to the audit table.

Relationship to handler_promotion.py:
    The existing ``check_and_promote_patterns()`` in handler_promotion.py
    handles PROVISIONAL -> VALIDATED based on rolling window metrics.
    This handler ADDS evidence tier as an additional gate and also handles
    CANDIDATE -> PROVISIONAL promotion.

    Both handlers can coexist: handler_promotion focuses on metric-based
    gates while handler_auto_promote focuses on evidence-based gates.

Design Principles:
    - Pure functions for criteria evaluation (no I/O)
    - Evidence tier read from denormalized column (fast, no joins)
    - Calls existing ``apply_transition()`` for actual state changes
    - Protocol-based dependency injection for testability
    - asyncpg-style positional parameters ($1, $2, etc.)

Reference:
    - OMN-2133: L1+L2 Attribution binder, auto-promote handler, transition guards
    - OMN-2043: Pattern Learning L1+L2 epic
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast, runtime_checkable
from uuid import UUID, uuid4

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import EvidenceTierLiteral, ModelGateSnapshot
from omniintelligence.protocols import ProtocolPatternRepository
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
        ModelTransitionResult,
    )
    from omniintelligence.protocols import (
        ProtocolIdempotencyStore,
        ProtocolKafkaPublisher,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MIN_INJECTION_COUNT_PROVISIONAL: int = 3
"""Minimum injections for CANDIDATE -> PROVISIONAL promotion.

Lower threshold than PROVISIONAL -> VALIDATED because we want patterns
to enter the provisional stage relatively quickly for further evaluation.
"""

MIN_INJECTION_COUNT_VALIDATED: int = 5
"""Minimum injections for PROVISIONAL -> VALIDATED promotion.

Same as existing MIN_INJECTION_COUNT in handler_promotion.py.
"""

MIN_SUCCESS_RATE: float = 0.6
"""Minimum success rate required for any promotion (60%)."""

MAX_FAILURE_STREAK: int = 3
"""Maximum consecutive failures allowed for promotion eligibility."""

_VALID_EVIDENCE_TIERS: frozenset[str] = frozenset(
    {"unmeasured", "observed", "measured", "verified"}
)
"""Valid evidence tier values matching EvidenceTierLiteral."""

_VALID_RUN_RESULTS: frozenset[str] = frozenset({"success", "partial", "failure"})
"""Valid pipeline run result values matching EnumRunResult."""


# =============================================================================
# SQL Queries
# =============================================================================

# Fetch candidate patterns eligible for CANDIDATE -> PROVISIONAL promotion
# Requires: evidence_tier >= OBSERVED, sufficient metrics, not disabled
SQL_FETCH_CANDIDATE_PATTERNS = """
SELECT lp.id, lp.pattern_signature, lp.status, lp.evidence_tier,
       lp.injection_count_rolling_20,
       lp.success_count_rolling_20,
       lp.failure_count_rolling_20,
       lp.failure_streak
FROM learned_patterns lp
LEFT JOIN disabled_patterns_current dpc ON lp.id = dpc.pattern_id
WHERE lp.status = 'candidate'
  AND lp.is_current = TRUE
  AND dpc.pattern_id IS NULL
  AND lp.evidence_tier IN ('observed', 'measured', 'verified')
ORDER BY lp.created_at ASC
LIMIT 500
"""

# Fetch provisional patterns eligible for PROVISIONAL -> VALIDATED promotion
# Requires: evidence_tier >= MEASURED, sufficient metrics, not disabled
SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER = """
SELECT lp.id, lp.pattern_signature, lp.status, lp.evidence_tier,
       lp.injection_count_rolling_20,
       lp.success_count_rolling_20,
       lp.failure_count_rolling_20,
       lp.failure_streak
FROM learned_patterns lp
LEFT JOIN disabled_patterns_current dpc ON lp.id = dpc.pattern_id
WHERE lp.status = 'provisional'
  AND lp.is_current = TRUE
  AND dpc.pattern_id IS NULL
  AND lp.evidence_tier IN ('measured', 'verified')
ORDER BY lp.created_at ASC
LIMIT 500
"""

# Count measured attributions for a pattern (for gate snapshot)
SQL_COUNT_ATTRIBUTIONS = """
SELECT COUNT(*) as count
FROM pattern_measured_attributions
WHERE pattern_id = $1
"""

# Get latest run result for a pattern (for gate snapshot)
SQL_LATEST_RUN_RESULT = """
SELECT measured_attribution_json->>'run_result' as run_result
FROM pattern_measured_attributions
WHERE pattern_id = $1
  AND run_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 1
"""


# =============================================================================
# Type Definitions
# =============================================================================


class _PatternMetricsRowRequired(TypedDict):
    """Required fields for PatternMetricsRow (always present in query result)."""

    id: UUID
    pattern_signature: str
    status: str
    evidence_tier: str


class PatternMetricsRow(_PatternMetricsRowRequired, total=False):
    """Row shape returned by SQL_FETCH_CANDIDATE_PATTERNS / SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER.

    Mirrors the SELECT columns from the promotion SQL queries. Required fields
    (id, pattern_signature, status, evidence_tier) are always present. Optional
    fields use ``total=False`` because asyncpg Records may contain None for
    nullable columns, and callers use ``.get()`` with fallback defaults.

    Required fields (always present in the query result):
        id: Pattern UUID primary key.
        pattern_signature: Unique signature string.
        status: Current lifecycle status (candidate / provisional / validated / deprecated).
        evidence_tier: Denormalized evidence tier (unmeasured / observed / measured / verified).

    Metric fields (nullable in DB, accessed via ``.get()`` with default 0):
        injection_count_rolling_20: Rolling window injection count.
        success_count_rolling_20: Rolling window success count.
        failure_count_rolling_20: Rolling window failure count.
        failure_streak: Current consecutive failure count.
    """

    injection_count_rolling_20: int | None
    success_count_rolling_20: int | None
    failure_count_rolling_20: int | None
    failure_streak: int | None


@runtime_checkable
class ProtocolApplyTransition(Protocol):
    """Protocol for the ``apply_transition`` function from handler_transition.

    Typed callable protocol replacing ``Callable[..., Any]`` so that callers
    get static type safety on the return type (``ModelTransitionResult``).

    The positional parameters mirror ``apply_transition()`` exactly:
        1. repository (ProtocolPatternRepository)
        2. idempotency_store (ProtocolIdempotencyStore | None)
        3. producer (ProtocolKafkaPublisher)

    All remaining parameters are keyword-only.
    """

    async def __call__(
        self,
        repository: ProtocolPatternRepository,
        idempotency_store: ProtocolIdempotencyStore | None,
        producer: ProtocolKafkaPublisher,
        *,
        request_id: UUID,
        correlation_id: UUID,
        pattern_id: UUID,
        from_status: EnumPatternLifecycleStatus,
        to_status: EnumPatternLifecycleStatus,
        trigger: str,
        actor: str,
        reason: str | None,
        gate_snapshot: ModelGateSnapshot | dict[str, object] | None,
        transition_at: datetime,
        publish_topic: str | None,
    ) -> ModelTransitionResult: ...


class AutoPromoteResult(TypedDict):
    """Result of a single auto-promotion attempt."""

    pattern_id: UUID
    from_status: str
    to_status: str
    promoted: bool
    reason: str
    evidence_tier: str
    gate_snapshot: dict[str, Any]  # any-ok: dynamically typed gate snapshot data


class AutoPromoteCheckResult(TypedDict):
    """Aggregated result of auto-promote check."""

    candidates_checked: int
    candidates_promoted: int
    provisionals_checked: int
    provisionals_promoted: int
    results: list[AutoPromoteResult]


# =============================================================================
# Pure Functions
# =============================================================================


def _meets_promotion_criteria(
    pattern: PatternMetricsRow,
    *,
    min_injection_count: int,
    min_success_rate: float = MIN_SUCCESS_RATE,
    max_failure_streak: int = MAX_FAILURE_STREAK,
) -> bool:
    """Check if a pattern meets promotion criteria (shared logic).

    Pure function. Evidence tier is pre-filtered in SQL query.

    Args:
        pattern: Pattern record containing rolling metrics.
        min_injection_count: Minimum injections required.
        min_success_rate: Minimum success rate (0.0-1.0).
        max_failure_streak: Maximum consecutive failures.

    Returns:
        True if pattern meets all metric gates.
    """
    injection_count = pattern.get("injection_count_rolling_20", 0) or 0
    success_count = pattern.get("success_count_rolling_20", 0) or 0
    failure_count = pattern.get("failure_count_rolling_20", 0) or 0
    failure_streak = pattern.get("failure_streak", 0) or 0

    if injection_count < min_injection_count:
        return False

    total_outcomes = success_count + failure_count
    if total_outcomes == 0:
        return False

    if (success_count / total_outcomes) < min_success_rate:
        return False

    if failure_streak >= max_failure_streak:
        return False

    return True


def meets_candidate_to_provisional_criteria(
    pattern: PatternMetricsRow,
    *,
    min_injection_count: int = MIN_INJECTION_COUNT_PROVISIONAL,
    min_success_rate: float = MIN_SUCCESS_RATE,
    max_failure_streak: int = MAX_FAILURE_STREAK,
) -> bool:
    """Check if a candidate pattern meets CANDIDATE -> PROVISIONAL criteria.

    Pure function. Evidence tier is pre-filtered in SQL query.
    """
    return _meets_promotion_criteria(
        pattern,
        min_injection_count=min_injection_count,
        min_success_rate=min_success_rate,
        max_failure_streak=max_failure_streak,
    )


def meets_provisional_to_validated_criteria(
    pattern: PatternMetricsRow,
    *,
    min_injection_count: int = MIN_INJECTION_COUNT_VALIDATED,
    min_success_rate: float = MIN_SUCCESS_RATE,
    max_failure_streak: int = MAX_FAILURE_STREAK,
) -> bool:
    """Check if a provisional pattern meets PROVISIONAL -> VALIDATED criteria.

    Pure function. Evidence tier is pre-filtered in SQL query.
    """
    return _meets_promotion_criteria(
        pattern,
        min_injection_count=min_injection_count,
        min_success_rate=min_success_rate,
        max_failure_streak=max_failure_streak,
    )


def _calculate_success_rate(pattern: PatternMetricsRow) -> float:
    """Calculate success rate from pattern data. Returns 0.0 if no outcomes."""
    success_count = pattern.get("success_count_rolling_20", 0) or 0
    failure_count = pattern.get("failure_count_rolling_20", 0) or 0
    total = success_count + failure_count
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, success_count / total))


async def _build_enriched_gate_snapshot(
    pattern: PatternMetricsRow,
    *,
    conn: ProtocolPatternRepository,
    correlation_id: UUID,
) -> ModelGateSnapshot:
    """Build gate snapshot enriched with evidence tier data.

    Args:
        pattern: Pattern record from SQL query.
        conn: Database connection for attribution count lookup.
        correlation_id: Correlation ID for traceability in warning logs.

    Returns:
        ModelGateSnapshot with evidence tier fields populated.
    """
    pattern_id = pattern["id"]
    raw_evidence_tier = pattern.get("evidence_tier", "unmeasured")
    # Validate against known values to prevent Pydantic ValidationError.
    # Cast is safe: we check membership in _VALID_EVIDENCE_TIERS which
    # exactly matches EvidenceTierLiteral, or assign None.
    evidence_tier: EvidenceTierLiteral | None = (
        cast(EvidenceTierLiteral, raw_evidence_tier)
        if raw_evidence_tier in _VALID_EVIDENCE_TIERS
        else None
    )

    # Count measured attributions
    attribution_count = 0
    try:
        count_row = await conn.fetchrow(SQL_COUNT_ATTRIBUTIONS, pattern_id)
        if count_row:
            attribution_count = count_row["count"]
    except Exception:  # broad-catch-ok: asyncpg driver boundary
        # asyncpg raises driver-specific exceptions (InterfaceError,
        # PostgresError, etc.) that are not stable across versions. We log
        # with exc_info=True so the full traceback is visible, then fall
        # through with attribution_count=0 so promotion evaluation can still
        # proceed with conservative defaults.
        logger.warning(
            "Failed to count attributions for gate snapshot",
            extra={
                "correlation_id": str(correlation_id),
                "pattern_id": str(pattern_id),
            },
            exc_info=True,
        )

    # Get latest run result (validate against known values)
    latest_run_result = None
    try:
        run_row = await conn.fetchrow(SQL_LATEST_RUN_RESULT, pattern_id)
        if run_row:
            raw_result = run_row.get("run_result")
            latest_run_result = raw_result if raw_result in _VALID_RUN_RESULTS else None
    except Exception:  # broad-catch-ok: asyncpg driver boundary
        # Same rationale as attribution count above. DB errors yield
        # latest_run_result=None (conservative default).
        logger.warning(
            "Failed to get latest run result for gate snapshot",
            extra={
                "correlation_id": str(correlation_id),
                "pattern_id": str(pattern_id),
            },
            exc_info=True,
        )

    return ModelGateSnapshot(
        success_rate_rolling_20=_calculate_success_rate(pattern),
        injection_count_rolling_20=pattern.get("injection_count_rolling_20", 0) or 0,
        failure_streak=pattern.get("failure_streak", 0) or 0,
        disabled=False,  # Already filtered in query
        evidence_tier=evidence_tier,
        measured_attribution_count=attribution_count,
        latest_run_result=latest_run_result,
    )


# =============================================================================
# Handler Functions
# =============================================================================


async def handle_auto_promote_check(
    repository: ProtocolPatternRepository,
    *,
    apply_transition_fn: ProtocolApplyTransition,
    idempotency_store: ProtocolIdempotencyStore | None = None,
    producer: ProtocolKafkaPublisher,
    correlation_id: UUID | None = None,
    publish_topic: str | None = None,
) -> AutoPromoteCheckResult:
    """Check and auto-promote patterns based on evidence tier gating.

    Main entry point for L2 Lifecycle Controller. Handles both:
    - CANDIDATE -> PROVISIONAL (evidence_tier >= OBSERVED)
    - PROVISIONAL -> VALIDATED (evidence_tier >= MEASURED)

    Calls ``apply_transition()`` for each eligible pattern to ensure
    the standard transition machinery (idempotency, audit trail, Kafka)
    is used.

    Args:
        repository: Database repository for pattern queries.
        apply_transition_fn: The ``apply_transition`` function from
            handler_transition.py. Injected to avoid circular imports.
        idempotency_store: Idempotency store for transition deduplication.
            May be None -- ``apply_transition()`` accepts an Optional
            idempotency store and skips deduplication when None.
            Callers that need idempotency should pass a concrete store.
        producer: Kafka producer for transition events. Required infrastructure
            — Kafka is the only transition path. Passing None is a programming
            error. Must be passed as a keyword argument.
        correlation_id: Optional correlation ID for tracing. When None a
            single fallback UUID is generated and reused for every
            transition in this invocation to ensure consistent tracing.
        publish_topic: Kafka topic for transition events. When ``None``, the
            ``apply_transition`` machinery uses its own default topic (typically
            the contract-declared publish topic). Callers that need to override
            the topic should pass an explicit string. ``None`` is a valid
            "use the default" signal, not a programming error.

    Returns:
        AutoPromoteCheckResult with per-pattern promotion details.
    """
    # Generate the fallback correlation_id ONCE so both candidate and
    # provisional phases share the same trace ID (M4 fix).
    effective_correlation_id: UUID = correlation_id or uuid4()

    logger.info(
        "Starting evidence-gated auto-promote check",
        extra={
            "correlation_id": str(effective_correlation_id),
        },
    )

    results: list[AutoPromoteResult] = []
    candidates_promoted = 0
    provisionals_promoted = 0

    # Phase 1: CANDIDATE -> PROVISIONAL
    candidate_patterns = await repository.fetch(SQL_FETCH_CANDIDATE_PATTERNS)
    logger.debug(
        "Fetched candidate patterns for CANDIDATE -> PROVISIONAL",
        extra={
            "correlation_id": str(effective_correlation_id),
            "pattern_count": len(candidate_patterns),
        },
    )

    for _raw_pattern in candidate_patterns:
        # Cast contract: SQL_FETCH_CANDIDATE_PATTERNS returns rows matching PatternMetricsRow shape
        pattern = cast(PatternMetricsRow, _raw_pattern)
        # Runtime guard: verify critical fields exist before proceeding.
        # If SQL columns change, this surfaces the error explicitly instead
        # of silently returning None on TypedDict key access.
        if "id" not in pattern or "pattern_signature" not in pattern:
            # Runtime guard: cast() does not validate keys at runtime.
            # mypy marks this as unreachable because the base TypedDict
            # guarantees these keys, but asyncpg rows may not conform.
            logger.warning(  # type: ignore[unreachable]
                "Skipping candidate pattern: missing required fields (id, pattern_signature)",
                extra={
                    "correlation_id": str(effective_correlation_id),
                    "available_keys": list(pattern.keys())
                    if hasattr(pattern, "keys")
                    else "N/A",
                },
            )
            continue
        if not meets_candidate_to_provisional_criteria(pattern):
            continue

        pattern_id = pattern["id"]
        gate_snapshot: ModelGateSnapshot | None = None
        request_id = uuid4()
        now = datetime.now(UTC)

        try:
            gate_snapshot = await _build_enriched_gate_snapshot(
                pattern, conn=repository, correlation_id=effective_correlation_id
            )
            transition_result = await apply_transition_fn(
                repository,
                idempotency_store,
                producer,
                request_id=request_id,
                correlation_id=effective_correlation_id,
                pattern_id=pattern_id,
                from_status=EnumPatternLifecycleStatus.CANDIDATE,
                to_status=EnumPatternLifecycleStatus.PROVISIONAL,
                trigger="auto_promote_evidence_gate",
                actor="auto_promote_handler",
                reason=f"Auto-promoted: evidence_tier={pattern.get('evidence_tier')}, "
                f"success_rate={gate_snapshot.success_rate_rolling_20:.2%}",
                gate_snapshot=gate_snapshot,
                transition_at=now,
                publish_topic=publish_topic,
            )

            promoted = transition_result.success and not transition_result.duplicate
            if promoted:
                candidates_promoted += 1

            results.append(
                AutoPromoteResult(
                    pattern_id=pattern_id,
                    from_status="candidate",
                    to_status="provisional",
                    promoted=promoted,
                    reason=transition_result.reason or "auto_promote_evidence_gate",
                    evidence_tier=pattern.get("evidence_tier", "unknown"),
                    gate_snapshot=gate_snapshot.model_dump(mode="json"),
                )
            )

        except Exception as exc:  # broad-catch-ok: asyncpg driver boundary
            sanitized_err = get_log_sanitizer().sanitize(str(exc))
            logger.error(
                "Failed to promote candidate pattern",
                extra={
                    "correlation_id": str(effective_correlation_id),
                    "pattern_id": str(pattern_id),
                    "error": sanitized_err,
                },
                exc_info=True,
            )
            results.append(
                AutoPromoteResult(
                    pattern_id=pattern_id,
                    from_status="candidate",
                    to_status="provisional",
                    promoted=False,
                    reason=f"promotion_failed: {type(exc).__name__}: {sanitized_err}",
                    evidence_tier=pattern.get("evidence_tier", "unknown"),
                    gate_snapshot=gate_snapshot.model_dump(mode="json")
                    if gate_snapshot is not None
                    else {},
                )
            )

    # Phase 2: PROVISIONAL -> VALIDATED
    provisional_patterns = await repository.fetch(
        SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER
    )
    logger.debug(
        "Fetched provisional patterns for PROVISIONAL -> VALIDATED",
        extra={
            "correlation_id": str(effective_correlation_id),
            "pattern_count": len(provisional_patterns),
        },
    )

    for _raw_pattern in provisional_patterns:
        # Cast contract: SQL_FETCH_PROVISIONAL_PATTERNS returns rows matching PatternMetricsRow shape
        pattern = cast(PatternMetricsRow, _raw_pattern)
        # Runtime guard: verify critical fields exist before proceeding.
        if "id" not in pattern or "pattern_signature" not in pattern:
            # Runtime guard: cast() does not validate keys at runtime.
            # mypy marks this as unreachable because the base TypedDict
            # guarantees these keys, but asyncpg rows may not conform.
            logger.warning(  # type: ignore[unreachable]
                "Skipping provisional pattern: missing required fields (id, pattern_signature)",
                extra={
                    "correlation_id": str(effective_correlation_id),
                    "available_keys": list(pattern.keys())
                    if hasattr(pattern, "keys")
                    else "N/A",
                },
            )
            continue
        if not meets_provisional_to_validated_criteria(pattern):
            continue

        pattern_id = pattern["id"]
        gate_snapshot = None
        request_id = uuid4()
        now = datetime.now(UTC)

        try:
            gate_snapshot = await _build_enriched_gate_snapshot(
                pattern, conn=repository, correlation_id=effective_correlation_id
            )
            transition_result = await apply_transition_fn(
                repository,
                idempotency_store,
                producer,
                request_id=request_id,
                correlation_id=effective_correlation_id,
                pattern_id=pattern_id,
                from_status=EnumPatternLifecycleStatus.PROVISIONAL,
                to_status=EnumPatternLifecycleStatus.VALIDATED,
                trigger="auto_promote_evidence_gate",
                actor="auto_promote_handler",
                reason=f"Auto-promoted: evidence_tier={pattern.get('evidence_tier')}, "
                f"success_rate={gate_snapshot.success_rate_rolling_20:.2%}",
                gate_snapshot=gate_snapshot,
                transition_at=now,
                publish_topic=publish_topic,
            )

            promoted = transition_result.success and not transition_result.duplicate
            if promoted:
                provisionals_promoted += 1

            results.append(
                AutoPromoteResult(
                    pattern_id=pattern_id,
                    from_status="provisional",
                    to_status="validated",
                    promoted=promoted,
                    reason=transition_result.reason or "auto_promote_evidence_gate",
                    evidence_tier=pattern.get("evidence_tier", "unknown"),
                    gate_snapshot=gate_snapshot.model_dump(mode="json"),
                )
            )

        except Exception as exc:  # broad-catch-ok: asyncpg driver boundary
            sanitized_err = get_log_sanitizer().sanitize(str(exc))
            logger.error(
                "Failed to promote provisional pattern",
                extra={
                    "correlation_id": str(effective_correlation_id),
                    "pattern_id": str(pattern_id),
                    "error": sanitized_err,
                },
                exc_info=True,
            )
            results.append(
                AutoPromoteResult(
                    pattern_id=pattern_id,
                    from_status="provisional",
                    to_status="validated",
                    promoted=False,
                    reason=f"promotion_failed: {type(exc).__name__}: {sanitized_err}",
                    evidence_tier=pattern.get("evidence_tier", "unknown"),
                    gate_snapshot=gate_snapshot.model_dump(mode="json")
                    if gate_snapshot is not None
                    else {},
                )
            )

    logger.info(
        "Evidence-gated auto-promote check complete",
        extra={
            "correlation_id": str(effective_correlation_id),
            "candidates_checked": len(candidate_patterns),
            "candidates_promoted": candidates_promoted,
            "provisionals_checked": len(provisional_patterns),
            "provisionals_promoted": provisionals_promoted,
        },
    )

    return AutoPromoteCheckResult(
        candidates_checked=len(candidate_patterns),
        candidates_promoted=candidates_promoted,
        provisionals_checked=len(provisional_patterns),
        provisionals_promoted=provisionals_promoted,
        results=results,
    )


__all__ = [
    "AutoPromoteCheckResult",
    "AutoPromoteResult",
    "MAX_FAILURE_STREAK",
    "MIN_INJECTION_COUNT_PROVISIONAL",
    "MIN_INJECTION_COUNT_VALIDATED",
    "MIN_SUCCESS_RATE",
    "PatternMetricsRow",
    "ProtocolApplyTransition",
    "handle_auto_promote_check",
    "meets_candidate_to_provisional_criteria",
    "meets_provisional_to_validated_criteria",
]
