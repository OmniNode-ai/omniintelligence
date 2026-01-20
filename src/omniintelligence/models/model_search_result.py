"""Typed search result models for OmniIntelligence.

These models provide type-safe structures for search results from
vector databases (Qdrant), semantic search, and pattern matching.

Usage:
    Instead of using untyped `list[dict[str, Any]]` for search results,
    use the typed models:

    # Before (untyped)
    results: list[dict[str, Any]] = [{"id": "r1", "score": 0.95, ...}]

    # After (typed)
    results: list[ModelSearchResult] = [ModelSearchResult(id="r1", score=0.95, ...)]
"""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class SearchResultMetadataDict(TypedDict, total=False):
    """Typed structure for search result metadata.

    Provides type-safe fields for search result metadata.
    """

    # Source information
    file_path: str
    source_type: str
    language: str

    # Entity classification
    entity_type: str
    entity_id: str
    category: str

    # Quality metrics
    quality_score: float
    confidence: float

    # Timestamps
    created_at: str
    indexed_at: str


class PatternMatchMetadataDict(TypedDict, total=False):
    """Typed structure for pattern match metadata.

    Provides type-safe fields for pattern match metadata.
    """

    # Pattern classification
    pattern_category: str
    pattern_subcategory: str
    is_anti_pattern: bool

    # Match context
    function_name: str
    class_name: str
    module_name: str

    # Quality info
    severity: str  # "info", "warning", "error"
    recommendation: str

    # Detection info
    detection_method: str
    confidence: float


class ModelSearchResult(BaseModel):
    """Typed search result model for vector and semantic search.

    This model provides type-safe search result representation for use
    with Qdrant vector search, semantic code search, and pattern matching.

    All fields use strong typing without dict[str, Any].

    Example:
        >>> result = ModelSearchResult(
        ...     id="doc_abc123",
        ...     score=0.95,
        ...     content="def calculate_total(): ...",
        ...     metadata={"file_path": "src/utils.py", "entity_type": "FUNCTION"},
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": "doc_abc123",
                "score": 0.95,
                "content": "def calculate_total(): ...",
                "metadata": {"file_path": "src/utils.py", "entity_type": "FUNCTION"},
            }
        },
    )

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the search result",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0 to 1.0, higher is more relevant)",
    )
    content: str | None = Field(
        default=None,
        description="Content snippet or full content of the matched document",
    )
    metadata: SearchResultMetadataDict = Field(
        default_factory=lambda: SearchResultMetadataDict(),
        description="Additional metadata about the search result with typed fields",
    )
    vector_id: str | None = Field(
        default=None,
        description="Vector ID in the vector database (if applicable)",
    )
    distance: float | None = Field(
        default=None,
        ge=0.0,
        description="Raw distance metric from vector search (lower is closer)",
    )


class ModelPatternMatch(BaseModel):
    """Typed pattern match result for code pattern detection.

    This model provides type-safe representation of detected patterns
    in code analysis and pattern learning operations.

    All fields use strong typing without dict[str, Any].

    Example:
        >>> match = ModelPatternMatch(
        ...     pattern_name="SINGLETON_PATTERN",
        ...     match_score=0.92,
        ...     matched_code="class Singleton: _instance = None ...",
        ...     source_path="src/patterns/singleton.py",
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "pattern_name": "SINGLETON_PATTERN",
                "match_score": 0.92,
                "matched_code": "class Singleton: _instance = None ...",
                "source_path": "src/patterns/singleton.py",
            }
        },
    )

    pattern_name: str = Field(
        ...,
        min_length=1,
        description="Name of the matched pattern",
    )
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the pattern match (0.0 to 1.0)",
    )
    matched_code: str | None = Field(
        default=None,
        description="Code snippet that matched the pattern",
    )
    source_path: str | None = Field(
        default=None,
        min_length=1,
        description="Path to the source file containing the match",
    )
    line_start: int | None = Field(
        default=None,
        ge=1,
        description="Starting line number of the match",
    )
    line_end: int | None = Field(
        default=None,
        ge=1,
        description="Ending line number of the match",
    )
    metadata: PatternMatchMetadataDict = Field(
        default_factory=lambda: PatternMatchMetadataDict(),
        description="Additional metadata about the pattern match with typed fields",
    )


__all__ = [
    "ModelPatternMatch",
    "ModelSearchResult",
    "PatternMatchMetadataDict",
    "SearchResultMetadataDict",
]
