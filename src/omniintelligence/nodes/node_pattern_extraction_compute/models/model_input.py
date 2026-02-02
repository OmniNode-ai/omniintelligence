"""Input Model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from omnibase_core.types import JsonType
from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_insight import (
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
    extract_tool_failure_patterns: bool = Field(
        default=True,
        description="Extract tool failure patterns from tool_executions",
    )
    min_pattern_occurrences: int = Field(
        default=2,
        ge=1,
        description="Minimum occurrences to consider a pattern",
    )
    min_distinct_sessions: int = Field(
        default=2,
        ge=1,
        description="Minimum distinct sessions a pattern must appear in",
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
    max_results_per_pattern_type: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum patterns to return per pattern subtype (e.g., recurring_failure, failure_sequence)",
    )
    reference_time: datetime | None = Field(
        default=None,
        description="Reference time for deterministic timestamps (uses max session ended_at if None)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


# TEMP_BOOTSTRAP: Should move to core intelligence input models
# Follow-up ticket: OMN-1608
class ModelToolExecution(BaseModel):
    """Single tool execution record for pattern analysis."""

    tool_name: str = Field(..., description="Tool name (Read, Write, Edit, Bash, etc.)")
    success: bool = Field(..., description="Whether the tool execution succeeded")
    error_message: str | None = Field(default=None, description="Error message if failed")
    error_type: str | None = Field(default=None, description="Exception type if failed")
    duration_ms: int | None = Field(default=None, ge=0, description="Execution duration")
    # IMPORTANT: Use JsonType | None, NOT dict[str, Any]
    tool_parameters: JsonType | None = Field(
        default=None, description="Tool input parameters (opaque JSON)"
    )
    timestamp: datetime = Field(..., description="When the tool was executed")

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
    tool_executions: tuple[ModelToolExecution, ...] = Field(
        default=(),
        description="Structured tool execution records including success/failure. "
        "ORDER IS AUTHORITATIVE for sequence detection.",
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
    options: ModelExtractionConfig = Field(
        default_factory=ModelExtractionConfig,
        description="Extraction configuration options",
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
    "ModelToolExecution",
]
