# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Enforcement event model for PostToolUse hook events.

Reference: OMN-2270, OMN-2263
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_enforcement_feedback_effect.models.model_pattern_violation import (
    ModelPatternViolation,
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
        """Ensure violations_found is consistent with the violations list."""
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


__all__ = ["ModelEnforcementEvent"]
