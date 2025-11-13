"""
RAG Search Service Response Models

Pydantic models for validating RAG search service responses.

Service: archon-search (port 8055)
Performance: Validation overhead <2ms for typical responses
"""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# NOTE: correlation_id support enabled for tracing
class RAGSearchMetadata(BaseModel):
    """
    Metadata for a RAG search result item.

    Contains source information, quality metrics, and context.
    """

    source: Optional[str] = Field(default=None, description="Source system or service")
    project_id: Optional[str] = Field(default=None, description="Project identifier")
    entity_type: Optional[str] = Field(
        default=None, description="Entity type (document, code, pattern, etc.)"
    )
    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality score (0.0-1.0)"
    )
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class RAGSearchResult(BaseModel):
    """
    Single search result item from RAG service.

    Contains the document content, relevance score, and metadata.

    Example:
        {
            "path": "/path/to/document.md",
            "source_path": "/path/to/document.md",
            "score": 0.92,
            "content": "Document content...",
            "title": "Document Title",
            "metadata": {
                "source": "qdrant",
                "quality_score": 0.85,
                "tags": ["documentation", "api"]
            }
        }
    """

    # Core fields (various services use different field names)
    path: Optional[str] = Field(
        default=None, description="Document path (legacy field)"
    )
    source_path: Optional[str] = Field(default=None, description="Document source path")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0.0-1.0)")
    content: str = Field(..., description="Document content or excerpt")
    title: Optional[str] = Field(default=None, description="Document title")
    metadata: Optional[RAGSearchMetadata] = Field(
        default=None, description="Result metadata"
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> Optional[Dict]:
        """Normalize metadata to dict or None."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        # If metadata is some other type, wrap it
        return {"extra": {"raw": v}}

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Validate and normalize score to 0.0-1.0 range."""
        if v < 0.0:
            return 0.0
        if v > 1.0:
            # Some services return scores > 1.0, normalize
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Score > 1.0 detected: {v}, clamping to 1.0")
            return 1.0
        return v

    def get_path(self) -> str:
        """Get document path (handles both 'path' and 'source_path')."""
        return self.source_path or self.path or "unknown"

    def get_metadata_field(self, key: str, default: Any = None) -> Any:
        """Get metadata field with default fallback."""
        if self.metadata is None:
            return default
        # Try direct field first
        value = getattr(self.metadata, key, None)
        if value is not None:
            return value
        # Try extra dict
        return self.metadata.extra.get(key, default)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_path": "/docs/api/authentication.md",
                "score": 0.92,
                "content": "# Authentication\\n\\nThis document describes...",
                "title": "Authentication Guide",
                "metadata": {
                    "source": "qdrant",
                    "quality_score": 0.85,
                    "tags": ["api", "security"],
                },
            }
        }
    )


class RAGSearchResponse(BaseModel):
    """
    Complete response from RAG search service.

    Contains list of results and optional metadata about the search operation.

    Example:
        {
            "results": [
                {
                    "source_path": "/path/to/doc.md",
                    "score": 0.92,
                    "content": "Document content..."
                }
            ],
            "total_results": 5,
            "query": "authentication",
            "processing_time_ms": 245.3,
            "sources": ["qdrant", "memgraph"],
            "cache_hit": false
        }
    """

    results: List[RAGSearchResult] = Field(
        default_factory=list, description="Search results"
    )
    total_results: Optional[int] = Field(
        default=None, description="Total number of results"
    )
    query: Optional[str] = Field(default=None, description="Original search query")
    processing_time_ms: Optional[float] = Field(
        default=None, description="Processing time in milliseconds"
    )
    sources: List[str] = Field(default_factory=list, description="Data sources queried")
    cache_hit: bool = Field(
        default=False, description="Whether result was served from cache"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional response metadata"
    )

    @field_validator("results", mode="before")
    @classmethod
    def validate_results(cls, v: Any) -> List[Dict]:
        """Normalize results list."""
        if isinstance(v, list):
            return v
        # Handle case where results are nested
        if isinstance(v, dict) and "results" in v:
            return v["results"]
        return []

    @field_validator("total_results", mode="before")
    @classmethod
    def set_total_results(cls, v: Any, info) -> Optional[int]:
        """Set total_results from results length if not provided."""
        if v is not None:
            return v
        # Get results from values if available
        if "results" in info.data:
            return len(info.data["results"])
        return None

    def get_result_count(self) -> int:
        """Get number of results returned."""
        return len(self.results)

    def is_empty(self) -> bool:
        """Check if search returned no results."""
        return len(self.results) == 0

    def get_top_result(self) -> Optional[RAGSearchResult]:
        """Get highest scoring result."""
        if not self.results:
            return None
        return max(self.results, key=lambda r: r.score)

    def get_avg_score(self) -> float:
        """Calculate average result score."""
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "source_path": "/docs/authentication.md",
                        "score": 0.92,
                        "content": "Authentication guide content...",
                        "title": "Authentication",
                    }
                ],
                "total_results": 1,
                "query": "authentication",
                "processing_time_ms": 245.3,
                "sources": ["qdrant"],
                "cache_hit": False,
            }
        }
    )
