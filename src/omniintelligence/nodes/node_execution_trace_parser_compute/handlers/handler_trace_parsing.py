"""Pure trace parsing logic for Execution Trace Parser Compute.

This module contains pure functions for parsing execution traces.
No I/O operations, no global state mutations.

Error Handling: Returns structured errors instead of raising exceptions.
Correlation ID: Threaded through all functions for end-to-end tracing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    BuildSpanResult,
    ParsedEventDict,
    SpanNodeDict,
    TimingDataDict,
)

if TYPE_CHECKING:
    from omniintelligence.nodes.node_execution_trace_parser_compute.models import (
        ModelTraceData,
        ModelTraceLog,
    )

logger = logging.getLogger(__name__)

# Parser version for tracking
PARSER_VERSION = "1.0.0"


def build_span_tree(
    trace_data: ModelTraceData,
    *,
    correlation_id: str | None = None,
) -> BuildSpanResult:
    """Build a span tree from trace data.

    Converts the flat ModelTraceData into a SpanNodeDict structure
    that can be traversed hierarchically.

    Args:
        trace_data: Raw trace data with span information.
        correlation_id: Correlation ID for tracing.

    Returns:
        BuildSpanResult with success=True and span, or success=False
        with error_message and error_type for structured error handling.
    """
    logger.debug(
        "Building span tree from trace data",
        extra={"correlation_id": correlation_id},
    )

    span_id = trace_data.span_id
    if not span_id:
        logger.debug(
            "Validation failed: span_id is required",
            extra={"correlation_id": correlation_id},
        )
        return BuildSpanResult(
            success=False,
            span=None,
            error_message="span_id is required for trace parsing",
            error_type="validation",
        )

    # Convert logs to dict format for internal processing
    logs_as_dicts: list[dict[str, str | None]] = []
    for log in trace_data.logs:
        logs_as_dicts.append(
            {
                "timestamp": log.timestamp,
                "level": log.level,
                "message": log.message,
            }
        )

    span = SpanNodeDict(
        span_id=span_id,
        trace_id=trace_data.trace_id,
        parent_span_id=trace_data.parent_span_id,
        operation_name=trace_data.operation_name,
        service_name=trace_data.service_name,
        start_time=trace_data.start_time,
        end_time=trace_data.end_time,
        duration_ms=trace_data.duration_ms,
        status=trace_data.status,
        tags=dict(trace_data.tags),
        logs=logs_as_dicts,
        children=[],  # Single trace doesn't have child spans in current model
    )

    logger.debug(
        "Successfully built span tree for span_id=%s",
        span_id,
        extra={"correlation_id": correlation_id},
    )

    return BuildSpanResult(
        success=True,
        span=span,
        error_message=None,
        error_type=None,
    )


def correlate_logs_with_span(
    span: SpanNodeDict,
    external_logs: list[ModelTraceLog],
    *,
    correlation_id: str | None = None,
) -> list[dict[str, str | None]]:
    """Correlate external logs with a span by trace_id and timestamp.

    Matches logs to the span based on trace_id correlation AND time window.
    Logs must be within the span's time window (start_time to end_time)
    to be associated with it.

    Args:
        span: The span node to correlate logs with.
        external_logs: List of external log entries to match.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of correlated log entries (merged with span's own logs).
    """
    logger.debug(
        "Correlating logs with span_id=%s",
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    correlated: list[dict[str, str | None]] = list(span["logs"])

    span_trace_id = span["trace_id"]
    if not span_trace_id:
        logger.debug(
            "No trace_id on span, returning only embedded logs",
            extra={"correlation_id": correlation_id},
        )
        return correlated

    # Parse span time boundaries for time window checking
    span_start = parse_timestamp(span["start_time"])
    span_end = parse_timestamp(span["end_time"])

    logs_matched = 0
    logs_rejected_no_timestamp = 0
    logs_rejected_outside_window = 0

    for log in external_logs:
        # Skip logs without timestamp (can't correlate temporally)
        if not log.timestamp:
            logs_rejected_no_timestamp += 1
            continue

        # Check if log has matching trace context in fields
        log_trace_id = log.fields.get("trace_id")
        if log_trace_id != span_trace_id:
            continue

        # Parse log timestamp for time window check
        log_time = parse_timestamp(log.timestamp)

        # Check if log is within span's time window
        if not _is_within_time_window(log_time, span_start, span_end):
            logs_rejected_outside_window += 1
            logger.debug(
                "Log rejected: outside span time window (log_time=%s, span=%s to %s)",
                log.timestamp,
                span["start_time"],
                span["end_time"],
                extra={"correlation_id": correlation_id},
            )
            continue

        correlated.append(
            {
                "timestamp": log.timestamp,
                "level": log.level,
                "message": log.message,
            }
        )
        logs_matched += 1

    logger.debug(
        "Log correlation complete: matched=%d, rejected_no_timestamp=%d, "
        "rejected_outside_window=%d",
        logs_matched,
        logs_rejected_no_timestamp,
        logs_rejected_outside_window,
        extra={"correlation_id": correlation_id},
    )

    # Sort by timestamp if available
    def get_timestamp(log: dict[str, str | None]) -> str:
        return log.get("timestamp") or ""

    correlated.sort(key=get_timestamp)

    return correlated


def _is_within_time_window(
    log_time: datetime | None,
    span_start: datetime | None,
    span_end: datetime | None,
) -> bool:
    """Check if a log timestamp is within the span's time window.

    Args:
        log_time: Parsed log timestamp.
        span_start: Parsed span start time.
        span_end: Parsed span end time.

    Returns:
        True if log is within span time window or if boundaries are unknown.
    """
    # If we can't parse the log time, accept it (be permissive)
    if log_time is None:
        return True

    # If span boundaries are unknown, accept the log (be permissive)
    if span_start is None and span_end is None:
        return True

    # Check start boundary (if known)
    if span_start is not None and log_time < span_start:
        return False

    # Check end boundary (if known)
    if span_end is not None and log_time > span_end:
        return False

    return True


def compute_timing_metrics(
    span: SpanNodeDict,
    *,
    correlation_id: str | None = None,
) -> TimingDataDict:
    """Compute timing metrics from a span.

    Extracts timing information including total duration, start/end times,
    and latency breakdown by operation.

    Args:
        span: The span node to compute timing from.
        correlation_id: Correlation ID for tracing.

    Returns:
        TimingDataDict with computed timing metrics.
    """
    logger.debug(
        "Computing timing metrics for span_id=%s",
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    latency_breakdown: dict[str, float] = {}

    # Add operation to latency breakdown if we have duration
    operation_name = span["operation_name"]
    duration_ms = span["duration_ms"]

    if operation_name and duration_ms is not None:
        latency_breakdown[operation_name] = duration_ms

    return TimingDataDict(
        total_duration_ms=duration_ms,
        start_time=span["start_time"],
        end_time=span["end_time"],
        span_count=1,  # Single span for now
        critical_path_ms=duration_ms,  # Single span is the critical path
        latency_breakdown=latency_breakdown,
    )


def parse_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse a timestamp string to datetime.

    Supports ISO 8601 format with optional microseconds and timezone.

    Args:
        timestamp_str: Timestamp string to parse.

    Returns:
        Parsed datetime or None if parsing fails.
    """
    if not timestamp_str:
        return None

    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    return None


def generate_event_id() -> str:
    """Generate a unique event ID.

    Returns:
        UUID string for event identification.
    """
    return str(uuid.uuid4())


def extract_span_events(
    span: SpanNodeDict,
    *,
    correlation_id: str | None = None,
) -> list[ParsedEventDict]:
    """Extract events from span transitions.

    Creates SPAN_START and SPAN_END events from a span's lifecycle.

    Args:
        span: The span node to extract events from.
        correlation_id: Correlation ID for tracing.

    Returns:
        List of parsed events (typically start and end events).
    """
    logger.debug(
        "Extracting span events for span_id=%s",
        span["span_id"],
        extra={"correlation_id": correlation_id},
    )

    events: list[ParsedEventDict] = []

    base_attributes: dict[str, str] = {}
    if span["status"]:
        base_attributes["status"] = span["status"]

    # Add tags to attributes
    for key, value in span["tags"].items():
        base_attributes[f"tag.{key}"] = value

    # SPAN_START event
    if span["start_time"]:
        events.append(
            ParsedEventDict(
                event_id=generate_event_id(),
                event_type="SPAN_START",
                timestamp=span["start_time"],
                span_id=span["span_id"],
                trace_id=span["trace_id"],
                operation_name=span["operation_name"],
                service_name=span["service_name"],
                attributes=dict(base_attributes),
            )
        )

    # SPAN_END event
    if span["end_time"]:
        end_attributes = dict(base_attributes)
        if span["duration_ms"] is not None:
            end_attributes["duration_ms"] = str(span["duration_ms"])

        events.append(
            ParsedEventDict(
                event_id=generate_event_id(),
                event_type="SPAN_END",
                timestamp=span["end_time"],
                span_id=span["span_id"],
                trace_id=span["trace_id"],
                operation_name=span["operation_name"],
                service_name=span["service_name"],
                attributes=end_attributes,
            )
        )

    logger.debug(
        "Extracted %d span events",
        len(events),
        extra={"correlation_id": correlation_id},
    )

    return events


def is_error_status(status: str | None) -> bool:
    """Determine if a status indicates an error.

    Args:
        status: Status string to check.

    Returns:
        True if status indicates an error condition.
    """
    if not status:
        return False

    error_indicators = [
        "error",
        "failed",
        "failure",
        "exception",
        "timeout",
        "aborted",
        "cancelled",
    ]

    status_lower = status.lower()
    return any(indicator in status_lower for indicator in error_indicators)


def is_error_log_level(level: str | None) -> bool:
    """Determine if a log level indicates an error.

    Args:
        level: Log level string to check.

    Returns:
        True if level indicates an error.
    """
    if not level:
        return False

    error_levels = ["error", "fatal", "critical", "severe"]
    return level.lower() in error_levels


__all__ = [
    "PARSER_VERSION",
    "build_span_tree",
    "compute_timing_metrics",
    "correlate_logs_with_span",
    "extract_span_events",
    "generate_event_id",
    "is_error_log_level",
    "is_error_status",
    "parse_timestamp",
]
