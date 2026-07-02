# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input models for the Cursor Hook Event Effect node."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from omnibase_core.enums.hooks.claude_code.enum_claude_code_hook_event_type import (
    EnumClaudeCodeHookEventType,
)
from omnibase_core.models.hooks.claude_code.model_claude_code_hook_event_payload import (
    ModelClaudeCodeHookEventPayload,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

EnumCursorHookEventType = EnumClaudeCodeHookEventType
ModelCursorHookEventPayload = ModelClaudeCodeHookEventPayload


class ModelCursorHookEvent(BaseModel):
    """Raw input schema for Cursor IDE hook events."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    event_type: EnumCursorHookEventType = Field(
        description="The type of Cursor IDE hook event"
    )
    session_id: str = Field(
        description="Cursor session identifier (string per Cursor plugin API)"
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Optional correlation ID for distributed tracing",
    )
    timestamp_utc: datetime = Field(
        description="When the event occurred; must be timezone-aware"
    )
    payload: ModelCursorHookEventPayload = Field(
        description="Event-specific data as a payload model"
    )
    agent_source: str = Field(
        default="cursor",
        description="Originating dispatcher frontend; always 'cursor' for this model.",
    )

    @field_validator("timestamp_utc")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        """Validate that timestamp_utc is timezone-aware."""
        if value.tzinfo is None:
            raise ValueError("timestamp_utc must be timezone-aware")
        return value

    def __repr__(self) -> str:
        """Return concise representation for debugging."""
        session_display = (
            self.session_id[:8] + "..." if len(self.session_id) > 8 else self.session_id
        )
        corr = " corr=..." if self.correlation_id else ""
        return (
            f"<CursorHookEvent {self.event_type.value} session={session_display}{corr}>"
        )


__all__ = [
    "EnumClaudeCodeHookEventType",
    "EnumCursorHookEventType",
    "ModelCursorHookEvent",
    "ModelCursorHookEventPayload",
]
