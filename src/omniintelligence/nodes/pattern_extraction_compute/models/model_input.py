"""Input Model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from omniintelligence.nodes.pattern_extraction_compute.models.model_insight import (
    ModelCodebaseInsight,
)


class ModelExtractionConfig(BaseModel):
    """Configuration for pattern extraction."""

    extract_file_patterns: bool = Field(
        default=True,
        description="Extract file access and co-access patterns",
    )
    extract_error_patterns: bool = Field(
        default=True,
        description="Extract error-prone file patterns",
    )
    extract_architecture_patterns: bool = Field(
        default=True,
        description="Extract architecture and module patterns",
    )
    extract_tool_patterns: bool = Field(
        default=True,
        description="Extract tool usage patterns",
    )
    min_pattern_occurrences: int = Field(
        default=2,
        ge=1,
        description="Minimum occurrences to consider a pattern",
    )
    min_confidence: float = Field(
        default=0.6,  # Aligned with contract.yaml configuration.extraction.min_confidence
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for patterns",
    )
    max_insights_per_type: int = Field(
        default=50,
        ge=1,
        description="Maximum insights to return per type",
    )
    reference_time: datetime | None = Field(
        default=None,
        description="Reference time for deterministic timestamps (uses max session ended_at if None)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelSessionSnapshot(BaseModel):
    """Snapshot of a Claude Code session for pattern analysis.

    This is a simplified view of session data focused on what's
    needed for pattern extraction.
    """

    session_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the session",
    )
    working_directory: str = Field(
        ...,
        description="Working directory for the session",
    )
    started_at: datetime = Field(
        ...,
        description="When the session started",
    )
    ended_at: datetime | None = Field(
        default=None,
        description="When the session ended (None if still active)",
    )
    files_accessed: tuple[str, ...] = Field(
        default=(),
        description="List of files accessed during the session",
    )
    files_modified: tuple[str, ...] = Field(
        default=(),
        description="List of files modified during the session",
    )
    tools_used: tuple[str, ...] = Field(
        default=(),
        description="Tools invoked during the session (in order)",
    )
    errors_encountered: tuple[str, ...] = Field(
        default=(),
        description="Error messages encountered",
    )
    outcome: str = Field(
        default="unknown",
        description="Session outcome: success, failure, partial, unknown",
    )
    metadata: dict[str, str | int | float | bool] = Field(
        default_factory=dict,
        description="Additional session metadata",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelPatternExtractionInput(BaseModel):
    """Input for the Pattern Extraction Compute node."""

    session_snapshots: tuple[ModelSessionSnapshot, ...] = Field(
        ...,
        min_length=1,
        description="Session snapshots to analyze for patterns",
    )
    config: ModelExtractionConfig = Field(
        default_factory=ModelExtractionConfig,
        description="Extraction configuration",
    )
    existing_insights: tuple[ModelCodebaseInsight, ...] = Field(
        default=(),
        description="Existing insights to merge with (for incremental updates)",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelExtractionConfig",
    "ModelPatternExtractionInput",
    "ModelSessionSnapshot",
]
