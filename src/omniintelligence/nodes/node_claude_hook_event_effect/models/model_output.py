# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for Claude Hook Event Effect node.

This module defines the output model for Claude Code hook event processing.
The result includes processing status, any classification results (for
UserPromptSubmit events), and metadata about the processing.

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EnumHookProcessingStatus(StrEnum):
    """Status of hook event processing."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnumKafkaEmissionStatus(StrEnum):
    """Status of Kafka event emission.

    Used in handler metadata to indicate the outcome of attempting
    to emit events to Kafka topics.
    """

    SUCCESS = "success"
    FAILED = "failed"
    NO_PRODUCER = "no_producer_available"
    NO_TOPIC_SUFFIX = "no_topic_suffix_configured"


class ModelIntentResult(BaseModel):
    """Result of intent classification (for UserPromptSubmit events).

    This model captures the intent classification output when a
    UserPromptSubmit event is processed. Graph storage is handled
    downstream by omnimemory consuming the Kafka event.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    intent_category: str = Field(
        ...,
        description="Classified intent category (e.g., debugging, code_generation)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification (0.0-1.0)",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords extracted from intent classification",
    )
    secondary_intents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Secondary intents with lower confidence",
    )
    emitted_to_kafka: bool = Field(
        default=False,
        description="Whether the intent was emitted to Kafka",
    )


class ModelClaudeHookResult(BaseModel):
    """Output model for Claude Code hook event processing.

    This model represents the result of processing any Claude Code hook
    event. For UserPromptSubmit events, it includes intent classification
    results. For other event types (currently no-op), it returns success
    with minimal metadata.

    Attributes:
        status: Overall processing status.
        event_type: The event type that was processed.
        session_id: Session ID from the input event.
        correlation_id: Correlation ID for tracing.
        intent_result: Intent classification result (UserPromptSubmit only).
        processing_time_ms: Time taken to process the event.
        processed_at: When processing completed.
        error_message: Error details if status is failed.
        metadata: Additional processing metadata.

    Example:
        >>> result = ModelClaudeHookResult(
        ...     status="success",
        ...     event_type="UserPromptSubmit",
        ...     session_id="session-123",
        ...     correlation_id=uuid4(),
        ...     intent_result=ModelIntentResult(
        ...         intent_category="debugging",
        ...         confidence=0.92,
        ...     ),
        ...     processing_time_ms=45.2,
        ...     processed_at=datetime.now(UTC),
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    status: EnumHookProcessingStatus = Field(
        ...,
        description="Overall processing status",
    )
    event_type: str = Field(
        ...,
        description="The event type that was processed",
    )
    session_id: str = Field(
        ...,
        description="Session ID from the input event",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (optional in core model)",
    )
    intent_result: ModelIntentResult | None = Field(
        default=None,
        description="Intent classification result (UserPromptSubmit only)",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time taken to process the event in milliseconds",
    )
    processed_at: datetime = Field(
        ...,
        description="When processing completed (UTC)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if status is failed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional processing metadata",
    )


__all__ = [
    "EnumHookProcessingStatus",
    "EnumKafkaEmissionStatus",
    "ModelClaudeHookResult",
    "ModelIntentResult",
]
