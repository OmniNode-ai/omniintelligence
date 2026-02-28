# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler functions for LLM routing decision processing.

This module implements the Bifrost feedback loop consumer: when omniclaude's
Bifrost LLM gateway makes a routing decision, it emits an LLM routing decision
event. This handler:

1. Consumes ``onex.evt.omniclaude.llm-routing-decision.v1`` events.
2. Upserts an idempotent record to ``llm_routing_decisions`` using
   ``(session_id, correlation_id)`` as the composite idempotency key.
3. Publishes ``onex.evt.omniintelligence.llm-routing-decision-processed.v1``
   after successful upsert (optional; gracefully degrades without Kafka).

Idempotency:
-----------
The upsert uses ``ON CONFLICT (session_id, correlation_id) DO UPDATE`` to
handle at-least-once Kafka delivery. Re-processing the same event is safe:
the conflict clause updates ``processed_at`` to the current timestamp.

Kafka Graceful Degradation (Repository Invariant):
----------------------------------------------------
The Kafka publisher is optional. DB upsert always runs first. If the publisher
is None, the DB write still succeeds and the result is SUCCESS. This satisfies
the ONEX invariant: "Effect nodes must never block on Kafka."

Reference:
    - OMN-2939: Bifrost feedback loop — add LLM routing decision consumer
    - OMN-2740: Bifrost LLM Gateway (producer in omniclaude)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Final

from omniintelligence.constants import TOPIC_LLM_ROUTING_DECISION_PROCESSED
from omniintelligence.nodes.node_llm_routing_decision_effect.models import (
    EnumLlmRoutingDecisionStatus,
    ModelLlmRoutingDecisionEvent,
    ModelLlmRoutingDecisionProcessedEvent,
    ModelLlmRoutingDecisionResult,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository
from omniintelligence.utils.log_sanitizer import get_log_sanitizer
from omniintelligence.utils.pg_status import parse_pg_status_count

logger = logging.getLogger(__name__)

# Dead-letter queue topic for failed llm-routing-decision-processed publishes.
DLQ_TOPIC: Final[str] = f"{TOPIC_LLM_ROUTING_DECISION_PROCESSED}.dlq"


# =============================================================================
# SQL Queries
# =============================================================================

# Idempotent upsert for LLM routing decisions.
# Idempotency key: (session_id, correlation_id)
# ON CONFLICT: update processed_at to latest delivery timestamp.
# Parameters:
#   $1  = session_id (text)
#   $2  = correlation_id (text)
#   $3  = selected_agent (text)
#   $4  = llm_confidence (float8)
#   $5  = llm_latency_ms (int4)
#   $6  = fallback_used (bool)
#   $7  = model_used (text)
#   $8  = fuzzy_top_candidate (text, nullable)
#   $9  = llm_selected_candidate (text, nullable)
#   $10 = agreement (bool)
#   $11 = routing_prompt_version (text)
#   $12 = processed_at (timestamptz)
SQL_UPSERT_LLM_ROUTING_DECISION = """
INSERT INTO llm_routing_decisions (
    session_id,
    correlation_id,
    selected_agent,
    llm_confidence,
    llm_latency_ms,
    fallback_used,
    model_used,
    fuzzy_top_candidate,
    llm_selected_candidate,
    agreement,
    routing_prompt_version,
    processed_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (session_id, correlation_id)
DO UPDATE SET
    processed_at = EXCLUDED.processed_at
;"""

# =============================================================================
# Handler Functions
# =============================================================================


async def process_llm_routing_decision(
    event: ModelLlmRoutingDecisionEvent,
    *,
    repository: ProtocolPatternRepository,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
) -> ModelLlmRoutingDecisionResult:
    """Process an LLM routing decision event and upsert to llm_routing_decisions.

    This is the main entry point for the LLM routing decision handler. It:
    1. Upserts the event to llm_routing_decisions with idempotency key
       (session_id, correlation_id).
    2. Publishes a confirmation event to Kafka (optional, graceful degradation).
    3. Returns structured result with processing status.

    Per handler contract: ALL exceptions are caught and returned as structured
    ERROR results. This function never raises - unexpected errors produce a
    result with status=EnumLlmRoutingDecisionStatus.ERROR.

    Args:
        event: The LLM routing decision event from omniclaude's Bifrost gateway.
        repository: Database repository implementing ProtocolPatternRepository.
        kafka_publisher: Optional Kafka publisher for confirmation events.
            If None, DB write still succeeds (graceful degradation).

    Returns:
        ModelLlmRoutingDecisionResult with processing status and upsert details.
    """
    try:
        return await _process_llm_routing_decision_inner(
            event=event,
            repository=repository,
            kafka_publisher=kafka_publisher,
        )
    except Exception as exc:
        # Handler contract: return structured errors, never raise.
        sanitized_error = get_log_sanitizer().sanitize(str(exc))
        logger.exception(
            "Unhandled exception in LLM routing decision handler",
            extra={
                "correlation_id": event.correlation_id,
                "session_id": event.session_id,
                "selected_agent": event.selected_agent,
                "error": sanitized_error,
                "error_type": type(exc).__name__,
            },
        )
        return ModelLlmRoutingDecisionResult(
            status=EnumLlmRoutingDecisionStatus.ERROR,
            session_id=event.session_id,
            correlation_id=event.correlation_id,
            selected_agent=event.selected_agent,
            was_upserted=False,
            processed_at=datetime.now(UTC),
            error_message=sanitized_error,
        )


async def _process_llm_routing_decision_inner(
    event: ModelLlmRoutingDecisionEvent,
    *,
    repository: ProtocolPatternRepository,
    kafka_publisher: ProtocolKafkaPublisher | None,
) -> ModelLlmRoutingDecisionResult:
    """Inner implementation of process_llm_routing_decision.

    Separated from the public entry point so the outer function can apply
    a top-level try/except that catches any unhandled exceptions and converts
    them to structured ERROR results per the handler contract.
    """
    now = datetime.now(UTC)

    logger.info(
        "Processing LLM routing decision event",
        extra={
            "correlation_id": event.correlation_id,
            "session_id": event.session_id,
            "selected_agent": event.selected_agent,
            "llm_confidence": event.llm_confidence,
            "agreement": event.agreement,
        },
    )

    # Step 1: Upsert to llm_routing_decisions with idempotency key.
    # ON CONFLICT (session_id, correlation_id) DO UPDATE SET processed_at
    # ensures at-least-once Kafka delivery is safe.
    status = await repository.execute(
        SQL_UPSERT_LLM_ROUTING_DECISION,
        event.session_id,
        event.correlation_id,
        event.selected_agent,
        event.llm_confidence,
        event.llm_latency_ms,
        event.fallback_used,
        event.model_used,
        event.fuzzy_top_candidate,
        event.llm_selected_candidate,
        event.agreement,
        event.routing_prompt_version,
        now,
    )

    rows_affected = parse_pg_status_count(status)
    was_upserted = rows_affected > 0

    logger.debug(
        "Upserted LLM routing decision record",
        extra={
            "correlation_id": event.correlation_id,
            "session_id": event.session_id,
            "selected_agent": event.selected_agent,
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
            was_upserted=was_upserted,
            processed_at=now,
        )

    return ModelLlmRoutingDecisionResult(
        status=EnumLlmRoutingDecisionStatus.SUCCESS,
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        selected_agent=event.selected_agent,
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
    correlation_id: str,
) -> None:
    """Route a failed message to the dead-letter queue.

    Follows the effect-node DLQ guideline: on Kafka publish failure, attempt
    to publish the original envelope plus error metadata to ``{topic}.dlq``.
    Secrets are sanitized via ``LogSanitizer``. Any errors from the DLQ
    publish attempt are swallowed to preserve graceful degradation.

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
            "node": "node_llm_routing_decision_effect",
        }

        await producer.publish(
            topic=DLQ_TOPIC,
            key=session_id,
            value=dlq_payload,
        )
    except Exception:
        # DLQ publish failed -- swallow to preserve graceful degradation.
        logger.warning(
            "DLQ publish failed for topic %s -- message lost",
            DLQ_TOPIC,
            exc_info=True,
            extra={
                "correlation_id": correlation_id,
                "session_id": session_id,
            },
        )


async def _publish_processed_event(
    event: ModelLlmRoutingDecisionEvent,
    kafka_publisher: ProtocolKafkaPublisher,
    was_upserted: bool,
    processed_at: datetime,
) -> None:
    """Publish a llm-routing-decision-processed confirmation event.

    Failures are logged but NOT propagated - the DB upsert already succeeded.
    On publish failure, the original envelope is routed to the DLQ topic.

    Args:
        event: The original LLM routing decision event.
        kafka_publisher: Kafka publisher for the confirmation event.
        was_upserted: Whether a DB row was created/updated.
        processed_at: Timestamp of when the upsert was processed.
    """
    event_model = ModelLlmRoutingDecisionProcessedEvent(
        session_id=event.session_id,
        correlation_id=event.correlation_id,
        selected_agent=event.selected_agent,
        was_upserted=was_upserted,
        processed_at=processed_at,
    )
    payload = event_model.model_dump(mode="json")
    try:
        await kafka_publisher.publish(
            topic=TOPIC_LLM_ROUTING_DECISION_PROCESSED,
            key=event.session_id,
            value=payload,
        )
        logger.debug(
            "Published LLM routing decision processed event",
            extra={
                "correlation_id": event.correlation_id,
                "session_id": event.session_id,
                "topic": TOPIC_LLM_ROUTING_DECISION_PROCESSED,
            },
        )
    except Exception as exc:
        # DB upsert already succeeded; Kafka failure is non-fatal.
        sanitized_error = get_log_sanitizer().sanitize(str(exc))
        logger.warning(
            "Failed to publish LLM routing decision processed event — "
            "DB upsert succeeded, Kafka publish failed (non-fatal)",
            exc_info=True,
            extra={
                "correlation_id": event.correlation_id,
                "session_id": event.session_id,
                "topic": TOPIC_LLM_ROUTING_DECISION_PROCESSED,
            },
        )

        await _route_to_dlq(
            producer=kafka_publisher,
            original_topic=TOPIC_LLM_ROUTING_DECISION_PROCESSED,
            original_envelope=payload,
            error_message=sanitized_error,
            error_timestamp=datetime.now(UTC).isoformat(),
            session_id=event.session_id,
            correlation_id=event.correlation_id,
        )


__all__ = [
    "DLQ_TOPIC",
    "process_llm_routing_decision",
]
