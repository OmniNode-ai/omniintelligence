"""Input model for Semantic Analysis Compute."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelSemanticAnalysisInput(BaseModel):
    """Input model for semantic analysis operations.

    This model represents the input for semantic code analysis.
    """

    code_snippet: str = Field(
        ...,
        description="Code snippet to analyze semantically",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for semantic analysis",
    )
    include_embeddings: bool = Field(
        default=True,
        description="Whether to generate embeddings",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSemanticAnalysisInput"]
