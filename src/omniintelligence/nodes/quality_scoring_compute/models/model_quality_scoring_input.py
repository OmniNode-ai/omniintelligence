"""Input model for Quality Scoring Compute."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ModelQualityScoringInput(BaseModel):
    """Input model for quality scoring operations.

    This model represents the input for scoring code quality.
    """

    source_path: str = Field(
        ...,
        description="Path to the source file being scored",
    )
    content: str = Field(
        ...,
        description="Source code content to score",
    )
    language: str = Field(
        default="python",
        description="Programming language of the content",
    )
    project_name: Optional[str] = Field(
        default=None,
        description="Name of the project for context",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelQualityScoringInput"]
