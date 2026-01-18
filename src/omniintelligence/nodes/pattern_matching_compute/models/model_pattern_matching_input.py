"""Input model for Pattern Matching Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPatternMatchingInput(BaseModel):
    """Input model for pattern matching operations.

    This model represents the input for matching code patterns.
    """

    code_snippet: str = Field(
        ...,
        min_length=1,
        description="Code snippet to match patterns against",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for pattern matching",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternMatchingInput"]
