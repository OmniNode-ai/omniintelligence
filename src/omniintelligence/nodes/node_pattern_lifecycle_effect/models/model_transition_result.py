# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for pattern_lifecycle_effect.

This module defines the result models for the pattern lifecycle effect node,
representing the outcomes of pattern status transition operations.

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
            True if transition applied OR if this was a valid duplicate.
        duplicate: Whether this was a duplicate request (idempotency hit).
            If True, the transition was already applied previously.
        pattern_id: The pattern that was (or would be) transitioned.
        from_status: The expected source status.
        to_status: The target status.
        transition_id: Unique ID of the audit record created, if any.
            None if duplicate, failed, or dry_run.
        reason: Human-readable reason for the result.
        transitioned_at: When the transition was recorded, if applied.
            None if duplicate, failed, or not yet applied.
        error_message: Detailed error message if success=False.
            None if successful.
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


class ModelPatternLifecycleTransitionedEvent(BaseModel):
    """Event payload for pattern-lifecycle-transitioned Kafka event.

    This model is published to Kafka when a pattern lifecycle transition
    is applied, enabling downstream consumers to react to status changes.

    Published to topic: onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = Field(
        default="PatternLifecycleTransitioned",
        description="Event type identifier",
    )
    pattern_id: UUID = Field(
        ...,
        description="The transitioned pattern ID",
    )
    from_status: EnumPatternLifecycleStatus = Field(
        ...,
        description="Status before transition",
    )
    to_status: EnumPatternLifecycleStatus = Field(
        ...,
        description="Status after transition",
    )
    trigger: str = Field(
        ...,
        description="What triggered this transition",
    )
    actor: str = Field(
        ...,
        description="Who applied the transition",
    )
    reason: str | None = Field(
        default=None,
        description="Human-readable reason for the transition",
    )
    transition_id: UUID = Field(
        ...,
        description="Unique ID of the audit record",
    )
    transitioned_at: AwareDatetime = Field(
        ...,
        description="Timestamp of the transition (timezone-aware)",
    )
    request_id: UUID = Field(
        ...,
        description="Idempotency key from the original request",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for distributed tracing",
    )


__all__ = [
    "ModelPatternLifecycleTransitionedEvent",
    "ModelTransitionResult",
]
