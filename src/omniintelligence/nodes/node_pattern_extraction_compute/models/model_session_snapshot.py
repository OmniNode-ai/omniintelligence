"""Session snapshot model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from omnibase_core.types import PrimitiveValue
from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.model_tool_execution import (
    ModelToolExecution,
)


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
    metadata: dict[str, PrimitiveValue] = Field(
        default_factory=dict,
        description="Additional session metadata",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSessionSnapshot"]
