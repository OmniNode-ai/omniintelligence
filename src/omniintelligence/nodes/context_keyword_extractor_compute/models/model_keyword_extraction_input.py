"""Input model for Context Keyword Extractor Compute."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ModelKeywordExtractionInput(BaseModel):
    """Input model for keyword extraction operations.

    This model represents the input for extracting contextual keywords.
    """

    content: str = Field(
        ...,
        description="Content to extract keywords from",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
    )
    extraction_strategy: str = Field(
        default="tfidf",
        description="Strategy for keyword extraction (tfidf, rake, textrank)",
    )
    max_keywords: int = Field(
        default=20,
        description="Maximum number of keywords to extract",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelKeywordExtractionInput"]
