# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Local model for the routing-feedback event payload consumed from omniclaude.

This is a consumer-side copy of ModelRoutingFeedbackPayload from omniclaude.
It defines only the fields this node consumes; additional producer fields are
silently ignored via ``extra='ignore'``.

OMN-2622: Switched subscription from routing-outcome-raw.v1 to routing-feedback.v1.
The producer (omniclaude) now emits all feedback outcomes (produced + skipped) on
routing-feedback.v1 with a ``feedback_status`` field. This consumer filters on
``feedback_status`` to decide whether to persist the record to routing_feedback_scores.

Reference: OMN-2622, OMN-2366, OMN-2935
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelRoutingFeedbackPayload(BaseModel):
    """Event payload for routing feedback consumed from omniclaude.

    Published to: ``onex.evt.omniclaude.routing-feedback.v1``

    OMN-2622: This model replaces ModelSessionRawOutcomePayload (was on
    ``routing-outcome-raw.v1``). All routing feedback outcomes — both
    produced and skipped — are now emitted on the routing-feedback topic.
    Filter on ``feedback_status`` to decide whether to learn:

    - ``feedback_status == "produced"``: reinforcement happened → persist to DB
    - ``feedback_status == "skipped"``: guardrail blocked → skip DB write,
      log skip_reason for observability

    Attributes:
        event_name: Literal discriminator for polymorphic deserialization.
        session_id: Session identifier string.
        outcome: Session outcome (success, failed, abandoned, unknown).
        feedback_status: Whether reinforcement was produced or skipped.
        skip_reason: Why reinforcement was skipped. None when produced.
        correlation_id: Optional correlation ID for distributed tracing.
        emitted_at: Timestamp when the event was emitted (UTC).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",  # forward-compatible: omniclaude may add fields
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
    outcome: str = Field(
        ...,
        description="Session outcome (success, failed, abandoned, unknown)",
    )
    feedback_status: Literal["produced", "skipped"] = Field(
        ...,
        description=(
            "Whether routing reinforcement was produced (all guardrails passed) "
            "or skipped (at least one guardrail failed). [OMN-2622]"
        ),
    )
    skip_reason: str | None = Field(
        default=None,
        description=(
            "Why reinforcement was skipped. None when feedback_status is 'produced'. [OMN-2622]"
        ),
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing. Optional.",
    )
    emitted_at: AwareDatetime = Field(
        ...,
        description="Timestamp when the event was emitted (UTC)",
    )


__all__ = ["ModelRoutingFeedbackPayload"]
