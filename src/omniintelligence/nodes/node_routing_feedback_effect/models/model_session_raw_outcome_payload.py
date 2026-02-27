# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Local model for the routing-outcome-raw event payload consumed from omniclaude.

This is a consumer-side copy of ModelSessionRawOutcomePayload from omniclaude.
It defines only the fields this node consumes; additional producer fields are
silently ignored via ``extra='ignore'``.

Reference: OMN-2935, OMN-2356
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelSessionRawOutcomePayload(BaseModel):
    """Event payload for raw session outcome signals consumed from omniclaude.

    Published to: ``onex.evt.omniclaude.routing-outcome-raw.v1``

    Replaces ``ModelRoutingFeedbackEvent`` (was on ``routing-feedback.v1``).
    omniclaude emits observable facts from session end — no derived scores.
    This node persists the raw signals and may compute derived metrics.

    Note: No ``correlation_id`` field — omniclaude removed it in OMN-2356
    (it was a missing field that caused schema drift). Idempotency key is
    ``session_id`` only.

    Attributes:
        event_name: Literal discriminator for polymorphic deserialization.
        session_id: Session identifier string.
        injection_occurred: Whether context injection happened this session.
        patterns_injected_count: Number of patterns injected (0 if no injection).
        tool_calls_count: Total tool calls observed during the session.
        duration_ms: Session duration in milliseconds (0 if unknown).
        agent_selected: Agent name selected by routing (empty string if none).
        routing_confidence: Routing confidence score (0.0-1.0).
        emitted_at: Timestamp when the event was emitted (UTC).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",  # forward-compatible: omniclaude may add fields
    )

    event_name: Literal["routing.outcome.raw"] = Field(
        default="routing.outcome.raw",
        description="Event type discriminator for polymorphic deserialization",
    )
    session_id: str = Field(
        ...,
        min_length=1,
        description="Session identifier from omniclaude",
    )
    injection_occurred: bool = Field(
        ...,
        description="Whether context injection happened this session",
    )
    patterns_injected_count: int = Field(
        ...,
        ge=0,
        description="Number of patterns injected (0 if no injection occurred)",
    )
    tool_calls_count: int = Field(
        ...,
        ge=0,
        description="Total tool calls observed during the session",
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Session duration in milliseconds (0 if unknown)",
    )
    agent_selected: str = Field(
        default="",
        description="Agent name selected by routing (empty string if none selected)",
    )
    routing_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Routing confidence score from the router (0.0-1.0)",
    )
    emitted_at: AwareDatetime = Field(
        ...,
        description="Timestamp when the event was emitted (UTC)",
    )


__all__ = ["ModelSessionRawOutcomePayload"]
