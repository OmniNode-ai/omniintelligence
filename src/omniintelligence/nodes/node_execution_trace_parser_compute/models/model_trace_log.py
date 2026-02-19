"""Trace log model for Execution Trace Parser Compute."""

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


__all__ = ["ModelTraceLog"]
