"""Trace metadata model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelTraceMetadata(BaseModel):
    """Typed model for trace parsing metadata.

    Provides strong typing for metadata about the parsing process.
    """

    parser_version: str | None = Field(default=None, description="Parser version used")
    parse_time_ms: float | None = Field(
        default=None, description="Time taken to parse in ms"
    )
    source_format: str | None = Field(
        default=None, description="Source format of the trace"
    )
    event_count: int | None = Field(
        default=None, ge=0, description="Number of events parsed"
    )
    error_count: int | None = Field(
        default=None, ge=0, description="Number of errors extracted"
    )
    warnings: list[str] = Field(default_factory=list, description="Parsing warnings")

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelTraceMetadata"]
