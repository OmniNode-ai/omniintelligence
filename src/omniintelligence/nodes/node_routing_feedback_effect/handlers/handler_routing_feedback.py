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

from omniintelligence.nodes.node_routing_feedback_effect.models import (
    EnumRoutingFeedbackStatus,
    ModelRoutingFeedbackEvent,
    ModelRoutingFeedbackResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository
from omniintelligence.utils.log_sanitizer import get_log_sanitizer
from omniintelligence.utils.pg_status import parse_pg_status_count

logger = logging.getLogger(__name__)


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
"""

# Topic for the processed confirmation event
TOPIC_ROUTING_FEEDBACK_PROCESSED = (
    "onex.evt.omniintelligence.routing-feedback-processed.v1"
)


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
    status = await repository.execute(
        SQL_UPSERT_ROUTING_FEEDBACK,
        event.session_id,
        event.correlation_id,
        event.stage,
        event.outcome,
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


async def _publish_processed_event(
    event: ModelRoutingFeedbackEvent,
    kafka_publisher: ProtocolKafkaPublisher,
    processed_at: datetime,
) -> None:
    """Publish a routing-feedback-processed confirmation event.

    Failures are logged but NOT propagated - the DB upsert already succeeded.
    This function is always called after a successful upsert, so callers should
    treat a Kafka failure as non-fatal.

    Args:
        event: The original routing feedback event.
        kafka_publisher: Kafka publisher for the confirmation event.
        processed_at: Timestamp of when the upsert was processed.
    """
    try:
        await kafka_publisher.publish(
            topic=TOPIC_ROUTING_FEEDBACK_PROCESSED,
            key=event.session_id,
            value={
                "event_name": "routing.feedback.processed",
                "session_id": event.session_id,
                "correlation_id": str(event.correlation_id),
                "stage": event.stage,
                "outcome": event.outcome,
                "processed_at": processed_at.isoformat(),
            },
        )
        logger.debug(
            "Published routing feedback processed event",
            extra={
                "correlation_id": str(event.correlation_id),
                "session_id": event.session_id,
                "topic": TOPIC_ROUTING_FEEDBACK_PROCESSED,
            },
        )
    except Exception:
        # DB upsert already succeeded; Kafka failure is non-fatal.
        # Log as warning so operators can detect persistent Kafka issues
        # without blocking the routing feedback pipeline.
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


__all__ = [
    "TOPIC_ROUTING_FEEDBACK_PROCESSED",
    "process_routing_feedback",
]
