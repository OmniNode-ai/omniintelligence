"""
Base Pydantic Models for Archon Services

Provides common data structures that can be used across all services
for consistent entity representation and service communication.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from entity_types import EntityType
from pydantic import BaseModel, ConfigDict, Field


class EntityMetadata(BaseModel):
    """Standardized metadata for entities across all services."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(
        default=None, description="Service or user that created this entity"
    )
    version: int = Field(default=1, description="Entity version for optimistic locking")

    # Quality and analysis metadata
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    validation_status: str = Field(
        default="unvalidated", description="Validation status"
    )

    # Source tracking
    source_path: Optional[str] = Field(
        default=None, description="Original source file path"
    )
    source_hash: Optional[str] = Field(
        default=None, description="Content hash for change detection"
    )
    line_number: Optional[int] = Field(
        default=None, description="Source line number if applicable"
    )

    # Service-specific extensions
    service_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Service-specific metadata"
    )
    tags: List[str] = Field(
        default_factory=list, description="Entity tags for categorization"
    )


class BaseEntity(BaseModel):
    """Base entity model that all services can extend."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )
    entity_id: str = Field(..., description="Unique entity identifier")
    entity_type: EntityType = Field(..., description="Standardized entity type")
    name: str = Field(..., description="Entity name")
    description: str = Field(default="", description="Entity description")

    # Content
    content: Optional[str] = Field(default=None, description="Entity content or body")
    summary: Optional[str] = Field(default=None, description="Brief entity summary")

    # Relationships and hierarchy
    parent_id: Optional[str] = Field(
        default=None, description="Parent entity ID if hierarchical"
    )
    project_id: Optional[str] = Field(default=None, description="Associated project ID")
    source_id: Optional[str] = Field(default=None, description="Associated source ID")

    # Vector and search
    embedding: Optional[List[float]] = Field(
        default=None, description="Vector embedding for similarity search"
    )

    # Standard metadata
    metadata: EntityMetadata = Field(default_factory=EntityMetadata)

    # Additional properties for service-specific extensions
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional properties"
    )


class BaseRelationship(BaseModel):
    """Base relationship model for connections between entities."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None}
    )
    relationship_id: str = Field(..., description="Unique relationship identifier")
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    relationship_type: str = Field(..., description="Type of relationship")

    # Relationship strength and metadata
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Relationship confidence"
    )
    weight: float = Field(
        default=1.0, ge=0.0, description="Relationship weight for graph algorithms"
    )
    bidirectional: bool = Field(
        default=False, description="Whether relationship is bidirectional"
    )

    # Context and properties
    context: Optional[str] = Field(default=None, description="Relationship context")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Additional relationship properties"
    )

    # Standard metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None)


class ServiceHealth(BaseModel):
    """Standardized health status model for all services."""

    status: str = Field(
        ..., description="Overall service status (healthy, degraded, unhealthy)"
    )
    service_name: str = Field(..., description="Service name")
    service_version: str = Field(default="1.0.0", description="Service version")

    # Connection status
    database_connected: bool = Field(
        default=False, description="Primary database connection status"
    )
    external_services: Dict[str, bool] = Field(
        default_factory=dict, description="External service connections"
    )

    # Performance metrics
    uptime_seconds: Optional[float] = Field(
        default=None, description="Service uptime in seconds"
    )
    last_health_check: datetime = Field(default_factory=datetime.utcnow)
    response_time_ms: Optional[float] = Field(
        default=None, description="Average response time"
    )

    # Issues and errors
    warnings: List[str] = Field(default_factory=list, description="Non-critical issues")
    errors: List[str] = Field(default_factory=list, description="Critical errors")
    error_message: Optional[str] = Field(
        default=None, description="Primary error message"
    )

    # Resource utilization
    memory_usage_mb: Optional[float] = Field(
        default=None, description="Memory usage in MB"
    )
    cpu_usage_percent: Optional[float] = Field(
        default=None, description="CPU usage percentage"
    )


class QualityMetrics(BaseModel):
    """Quality assessment metrics for entities and code."""

    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall quality score"
    )

    # Code quality metrics
    complexity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    maintainability_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    readability_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Documentation quality
    documentation_coverage: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    documentation_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Testing metrics
    test_coverage: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    test_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Architecture compliance
    architecture_compliance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    onex_compliance: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Detailed analysis
    issues: List[Dict[str, Any]] = Field(
        default_factory=list, description="Identified issues"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )
    patterns: List[Dict[str, Any]] = Field(
        default_factory=list, description="Detected patterns"
    )

    # Analysis metadata
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    analyzer_version: str = Field(
        default="1.0.0", description="Quality analyzer version"
    )


class PerformanceMetrics(BaseModel):
    """Performance measurement and optimization metrics."""

    operation_name: str = Field(..., description="Name of operation being measured")

    # Core performance metrics
    response_time_ms: float = Field(
        ..., ge=0, description="Response time in milliseconds"
    )
    throughput_per_second: Optional[float] = Field(
        default=None, ge=0, description="Operations per second"
    )
    memory_usage_mb: Optional[float] = Field(
        default=None, ge=0, description="Memory usage in MB"
    )
    cpu_usage_percent: Optional[float] = Field(
        default=None, ge=0, le=100, description="CPU usage percentage"
    )

    # Resource utilization
    disk_io_mb: Optional[float] = Field(
        default=None, ge=0, description="Disk I/O in MB"
    )
    network_io_mb: Optional[float] = Field(
        default=None, ge=0, description="Network I/O in MB"
    )
    database_queries: Optional[int] = Field(
        default=None, ge=0, description="Number of database queries"
    )

    # Performance baseline comparison
    baseline_response_time_ms: Optional[float] = Field(default=None, ge=0)
    performance_improvement_percent: Optional[float] = Field(
        default=None, description="Performance improvement vs baseline"
    )

    # Context and analysis
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    measurement_duration_seconds: Optional[float] = Field(default=None, ge=0)
    sample_size: Optional[int] = Field(default=None, ge=1)

    # Optimization tracking
    optimization_applied: Optional[str] = Field(
        default=None, description="Applied optimization technique"
    )
    roi_score: Optional[float] = Field(
        default=None, ge=0, description="Return on investment score"
    )

    # Additional metrics
    custom_metrics: Dict[str, float] = Field(
        default_factory=dict, description="Custom performance metrics"
    )
