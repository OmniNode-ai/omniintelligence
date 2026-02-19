"""Timing data model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelTimingData(BaseModel):
    """Typed model for timing information.

    Provides strong typing for timing metrics extracted from traces.
    """

    total_duration_ms: float | None = Field(
        default=None, description="Total duration in milliseconds"
    )
    start_time: str | None = Field(default=None, description="Start timestamp")
    end_time: str | None = Field(default=None, description="End timestamp")
    span_count: int | None = Field(default=None, ge=0, description="Number of spans")
    critical_path_ms: float | None = Field(
        default=None, description="Critical path duration in ms"
    )
    latency_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Latency breakdown by operation"
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelTimingData"]
