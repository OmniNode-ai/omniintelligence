"""Output model for Semantic Analysis Compute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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
        description="Similarity scores to known patterns (0.0 to 1.0)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the analysis",
    )

    @field_validator("similarity_scores")
    @classmethod
    def validate_similarity_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all similarity scores are within 0.0 to 1.0 range."""
        for pattern_name, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Similarity score for '{pattern_name}' must be between 0.0 and 1.0, "
                    f"got {score}"
                )
        return v

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSemanticAnalysisOutput"]
