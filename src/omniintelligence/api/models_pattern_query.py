"""Request and response models for the pattern query API.

These models define the contract for GET /api/v1/patterns, providing
typed request validation and structured response serialization.

Ticket: OMN-2253
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternQueryResponse(BaseModel):
    """Single pattern entry in query results.

    Maps to the PatternSummary model from the repository contract,
    providing the subset of fields needed by enforcement/compliance nodes.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    id: UUID = Field(..., description="Pattern UUID")
    pattern_signature: str = Field(..., description="Pattern signature text")
    signature_hash: str = Field(
        ...,
        description="SHA256 hash for stable lineage identity",
    )
    domain_id: str = Field(
        ..., min_length=1, max_length=50, description="Domain identifier"
    )
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0.0-1.0). None means not yet computed.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pattern confidence score",
    )
    status: Literal["validated", "provisional"] = Field(
        ...,
        description="Lifecycle status (validated or provisional)",
    )
    is_current: bool = Field(
        default=True,
        description="Whether this is the current version",
    )
    version: int = Field(default=1, ge=1, description="Pattern version number")
    created_at: datetime = Field(..., description="Row creation timestamp")


class ModelPatternQueryPage(BaseModel):
    """Paginated response for pattern queries.

    Wraps a list of pattern results with pagination metadata
    to support cursor-free offset-based pagination.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    patterns: list[ModelPatternQueryResponse] = Field(
        ...,
        description="List of patterns matching the query",
    )
    total_returned: int = Field(
        ...,
        ge=0,
        description=(
            "Number of patterns in this page. "
            "When total_returned < limit, this is the final page."
        ),
    )
    limit: int = Field(
        ...,
        ge=1,
        le=200,
        description="Maximum patterns per page (request parameter)",
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Number of patterns skipped (request parameter)",
    )


__all__ = [
    "ModelPatternQueryPage",
    "ModelPatternQueryResponse",
]
