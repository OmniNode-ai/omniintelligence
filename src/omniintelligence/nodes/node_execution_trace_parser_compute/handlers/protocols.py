"""TypedDict structures for trace parsing handlers.

These structures define the contracts between pure functions and orchestrators.
Using TypedDict enables static type checking without Pydantic overhead.
"""

from __future__ import annotations

from typing import TypedDict


class ParsedEventDict(TypedDict):
    """Parsed event extracted from trace span."""

    event_id: str
    event_type: str  # SPAN_START, SPAN_END, ERROR_OCCURRED, STATE_TRANSITION
    timestamp: str | None
    span_id: str | None
    trace_id: str | None
    operation_name: str | None
    service_name: str | None
    attributes: dict[str, str]


class ErrorEventDict(TypedDict):
    """Error event extracted from trace."""

    error_id: str
    error_type: str  # SPAN_ERROR, LOG_ERROR, TIMEOUT
    error_message: str | None
    timestamp: str | None
    span_id: str | None
    stack_trace: str | None
    attributes: dict[str, str]


class TimingDataDict(TypedDict):
    """Timing information extracted from trace."""

    total_duration_ms: float | None
    start_time: str | None
    end_time: str | None
    span_count: int
    critical_path_ms: float | None
    latency_breakdown: dict[str, float]


class TraceMetadataDict(TypedDict):
    """Metadata about the parsing process."""

    parser_version: str
    parse_time_ms: float
    source_format: str
    event_count: int
    error_count: int
    warnings: list[str]


class TraceParsingResult(TypedDict):
    """Result structure for trace parsing handler."""

    success: bool
    parsed_events: list[ParsedEventDict]
    error_events: list[ErrorEventDict]
    timing_data: TimingDataDict
    metadata: TraceMetadataDict


class SpanNodeDict(TypedDict):
    """Internal representation of a span in the tree."""

    span_id: str
    trace_id: str | None
    parent_span_id: str | None
    operation_name: str | None
    service_name: str | None
    start_time: str | None
    end_time: str | None
    duration_ms: float | None
    status: str | None
    tags: dict[str, str]
    logs: list[dict[str, str | None]]
    children: list[str]  # Child span IDs


class BuildSpanResult(TypedDict):
    """Result structure for build_span_tree that supports structured errors."""

    success: bool
    span: SpanNodeDict | None
    error_message: str | None
    error_type: str | None  # "validation" or "compute"


def create_empty_timing_data() -> TimingDataDict:
    """Create empty timing data for error cases."""
    return TimingDataDict(
        total_duration_ms=None,
        start_time=None,
        end_time=None,
        span_count=0,
        critical_path_ms=None,
        latency_breakdown={},
    )


def create_error_metadata(
    parse_time_ms: float,
    source_format: str,
    warnings: list[str] | None = None,
) -> TraceMetadataDict:
    """Create metadata for error cases."""
    return TraceMetadataDict(
        parser_version="1.0.0",
        parse_time_ms=parse_time_ms,
        source_format=source_format,
        event_count=0,
        error_count=0,
        warnings=warnings or [],
    )


__all__ = [
    "BuildSpanResult",
    "ErrorEventDict",
    "ParsedEventDict",
    "SpanNodeDict",
    "TimingDataDict",
    "TraceMetadataDict",
    "TraceParsingResult",
    "create_empty_timing_data",
    "create_error_metadata",
]
