# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event models for intelligence operation lifecycle telemetry.

Published by the dispatch callback wrapper at the start and end of each
intelligence operation. Consumed by omnidash /intelligence page to show
active operations and their lifecycle.

Reference: OMN-6125 (Dashboard Data Pipeline Gaps)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelOperationStartedEvent(BaseModel):
    """Frozen event model for intelligence operation start telemetry.

    Emitted at the start of each intelligence operation dispatch
    (claude-hook, pattern-lifecycle, pattern-storage, etc.).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    operation_id: str = Field(
        min_length=1, description="Unique ID for this operation invocation"
    )
    operation_type: str = Field(
        min_length=1,
        description="Handler/route ID that identifies the operation type",
    )
    correlation_id: str = Field(
        min_length=1, description="Distributed tracing correlation ID"
    )
    session_id: str | None = Field(
        default=None, description="Session ID if extractable from payload"
    )
    started_at: datetime = Field(description="UTC timestamp of operation start")

    @field_validator("started_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        """Validate that started_at is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        return v


class ModelOperationCompletedEvent(BaseModel):
    """Frozen event model for intelligence operation completion telemetry.

    Emitted at the end of each intelligence operation dispatch with
    status (success/failure/timeout) and duration.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    operation_id: str = Field(
        min_length=1, description="Unique ID matching the started event"
    )
    operation_type: str = Field(
        min_length=1,
        description="Handler/route ID that identifies the operation type",
    )
    correlation_id: str = Field(
        min_length=1, description="Distributed tracing correlation ID"
    )
    status: str = Field(
        min_length=1,
        description="Outcome status: 'success', 'failure', or 'timeout'",
    )
    duration_ms: int = Field(ge=0, description="Wall-clock duration in milliseconds")
    completed_at: datetime = Field(description="UTC timestamp of operation completion")

    @field_validator("completed_at")
    @classmethod
    def validate_tz_aware(cls, v: datetime) -> datetime:
        """Validate that completed_at is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")
        return v


__all__ = ["ModelOperationCompletedEvent", "ModelOperationStartedEvent"]
