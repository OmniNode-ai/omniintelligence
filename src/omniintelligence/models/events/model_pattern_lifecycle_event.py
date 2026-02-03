"""Pattern Lifecycle Event Model.

This event is published by handlers (promotion, demotion) to request
a pattern status transition. The reducer consumes this event, validates
the transition against contract.yaml, and emits an intent for the effect node.

Naming note: "Event" not "Requested" because the reducer IS the permission boundary.
No separate "Approved" event exists - the reducer decides and emits intent.

Ticket: OMN-1805
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternLifecycleEvent(BaseModel):
    """Pattern lifecycle event - consumed by reducer.

    The request_id is the idempotency key and flows end-to-end:
    Event.request_id → Reducer → Intent → Audit table
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: Literal["PatternLifecycleEvent"] = Field(
        default="PatternLifecycleEvent", description="Event type discriminator"
    )
    request_id: UUID = Field(
        ...,
        description="Idempotency key - flows end-to-end through the system",
    )
    pattern_id: UUID = Field(..., description="Pattern to transition")
    from_status: str = Field(..., description="Current status")
    to_status: str = Field(..., description="Target status")
    trigger: str = Field(
        ...,
        description="Trigger name: validation_passed, promote, deprecate, manual_reenable",
    )
    correlation_id: UUID | None = Field(
        default=None, description="For distributed tracing"
    )
    actor: str = Field(default="handler", description="Who initiated the transition")
    actor_type: Literal["system", "admin", "handler"] = Field(
        default="handler",
        description="Actor type for guard condition evaluation",
    )
    reason: str | None = Field(
        default=None, description="Human-readable reason for transition"
    )
    gate_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="Gate values at the time of decision (e.g., success_rate, injection_count)",
    )
    occurred_at: datetime = Field(
        ..., description="When the transition was requested"
    )


__all__ = ["ModelPatternLifecycleEvent"]
