"""Output model for Context Keyword Extractor Compute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelKeywordExtractionOutput(BaseModel):
    """Output model for keyword extraction operations.

    This model represents the result of extracting contextual keywords.
    """

    success: bool = Field(
        ...,
        description="Whether keyword extraction succeeded",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="List of extracted keywords",
    )
    keyword_contexts: dict[str, Any] = Field(
        default_factory=dict,
        description="Context information for each keyword",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the extraction",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelKeywordExtractionOutput"]
