# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Routing feedback result model.

OMN-2622: Updated to reflect routing-feedback.v1 consumer (was routing-outcome-raw.v1).
Raw signal fields (injection_occurred, patterns_injected_count, etc.) removed;
replaced with feedback_status and skip_reason from the new payload schema.

Reference: OMN-2366, OMN-2935, OMN-2622
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_routing_feedback_effect.models.enum_routing_feedback_status import (
    EnumRoutingFeedbackStatus,
)


class ModelRoutingFeedbackResult(BaseModel):
    """Result of processing a routing-feedback event (OMN-2622).

    Returned by the handler after consuming a routing-feedback.v1 event
    and either upserting the idempotent record to routing_feedback_scores
    (when feedback_status == "produced") or skipping the DB write
    (when feedback_status == "skipped").

    Attributes:
        status: Overall processing status.
        session_id: Session ID from the input event.
        outcome: Session outcome (success, failed, abandoned, unknown).
        feedback_status: Whether reinforcement was produced or skipped.
        skip_reason: Why reinforcement was skipped (None if produced).
        was_upserted: True if a row was inserted or updated in DB.
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
    outcome: str = Field(
        ...,
        description="Session outcome from the input event",
    )
    feedback_status: Literal["produced", "skipped"] = Field(
        ...,
        description=(
            "Whether routing reinforcement was produced or skipped. "
            "Skipped events are not persisted to routing_feedback_scores. [OMN-2622]"
        ),
    )
    skip_reason: str | None = Field(
        default=None,
        description="Why reinforcement was skipped. None when feedback_status is 'produced'. [OMN-2622]",
    )
    was_upserted: bool = Field(
        default=False,
        description=(
            "True if a row was inserted or updated in routing_feedback_scores. "
            "Always False when feedback_status is 'skipped'. "
            "ON CONFLICT DO UPDATE always returns True on the success path."
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
