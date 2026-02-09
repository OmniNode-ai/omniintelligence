# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Intent receipt model for Intelligence Orchestrator.

This module provides the structured result returned when the orchestrator
receives and processes an intent emitted by the intelligence reducer.

The receipt confirms that the intent was received, logged, and recorded,
proving the intent channel works end-to-end.

Ticket: OMN-2034
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelIntentReceipt(BaseModel):
    """Receipt confirming an intent was received and recorded by the orchestrator.

    This model captures the essential metadata about intent reception,
    providing observability into the reducer-to-orchestrator intent channel.

    Attributes:
        received: Whether the intent was successfully received.
        intent_id: The unique ID of the received intent.
        intent_type: The type of the received intent (for routing context).
        target: The target URI the intent was addressed to.
        correlation_id: Correlation ID for distributed tracing.
        received_at: Timestamp when the intent was received.
        message: Human-readable description of what happened.
    """

    received: bool = Field(
        ...,
        description="Whether the intent was successfully received and recorded",
    )
    intent_id: UUID = Field(
        ...,
        description="The unique ID of the received intent",
    )
    intent_type: str = Field(
        ...,
        description="The type of the received intent",
    )
    target: str = Field(
        ...,
        description="The target URI the intent was addressed to",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the intent was received",
    )
    message: str = Field(
        default="Intent received and recorded",
        description="Human-readable description of the receipt",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelIntentReceipt"]
