"""Input model for Execution Trace Parser Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelTraceParsingInput(BaseModel):
    """Input model for trace parsing operations.

    This model represents the input for parsing execution traces.
    """

    trace_data: dict[str, Any] = Field(
        ...,
        description="Raw trace data to parse",
    )
    correlation_id: Optional[str] = Field(
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


__all__ = ["ModelTraceParsingInput"]
