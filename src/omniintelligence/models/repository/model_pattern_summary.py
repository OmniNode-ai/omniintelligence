# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Model for pattern summary (subset of columns for list operations).

Lightweight model containing only the fields returned by list_by_domain
and similar summary queries. Avoids the overhead of full PatternRow
when only basic fields are needed.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternSummary(BaseModel):
    """Summary model for pattern list operations.

    Used by operations like list_by_domain that return a subset of columns
    for efficiency. Contains identity, quality metrics, and basic state.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    # Identity
    id: UUID = Field(..., description="Pattern UUID")
    pattern_signature: str = Field(..., description="Pattern signature text")
    signature_hash: str = Field(
        ...,
        description="SHA256 hash of canonicalized signature for stable lineage identity",
    )
    domain_id: str = Field(..., max_length=50, description="Domain identifier")

    # Quality metrics
    quality_score: float | None = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall quality score",
    )
    confidence: float = Field(..., ge=0.5, le=1.0, description="Pattern confidence")

    # State
    status: str = Field(
        ...,
        description="Pattern status: candidate, provisional, validated, deprecated",
    )
    is_current: bool = Field(
        default=True,
        description="Whether this is the current version",
    )
    version: int = Field(default=1, ge=1, description="Pattern version number")

    # Timestamps
    created_at: datetime = Field(..., description="Row creation timestamp")


__all__ = ["ModelPatternSummary"]
