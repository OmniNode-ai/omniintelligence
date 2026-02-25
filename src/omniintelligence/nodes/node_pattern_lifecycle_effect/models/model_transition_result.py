# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Transition result model for pattern lifecycle operations.

Ticket: OMN-1805
"""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumPatternLifecycleStatus


class ModelTransitionResult(BaseModel):
    """Result of a pattern status transition attempt.

    Represents the outcome of applying a pattern lifecycle transition,
    including success/failure status, duplicate detection, and audit info.

    Attributes:
        success: Whether the transition was applied successfully.
        duplicate: Whether this was a duplicate request (idempotency hit).
        pattern_id: The pattern that was (or would be) transitioned.
        from_status: The expected source status.
        to_status: The target status.
        transition_id: Unique ID of the audit record created, if any.
        reason: Human-readable reason for the result.
        transitioned_at: When the transition was recorded, if applied.
        error_message: Detailed error message if success=False.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    success: bool = Field(
        ...,
        description="Whether the transition succeeded (True also for valid duplicates)",
    )
    duplicate: bool = Field(
        default=False,
        description="Whether this was a duplicate request (idempotency hit)",
    )
    pattern_id: UUID = Field(
        ...,
        description="The pattern that was (or would be) transitioned",
    )
    from_status: EnumPatternLifecycleStatus = Field(
        ...,
        description="The expected source status",
    )
    to_status: EnumPatternLifecycleStatus = Field(
        ...,
        description="The target status",
    )
    transition_id: UUID | None = Field(
        default=None,
        description="Unique ID of the audit record created, if any",
    )
    reason: str | None = Field(
        default=None,
        description="Human-readable reason for the result",
    )
    transitioned_at: AwareDatetime | None = Field(
        default=None,
        description="When the transition was recorded, if applied (timezone-aware)",
    )
    error_message: str | None = Field(
        default=None,
        description="Detailed error message if success=False",
    )


__all__ = ["ModelTransitionResult"]
