# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Request model for ``HandlerTransition.handle``.

Carries the per-call values of a pattern lifecycle transition. Collaborators
(repository, idempotency store, Kafka producer) are bound to the handler at
construction time and are NOT part of the request.

Ticket: OMN-1805, OMN-21536
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.domain import ModelGateSnapshot


class ModelPatternLifecycleTransitionRequest(BaseModel):
    """Per-call input for applying a pattern lifecycle status transition.

    Attributes:
        request_id: Idempotency key - MUST match the original event request_id.
        correlation_id: For distributed tracing.
        pattern_id: Pattern to update.
        from_status: Expected current status (for optimistic locking).
        to_status: New status to apply.
        trigger: What triggered this transition.
        actor: Who applied the transition.
        reason: Human-readable reason (optional).
        gate_snapshot: Gate values at decision time (optional).
        transition_at: When to record as transition time.
        publish_topic: Full Kafka topic for publishing transition events.
            Required when the handler was constructed with a producer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    request_id: UUID = Field(..., description="Idempotency key")
    correlation_id: UUID = Field(..., description="Distributed tracing ID")
    pattern_id: UUID = Field(..., description="Pattern to update")
    from_status: EnumPatternLifecycleStatus = Field(
        ..., description="Expected current status (optimistic lock)"
    )
    to_status: EnumPatternLifecycleStatus = Field(
        ..., description="New status to apply"
    )
    trigger: str = Field(..., description="What triggered this transition")
    actor: str = Field(default="reducer", description="Who applied the transition")
    reason: str | None = Field(default=None, description="Human-readable reason")
    # dict is listed first with left_to_right so a raw dict snapshot is carried
    # through verbatim instead of being coerced into (and truncated by)
    # ModelGateSnapshot; ModelGateSnapshot instances fall through to the model.
    gate_snapshot: dict[str, object] | ModelGateSnapshot | None = Field(
        default=None,
        description="Gate values at decision time",
        union_mode="left_to_right",
    )
    transition_at: datetime = Field(..., description="Recorded transition time")
    publish_topic: str | None = Field(
        default=None,
        description="Full Kafka topic for transition events (required with a producer)",
    )


__all__ = ["ModelPatternLifecycleTransitionRequest"]
