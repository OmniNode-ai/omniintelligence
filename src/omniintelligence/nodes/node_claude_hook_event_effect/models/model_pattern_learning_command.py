"""Pattern learning command model for Stop events.

Related: OMN-2210
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelPatternLearningCommand(BaseModel):
    """Command payload emitted on Stop events to trigger pattern extraction.

    Published to ``onex.cmd.omniintelligence.pattern-learning.v1`` when a
    Claude Code session stops. Consumed by the intelligence orchestrator to
    initiate pattern learning from session data.

    Related:
        - OMN-2210: Wire intelligence nodes into registration + pattern extraction
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_type: str = Field(
        default="PatternLearningRequested",
        description="Event type discriminator, always 'PatternLearningRequested'",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the hook event",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for distributed tracing",
    )
    trigger: str = Field(
        default="session_stop",
        description="Trigger source, always 'session_stop'",
    )
    timestamp: str = Field(
        ...,
        description="ISO-8601 timestamp of when the command was emitted",
    )

    @field_validator("timestamp")
    @classmethod
    def _validate_iso8601_timestamp(cls, v: str) -> str:
        """Validate that timestamp is a valid ISO-8601 string."""
        datetime.fromisoformat(v)
        return v


__all__ = ["ModelPatternLearningCommand"]
