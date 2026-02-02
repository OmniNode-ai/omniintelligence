"""Output model for Success Criteria Matcher Compute."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class CriteriaMatchMetadataDict(TypedDict, total=False):
    """Typed structure for criteria matching metadata.

    Provides type-safe fields for matching result metadata.
    """

    # Processing info
    processing_time_ms: int
    timestamp: str

    # Match details
    total_criteria: int
    matched_count: int
    unmatched_count: int
    skipped_count: int

    # Scoring details
    weighted_score: float
    required_criteria_met: bool

    # Debug info
    match_details: list[str]


class ModelSuccessCriteriaOutput(BaseModel):
    """Output model for success criteria matching operations.

    This model represents the result of matching against success criteria.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether criteria matching succeeded",
    )
    matched_criteria: list[str] = Field(
        default_factory=list,
        description="List of matched criteria identifiers",
    )
    match_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall match score (0.0 to 1.0)",
    )
    unmatched_criteria: list[str] = Field(
        default_factory=list,
        description="List of unmatched criteria identifiers",
    )
    metadata: CriteriaMatchMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the matching with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "CriteriaMatchMetadataDict",
    "ModelSuccessCriteriaOutput",
]
