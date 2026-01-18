"""Output model for Execution Trace Parser Compute."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class ParsedEventDict(TypedDict, total=False):
    """Typed structure for parsed trace events."""

    event_id: str
    event_type: str
    timestamp: str
    span_id: str
    trace_id: str
    operation_name: str
    service_name: str
    attributes: dict[str, Any]


class ErrorEventDict(TypedDict, total=False):
    """Typed structure for error events extracted from traces."""

    error_id: str
    error_type: str
    error_message: str
    timestamp: str
    span_id: str
    stack_trace: str | None
    attributes: dict[str, Any]


class TimingDataDict(TypedDict, total=False):
    """Typed structure for timing information."""

    total_duration_ms: float
    start_time: str
    end_time: str
    span_count: int
    critical_path_ms: float
    latency_breakdown: dict[str, float]


class TraceMetadataDict(TypedDict, total=False):
    """Typed structure for trace parsing metadata."""

    parser_version: str
    parse_time_ms: float
    source_format: str
    event_count: int
    error_count: int
    warnings: list[str]


class ModelTraceParsingOutput(BaseModel):
    """Output model for trace parsing operations.

    This model represents the result of parsing execution traces.
    """

    success: bool = Field(
        ...,
        description="Whether trace parsing succeeded",
    )
    parsed_events: list[ParsedEventDict | dict[str, Any]] = Field(
        default_factory=list,
        description="List of parsed trace events",
    )
    error_events: list[ErrorEventDict | dict[str, Any]] = Field(
        default_factory=list,
        description="List of error events extracted from trace",
    )
    timing_data: TimingDataDict | dict[str, Any] = Field(
        default_factory=dict,
        description="Timing information extracted from trace",
    )
    metadata: TraceMetadataDict | dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the parsing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ErrorEventDict",
    "ModelTraceParsingOutput",
    "ParsedEventDict",
    "TimingDataDict",
    "TraceMetadataDict",
]
