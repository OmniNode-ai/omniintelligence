"""Output model for Semantic Analysis Compute."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field, field_validator

from omniintelligence.nodes.node_semantic_analysis_compute.models.model_semantic_entity import (
    ModelSemanticEntity,
)
from omniintelligence.nodes.node_semantic_analysis_compute.models.model_semantic_relation import (
    ModelSemanticRelation,
)


class SemanticFeaturesDict(TypedDict, total=False):
    """Typed structure for extracted semantic features.

    Contains the semantic features extracted from code analysis.
    With total=False, all fields are optional.
    """

    # Code structure features
    function_count: int
    class_count: int
    import_count: int
    line_count: int
    complexity_score: float

    # Semantic features
    primary_language: str
    detected_frameworks: list[str]
    detected_patterns: list[str]
    code_purpose: str

    # Entity features
    entity_names: list[str]
    relationship_count: int

    # Quality indicators
    documentation_ratio: float
    test_coverage_indicator: float


class SemanticAnalysisMetadataDict(TypedDict, total=False):
    """Typed structure for semantic analysis metadata.

    Contains information about the analysis operation.
    With total=False, all fields are optional.
    """

    # Operation status (used by stubs and real implementations)
    status: str
    message: str
    tracking_url: str

    # Processing info
    processing_time_ms: float
    algorithm_version: str
    model_name: str

    # Input statistics
    input_length: int
    input_line_count: int
    input_token_count: int

    # Output statistics
    features_extracted: int
    embedding_dimension: int

    # Request context
    correlation_id: str  # Expected format: UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    timestamp_utc: str


class ModelSemanticAnalysisOutput(BaseModel):
    """Output model for semantic analysis operations.

    This model represents the result of semantic code analysis.
    """

    success: bool = Field(
        ...,
        description="Whether semantic analysis succeeded",
    )
    semantic_features: SemanticFeaturesDict = Field(
        default_factory=lambda: SemanticFeaturesDict(),
        description="Typed semantic features extracted from code. Uses SemanticFeaturesDict "
        "with total=False, allowing any subset of typed fields.",
    )
    embeddings: list[float] = Field(
        default_factory=list,
        description="Generated embeddings for the code",
    )
    similarity_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Similarity scores to known patterns (0.0 to 1.0)",
    )
    metadata: SemanticAnalysisMetadataDict | None = Field(
        default=None,
        description="Typed metadata about the analysis. Uses SemanticAnalysisMetadataDict "
        "with total=False, allowing any subset of typed fields.",
    )

    # AST-based semantic analysis fields
    parse_ok: bool = Field(
        default=True,
        description="Whether the AST parsing completed successfully",
    )
    entities: list[ModelSemanticEntity] = Field(
        default_factory=list,
        description="Semantic entities extracted from the code via AST analysis",
    )
    relations: list[ModelSemanticRelation] = Field(
        default_factory=list,
        description="Semantic relations between entities in the code graph",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during analysis",
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


__all__ = [
    "ModelSemanticAnalysisOutput",
    "SemanticAnalysisMetadataDict",
    "SemanticFeaturesDict",
]
