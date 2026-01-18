"""Output model for Semantic Analysis Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelSemanticAnalysisOutput(BaseModel):
    """Output model for semantic analysis operations.

    This model represents the result of semantic code analysis.
    """

    success: bool = Field(
        ...,
        description="Whether semantic analysis succeeded",
    )
    semantic_features: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted semantic features",
    )
    embeddings: list[float] = Field(
        default_factory=list,
        description="Generated embeddings for the code",
    )
    similarity_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Similarity scores to known patterns",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the analysis",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSemanticAnalysisOutput"]
