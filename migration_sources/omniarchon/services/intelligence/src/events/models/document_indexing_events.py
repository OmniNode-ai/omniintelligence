"""
Document Indexing Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Document Indexing Handler operations:
- DOCUMENT_INDEX_REQUESTED: Triggered when document indexing is requested
- DOCUMENT_INDEX_COMPLETED: Triggered when document indexing completes successfully
- DOCUMENT_INDEX_FAILED: Triggered when document indexing fails

ONEX Compliance:
- Model-based naming: ModelDocumentIndex{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Reference: EVENT_HANDLER_CONTRACTS.md, intelligence_adapter_events.py pattern
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumDocumentIndexEventType(str, Enum):
    """Event types for document indexing operations."""

    DOCUMENT_INDEX_REQUESTED = "DOCUMENT_INDEX_REQUESTED"
    DOCUMENT_INDEX_COMPLETED = "DOCUMENT_INDEX_COMPLETED"
    DOCUMENT_INDEX_FAILED = "DOCUMENT_INDEX_FAILED"


class EnumIndexingErrorCode(str, Enum):
    """Error codes for document indexing failures."""

    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    PARSING_ERROR = "PARSING_ERROR"
    METADATA_STAMPING_FAILED = "METADATA_STAMPING_FAILED"
    ENTITY_EXTRACTION_FAILED = "ENTITY_EXTRACTION_FAILED"
    VECTOR_INDEXING_FAILED = "VECTOR_INDEXING_FAILED"
    KNOWLEDGE_GRAPH_FAILED = "KNOWLEDGE_GRAPH_FAILED"
    QUALITY_ASSESSMENT_FAILED = "QUALITY_ASSESSMENT_FAILED"
    TIMEOUT = "TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Event Payload Models
# ============================================================================


class ModelDocumentIndexRequestPayload(BaseModel):
    """
    Payload for DOCUMENT_INDEX_REQUESTED event.

    Captures all parameters needed to perform full intelligence pipeline
    including metadata stamping, entity extraction, vector indexing,
    knowledge graph storage, and quality assessment.

    Attributes:
        source_path: File path or URL to document being indexed
        content: Optional document content (if not reading from source_path)
        language: Programming language (python, typescript, rust, etc.)
        project_id: Optional project identifier for organizational context
        repository_url: Optional git repository URL
        commit_sha: Optional git commit SHA for version tracking
        indexing_options: Indexing configuration options
        user_id: Optional user identifier for authorization and audit
    """

    source_path: str = Field(
        ...,
        description="File path or URL to document being indexed",
        examples=["src/services/intelligence/quality_service.py"],
        min_length=1,
    )

    content: Optional[str] = Field(
        None,
        description="Document content (if not reading from source_path)",
    )

    language: Optional[str] = Field(
        None,
        description="Programming language (python, typescript, rust, etc.)",
        examples=["python", "typescript", "rust"],
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier for organizational context",
        examples=["omniarchon", "project-123"],
    )

    repository_url: Optional[str] = Field(
        None,
        description="Git repository URL if applicable",
        examples=["https://github.com/org/repo"],
    )

    commit_sha: Optional[str] = Field(
        None,
        description="Git commit SHA for version tracking",
        examples=["a1b2c3d4e5f6"],
    )

    indexing_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Indexing configuration options",
        examples=[
            {
                "skip_metadata_stamping": False,
                "skip_vector_indexing": False,
                "skip_knowledge_graph": False,
                "skip_quality_assessment": False,
                "force_reindex": False,
                "chunk_size": 1000,
                "chunk_overlap": 200,
            }
        ],
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for authorization and audit",
    )

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, v: str) -> str:
        """Ensure source_path is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("source_path cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "source_path": "src/services/intelligence/quality_service.py",
                    "content": None,
                    "language": "python",
                    "project_id": "omniarchon",
                    "repository_url": "https://github.com/org/omniarchon",
                    "commit_sha": "a1b2c3d4e5f6",
                    "indexing_options": {
                        "skip_metadata_stamping": False,
                        "chunk_size": 1000,
                        "chunk_overlap": 200,
                    },
                    "user_id": "system",
                }
            ]
        },
    )


class ModelDocumentIndexCompletedPayload(BaseModel):
    """
    Payload for DOCUMENT_INDEX_COMPLETED event.

    Captures results from full intelligence pipeline including metadata hash,
    extracted entities, vector IDs, quality scores, and performance metrics.

    Attributes:
        source_path: File path that was indexed
        document_hash: BLAKE3 content hash from metadata stamping
        entity_ids: Entity IDs created in knowledge graph
        vector_ids: Vector IDs created in Qdrant
        quality_score: Optional overall quality score (0.0-1.0)
        onex_compliance: Optional ONEX architectural compliance (0.0-1.0)
        entities_extracted: Number of entities extracted
        relationships_created: Number of relationships created in knowledge graph
        chunks_indexed: Number of chunks indexed in vector database
        processing_time_ms: Total processing time in milliseconds
        service_timings: Breakdown of processing time by service
        cache_hit: Whether document was already indexed (deduplication)
        reindex_required: Whether future reindexing is recommended
    """

    source_path: str = Field(
        ...,
        description="File path that was indexed",
    )

    document_hash: str = Field(
        ...,
        description="BLAKE3 content hash from metadata stamping",
        examples=["blake3:a1b2c3d4e5f6..."],
    )

    entity_ids: list[str] = Field(
        default_factory=list,
        description="Entity IDs created in knowledge graph",
        examples=[["entity-uuid-1", "entity-uuid-2"]],
    )

    vector_ids: list[str] = Field(
        default_factory=list,
        description="Vector IDs created in Qdrant",
        examples=[["vec-uuid-1", "vec-uuid-2"]],
    )

    quality_score: Optional[float] = Field(
        None,
        description="Overall quality score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    onex_compliance: Optional[float] = Field(
        None,
        description="ONEX architectural compliance (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    entities_extracted: int = Field(
        ...,
        description="Number of entities extracted (functions, classes, etc.)",
        ge=0,
    )

    relationships_created: int = Field(
        ...,
        description="Number of relationships created in knowledge graph",
        ge=0,
    )

    chunks_indexed: int = Field(
        ...,
        description="Number of chunks indexed in vector database",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
        ge=0.0,
    )

    service_timings: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of processing time by service",
        examples=[
            {
                "metadata_stamping_ms": 45.2,
                "entity_extraction_ms": 234.5,
                "vector_indexing_ms": 123.4,
                "knowledge_graph_ms": 89.3,
                "quality_assessment_ms": 156.7,
            }
        ],
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether document was already indexed (deduplication)",
    )

    reindex_required: bool = Field(
        default=False,
        description="Whether future reindexing is recommended",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "source_path": "src/services/intelligence/quality_service.py",
                    "document_hash": "blake3:a1b2c3d4e5f6...",
                    "entity_ids": ["entity-uuid-1", "entity-uuid-2"],
                    "vector_ids": ["vec-uuid-1", "vec-uuid-2"],
                    "quality_score": 0.87,
                    "onex_compliance": 0.92,
                    "entities_extracted": 12,
                    "relationships_created": 18,
                    "chunks_indexed": 5,
                    "processing_time_ms": 649.1,
                    "service_timings": {
                        "metadata_stamping_ms": 45.2,
                        "entity_extraction_ms": 234.5,
                        "vector_indexing_ms": 123.4,
                        "knowledge_graph_ms": 89.3,
                        "quality_assessment_ms": 156.7,
                    },
                    "cache_hit": False,
                    "reindex_required": False,
                }
            ]
        },
    )


class ModelDocumentIndexFailedPayload(BaseModel):
    """
    Payload for DOCUMENT_INDEX_FAILED event.

    Captures failure information including error details, failed service,
    partial results, and retry eligibility.

    Attributes:
        source_path: File path that failed indexing
        error_message: Human-readable error description
        error_code: Machine-readable error code
        failed_service: Optional service that caused the failure
        retry_allowed: Whether the operation can be retried
        retry_count: Number of retries attempted
        processing_time_ms: Time taken before failure
        partial_results: Partial results from services that succeeded
        error_details: Additional error context and stack trace
        suggested_action: Optional recommended action to resolve the error
    """

    source_path: str = Field(
        ...,
        description="File path that failed indexing",
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        min_length=1,
    )

    error_code: EnumIndexingErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    failed_service: Optional[str] = Field(
        None,
        description="Service that caused the failure",
        examples=["metadata_stamping", "entity_extraction", "vector_indexing"],
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether the operation can be retried",
    )

    retry_count: int = Field(
        default=0,
        description="Number of retries attempted",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Time taken before failure",
        ge=0.0,
    )

    partial_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Partial results from services that succeeded",
        examples=[
            {
                "metadata_stamping": {"hash": "blake3:..."},
                "entity_extraction": {"entities_count": 12},
            }
        ],
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context and stack trace",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action to resolve the error",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "source_path": "src/broken/invalid_syntax.py",
                    "error_message": "Failed to parse Python code: unexpected EOF",
                    "error_code": "PARSING_ERROR",
                    "failed_service": "entity_extraction",
                    "retry_allowed": False,
                    "retry_count": 0,
                    "processing_time_ms": 456.7,
                    "partial_results": {"metadata_stamping": {"hash": "blake3:..."}},
                    "error_details": {
                        "exception_type": "SyntaxError",
                        "line_number": 42,
                    },
                    "suggested_action": "Verify source code syntax is valid",
                }
            ]
        },
    )


class DocumentIndexingEventHelpers:
    """
    Helper methods for creating and managing Document Indexing events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    # Topic routing configuration
    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "intelligence"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_index_requested_event(
        payload: ModelDocumentIndexRequestPayload,
        correlation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create DOCUMENT_INDEX_REQUESTED event envelope.

        Args:
            payload: Request payload with indexing parameters
            correlation_id: Optional correlation ID for tracking
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        correlation_id = correlation_id or uuid4()

        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{DocumentIndexingEventHelpers.DOMAIN}.{DocumentIndexingEventHelpers.PATTERN}.document_index_requested.{DocumentIndexingEventHelpers.VERSION}",
                "service": DocumentIndexingEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "document-indexing-handler-1",
                "causation_id": None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_index_completed_event(
        payload: ModelDocumentIndexCompletedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create DOCUMENT_INDEX_COMPLETED event envelope.

        Args:
            payload: Completion payload with indexing results
            correlation_id: Correlation ID from original request
            causation_id: Optional event ID that caused this event
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{DocumentIndexingEventHelpers.DOMAIN}.{DocumentIndexingEventHelpers.PATTERN}.document_index_completed.{DocumentIndexingEventHelpers.VERSION}",
                "service": DocumentIndexingEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "document-indexing-handler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_index_failed_event(
        payload: ModelDocumentIndexFailedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create DOCUMENT_INDEX_FAILED event envelope.

        Args:
            payload: Failure payload with error details
            correlation_id: Correlation ID from original request
            causation_id: Optional event ID that caused this event
            source_instance: Optional source instance identifier

        Returns:
            Event envelope dictionary ready for Kafka publishing
        """
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": f"omninode.{DocumentIndexingEventHelpers.DOMAIN}.{DocumentIndexingEventHelpers.PATTERN}.document_index_failed.{DocumentIndexingEventHelpers.VERSION}",
                "service": DocumentIndexingEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "document-indexing-handler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumDocumentIndexEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of document indexing event
            environment: Environment (development, staging, production)

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{DocumentIndexingEventHelpers.SERVICE_PREFIX}.{DocumentIndexingEventHelpers.DOMAIN}.{event_suffix}.{DocumentIndexingEventHelpers.VERSION}"

    @staticmethod
    def deserialize_event(event_dict: dict[str, Any]) -> tuple[str, BaseModel]:
        """
        Deserialize event envelope and extract typed payload.

        Args:
            event_dict: Event envelope dictionary from Kafka

        Returns:
            Tuple of (event_type, typed_payload_model)

        Raises:
            ValueError: If event_type is unknown or payload is invalid
        """
        event_type = event_dict.get("event_type", "")

        # Extract payload
        payload_data = event_dict.get("payload", {})

        # Determine event type and deserialize payload
        if "document_index_requested" in event_type:
            payload = ModelDocumentIndexRequestPayload(**payload_data)
            return (EnumDocumentIndexEventType.DOCUMENT_INDEX_REQUESTED.value, payload)

        elif "document_index_completed" in event_type:
            payload = ModelDocumentIndexCompletedPayload(**payload_data)
            return (EnumDocumentIndexEventType.DOCUMENT_INDEX_COMPLETED.value, payload)

        elif "document_index_failed" in event_type:
            payload = ModelDocumentIndexFailedPayload(**payload_data)
            return (EnumDocumentIndexEventType.DOCUMENT_INDEX_FAILED.value, payload)

        else:
            raise ValueError(f"Unknown event type: {event_type}")


# ============================================================================
# Convenience Functions
# ============================================================================


def create_request_event(
    source_path: str,
    content: Optional[str] = None,
    language: Optional[str] = None,
    project_id: Optional[str] = None,
    repository_url: Optional[str] = None,
    commit_sha: Optional[str] = None,
    indexing_options: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """
    Convenience function to create DOCUMENT_INDEX_REQUESTED event.

    Args:
        source_path: File path or URL to document
        content: Optional document content
        language: Optional programming language
        project_id: Optional project identifier
        repository_url: Optional git repository URL
        commit_sha: Optional git commit SHA
        indexing_options: Optional indexing configuration
        user_id: Optional user identifier
        correlation_id: Optional correlation ID

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelDocumentIndexRequestPayload(
        source_path=source_path,
        content=content,
        language=language,
        project_id=project_id,
        repository_url=repository_url,
        commit_sha=commit_sha,
        indexing_options=indexing_options or {},
        user_id=user_id,
    )

    return DocumentIndexingEventHelpers.create_index_requested_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_completed_event(
    source_path: str,
    document_hash: str,
    entity_ids: list[str],
    vector_ids: list[str],
    entities_extracted: int,
    relationships_created: int,
    chunks_indexed: int,
    processing_time_ms: float,
    correlation_id: UUID,
    quality_score: Optional[float] = None,
    onex_compliance: Optional[float] = None,
    service_timings: Optional[dict[str, float]] = None,
    cache_hit: bool = False,
    reindex_required: bool = False,
) -> dict[str, Any]:
    """
    Convenience function to create DOCUMENT_INDEX_COMPLETED event.

    Args:
        source_path: File path indexed
        document_hash: BLAKE3 content hash
        entity_ids: Entity IDs created
        vector_ids: Vector IDs created
        entities_extracted: Number of entities extracted
        relationships_created: Number of relationships created
        chunks_indexed: Number of chunks indexed
        processing_time_ms: Processing time in milliseconds
        correlation_id: Correlation ID from request
        quality_score: Optional quality score
        onex_compliance: Optional ONEX compliance score
        service_timings: Optional service timing breakdown
        cache_hit: Whether result was cached
        reindex_required: Whether reindexing is recommended

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelDocumentIndexCompletedPayload(
        source_path=source_path,
        document_hash=document_hash,
        entity_ids=entity_ids,
        vector_ids=vector_ids,
        quality_score=quality_score,
        onex_compliance=onex_compliance,
        entities_extracted=entities_extracted,
        relationships_created=relationships_created,
        chunks_indexed=chunks_indexed,
        processing_time_ms=processing_time_ms,
        service_timings=service_timings or {},
        cache_hit=cache_hit,
        reindex_required=reindex_required,
    )

    return DocumentIndexingEventHelpers.create_index_completed_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_failed_event(
    source_path: str,
    error_message: str,
    error_code: EnumIndexingErrorCode,
    correlation_id: UUID,
    failed_service: Optional[str] = None,
    retry_allowed: bool = False,
    retry_count: int = 0,
    processing_time_ms: float = 0.0,
    partial_results: Optional[dict[str, Any]] = None,
    error_details: Optional[dict[str, Any]] = None,
    suggested_action: Optional[str] = None,
) -> dict[str, Any]:
    """
    Convenience function to create DOCUMENT_INDEX_FAILED event.

    Args:
        source_path: File path that failed
        error_message: Human-readable error message
        error_code: Machine-readable error code
        correlation_id: Correlation ID from request
        failed_service: Optional service that failed
        retry_allowed: Whether retry is allowed
        retry_count: Number of retries attempted
        processing_time_ms: Processing time before failure
        partial_results: Optional partial results
        error_details: Optional error details
        suggested_action: Optional suggested action

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelDocumentIndexFailedPayload(
        source_path=source_path,
        error_message=error_message,
        error_code=error_code,
        failed_service=failed_service,
        retry_allowed=retry_allowed,
        retry_count=retry_count,
        processing_time_ms=processing_time_ms,
        partial_results=partial_results or {},
        error_details=error_details or {},
        suggested_action=suggested_action,
    )

    return DocumentIndexingEventHelpers.create_index_failed_event(
        payload=payload,
        correlation_id=correlation_id,
    )
