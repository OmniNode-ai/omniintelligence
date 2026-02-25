# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for Claude Code hook event processing.

Reference: OMN-1456
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_claude_hook_event_effect.models.enum_hook_processing_status import (
    EnumHookProcessingStatus,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models.model_intent_result import (
    ModelIntentResult,
)


class ModelClaudeHookResult(BaseModel):
    """Output model for Claude Code hook event processing.

    This model represents the result of processing any Claude Code hook
    event. For UserPromptSubmit events, it includes intent classification
    results. For other event types (currently no-op), it returns success
    with minimal metadata.

    Attributes:
        status: Overall processing status.
        event_type: The event type that was processed.
        session_id: Session ID from the input event.
        correlation_id: Correlation ID for tracing.
        intent_result: Intent classification result (UserPromptSubmit only).
        processing_time_ms: Time taken to process the event.
        processed_at: When processing completed.
        error_message: Error details if status is failed.
        metadata: Additional processing metadata.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    status: EnumHookProcessingStatus = Field(
        ...,
        description="Overall processing status",
    )
    event_type: str = Field(
        ...,
        description="The event type that was processed",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the input event",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (optional in core model)",
    )
    intent_result: ModelIntentResult | None = Field(
        default=None,
        description="Intent classification result (UserPromptSubmit only)",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time taken to process the event in milliseconds",
    )
    processed_at: datetime = Field(
        ...,
        description="When processing completed (UTC)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if status is failed",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Additional processing metadata",
    )


__all__ = ["ModelClaudeHookResult"]
