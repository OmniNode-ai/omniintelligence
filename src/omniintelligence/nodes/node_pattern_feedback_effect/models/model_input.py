"""Input models for node_pattern_feedback_effect.

This module defines the input models for the pattern feedback effect node,
which records session outcomes and updates pattern metrics.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class ModelSessionOutcomeRequest(BaseModel):
    """Request to record a session outcome and update pattern metrics.

    This model captures the result of a Claude Code session and links it
    to any patterns that were injected during that session. The feedback
    is used to update pattern effectiveness metrics.
    """

    session_id: UUID = Field(..., description="The Claude Code session ID")
    success: bool = Field(..., description="Whether the session succeeded")
    failure_reason: str | None = Field(
        default=None,
        description="Reason for failure if success=False",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Optional correlation ID for tracing",
    )
