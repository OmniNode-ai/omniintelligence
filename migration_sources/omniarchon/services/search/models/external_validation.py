"""
Pydantic Validation Models for External API Responses

Provides validation for responses from:
- Ollama API (embeddings)
- Qdrant API (vector search)
- Memgraph API (graph search)
- Bridge Service API (metadata)
- Intelligence Service API (quality assessment)

All models include:
- Strict validation with proper error messages
- Optional fields with defaults for graceful degradation
- Type coercion where appropriate
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Ollama API Response Models
# ============================================================================


class OllamaEmbeddingResponse(BaseModel):
    """Validation model for Ollama embedding API response"""

    model_config = ConfigDict(extra="allow")

    embedding: List[float] = Field(
        ..., description="Embedding vector", min_length=1, max_length=10000
    )
    model: Optional[str] = Field(None, description="Model used for embedding")
    prompt: Optional[str] = Field(None, description="Original prompt")

    @field_validator("embedding")
    @classmethod
    def validate_embedding_values(cls, v: List[float]) -> List[float]:
        """Ensure all embedding values are valid floats"""
        if not all(
            isinstance(x, (int, float)) and not (x != x) for x in v
        ):  # Check for NaN
            raise ValueError("Embedding contains invalid float values")
        return v


class OllamaHealthResponse(BaseModel):
    """Validation model for Ollama health check response"""

    model_config = ConfigDict(extra="allow")

    status: Optional[str] = Field(None, description="Service status")
    models: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Available models"
    )


# ============================================================================
# Qdrant API Response Models
# ============================================================================


class QdrantPointPayload(BaseModel):
    """Validation model for Qdrant point payload"""

    model_config = ConfigDict(extra="allow")

    entity_id: str = Field(..., description="Entity identifier")
    entity_type: str = Field(..., description="Entity type")
    title: Optional[str] = Field(None, description="Entity title")
    content: Optional[str] = Field(None, description="Entity content")
    url: Optional[str] = Field(None, description="Entity URL")
    source_id: Optional[str] = Field(None, description="Source identifier")
    project_id: Optional[str] = Field(None, description="Project identifier")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality score"
    )


class QdrantScoredPoint(BaseModel):
    """Validation model for Qdrant scored point"""

    model_config = ConfigDict(extra="allow")

    id: Union[str, int] = Field(..., description="Point ID")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    payload: QdrantPointPayload = Field(..., description="Point payload")
    version: Optional[int] = Field(None, description="Point version")


class QdrantSearchResponse(BaseModel):
    """Validation model for Qdrant search response"""

    model_config = ConfigDict(extra="allow")

    result: List[QdrantScoredPoint] = Field(
        default_factory=list, description="Search results"
    )
    status: Optional[str] = Field(None, description="Response status")
    time: Optional[float] = Field(None, ge=0.0, description="Query time in seconds")

    @field_validator("result")
    @classmethod
    def validate_results_not_empty(
        cls, v: List[QdrantScoredPoint]
    ) -> List[QdrantScoredPoint]:
        """Allow empty results but validate structure when present"""
        return v


class QdrantCollectionInfo(BaseModel):
    """Validation model for Qdrant collection info"""

    model_config = ConfigDict(extra="allow")

    status: str = Field(..., description="Collection status")
    vectors_count: Optional[int] = Field(None, ge=0, description="Number of vectors")
    points_count: Optional[int] = Field(None, ge=0, description="Number of points")
    indexed_vectors_count: Optional[int] = Field(
        None, ge=0, description="Number of indexed vectors"
    )
    segments_count: Optional[int] = Field(None, ge=0, description="Number of segments")


# ============================================================================
# Memgraph API Response Models
# ============================================================================


class MemgraphNodeProperties(BaseModel):
    """Validation model for Memgraph node properties"""

    model_config = ConfigDict(extra="allow")

    entity_id: Optional[str] = Field(None, description="Entity identifier")
    title: Optional[str] = Field(None, description="Node title")
    name: Optional[str] = Field(None, description="Node name")
    content: Optional[str] = Field(None, description="Node content")
    url: Optional[str] = Field(None, description="Node URL")
    source_id: Optional[str] = Field(None, description="Source identifier")
    project_id: Optional[str] = Field(None, description="Project identifier")


class MemgraphRelationshipProperties(BaseModel):
    """Validation model for Memgraph relationship properties"""

    model_config = ConfigDict(extra="allow")

    type: Optional[str] = Field(None, description="Relationship type")
    confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score"
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class MemgraphNode(BaseModel):
    """Validation model for Memgraph node"""

    model_config = ConfigDict(extra="allow")

    identity: Optional[int] = Field(None, description="Node ID")
    labels: List[str] = Field(default_factory=list, description="Node labels")
    properties: MemgraphNodeProperties = Field(
        default_factory=MemgraphNodeProperties, description="Node properties"
    )


class MemgraphRelationship(BaseModel):
    """Validation model for Memgraph relationship"""

    model_config = ConfigDict(extra="allow")

    identity: Optional[int] = Field(None, description="Relationship ID")
    type: str = Field(..., description="Relationship type")
    start_node: Optional[int] = Field(None, description="Start node ID")
    end_node: Optional[int] = Field(None, description="End node ID")
    properties: MemgraphRelationshipProperties = Field(
        default_factory=MemgraphRelationshipProperties,
        description="Relationship properties",
    )


class MemgraphQueryResult(BaseModel):
    """Validation model for Memgraph query result"""

    model_config = ConfigDict(extra="allow")

    entity: Optional[MemgraphNode] = Field(None, description="Entity node")
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list, description="Related entities"
    )
    path: List[str] = Field(default_factory=list, description="Path to entity")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Relevance score")


class MemgraphHealthResponse(BaseModel):
    """Validation model for Memgraph health check"""

    model_config = ConfigDict(extra="allow")

    status: str = Field(..., description="Health status")


# ============================================================================
# Bridge Service API Response Models
# ============================================================================


class BridgeMappingStats(BaseModel):
    """Validation model for Bridge service mapping stats"""

    model_config = ConfigDict(extra="allow")

    supabase_entities: Dict[str, int] = Field(
        default_factory=dict, description="Supabase entity counts"
    )
    qdrant_entities: Dict[str, int] = Field(
        default_factory=dict, description="Qdrant entity counts"
    )
    memgraph_entities: Dict[str, int] = Field(
        default_factory=dict, description="Memgraph entity counts"
    )
    total_entities: Optional[int] = Field(None, ge=0, description="Total entity count")
    last_sync: Optional[str] = Field(None, description="Last sync timestamp")

    @field_validator("supabase_entities", "qdrant_entities", "memgraph_entities")
    @classmethod
    def validate_entity_counts(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Ensure all counts are non-negative"""
        for key, value in v.items():
            if not isinstance(value, int) or value < 0:
                v[key] = 0
        return v


class BridgeHealthResponse(BaseModel):
    """Validation model for Bridge service health check"""

    model_config = ConfigDict(extra="allow")

    status: str = Field(..., description="Service status")
    services: Optional[Dict[str, bool]] = Field(
        None, description="Dependent service health"
    )


# ============================================================================
# Intelligence Service API Response Models
# ============================================================================


class IntelligenceQualityIssue(BaseModel):
    """Validation model for quality assessment issue"""

    model_config = ConfigDict(extra="allow")

    severity: str = Field(..., description="Issue severity")
    category: str = Field(..., description="Issue category")
    message: str = Field(..., description="Issue description")
    line_number: Optional[int] = Field(None, ge=1, description="Line number")
    recommendation: Optional[str] = Field(None, description="Recommendation")


class IntelligenceQualityResponse(BaseModel):
    """Validation model for Intelligence service quality assessment"""

    model_config = ConfigDict(extra="allow")

    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall quality score"
    )
    complexity: Optional[str] = Field(None, description="Complexity level")
    onex_compliance: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="ONEX compliance score"
    )
    issues: List[IntelligenceQualityIssue] = Field(
        default_factory=list, description="Quality issues"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )
    patterns_detected: Optional[List[str]] = Field(
        None, description="Detected patterns"
    )
    temporal_category: Optional[str] = Field(None, description="Era classification")


class IntelligenceHealthResponse(BaseModel):
    """Validation model for Intelligence service health check"""

    model_config = ConfigDict(extra="allow")

    status: str = Field(..., description="Service status")
    subsystems: Optional[Dict[str, bool]] = Field(
        None, description="Subsystem health status"
    )


# ============================================================================
# Validation Result Models
# ============================================================================


class ValidationStatus(str, Enum):
    """Validation status enum"""

    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"
    FAILED = "failed"


class ValidationResult(BaseModel):
    """Generic validation result with confidence scoring"""

    model_config = ConfigDict(extra="allow")

    status: ValidationStatus = Field(..., description="Validation status")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in validated data"
    )
    validated_data: Optional[Any] = Field(None, description="Validated data")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    raw_response: Optional[Dict[str, Any]] = Field(
        None, description="Original raw response"
    )
    service_name: str = Field(..., description="Source service name")

    @field_validator("confidence")
    @classmethod
    def adjust_confidence_for_errors(cls, v: float, info) -> float:
        """Reduce confidence based on validation errors"""
        errors = info.data.get("errors", [])
        warnings = info.data.get("warnings", [])

        # Reduce confidence for each error/warning
        penalty = len(errors) * 0.2 + len(warnings) * 0.1
        return max(0.0, v - penalty)
