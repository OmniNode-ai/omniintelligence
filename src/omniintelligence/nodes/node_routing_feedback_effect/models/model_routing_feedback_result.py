# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Routing feedback result model.

Reference: OMN-2366, OMN-2935
"""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_routing_feedback_effect.models.enum_routing_feedback_status import (
    EnumRoutingFeedbackStatus,
)


class ModelRoutingFeedbackResult(BaseModel):
    """Result of processing a routing-outcome-raw event (OMN-2935).

    Returned by the handler after consuming a routing-outcome-raw event and
    upserting the idempotent record to routing_feedback_scores.

    Attributes:
        status: Overall processing status.
        session_id: Session ID from the input event.
        injection_occurred: Whether context injection happened this session.
        patterns_injected_count: Number of patterns injected.
        tool_calls_count: Total tool calls observed.
        duration_ms: Session duration in milliseconds.
        agent_selected: Agent name selected by routing.
        routing_confidence: Routing confidence score (0.0-1.0).
        was_upserted: True if a row was inserted or updated.
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
    injection_occurred: bool = Field(
        ...,
        description="Whether context injection happened this session",
    )
    patterns_injected_count: int = Field(
        ...,
        description="Number of patterns injected (0 if no injection occurred)",
    )
    tool_calls_count: int = Field(
        ...,
        description="Total tool calls observed during the session",
    )
    duration_ms: int = Field(
        ...,
        description="Session duration in milliseconds (0 if unknown)",
    )
    agent_selected: str = Field(
        ...,
        description="Agent name selected by routing (empty string if none)",
    )
    routing_confidence: float = Field(
        ...,
        description="Routing confidence score (0.0-1.0)",
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
