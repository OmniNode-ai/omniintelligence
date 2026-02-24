# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reducer metadata model for Intelligence Reducer."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumFSMType


class ModelReducerMetadata(BaseModel):
    """Typed structure for reducer output metadata.

    Contains timing, context, and traceability information about the
    state transition.
    """

    transition_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of the state transition",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Processing time in milliseconds",
    )
    lease_id: str | None = Field(
        default=None,
        description="Action lease ID if distributed coordination was used",
    )
    epoch: int | None = Field(
        default=None,
        description="Epoch for action lease management",
    )
    fsm_type: EnumFSMType = Field(
        ...,
        description="FSM type that was processed",
    )
    entity_id: str = Field(
        ...,
        description="Entity ID that was processed",
    )
    action: str = Field(
        ...,
        description="Action that triggered the transition",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency key used for deduplication",
    )
    was_duplicate: bool = Field(
        default=False,
        description="Whether this was a duplicate action (skipped)",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["ModelReducerMetadata"]
