"""
Inter-Service Communication Models

Standardized request/response models for communication between Archon services.
Ensures type safety and consistent data exchange patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from base_models import BaseEntity, BaseRelationship, ServiceHealth
from entity_types import EntityType
from pydantic import BaseModel, Field

T = TypeVar("T")


class ServiceStatus(str, Enum):
    """Standard service status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class OperationStatus(str, Enum):
    """Standard operation status values."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"


class ServiceRequest(BaseModel, Generic[T]):
    """Base request model for inter-service communication."""

    request_id: str = Field(..., description="Unique request identifier")
    requesting_service: str = Field(..., description="Name of the requesting service")
    target_service: str = Field(..., description="Name of the target service")
    operation: str = Field(..., description="Operation to perform")

    # Request data
    data: T = Field(..., description="Request payload")

    # Request context
    correlation_id: Optional[str] = Field(
        default=None, description="Correlation ID for request tracing"
    )
    user_id: Optional[str] = Field(default=None, description="User ID if applicable")
    project_id: Optional[str] = Field(default=None, description="Project context")

    # Request metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    timeout_seconds: Optional[int] = Field(default=30, description="Request timeout")
    priority: int = Field(default=1, ge=1, le=10, description="Request priority (1-10)")

    # Additional parameters
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Additional parameters"
    )


class ServiceResponse(BaseModel, Generic[T]):
    """Base response model for inter-service communication."""

    request_id: str = Field(..., description="Original request identifier")
    responding_service: str = Field(..., description="Name of the responding service")
    status: OperationStatus = Field(..., description="Operation status")

    # Response data
    data: Optional[T] = Field(default=None, description="Response payload")

    # Response metadata
    message: Optional[str] = Field(
        default=None, description="Human-readable status message"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = Field(
        default=None, description="Processing time in milliseconds"
    )

    # Error information
    error_code: Optional[str] = Field(default=None, description="Error code if failed")
    error_details: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed error information"
    )

    # Tracing and debugging
    correlation_id: Optional[str] = Field(
        default=None, description="Request correlation ID"
    )
    trace_id: Optional[str] = Field(default=None, description="Distributed trace ID")

    # Performance metrics
    metrics: Optional[Dict[str, float]] = Field(
        default=None, description="Operation performance metrics"
    )


# Specific request/response models for common operations


class EntitySyncRequest(BaseModel):
    """Request model for entity synchronization between services."""

    entities: List[BaseEntity] = Field(
        default_factory=list, description="Entities to sync"
    )
    relationships: List[BaseRelationship] = Field(
        default_factory=list, description="Relationships to sync"
    )

    # Sync parameters
    sync_mode: str = Field(
        default="incremental", description="Sync mode: full, incremental, or verify"
    )
    force_update: bool = Field(
        default=False, description="Force update even if no changes detected"
    )
    include_deleted: bool = Field(
        default=False, description="Include deleted entities in sync"
    )

    # Filtering
    entity_types: Optional[List[EntityType]] = Field(
        default=None, description="Entity types to sync"
    )
    project_ids: Optional[List[str]] = Field(
        default=None, description="Project IDs to sync"
    )
    since_timestamp: Optional[datetime] = Field(
        default=None, description="Sync changes since timestamp"
    )

    # Sync options
    batch_size: int = Field(
        default=100, ge=1, le=1000, description="Batch size for processing"
    )
    validate_references: bool = Field(
        default=True, description="Validate entity references"
    )
    create_missing_references: bool = Field(
        default=False, description="Create missing referenced entities"
    )


class EntitySyncResponse(BaseModel):
    """Response model for entity synchronization operations."""

    sync_id: str = Field(..., description="Unique synchronization identifier")

    # Sync results
    entities_processed: int = Field(
        default=0, description="Number of entities processed"
    )
    entities_created: int = Field(default=0, description="Number of entities created")
    entities_updated: int = Field(default=0, description="Number of entities updated")
    entities_deleted: int = Field(default=0, description="Number of entities deleted")
    entities_skipped: int = Field(default=0, description="Number of entities skipped")

    relationships_processed: int = Field(
        default=0, description="Number of relationships processed"
    )
    relationships_created: int = Field(
        default=0, description="Number of relationships created"
    )
    relationships_updated: int = Field(
        default=0, description="Number of relationships updated"
    )
    relationships_deleted: int = Field(
        default=0, description="Number of relationships deleted"
    )

    # Error tracking
    errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Sync errors"
    )
    warnings: List[str] = Field(default_factory=list, description="Sync warnings")

    # Performance metrics
    sync_duration_ms: Optional[float] = Field(
        default=None, description="Total sync duration"
    )
    throughput_entities_per_second: Optional[float] = Field(
        default=None, description="Sync throughput"
    )

    # Sync metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    next_sync_recommended: Optional[datetime] = Field(
        default=None, description="Recommended next sync time"
    )


class HealthCheckRequest(BaseModel):
    """Request model for service health checks."""

    include_detailed_status: bool = Field(
        default=False, description="Include detailed component status"
    )
    include_metrics: bool = Field(
        default=False, description="Include performance metrics"
    )
    check_external_dependencies: bool = Field(
        default=True, description="Check external service dependencies"
    )
    timeout_seconds: int = Field(
        default=10, ge=1, le=60, description="Health check timeout"
    )


class HealthCheckResponse(BaseModel):
    """Response model for service health checks."""

    health: ServiceHealth = Field(..., description="Service health information")

    # Component health
    components: Optional[Dict[str, ServiceHealth]] = Field(
        default=None, description="Individual component health"
    )

    # Dependency health
    dependencies: Optional[Dict[str, bool]] = Field(
        default=None, description="External dependency status"
    )

    # Performance indicators
    performance_indicators: Optional[Dict[str, float]] = Field(
        default=None, description="Key performance metrics"
    )

    # Health check metadata
    check_duration_ms: Optional[float] = Field(
        default=None, description="Health check duration"
    )
    last_full_check: Optional[datetime] = Field(
        default=None, description="Last comprehensive health check"
    )


class SearchRequest(BaseModel):
    """Request model for search operations across services."""

    query: str = Field(..., description="Search query")

    # Search parameters
    search_mode: str = Field(
        default="hybrid", description="Search mode (semantic, structural, hybrid)"
    )
    entity_types: Optional[List[EntityType]] = Field(
        default=None, description="Entity types to search"
    )
    limit: int = Field(
        default=10, ge=1, le=100, description="Maximum results to return"
    )
    offset: int = Field(default=0, ge=0, description="Results offset for pagination")

    # Filtering
    project_ids: Optional[List[str]] = Field(
        default=None, description="Project ID filter"
    )
    source_ids: Optional[List[str]] = Field(
        default=None, description="Source ID filter"
    )
    date_range: Optional[Dict[str, datetime]] = Field(
        default=None, description="Date range filter"
    )

    # Search options
    include_content: bool = Field(
        default=False, description="Include full content in results"
    )
    include_relationships: bool = Field(
        default=False, description="Include entity relationships"
    )
    minimum_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Minimum relevance score"
    )

    # Advanced options
    boost_recent: bool = Field(
        default=False, description="Boost recently updated entities"
    )
    semantic_search_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Semantic similarity threshold"
    )


class SearchResponse(BaseModel):
    """Response model for search operations."""

    query: str = Field(..., description="Original search query")
    total_results: int = Field(
        default=0, description="Total number of matching results"
    )
    returned_results: int = Field(
        default=0, description="Number of results in this response"
    )

    # Results
    entities: List[BaseEntity] = Field(
        default_factory=list, description="Matching entities"
    )
    relationships: List[BaseRelationship] = Field(
        default_factory=list, description="Related relationships"
    )

    # Search metadata
    search_time_ms: float = Field(..., description="Search execution time")
    search_mode_used: str = Field(..., description="Actual search mode used")

    # Result analysis
    entity_type_counts: Dict[str, int] = Field(
        default_factory=dict, description="Results by entity type"
    )
    source_counts: Dict[str, int] = Field(
        default_factory=dict, description="Results by source"
    )
    score_distribution: Optional[Dict[str, int]] = Field(
        default=None, description="Score distribution"
    )

    # Pagination
    has_more_results: bool = Field(default=False, description="More results available")
    next_offset: Optional[int] = Field(default=None, description="Next page offset")

    # Performance metrics
    cache_hit: bool = Field(default=False, description="Whether results were cached")
    index_stats: Optional[Dict[str, Any]] = Field(
        default=None, description="Search index statistics"
    )


# Utility functions for creating requests and responses


def create_service_request(
    requesting_service: str,
    target_service: str,
    operation: str,
    data: Any,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> ServiceRequest:
    """Create a standardized service request."""
    import uuid

    return ServiceRequest(
        request_id=str(uuid.uuid4()),
        requesting_service=requesting_service,
        target_service=target_service,
        operation=operation,
        data=data,
        correlation_id=correlation_id,
        **kwargs,
    )


def create_service_response(
    request_id: str,
    responding_service: str,
    status: OperationStatus,
    data: Optional[Any] = None,
    message: Optional[str] = None,
    **kwargs,
) -> ServiceResponse:
    """Create a standardized service response."""
    return ServiceResponse(
        request_id=request_id,
        responding_service=responding_service,
        status=status,
        data=data,
        message=message,
        **kwargs,
    )


def create_error_response(
    request_id: str,
    responding_service: str,
    error_code: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ServiceResponse:
    """Create a standardized error response."""
    return ServiceResponse(
        request_id=request_id,
        responding_service=responding_service,
        status=OperationStatus.FAILED,
        data=None,
        message=error_message,
        error_code=error_code,
        error_details=error_details,
        **kwargs,
    )
