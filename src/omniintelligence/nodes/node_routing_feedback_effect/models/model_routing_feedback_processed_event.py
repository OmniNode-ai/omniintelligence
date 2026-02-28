# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Routing feedback processed event model.

Formalizes the Kafka payload published by ``_publish_processed_event()``
to ``onex.evt.omniintelligence.routing-feedback-processed.v1`` after a
successful upsert to ``routing_feedback_scores``.

OMN-2622: Updated to reflect routing-feedback.v1 consumer schema.
Raw signal fields (injection_occurred, patterns_injected_count, etc.) replaced
with feedback_status and outcome from the new payload.

Reference: OMN-2366, OMN-2935, OMN-2622
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelRoutingFeedbackProcessedEvent(BaseModel):
    """Kafka event emitted after a routing-feedback record is processed (OMN-2622).

    This model represents the payload published to
    ``onex.evt.omniintelligence.routing-feedback-processed.v1``. Events are
    immutable after emission (``frozen=True``).

    Only emitted when ``feedback_status == "produced"`` (i.e., the record
    was actually upserted to routing_feedback_scores). Skipped events do
    not produce a processed confirmation.

    Attributes:
        event_name: Fixed discriminator identifying the event type.
        session_id: Session ID from the original routing-feedback event.
        outcome: Session outcome from the original event.
        feedback_status: Always "produced" for this event (skipped events not emitted).
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
        description="Session ID from the original routing-feedback event",
    )
    outcome: str = Field(
        ...,
        description="Session outcome from the original routing-feedback event",
    )
    feedback_status: Literal["produced"] = Field(
        default="produced",
        description=(
            "Always 'produced' for this event — only emitted when reinforcement "
            "was produced (not skipped). [OMN-2622]"
        ),
    )
    emitted_at: AwareDatetime = Field(
        ...,
        description=(
            "Timestamp from the original event envelope — when omniclaude "
            "emitted the routing-feedback event"
        ),
    )
    processed_at: AwareDatetime = Field(
        ...,
        description="Timestamp of when the upsert completed in this handler",
    )


__all__ = ["ModelRoutingFeedbackProcessedEvent"]
