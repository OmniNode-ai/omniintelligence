# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Codebase Insight Model for Pattern Extraction.

This module defines the ModelCodebaseInsight model representing
individual insights extracted from codebase analysis. Uses the
EnumInsightType from enum_insight_type.py (no duplication).
"""

from __future__ import annotations

from datetime import datetime

from omnibase_core.types import PrimitiveValue
from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_extraction_compute.models.enum_insight_type import (
    EnumInsightType,
)


class ModelCodebaseInsight(BaseModel):
    """A single insight extracted from session analysis.

    Represents a pattern, trend, or observation discovered from
    analyzing Claude Code session data.

    Attributes:
        insight_id: Unique identifier for this insight.
        insight_type: Category of the insight from EnumInsightType.
        description: Human-readable description of the insight.
        confidence: Confidence score from 0.0 to 1.0.
        evidence_files: File paths that support this insight.
        evidence_session_ids: Session IDs that contribute to this insight.
        occurrence_count: Number of times this pattern was observed.
        working_directory: Working directory context if applicable.
        first_observed: When the pattern was first observed.
        last_observed: When the pattern was most recently observed.
        metadata: Additional typed metadata for the insight.
    """

    insight_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this insight",
    )
    insight_type: EnumInsightType = Field(
        ...,
        description="Category of the insight",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Human-readable description of the insight",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0",
    )
    evidence_files: tuple[str, ...] = Field(
        default=(),
        description="File paths that support this insight",
    )
    evidence_session_ids: tuple[str, ...] = Field(
        default=(),
        description="Session IDs that contribute to this insight",
    )
    occurrence_count: int = Field(
        default=1,
        ge=1,
        description="Number of times this pattern was observed",
    )
    working_directory: str | None = Field(
        default=None,
        description="Working directory context if applicable",
    )
    first_observed: datetime = Field(
        ...,
        description="When the pattern was first observed",
    )
    last_observed: datetime = Field(
        ...,
        description="When the pattern was most recently observed",
    )
    metadata: dict[str, PrimitiveValue] = Field(
        default_factory=dict,
        description="Additional typed metadata for the insight",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelCodebaseInsight"]
