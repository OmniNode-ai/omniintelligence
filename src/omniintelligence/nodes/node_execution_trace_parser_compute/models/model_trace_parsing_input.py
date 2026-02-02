"""Input model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelTraceLog(BaseModel):
    """Typed model for trace log entries.

    Provides strong typing for log entries within trace spans.
    """

    timestamp: str | None = Field(default=None, description="Log entry timestamp")
    level: str | None = Field(default=None, description="Log level (INFO, WARN, ERROR)")
    message: str | None = Field(default=None, description="Log message content")
    fields: dict[str, str] = Field(
        default_factory=dict, description="Additional log fields"
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelTraceData(BaseModel):
    """Typed model for trace data.

    Provides strong typing for trace span data used in trace parsing.
    All common trace fields are explicitly typed for type safety.
    """

    span_id: str | None = Field(default=None, description="Unique span identifier")
    trace_id: str | None = Field(default=None, description="Trace identifier")
    parent_span_id: str | None = Field(
        default=None, description="Parent span identifier"
    )
    operation_name: str | None = Field(
        default=None, description="Name of the operation"
    )
    service_name: str | None = Field(default=None, description="Service name")
    start_time: str | None = Field(default=None, description="Span start timestamp")
    end_time: str | None = Field(default=None, description="Span end timestamp")
    duration_ms: float | None = Field(default=None, description="Duration in ms")
    status: str | None = Field(default=None, description="Span status")
    tags: dict[str, str] = Field(default_factory=dict, description="Span tags")
    logs: list[ModelTraceLog] = Field(
        default_factory=list, description="Log entries within the span"
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelTraceParsingInput(BaseModel):
    """Input model for trace parsing operations.

    This model represents the input for parsing execution traces.
    """

    trace_data: ModelTraceData = Field(
        ...,
        description="Raw trace data to parse (typed for common trace fields)",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    trace_format: str = Field(
        default="json",
        description="Format of the trace data (json, protobuf, etc.)",
    )
    extract_errors: bool = Field(
        default=True,
        description="Whether to extract error events",
    )
    extract_timing: bool = Field(
        default=True,
        description="Whether to extract timing data",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelTraceData",
    "ModelTraceLog",
    "ModelTraceParsingInput",
]
