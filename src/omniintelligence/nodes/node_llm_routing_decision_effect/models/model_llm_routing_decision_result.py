# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""LLM routing decision processing result model.

Reference: OMN-2939
"""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_llm_routing_decision_effect.models.enum_llm_routing_decision_status import (
    EnumLlmRoutingDecisionStatus,
)


class ModelLlmRoutingDecisionResult(BaseModel):
    """Result of processing an LLM routing decision event.

    Returned by the handler after consuming a routing decision event and
    upserting the idempotent record to llm_routing_decisions.

    Attributes:
        status: Overall processing status.
        session_id: Session ID from the input event.
        correlation_id: Correlation ID from the input event.
        selected_agent: Agent name selected by the LLM router.
        was_upserted: True if a row was inserted or updated (ON CONFLICT DO
            UPDATE always counts as a change on the success path).
        processed_at: Timestamp of when processing completed.
        error_message: Error details if status is ERROR.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: EnumLlmRoutingDecisionStatus = Field(
        ...,
        description="Overall processing status",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the input event",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID from the input event",
    )
    selected_agent: str = Field(
        ...,
        description="Agent name selected by the LLM router",
    )
    was_upserted: bool = Field(
        default=False,
        description=(
            "True if a row was inserted or updated in llm_routing_decisions. "
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


__all__ = ["ModelLlmRoutingDecisionResult"]
