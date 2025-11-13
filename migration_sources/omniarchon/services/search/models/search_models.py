"""
Search Models for Enhanced Search Service

Data models for search requests, responses, and result ranking.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# Import unified EntityType from shared models
try:
    import os
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))
    from shared.models.entity_types import EntityType, normalize_entity_type
except ImportError:
    # Fallback to local definition if shared models not available
    class EntityType(str, Enum):
        """Entity types for search filtering (fallback)"""

        DOCUMENT = "document"
        SOURCE = "source"
        PROJECT = "project"
        PAGE = "page"
        CODE_EXAMPLE = "code_example"
        FUNCTION = "function"
        CLASS = "class"
        VARIABLE = "variable"
        ENTITY = "entity"  # Extracted knowledge entities

    def normalize_entity_type(entity_type):
        """Fallback normalization function"""
        return EntityType(entity_type.lower())


class SearchMode(str, Enum):
    """Search mode options"""

    SEMANTIC = "semantic"  # Vector similarity search
    STRUCTURAL = "structural"  # Graph traversal search
    HYBRID = "hybrid"  # Combined semantic + structural
    RELATIONAL = "relational"  # Traditional PostgreSQL search


class SearchRequest(BaseModel):
    """Enhanced search request model"""

    query: str = Field(..., description="Search query text")
    mode: SearchMode = Field(default=SearchMode.HYBRID, description="Search mode")
    entity_types: Optional[List[EntityType]] = Field(
        default=None, description="Filter by entity types"
    )
    source_ids: Optional[List[str]] = Field(
        default=None, description="Filter by source IDs"
    )
    project_ids: Optional[List[str]] = Field(
        default=None, description="Filter by project IDs"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata filters (e.g., language, file_type, project_name, quality_score ranges)",
    )
    path_pattern: Optional[str] = Field(
        default=None,
        description="Glob pattern for filtering by file path (e.g., 'services/**/*.py', '*.py', 'tests/**/test_*.py')",
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


class SearchResult(BaseModel):
    """Individual search result"""

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )

    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: EntityType = Field(..., description="Type of entity")
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

    # Quality and ONEX Compliance Fields
    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality assessment score (0.0-1.0)"
    )
    onex_compliance: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="ONEX compliance score (0.0-1.0)"
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type (effect, compute, reducer, orchestrator)",
    )
    concepts: Optional[List[str]] = Field(
        default=None, description="Extracted concepts and themes"
    )
    themes: Optional[List[str]] = Field(default=None, description="Thematic categories")
    relative_path: Optional[str] = Field(
        default=None, description="Relative path within project"
    )
    project_name: Optional[str] = Field(default=None, description="Project name")
    content_hash: Optional[str] = Field(
        default=None, description="BLAKE3 content hash for deduplication"
    )

    # Relationships (if requested)
    relationships: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Related entities"
    )
    path_to_query: Optional[List[str]] = Field(
        default=None, description="Path from query to result in graph"
    )

    # Pattern intelligence fields
    pattern_type: Optional[str] = Field(
        default=None,
        description="Pattern classification: 'code' | 'execution' | 'document'",
    )
    pattern_name: Optional[str] = Field(
        default=None, description="Canonical pattern name or identifier"
    )
    pattern_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Pattern detection confidence score"
    )
    node_types: Optional[List[str]] = Field(
        default=None, description="ONEX node types associated with this pattern"
    )
    use_cases: Optional[List[str]] = Field(
        default=None, description="Pattern use cases and applications"
    )
    examples: Optional[List[str]] = Field(
        default=None, description="Pattern usage examples or references"
    )
    file_path: Optional[str] = Field(
        default=None, description="Full file path for code patterns"
    )


class SearchResponse(BaseModel):
    """Enhanced search response"""

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

    # Facets and aggregations
    entity_type_counts: Dict[str, int] = Field(
        default_factory=dict, description="Results by entity type"
    )
    source_counts: Dict[str, int] = Field(
        default_factory=dict, description="Results by source"
    )

    # Pagination
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(default=20, description="Results per page")
    has_more: bool = Field(default=False, description="More results available")


class RelationshipSearchRequest(BaseModel):
    """Request for finding entity relationships"""

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


class EntityRelationship(BaseModel):
    """Entity relationship model"""

    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Type of relationship")
    relationship_properties: Dict[str, Any] = Field(
        default_factory=dict, description="Relationship metadata"
    )
    confidence_score: Optional[float] = Field(
        default=None, description="Relationship confidence"
    )


class RelationshipSearchResponse(BaseModel):
    """Response for relationship search"""

    source_entity_id: str = Field(..., description="Starting entity ID")
    relationships: List[EntityRelationship] = Field(
        default_factory=list, description="Found relationships"
    )
    paths: Optional[List[List[str]]] = Field(
        default=None, description="Paths between entities"
    )
    search_time_ms: float = Field(..., description="Search time in milliseconds")


class SearchAnalyticsRequest(BaseModel):
    """Request for search analytics"""

    time_period_days: int = Field(
        default=30, ge=1, le=365, description="Analysis time period"
    )
    entity_types: Optional[List[EntityType]] = Field(
        default=None, description="Filter by entity types"
    )


class SearchAnalytics(BaseModel):
    """Search analytics response"""

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )

    total_searches: int = Field(..., description="Total number of searches")
    popular_queries: List[Dict[str, Any]] = Field(
        default_factory=list, description="Most popular queries"
    )
    search_modes_usage: Dict[str, int] = Field(
        default_factory=dict, description="Usage by search mode"
    )
    average_response_time_ms: float = Field(..., description="Average response time")
    entity_type_preferences: Dict[str, int] = Field(
        default_factory=dict, description="Entity type popularity"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Analytics timestamp"
    )


class ArchonDocument(BaseModel):
    """
    Document model for Archon vector storage with pattern intelligence support.

    Represents documents indexed in Qdrant with full metadata including
    code patterns, execution patterns, and quality metrics.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )

    # Core document fields
    entity_id: str = Field(..., description="Unique document identifier")
    entity_type: str = Field(default="document", description="Entity type")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    url: Optional[str] = Field(default=None, description="Source URL if applicable")
    source_id: Optional[str] = Field(default=None, description="Source identifier")
    project_id: Optional[str] = Field(default=None, description="Project identifier")
    created_at: Optional[datetime] = Field(
        default=None, description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Last update timestamp"
    )

    # Quality and ONEX fields
    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality assessment score (0.0-1.0)"
    )
    onex_compliance: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="ONEX compliance score (0.0-1.0)"
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type (effect, compute, reducer, orchestrator)",
    )
    concepts: Optional[List[str]] = Field(
        default=None, description="Extracted concepts and themes"
    )
    themes: Optional[List[str]] = Field(default=None, description="Thematic categories")
    relative_path: Optional[str] = Field(
        default=None, description="Relative path within project"
    )
    project_name: Optional[str] = Field(default=None, description="Project name")
    content_hash: Optional[str] = Field(
        default=None, description="BLAKE3 content hash for deduplication"
    )

    # Pattern intelligence fields
    pattern_type: Optional[str] = Field(
        default=None,
        description="Pattern classification: 'code' | 'execution' | 'document'",
    )
    pattern_name: Optional[str] = Field(
        default=None, description="Canonical pattern name or identifier"
    )
    pattern_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Pattern detection confidence score"
    )
    node_types: Optional[List[str]] = Field(
        default=None, description="ONEX node types associated with this pattern"
    )
    use_cases: Optional[List[str]] = Field(
        default=None, description="Pattern use cases and applications"
    )
    examples: Optional[List[str]] = Field(
        default=None, description="Pattern usage examples or references"
    )
    file_path: Optional[str] = Field(
        default=None, description="Full file path for code patterns"
    )


class HealthStatus(BaseModel):
    """Search service health status"""

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )

    status: str = Field(..., description="Overall service status")
    memgraph_connected: bool = Field(default=False)
    intelligence_connected: bool = Field(default=False)
    bridge_connected: bool = Field(default=False)
    embedding_service_connected: bool = Field(default=False)
    vector_index_ready: bool = Field(default=False)
    service_version: str = Field(default="1.0.0")
    uptime_seconds: Optional[float] = None
    error: Optional[str] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)
