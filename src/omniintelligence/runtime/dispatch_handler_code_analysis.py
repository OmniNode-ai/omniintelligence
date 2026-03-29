# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch handler for code analysis commands (OMN-6969).

Processes ``code-analysis.v1`` command events from omniclaude's
IntelligenceEventClient. Parses ModelCodeAnalysisRequestPayload,
runs heuristic quality scoring, and publishes
ModelCodeAnalysisCompletedPayload or ModelCodeAnalysisFailedPayload.

Architecture:
    - Heuristic-only scoring in this handler (LLM upgrade in OMN-6967)
    - Produces completed/failed events to Kafka for request-response wiring
    - Dispatch alias used by create_intelligence_dispatch_engine()
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)
from omniintelligence.models.events.model_code_analysis_completed import (
    ModelCodeAnalysisCompletedPayload,
)
from omniintelligence.models.events.model_code_analysis_failed import (
    ModelCodeAnalysisFailedPayload,
)
from omniintelligence.models.events.model_code_analysis_request import (
    ModelCodeAnalysisRequestPayload,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.runtime.contract_topics import (
    canonical_topic_to_dispatch_alias,
)
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# Canonical topic strings (ONEX naming: .cmd. / .evt.)
_CANONICAL_CMD = "onex.cmd.omniintelligence.code-analysis.v1"  # noqa: topic-naming-lint
_CANONICAL_COMPLETED = "onex.evt.omniintelligence.code-analysis-completed.v1"  # noqa: topic-naming-lint
_CANONICAL_FAILED = "onex.evt.omniintelligence.code-analysis-failed.v1"  # noqa: topic-naming-lint

# Dispatch alias — derived from canonical topic via bridge conversion.
DISPATCH_ALIAS_CODE_ANALYSIS = canonical_topic_to_dispatch_alias(_CANONICAL_CMD)

# Default publish topics for response events
TOPIC_CODE_ANALYSIS_COMPLETED = _CANONICAL_COMPLETED
TOPIC_CODE_ANALYSIS_FAILED = _CANONICAL_FAILED


# =============================================================================
# Heuristic Quality Scoring
# =============================================================================


def _heuristic_quality_score(
    content: str,
    language: str,
    operation_type: EnumAnalysisOperationType,
) -> ModelCodeAnalysisCompletedPayload:
    """Run heuristic quality scoring on source code content.

    This is a baseline implementation that checks for common code quality
    signals. Task 7 (OMN-6967) will upgrade this to LLM-powered analysis.

    Returns:
        ModelCodeAnalysisCompletedPayload with quality metrics.
    """
    start = time.monotonic()
    lines = content.splitlines()
    total_lines = len(lines)

    issues: list[str] = []
    recommendations: list[str] = []

    # Check for common issues
    if total_lines == 0:
        issues.append("Empty file")

    long_lines = sum(1 for line in lines if len(line) > 120)
    if long_lines > 0:
        issues.append(f"{long_lines} lines exceed 120 characters")

    # Check for common anti-patterns
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("# TODO") or stripped.startswith("# FIXME"):
            issues.append(f"Line {i}: unresolved {stripped.split()[1]}")
        if "import *" in stripped:
            issues.append(f"Line {i}: wildcard import")
        if "except:" in stripped and "except Exception" not in stripped:
            issues.append(f"Line {i}: bare except clause")
        if "print(" in stripped and language == "python":
            recommendations.append(f"Line {i}: consider using logging instead of print")

    # Calculate quality score
    issue_penalty = min(len(issues) * 0.1, 0.5)
    line_quality = 1.0 - (long_lines / max(total_lines, 1)) * 0.3
    quality_score = max(0.0, min(1.0, line_quality - issue_penalty))

    # Complexity heuristic: count nesting depth
    max_indent = 0
    for line in lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if language == "python":
                indent = indent // 4
            max_indent = max(max_indent, indent)

    complexity_score = max(0.0, min(1.0, 1.0 - (max_indent / 10.0)))

    processing_time_ms = (time.monotonic() - start) * 1000

    return ModelCodeAnalysisCompletedPayload(
        quality_score=round(quality_score, 3),
        issues_count=len(issues),
        recommendations_count=len(recommendations),
        processing_time_ms=round(processing_time_ms, 2),
        operation_type=operation_type,
        complexity_score=round(complexity_score, 3),
        maintainability_score=round((quality_score + complexity_score) / 2, 3),
        results_summary={
            "issues": issues[:20],
            "recommendations": recommendations[:10],
            "total_lines": total_lines,
            "max_nesting_depth": max_indent,
        },
    )


# =============================================================================
# Dispatch Handler Factory
# =============================================================================


def create_code_analysis_dispatch_handler(
    *,
    kafka_producer: ProtocolKafkaPublisher | None = None,
    publish_topic_completed: str | None = None,
    publish_topic_failed: str | None = None,
) -> Callable[
    [ModelEventEnvelope[object], ProtocolHandlerContext],
    Awaitable[str],
]:
    """Create a dispatch handler for code-analysis command events.

    Args:
        kafka_producer: Optional Kafka publisher for response events.
        publish_topic_completed: Topic for completed events.
        publish_topic_failed: Topic for failed events.

    Returns:
        Async handler function with signature (envelope, context) -> str.
    """
    _topic_completed = publish_topic_completed or TOPIC_CODE_ANALYSIS_COMPLETED
    _topic_failed = publish_topic_failed or TOPIC_CODE_ANALYSIS_FAILED

    async def _handle(
        envelope: ModelEventEnvelope[object],
        context: ProtocolHandlerContext,
    ) -> str:
        """Bridge handler: envelope -> code analysis -> completed/failed."""
        raw_ctx_id = getattr(context, "correlation_id", None)
        if isinstance(raw_ctx_id, UUID):
            ctx_correlation_id = raw_ctx_id
        elif raw_ctx_id is not None:
            try:
                ctx_correlation_id = UUID(str(raw_ctx_id))
            except (ValueError, AttributeError):
                ctx_correlation_id = uuid4()
        else:
            ctx_correlation_id = uuid4()

        payload = envelope.payload
        if not isinstance(payload, dict):
            msg = (
                f"Unexpected payload type {type(payload).__name__} "
                f"for code-analysis (correlation_id={ctx_correlation_id})"
            )
            logger.warning(msg)
            raise ValueError(msg)

        # Parse request
        try:
            request = ModelCodeAnalysisRequestPayload(**payload)
        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.warning(
                "Failed to parse code-analysis request: %s (correlation_id=%s)",
                sanitized,
                ctx_correlation_id,
            )
            # Publish failure event
            failed = ModelCodeAnalysisFailedPayload(
                correlation_id=ctx_correlation_id,
                error_code="INVALID_REQUEST",
                error_message=f"Payload parse error: {sanitized}",
                retry_allowed=False,
            )
            await _publish_event(
                kafka_producer, _topic_failed, failed, ctx_correlation_id
            )
            return "error:invalid_request"

        # Use request correlation_id if provided
        correlation_id = request.correlation_id or ctx_correlation_id
        safe_path = get_log_sanitizer().sanitize(request.source_path or "<no_path>")

        logger.info(
            "Processing code-analysis command "
            "(source_path=%s, operation=%s, language=%s, correlation_id=%s)",
            safe_path,
            request.operation_type.value,
            request.language,
            correlation_id,
        )

        try:
            result = _heuristic_quality_score(
                request.content,
                request.language,
                request.operation_type,
            )
            # Attach context from request
            completed = result.model_copy(
                update={
                    "correlation_id": correlation_id,
                    "source_path": request.source_path or "",
                }
            )

            await _publish_event(
                kafka_producer, _topic_completed, completed, correlation_id
            )

            logger.info(
                "Code analysis completed "
                "(source_path=%s, quality=%.3f, issues=%d, "
                "processing_ms=%.1f, correlation_id=%s)",
                safe_path,
                completed.quality_score,
                completed.issues_count,
                completed.processing_time_ms,
                correlation_id,
            )
            return "ok"

        except Exception as exc:
            sanitized = get_log_sanitizer().sanitize(str(exc))
            logger.exception(
                "Code analysis failed (source_path=%s, correlation_id=%s)",
                safe_path,
                correlation_id,
            )
            failed = ModelCodeAnalysisFailedPayload(
                correlation_id=correlation_id,
                error_code="ANALYSIS_ERROR",
                error_message=sanitized,
                operation_type=request.operation_type,
                source_path=request.source_path or "",
                retry_allowed=True,
            )
            await _publish_event(kafka_producer, _topic_failed, failed, correlation_id)
            return "error:analysis_failed"

    return _handle


async def _publish_event(
    producer: ProtocolKafkaPublisher | None,
    topic: str,
    payload: ModelCodeAnalysisCompletedPayload | ModelCodeAnalysisFailedPayload,
    correlation_id: UUID,
) -> None:
    """Publish a code analysis response event to Kafka."""
    if producer is None:
        logger.debug(
            "No Kafka producer — skipping publish to %s (correlation_id=%s)",
            topic,
            correlation_id,
        )
        return

    try:
        event_data = payload.model_dump(mode="json")
        await producer.publish(
            topic=topic,
            key=str(correlation_id),
            value=event_data,
        )
    except Exception:
        logger.exception(
            "Failed to publish to %s (correlation_id=%s)",
            topic,
            correlation_id,
        )
