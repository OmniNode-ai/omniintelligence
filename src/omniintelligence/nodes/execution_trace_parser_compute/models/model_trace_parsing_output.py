"""Output model for Execution Trace Parser Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelTraceParsingOutput(BaseModel):
    """Output model for trace parsing operations.

    This model represents the result of parsing execution traces.
    """

    success: bool = Field(
        ...,
        description="Whether trace parsing succeeded",
    )
    parsed_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of parsed trace events",
    )
    error_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of error events extracted from trace",
    )
    timing_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Timing information extracted from trace",
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional metadata about the parsing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelTraceParsingOutput"]
