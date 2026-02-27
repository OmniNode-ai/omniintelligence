# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler functions for routing feedback processing.

This module implements the routing-outcome-raw consumer (OMN-2935): when
omniclaude's session-end hook emits a routing-outcome-raw event, this handler:

1. Consumes ``onex.evt.omniclaude.routing-outcome-raw.v1`` events.
2. Upserts an idempotent record to ``routing_feedback_scores`` using
   ``session_id`` as the idempotency key (no correlation_id in new payload).
3. Publishes ``onex.evt.omniintelligence.routing-feedback-processed.v1`` after
   successful upsert (optional; gracefully degrades without Kafka).

Migration note (OMN-2935):
    Replaced ModelRoutingFeedbackEvent (routing-feedback.v1) with
    ModelSessionRawOutcomePayload (routing-outcome-raw.v1). The new payload
    carries raw observable facts: injection_occurred, patterns_injected_count,
    tool_calls_count, duration_ms, agent_selected, routing_confidence.
    correlation_id and outcome are no longer present in the producer payload.

Idempotency:
-----------
The upsert uses ``ON CONFLICT (session_id) DO UPDATE`` to handle at-least-once
Kafka delivery. Re-processing the same session_id is safe.

The ``was_upserted`` flag in the result is ``True`` on the success path for
both the first delivery and idempotent re-deliveries.

Kafka Graceful Degradation (Repository Invariant):
----------------------------------------------------
The Kafka publisher is optional. DB upsert always runs first. If the publisher
is None, the DB write still succeeds and the result is SUCCESS. This satisfies
the ONEX invariant: "Effect nodes must never block on Kafka."

Reference:
    - OMN-2366: Add routing.feedback consumer in omniintelligence
    - OMN-2356: Session-end hook routing feedback producer (omniclaude)
    - OMN-2935: Fix routing feedback loop — subscribe to routing-outcome-raw.v1

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

from omniintelligence.constants import TOPIC_ROUTING_FEEDBACK_PROCESSED
from omniintelligence.nodes.node_routing_feedback_effect.models import (
    EnumRoutingFeedbackStatus,
    ModelRoutingFeedbackProcessedEvent,
    ModelRoutingFeedbackResult,
    ModelSessionRawOutcomePayload,
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
# Idempotency key: session_id
# ON CONFLICT: update all raw signal fields + processed_at on re-delivery.
# Parameters:
#   $1 = session_id (text)
#   $2 = injection_occurred (bool)
#   $3 = patterns_injected_count (int)
#   $4 = tool_calls_count (int)
#   $5 = duration_ms (int)
#   $6 = agent_selected (text)
#   $7 = routing_confidence (float)
#   $8 = processed_at (timestamptz)
SQL_UPSERT_ROUTING_FEEDBACK = """
INSERT INTO routing_feedback_scores (
    session_id,
    injection_occurred,
    patterns_injected_count,
    tool_calls_count,
    duration_ms,
    agent_selected,
    routing_confidence,
    processed_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (session_id)
DO UPDATE SET
    injection_occurred = EXCLUDED.injection_occurred,
    patterns_injected_count = EXCLUDED.patterns_injected_count,
    tool_calls_count = EXCLUDED.tool_calls_count,
    duration_ms = EXCLUDED.duration_ms,
    agent_selected = EXCLUDED.agent_selected,
    routing_confidence = EXCLUDED.routing_confidence,
    processed_at = EXCLUDED.processed_at
;"""

# =============================================================================
# Handler Functions
# =============================================================================


async def process_routing_feedback(
    event: ModelSessionRawOutcomePayload,
    *,
    repository: ProtocolPatternRepository,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
) -> ModelRoutingFeedbackResult:
    """Process a routing-outcome-raw event and upsert to routing_feedback_scores.

    This is the main entry point for the routing feedback handler. It:
    1. Upserts the event to routing_feedback_scores with idempotency key
       session_id.
    2. Publishes a confirmation event to Kafka (optional, graceful degradation).
    3. Returns structured result with processing status.

    Per handler contract: ALL exceptions are caught and returned as structured
    ERROR results. This function never raises - unexpected errors produce a
    result with status=EnumRoutingFeedbackStatus.ERROR.

    Args:
        event: The routing-outcome-raw event from omniclaude's session-end hook.
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
                "session_id": event.session_id,
                "agent_selected": event.agent_selected,
                "error": sanitized_error,
                "error_type": type(exc).__name__,
            },
        )
        return ModelRoutingFeedbackResult(
            status=EnumRoutingFeedbackStatus.ERROR,
            session_id=event.session_id,
            injection_occurred=event.injection_occurred,
            patterns_injected_count=event.patterns_injected_count,
            tool_calls_count=event.tool_calls_count,
            duration_ms=event.duration_ms,
            agent_selected=event.agent_selected,
            routing_confidence=event.routing_confidence,
            was_upserted=False,
            processed_at=datetime.now(UTC),
            error_message=sanitized_error,
        )


async def _process_routing_feedback_inner(
    event: ModelSessionRawOutcomePayload,
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
        "Processing routing-outcome-raw event",
        extra={
            "session_id": event.session_id,
            "injection_occurred": event.injection_occurred,
            "patterns_injected_count": event.patterns_injected_count,
            "agent_selected": event.agent_selected,
            "routing_confidence": event.routing_confidence,
        },
    )

    # Step 1: Upsert to routing_feedback_scores with idempotency key session_id.
    # ON CONFLICT (session_id) DO UPDATE ensures at-least-once Kafka delivery
    # is safe — re-delivering the same session updates the raw signal fields.
    status = await repository.execute(
        SQL_UPSERT_ROUTING_FEEDBACK,
        event.session_id,
        event.injection_occurred,
        event.patterns_injected_count,
        event.tool_calls_count,
        event.duration_ms,
        event.agent_selected,
        event.routing_confidence,
        now,
    )

    rows_affected = parse_pg_status_count(status)
    was_upserted = rows_affected > 0

    logger.debug(
        "Upserted routing feedback record",
        extra={
            "session_id": event.session_id,
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
        injection_occurred=event.injection_occurred,
        patterns_injected_count=event.patterns_injected_count,
        tool_calls_count=event.tool_calls_count,
        duration_ms=event.duration_ms,
        agent_selected=event.agent_selected,
        routing_confidence=event.routing_confidence,
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
    """
    try:
        sanitizer = get_log_sanitizer()
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
                "session_id": session_id,
            },
        )


async def _publish_processed_event(
    event: ModelSessionRawOutcomePayload,
    kafka_publisher: ProtocolKafkaPublisher,
    processed_at: datetime,
) -> None:
    """Publish a routing-feedback-processed confirmation event.

    Failures are logged but NOT propagated - the DB upsert already succeeded.
    On publish failure, the original envelope is routed to the DLQ topic
    (``TOPIC_ROUTING_FEEDBACK_PROCESSED + ".dlq"``) per effect-node guidelines.

    Args:
        event: The original routing-outcome-raw event.
        kafka_publisher: Kafka publisher for the confirmation event.
        processed_at: Timestamp of when the upsert was processed.
    """
    event_model = ModelRoutingFeedbackProcessedEvent(
        session_id=event.session_id,
        injection_occurred=event.injection_occurred,
        patterns_injected_count=event.patterns_injected_count,
        agent_selected=event.agent_selected,
        routing_confidence=event.routing_confidence,
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
                "session_id": event.session_id,
                "topic": TOPIC_ROUTING_FEEDBACK_PROCESSED,
            },
        )
    except Exception as exc:
        # DB upsert already succeeded; Kafka failure is non-fatal.
        sanitized_error = get_log_sanitizer().sanitize(str(exc))
        logger.warning(
            "Failed to publish routing feedback processed event — "
            "DB upsert succeeded, Kafka publish failed (non-fatal)",
            exc_info=True,
            extra={
                "session_id": event.session_id,
                "topic": TOPIC_ROUTING_FEEDBACK_PROCESSED,
            },
        )

        # Route to DLQ per effect-node guidelines.
        await _route_to_dlq(
            producer=kafka_publisher,
            original_topic=TOPIC_ROUTING_FEEDBACK_PROCESSED,
            original_envelope=payload,
            error_message=sanitized_error,
            error_timestamp=datetime.now(UTC).isoformat(),
            session_id=event.session_id,
        )


__all__ = [
    "DLQ_TOPIC",
    "process_routing_feedback",
]
