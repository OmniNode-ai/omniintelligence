# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for pattern storage effect node.

This module defines the output event models for pattern storage operations:
- ModelPatternStoredEvent: Emitted when a pattern is stored (pattern-stored.v1)
- ModelPatternPromotedEvent: Emitted when a pattern is promoted (pattern-promoted.v1)

Reference:
    - OMN-1668: Pattern storage effect models
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)


class ModelPatternMetricsSnapshot(BaseModel):
    """Snapshot of pattern metrics at promotion time.

    Captures the metrics used to justify a pattern state promotion,
    providing auditability for governance decisions.

    Attributes:
        confidence: Current confidence score at promotion time.
        match_count: Number of times the pattern was matched.
        success_rate: Success rate of pattern applications.
        last_matched_at: Timestamp of last pattern match.
        validation_count: Number of validation passes.
        additional_metrics: Extra metrics as key-value pairs.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Current confidence score at promotion time",
    )
    match_count: int = Field(
        default=0,
        ge=0,
        description="Number of times the pattern was matched",
    )
    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Success rate of pattern applications (0.0-1.0)",
    )
    last_matched_at: datetime | None = Field(
        default=None,
        description="Timestamp of last pattern match (UTC)",
    )
    validation_count: int = Field(
        default=0,
        ge=0,
        description="Number of validation passes",
    )
    additional_metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Extra metrics as key-value pairs (numeric values only)",
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

    Example:
        >>> event = ModelPatternStoredEvent(
        ...     pattern_id=uuid4(),
        ...     signature="def.*return.*None",
        ...     signature_hash="abc123def456",
        ...     domain="code_patterns",
        ...     version=1,
        ...     confidence=0.85,
        ...     state=EnumPatternState.CANDIDATE,
        ...     stored_at=datetime.now(UTC),
        ...     actor="pattern_learning_compute",
        ...     source_run_id="run-123",
        ... )
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


class ModelPatternPromotedEvent(BaseModel):
    """Event model for pattern-promoted.v1 events.

    Emitted when a pattern is promoted from one state to another
    (e.g., candidate → provisional, provisional → validated).
    Contains audit trail information for governance compliance.

    Attributes:
        pattern_id: Unique identifier of the promoted pattern.
        from_state: Previous state before promotion.
        to_state: New state after promotion.
        reason: Human-readable reason for the promotion.
        metrics_snapshot: Snapshot of metrics at promotion time.
        promoted_at: Timestamp when the promotion occurred.
        correlation_id: Correlation ID for distributed tracing.
        actor: Identifier of the entity that triggered the promotion.

    Example:
        >>> event = ModelPatternPromotedEvent(
        ...     pattern_id=uuid4(),
        ...     from_state=EnumPatternState.CANDIDATE,
        ...     to_state=EnumPatternState.PROVISIONAL,
        ...     reason="Pattern met verification criteria",
        ...     metrics_snapshot=ModelPatternMetricsSnapshot(
        ...         confidence=0.85,
        ...         match_count=10,
        ...         success_rate=0.9,
        ...     ),
        ...     promoted_at=datetime.now(UTC),
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    pattern_id: UUID = Field(
        ...,
        description="Unique identifier of the promoted pattern",
    )
    from_state: EnumPatternState = Field(
        ...,
        description="Previous state before promotion",
    )
    to_state: EnumPatternState = Field(
        ...,
        description="New state after promotion",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Human-readable reason for the promotion",
    )
    metrics_snapshot: ModelPatternMetricsSnapshot = Field(
        ...,
        description="Snapshot of metrics at promotion time for audit",
    )
    promoted_at: datetime = Field(
        ...,
        description="Timestamp when the promotion occurred (UTC)",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    actor: str | None = Field(
        default=None,
        description="Identifier of the entity that triggered the promotion",
    )

    def is_valid_transition(self) -> bool:
        """Check if the state transition is valid.

        Valid transitions are:
        - CANDIDATE → PROVISIONAL
        - PROVISIONAL → VALIDATED

        Returns:
            True if the transition is valid, False otherwise.
        """
        valid_transitions = {
            (EnumPatternState.CANDIDATE, EnumPatternState.PROVISIONAL),
            (EnumPatternState.PROVISIONAL, EnumPatternState.VALIDATED),
        }
        return (self.from_state, self.to_state) in valid_transitions


__all__ = [
    "ModelPatternMetricsSnapshot",
    "ModelPatternPromotedEvent",
    "ModelPatternStoredEvent",
]
