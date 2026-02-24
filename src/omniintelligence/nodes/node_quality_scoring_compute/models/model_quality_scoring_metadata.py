# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Quality scoring metadata model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelQualityScoringMetadata(BaseModel):
    """Typed metadata for quality scoring output.

    Attributes:
        status: Current status of the scoring operation.
        message: Human-readable message about the scoring result.
        tracking_url: URL for tracking stub implementation progress.
        source_language: Programming language of the scored content.
        analysis_version: Version of the analysis algorithm used.
        processing_time_ms: Time taken to process the scoring in milliseconds.
    """

    status: str = Field(
        default="completed",
        description="Status of the scoring operation (e.g., 'completed', 'stub', 'error')",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable message about the scoring result",
    )
    tracking_url: str | None = Field(
        default=None,
        description="URL for tracking stub implementation progress (for stub nodes)",
    )
    source_language: str | None = Field(
        default=None,
        description="Programming language of the scored content",
    )
    analysis_version: str | None = Field(
        default=None,
        description="Version of the analysis algorithm used",
    )
    processing_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Time taken to process the scoring in milliseconds",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQualityScoringMetadata"]
