"""Event extraction logic for Execution Trace Parser Compute.

This module contains pure functions for extracting error events and
state transitions from trace spans and logs.

Correlation ID: Threaded through all functions for end-to-end tracing.
"""

from __future__ import annotations

import logging

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.handler_trace_parsing import (
    generate_event_id,
    is_error_log_level,
    is_error_status,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    ErrorEventDict,
    SpanNodeDict,
)

logger = logging.getLogger(__name__)


def detect_span_errors(
    span: SpanNodeDict,
    *,
    correlation_id: str | None = None,
) -> list[ErrorEventDict]:
    """Detect errors from span status.

    Analyzes the span's status field to identify error conditions.

    Args:
        span: The span node to check for errors.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of error events detected from span status.
    """
    logger.debug(
        "Detecting span errors for span_id=%s",
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    errors: list[ErrorEventDict] = []

    if is_error_status(span["status"]):
        attributes: dict[str, str] = {}

        # Include operation context
        if span["operation_name"]:
            attributes["operation_name"] = span["operation_name"]
        if span["service_name"]:
            attributes["service_name"] = span["service_name"]

        # Include duration_ms for monitoring
        if span["duration_ms"] is not None:
            attributes["duration_ms"] = str(span["duration_ms"])

        # Include relevant tags
        for key, value in span["tags"].items():
            if "error" in key.lower() or "exception" in key.lower():
                attributes[f"tag.{key}"] = value

        # Extract error message from tags if available
        error_message = (
            span["tags"].get("error.message")
            or span["tags"].get("exception.message")
            or span["tags"].get("error")
            or f"Span status indicates error: {span['status']}"
        )

        # Extract stack trace from tags if available
        stack_trace = span["tags"].get("error.stack") or span["tags"].get(
            "exception.stacktrace"
        )

        errors.append(
            ErrorEventDict(
                error_id=generate_event_id(),
                error_type="SPAN_ERROR",
                error_message=error_message,
                timestamp=span["end_time"] or span["start_time"],
                span_id=span["span_id"],
                stack_trace=stack_trace,
                attributes=attributes,
            )
        )

        logger.debug(
            "Detected SPAN_ERROR for span_id=%s",
            span["span_id"],
            extra={"correlation_id": correlation_id},
        )

    return errors


def detect_log_errors(
    span: SpanNodeDict,
    correlated_logs: list[dict[str, str | None]],
    *,
    correlation_id: str | None = None,
) -> list[ErrorEventDict]:
    """Detect errors from log entries.

    Analyzes correlated logs for error-level entries and extracts
    error events with context.

    Args:
        span: The span node providing context.
        correlated_logs: Log entries correlated with the span.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of error events detected from logs.
    """
    logger.debug(
        "Detecting log errors for span_id=%s (log_count=%d)",
        span["span_id"],
        len(correlated_logs),
        extra={"correlation_id": correlation_id},
    )

    errors: list[ErrorEventDict] = []

    for log in correlated_logs:
        level = log.get("level")
        if not is_error_log_level(level):
            continue

        attributes: dict[str, str] = {}

        # Include span context
        if span["operation_name"]:
            attributes["operation_name"] = span["operation_name"]
        if span["service_name"]:
            attributes["service_name"] = span["service_name"]
        if level:
            attributes["log_level"] = level

        # Include duration_ms for monitoring
        if span["duration_ms"] is not None:
            attributes["duration_ms"] = str(span["duration_ms"])

        errors.append(
            ErrorEventDict(
                error_id=generate_event_id(),
                error_type="LOG_ERROR",
                error_message=log.get("message"),
                timestamp=log.get("timestamp"),
                span_id=span["span_id"],
                stack_trace=None,  # Logs typically don't include stack traces
                attributes=attributes,
            )
        )

    if errors:
        logger.debug(
            "Detected %d LOG_ERROR events for span_id=%s",
            len(errors),
            span["span_id"],
            extra={"correlation_id": correlation_id},
        )

    return errors


def detect_timeout_errors(
    span: SpanNodeDict,
    *,
    correlation_id: str | None = None,
) -> list[ErrorEventDict]:
    """Detect timeout errors from span characteristics.

    Identifies potential timeout conditions based on span status,
    duration, and tags.

    Args:
        span: The span node to check for timeouts.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of timeout error events.
    """
    logger.debug(
        "Detecting timeout errors for span_id=%s",
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    errors: list[ErrorEventDict] = []

    # Check for explicit timeout status
    status = span["status"]
    if status and "timeout" in status.lower():
        attributes: dict[str, str] = {}

        if span["operation_name"]:
            attributes["operation_name"] = span["operation_name"]
        if span["duration_ms"] is not None:
            attributes["duration_ms"] = str(span["duration_ms"])

        errors.append(
            ErrorEventDict(
                error_id=generate_event_id(),
                error_type="TIMEOUT",
                error_message=f"Operation timed out: {span['operation_name'] or 'unknown'}",
                timestamp=span["end_time"] or span["start_time"],
                span_id=span["span_id"],
                stack_trace=None,
                attributes=attributes,
            )
        )

        logger.debug(
            "Detected TIMEOUT error via status for span_id=%s",
            span["span_id"],
            extra={"correlation_id": correlation_id},
        )

    # Check for timeout tags
    timeout_tag = span["tags"].get("timeout") or span["tags"].get("error.timeout")
    if timeout_tag and timeout_tag.lower() in ("true", "1", "yes"):
        if not errors:  # Avoid duplicate if already caught via status
            attributes = {}
            if span["operation_name"]:
                attributes["operation_name"] = span["operation_name"]
            if span["duration_ms"] is not None:
                attributes["duration_ms"] = str(span["duration_ms"])

            errors.append(
                ErrorEventDict(
                    error_id=generate_event_id(),
                    error_type="TIMEOUT",
                    error_message=f"Timeout indicated by tag: {span['operation_name'] or 'unknown'}",
                    timestamp=span["end_time"] or span["start_time"],
                    span_id=span["span_id"],
                    stack_trace=None,
                    attributes=attributes,
                )
            )

            logger.debug(
                "Detected TIMEOUT error via tag for span_id=%s",
                span["span_id"],
                extra={"correlation_id": correlation_id},
            )

    return errors


def extract_all_errors(
    span: SpanNodeDict,
    correlated_logs: list[dict[str, str | None]],
    *,
    correlation_id: str | None = None,
) -> list[ErrorEventDict]:
    """Extract all error events from a span and its logs.

    Combines error detection from multiple sources:
    - Span status errors
    - Log-level errors
    - Timeout conditions

    Args:
        span: The span node to analyze.
        correlated_logs: Log entries correlated with the span.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of all detected error events, deduplicated.
    """
    logger.debug(
        "Extracting all errors for span_id=%s",
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    errors: list[ErrorEventDict] = []

    # Detect span status errors
    errors.extend(detect_span_errors(span, correlation_id=correlation_id))

    # Detect log-level errors
    errors.extend(detect_log_errors(span, correlated_logs, correlation_id=correlation_id))

    # Detect timeout errors (may overlap with span errors)
    timeout_errors = detect_timeout_errors(span, correlation_id=correlation_id)
    for timeout_error in timeout_errors:
        # Avoid adding timeout if we already have a span error for the same span
        existing_span_error = any(
            e["span_id"] == timeout_error["span_id"] and e["error_type"] == "SPAN_ERROR"
            for e in errors
        )
        if not existing_span_error:
            errors.append(timeout_error)

    logger.debug(
        "Extracted %d total errors for span_id=%s",
        len(errors),
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    return errors


__all__ = [
    "detect_log_errors",
    "detect_span_errors",
    "detect_timeout_errors",
    "extract_all_errors",
]
