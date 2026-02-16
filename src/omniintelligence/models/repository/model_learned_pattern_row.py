"""Model for full learned_patterns table row.

Maps all columns from the learned_patterns table for complete
pattern data access. Used by repository operations that need
the full pattern state.

Note on Defaults:
    Default values in this model are for Python-side instantiation and
    validation (e.g., creating instances in tests or application code).
    The contract YAML (`learned_patterns.repository.yaml`) is the source
    of truth for database operations - the repository uses contract-defined
    defaults when inserting rows. Model defaults should be kept in sync
    with contract defaults, but contract takes precedence for persistence.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.enums import EnumPatternLifecycleStatus


class ModelDomainCandidate(BaseModel):
    """A candidate domain classification with its confidence score.

    Represents one entry in the domain_candidates JSONB array stored
    in the learned_patterns table. Each candidate pairs a domain
    identifier with a confidence score indicating how well the
    pattern matches that domain.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    domain: str = Field(..., description="Domain identifier for this candidate")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this domain classification",
    )


class ModelLearnedPatternRow(BaseModel):
    """Full row model for learned_patterns table.

    Contains all columns from the database table. Used when
    complete pattern data is needed (e.g., get_pattern, lineage queries).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    # Identity
    id: UUID = Field(..., description="Pattern UUID (primary key)")
    pattern_signature: str = Field(..., description="Pattern signature text")
    signature_hash: str = Field(
        ...,
        description="SHA256 hash of canonicalized signature for stable lineage identity",
    )
    domain_id: str = Field(..., max_length=50, description="Domain identifier")
    domain_version: str = Field(..., max_length=20, description="Domain version")

    # Classification
    domain_candidates: list[ModelDomainCandidate] = Field(
        default_factory=list,
        description="Candidate domains with scores",
    )
    keywords: list[str] | None = Field(
        default=None,
        description="Extracted keywords for search",
    )

    # Quality metrics
    confidence: float = Field(..., ge=0.5, le=1.0, description="Pattern confidence")
    quality_score: float | None = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall quality score",
    )

    # Lifecycle
    status: EnumPatternLifecycleStatus = Field(
        ...,
        description="Pattern status: candidate, provisional, validated, deprecated",
    )
    promoted_at: datetime | None = Field(
        default=None,
        description="When pattern was promoted to validated",
    )
    deprecated_at: datetime | None = Field(
        default=None,
        description="When pattern was deprecated",
    )
    deprecation_reason: str | None = Field(
        default=None,
        description="Reason for deprecation",
    )

    # Provenance
    source_session_ids: list[UUID] = Field(
        ...,
        description="Session UUIDs where pattern was observed",
    )
    recurrence_count: int = Field(
        default=1,
        ge=1,
        description="Number of times pattern has been seen",
    )
    first_seen_at: datetime = Field(..., description="First observation timestamp")
    last_seen_at: datetime = Field(..., description="Most recent observation")
    distinct_days_seen: int = Field(
        default=1,
        ge=1,
        description="Number of distinct days pattern was observed",
    )

    # Rolling performance metrics (window of 20 injections)
    injection_count_rolling_20: int | None = Field(
        default=0,
        ge=0,
        le=20,
        description="Injection count in rolling window",
    )
    success_count_rolling_20: int | None = Field(
        default=0,
        ge=0,
        le=20,
        description="Success count in rolling window",
    )
    failure_count_rolling_20: int | None = Field(
        default=0,
        ge=0,
        le=20,
        description="Failure count in rolling window",
    )
    failure_streak: int | None = Field(
        default=0,
        ge=0,
        description="Consecutive failures count",
    )

    # Versioning
    version: int = Field(default=1, ge=1, description="Pattern version number")
    is_current: bool = Field(
        default=True,
        description="Whether this is the current version",
    )
    supersedes: UUID | None = Field(
        default=None,
        description="Previous version this pattern supersedes",
    )
    superseded_by: UUID | None = Field(
        default=None,
        description="Newer version that supersedes this pattern",
    )

    # Compilation
    compiled_snippet: str | None = Field(
        default=None,
        description="Compiled pattern snippet for injection",
    )
    compiled_token_count: int | None = Field(
        default=None,
        ge=1,
        description="Token count of compiled snippet",
    )
    compiled_at: datetime | None = Field(
        default=None,
        description="When pattern was compiled",
    )

    # Timestamps
    created_at: datetime = Field(..., description="Row creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


__all__ = ["ModelDomainCandidate", "ModelLearnedPatternRow"]
