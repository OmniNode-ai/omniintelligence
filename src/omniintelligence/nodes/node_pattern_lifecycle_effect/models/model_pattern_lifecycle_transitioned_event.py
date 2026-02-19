# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern lifecycle transitioned event model.

Ticket: OMN-1805
"""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumPatternLifecycleStatus


class ModelPatternLifecycleTransitionedEvent(BaseModel):
    """Event payload for pattern-lifecycle-transitioned Kafka event.

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


__all__ = ["ModelPatternLifecycleTransitionedEvent"]
