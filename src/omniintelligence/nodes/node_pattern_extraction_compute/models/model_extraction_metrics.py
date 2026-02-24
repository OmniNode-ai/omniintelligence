# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Extraction metrics model for Pattern Extraction Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelExtractionMetrics(BaseModel):
    """Metrics from the pattern extraction process."""

    sessions_analyzed: int = Field(
        default=0,
        ge=0,
        description="Number of sessions analyzed",
    )
    total_patterns_found: int = Field(
        default=0,
        ge=0,
        description="Total raw patterns found before deduplication",
    )
    new_insights_count: int = Field(
        default=0,
        ge=0,
        description="Number of new insights created",
    )
    updated_insights_count: int = Field(
        default=0,
        ge=0,
        description="Number of existing insights updated",
    )
    file_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of file access patterns found",
    )
    error_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of error patterns found",
    )
    architecture_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of architecture patterns found",
    )
    tool_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of tool usage patterns found",
    )
    tool_failure_patterns_count: int = Field(
        default=0,
        ge=0,
        description="Number of tool failure patterns extracted",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelExtractionMetrics"]
