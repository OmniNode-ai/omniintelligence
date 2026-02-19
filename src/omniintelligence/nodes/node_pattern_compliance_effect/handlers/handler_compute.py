"""Handler for pattern compliance compute node orchestration.

This module bridges the node's typed input/output models and the pure
compliance evaluation functions. It manages timing, error handling,
and LLM client interaction.

The handler:
    - Accepts ModelComplianceRequest (Pydantic model)
    - Calls ProtocolLlmClient for LLM inference
    - Parses the response via handler_compliance functions
    - Returns ModelComplianceResult (Pydantic model)
    - Handles all error cases gracefully (returns structured output)
    - Routes failures to DLQ when kafka_producer is available (optional)

Kafka Publisher Optionality:
----------------------------
The ``kafka_producer`` dependency is OPTIONAL (contract marks it as ``required: false``).
When the Kafka publisher is unavailable (None), compliance evaluations still return
structured error output, but failed evaluations are NOT routed to the Dead Letter Queue.

DLQ Routing:
------------
When ``kafka_producer`` is provided and an evaluation fails (LLM error or parse error),
the failure payload is routed to ``{DLQ_TOPIC}`` for downstream analysis and retry.
DLQ publish failures are caught and logged -- they never propagate as exceptions.

Ticket: OMN-2256
"""

from __future__ import annotations

import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from omniintelligence.nodes.node_pattern_compliance_effect.handlers.exceptions import (
    ComplianceValidationError,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.handler_compliance import (
    COMPLIANCE_PROMPT_VERSION,
    build_compliance_prompt,
    parse_llm_response,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ProtocolLlmClient,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_request import (
    ModelComplianceRequest,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models.model_compliance_result import (
    ModelComplianceMetadata,
    ModelComplianceResult,
    ModelComplianceViolation,
)
from omniintelligence.protocols import ProtocolKafkaPublisher
from omniintelligence.utils.log_sanitizer import get_log_sanitizer

logger = logging.getLogger(__name__)

# Default model identifier for Coder-14B.
DEFAULT_MODEL: Final[str] = "Qwen/Qwen2.5-Coder-14B-Instruct"

# Status constants for metadata.
STATUS_COMPLETED: Final[str] = "completed"
STATUS_VALIDATION_ERROR: Final[str] = "validation_error"
STATUS_LLM_ERROR: Final[str] = "llm_error"
STATUS_PARSE_ERROR: Final[str] = "parse_error"
STATUS_UNKNOWN_ERROR: Final[str] = "unknown_error"

# DLQ topic for failed compliance evaluations.
DLQ_TOPIC: Final[str] = "onex.evt.omniintelligence.pattern-compliance-evaluation.v1.dlq"

# System prompt for the LLM.
_SYSTEM_PROMPT: Final[str] = (
    "You are a code compliance evaluator. You analyze source code against "
    "a set of patterns and report violations. You respond ONLY with valid JSON, "
    "no markdown fences, no commentary."
)


async def handle_evaluate_compliance(
    input_data: ModelComplianceRequest,
    *,
    llm_client: ProtocolLlmClient | None,
    model: str = DEFAULT_MODEL,
    correlation_id: UUID | None = None,
    kafka_producer: ProtocolKafkaPublisher | None = None,
) -> ModelComplianceResult:
    """Handle evaluate_compliance operation.

    Orchestrates the compliance evaluation workflow:
    1. Validates input
    2. Builds the compliance prompt
    3. Calls the LLM via ProtocolLlmClient
    4. Parses the response into violations
    5. Constructs the output model with metadata
    6. Routes failures to DLQ when kafka_producer is available

    Error Handling:
        Domain errors (LLM failures, parse failures) are returned as
        structured output with the appropriate status code. Only invariant
        violations (ComplianceValidationError) propagate as exceptions,
        which are caught at this level and returned as structured output.

    Kafka DLQ Routing:
        When ``kafka_producer`` is provided and an evaluation fails (LLM error,
        parse error, or unknown error), the failure is routed to the Dead Letter
        Queue topic for downstream analysis and retry. DLQ publish failures are
        caught and logged -- they never propagate as exceptions.

    Args:
        input_data: Typed input model with code and patterns.
        llm_client: LLM client for inference calls. When None, returns a
            structured llm_error result immediately without attempting inference.
        model: Model identifier for LLM (default: Coder-14B).
        correlation_id: Explicit correlation ID for tracing. If provided,
            overrides input_data.correlation_id. Falls back to
            input_data.correlation_id when None.
        kafka_producer: Optional Kafka producer for DLQ routing. When None,
            the handler operates normally without DLQ routing. When provided,
            failed evaluations are routed to the DLQ topic. Kafka failures
            are caught and logged, never raised.

    Returns:
        ModelComplianceResult with compliance status, violations, and metadata.
        Always returns a valid output, even on errors.
    """
    start_time = time.perf_counter()
    patterns_count = len(input_data.applicable_patterns)
    cid = correlation_id if correlation_id is not None else input_data.correlation_id

    logger.debug(
        "Starting compliance evaluation. source_path=%s, language=%s, "
        "patterns_count=%d, model=%s",
        input_data.source_path,
        input_data.language,
        patterns_count,
        model,
        extra={"correlation_id": str(cid)},
    )

    try:
        return await _execute_compliance(
            input_data,
            llm_client=llm_client,
            model=model,
            start_time=start_time,
            correlation_id=cid,
            kafka_producer=kafka_producer,
        )

    except ComplianceValidationError as e:
        processing_time = _safe_elapsed_ms(start_time)
        logger.warning(
            "Compliance validation error: %s",
            e,
            extra={"correlation_id": str(cid)},
        )
        return _create_error_output(
            correlation_id=cid,
            status=STATUS_VALIDATION_ERROR,
            message=str(e),
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    except Exception as e:
        processing_time = _safe_elapsed_ms(start_time)

        try:
            logger.exception(
                "Unhandled exception in pattern compliance compute. "
                "source_path=%s, language=%s, processing_time_ms=%.2f",
                getattr(input_data, "source_path", "<unknown>"),
                getattr(input_data, "language", "<unknown>"),
                processing_time,
                extra={"correlation_id": str(cid)},
            )
        except Exception:
            with contextlib.suppress(Exception):
                logger.error(
                    "Pattern compliance compute failed: %s",
                    e,
                    extra={"correlation_id": str(cid)},
                )

        error_result = _create_error_output(
            correlation_id=cid,
            status=STATUS_UNKNOWN_ERROR,
            message=f"Unhandled error: {e}",
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

        if kafka_producer is not None:
            await _route_to_dlq(
                producer=kafka_producer,
                correlation_id=cid,
                source_path=getattr(input_data, "source_path", "<unknown>"),
                language=getattr(input_data, "language", "<unknown>"),
                error_status=STATUS_UNKNOWN_ERROR,
                error_message=f"Unhandled error: {e}",
            )

        return error_result


async def _execute_compliance(
    input_data: ModelComplianceRequest,
    *,
    llm_client: ProtocolLlmClient | None,
    model: str,
    start_time: float,
    correlation_id: UUID,
    kafka_producer: ProtocolKafkaPublisher | None = None,
) -> ModelComplianceResult:
    """Execute the compliance evaluation logic.

    Domain errors (LLM failures, parse failures) are returned as structured
    output rather than raised, following the ONEX handler convention. When
    ``kafka_producer`` is provided, failures are also routed to the DLQ.

    Args:
        input_data: Typed input model with code and patterns.
        llm_client: LLM client for inference calls. When None, returns a
            structured llm_error result immediately without attempting inference.
        model: Model identifier for LLM.
        start_time: Performance counter start time for timing.
        correlation_id: Resolved correlation ID for tracing. Already resolved
            by the caller (explicit kwarg or input_data fallback).
        kafka_producer: Optional Kafka producer for DLQ routing on failures.

    Returns:
        ModelComplianceResult with evaluation results or structured error.

    Raises:
        ComplianceValidationError: If input validation fails (invariant).
    """
    cid = correlation_id
    patterns_count = len(input_data.applicable_patterns)

    # 0. Guard: no LLM client configured -- return structured error immediately.
    # This is the PRIMARY protection against None llm_client on the normal call
    # path. handle_evaluate_compliance() does NOT short-circuit before calling
    # this function; it always delegates to _execute_compliance() unconditionally.
    # The guard here is live code for every call where llm_client=None.
    if llm_client is None:
        processing_time = _safe_elapsed_ms(start_time)
        error_msg = "LLM client is not configured (llm_client=None)"
        logger.warning(
            "%s. source_path=%s",
            error_msg,
            input_data.source_path,
            extra={"correlation_id": str(cid)},
        )

        if kafka_producer is not None:
            await _route_to_dlq(
                producer=kafka_producer,
                correlation_id=cid,
                source_path=input_data.source_path,
                language=input_data.language,
                error_status=STATUS_LLM_ERROR,
                error_message=error_msg,
            )

        return _create_error_output(
            correlation_id=cid,
            status=STATUS_LLM_ERROR,
            message=error_msg,
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    # 1. Build prompt
    prompt = build_compliance_prompt(
        content=input_data.content,
        language=input_data.language,
        patterns=list(input_data.applicable_patterns),
    )

    # 2. Call LLM
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    logger.debug(
        "Calling LLM for compliance evaluation. model=%s, patterns_count=%d",
        model,
        patterns_count,
        extra={"correlation_id": str(cid)},
    )

    try:
        raw_response = await llm_client.chat_completion(
            messages=messages,
            model=model,
            temperature=0.0,
            max_tokens=2048,
        )
    except Exception as e:
        processing_time = _safe_elapsed_ms(start_time)
        error_msg = f"LLM inference failed: {e}"
        logger.warning(
            "LLM inference failed: %s",
            e,
            extra={"correlation_id": str(cid)},
        )

        if kafka_producer is not None:
            await _route_to_dlq(
                producer=kafka_producer,
                correlation_id=cid,
                source_path=input_data.source_path,
                language=input_data.language,
                error_status=STATUS_LLM_ERROR,
                error_message=error_msg,
            )

        return _create_error_output(
            correlation_id=cid,
            status=STATUS_LLM_ERROR,
            message=error_msg,
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    # 3. Parse response (returns structured error on failure)
    parsed = parse_llm_response(
        raw_text=raw_response,
        patterns=list(input_data.applicable_patterns),
    )

    processing_time = (time.perf_counter() - start_time) * 1000

    # Check if parsing returned an error result (no violations, confidence=0.0).
    # A parse error is indicated by confidence=0.0 and empty violations when
    # the raw_response differs from the original LLM response (it contains
    # the error message instead).
    if parsed["confidence"] == 0.0 and parsed["raw_response"] != raw_response:
        logger.warning(
            "LLM response parse failed. source_path=%s, processing_time_ms=%.2f",
            input_data.source_path,
            processing_time,
            extra={"correlation_id": str(cid)},
        )

        if kafka_producer is not None:
            await _route_to_dlq(
                producer=kafka_producer,
                correlation_id=cid,
                source_path=input_data.source_path,
                language=input_data.language,
                error_status=STATUS_PARSE_ERROR,
                error_message=parsed["raw_response"],
            )

        return _create_error_output(
            correlation_id=cid,
            status=STATUS_PARSE_ERROR,
            message=parsed["raw_response"],
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    # 4. Build violations list
    violations = [
        ModelComplianceViolation(
            pattern_id=v["pattern_id"],
            pattern_signature=v["pattern_signature"],
            description=v["description"],
            severity=v["severity"],
            line_reference=v["line_reference"],
        )
        for v in parsed["violations"]
    ]

    logger.debug(
        "Compliance evaluation completed. compliant=%s, violations=%d, "
        "confidence=%.2f, processing_time_ms=%.2f",
        parsed["compliant"],
        len(violations),
        parsed["confidence"],
        processing_time,
        extra={"correlation_id": str(cid)},
    )

    return ModelComplianceResult(
        success=True,
        violations=violations,
        compliant=parsed["compliant"],
        confidence=parsed["confidence"],
        metadata=ModelComplianceMetadata(
            correlation_id=cid,
            status=STATUS_COMPLETED,
            compliance_prompt_version=COMPLIANCE_PROMPT_VERSION,
            model_used=model,
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        ),
    )


def _create_error_output(
    *,
    correlation_id: UUID,
    status: str,
    message: str,
    processing_time_ms: float,
    patterns_checked: int,
) -> ModelComplianceResult:
    """Create error output with consistent structure.

    Args:
        correlation_id: Correlation ID for tracing.
        status: Error status code.
        message: Error message.
        processing_time_ms: Elapsed time in milliseconds.
        patterns_checked: Number of patterns that were to be checked.

    Returns:
        ModelComplianceResult indicating failure.
    """
    return ModelComplianceResult(
        success=False,
        violations=[],
        compliant=False,
        confidence=0.0,
        metadata=ModelComplianceMetadata(
            correlation_id=correlation_id,
            status=status,
            message=message,
            compliance_prompt_version=COMPLIANCE_PROMPT_VERSION,
            processing_time_ms=processing_time_ms,
            patterns_checked=patterns_checked,
        ),
    )


def _safe_elapsed_ms(start_time: float) -> float:
    """Safely calculate elapsed time in milliseconds.

    Never raises -- returns 0.0 if calculation fails.

    Args:
        start_time: Performance counter start time.

    Returns:
        Elapsed time in milliseconds, or 0.0 on any error.
    """
    try:
        return (time.perf_counter() - start_time) * 1000
    except Exception:
        return 0.0


async def _route_to_dlq(
    *,
    producer: ProtocolKafkaPublisher,
    correlation_id: UUID,
    source_path: str,
    language: str,
    error_status: str,
    error_message: str,
) -> None:
    """Route a failed compliance evaluation to the Dead Letter Queue.

    Follows the effect-node DLQ guideline: on evaluation failure, publish
    the error context to ``{DLQ_TOPIC}`` for downstream analysis and retry.
    Secrets are sanitized via ``LogSanitizer``. Any errors from the DLQ
    publish attempt are swallowed to preserve graceful degradation.

    This function NEVER raises -- all exceptions are caught and logged.

    Args:
        producer: Kafka producer for DLQ publish.
        correlation_id: Correlation ID for distributed tracing.
        source_path: Path of the source file that was being evaluated.
        language: Programming language of the source file.
        error_status: Error status code (e.g., "llm_error", "parse_error").
        error_message: Error description from the failed evaluation.
    """
    try:
        sanitizer = get_log_sanitizer()

        dlq_payload: dict[str, object] = {
            "original_topic": "pattern-compliance-evaluation",
            "correlation_id": str(correlation_id),
            "source_path": sanitizer.sanitize(source_path),
            "language": language,
            "error_status": error_status,
            "error_message": sanitizer.sanitize(error_message),
            "error_timestamp": datetime.now(UTC).isoformat(),
            "service": "omniintelligence",
            "node": "node_pattern_compliance_effect",
        }

        await producer.publish(
            topic=DLQ_TOPIC,
            key=str(correlation_id),
            value=dlq_payload,
        )

        logger.info(
            "Failed compliance evaluation routed to DLQ",
            extra={
                "correlation_id": str(correlation_id),
                "dlq_topic": DLQ_TOPIC,
                "error_status": error_status,
            },
        )

    except Exception as dlq_exc:
        # DLQ publish failed -- swallow to preserve graceful degradation,
        # but log at WARNING so operators can detect persistent Kafka issues.
        sanitizer = get_log_sanitizer()
        sanitized_dlq_error = sanitizer.sanitize(str(dlq_exc))

        logger.warning(
            "DLQ publish failed for compliance evaluation -- message lost",
            extra={
                "correlation_id": str(correlation_id),
                "dlq_topic": DLQ_TOPIC,
                "error": sanitized_dlq_error,
                "error_type": type(dlq_exc).__name__,
            },
        )


__all__ = ["DLQ_TOPIC", "handle_evaluate_compliance"]
