"""Input model for Semantic Analysis Compute."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class SemanticAnalysisContextDict(TypedDict, total=False):
    """Typed structure for semantic analysis context.

    Provides stronger typing for context fields used in semantic analysis.
    With total=False, all fields are optional.
    """

    # Source tracking
    source_path: str
    source_language: str
    source_framework: str

    # Analysis parameters
    analysis_depth: str  # e.g., "shallow", "deep"
    similarity_threshold: float
    max_similar_patterns: int

    # Codebase context
    project_name: str
    repository_name: str
    module_name: str
    class_name: str
    function_name: str

    # Request metadata
    correlation_id: str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    request_id: str
    timestamp_utc: str


class ModelSemanticAnalysisInput(BaseModel):
    """Input model for semantic analysis operations.

    This model represents the input for semantic code analysis.
    """

    code_snippet: str = Field(
        ...,
        min_length=1,
        description="Code snippet to analyze semantically",
    )
    context: SemanticAnalysisContextDict = Field(
        default_factory=lambda: SemanticAnalysisContextDict(),
        description="Typed context for semantic analysis. Uses SemanticAnalysisContextDict "
        "with total=False, allowing any subset of typed fields.",
    )
    include_embeddings: bool = Field(
        default=True,
        description="Whether to generate embeddings",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSemanticAnalysisInput", "SemanticAnalysisContextDict"]
