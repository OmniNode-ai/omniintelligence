"""
Document Processing Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Document Processing operations:
- PROCESS_DOCUMENT_REQUESTED/COMPLETED/FAILED: Process single document
- BATCH_INDEX_REQUESTED/COMPLETED/FAILED: Batch index multiple documents

ONEX Compliance:
- Model-based naming: ModelDocument{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Purpose: Phase 4 - Bridge & Utility Events Implementation
Reference: EVENT_BUS_ARCHITECTURE.md, document_indexing_events.py pattern
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


# ============================================================================
# Enums
# ============================================================================


class EnumDocumentProcessingEventType(str, Enum):
    """Event types for document processing operations."""

    # Process Document
    PROCESS_DOCUMENT_REQUESTED = "PROCESS_DOCUMENT_REQUESTED"
    PROCESS_DOCUMENT_COMPLETED = "PROCESS_DOCUMENT_COMPLETED"
    PROCESS_DOCUMENT_FAILED = "PROCESS_DOCUMENT_FAILED"

    # Batch Index
    BATCH_INDEX_REQUESTED = "BATCH_INDEX_REQUESTED"
    BATCH_INDEX_COMPLETED = "BATCH_INDEX_COMPLETED"
    BATCH_INDEX_FAILED = "BATCH_INDEX_FAILED"


class EnumDocumentProcessingErrorCode(str, Enum):
    """Error codes for document processing operations."""

    INVALID_INPUT = "INVALID_INPUT"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSING_ERROR = "PARSING_ERROR"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BATCH_TOO_LARGE = "BATCH_TOO_LARGE"


# ============================================================================
# Process Document Event Payloads
# ============================================================================


class ModelDocumentProcessRequestPayload(BaseModel):
    """
    Payload for PROCESS_DOCUMENT_REQUESTED event.

    Attributes:
        document_path: Path to document to process
        content: Optional document content (if not reading from path)
        document_type: Document type (code, markdown, plain_text, etc.)
        processing_options: Processing configuration options
        extract_entities: Whether to extract entities
        generate_embeddings: Whether to generate embeddings
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    document_path: str = Field(
        ...,
        description="Path to document to process",
        examples=["docs/architecture.md", "src/api/server.py"],
        min_length=1,
    )

    content: Optional[str] = Field(
        None,
        description="Document content (if not reading from path)",
    )

    document_type: str = Field(
        default="auto",
        description="Document type (code, markdown, plain_text, etc.)",
        examples=["code", "markdown", "plain_text", "auto"],
    )

    processing_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Processing configuration options",
        examples=[
            {
                "extract_keywords": True,
                "analyze_sentiment": False,
                "generate_summary": True,
            }
        ],
    )

    extract_entities: bool = Field(
        default=True, description="Whether to extract entities"
    )

    generate_embeddings: bool = Field(
        default=True, description="Whether to generate embeddings"
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier for context",
        examples=["project-123"],
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for audit",
        examples=["user-456"],
    )

    @field_validator("document_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Ensure document_path is not empty."""
        if not v or not v.strip():
            raise ValueError("document_path cannot be empty")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelDocumentProcessCompletedPayload(BaseModel):
    """
    Payload for PROCESS_DOCUMENT_COMPLETED event.

    Attributes:
        document_path: Path to processed document
        entities_extracted: Number of entities extracted
        embeddings_generated: Number of embeddings generated
        processing_results: Detailed processing results
        processing_time_ms: Processing time in milliseconds
        cache_hit: Whether result was cached
    """

    document_path: str = Field(..., description="Path to processed document")

    entities_extracted: int = Field(
        ..., description="Number of entities extracted", ge=0
    )

    embeddings_generated: int = Field(
        ..., description="Number of embeddings generated", ge=0
    )

    processing_results: dict[str, Any] = Field(
        ...,
        description="Detailed processing results",
        examples=[
            {
                "entity_types": ["function", "class", "import"],
                "keywords": ["async", "await", "database"],
                "summary": "API server implementation",
            }
        ],
    )

    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds", ge=0.0
    )

    cache_hit: bool = Field(default=False, description="Whether result was cached")

    model_config = ConfigDict(frozen=True)


class ModelDocumentProcessFailedPayload(BaseModel):
    """
    Payload for PROCESS_DOCUMENT_FAILED event.

    Attributes:
        document_path: Path to document that failed
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
        error_details: Additional error context
    """

    document_path: str = Field(..., description="Path to document that failed")

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    error_code: EnumDocumentProcessingErrorCode = Field(
        ..., description="Machine-readable error code"
    )

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    model_config = ConfigDict(frozen=True)


class ModelBatchIndexRequestPayload(BaseModel):
    """
    Payload for BATCH_INDEX_REQUESTED event.

    Attributes:
        document_paths: List of document paths to index
        batch_options: Batch processing configuration
        skip_existing: Skip already indexed documents
        parallel_workers: Number of parallel workers
        project_id: Optional project identifier
        user_id: Optional user identifier
    """

    document_paths: list[str] = Field(
        ...,
        description="List of document paths to index",
        min_length=1,
        max_length=1000,
        examples=[["docs/README.md", "src/api.py", "tests/test_api.py"]],
    )

    batch_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Batch processing configuration",
        examples=[{"chunk_size": 100, "extract_entities": True}],
    )

    skip_existing: bool = Field(
        default=True, description="Skip already indexed documents"
    )

    parallel_workers: int = Field(
        default=4,
        description="Number of parallel workers",
        ge=1,
        le=32,
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier for context",
        examples=["project-123"],
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for audit",
        examples=["user-456"],
    )

    @field_validator("document_paths")
    @classmethod
    def validate_paths(cls, v: list[str]) -> list[str]:
        """Ensure all paths are non-empty."""
        if not v:
            raise ValueError("document_paths cannot be empty")
        for path in v:
            if not path or not path.strip():
                raise ValueError("All document paths must be non-empty")
        return [p.strip() for p in v]

    model_config = ConfigDict(frozen=False)


class ModelBatchIndexCompletedPayload(BaseModel):
    """
    Payload for BATCH_INDEX_COMPLETED event.

    Attributes:
        total_documents: Total documents in batch
        documents_indexed: Number of documents successfully indexed
        documents_skipped: Number of documents skipped
        documents_failed: Number of documents that failed
        batch_results: Detailed batch results
        processing_time_ms: Total processing time in milliseconds
        failed_documents: List of failed document paths with errors
    """

    total_documents: int = Field(..., description="Total documents in batch", ge=0)

    documents_indexed: int = Field(
        ..., description="Number of documents successfully indexed", ge=0
    )

    documents_skipped: int = Field(..., description="Number of documents skipped", ge=0)

    documents_failed: int = Field(
        ..., description="Number of documents that failed", ge=0
    )

    batch_results: dict[str, Any] = Field(
        ...,
        description="Detailed batch results",
        examples=[
            {
                "total_entities": 150,
                "total_embeddings": 75,
                "avg_processing_time_ms": 234.5,
            }
        ],
    )

    processing_time_ms: float = Field(
        ..., description="Total processing time in milliseconds", ge=0.0
    )

    failed_documents: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of failed document paths with errors",
        examples=[
            [
                {
                    "path": "docs/broken.md",
                    "error": "Parsing error",
                    "error_code": "PARSING_ERROR",
                }
            ]
        ],
    )

    model_config = ConfigDict(frozen=True)


class ModelBatchIndexFailedPayload(BaseModel):
    """
    Payload for BATCH_INDEX_FAILED event.

    Attributes:
        total_documents: Total documents in batch
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
        partial_results: Optional partial results before failure
    """

    total_documents: int = Field(..., description="Total documents in batch", ge=0)

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    error_code: EnumDocumentProcessingErrorCode = Field(
        ..., description="Machine-readable error code"
    )

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    partial_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional partial results before failure",
        examples=[{"documents_processed": 25, "last_successful_path": "docs/test.md"}],
    )

    model_config = ConfigDict(frozen=True)


class DocumentProcessingEventHelpers:
    """Helper methods for creating Document Processing events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "document"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def _create_envelope(
        event_type: str,
        payload: BaseModel,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create event envelope with fallback for missing imports."""
        # Local import to avoid circular dependency
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={
                "event_type": event_type,
                "service": DocumentProcessingEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "intelligence-document-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )
        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumDocumentProcessingEventType, environment: str = "development"
    ) -> str:
        """Generate Kafka topic name for event type."""
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{DocumentProcessingEventHelpers.SERVICE_PREFIX}.{DocumentProcessingEventHelpers.DOMAIN}.{event_suffix}.{DocumentProcessingEventHelpers.VERSION}"


# ============================================================================
# Convenience Functions
# ============================================================================


def create_process_document_request(
    document_path: str,
    content: Optional[str] = None,
    document_type: str = "auto",
    processing_options: Optional[dict[str, Any]] = None,
    extract_entities: bool = True,
    generate_embeddings: bool = True,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create PROCESS_DOCUMENT_REQUESTED event."""
    payload = ModelDocumentProcessRequestPayload(
        document_path=document_path,
        content=content,
        document_type=document_type,
        processing_options=processing_options or {},
        extract_entities=extract_entities,
        generate_embeddings=generate_embeddings,
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{DocumentProcessingEventHelpers.DOMAIN}.{DocumentProcessingEventHelpers.PATTERN}.process_document_requested.{DocumentProcessingEventHelpers.VERSION}"

    return DocumentProcessingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_process_document_completed(
    document_path: str,
    entities_extracted: int,
    embeddings_generated: int,
    processing_results: dict[str, Any],
    processing_time_ms: float,
    correlation_id: UUID,
    cache_hit: bool = False,
) -> dict[str, Any]:
    """Create PROCESS_DOCUMENT_COMPLETED event."""
    payload = ModelDocumentProcessCompletedPayload(
        document_path=document_path,
        entities_extracted=entities_extracted,
        embeddings_generated=embeddings_generated,
        processing_results=processing_results,
        processing_time_ms=processing_time_ms,
        cache_hit=cache_hit,
    )

    event_type = f"omninode.{DocumentProcessingEventHelpers.DOMAIN}.{DocumentProcessingEventHelpers.PATTERN}.process_document_completed.{DocumentProcessingEventHelpers.VERSION}"

    return DocumentProcessingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_process_document_failed(
    document_path: str,
    error_message: str,
    error_code: EnumDocumentProcessingErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
    error_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create PROCESS_DOCUMENT_FAILED event."""
    payload = ModelDocumentProcessFailedPayload(
        document_path=document_path,
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
        error_details=error_details or {},
    )

    event_type = f"omninode.{DocumentProcessingEventHelpers.DOMAIN}.{DocumentProcessingEventHelpers.PATTERN}.process_document_failed.{DocumentProcessingEventHelpers.VERSION}"

    return DocumentProcessingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_batch_index_request(
    document_paths: list[str],
    batch_options: Optional[dict[str, Any]] = None,
    skip_existing: bool = True,
    parallel_workers: int = 4,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Create BATCH_INDEX_REQUESTED event."""
    payload = ModelBatchIndexRequestPayload(
        document_paths=document_paths,
        batch_options=batch_options or {},
        skip_existing=skip_existing,
        parallel_workers=parallel_workers,
    )

    correlation_id = correlation_id or uuid4()
    event_type = f"omninode.{DocumentProcessingEventHelpers.DOMAIN}.{DocumentProcessingEventHelpers.PATTERN}.batch_index_requested.{DocumentProcessingEventHelpers.VERSION}"

    return DocumentProcessingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_batch_index_completed(
    total_documents: int,
    documents_indexed: int,
    documents_skipped: int,
    documents_failed: int,
    batch_results: dict[str, Any],
    processing_time_ms: float,
    correlation_id: UUID,
    failed_documents: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Create BATCH_INDEX_COMPLETED event."""
    payload = ModelBatchIndexCompletedPayload(
        total_documents=total_documents,
        documents_indexed=documents_indexed,
        documents_skipped=documents_skipped,
        documents_failed=documents_failed,
        batch_results=batch_results,
        processing_time_ms=processing_time_ms,
        failed_documents=failed_documents or [],
    )

    event_type = f"omninode.{DocumentProcessingEventHelpers.DOMAIN}.{DocumentProcessingEventHelpers.PATTERN}.batch_index_completed.{DocumentProcessingEventHelpers.VERSION}"

    return DocumentProcessingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_batch_index_failed(
    total_documents: int,
    error_message: str,
    error_code: EnumDocumentProcessingErrorCode,
    correlation_id: UUID,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
    partial_results: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create BATCH_INDEX_FAILED event."""
    payload = ModelBatchIndexFailedPayload(
        total_documents=total_documents,
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
        partial_results=partial_results or {},
    )

    event_type = f"omninode.{DocumentProcessingEventHelpers.DOMAIN}.{DocumentProcessingEventHelpers.PATTERN}.batch_index_failed.{DocumentProcessingEventHelpers.VERSION}"

    return DocumentProcessingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )
