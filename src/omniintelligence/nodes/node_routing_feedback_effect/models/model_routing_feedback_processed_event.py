# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Routing feedback processed event model.

Formalizes the Kafka payload published by ``_publish_processed_event()``
to ``onex.evt.omniintelligence.routing-feedback-processed.v1`` after a
successful upsert to ``routing_feedback_scores``.

Reference: OMN-2366
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_routing_feedback_effect.models.enum_routing_feedback_outcome import (
    EnumRoutingFeedbackOutcome,
)


class ModelRoutingFeedbackProcessedEvent(BaseModel):
    """Kafka event emitted after a routing feedback record is upserted.

    This model represents the payload published to
    ``onex.evt.omniintelligence.routing-feedback-processed.v1``. Events are
    immutable after emission (``frozen=True``).

    Attributes:
        event_name: Fixed discriminator identifying the event type.
        session_id: Session ID from the original routing feedback event.
        correlation_id: Correlation ID from the original routing feedback event.
        stage: Hook stage from the original routing feedback event.
        outcome: Session outcome from the original routing feedback event.
        emitted_at: Timestamp from the original event envelope (when omniclaude
            emitted the routing feedback event).
        processed_at: Timestamp of when the upsert completed in this handler.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_name: Literal["routing.feedback.processed"] = Field(
        default="routing.feedback.processed",
        description="Fixed discriminator identifying the event type",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the original routing feedback event",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from the original routing feedback event",
    )
    stage: str = Field(
        ...,
        min_length=1,
        description="Hook stage from the original routing feedback event",
    )
    outcome: EnumRoutingFeedbackOutcome = Field(
        ...,
        description="Session outcome from the original routing feedback event",
    )
    emitted_at: AwareDatetime = Field(
        ...,
        description=(
            "Timestamp from the original event envelope — when omniclaude "
            "emitted the routing feedback event"
        ),
    )
    processed_at: AwareDatetime = Field(
        ...,
        description="Timestamp of when the upsert completed in this handler",
    )


__all__ = ["ModelRoutingFeedbackProcessedEvent"]
