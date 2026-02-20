# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Routing feedback result model.

Reference: OMN-2366
"""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_routing_feedback_effect.models.enum_routing_feedback_outcome import (
    EnumRoutingFeedbackOutcome,
)
from omniintelligence.nodes.node_routing_feedback_effect.models.enum_routing_feedback_status import (
    EnumRoutingFeedbackStatus,
)


class ModelRoutingFeedbackResult(BaseModel):
    """Result of processing a routing feedback event.

    Returned by the handler after consuming a routing feedback event and
    upserting the idempotent record to routing_feedback_scores.

    Attributes:
        status: Overall processing status.
        session_id: Session ID from the input event.
        correlation_id: Correlation ID from the input event.
        stage: Hook stage from the input event.
        outcome: Session outcome from the input event.
        was_upserted: True if a row was inserted or updated (ON CONFLICT DO
            UPDATE always counts as a change on the success path).
        processed_at: Timestamp of when processing completed.
        error_message: Error details if status is ERROR.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: EnumRoutingFeedbackStatus = Field(
        ...,
        description="Overall processing status",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the input event",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID from the input event",
    )
    stage: str = Field(
        ...,
        description="Hook stage from the input event",
    )
    outcome: EnumRoutingFeedbackOutcome = Field(
        ...,
        description="Session outcome from the input event",
    )
    was_upserted: bool = Field(
        default=False,
        description=(
            "True if a row was inserted or updated in routing_feedback_scores. "
            "ON CONFLICT DO UPDATE always returns True on the success path; "
            "False only when status is ERROR and the upsert did not execute."
        ),
    )
    processed_at: AwareDatetime = Field(
        ...,
        description="Timestamp of when processing completed",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if status is ERROR",
    )


__all__ = ["ModelRoutingFeedbackResult"]
