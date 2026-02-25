# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Extraction config model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelExtractionConfig(BaseModel):
    """Configuration for pattern extraction."""

    extract_file_patterns: bool = Field(
        default=True,
        description="Extract file access and co-access patterns",
    )
    extract_error_patterns: bool = Field(
        default=True,
        description="Extract error-prone file patterns",
    )
    extract_architecture_patterns: bool = Field(
        default=True,
        description="Extract architecture and module patterns",
    )
    extract_tool_patterns: bool = Field(
        default=True,
        description="Extract tool usage patterns",
    )
    extract_tool_failure_patterns: bool = Field(
        default=True,
        description="Extract tool failure patterns from tool_executions",
    )
    min_pattern_occurrences: int = Field(
        default=2,
        ge=1,
        description="Minimum occurrences to consider a pattern",
    )
    min_distinct_sessions: int = Field(
        default=2,
        ge=1,
        description="Minimum distinct sessions a pattern must appear in",
    )
    min_confidence: float = Field(
        default=0.6,  # Aligned with contract.yaml configuration.extraction.min_confidence
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for patterns",
    )
    max_insights_per_type: int = Field(
        default=50,
        ge=1,
        description="Maximum insights to return per type",
    )
    max_results_per_pattern_type: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum patterns to return per pattern subtype (e.g., recurring_failure, failure_sequence)",
    )
    reference_time: datetime | None = Field(
        default=None,
        description="Reference time for deterministic timestamps (uses max session ended_at if None)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelExtractionConfig"]
