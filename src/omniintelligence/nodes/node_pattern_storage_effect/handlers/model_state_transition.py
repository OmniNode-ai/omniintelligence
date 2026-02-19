# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ModelStateTransition - audit record for a pattern state transition."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)

DEFAULT_ACTOR: str = "system"
"""Default actor for state transitions when not specified."""


class ModelStateTransition(BaseModel):
    """Audit record for a pattern state transition.

    This model represents a single state transition event recorded in the
    pattern_state_transitions database table for audit trail purposes.

    Attributes:
        id: Unique identifier for this transition record.
        pattern_id: The pattern that was transitioned.
        domain: Domain of the pattern (for lineage context).
        signature_hash: Signature hash of the pattern (for lineage context).
        from_state: Previous state before transition (None for initial state).
        to_state: New state after transition.
        reason: Human-readable reason for the transition.
        actor: Identifier of the entity that triggered the transition.
        event_id: Idempotency key for deduplication.
        metadata: Additional context as key-value pairs.
        created_at: Timestamp when the transition was recorded (UTC).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this transition record",
    )
    pattern_id: UUID = Field(
        ...,
        description="The pattern that was transitioned",
    )
    domain: str | None = Field(
        default=None,
        description="Domain of the pattern (for lineage context)",
    )
    signature_hash: str | None = Field(
        default=None,
        description="Signature hash of the pattern (for lineage context)",
    )
    from_state: EnumPatternState | None = Field(
        ...,
        description="Previous state before transition (None for initial state)",
    )
    to_state: EnumPatternState = Field(
        ...,
        description="New state after transition",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Human-readable reason for the transition",
    )
    actor: str = Field(
        default=DEFAULT_ACTOR,
        min_length=1,
        description="Identifier of the entity that triggered the transition",
    )
    event_id: UUID = Field(
        default_factory=uuid4,
        description="Idempotency key for deduplication",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Additional context as key-value pairs",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the transition was recorded (UTC)",
    )
