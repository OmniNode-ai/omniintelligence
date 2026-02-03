# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler functions for pattern lifecycle status transitions.

This module implements the pattern lifecycle transition logic: applying
status changes atomically with audit trail and idempotency guarantees.

This is the ONLY code path that may update learned_patterns.status.

Atomicity Guarantee:
--------------------
Every transition is applied within a single database transaction:
    1. UPDATE learned_patterns SET status = $to_status (with status guard)
    2. INSERT INTO pattern_lifecycle_transitions (audit record)

If either operation fails, both are rolled back.

Idempotency:
------------
Uses request_id as idempotency key:
    1. Before applying: check if request_id was already processed
    2. If duplicate: return success=true, duplicate=true immediately
    3. After success: record request_id to prevent replay

Status Guard:
-------------
The UPDATE includes a WHERE clause that checks:
    - id = $pattern_id
    - status = $from_status (optimistic locking)

If the pattern's current status doesn't match from_status, zero rows
are updated and we return a StatusMismatchError.

PROVISIONAL Guard:
------------------
Legacy protection: transitions TO "provisional" are rejected.
PROVISIONAL was the original bootstrap state before the CANDIDATE ->
PROVISIONAL -> VALIDATED -> DEPRECATED lifecycle was introduced.
New patterns should start as CANDIDATE, not PROVISIONAL.

Kafka Publisher Optionality:
----------------------------
The ``kafka_producer`` dependency is OPTIONAL (contract marks it as ``required: false``).
When the Kafka publisher is unavailable (None), transitions still occur in the database,
but ``PatternLifecycleTransitioned`` events are NOT emitted to Kafka.

Design Principles:
    - Atomic transactions for data integrity
    - Request-ID-based idempotency for exactly-once semantics
    - Status guard for optimistic locking
    - PROVISIONAL guard for legacy protection
    - Protocol-based dependency injection for testability
    - Kafka event emission for downstream notification (when available)
    - asyncpg-style positional parameters ($1, $2, etc.)

Reference:
    - OMN-1805: Pattern lifecycle effect node with atomic projections
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from omniintelligence.constants import TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1
from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_pattern_lifecycle_effect.models import (
    ModelPatternLifecycleTransitionedEvent,
    ModelTransitionResult,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

PROVISIONAL_STATUS: EnumPatternLifecycleStatus = EnumPatternLifecycleStatus.PROVISIONAL
"""Legacy status that new transitions are not allowed to target."""


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolPatternRepository(Protocol):
    """Protocol for pattern data access operations.

    This protocol defines the interface required for database operations
    in the transition handler. It supports both asyncpg connections and
    mock implementations for testing.

    The methods mirror asyncpg.Connection semantics:
        - fetch: Execute query and return list of Records
        - fetchrow: Execute query and return single Record or None
        - execute: Execute query and return status string (e.g., "UPDATE 1")

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

    async def fetchrow(self, query: str, *args: Any) -> Mapping[str, Any] | None:
        """Execute a query and return first row, or None.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            Single record or None if no rows.
        """
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status string.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            Status string from PostgreSQL (e.g., "UPDATE 1", "INSERT 0 1").
        """
        ...


@runtime_checkable
class ProtocolIdempotencyStore(Protocol):
    """Protocol for idempotency key tracking.

    This protocol defines the interface for checking and recording
    idempotency keys (request_id values) to prevent duplicate transitions.

    The implementation may use PostgreSQL, Redis, or in-memory storage
    depending on the deployment environment.

    Idempotency Timing:
        To ensure operations are retriable on failure, the idempotency key
        should be recorded AFTER successful completion:

        1. Call exists() to check for duplicates
        2. If duplicate, return cached success
        3. Perform the operation
        4. On SUCCESS, call record() to mark as processed
        5. On FAILURE, do NOT record - allows retry

        This ensures that failed operations can be retried with the same
        request_id, while preventing duplicate processing of successful ones.
    """

    async def check_and_record(self, request_id: UUID) -> bool:
        """Check if request_id exists, and if not, record it atomically.

        This operation must be atomic (check-and-set) to prevent race
        conditions between concurrent requests with the same request_id.

        Args:
            request_id: The idempotency key to check and record.

        Returns:
            True if this is a DUPLICATE (request_id already existed).
            False if this is NEW (request_id was just recorded).

        Note:
            Returns True for duplicates (not False) because the common
            case is "not a duplicate" and we want that to be falsy for
            easy if-statement guards.

        Warning:
            For operations that may fail, prefer using exists() + record()
            separately to ensure failed operations remain retriable.
        """
        ...

    async def exists(self, request_id: UUID) -> bool:
        """Check if request_id exists without recording.

        Args:
            request_id: The idempotency key to check.

        Returns:
            True if request_id exists, False otherwise.
        """
        ...

    async def record(self, request_id: UUID) -> None:
        """Record a request_id as processed (without checking).

        This should be called AFTER successful operation completion to
        prevent replay of the same request_id.

        Args:
            request_id: The idempotency key to record.

        Note:
            If the request_id already exists, this is a no-op (idempotent).
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
    trigger,
    actor,
    reason,
    gate_snapshot,
    transition_at,
    request_id,
    correlation_id
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""

# Check if pattern exists and get current status
SQL_GET_PATTERN_STATUS = """
SELECT id, status
FROM learned_patterns
WHERE id = $1
"""


# =============================================================================
# Handler Functions
# =============================================================================


async def apply_transition(
    repository: ProtocolPatternRepository,
    idempotency_store: ProtocolIdempotencyStore,
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
    gate_snapshot: dict[str, Any] | None = None,
    transition_at: datetime,
    topic_env_prefix: str = "dev",
    conn: ProtocolPatternRepository | None = None,
) -> ModelTransitionResult:
    """Apply a pattern status transition with atomicity and idempotency.

    This is the main entry point for the transition handler. It:
    1. Validates PROVISIONAL guard (rejects to_status == "provisional")
    2. Checks idempotency store for duplicate request_id (without recording)
    3. Atomically: UPDATE pattern status + INSERT audit record (within transaction)
    4. Records idempotency key AFTER successful database operations
    5. Emits Kafka event (if producer available) - failures don't fail the operation

    Idempotency Timing:
        The idempotency key is recorded AFTER successful database operations,
        not before. This ensures that failed operations can be retried with
        the same request_id.

    Transaction Control:
        If ``conn`` is provided, it is used for all database operations,
        allowing the caller to manage the transaction externally. Both the
        UPDATE and INSERT operations will use the same connection, ensuring
        atomicity within the caller's transaction boundary.

        If ``conn`` is None, operations use the ``repository`` directly.
        In this case, atomicity depends on the repository's implementation.

    Args:
        repository: Database repository implementing ProtocolPatternRepository.
        idempotency_store: Idempotency store for request_id deduplication.
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
        topic_env_prefix: Environment prefix for Kafka topic.
        conn: Optional external connection for caller-managed transactions.
            If provided, all database operations use this connection.
            If None, operations use the repository directly.

    Returns:
        ModelTransitionResult with transition outcome.

    Raises:
        ValueError: If to_status is "provisional" (PROVISIONAL guard).
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

    # Step 0: Validate trigger is not empty
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

    # Step 1: PROVISIONAL guard - reject transitions TO provisional
    if to_status == PROVISIONAL_STATUS:
        logger.warning(
            "PROVISIONAL guard: Rejecting transition to provisional status",
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
            reason="PROVISIONAL guard: Transitions to 'provisional' are not allowed",
            transitioned_at=None,
            error_message="Transitions to 'provisional' status are not allowed. "
            "Use 'candidate' for new patterns.",
        )

    # Step 2: Check idempotency - is this a duplicate request?
    # Use exists() to check WITHOUT recording. The key will be recorded
    # AFTER successful database operations to ensure failed ops are retriable.
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

    # Step 3: Verify pattern exists and check current status
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

    # Step 4: Atomic transaction - UPDATE status + INSERT audit
    # Both operations use the same db connection for atomicity
    transition_id = uuid4()

    try:
        # Update pattern status with guard clause
        update_status = await db.execute(
            SQL_UPDATE_PATTERN_STATUS,
            pattern_id,
            to_status,
            transition_at,
            from_status,  # Status guard - must match current status
        )
        rows_updated = _parse_update_count(update_status)

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
        # Convert gate_snapshot dict to JSON string if present
        gate_snapshot_json = json.dumps(gate_snapshot) if gate_snapshot else None

        await db.execute(
            SQL_INSERT_LIFECYCLE_TRANSITION,
            transition_id,
            pattern_id,
            from_status,
            to_status,
            trigger,
            actor,
            reason,
            gate_snapshot_json,
            transition_at,
            request_id,
            correlation_id,
        )

        # Step 4b: Record idempotency key AFTER successful database operations
        # This ensures failed operations can be retried with the same request_id
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
        logger.error(
            "Failed to apply pattern lifecycle transition",
            extra={
                "correlation_id": str(correlation_id),
                "request_id": str(request_id),
                "pattern_id": str(pattern_id),
                "error": str(exc),
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
            error_message=str(exc),
        )

    # Step 5: Emit Kafka event (if producer available)
    # Kafka failures do NOT fail the main operation - the database transition
    # already succeeded. Failed events are routed to DLQ for later processing.
    if producer is not None:
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
                topic_env_prefix=topic_env_prefix,
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
                topic_env_prefix=topic_env_prefix,
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
    *,
    topic_env_prefix: str = "dev",
) -> None:
    """Emit a pattern-lifecycle-transitioned event to Kafka.

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
        topic_env_prefix: Environment prefix for topic.
    """
    # Build topic name with environment prefix
    topic = f"{topic_env_prefix}.{TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1}"

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
    *,
    topic_env_prefix: str = "dev",
) -> None:
    """Send failed event to Dead Letter Queue with sanitized error message.

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
        topic_env_prefix: Environment prefix for topic.
    """
    # Build DLQ topic name: {original_topic}.dlq
    original_topic = f"{topic_env_prefix}.{TOPIC_SUFFIX_PATTERN_LIFECYCLE_TRANSITIONED_V1}"
    dlq_topic = f"{original_topic}.dlq"

    try:
        # Build DLQ payload with error metadata
        # Note: error_message should already be sanitized by caller
        dlq_payload = {
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
        sanitized_payload = {
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
    "ProtocolIdempotencyStore",
    "ProtocolKafkaPublisher",
    "ProtocolPatternRepository",
    "apply_transition",
]
