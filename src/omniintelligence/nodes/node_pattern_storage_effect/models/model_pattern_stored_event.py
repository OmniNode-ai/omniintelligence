# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelPatternStoredEvent - event model for pattern-stored.v1 events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)


class ModelPatternStoredEvent(BaseModel):
    """Event model for pattern-stored.v1 events.

    Emitted when a pattern is successfully stored in the pattern database.
    Contains all information needed to reconstruct the storage operation
    for auditing and downstream processing.

    Attributes:
        pattern_id: Unique identifier for the stored pattern.
        signature: The pattern signature that was stored.
        signature_hash: Hash of the signature (part of lineage key).
        domain: Domain of the pattern (part of lineage key).
        version: Version number in the pattern lineage.
        confidence: Confidence score at storage time.
        state: Initial state of the pattern (typically CANDIDATE).
        stored_at: Timestamp when the pattern was stored.
        actor: Identifier of the entity that stored the pattern.
        source_run_id: ID of the run that produced this pattern.
        correlation_id: Correlation ID for distributed tracing.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    pattern_id: UUID = Field(
        ...,
        description="Unique identifier for the stored pattern",
    )
    signature: str = Field(
        ...,
        min_length=1,
        description="The pattern signature that was stored",
    )
    signature_hash: str = Field(
        ...,
        min_length=1,
        description="Hash of the signature (part of lineage key)",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="Domain of the pattern (part of lineage key)",
    )
    version: int = Field(
        ...,
        ge=1,
        description="Version number in the pattern lineage",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score at storage time",
    )
    state: EnumPatternState = Field(
        default=EnumPatternState.CANDIDATE,
        description="Initial state of the pattern",
    )
    stored_at: datetime = Field(
        ...,
        description="Timestamp when the pattern was stored (UTC)",
    )
    actor: str | None = Field(
        default=None,
        description="Identifier of the entity that stored the pattern",
    )
    source_run_id: str | None = Field(
        default=None,
        description="ID of the run that produced this pattern",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )

    @property
    def lineage_key(self) -> tuple[str, str]:
        """Return the lineage key for this pattern.

        Returns:
            Tuple of (domain, signature_hash) as the lineage key.
        """
        return (self.domain, self.signature_hash)
