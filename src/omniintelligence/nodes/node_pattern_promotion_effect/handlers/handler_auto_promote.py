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
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID, uuid4

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.protocols import ProtocolPatternRepository

if TYPE_CHECKING:
    from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
        ProtocolIdempotencyStore,
    )
    from omniintelligence.protocols import ProtocolKafkaPublisher

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
"""Valid pipeline run result values matching RunResultLiteral."""


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


class AutoPromoteResult(TypedDict):
    """Result of a single auto-promotion attempt."""

    pattern_id: UUID
    from_status: str
    to_status: str
    promoted: bool
    reason: str
    evidence_tier: str
    gate_snapshot: dict[str, Any]


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
    pattern: Mapping[str, Any],
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
    pattern: Mapping[str, Any],
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
    pattern: Mapping[str, Any],
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


def _calculate_success_rate(pattern: Mapping[str, Any]) -> float:
    """Calculate success rate from pattern data. Returns 0.0 if no outcomes."""
    success_count = pattern.get("success_count_rolling_20", 0) or 0
    failure_count = pattern.get("failure_count_rolling_20", 0) or 0
    total = success_count + failure_count
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, success_count / total))


async def _build_enriched_gate_snapshot(
    pattern: Mapping[str, Any],
    *,
    conn: ProtocolPatternRepository,
) -> ModelGateSnapshot:
    """Build gate snapshot enriched with evidence tier data.

    Args:
        pattern: Pattern record from SQL query.
        conn: Database connection for attribution count lookup.

    Returns:
        ModelGateSnapshot with evidence tier fields populated.
    """
    pattern_id = pattern["id"]
    raw_evidence_tier = pattern.get("evidence_tier", "unmeasured")
    # Validate against known values to prevent Pydantic ValidationError
    evidence_tier = (
        raw_evidence_tier if raw_evidence_tier in _VALID_EVIDENCE_TIERS else None
    )

    # Count measured attributions
    attribution_count = 0
    try:
        count_row = await conn.fetchrow(SQL_COUNT_ATTRIBUTIONS, pattern_id)
        if count_row:
            attribution_count = count_row["count"]
    except Exception:
        logger.warning("Failed to count attributions for gate snapshot", exc_info=True)

    # Get latest run result (validate against known values)
    latest_run_result = None
    try:
        run_row = await conn.fetchrow(SQL_LATEST_RUN_RESULT, pattern_id)
        if run_row:
            raw_result = run_row.get("run_result")
            latest_run_result = raw_result if raw_result in _VALID_RUN_RESULTS else None
    except Exception:
        logger.warning(
            "Failed to get latest run result for gate snapshot", exc_info=True
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
    apply_transition_fn: Callable[..., Any],
    idempotency_store: ProtocolIdempotencyStore | None = None,
    producer: ProtocolKafkaPublisher | None = None,
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
        idempotency_store: Optional idempotency store for transition
            deduplication. When None, passed through to apply_transition_fn
            which handles the None case.
        producer: Optional Kafka producer for transition events.
        correlation_id: Optional correlation ID for tracing.
        publish_topic: Kafka topic for transition events (required if producer).

    Returns:
        AutoPromoteCheckResult with per-pattern promotion details.
    """
    logger.info(
        "Starting evidence-gated auto-promote check",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
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
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_count": len(candidate_patterns),
        },
    )

    for pattern in candidate_patterns:
        if not meets_candidate_to_provisional_criteria(pattern):
            continue

        pattern_id = pattern["id"]
        gate_snapshot = await _build_enriched_gate_snapshot(pattern, conn=repository)
        request_id = uuid4()
        now = datetime.now(UTC)

        try:
            transition_result = await apply_transition_fn(
                repository,
                idempotency_store,
                producer,
                request_id=request_id,
                correlation_id=correlation_id or uuid4(),
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

        except Exception as exc:
            logger.error(
                "Failed to promote candidate pattern",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "pattern_id": str(pattern_id),
                    "error": str(exc),
                },
                exc_info=True,
            )
            results.append(
                AutoPromoteResult(
                    pattern_id=pattern_id,
                    from_status="candidate",
                    to_status="provisional",
                    promoted=False,
                    reason=f"promotion_failed: {type(exc).__name__}: {exc!s}",
                    evidence_tier=pattern.get("evidence_tier", "unknown"),
                    gate_snapshot=gate_snapshot.model_dump(mode="json"),
                )
            )

    # Phase 2: PROVISIONAL -> VALIDATED
    provisional_patterns = await repository.fetch(
        SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER
    )
    logger.debug(
        "Fetched provisional patterns for PROVISIONAL -> VALIDATED",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
            "pattern_count": len(provisional_patterns),
        },
    )

    for pattern in provisional_patterns:
        if not meets_provisional_to_validated_criteria(pattern):
            continue

        pattern_id = pattern["id"]
        gate_snapshot = await _build_enriched_gate_snapshot(pattern, conn=repository)
        request_id = uuid4()
        now = datetime.now(UTC)

        try:
            transition_result = await apply_transition_fn(
                repository,
                idempotency_store,
                producer,
                request_id=request_id,
                correlation_id=correlation_id or uuid4(),
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

        except Exception as exc:
            logger.error(
                "Failed to promote provisional pattern",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "pattern_id": str(pattern_id),
                    "error": str(exc),
                },
                exc_info=True,
            )
            results.append(
                AutoPromoteResult(
                    pattern_id=pattern_id,
                    from_status="provisional",
                    to_status="validated",
                    promoted=False,
                    reason=f"promotion_failed: {type(exc).__name__}: {exc!s}",
                    evidence_tier=pattern.get("evidence_tier", "unknown"),
                    gate_snapshot=gate_snapshot.model_dump(mode="json"),
                )
            )

    logger.info(
        "Evidence-gated auto-promote check complete",
        extra={
            "correlation_id": str(correlation_id) if correlation_id else None,
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
    "handle_auto_promote_check",
    "meets_candidate_to_provisional_criteria",
    "meets_provisional_to_validated_criteria",
]
