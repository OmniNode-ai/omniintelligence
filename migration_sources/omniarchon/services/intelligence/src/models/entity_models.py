"""
Pydantic models for Archon Intelligence Service

Data models for entity extraction, storage, and API communication.
Based on omnibase_3 patterns adapted for Archon knowledge graph.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class EntityType(str, Enum):
    """Knowledge entity types supported by the intelligence service"""

    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"
    MODULE = "MODULE"
    INTERFACE = "INTERFACE"
    API_ENDPOINT = "API_ENDPOINT"
    SERVICE = "SERVICE"
    COMPONENT = "COMPONENT"
    CONCEPT = "CONCEPT"
    DOCUMENT = "DOCUMENT"
    CODE_EXAMPLE = "CODE_EXAMPLE"
    PATTERN = "PATTERN"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    CONFIG_SETTING = "CONFIG_SETTING"


class RelationshipType(str, Enum):
    """Relationship types between entities"""

    CONTAINS = "CONTAINS"
    REFERENCES = "REFERENCES"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    CALLS = "CALLS"
    DEPENDS_ON = "DEPENDS_ON"
    RELATES_TO = "RELATES_TO"
    MENTIONS = "MENTIONS"
    DOCUMENTED_IN = "DOCUMENTED_IN"
    EXAMPLE_OF = "EXAMPLE_OF"
    PART_OF = "PART_OF"
    SIMILAR_TO = "SIMILAR_TO"
    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    INHERITS = "INHERITS"


class EntityMetadata(BaseModel):
    """Metadata associated with extracted entities"""

    file_hash: Optional[str] = None
    extraction_method: str = Field(default="base_extraction")
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    documentation_refs: List[str] = Field(default_factory=list)
    validation_status: str = Field(default="unvalidated")
    review_status: str = Field(default="unreviewed")
    complexity_score: Optional[float] = None
    maintainability_score: Optional[float] = None
    dependencies: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeEntity(BaseModel):
    """Core knowledge entity model"""

    entity_id: str = Field(..., description="Unique identifier for the entity")
    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    description: str = Field(..., description="Entity description")
    source_path: str = Field(..., description="Source file or document path")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: EntityMetadata = Field(default_factory=EntityMetadata)
    source_line_number: Optional[int] = None
    embedding: Optional[List[float]] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeRelationship(BaseModel):
    """Relationship between knowledge entities"""

    relationship_id: str = Field(
        ..., description="Unique identifier for the relationship"
    )
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# API Request Models


class DocumentRequest(BaseModel):
    """Request model for document entity extraction"""

    content: str = Field(..., description="Document content to analyze")
    source_path: str = Field(..., description="Source document path")
    metadata: Optional[Dict[str, Any]] = None
    store_entities: bool = Field(
        default=True, description="Whether to store entities in graph"
    )
    extract_relationships: bool = Field(
        default=True, description="Whether to extract relationships"
    )
    trigger_freshness_analysis: bool = Field(
        default=True, description="Whether to trigger automatic freshness analysis"
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional metadata field to prevent None access errors.

        Expected schema (when present):
        - metadata: {"project_id": str, "user_id": str, "tags": list[str], ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"metadata must be a dict or None, got {type(v).__name__}")
        return v


class CodeRequest(BaseModel):
    """Request model for code entity extraction"""

    content: str = Field(..., description="Code content to analyze")
    source_path: str = Field(..., description="Source file path")
    language: Optional[str] = Field(default=None, description="Programming language")
    metadata: Optional[Dict[str, Any]] = None
    store_entities: bool = Field(
        default=True, description="Whether to store entities in graph"
    )
    extract_relationships: bool = Field(
        default=True, description="Whether to extract relationships"
    )
    trigger_freshness_analysis: bool = Field(
        default=True, description="Whether to trigger automatic freshness analysis"
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional metadata field to prevent None access errors.

        Expected schema (when present):
        - metadata: {"project_id": str, "framework": str, "version": str, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"metadata must be a dict or None, got {type(v).__name__}")
        return v


class EntitySearchRequest(BaseModel):
    """Request model for entity search"""

    query: str = Field(..., description="Search query")
    entity_type: Optional[EntityType] = None
    source_path_filter: Optional[str] = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)
    include_relationships: bool = Field(default=False)


# API Response Models


class ConfidenceStats(BaseModel):
    """Statistics about confidence scores"""

    mean: float = Field(default=0.0)
    min: float = Field(default=0.0)
    max: float = Field(default=0.0)
    std: Optional[float] = None


class EntityExtractionResult(BaseModel):
    """Result of entity extraction operation"""

    entities: List[KnowledgeEntity] = Field(default_factory=list)
    relationships: List[KnowledgeRelationship] = Field(default_factory=list)
    total_count: int = Field(default=0)
    processing_time_ms: float = Field(default=0.0)
    confidence_stats: ConfidenceStats = Field(default_factory=ConfidenceStats)
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)


class EntitySearchResult(BaseModel):
    """Result of entity search operation"""

    entities: List[KnowledgeEntity] = Field(default_factory=list)
    total_count: int = Field(default=0)
    query_time_ms: float = Field(default=0.0)
    has_more: bool = Field(default=False)


class RelationshipSearchResult(BaseModel):
    """Result of relationship search operation"""

    relationships: List[KnowledgeRelationship] = Field(default_factory=list)
    related_entities: List[KnowledgeEntity] = Field(default_factory=list)
    total_count: int = Field(default=0)
    query_time_ms: float = Field(default=0.0)


class HealthStatus(BaseModel):
    """Health status of the intelligence service"""

    status: str = Field(..., description="Overall service status")
    memgraph_connected: bool = Field(default=False)
    ollama_connected: bool = Field(default=False)
    freshness_database_connected: bool = Field(default=False)
    service_version: str = Field(default="1.0.0")
    uptime_seconds: Optional[float] = None
    error: Optional[str] = None
    last_check: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Quality Scoring Models


class QualityScore(BaseModel):
    """Quality score for extracted entities and code"""

    overall_score: float = Field(..., ge=0.0, le=1.0)
    temporal_relevance: float = Field(..., ge=0.0, le=1.0)
    complexity_score: Optional[float] = None
    maintainability_score: Optional[float] = None
    documentation_score: Optional[float] = None
    test_coverage_score: Optional[float] = None
    factors: Dict[str, float] = Field(default_factory=dict)
    reasoning: Optional[str] = None


class PatternMatch(BaseModel):
    """Detected pattern in code or documentation"""

    pattern_name: str = Field(..., description="Name of detected pattern")
    pattern_type: str = Field(..., description="Type/category of pattern")
    confidence: float = Field(..., ge=0.0, le=1.0)
    description: str = Field(..., description="Pattern description")
    location: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    recommendation: Optional[str] = None

    @field_validator("location", mode="before")
    @classmethod
    def validate_location(cls, v: Any) -> Optional[Dict[str, Any]]:
        """
        Validate optional location field to prevent None access errors.

        Expected schema (when present):
        - location: {"file": str, "line": int, "column": int, "end_line": int, ...}
        """
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError(f"location must be a dict or None, got {type(v).__name__}")
        return v
