"""
Enhanced Search Models with Unified Entity Types

Updated version of search models that uses the shared EntityType system
while maintaining backwards compatibility with existing search operations.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared_models"))

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from base_models import ServiceHealth
from entity_types import EntityType as UnifiedEntityType
from entity_types import (
    EntityTypeMapper,
    SearchEntityType,
    normalize_entity_type,
)
from pydantic import BaseModel, Field, validator


class SearchMode(str, Enum):
    """Search mode options"""

    SEMANTIC = "semantic"  # Vector similarity search
    STRUCTURAL = "structural"  # Graph traversal search
    HYBRID = "hybrid"  # Combined semantic + structural
    RELATIONAL = "relational"  # Traditional PostgreSQL search


class SearchRequest(BaseModel):
    """Enhanced search request model with unified entity types"""

    query: str = Field(..., description="Search query text")
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="Search mode")
    entity_types: Optional[List[UnifiedEntityType]] = Field(
        default=None, description="Filter by entity types"
    )
    source_ids: Optional[List[str]] = Field(
        default=None, description="Filter by source IDs"
    )
    project_ids: Optional[List[str]] = Field(
        default=None, description="Filter by project IDs"
    )

    # Semantic search parameters
    semantic_threshold: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Minimum semantic similarity"
    )
    max_semantic_results: int = Field(
        default=50, ge=1, le=200, description="Max semantic search results"
    )

    # Graph traversal parameters
    max_graph_depth: int = Field(
        default=3, ge=1, le=5, description="Maximum graph traversal depth"
    )
    relationship_types: Optional[List[str]] = Field(
        default=None, description="Filter by relationship types"
    )

    # Result parameters
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum results to return"
    )
    offset: int = Field(default=0, ge=0, description="Result offset for pagination")
    include_content: bool = Field(
        default=True, description="Include full content in results"
    )
    include_relationships: bool = Field(
        default=True, description="Include entity relationships"
    )

    @validator("entity_types", pre=True)
    def normalize_entity_types(cls, v):
        """Normalize entity types from various formats."""
        if v is None:
            return v

        normalized_types = []
        for entity_type in v:
            try:
                normalized_types.append(normalize_entity_type(entity_type))
            except ValueError as e:
                # Log warning but continue with other types
                print(f"Warning: Could not normalize entity type '{entity_type}': {e}")

        return normalized_types if normalized_types else None

    def to_legacy_search_types(self) -> Optional[List[SearchEntityType]]:
        """Convert unified entity types to legacy search types for backwards compatibility."""
        if not self.entity_types:
            return None

        legacy_types = []
        for unified_type in self.entity_types:
            legacy_type = EntityTypeMapper.to_search_type(unified_type)
            if legacy_type not in legacy_types:
                legacy_types.append(legacy_type)

        return legacy_types


class SearchResult(BaseModel):
    """Individual search result with unified entity support"""

    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: UnifiedEntityType = Field(..., description="Unified entity type")
    title: str = Field(..., description="Result title")
    content: Optional[str] = Field(default=None, description="Result content")
    url: Optional[str] = Field(default=None, description="Source URL if applicable")

    # Scoring and ranking
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall relevance score"
    )
    semantic_score: Optional[float] = Field(
        default=None, description="Semantic similarity score"
    )
    structural_score: Optional[float] = Field(
        default=None, description="Structural relevance score"
    )

    # Metadata
    source_id: Optional[str] = Field(default=None, description="Source identifier")
    project_id: Optional[str] = Field(default=None, description="Project identifier")
    created_at: Optional[datetime] = Field(
        default=None, description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Last update timestamp"
    )

    # Relationships (if requested)
    relationships: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Related entities"
    )
    path_to_query: Optional[List[str]] = Field(
        default=None, description="Path from query to result in graph"
    )

    @validator("entity_type", pre=True)
    def normalize_entity_type(cls, v):
        """Normalize entity type from various formats."""
        return normalize_entity_type(v)

    def to_legacy_search_type(self) -> SearchEntityType:
        """Get the legacy search type for this result."""
        return EntityTypeMapper.to_search_type(self.entity_type)


class SearchResponse(BaseModel):
    """Enhanced search response with unified types"""

    query: str = Field(..., description="Original search query")
    mode: SearchMode = Field(..., description="Search mode used")
    total_results: int = Field(..., description="Total number of results found")
    returned_results: int = Field(..., description="Number of results in this response")

    results: List[SearchResult] = Field(
        default_factory=list, description="Search results"
    )

    # Search statistics
    search_time_ms: float = Field(..., description="Total search time in milliseconds")
    semantic_search_time_ms: Optional[float] = Field(
        default=None, description="Semantic search time"
    )
    graph_search_time_ms: Optional[float] = Field(
        default=None, description="Graph search time"
    )
    relational_search_time_ms: Optional[float] = Field(
        default=None, description="Relational search time"
    )

    # Facets and aggregations (using unified types)
    entity_type_counts: Dict[str, int] = Field(
        default_factory=dict, description="Results by unified entity type"
    )
    source_counts: Dict[str, int] = Field(
        default_factory=dict, description="Results by source"
    )

    # Pagination
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(default=20, description="Results per page")
    has_more: bool = Field(default=False, description="More results available")

    def get_legacy_entity_type_counts(self) -> Dict[str, int]:
        """Get entity type counts using legacy search types for backwards compatibility."""
        legacy_counts = {}

        for result in self.results:
            legacy_type = result.to_legacy_search_type()
            legacy_key = legacy_type.value
            legacy_counts[legacy_key] = legacy_counts.get(legacy_key, 0) + 1

        return legacy_counts


class RelationshipSearchRequest(BaseModel):
    """Request for finding entity relationships with unified types"""

    entity_id: str = Field(..., description="Starting entity ID")
    target_entity_ids: Optional[List[str]] = Field(
        default=None, description="Target entity IDs"
    )
    relationship_types: Optional[List[str]] = Field(
        default=None, description="Relationship type filter"
    )
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum search depth")
    include_paths: bool = Field(
        default=True, description="Include paths between entities"
    )

    # Entity type filtering
    entity_type_filter: Optional[List[UnifiedEntityType]] = Field(
        default=None, description="Filter by entity types"
    )

    @validator("entity_type_filter", pre=True)
    def normalize_entity_type_filter(cls, v):
        """Normalize entity type filter."""
        if v is None:
            return v

        normalized_types = []
        for entity_type in v:
            try:
                normalized_types.append(normalize_entity_type(entity_type))
            except ValueError as e:
                print(
                    f"Warning: Could not normalize entity type filter '{entity_type}': {e}"
                )

        return normalized_types if normalized_types else None


class EntityRelationship(BaseModel):
    """Entity relationship model with unified types"""

    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Type of relationship")
    relationship_properties: Dict[str, Any] = Field(
        default_factory=dict, description="Relationship metadata"
    )
    confidence_score: Optional[float] = Field(
        default=None, description="Relationship confidence"
    )

    # Entity type information for filtering
    source_entity_type: Optional[UnifiedEntityType] = Field(
        default=None, description="Source entity type"
    )
    target_entity_type: Optional[UnifiedEntityType] = Field(
        default=None, description="Target entity type"
    )

    @validator("source_entity_type", "target_entity_type", pre=True)
    def normalize_entity_types(cls, v):
        """Normalize entity types."""
        if v is None:
            return v
        return normalize_entity_type(v)


class RelationshipSearchResponse(BaseModel):
    """Response for relationship search with unified types"""

    source_entity_id: str = Field(..., description="Starting entity ID")
    relationships: List[EntityRelationship] = Field(
        default_factory=list, description="Found relationships"
    )
    paths: Optional[List[List[str]]] = Field(
        default=None, description="Paths between entities"
    )
    search_time_ms: float = Field(..., description="Search time in milliseconds")

    # Type statistics
    entity_type_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Entity types in results"
    )
    relationship_type_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Relationship types"
    )


class SearchAnalyticsRequest(BaseModel):
    """Request for search analytics with unified types"""

    time_period_days: int = Field(
        default=30, ge=1, le=365, description="Analysis time period"
    )
    entity_types: Optional[List[UnifiedEntityType]] = Field(
        default=None, description="Filter by entity types"
    )

    @validator("entity_types", pre=True)
    def normalize_entity_types(cls, v):
        """Normalize entity types."""
        if v is None:
            return v

        normalized_types = []
        for entity_type in v:
            try:
                normalized_types.append(normalize_entity_type(entity_type))
            except ValueError as e:
                print(f"Warning: Could not normalize entity type '{entity_type}': {e}")

        return normalized_types if normalized_types else None


class SearchAnalytics(BaseModel):
    """Search analytics response with unified types"""

    total_searches: int = Field(..., description="Total number of searches")
    popular_queries: List[Dict[str, Any]] = Field(
        default_factory=list, description="Most popular queries"
    )
    search_modes_usage: Dict[str, int] = Field(
        default_factory=dict, description="Usage by search mode"
    )
    average_response_time_ms: float = Field(..., description="Average response time")
    entity_type_preferences: Dict[str, int] = Field(
        default_factory=dict, description="Entity type popularity using unified types"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Analytics timestamp"
    )


class EnhancedHealthStatus(ServiceHealth):
    """Enhanced health status for search service"""

    vector_index_ready: bool = Field(
        default=False, description="Vector search index status"
    )
    graph_database_ready: bool = Field(
        default=False, description="Graph database status"
    )

    # Index statistics
    total_indexed_entities: Optional[int] = Field(
        default=None, description="Total entities in search index"
    )
    entity_type_breakdown: Dict[str, int] = Field(
        default_factory=dict, description="Entities by unified type"
    )
    index_freshness_hours: Optional[float] = Field(
        default=None, description="Hours since last full index"
    )

    # Performance metrics
    average_search_time_ms: Optional[float] = Field(
        default=None, description="Average search response time"
    )
    cache_hit_rate_percent: Optional[float] = Field(
        default=None, description="Search result cache hit rate"
    )


# Utility functions for backwards compatibility


def convert_legacy_entity_types(legacy_types: List[str]) -> List[UnifiedEntityType]:
    """Convert legacy entity type strings to unified types."""
    unified_types = []

    for legacy_type in legacy_types:
        try:
            unified_type = normalize_entity_type(legacy_type)
            if unified_type not in unified_types:
                unified_types.append(unified_type)
        except ValueError:
            # Skip invalid types with a warning
            print(f"Warning: Could not convert legacy entity type '{legacy_type}'")

    return unified_types


def create_backwards_compatible_search_request(
    query: str,
    legacy_entity_types: Optional[List[str]] = None,
    mode: str = "hybrid",
    **kwargs,
) -> SearchRequest:
    """Create a search request from legacy parameters."""
    unified_entity_types = None
    if legacy_entity_types:
        unified_entity_types = convert_legacy_entity_types(legacy_entity_types)

    return SearchRequest(
        query=query, mode=SearchMode(mode), entity_types=unified_entity_types, **kwargs
    )


def extract_legacy_response_data(response: SearchResponse) -> Dict[str, Any]:
    """Extract response data in legacy format for backwards compatibility."""
    return {
        "query": response.query,
        "mode": response.mode.value,
        "total_results": response.total_results,
        "results": [
            {
                "entity_id": result.entity_id,
                "entity_type": result.to_legacy_search_type().value,  # Legacy format
                "title": result.title,
                "content": result.content,
                "url": result.url,
                "relevance_score": result.relevance_score,
                "semantic_score": result.semantic_score,
                "source_id": result.source_id,
                "created_at": result.created_at,
                "relationships": result.relationships,
            }
            for result in response.results
        ],
        "search_time_ms": response.search_time_ms,
        "entity_type_counts": response.get_legacy_entity_type_counts(),  # Legacy format
        "has_more": response.has_more,
    }
