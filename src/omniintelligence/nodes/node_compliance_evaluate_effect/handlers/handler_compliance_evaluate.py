# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Handler for compliance-evaluate command processing.

Bridges the Kafka command payload (ModelComplianceEvaluateCommand) to the
existing handle_evaluate_compliance() leaf node handler from
node_pattern_compliance_effect, then emits a compliance-evaluated event.

Design:
    - Deserializes the Kafka payload into ModelComplianceEvaluateCommand
    - Converts applicable_patterns to ModelApplicablePattern (OMN-2256 format)
    - Calls handle_evaluate_compliance() with the injected llm_client
    - Maps the result to ModelComplianceEvaluatedEvent
    - Publishes the event to Kafka if kafka_producer is available
    - Routes failures to DLQ

Kafka Publisher Optionality:
    The ``kafka_producer`` dependency is OPTIONAL (graceful degradation).
    When None, the evaluation runs normally but results are not published.

Idempotency:
    Key is (source_path, content_sha256, pattern_id) -- NOT correlation_id.
    Actual deduplication is performed by the dispatch handler layer using
    the idempotency store. This handler does not duplicate that check.

Ticket: OMN-2339
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from omniintelligence.nodes.node_compliance_evaluate_effect.models.model_command import (
    ModelComplianceEvaluateCommand,
)
from omniintelligence.nodes.node_compliance_evaluate_effect.models.model_event import (
    ModelComplianceEvaluatedEvent,
    ModelComplianceViolationPayload,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.handler_compute import (
    DEFAULT_MODEL,
    handle_evaluate_compliance,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ProtocolLlmClient,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_request import (
    ModelApplicablePattern,
    ModelComplianceRequest,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# Publish topic constant - matches contract.yaml publish_topics[0].
PUBLISH_TOPIC: Final[str] = "onex.evt.omniintelligence.compliance-evaluated.v1"
DLQ_TOPIC: Final[str] = f"{PUBLISH_TOPIC}.dlq"

# Status constants for the compliance-evaluated event.
# Mirrors the STATUS_* constants from node_pattern_compliance_effect.handlers.handler_compute
# for the statuses this node can produce.  Documented in contract.yaml publish_topics
# and handler docstrings.
#
# Status values:
#   STATUS_EVALUATION_FAILED - fallback when result.metadata is None and
#                              result.success is False (unexpected leaf behaviour).
STATUS_EVALUATION_FAILED: Final[str] = "evaluation_failed"


async def handle_compliance_evaluate_command(
    command: ModelComplianceEvaluateCommand,
    *,
    llm_client: ProtocolLlmClient | None,
    model: str = DEFAULT_MODEL,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic: str = PUBLISH_TOPIC,
) -> ModelComplianceEvaluatedEvent:
    """Handle a compliance-evaluate command from Kafka.

    Orchestrates the full workflow:
    1. Map command payload to ModelComplianceRequest (OMN-2256 format)
    2. Call handle_evaluate_compliance() with the injected llm_client
    3. Map result to ModelComplianceEvaluatedEvent
    4. Publish the event to Kafka (if kafka_producer available)
    5. Route failures to DLQ (if kafka_producer available)

    Error Handling:
        All errors from handle_evaluate_compliance() are already captured
        as structured output (success=False, appropriate status). This
        handler only routes failures to DLQ and logs them.

    Args:
        command: Deserialized Kafka command payload.
        llm_client: LLM client for Coder-14B inference. When None,
            handle_evaluate_compliance() returns a structured llm_error
            result; no exception is raised.
        model: Model identifier (default: Coder-14B).
        kafka_producer: Optional Kafka producer for event emission.
        publish_topic: Full publish topic (from contract, default: PUBLISH_TOPIC).

    Returns:
        ModelComplianceEvaluatedEvent with evaluation results.
        Always returns a valid event, even on errors.
    """
    start_time = time.perf_counter()
    cid = command.correlation_id

    # Sanitize source_path once up front so all log calls (including early-return
    # branches) use the safe form and never emit an unsanitized path.
    sanitizer = get_log_sanitizer()
    safe_source_path: str = sanitizer.sanitize(command.source_path)

    # Validate that content_sha256 matches the actual SHA-256 of content.
    # A mismatch means the caller sent a stale or incorrect hash, which would
    # cause incorrect idempotency deduplication at the dispatch layer.
    computed_sha256 = hashlib.sha256(command.content.encode()).hexdigest()
    if computed_sha256 != command.content_sha256:
        logger.warning(
            "content_sha256 mismatch: declared=%s, computed=%s, "
            "source_path=%s, correlation_id=%s",
            command.content_sha256,
            computed_sha256,
            safe_source_path,
            cid,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_event = ModelComplianceEvaluatedEvent(
            event_type="ComplianceEvaluated",
            correlation_id=cid,
            source_path=safe_source_path,
            content_sha256=command.content_sha256,
            language=command.language,
            success=False,
            compliant=False,
            violations=[],
            confidence=0.0,
            patterns_checked=len(command.applicable_patterns),
            model_used=None,
            status="validation_error",
            processing_time_ms=elapsed_ms,
            evaluated_at=datetime.now(UTC).isoformat(),
        )
        # Route to DLQ so operators can inspect and replay tampered/stale messages.
        # Mirrors the DLQ routing in _publish_event() for Kafka publish failures.
        if kafka_producer is not None:
            await _route_to_dlq(
                producer=kafka_producer,
                correlation_id=cid,
                source_path=safe_source_path,
                error_message=(
                    f"content_sha256 mismatch: declared={command.content_sha256}, "
                    f"computed={computed_sha256}"
                ),
                original_topic=publish_topic,
                original_envelope=command.model_dump(mode="json"),
                retry_count=0,
            )
        return error_event

    logger.info(
        "Processing compliance-evaluate command. "
        "source_path=%s, language=%s, patterns=%d, correlation_id=%s",
        safe_source_path,
        command.language,
        len(command.applicable_patterns),
        cid,
    )

    # 1. Map payload patterns to ModelApplicablePattern (OMN-2256 format).
    applicable_patterns = [
        ModelApplicablePattern(
            pattern_id=p.pattern_id,
            pattern_signature=p.pattern_signature,
            domain_id=p.domain_id,
            confidence=p.confidence,
        )
        for p in command.applicable_patterns
    ]

    # 2. Build the compliance request.
    request = ModelComplianceRequest(
        correlation_id=cid,
        source_path=safe_source_path,
        content=command.content,
        language=command.language,
        applicable_patterns=applicable_patterns,
    )

    # 3. Call the leaf handler (all error handling is inside).
    # Pass kafka_producer=None so the leaf handler does not attempt its own
    # DLQ routing to its own DLQ topic.  The outer handler (_publish_event /
    # _route_to_dlq) owns all DLQ routing for this node's topic boundary.
    # Forwarding kafka_producer to the leaf would cause dual DLQ publishes on
    # error paths, and the leaf's DLQ payload omits the content_sha256
    # idempotency fields required by node_compliance_evaluate_effect.
    result = await handle_evaluate_compliance(
        request,
        llm_client=llm_client,
        model=model,
        correlation_id=cid,
        kafka_producer=None,
    )

    evaluated_at = datetime.now(UTC).isoformat()
    processing_time_ms = (
        time.perf_counter() - start_time
    ) * 1000  # excludes Kafka publish latency

    # 4. Map result violations to event payload format.
    violations = [
        ModelComplianceViolationPayload(
            pattern_id=v.pattern_id,
            pattern_signature=v.pattern_signature,
            description=v.description,
            severity=v.severity,
            line_reference=v.line_reference,
        )
        for v in result.violations
    ]

    # 5. Build the output event.
    # Use safe_source_path (sanitized at function entry) so the in-memory
    # event object never carries an unsanitized path value.
    metadata = result.metadata
    event = ModelComplianceEvaluatedEvent(
        event_type="ComplianceEvaluated",
        correlation_id=cid,
        source_path=safe_source_path,
        content_sha256=command.content_sha256,
        language=command.language,
        success=result.success,
        compliant=result.compliant,
        violations=violations,
        confidence=result.confidence,
        patterns_checked=metadata.patterns_checked
        if metadata is not None
        else len(applicable_patterns),
        model_used=metadata.model_used if metadata is not None else model,
        status=metadata.status
        if metadata is not None and metadata.status is not None
        else ("completed" if result.success else STATUS_EVALUATION_FAILED),
        processing_time_ms=processing_time_ms,
        evaluated_at=evaluated_at,
    )

    # 6. Publish event to Kafka (if producer available).
    if kafka_producer is not None:
        await _publish_event(
            event=event,
            producer=kafka_producer,
            publish_topic=publish_topic,
        )

    logger.info(
        "Compliance evaluate command handled. "
        "source_path=%s, success=%s, compliant=%s, violations=%d, "
        "confidence=%.2f, processing_time_ms=%.2f, correlation_id=%s",
        safe_source_path,
        result.success,
        result.compliant,
        len(violations),
        result.confidence,
        (processing_time_ms or 0.0),
        cid,
    )

    return event


async def _publish_event(
    *,
    event: ModelComplianceEvaluatedEvent,
    producer: ProtocolKafkaPublisher,
    publish_topic: str,
) -> None:
    """Publish a compliance-evaluated event to Kafka.

    Routes to DLQ if publish fails. Never raises.

    Args:
        event: The compliance-evaluated event to publish.
        producer: Kafka producer.
        publish_topic: Full publish topic name.
    """
    sanitizer = get_log_sanitizer()
    cid = event.correlation_id

    payload: dict[str, object] = {
        "event_type": event.event_type,
        "correlation_id": str(cid),
        "source_path": sanitizer.sanitize(event.source_path),
        "content_sha256": event.content_sha256,
        "language": event.language,
        "success": event.success,
        "compliant": event.compliant,
        "violations": [
            {
                "pattern_id": v.pattern_id,
                "pattern_signature": v.pattern_signature,
                "description": v.description,
                "severity": v.severity,
                "line_reference": v.line_reference,
            }
            for v in event.violations
        ],
        "confidence": event.confidence,
        "patterns_checked": event.patterns_checked,
        "model_used": event.model_used,
        "status": event.status,
        "processing_time_ms": event.processing_time_ms,
        "evaluated_at": event.evaluated_at,
    }

    try:
        await producer.publish(
            topic=publish_topic,
            key=str(cid),
            value=payload,
        )
        logger.debug(
            "Compliance-evaluated event published. topic=%s, correlation_id=%s",
            publish_topic,
            cid,
        )
    except Exception as publish_exc:
        sanitized_error = sanitizer.sanitize(str(publish_exc))
        logger.warning(
            "Failed to publish compliance-evaluated event, routing to DLQ. "
            "correlation_id=%s, error=%s",
            cid,
            sanitized_error,
        )
        await _route_to_dlq(
            producer=producer,
            correlation_id=cid,
            # event.source_path is already sanitized (set from safe_source_path at event construction)
            source_path=event.source_path,
            error_message=sanitized_error,
            original_topic=publish_topic,
            original_envelope=payload,
            retry_count=0,
        )


async def _route_to_dlq(
    *,
    producer: ProtocolKafkaPublisher,
    correlation_id: UUID,
    source_path: str,
    error_message: str,
    original_topic: str,
    original_envelope: dict[str, object] | None = None,
    retry_count: int = 0,
) -> None:
    """Route a failed event publish to the Dead Letter Queue.

    Swallows all exceptions to preserve graceful degradation.

    Args:
        producer: Kafka producer.
        correlation_id: Correlation ID for tracing.
        source_path: Source file path (sanitized externally).
        error_message: Error from the failed publish (already sanitized).
        original_topic: The topic that failed.
        original_envelope: Original Kafka message payload for replay by DLQ consumers.
            Defaults to an empty dict when not provided.
        retry_count: Number of delivery attempts already made (for exponential
            backoff by DLQ consumers). Defaults to 0.
    """
    try:
        sanitizer = get_log_sanitizer()
        dlq_payload: dict[str, object] = {
            "original_topic": original_topic,
            "correlation_id": str(correlation_id),
            "source_path": sanitizer.sanitize(source_path),
            "error_message": error_message,
            "error_timestamp": datetime.now(UTC).isoformat(),
            "service": "omniintelligence",
            "node": "node_compliance_evaluate_effect",
            "original_envelope": original_envelope or {},
            "retry_count": retry_count,
        }
        await producer.publish(
            topic=DLQ_TOPIC,
            key=str(correlation_id),
            value=dlq_payload,
        )
        logger.debug(
            "Compliance-evaluated DLQ entry published. dlq_topic=%s, correlation_id=%s",
            DLQ_TOPIC,
            correlation_id,
        )
    except Exception as dlq_exc:
        # Swallow DLQ failures entirely -- do not propagate.
        sanitizer = get_log_sanitizer()
        logger.warning(
            "DLQ publish failed for compliance-evaluate -- message lost. "
            "dlq_topic=%s, correlation_id=%s, error=%s",
            DLQ_TOPIC,
            correlation_id,
            sanitizer.sanitize(str(dlq_exc)),
        )


__all__ = [
    "DLQ_TOPIC",
    "PUBLISH_TOPIC",
    "STATUS_EVALUATION_FAILED",
    "handle_compliance_evaluate_command",
]
