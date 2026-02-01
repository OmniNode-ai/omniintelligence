"""Input models for node_pattern_feedback_effect.

This module defines the input models for the pattern feedback effect node,
which records session outcomes and updates pattern metrics.

The canonical input type is ClaudeSessionOutcome from omnibase_core, which
represents the shared schema for session outcome events across the platform.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from omnibase_core.integrations.claude_code import (
    ClaudeCodeSessionOutcome,
    ClaudeSessionOutcome,
)


class ModelSessionOutcomeRequest(BaseModel):
    """LEGACY: Adapter for direct API calls. Prefer ClaudeSessionOutcome for events.

    This model is preserved for backward compatibility with existing callers.
    New code should use ClaudeSessionOutcome directly.
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

    def to_claude_session_outcome(self) -> ClaudeSessionOutcome:
        """Convert legacy request to shared schema."""
        from omnibase_core.enums.hooks.claude_code import EnumClaudeCodeSessionOutcome

        return ClaudeSessionOutcome(
            session_id=self.session_id,
            outcome=(
                EnumClaudeCodeSessionOutcome.SUCCESS
                if self.success
                else EnumClaudeCodeSessionOutcome.FAILED
            ),
            error=None,  # Legacy format doesn't have structured error
            correlation_id=self.correlation_id,
        )


# Canonical input type for event-driven consumption
SessionOutcomeInput = ClaudeSessionOutcome


__all__ = [
    "ClaudeCodeSessionOutcome",  # Enum re-export
    "ClaudeSessionOutcome",  # Direct re-export
    "ModelSessionOutcomeRequest",  # Legacy adapter
    "SessionOutcomeInput",  # Canonical (alias to ClaudeSessionOutcome)
]
