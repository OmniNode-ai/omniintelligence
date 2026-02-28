# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern lifecycle status transitions.

This module implements the pattern lifecycle transition logic: applying
status changes atomically with audit trail and idempotency guarantees.

This is the ONLY code path that may update learned_patterns.status.

Atomicity Guarantee:
--------------------
When ``conn`` is provided, UPDATE and INSERT execute in the caller's transaction.
When ``conn`` is None, operations execute independently on the repository connection.
Callers requiring atomicity MUST provide a transactional connection.

    1. UPDATE learned_patterns SET status = $to_status (with status guard)
    2. INSERT INTO pattern_lifecycle_transitions (audit record)

If a transactional ``conn`` is provided and either operation fails, both are
rolled back by the caller's transaction. If ``conn`` is None, the two operations
are independent and a failure after the UPDATE but before the INSERT could leave
the status updated without an audit record.

Idempotency:
------------
Uses request_id as idempotency key (when idempotency_store is provided):
    1. Before applying: check if request_id was already processed
    2. If duplicate: return success=true, duplicate=true immediately
    3. After success: record request_id to prevent replay

The idempotency store is OPTIONAL. When None, idempotency checks are skipped
and all requests are treated as new. This aligns with the optional Kafka pattern.

Note: The idempotency record() call is best-effort and not part of the DB
transaction. A crash between DB commit and record() allows replay, which is
safe because the transition is idempotent by (pattern_id, from_status, to_status)
check via the status guard WHERE clause.

Status Guard:
-------------
The UPDATE includes a WHERE clause that checks:
    - id = $pattern_id
    - status = $from_status (optimistic locking)

If the pattern's current status doesn't match from_status, zero rows
are updated and we return a StatusMismatchError.

PROVISIONAL Guard:
------------------
Legacy protection: most transitions TO "provisional" are rejected.
The exception is CANDIDATE -> PROVISIONAL, which is the valid lifecycle
promotion path (introduced by OMN-2133). All other transitions to
PROVISIONAL are blocked to prevent patterns from being created directly
as PROVISIONAL (the old bootstrap state).

Kafka Publisher Optionality:
----------------------------
The ``kafka_producer`` dependency is OPTIONAL (contract marks it as ``required: false``).
When the Kafka publisher is unavailable (None), transitions still occur in the database,
but ``PatternLifecycleTransitioned`` events are NOT emitted to Kafka.

Design Principles:
    - Transaction-scoped atomicity when caller provides ``conn``
    - Request-ID-based idempotency for exactly-once semantics (when store provided)
    - Status guard for optimistic locking
    - PROVISIONAL guard for legacy protection
    - Protocol-based dependency injection for testability
    - Kafka event emission for downstream notification (when available)
    - Idempotency store is optional (same pattern as Kafka producer)
    - asyncpg-style positional parameters ($1, $2, etc.)

Reference:
    - OMN-1805: Pattern lifecycle effect node with atomic projections
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from omniintelligence.enums import EnumEvidenceTier, EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot
from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
    ModelPatternLifecycleTransitionedEvent,
    ModelTransitionResult,
)
from omniintelligence.protocols import (
    ProtocolIdempotencyStore,
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer
from omniintelligence.utils.pg_status import parse_pg_status_count

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

PROVISIONAL_STATUS: EnumPatternLifecycleStatus = EnumPatternLifecycleStatus.PROVISIONAL
"""Legacy status that new transitions are not allowed to target."""


# =============================================================================
# SQL Queries
# =============================================================================

# Update pattern status with guard clause
SQL_UPDATE_PATTERN_STATUS = """
UPDATE learned_patterns
SET status = $2,
    updated_at = $3
WHERE id = $1
  AND status = $4
"""

# Insert audit record into lifecycle transitions table
SQL_INSERT_LIFECYCLE_TRANSITION = """
INSERT INTO pattern_lifecycle_transitions (
    id,
    pattern_id,
    from_status,
    to_status,
    transition_trigger,
    actor,
    reason,
    gate_snapshot,
    transition_at,
    request_id,
    correlation_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""

# Check if pattern exists, get current status and evidence tier
SQL_GET_PATTERN_STATUS = """
SELECT id, status, evidence_tier
FROM learned_patterns
WHERE id = $1
"""


# =============================================================================
# Handler Functions
# =============================================================================


async def apply_transition(
    repository: ProtocolPatternRepository,
    idempotency_store: ProtocolIdempotencyStore | None,
    producer: ProtocolKafkaPublisher | None,
    *,
    request_id: UUID,
    correlation_id: UUID,
    pattern_id: UUID,
    from_status: EnumPatternLifecycleStatus,
    to_status: EnumPatternLifecycleStatus,
    trigger: str,
    actor: str = "reducer",
    reason: str | None = None,
    gate_snapshot: ModelGateSnapshot | dict[str, object] | None = None,
    transition_at: datetime,
    publish_topic: str | None = None,
    conn: ProtocolPatternRepository | None = None,
) -> ModelTransitionResult:
    """Apply a pattern status transition with audit trail and idempotency.

    This is the main entry point for the transition handler. It:
    1. Validates PROVISIONAL guard (rejects to_status == "provisional")
    2. Checks idempotency store for duplicate request_id (when store provided)
    3. UPDATE pattern status + INSERT audit record (via ``conn`` or ``repository``)
    4. Records idempotency key AFTER successful database operations (best-effort)
    5. Emits Kafka event (if producer available) - failures don't fail the operation

    Atomicity Guarantee:
        When ``conn`` is provided, UPDATE and INSERT execute in the caller's
        transaction. When ``conn`` is None, operations execute independently on
        the repository connection. Callers requiring atomicity MUST provide a
        transactional connection.

    Idempotency Timing:
        The idempotency key is recorded AFTER successful database operations,
        not before. This ensures that failed operations can be retried with
        the same request_id. The record() call is best-effort and not part of
        the DB transaction; see inline comments for safety rationale.

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        idempotency_store: Optional idempotency store for request_id deduplication.
            When None, idempotency checks are skipped and all requests are
            treated as new. This follows the same optional-dependency pattern
            as the Kafka producer.
        producer: Optional Kafka producer implementing ProtocolKafkaPublisher.
            If None, Kafka events are not emitted but database transitions
            still occur.
        request_id: Idempotency key - MUST match original event.request_id.
        correlation_id: For distributed tracing.
        pattern_id: Pattern to update.
        from_status: Expected current status (for optimistic locking).
        to_status: New status to apply.
        trigger: What triggered this transition.
        actor: Who applied the transition.
        reason: Human-readable reason (optional).
        gate_snapshot: Gate values at decision time (optional).
        transition_at: When to record as transition time.
        publish_topic: Full Kafka topic for publishing transition events.
            Source of truth is the contract's event_bus.publish_topics.
            Required when producer is provided; can be None if producer
            is None (no Kafka emission).
        conn: Optional transactional connection. When provided, all DB
            operations use this connection for transaction control (both
            the UPDATE and INSERT execute within the caller's transaction
            boundary, ensuring atomicity). When None, operations execute
            on the repository directly, and each statement auto-commits
            independently.

    Returns:
        ModelTransitionResult with transition outcome. On validation failure
        (e.g., PROVISIONAL guard, missing publish_topic), returns result
        with success=False and descriptive error_message rather than raising.
    """
    logger.info(
        "Applying pattern lifecycle transition",
        extra={
            "correlation_id": str(correlation_id),
            "request_id": str(request_id),
            "pattern_id": str(pattern_id),
            "from_status": from_status,
            "to_status": to_status,
            "trigger": trigger,
        },
    )

    # Trigger documents why the transition occurred - empty triggers make audit logs useless
    if not trigger or not trigger.strip():
        logger.warning(
            "Empty trigger rejected - trigger is required for audit trail",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "from_status": from_status,
                "to_status": to_status,
            },
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason="Validation error: trigger is required",
            transitioned_at=None,
            error_message="Trigger cannot be empty or whitespace-only. "
            "A meaningful trigger is required for audit trail integrity.",
        )

    # Validate publish_topic when Kafka producer is available - must fail before any DB ops
    # to avoid partial-success states where DB writes succeed but events cannot be emitted.
    if producer is not None and publish_topic is None:
        logger.warning(
            "publish_topic required when producer is available",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "from_status": from_status,
                "to_status": to_status,
            },
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason="Configuration error: publish_topic required with Kafka producer",
            transitioned_at=None,
            error_message="publish_topic is required when Kafka producer is available. "
            "Provide the full topic from the contract's event_bus.publish_topics.",
        )

    # PROVISIONAL guard: reject transitions TO provisional EXCEPT CANDIDATE -> PROVISIONAL
    # (CANDIDATE -> PROVISIONAL is the valid lifecycle promotion path, OMN-2133)
    if (
        to_status == PROVISIONAL_STATUS
        and from_status != EnumPatternLifecycleStatus.CANDIDATE
    ):
        logger.warning(
            "PROVISIONAL guard: Rejecting non-CANDIDATE transition to provisional",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "from_status": from_status,
                "to_status": to_status,
            },
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason="PROVISIONAL guard: Only CANDIDATE -> PROVISIONAL is allowed",
            transitioned_at=None,
            error_message="Transitions to 'provisional' status are only allowed from "
            "'candidate'. Use CANDIDATE -> PROVISIONAL for lifecycle promotion.",
        )

    # Evidence tier enforcement is deferred until after pattern lookup because we need
    # the current evidence_tier from the database. Rules: PROVISIONAL requires >= OBSERVED,
    # VALIDATED requires >= MEASURED. See enforcement code after pattern fetch below.

    # Check idempotency before hitting the database: use exists() WITHOUT recording yet.
    # Recording happens AFTER successful DB operations so failed ops remain retriable.
    # When idempotency_store is None, skip (all requests treated as new).
    if idempotency_store is not None:
        is_duplicate = await idempotency_store.exists(request_id)
        if is_duplicate:
            logger.info(
                "Duplicate request_id detected - returning cached success",
                extra={
                    "correlation_id": str(correlation_id),
                    "request_id": str(request_id),
                    "pattern_id": str(pattern_id),
                },
            )
            return ModelTransitionResult(
                success=True,
                duplicate=True,
                pattern_id=pattern_id,
                from_status=from_status,
                to_status=to_status,
                transition_id=None,
                reason="Duplicate request - transition already applied",
                transitioned_at=None,
            )

    # Verify pattern exists and check current status.
    # Use conn if provided for external transaction control, otherwise use repository
    db = conn if conn is not None else repository
    pattern_row = await db.fetchrow(SQL_GET_PATTERN_STATUS, pattern_id)
    if pattern_row is None:
        logger.warning(
            "Pattern not found",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
            },
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason="Pattern not found",
            transitioned_at=None,
            error_message=f"Pattern with ID {pattern_id} does not exist",
        )

    # Evidence tier enforcement (OMN-2133): read from pattern row (added in migration 011).
    # If null or unparseable, treat as UNMEASURED for defensive minimum-privilege behavior.
    raw_evidence_tier = pattern_row.get("evidence_tier")
    try:
        current_evidence_tier = (
            EnumEvidenceTier(raw_evidence_tier)
            if raw_evidence_tier
            else EnumEvidenceTier.UNMEASURED
        )
    except ValueError:
        logger.warning(
            "Unparseable evidence_tier, treating as UNMEASURED",
            extra={
                "correlation_id": str(correlation_id),
                "pattern_id": str(pattern_id),
                "raw_evidence_tier": raw_evidence_tier,
            },
        )
        current_evidence_tier = EnumEvidenceTier.UNMEASURED

    # Guard: CANDIDATE -> PROVISIONAL requires evidence_tier >= OBSERVED
    if (
        to_status == EnumPatternLifecycleStatus.PROVISIONAL
        and current_evidence_tier < EnumEvidenceTier.OBSERVED
    ):
        logger.warning(
            "Evidence tier guard: insufficient tier for PROVISIONAL",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "evidence_tier": current_evidence_tier.value,
                "required_tier": EnumEvidenceTier.OBSERVED.value,
            },
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason="Evidence tier guard: insufficient evidence for PROVISIONAL",
            transitioned_at=None,
            error_message=f"Transition to PROVISIONAL requires evidence_tier >= OBSERVED, "
            f"but pattern has evidence_tier='{current_evidence_tier.value}'.",
        )

    # Guard: PROVISIONAL -> VALIDATED requires evidence_tier >= MEASURED
    if (
        to_status == EnumPatternLifecycleStatus.VALIDATED
        and current_evidence_tier < EnumEvidenceTier.MEASURED
    ):
        logger.warning(
            "Evidence tier guard: insufficient tier for VALIDATED",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "evidence_tier": current_evidence_tier.value,
                "required_tier": EnumEvidenceTier.MEASURED.value,
            },
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason="Evidence tier guard: insufficient evidence for VALIDATED",
            transitioned_at=None,
            error_message=f"Transition to VALIDATED requires evidence_tier >= MEASURED, "
            f"but pattern has evidence_tier='{current_evidence_tier.value}'.",
        )

    # UPDATE status + INSERT audit record on the same db handle for atomicity.
    # Atomicity guarantee: when conn is provided both execute in caller's transaction;
    # when conn is None they auto-commit independently (callers requiring atomicity MUST
    # pass conn).
    transition_id = uuid4()

    try:
        # Update pattern status with guard clause
        update_status = await db.execute(
            SQL_UPDATE_PATTERN_STATUS,
            pattern_id,
            to_status.value,
            transition_at,
            from_status.value,  # Status guard - must match current status
        )
        rows_updated = parse_pg_status_count(update_status)

        if rows_updated == 0:
            # Status guard failed - current status doesn't match from_status
            current_status = pattern_row.get("status", "unknown")
            logger.warning(
                "Status guard failed - current status does not match from_status",
                extra={
                    "correlation_id": str(correlation_id),
                    "request_id": str(request_id),
                    "pattern_id": str(pattern_id),
                    "expected_status": from_status,
                    "current_status": current_status,
                },
            )
            return ModelTransitionResult(
                success=False,
                duplicate=False,
                pattern_id=pattern_id,
                from_status=from_status,
                to_status=to_status,
                transition_id=None,
                reason="Status guard failed",
                transitioned_at=None,
                error_message=f"Expected status '{from_status}' but pattern has status "
                f"'{current_status}'. Transition rejected (optimistic lock failure).",
            )

        # Insert audit record
        # Convert gate_snapshot to JSON string if present
        # Handle both ModelGateSnapshot (Pydantic) and dict for backwards compatibility
        # Enrich with evidence_tier from the pattern row (OMN-2133)
        if gate_snapshot is None:
            # Create minimal snapshot with evidence_tier for audit trail
            gate_snapshot_json = json.dumps(
                {
                    "evidence_tier": current_evidence_tier.value,
                }
            )
        elif isinstance(gate_snapshot, dict):
            # Enrich dict with evidence_tier if not already present
            enriched = {**gate_snapshot}
            if "evidence_tier" not in enriched:
                enriched["evidence_tier"] = current_evidence_tier.value
            gate_snapshot_json = json.dumps(enriched)
        else:
            # ModelGateSnapshot - serialize and enrich with evidence_tier
            snapshot_dict = gate_snapshot.model_dump(mode="json")
            if snapshot_dict.get("evidence_tier") is None:
                snapshot_dict["evidence_tier"] = current_evidence_tier.value
            gate_snapshot_json = json.dumps(snapshot_dict)

        await db.execute(
            SQL_INSERT_LIFECYCLE_TRANSITION,
            transition_id,
            pattern_id,
            from_status.value,
            to_status.value,
            trigger,
            actor,
            reason,
            gate_snapshot_json,
            transition_at,
            request_id,
            correlation_id,
        )

        # Record idempotency key AFTER DB success so failed ops stay retriable.
        # Best-effort: not part of the DB transaction. A crash between commit and record()
        # allows replay, which is safe by (pattern_id, from_status, to_status) idempotency.
        if idempotency_store is not None:
            await idempotency_store.record(request_id)

        logger.info(
            "Pattern lifecycle transition applied successfully",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "transition_id": str(transition_id),
                "from_status": from_status,
                "to_status": to_status,
            },
        )

    except Exception as exc:
        sanitized_error = get_log_sanitizer().sanitize(str(exc))
        logger.error(
            "Failed to apply pattern lifecycle transition",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "error": sanitized_error,
                "error_type": type(exc).__name__,
            },
            exc_info=True,
        )
        return ModelTransitionResult(
            success=False,
            duplicate=False,
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            transition_id=None,
            reason=f"Database error: {type(exc).__name__}",
            transitioned_at=None,
            error_message=sanitized_error,
        )

    # Emit Kafka event if producer is available. Kafka failures do NOT fail the main
    # operation — DB transition already committed. Failed events route to DLQ.
    if producer is not None:
        # Type narrowing: Step 0b validates publish_topic when producer is available
        if publish_topic is None:  # pragma: no cover - guarded by Step 0b
            raise ValueError("publish_topic is required when producer is available")
        try:
            await _emit_transition_event(
                producer=producer,
                pattern_id=pattern_id,
                from_status=from_status,
                to_status=to_status,
                trigger=trigger,
                actor=actor,
                reason=reason,
                transition_id=transition_id,
                transitioned_at=transition_at,
                request_id=request_id,
                correlation_id=correlation_id,
                topic=publish_topic,
            )
        except Exception as kafka_exc:
            # Kafka failure - log with sanitization and route to DLQ
            # The main operation succeeded, so we return success below
            sanitizer = get_log_sanitizer()
            sanitized_error = sanitizer.sanitize(str(kafka_exc))

            logger.error(
                "Kafka event emission failed - routing to DLQ",
                extra={
                    "correlation_id": str(correlation_id),
                    "request_id": str(request_id),
                    "pattern_id": str(pattern_id),
                    "transition_id": str(transition_id),
                    "error": sanitized_error,
                    "error_type": type(kafka_exc).__name__,
                },
            )

            # Attempt DLQ routing (best effort, don't fail on DLQ errors)
            await _send_to_dlq(
                producer=producer,
                pattern_id=pattern_id,
                from_status=from_status,
                to_status=to_status,
                trigger=trigger,
                actor=actor,
                reason=reason,
                transition_id=transition_id,
                transitioned_at=transition_at,
                request_id=request_id,
                correlation_id=correlation_id,
                topic=publish_topic,
                error_message=sanitized_error,
            )

    return ModelTransitionResult(
        success=True,
        duplicate=False,
        pattern_id=pattern_id,
        from_status=from_status,
        to_status=to_status,
        transition_id=transition_id,
        reason=reason or f"Transition applied: {trigger}",
        transitioned_at=transition_at,
    )


async def _emit_transition_event(
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    from_status: EnumPatternLifecycleStatus,
    to_status: EnumPatternLifecycleStatus,
    trigger: str,
    actor: str,
    reason: str | None,
    transition_id: UUID,
    transitioned_at: datetime,
    request_id: UUID,
    correlation_id: UUID,
    topic: str,
) -> None:
    """Emit a pattern-lifecycle-transitioned event to Kafka.

    Internal function - assumes topic has been validated by caller.

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The transitioned pattern ID.
        from_status: Previous status.
        to_status: New status.
        trigger: What triggered the transition.
        actor: Who applied the transition.
        reason: Human-readable reason.
        transition_id: Unique ID for this transition audit record.
        transitioned_at: When the transition occurred.
        request_id: Idempotency key.
        correlation_id: For distributed tracing.
        topic: Full Kafka topic for the transition event.
    """
    # Build event payload using the model
    event = ModelPatternLifecycleTransitionedEvent(
        event_type="PatternLifecycleTransitioned",
        pattern_id=pattern_id,
        from_status=from_status,
        to_status=to_status,
        trigger=trigger,
        actor=actor,
        reason=reason,
        transition_id=transition_id,
        transitioned_at=transitioned_at,
        request_id=request_id,
        correlation_id=correlation_id,
    )

    # Publish to Kafka
    await producer.publish(
        topic=topic,
        key=str(pattern_id),
        value=event.model_dump(mode="json"),
    )

    logger.debug(
        "Emitted pattern-lifecycle-transitioned event",
        extra={
            "correlation_id": str(correlation_id),
            "pattern_id": str(pattern_id),
            "transition_id": str(transition_id),
            "topic": topic,
        },
    )


async def _send_to_dlq(
    producer: ProtocolKafkaPublisher,
    pattern_id: UUID,
    from_status: str,
    to_status: str,
    trigger: str,
    actor: str,
    reason: str | None,
    transition_id: UUID,
    transitioned_at: datetime,
    request_id: UUID,
    correlation_id: UUID,
    error_message: str,
    topic: str,
) -> None:
    """Send failed event to Dead Letter Queue with sanitized error message.

    Internal function - assumes topic has been validated by caller.

    DLQ events are sanitized to prevent secrets from leaking during debugging
    and error analysis. This function is best-effort: DLQ send failures are
    logged but do not propagate exceptions.

    Args:
        producer: Kafka producer implementing ProtocolKafkaPublisher.
        pattern_id: The pattern ID for the failed transition.
        from_status: Previous status.
        to_status: Target status.
        trigger: What triggered the transition.
        actor: Who applied the transition.
        reason: Human-readable reason.
        transition_id: Unique ID for this transition.
        transitioned_at: When the transition occurred.
        request_id: Idempotency key.
        correlation_id: For distributed tracing.
        error_message: Sanitized error message (must be pre-sanitized by caller).
        topic: Full Kafka topic for the transition event.
    """
    # Build DLQ topic name: {original_topic}.dlq
    original_topic = topic
    dlq_topic = f"{original_topic}.dlq"

    try:
        # Build DLQ payload with error metadata
        # Note: error_message should already be sanitized by caller
        # Explicit dict[str, object] annotation to satisfy ProtocolKafkaPublisher.publish()
        # (dict is invariant in its value type; without annotation, mypy infers
        # dict[str, str | None] which is not assignable to dict[str, object]).
        dlq_payload: dict[str, object] = {
            "original_topic": original_topic,
            "pattern_id": str(pattern_id),
            "from_status": from_status,
            "to_status": to_status,
            "trigger": trigger,
            "actor": actor,
            "reason": reason,
            "transition_id": str(transition_id),
            "transitioned_at": transitioned_at.isoformat(),
            "request_id": str(request_id),
            "correlation_id": str(correlation_id),
            "error_message": error_message,
            "error_timestamp": datetime.now(UTC).isoformat(),
            "service": "omniintelligence",
        }

        # Sanitize the entire payload to catch any secrets we might have missed
        sanitizer = get_log_sanitizer()
        sanitized_payload: dict[str, object] = {
            k: sanitizer.sanitize(str(v)) if isinstance(v, str) else v
            for k, v in dlq_payload.items()
        }

        await producer.publish(
            topic=dlq_topic,
            key=str(pattern_id),
            value=sanitized_payload,
        )

        logger.info(
            "Event sent to DLQ",
            extra={
                "correlation_id": str(correlation_id),
                "pattern_id": str(pattern_id),
                "transition_id": str(transition_id),
                "dlq_topic": dlq_topic,
            },
        )

    except Exception as dlq_exc:
        # DLQ send failed - log but don't propagate
        # The main operation already succeeded, we can't fail here
        sanitizer = get_log_sanitizer()
        sanitized_dlq_error = sanitizer.sanitize(str(dlq_exc))

        logger.error(
            "Failed to send event to DLQ",
            extra={
                "correlation_id": str(correlation_id),
                "pattern_id": str(pattern_id),
                "transition_id": str(transition_id),
                "dlq_topic": dlq_topic,
                "error": sanitized_dlq_error,
                "error_type": type(dlq_exc).__name__,
            },
        )


__all__ = [
    "ProtocolIdempotencyStore",
    "apply_transition",
]
