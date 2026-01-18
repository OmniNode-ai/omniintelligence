"""Input model for Execution Trace Parser Compute."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class TraceDataDict(TypedDict, total=False):
    """Typed structure for trace data.

    Provides stronger typing for common trace fields while allowing
    additional fields via dict[str, Any] union.
    """

    span_id: str
    trace_id: str
    parent_span_id: str | None
    operation_name: str
    service_name: str
    start_time: str
    end_time: str
    duration_ms: float
    status: str
    tags: dict[str, str]
    logs: list[dict[str, Any]]


class ModelTraceParsingInput(BaseModel):
    """Input model for trace parsing operations.

    This model represents the input for parsing execution traces.
    """

    trace_data: TraceDataDict | dict[str, Any] = Field(
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
    "ModelTraceParsingInput",
    "TraceDataDict",
]
