"""Parsed event model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelParsedEvent(BaseModel):
    """Typed model for parsed trace events.

    Provides strong typing for trace events extracted during parsing.
    """

    event_id: str | None = Field(default=None, description="Unique event identifier")
    event_type: str | None = Field(default=None, description="Type of event")
    timestamp: str | None = Field(default=None, description="Event timestamp")
    span_id: str | None = Field(default=None, description="Associated span ID")
    trace_id: str | None = Field(default=None, description="Associated trace ID")
    operation_name: str | None = Field(default=None, description="Operation name")
    service_name: str | None = Field(default=None, description="Service name")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Event attributes"
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelParsedEvent"]
