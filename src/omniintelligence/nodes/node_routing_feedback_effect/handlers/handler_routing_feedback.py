# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler functions for routing feedback processing.

This module implements the routing feedback consumer: when omniclaude's
session-end hook determines that a routing decision should be reinforced,
it emits a routing.feedback event. This handler:

1. Consumes ``onex.evt.omniclaude.routing-feedback.v1`` events.
2. Upserts an idempotent record to ``routing_feedback_scores`` using
   ``(session_id, correlation_id, stage)`` as the composite idempotency key.
3. Publishes ``onex.evt.omniintelligence.routing-feedback-processed.v1`` after
   successful upsert (optional; gracefully degrades without Kafka).

Idempotency:
-----------
The upsert uses ``ON CONFLICT (session_id, correlation_id, stage) DO UPDATE``
to handle at-least-once Kafka delivery. Re-processing the same event is safe:
the conflict clause updates ``processed_at`` to the current timestamp and
returns the existing row count.

The ``was_upserted`` flag in the result is ``True`` on the success path for
both the first delivery and idempotent re-deliveries, because ``ON CONFLICT DO
UPDATE`` always updates ``processed_at`` and counts as a row change. It is
``False`` only when ``status`` is ``ERROR`` and the upsert did not execute.
Use the ``status`` field to distinguish between SUCCESS and ERROR.

Note: this relies on PostgreSQL behaviour where ON CONFLICT DO UPDATE always
counts the affected row (returning ``"UPDATE 1"``), regardless of whether the
SET clause actually changes any column values. This is guaranteed by the
PostgreSQL specification and is not specific to any particular version.

Kafka Graceful Degradation (Repository Invariant):
----------------------------------------------------
The Kafka publisher is optional. DB upsert always runs first. If the publisher
is None, the DB write still succeeds and the result is SUCCESS. This satisfies
the ONEX invariant: "Effect nodes must never block on Kafka."

Reference:
    - OMN-2366: Add routing.feedback consumer in omniintelligence
    - OMN-2356: Session-end hook routing feedback producer (omniclaude)

Design Principles:
    - Pure handler functions with injected repository and optional publisher
    - Protocol-based dependency injection for testability
    - asyncpg-style positional parameters ($1, $2, etc.)
    - Structured error returns, never raises domain errors
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from omniintelligence.constants import TOPIC_ROUTING_FEEDBACK_PROCESSED
from omniintelligence.nodes.node_routing_feedback_effect.models import (
    EnumRoutingFeedbackStatus,
    ModelRoutingFeedbackEvent,
    ModelRoutingFeedbackProcessedEvent,
    ModelRoutingFeedbackResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository
from omniintelligence.utils.log_sanitizer import get_log_sanitizer
from omniintelligence.utils.pg_status import parse_pg_status_count

logger = logging.getLogger(__name__)

# Dead-letter queue topic for failed routing-feedback-processed publishes.
DLQ_TOPIC: Final[str] = f"{TOPIC_ROUTING_FEEDBACK_PROCESSED}.dlq"


# =============================================================================
# SQL Queries
# =============================================================================

# Idempotent upsert for routing feedback scores.
# Idempotency key: (session_id, correlation_id, stage)
# ON CONFLICT: update processed_at to latest delivery timestamp.
# Parameters:
#   $1 = session_id (text)
#   $2 = correlation_id (uuid)
#   $3 = stage (text)
#   $4 = outcome (text: 'success' | 'failed')
#   $5 = processed_at (timestamptz)
SQL_UPSERT_ROUTING_FEEDBACK = """
INSERT INTO routing_feedback_scores (
    session_id,
    correlation_id,
    stage,
    outcome,
    processed_at
)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (session_id, correlation_id, stage)
DO UPDATE SET
    processed_at = EXCLUDED.processed_at
;"""

# =============================================================================
# Handler Functions
# =============================================================================


async def process_routing_feedback(
    event: ModelRoutingFeedbackEvent,
    *,
    repository: ProtocolPatternRepository,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
) -> ModelRoutingFeedbackResult:
    """Process a routing feedback event and upsert to routing_feedback_scores.

    This is the main entry point for the routing feedback handler. It:
    1. Upserts the event to routing_feedback_scores with idempotency key
       (session_id, correlation_id, stage).
    2. Publishes a confirmation event to Kafka (optional, graceful degradation).
    3. Returns structured result with processing status.

    Per handler contract: ALL exceptions are caught and returned as structured
    ERROR results. This function never raises - unexpected errors produce a
    result with status=EnumRoutingFeedbackStatus.ERROR.

    Args:
        event: The routing feedback event from omniclaude's session-end hook.
        repository: Database repository implementing ProtocolPatternRepository.
        kafka_publisher: Optional Kafka publisher for confirmation events.
            If None, DB write still succeeds (graceful degradation).

    Returns:
        ModelRoutingFeedbackResult with processing status and upsert details.
    """
    try:
        return await _process_routing_feedback_inner(
            event=event,
            repository=repository,
            kafka_publisher=kafka_publisher,
        )
    except Exception as exc:
        # Handler contract: return structured errors, never raise.
        sanitized_error = get_log_sanitizer().sanitize(str(exc))
        logger.exception(
            "Unhandled exception in routing feedback handler",
            extra={
                "correlation_id": str(event.correlation_id),
                "session_id": event.session_id,
                "stage": event.stage,
                "error": sanitized_error,
                "error_type": type(exc).__name__,
            },
        )
        return ModelRoutingFeedbackResult(
            status=EnumRoutingFeedbackStatus.ERROR,
            session_id=event.session_id,
            correlation_id=event.correlation_id,
            stage=event.stage,
            outcome=event.outcome,
            was_upserted=False,
            processed_at=datetime.now(UTC),
            error_message=sanitized_error,
        )


async def _process_routing_feedback_inner(
    event: ModelRoutingFeedbackEvent,
    *,
    repository: ProtocolPatternRepository,
    kafka_publisher: ProtocolKafkaPublisher | None,
) -> ModelRoutingFeedbackResult:
    """Inner implementation of process_routing_feedback.

    Separated from the public entry point so the outer function can apply
    a top-level try/except that catches any unhandled exceptions and converts
    them to structured ERROR results per the handler contract.
    """
    now = datetime.now(UTC)

    logger.info(
        "Processing routing feedback event",
        extra={
            "correlation_id": str(event.correlation_id),
            "session_id": event.session_id,
            "stage": event.stage,
            "outcome": event.outcome,
        },
    )

    # Step 1: Upsert to routing_feedback_scores with idempotency key.
    # ON CONFLICT (session_id, correlation_id, stage) DO UPDATE SET processed_at
    # ensures at-least-once Kafka delivery is safe.
    #
    # Note: event.emitted_at is intentionally not persisted here. It is
    # producer-side metadata for the event envelope (when omniclaude emitted
    # the event) and has no corresponding column in routing_feedback_scores.
    # processed_at (generated at handler invocation time) is the storage
    # timestamp of record.
    status = await repository.execute(
        SQL_UPSERT_ROUTING_FEEDBACK,
        event.session_id,
        event.correlation_id,
        event.stage,
        event.outcome.value,
        now,
    )

    rows_affected = parse_pg_status_count(status)
    was_upserted = rows_affected > 0

    logger.debug(
        "Upserted routing feedback record",
        extra={
            "correlation_id": str(event.correlation_id),
            "session_id": event.session_id,
            "stage": event.stage,
            "rows_affected": rows_affected,
            "was_upserted": was_upserted,
        },
    )

    # Step 2: Publish confirmation event (optional, graceful degradation).
    # DB write already succeeded; Kafka failure does NOT roll back the upsert.
    if kafka_publisher is not None:
        await _publish_processed_event(
            event=event,
            kafka_publisher=kafka_publisher,
            processed_at=now,
        )

    return ModelRoutingFeedbackResult(
        status=EnumRoutingFeedbackStatus.SUCCESS,
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        stage=event.stage,
        outcome=event.outcome,
        was_upserted=was_upserted,
        processed_at=now,
        error_message=None,
    )


async def _route_to_dlq(
    *,
    producer: ProtocolKafkaPublisher,
    original_topic: str,
    original_envelope: dict[str, object],
    error_message: str,
    error_timestamp: str,
    session_id: str,
    correlation_id: UUID,
) -> None:
    """Route a failed message to the dead-letter queue.

    Follows the effect-node DLQ guideline: on Kafka publish failure, attempt
    to publish the original envelope plus error metadata to ``{topic}.dlq``.
    Secrets are sanitized via ``LogSanitizer``. Any errors from the DLQ
    publish attempt are swallowed to preserve graceful degradation.

    Known limitation: DLQ publish uses the same producer that failed.
    If the failure is producer-level (connection lost), the DLQ write will
    also fail and be swallowed. Topic-level errors will succeed.

    Args:
        producer: Kafka producer for DLQ publish.
        original_topic: Original topic that failed.
        original_envelope: Original message payload that failed to publish.
        error_message: Error description from the failed publish (pre-sanitized).
        error_timestamp: ISO-formatted timestamp of the failure.
        session_id: Session ID used as the Kafka message key.
        correlation_id: Correlation ID for tracing.
    """
    try:
        sanitizer = get_log_sanitizer()
        # NOTE: Sanitization covers top-level string values. The current
        # envelope (routing-feedback-processed payload) produces only
        # top-level string/primitive fields, so this is sufficient.
        # INVARIANT: DLQ payloads from this handler are flat dicts; nested
        # sanitization is not required. If the envelope gains nested objects,
        # add recursive sanitization here.
        sanitized_envelope = {
            k: sanitizer.sanitize(str(v)) if isinstance(v, str) else v
            for k, v in original_envelope.items()
        }

        dlq_payload: dict[str, object] = {
            "original_topic": original_topic,
            "original_envelope": sanitized_envelope,
            "error_message": sanitizer.sanitize(error_message),
            "error_timestamp": error_timestamp,
            "retry_count": 0,
            "service": "omniintelligence",
            "node": "node_routing_feedback_effect",
        }

        await producer.publish(
            topic=DLQ_TOPIC,
            key=session_id,
            value=dlq_payload,
        )
    except Exception:
        # DLQ publish failed -- swallow to preserve graceful degradation,
        # but log at WARNING so operators can detect persistent Kafka issues.
        logger.warning(
            "DLQ publish failed for topic %s -- message lost",
            DLQ_TOPIC,
            exc_info=True,
            extra={
                "correlation_id": str(correlation_id),
                "session_id": session_id,
            },
        )


async def _publish_processed_event(
    event: ModelRoutingFeedbackEvent,
    kafka_publisher: ProtocolKafkaPublisher,
    processed_at: datetime,
) -> None:
    """Publish a routing-feedback-processed confirmation event.

    Failures are logged but NOT propagated - the DB upsert already succeeded.
    On publish failure, the original envelope is routed to the DLQ topic
    (``TOPIC_ROUTING_FEEDBACK_PROCESSED + ".dlq"``) per effect-node guidelines.

    Args:
        event: The original routing feedback event.
        kafka_publisher: Kafka publisher for the confirmation event.
        processed_at: Timestamp of when the upsert was processed.
    """
    event_model = ModelRoutingFeedbackProcessedEvent(
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        stage=event.stage,
        outcome=event.outcome,
        emitted_at=event.emitted_at,
        processed_at=processed_at,
    )
    payload = event_model.model_dump(mode="json")
    try:
        await kafka_publisher.publish(
            topic=TOPIC_ROUTING_FEEDBACK_PROCESSED,
            key=event.session_id,
            value=payload,
        )
        logger.debug(
            "Published routing feedback processed event",
            extra={
                "correlation_id": str(event.correlation_id),
                "session_id": event.session_id,
                "topic": TOPIC_ROUTING_FEEDBACK_PROCESSED,
            },
        )
    except Exception as exc:
        # DB upsert already succeeded; Kafka failure is non-fatal.
        # Log as warning so operators can detect persistent Kafka issues
        # without blocking the routing feedback pipeline.
        sanitized_error = get_log_sanitizer().sanitize(str(exc))
        logger.warning(
            "Failed to publish routing feedback processed event — "
            "DB upsert succeeded, Kafka publish failed (non-fatal)",
            exc_info=True,
            extra={
                "correlation_id": str(event.correlation_id),
                "session_id": event.session_id,
                "topic": TOPIC_ROUTING_FEEDBACK_PROCESSED,
            },
        )

        # Route to DLQ per effect-node guidelines.
        # Sanitize error before passing to _route_to_dlq for defense-in-depth
        # (_route_to_dlq also sanitizes internally, but we sanitize at the call
        # site to avoid passing raw exception strings across function boundaries).
        await _route_to_dlq(
            producer=kafka_publisher,
            original_topic=TOPIC_ROUTING_FEEDBACK_PROCESSED,
            original_envelope=payload,
            error_message=sanitized_error,
            error_timestamp=datetime.now(UTC).isoformat(),
            session_id=event.session_id,
            correlation_id=event.correlation_id,
        )


__all__ = [
    "DLQ_TOPIC",
    "process_routing_feedback",
]
