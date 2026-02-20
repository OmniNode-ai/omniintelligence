# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Routing feedback event model consumed from omniclaude's session-end hook.

Reference: OMN-2366, OMN-2356
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelRoutingFeedbackEvent(BaseModel):
    """Routing feedback event consumed from omniclaude's session-end hook.

    Published to: ``onex.evt.omniclaude.routing-feedback.v1``

    This event announces that a routing decision was reinforced at session end.
    The guardrails in omniclaude emit this only when the routing decision
    quality meets the reinforcement criteria (all gates passed).

    The ``stage`` field defaults to ``"session_end"`` for all events produced
    by omniclaude's session-end hook. It is included in the idempotency key
    to support potential future hooks emitting at different stages.

    Attributes:
        event_name: Literal discriminator for polymorphic deserialization.
        session_id: Session identifier from omniclaude.
        correlation_id: Distributed tracing correlation ID. Required field;
            must be provided by the producer (no default).
        stage: Hook stage that emitted this event (always ``"session_end"``
            from omniclaude's current implementation).
        outcome: Session outcome (``"success"`` or ``"failed"``).
        emitted_at: Timestamp when the event was emitted (UTC).

    Example:
        >>> from datetime import UTC, datetime
        >>> from uuid import uuid4
        >>> event = ModelRoutingFeedbackEvent(
        ...     session_id="abc12345-session",
        ...     correlation_id=uuid4(),
        ...     outcome="success",
        ...     emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",  # omniclaude may add fields; ignore unknown
    )

    event_name: Literal["routing.feedback"] = Field(
        default="routing.feedback",
        description="Event type discriminator for polymorphic deserialization",
    )
    session_id: str = Field(
        ...,
        min_length=1,
        description="Session identifier from omniclaude",
    )
    correlation_id: UUID = Field(
        ...,
        description="Distributed tracing correlation ID",
    )
    stage: str = Field(
        default="session_end",
        description="Hook stage that emitted this event",
    )
    outcome: Literal["success", "failed"] = Field(
        ...,
        description="Session outcome that triggered feedback",
    )
    emitted_at: datetime = Field(
        ...,
        description="Timestamp when the event was emitted (UTC)",
    )


__all__ = ["ModelRoutingFeedbackEvent"]
