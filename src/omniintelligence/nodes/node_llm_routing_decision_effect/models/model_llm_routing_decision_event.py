# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""LLM routing decision event model consumed from omniclaude's Bifrost LLM gateway.

Reference: OMN-2939, OMN-2740
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ModelLlmRoutingDecisionEvent(BaseModel):
    """LLM routing decision event consumed from omniclaude's Bifrost LLM gateway.

    Published to: ``onex.evt.omniclaude.llm-routing-decision.v1``

    This event is emitted by ``_emit_llm_routing_decision()`` in omniclaude's
    ``route_via_events_wrapper.py`` after a successful LLM routing decision.
    It contains the full decision metadata required to compare LLM vs fuzzy
    matching agreement and track model performance over time.

    Attributes:
        event_name: Literal discriminator for polymorphic deserialization.
        session_id: Session identifier from omniclaude.
        correlation_id: Distributed tracing correlation ID.
        selected_agent: Agent name selected by the LLM router.
        llm_confidence: Confidence score returned by the LLM (0.0-1.0).
        llm_latency_ms: Routing latency in milliseconds.
        fallback_used: True if the LLM fell back to fuzzy matching.
        model_used: Model identifier used for routing (e.g. model endpoint URL).
        fuzzy_top_candidate: Top agent from fuzzy matching (determinism audit).
        llm_selected_candidate: Raw agent name the LLM returned before mapping.
        agreement: True when LLM and fuzzy top candidates agree.
        routing_prompt_version: Prompt template version string.
        emitted_at: Timestamp when the event was emitted (UTC). Optional
            because earlier versions of omniclaude may not include it.

    Example:
        >>> from datetime import UTC, datetime
        >>> from uuid import uuid4
        >>> event = ModelLlmRoutingDecisionEvent(
        ...     session_id="abc12345-session",
        ...     correlation_id=uuid4(),
        ...     selected_agent="agent-api",
        ...     llm_confidence=0.92,
        ...     llm_latency_ms=45,
        ...     fallback_used=False,
        ...     model_used="http://192.168.86.201:8001",
        ...     fuzzy_top_candidate="agent-api",
        ...     llm_selected_candidate="agent-api",
        ...     agreement=True,
        ...     routing_prompt_version="v1.2",
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",  # omniclaude may add fields; ignore unknown
    )

    event_name: Literal["llm.routing.decision"] = Field(
        default="llm.routing.decision",
        description="Event type discriminator for polymorphic deserialization",
    )
    session_id: str = Field(
        ...,
        min_length=1,
        description="Session identifier from omniclaude",
    )
    correlation_id: str = Field(
        ...,
        min_length=1,
        description="Distributed tracing correlation ID (string from omniclaude)",
    )
    selected_agent: str = Field(
        ...,
        min_length=1,
        description="Agent name selected by the LLM router",
    )
    llm_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score returned by the LLM (0.0-1.0)",
    )
    llm_latency_ms: int = Field(
        default=0,
        ge=0,
        description="Routing latency in milliseconds",
    )
    fallback_used: bool = Field(
        default=False,
        description="True if the LLM fell back to fuzzy matching",
    )
    model_used: str = Field(
        default="",
        description="Model identifier used for routing",
    )
    fuzzy_top_candidate: str | None = Field(
        default=None,
        description="Top agent from fuzzy matching (determinism audit)",
    )
    llm_selected_candidate: str | None = Field(
        default=None,
        description="Raw agent name the LLM returned before mapping",
    )
    agreement: bool = Field(
        default=False,
        description="True when LLM and fuzzy top candidates agree",
    )
    routing_prompt_version: str = Field(
        default="",
        description="Prompt template version string",
    )
    emitted_at: AwareDatetime | None = Field(
        default=None,
        description="Timestamp when the event was emitted (UTC); optional for backwards compat",
    )


__all__ = ["ModelLlmRoutingDecisionEvent"]
