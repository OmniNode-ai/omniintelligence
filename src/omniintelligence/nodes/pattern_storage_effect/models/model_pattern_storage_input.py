# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input model for pattern storage effect node.

This module defines the input model for pattern storage operations,
representing patterns received from the pattern-learned.v1 event.

The lineage key is (domain, signature_hash) for deduplication and
version tracking.

Reference:
    - OMN-1668: Pattern storage effect models
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omniintelligence.nodes.pattern_storage_effect.models.model_pattern_state import (
    PatternStorageGovernance,
)


class ModelPatternStorageMetadata(BaseModel):
    """Metadata for pattern storage operations.

    Captures contextual information about the pattern including its
    source, learning context, and any additional attributes.

    Attributes:
        source_run_id: ID of the run that produced this pattern.
        actor: Identifier of the entity that created/learned the pattern.
        learning_context: Context in which the pattern was learned.
        tags: Optional tags for categorization.
        additional_attributes: Extra metadata as key-value pairs.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source_run_id: str | None = Field(
        default=None,
        description="ID of the run that produced this pattern",
    )
    actor: str | None = Field(
        default=None,
        description="Identifier of the entity that created/learned the pattern",
    )
    learning_context: str | None = Field(
        default=None,
        description="Context in which the pattern was learned",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for categorization",
    )
    additional_attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Extra metadata as key-value pairs (string values only)",
    )


class ModelPatternStorageInput(BaseModel):
    """Input model for pattern storage operations.

    Represents a learned pattern from the pattern-learned.v1 event
    that is ready to be stored. Includes validation to enforce the
    minimum confidence threshold.

    The lineage key (domain, signature_hash) uniquely identifies a
    pattern lineage for deduplication and version tracking.

    Attributes:
        pattern_id: Unique identifier for this pattern instance.
        signature: The pattern signature (behavioral/structural fingerprint).
        signature_hash: Hash of the signature for efficient lookup.
        domain: Domain where the pattern was learned (e.g., "code_review").
        confidence: Confidence score (must be >= MIN_CONFIDENCE = 0.5).
        correlation_id: Correlation ID for distributed tracing.
        version: Version number for pattern lineage (defaults to 1).
        metadata: Additional metadata about the pattern.
        learned_at: Timestamp when the pattern was learned.

    Example:
        >>> input_model = ModelPatternStorageInput(
        ...     pattern_id=uuid4(),
        ...     signature="def.*return.*None",
        ...     signature_hash="abc123def456",
        ...     domain="code_patterns",
        ...     confidence=0.85,
        ...     correlation_id=uuid4(),
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    pattern_id: UUID = Field(
        ...,
        description="Unique identifier for this pattern instance",
    )
    signature: str = Field(
        ...,
        min_length=1,
        description="The pattern signature (behavioral/structural fingerprint)",
    )
    signature_hash: str = Field(
        ...,
        min_length=1,
        description="Hash of the signature for efficient lookup (lineage key component)",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="Domain where the pattern was learned (lineage key component)",
    )
    confidence: float = Field(
        ...,
        ge=PatternStorageGovernance.MIN_CONFIDENCE,
        le=1.0,
        description=f"Confidence score (must be >= {PatternStorageGovernance.MIN_CONFIDENCE})",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Version number for pattern lineage",
    )
    metadata: ModelPatternStorageMetadata = Field(
        default_factory=ModelPatternStorageMetadata,
        description="Additional metadata about the pattern",
    )
    learned_at: datetime | None = Field(
        default=None,
        description="Timestamp when the pattern was learned (UTC)",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        """Validate confidence meets minimum governance threshold.

        NOTE: This validator intentionally duplicates the Pydantic `ge` constraint
        on the confidence field. The duplication serves governance purposes:
        1. Provides explicit, governance-specific error messages for audit trails
        2. Makes the governance rule visible at validation layer (not just schema)
        3. Ensures consistent error messaging across all validation contexts

        The MIN_CONFIDENCE threshold is a governance constant that cannot
        be overridden. This ensures all stored patterns meet quality standards.

        Raises:
            ValueError: If confidence is below MIN_CONFIDENCE threshold.
        """
        if v < PatternStorageGovernance.MIN_CONFIDENCE:
            msg = (
                f"Confidence {v} is below minimum threshold "
                f"{PatternStorageGovernance.MIN_CONFIDENCE}"
            )
            raise ValueError(msg)
        return v

    @property
    def lineage_key(self) -> tuple[str, str]:
        """Return the lineage key for this pattern.

        The lineage key (domain, signature) uniquely identifies
        a pattern lineage for deduplication and version tracking.

        Returns:
            Tuple of (domain, signature) as the lineage key.
        """
        return (self.domain, self.signature)


__all__ = [
    "ModelPatternStorageInput",
    "ModelPatternStorageMetadata",
]
