"""
Pydantic models for search service requests and responses.

These models ensure proper serialization/deserialization between the MCP service
and the enhanced search service, eliminating data format mismatches.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, validator

# Import unified EntityType from shared models
try:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../.."))
    from shared.models.entity_types import EntityType, normalize_entity_type
except ImportError:
    # Fallback to local definition if shared models not available
    class EntityType(str, Enum):
        """Available entity types for filtering (fallback)."""

        DOCUMENT = "document"
        PAGE = "page"
        CODE_EXAMPLE = "code_example"
        PROJECT = "project"
        FUNCTION = "function"
        CLASS = "class"
        VARIABLE = "variable"
        SOURCE = "source"
        ENTITY = "entity"

    def normalize_entity_type(entity_type):
        """Fallback normalization function"""
        return EntityType(entity_type.lower())


class SearchMode(str, Enum):
    """Available search modes for enhanced search."""

    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    RELATIONAL = "relational"
    HYBRID = "hybrid"


# === REQUEST MODELS ===


class EnhancedSearchRequest(BaseModel):
    """Request model for enhanced search API."""

    query: str = Field(..., description="Search query text")
    mode: SearchMode = Field(SearchMode.HYBRID, description="Search mode")
    entity_types: Optional[list[EntityType]] = Field(
        None, description="Filter by entity types"
    )
    source_ids: Optional[list[str]] = Field(
        None, description="Filter by specific source IDs"
    )
    limit: int = Field(5, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Results offset for pagination")
    include_content: bool = Field(False, description="Include full content in results")
    include_relationships: bool = Field(
        False, description="Include entity relationships"
    )

    @validator("entity_types", pre=True)
    def validate_entity_types(cls, v):
        """Convert string list to EntityType enums."""
        if v is None:
            return v
        if isinstance(v, str):
            # Handle comma-separated string
            v = [s.strip() for s in v.split(",")]

        # Use normalize_entity_type for better compatibility
        try:
            return [normalize_entity_type(item) for item in v]
        except (ValueError, NameError):
            # Fallback to direct EntityType construction
            return [EntityType(item.lower()) for item in v]


class RAGQueryRequest(BaseModel):
    """Request model for RAG query API."""

    query: str = Field(..., description="Search query")
    source_domain: Optional[str] = Field(None, description="Domain filter")
    match_count: int = Field(5, ge=1, le=50, description="Maximum results")
    use_enhanced_search: Optional[bool] = Field(None, description="Use enhanced search")


class CodeExamplesRequest(BaseModel):
    """Request model for code examples search."""

    query: str = Field(..., description="Code search query")
    source_domain: Optional[str] = Field(None, description="Domain filter")
    match_count: int = Field(5, ge=1, le=50, description="Maximum results")


# === RESPONSE MODELS ===


class SearchResult(BaseModel):
    """Individual search result item."""

    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: str = Field(..., description="Type of entity")
    title: str = Field(..., description="Result title")
    content: Optional[str] = Field(None, description="Content text")
    url: Optional[str] = Field(None, description="Source URL")
    summary: Optional[str] = Field(None, description="Content summary")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    source_id: Optional[str] = Field(None, description="Source identifier")
    similarity: Optional[float] = Field(None, description="Similarity score")
    relevance_score: Optional[float] = Field(None, description="Relevance score")
    rerank_score: Optional[float] = Field(None, description="Rerank score")
    semantic_score: Optional[float] = Field(
        None, description="Semantic similarity score"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp")


class EnhancedSearchResponse(BaseModel):
    """Response model for enhanced search API."""

    query: str = Field(..., description="Original query")
    mode: SearchMode = Field(..., description="Search mode used")
    total_results: int = Field(..., description="Total number of results")
    returned_results: int = Field(..., description="Number of results returned")
    results: list[SearchResult] = Field(
        default_factory=list, description="Search results"
    )
    search_time_ms: float = Field(..., description="Total search time in milliseconds")
    semantic_search_time_ms: Optional[float] = Field(
        None, description="Semantic search time"
    )
    graph_search_time_ms: Optional[float] = Field(None, description="Graph search time")
    relational_search_time_ms: Optional[float] = Field(
        None, description="Relational search time"
    )
    entity_type_counts: dict[str, int] = Field(
        default_factory=dict, description="Entity type breakdown"
    )
    source_counts: dict[str, int] = Field(
        default_factory=dict, description="Source breakdown"
    )
    offset: int = Field(0, description="Results offset")
    limit: int = Field(..., description="Results limit")
    has_more: bool = Field(False, description="Whether more results are available")


class RAGQueryResponse(BaseModel):
    """Response model for RAG query API."""

    success: bool = Field(..., description="Operation success status")
    results: list[SearchResult] = Field(
        default_factory=list, description="Search results"
    )
    reranked: bool = Field(False, description="Whether results were reranked")
    total_results: int = Field(0, description="Total number of results")
    search_mode: Optional[SearchMode] = Field(None, description="Search mode used")
    search_time_ms: Optional[float] = Field(
        None, description="Search time in milliseconds"
    )
    enhanced: bool = Field(False, description="Whether enhanced search was used")
    error: Optional[str] = Field(None, description="Error message if any")


class CodeExamplesResponse(BaseModel):
    """Response model for code examples search."""

    success: bool = Field(..., description="Operation success status")
    results: list[SearchResult] = Field(
        default_factory=list, description="Code examples"
    )
    reranked: bool = Field(False, description="Whether results were reranked")
    error: Optional[str] = Field(None, description="Error message if any")


# === ERROR MODELS ===


class SearchError(BaseModel):
    """Error response model."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = Field(False, description="Always false for errors")
    error: SearchError = Field(..., description="Error information")


# === UTILITY FUNCTIONS ===


def transform_enhanced_to_rag_response(
    enhanced_response: EnhancedSearchResponse,
    reranked: bool = True,
    enhanced: bool = True,
) -> RAGQueryResponse:
    """Transform EnhancedSearchResponse to RAGQueryResponse format."""
    return RAGQueryResponse(
        success=True,
        results=enhanced_response.results,
        reranked=reranked,
        total_results=enhanced_response.total_results,
        search_mode=enhanced_response.mode,
        search_time_ms=enhanced_response.search_time_ms,
        enhanced=enhanced,
        error=None,
    )


def transform_enhanced_to_code_examples_response(
    enhanced_response: EnhancedSearchResponse, reranked: bool = True
) -> CodeExamplesResponse:
    """Transform EnhancedSearchResponse to CodeExamplesResponse format."""
    return CodeExamplesResponse(
        success=True, results=enhanced_response.results, reranked=reranked, error=None
    )


# === VALIDATION HELPERS ===


def validate_search_request(request_data: dict[str, Any]) -> EnhancedSearchRequest:
    """Validate and parse search request data."""
    return EnhancedSearchRequest(**request_data)


def validate_rag_request(request_data: dict[str, Any]) -> RAGQueryRequest:
    """Validate and parse RAG query request data."""
    return RAGQueryRequest(**request_data)


def validate_code_examples_request(request_data: dict[str, Any]) -> CodeExamplesRequest:
    """Validate and parse code examples request data."""
    return CodeExamplesRequest(**request_data)
