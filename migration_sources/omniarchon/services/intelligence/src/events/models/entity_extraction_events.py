"""
Entity Extraction Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Entity Extraction operations:
- CODE_EXTRACTION_REQUESTED/COMPLETED/FAILED: Extract entities from code
- DOCUMENT_EXTRACTION_REQUESTED/COMPLETED/FAILED: Extract entities from documents
- ENTITY_SEARCH_REQUESTED/COMPLETED/FAILED: Search for entities
- RELATIONSHIP_QUERY_REQUESTED/COMPLETED/FAILED: Query entity relationships

ONEX Compliance:
- Model-based naming: ModelEntityExtraction{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Reference: EVENT_BUS_ARCHITECTURE.md, intelligence_adapter_events.py
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Type-only import for type hints


class EnumEntityExtractionEventType(str, Enum):
    """Event types for entity extraction operations."""

    # Code Extraction Events
    CODE_EXTRACTION_REQUESTED = "CODE_EXTRACTION_REQUESTED"
    CODE_EXTRACTION_COMPLETED = "CODE_EXTRACTION_COMPLETED"
    CODE_EXTRACTION_FAILED = "CODE_EXTRACTION_FAILED"

    # Document Extraction Events
    DOCUMENT_EXTRACTION_REQUESTED = "DOCUMENT_EXTRACTION_REQUESTED"
    DOCUMENT_EXTRACTION_COMPLETED = "DOCUMENT_EXTRACTION_COMPLETED"
    DOCUMENT_EXTRACTION_FAILED = "DOCUMENT_EXTRACTION_FAILED"

    # Entity Search Events
    ENTITY_SEARCH_REQUESTED = "ENTITY_SEARCH_REQUESTED"
    ENTITY_SEARCH_COMPLETED = "ENTITY_SEARCH_COMPLETED"
    ENTITY_SEARCH_FAILED = "ENTITY_SEARCH_FAILED"

    # Relationship Query Events
    RELATIONSHIP_QUERY_REQUESTED = "RELATIONSHIP_QUERY_REQUESTED"
    RELATIONSHIP_QUERY_COMPLETED = "RELATIONSHIP_QUERY_COMPLETED"
    RELATIONSHIP_QUERY_FAILED = "RELATIONSHIP_QUERY_FAILED"


class EnumEntityExtractionErrorCode(str, Enum):
    """Error codes for failed entity extraction operations."""

    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    PARSING_ERROR = "PARSING_ERROR"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    DATABASE_ERROR = "DATABASE_ERROR"


# ============================================================================
# Code Extraction Event Payloads
# ============================================================================


class ModelCodeExtractionRequestPayload(BaseModel):
    """
    Payload for CODE_EXTRACTION_REQUESTED event.

    Attributes:
        content: Code content to extract entities from
        source_path: Path to source file
        language: Programming language
        store_entities: Whether to store extracted entities
        trigger_freshness_analysis: Trigger freshness analysis
        metadata: Additional metadata
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    content: str = Field(
        ...,
        description="Code content to extract entities from",
        min_length=1,
    )

    source_path: str = Field(
        ...,
        description="Path to source file",
        min_length=1,
    )

    language: str = Field(
        default="python",
        description="Programming language",
        examples=["python", "typescript", "rust"],
    )

    extract_types: Optional[list[str]] = Field(
        None,
        description="Entity types to extract",
        examples=[["CLASS", "FUNCTION", "VARIABLE"]],
    )

    store_entities: bool = Field(
        default=True,
        description="Whether to store extracted entities",
    )

    trigger_freshness_analysis: bool = Field(
        default=False,
        description="Trigger freshness analysis",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty")
        return v

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, v: str) -> str:
        """Ensure source_path is not empty."""
        if not v or not v.strip():
            raise ValueError("source_path cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelCodeExtractionCompletedPayload(BaseModel):
    """
    Payload for CODE_EXTRACTION_COMPLETED event.

    Attributes:
        source_path: Source file path
        entities_count: Number of entities extracted
        entity_types: Entity types extracted
        confidence_mean: Mean confidence score
        confidence_min: Minimum confidence
        confidence_max: Maximum confidence
        processing_time_ms: Processing time
        stored: Whether entities were stored
        cache_hit: Whether cached
    """

    source_path: str = Field(
        ...,
        description="Source file path",
    )

    entities_count: int = Field(
        ...,
        description="Number of entities extracted",
        ge=0,
    )

    entity_types: list[str] = Field(
        default_factory=list,
        description="Entity types extracted",
        examples=[["FUNCTION", "CLASS", "VARIABLE"]],
    )

    confidence_mean: float = Field(
        ...,
        description="Mean confidence score",
        ge=0.0,
        le=1.0,
    )

    confidence_min: float = Field(
        ...,
        description="Minimum confidence",
        ge=0.0,
        le=1.0,
    )

    confidence_max: float = Field(
        ...,
        description="Maximum confidence",
        ge=0.0,
        le=1.0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0.0,
    )

    stored: bool = Field(
        default=False,
        description="Whether entities were stored",
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelCodeExtractionFailedPayload(BaseModel):
    """
    Payload for CODE_EXTRACTION_FAILED event.

    Attributes:
        source_path: Source file path
        error_message: Human-readable error
        error_code: Machine-readable error code
        retry_allowed: Whether retry allowed
        retry_count: Retry attempts
        processing_time_ms: Time before failure
        error_details: Error context
        suggested_action: Recommended action
    """

    source_path: str = Field(
        ...,
        description="Source file path",
    )

    error_message: str = Field(
        ...,
        description="Human-readable error",
        min_length=1,
    )

    error_code: EnumEntityExtractionErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry attempts",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Time before failure",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action",
    )

    model_config = ConfigDict(frozen=True)


class ModelDocumentExtractionRequestPayload(BaseModel):
    """
    Payload for DOCUMENT_EXTRACTION_REQUESTED event.

    Attributes:
        content: Document content
        source_path: Source path
        document_type: Document type
        extract_keywords: Extract keywords
        store_entities: Store entities
        metadata: Additional metadata
        project_id: Project identifier
        user_id: User identifier
    """

    content: str = Field(
        ...,
        description="Document content",
        min_length=1,
    )

    source_path: str = Field(
        ...,
        description="Source path",
        min_length=1,
    )

    document_type: str = Field(
        default="markdown",
        description="Document type",
    )

    extract_keywords: bool = Field(
        default=True,
        description="Extract keywords",
    )

    store_entities: bool = Field(
        default=True,
        description="Store entities",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not empty."""
        if not v or not v.strip():
            raise ValueError("content cannot be empty")
        return v

    model_config = ConfigDict(frozen=False)


class ModelDocumentExtractionCompletedPayload(BaseModel):
    """
    Payload for DOCUMENT_EXTRACTION_COMPLETED event.

    Attributes:
        source_path: Source path
        entities_count: Entities extracted
        keywords_count: Keywords extracted
        confidence_mean: Mean confidence
        processing_time_ms: Processing time
        stored: Whether stored
        cache_hit: Whether cached
    """

    source_path: str = Field(
        ...,
        description="Source path",
    )

    entities_count: int = Field(
        ...,
        description="Entities extracted",
        ge=0,
    )

    keywords_count: int = Field(
        default=0,
        description="Keywords extracted",
        ge=0,
    )

    confidence_mean: float = Field(
        ...,
        description="Mean confidence",
        ge=0.0,
        le=1.0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    stored: bool = Field(
        default=False,
        description="Whether stored",
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelDocumentExtractionFailedPayload(BaseModel):
    """
    Payload for DOCUMENT_EXTRACTION_FAILED event.

    Attributes:
        source_path: Source path
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    source_path: str = Field(
        ...,
        description="Source path",
    )

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumEntityExtractionErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class ModelEntitySearchRequestPayload(BaseModel):
    """
    Payload for ENTITY_SEARCH_REQUESTED event.

    Attributes:
        query: Search query
        entity_type: Entity type filter
        limit: Result limit
        min_confidence: Minimum confidence
        project_id: Project identifier
        user_id: User identifier
    """

    query: str = Field(
        ...,
        description="Search query",
        min_length=1,
    )

    entity_type: Optional[str] = Field(
        None,
        description="Entity type filter",
    )

    limit: int = Field(
        default=10,
        description="Result limit",
        ge=1,
        le=100,
    )

    min_confidence: float = Field(
        default=0.0,
        description="Minimum confidence",
        ge=0.0,
        le=1.0,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty."""
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelEntitySearchCompletedPayload(BaseModel):
    """
    Payload for ENTITY_SEARCH_COMPLETED event.

    Attributes:
        query: Search query
        results_count: Number of results
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    query: str = Field(
        ...,
        description="Search query",
    )

    results_count: int = Field(
        ...,
        description="Number of results",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelEntitySearchFailedPayload(BaseModel):
    """
    Payload for ENTITY_SEARCH_FAILED event.

    Attributes:
        query: Search query
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    query: str = Field(
        ...,
        description="Search query",
    )

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumEntityExtractionErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class ModelRelationshipQueryRequestPayload(BaseModel):
    """
    Payload for RELATIONSHIP_QUERY_REQUESTED event.

    Attributes:
        entity_id: Entity ID to query relationships for
        relationship_type: Relationship type filter
        limit: Result limit
        project_id: Project identifier
        user_id: User identifier
    """

    entity_id: str = Field(
        ...,
        description="Entity ID",
        min_length=1,
    )

    relationship_type: Optional[str] = Field(
        None,
        description="Relationship type filter",
    )

    limit: int = Field(
        default=20,
        description="Result limit",
        ge=1,
        le=100,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier",
    )

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        """Ensure entity_id is not empty."""
        if not v or not v.strip():
            raise ValueError("entity_id cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelRelationshipQueryCompletedPayload(BaseModel):
    """
    Payload for RELATIONSHIP_QUERY_COMPLETED event.

    Attributes:
        entity_id: Entity ID
        relationships_count: Number of relationships
        processing_time_ms: Processing time
        cache_hit: Whether cached
    """

    entity_id: str = Field(
        ...,
        description="Entity ID",
    )

    relationships_count: int = Field(
        ...,
        description="Number of relationships",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether cached",
    )

    model_config = ConfigDict(frozen=True)


class ModelRelationshipQueryFailedPayload(BaseModel):
    """
    Payload for RELATIONSHIP_QUERY_FAILED event.

    Attributes:
        entity_id: Entity ID
        error_message: Error message
        error_code: Error code
        retry_allowed: Retry allowed
        retry_count: Retry count
        processing_time_ms: Processing time
        error_details: Error details
        suggested_action: Suggested action
    """

    entity_id: str = Field(
        ...,
        description="Entity ID",
    )

    error_message: str = Field(
        ...,
        description="Error message",
        min_length=1,
    )

    error_code: EnumEntityExtractionErrorCode = Field(
        ...,
        description="Error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Retry allowed",
    )

    retry_count: int = Field(
        default=0,
        description="Retry count",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Processing time",
        ge=0.0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Suggested action",
    )

    model_config = ConfigDict(frozen=True)


class EntityExtractionEventHelpers:
    """
    Helper methods for creating and managing Entity Extraction events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "entity"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_event_envelope(
        event_type: str,
        payload: BaseModel,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create event envelope for any entity extraction event.

        Args:
            event_type: Event type suffix
            payload: Event payload model
            correlation_id: Optional correlation ID
            causation_id: Optional causation ID
            source_instance: Optional source instance

        Returns:
            Event envelope dictionary
        """
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{EntityExtractionEventHelpers.DOMAIN}.{EntityExtractionEventHelpers.PATTERN}.{event_type}.{EntityExtractionEventHelpers.VERSION}",
                "service": EntityExtractionEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-entity-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumEntityExtractionEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of entity extraction event
            environment: Environment

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()
        return f"{env_prefix}.{EntityExtractionEventHelpers.SERVICE_PREFIX}.{EntityExtractionEventHelpers.DOMAIN}.{event_suffix}.{EntityExtractionEventHelpers.VERSION}"
