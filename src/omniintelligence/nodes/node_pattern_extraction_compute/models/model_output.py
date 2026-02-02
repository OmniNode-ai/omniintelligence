"""Output Model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)


class ModelExtractionMetrics(BaseModel):
    """Metrics from the pattern extraction process."""

    sessions_analyzed: int = Field(
        default=0,
        ge=0,
        description="Number of sessions analyzed",
    )
    total_patterns_found: int = Field(
        default=0,
        ge=0,
        description="Total raw patterns found before deduplication",
    )
    new_insights_count: int = Field(
        default=0,
        ge=0,
        description="Number of new insights created",
    )
    updated_insights_count: int = Field(
        default=0,
        ge=0,
        description="Number of existing insights updated",
    )
    file_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of file access patterns found",
    )
    error_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of error patterns found",
    )
    architecture_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of architecture patterns found",
    )
    tool_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of tool usage patterns found",
    )
    tool_failure_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of tool failure patterns extracted",
    )

    model_config = {"frozen": True, "extra": "forbid"}


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


class ModelPatternExtractionOutput(BaseModel):
    """Output from the Pattern Extraction Compute node."""

    success: bool = Field(
        ...,
        description="Whether extraction completed successfully",
    )
    new_insights: tuple[ModelCodebaseInsight, ...] = Field(
        default=(),
        description="Newly discovered insights",
    )
    updated_insights: tuple[ModelCodebaseInsight, ...] = Field(
        default=(),
        description="Existing insights that were updated with new evidence",
    )
    metrics: ModelExtractionMetrics = Field(
        default_factory=ModelExtractionMetrics,
        description="Extraction metrics",
    )
    metadata: ModelPatternExtractionMetadata = Field(
        default_factory=ModelPatternExtractionMetadata,
        description="Execution metadata",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelExtractionMetrics",
    "ModelPatternExtractionMetadata",
    "ModelPatternExtractionOutput",
]
