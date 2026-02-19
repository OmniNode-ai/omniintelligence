"""Pattern extraction metadata model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelPatternExtractionMetadata(BaseModel):
    """Metadata about the pattern extraction execution."""

    status: str = Field(
        default="pending",
        description="Execution status: pending, completed, validation_error, compute_error",
    )
    message: str | None = Field(
        default=None,
        description="Optional status message or error description",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total processing time in milliseconds",
    )
    reference_time: datetime | None = Field(
        default=None,
        description="Reference timestamp used for insight timestamps",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternExtractionMetadata"]
