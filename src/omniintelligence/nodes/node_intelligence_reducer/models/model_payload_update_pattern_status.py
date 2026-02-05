"""Pattern Status Update Intent Payload.

This payload is emitted by the reducer as a ModelIntent and consumed by
NodePatternLifecycleEffect to apply the status projection to the database.

The request_id MUST be preserved from the original event for end-to-end
idempotency tracing.

Ticket: OMN-1805
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot


class ModelPayloadUpdatePatternStatus(BaseModel):
    """Intent payload for pattern status update projection.

    Effect node uses this to:
    1. UPDATE learned_patterns.status with status guard
    2. INSERT audit record into pattern_lifecycle_transitions

    Both operations MUST be in the same transaction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    intent_type: Literal["postgres.update_pattern_status"] = Field(
        default="postgres.update_pattern_status",
        description="Intent type for effect node routing",
    )
    request_id: UUID = Field(
        ...,
        description="Idempotency key - MUST match original event.request_id",
    )
    correlation_id: UUID = Field(..., description="For distributed tracing")
    pattern_id: UUID = Field(..., description="Pattern to update")
    from_status: EnumPatternLifecycleStatus = Field(
        ..., description="Expected current status (for optimistic locking)"
    )
    to_status: EnumPatternLifecycleStatus = Field(
        ..., description="New status to apply"
    )
    trigger: str = Field(
        ..., min_length=1, description="What triggered this transition"
    )
    actor: str = Field(default="reducer", description="Who applied the transition")
    reason: str | None = Field(default=None, description="Human-readable reason")
    gate_snapshot: ModelGateSnapshot | None = Field(
        default=None, description="Gate values at decision time"
    )
    transition_at: AwareDatetime = Field(
        ..., description="When to record as transition time (must be timezone-aware)"
    )


__all__ = ["ModelPayloadUpdatePatternStatus"]
