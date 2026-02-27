# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Routing feedback processed event model.

Formalizes the Kafka payload published by ``_publish_processed_event()``
to ``onex.evt.omniintelligence.routing-feedback-processed.v1`` after a
successful upsert to ``routing_feedback_scores``.

Reference: OMN-2366, OMN-2935
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelRoutingFeedbackProcessedEvent(BaseModel):
    """Kafka event emitted after a routing-outcome-raw record is upserted (OMN-2935).

    This model represents the payload published to
    ``onex.evt.omniintelligence.routing-feedback-processed.v1``. Events are
    immutable after emission (``frozen=True``).

    Attributes:
        event_name: Fixed discriminator identifying the event type.
        session_id: Session ID from the original routing-outcome-raw event.
        injection_occurred: Whether context injection happened this session.
        patterns_injected_count: Number of patterns injected.
        agent_selected: Agent name selected by routing.
        routing_confidence: Routing confidence score (0.0-1.0).
        emitted_at: Timestamp from the original event envelope.
        processed_at: Timestamp of when the upsert completed in this handler.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_name: Literal["routing.feedback.processed"] = Field(
        default="routing.feedback.processed",
        description="Fixed discriminator identifying the event type",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the original routing-outcome-raw event",
    )
    injection_occurred: bool = Field(
        ...,
        description="Whether context injection happened this session",
    )
    patterns_injected_count: int = Field(
        ...,
        description="Number of patterns injected (0 if no injection occurred)",
    )
    agent_selected: str = Field(
        ...,
        description="Agent name selected by routing (empty string if none)",
    )
    routing_confidence: float = Field(
        ...,
        description="Routing confidence score from the router (0.0-1.0)",
    )
    emitted_at: AwareDatetime = Field(
        ...,
        description=(
            "Timestamp from the original event envelope — when omniclaude "
            "emitted the routing-outcome-raw event"
        ),
    )
    processed_at: AwareDatetime = Field(
        ...,
        description="Timestamp of when the upsert completed in this handler",
    )


__all__ = ["ModelRoutingFeedbackProcessedEvent"]
