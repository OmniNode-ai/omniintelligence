# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input models for node_enforcement_feedback_effect.

This module defines the input event model consumed from the Kafka topic
``onex.evt.omniclaude.pattern-enforcement.v1``. The event is produced by
omniclaude's PostToolUse hook (OMN-2263) when it checks patterns against
tool output and detects violations.

Reference:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
    - OMN-2263: PostToolUse pattern enforcement hook (producer)
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelPatternViolation(BaseModel):
    """A single pattern violation detected during enforcement.

    Represents one pattern that was checked and found violated during
    a PostToolUse enforcement check in omniclaude.

    Attributes:
        pattern_id: The pattern that was violated.
        pattern_name: Human-readable name for logging and audit.
        was_advised: Whether the agent was advised about this violation.
        was_corrected: Whether the agent subsequently corrected the violation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: UUID = Field(
        ...,
        description="The ID of the pattern that was violated",
    )
    pattern_name: str = Field(
        default="",
        description="Human-readable name of the violated pattern",
    )
    was_advised: bool = Field(
        default=False,
        description="Whether the agent was advised about this violation",
    )
    was_corrected: bool = Field(
        default=False,
        description="Whether the agent subsequently corrected the violation",
    )


class ModelEnforcementEvent(BaseModel):
    """Enforcement event consumed from omniclaude's PostToolUse hook.

    Published to: ``onex.evt.omniclaude.pattern-enforcement.v1``

    This event carries the result of pattern enforcement checks performed
    during PostToolUse processing. It includes which patterns were checked,
    which violations were found, and whether corrections were made.

    Attributes:
        event_type: Event type identifier for routing.
        correlation_id: Distributed tracing correlation ID.
        session_id: The Claude Code session that produced this event.
        patterns_checked: Total number of patterns checked.
        violations_found: Total number of violations detected.
        violations: Detailed per-pattern violation information.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = Field(
        default="PatternEnforcement",
        description="Event type identifier for routing",
    )
    correlation_id: UUID = Field(
        ...,
        description="Distributed tracing correlation ID",
    )
    session_id: UUID = Field(
        ...,
        description="The Claude Code session that produced this event",
    )
    patterns_checked: int = Field(
        ...,
        ge=0,
        description="Total number of patterns checked during enforcement",
    )
    violations_found: int = Field(
        ...,
        ge=0,
        description="Total number of violations detected",
    )
    violations: list[ModelPatternViolation] = Field(
        default_factory=list,
        description="Detailed per-pattern violation information",
    )

    @model_validator(mode="after")
    def _check_violations_found_matches_len(self) -> ModelEnforcementEvent:
        """Ensure violations_found is consistent with the violations list.

        This prevents callers from independently setting violations_found
        to a value that does not match the actual number of violations
        provided.
        """
        expected = len(self.violations)
        if self.violations_found != expected:
            msg = (
                f"violations_found ({self.violations_found}) does not match "
                f"len(violations) ({expected})"
            )
            raise ValueError(msg)
        if self.violations_found > self.patterns_checked:
            msg = (
                f"violations_found ({self.violations_found}) cannot exceed "
                f"patterns_checked ({self.patterns_checked})"
            )
            raise ValueError(msg)
        return self


__all__ = [
    "ModelEnforcementEvent",
    "ModelPatternViolation",
]
