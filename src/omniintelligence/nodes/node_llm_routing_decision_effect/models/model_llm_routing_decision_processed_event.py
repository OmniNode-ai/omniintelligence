# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""LLM routing decision processed confirmation event model.

Reference: OMN-2939
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelLlmRoutingDecisionProcessedEvent(BaseModel):
    """Confirmation event published after processing an LLM routing decision event.

    Published to: ``onex.evt.omniintelligence.llm-routing-decision-processed.v1``

    Attributes:
        event_name: Literal discriminator for polymorphic deserialization.
        session_id: Session ID from the original event.
        correlation_id: Correlation ID from the original event.
        selected_agent: Agent name selected by the LLM router.
        was_upserted: Whether a DB row was created/updated.
        processed_at: Timestamp of when processing completed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_name: Literal["llm.routing.decision.processed"] = Field(
        default="llm.routing.decision.processed",
        description="Event type discriminator",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the original event",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID from the original event",
    )
    selected_agent: str = Field(
        ...,
        description="Agent name selected by the LLM router",
    )
    was_upserted: bool = Field(
        default=False,
        description="Whether a DB row was created/updated",
    )
    processed_at: AwareDatetime = Field(
        ...,
        description="Timestamp of when processing completed",
    )


__all__ = ["ModelLlmRoutingDecisionProcessedEvent"]
