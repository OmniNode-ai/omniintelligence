"""
Repository Crawler Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Repository Crawler Handler operations:
- REPOSITORY_SCAN_REQUESTED: Triggered when repository scan is requested
- REPOSITORY_SCAN_COMPLETED: Triggered when repository scan completes successfully
- REPOSITORY_SCAN_FAILED: Triggered when repository scan fails

ONEX Compliance:
- Model-based naming: ModelRepositoryScan{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-22
Reference: EVENT_HANDLER_CONTRACTS.md, EVENT_BUS_ARCHITECTURE.md
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import from local event base to avoid circular imports

# Type-only import for type hints


class EnumRepositoryCrawlerEventType(str, Enum):
    """Event types for repository crawler operations."""

    REPOSITORY_SCAN_REQUESTED = "REPOSITORY_SCAN_REQUESTED"
    REPOSITORY_SCAN_COMPLETED = "REPOSITORY_SCAN_COMPLETED"
    REPOSITORY_SCAN_FAILED = "REPOSITORY_SCAN_FAILED"


class EnumScanScope(str, Enum):
    """Scope of repository scan."""

    FULL = "FULL"  # Scan entire repository
    INCREMENTAL = "INCREMENTAL"  # Only scan changed files since last scan
    SELECTIVE = "SELECTIVE"  # Scan specific paths/patterns


class EnumCrawlerErrorCode(str, Enum):
    """Error codes for repository scan failures."""

    INVALID_INPUT = "INVALID_INPUT"
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    GIT_ERROR = "GIT_ERROR"
    NO_FILES_FOUND = "NO_FILES_FOUND"
    PATTERN_ERROR = "PATTERN_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Event Payload Models
# ============================================================================


class ModelRepositoryScanRequestPayload(BaseModel):
    """
    Payload for REPOSITORY_SCAN_REQUESTED event.

    Captures all parameters needed to perform repository scanning including
    repository path, scan scope, file patterns, and optional configuration.

    Attributes:
        repository_path: Local filesystem path or Git URL
        project_id: Project identifier
        scan_scope: Scope of scan (full, incremental, selective)
        file_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        commit_sha: Optional Git commit SHA to scan
        branch: Optional Git branch to scan
        batch_size: Number of files to process per batch
        indexing_options: Options to pass to DOCUMENT_INDEX_REQUESTED events
        user_id: Optional user identifier for authorization
    """

    repository_path: str = Field(
        ...,
        description="Local filesystem path or Git URL",
        examples=["/path/to/repo", "https://github.com/org/repo"],
        min_length=1,
    )

    project_id: str = Field(
        ...,
        description="Project identifier",
        examples=["omniarchon", "project-123"],
        min_length=1,
    )

    scan_scope: EnumScanScope = Field(
        default=EnumScanScope.FULL,
        description="Scope of scan (full, incremental, selective)",
    )

    file_patterns: list[str] = Field(
        default_factory=lambda: ["**/*.py", "**/*.ts", "**/*.rs", "**/*.go"],
        description="Glob patterns for files to include",
        examples=[["**/*.py", "**/*.ts"]],
    )

    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/__pycache__/**",
            "**/node_modules/**",
            "**/.git/**",
        ],
        description="Glob patterns for files to exclude",
    )

    commit_sha: Optional[str] = Field(
        None,
        description="Git commit SHA to scan (HEAD if not specified)",
    )

    branch: Optional[str] = Field(
        None,
        description="Git branch to scan",
        examples=["main", "develop"],
    )

    batch_size: int = Field(
        default=50,
        description="Number of files to process per batch",
        ge=1,
        le=500,
    )

    indexing_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Options to pass to DOCUMENT_INDEX_REQUESTED events",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for authorization",
    )

    @field_validator("repository_path")
    @classmethod
    def validate_repository_path(cls, v: str) -> str:
        """Ensure repository_path is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("repository_path cannot be empty or whitespace")
        return v.strip()

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        """Ensure project_id is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("project_id cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "repository_path": "/Volumes/PRO-G40/Code/omniarchon",
                    "project_id": "omniarchon",
                    "scan_scope": "FULL",
                    "file_patterns": ["**/*.py", "**/*.ts"],
                    "exclude_patterns": ["**/__pycache__/**", "**/node_modules/**"],
                    "batch_size": 50,
                    "indexing_options": {
                        "skip_metadata_stamping": False,
                        "skip_vector_indexing": False,
                    },
                }
            ]
        },
    )


class ModelRepositoryScanCompletedPayload(BaseModel):
    """
    Payload for REPOSITORY_SCAN_COMPLETED event.

    Captures scan results including files discovered, files published,
    and scan statistics.

    Attributes:
        repository_path: Repository that was scanned
        project_id: Project identifier
        scan_scope: Scope of scan performed
        files_discovered: Total files discovered matching patterns
        files_published: Files published for indexing
        files_skipped: Files skipped (already indexed, excluded, etc.)
        batches_created: Number of batches created
        processing_time_ms: Total scan time in milliseconds
        commit_sha: Optional Git commit SHA scanned
        branch: Optional Git branch scanned
        file_summaries: Summary of discovered files
    """

    repository_path: str = Field(
        ...,
        description="Repository that was scanned",
    )

    project_id: str = Field(
        ...,
        description="Project identifier",
    )

    scan_scope: EnumScanScope = Field(
        ...,
        description="Scope of scan performed",
    )

    files_discovered: int = Field(
        ...,
        description="Total files discovered matching patterns",
        ge=0,
    )

    files_published: int = Field(
        ...,
        description="Files published for indexing",
        ge=0,
    )

    files_skipped: int = Field(
        default=0,
        description="Files skipped (already indexed, excluded, etc.)",
        ge=0,
    )

    batches_created: int = Field(
        ...,
        description="Number of batches created",
        ge=0,
    )

    processing_time_ms: float = Field(
        ...,
        description="Total scan time in milliseconds",
        ge=0.0,
    )

    commit_sha: Optional[str] = Field(
        None,
        description="Git commit SHA scanned",
    )

    branch: Optional[str] = Field(
        None,
        description="Git branch scanned",
    )

    file_summaries: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Summary of discovered files",
        examples=[
            [
                {"path": "src/api.py", "size": 12345, "language": "python"},
                {"path": "src/utils.ts", "size": 6789, "language": "typescript"},
            ]
        ],
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "repository_path": "/Volumes/PRO-G40/Code/omniarchon",
                    "project_id": "omniarchon",
                    "scan_scope": "FULL",
                    "files_discovered": 245,
                    "files_published": 240,
                    "files_skipped": 5,
                    "batches_created": 5,
                    "processing_time_ms": 5432.1,
                    "commit_sha": "a1b2c3d4",
                    "branch": "main",
                    "file_summaries": [
                        {"path": "src/api.py", "size": 12345, "language": "python"}
                    ],
                }
            ]
        },
    )


class ModelRepositoryScanFailedPayload(BaseModel):
    """
    Payload for REPOSITORY_SCAN_FAILED event.

    Captures failure information including error details, operation context,
    and retry eligibility.

    Attributes:
        repository_path: Repository that failed to scan
        project_id: Optional project identifier
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether the operation can be retried
        retry_count: Number of retries attempted
        processing_time_ms: Time taken before failure in milliseconds
        files_processed_before_failure: Number of files successfully processed before failure
        error_details: Additional error context
        suggested_action: Recommended action to resolve the error
    """

    repository_path: str = Field(
        ...,
        description="Repository that failed to scan",
    )

    project_id: Optional[str] = Field(
        None,
        description="Project identifier",
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        examples=[
            "Repository not found at path: /invalid/path",
            "Permission denied accessing repository",
            "No files matching patterns found",
        ],
        min_length=1,
    )

    error_code: EnumCrawlerErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    retry_allowed: bool = Field(
        ...,
        description="Whether the operation can be retried",
        examples=[True, False],
    )

    retry_count: int = Field(
        default=0,
        description="Number of retries attempted",
        ge=0,
        examples=[0, 1, 2, 3],
    )

    processing_time_ms: float = Field(
        ...,
        description="Time taken before failure in milliseconds",
        ge=0.0,
        examples=[456.7, 1234.5],
    )

    files_processed_before_failure: int = Field(
        default=0,
        description="Number of files successfully processed before failure",
        ge=0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
        examples=[
            {
                "exception_type": "FileNotFoundError",
                "path": "/invalid/path",
                "stack_trace": "...",
            }
        ],
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action to resolve the error",
        examples=[
            "Verify repository path exists and is accessible",
            "Check file patterns are valid glob patterns",
            "Ensure sufficient permissions to read repository",
        ],
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "repository_path": "/invalid/path",
                    "project_id": "omniarchon",
                    "error_message": "Repository not found at path: /invalid/path",
                    "error_code": "REPOSITORY_NOT_FOUND",
                    "retry_allowed": False,
                    "retry_count": 0,
                    "processing_time_ms": 123.4,
                    "files_processed_before_failure": 0,
                    "error_details": {
                        "exception_type": "FileNotFoundError",
                        "path": "/invalid/path",
                    },
                    "suggested_action": "Verify repository path exists and is accessible",
                }
            ]
        },
    )


class RepositoryCrawlerEventHelpers:
    """
    Helper methods for creating and managing Repository Crawler events.

    Provides factory methods to create properly-formed event envelopes
    with correct topic routing, correlation tracking, and serialization.
    """

    # Topic routing configuration
    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN = "intelligence"
    PATTERN = "event"
    VERSION = "v1"

    @staticmethod
    def create_scan_requested_event(
        payload: ModelRepositoryScanRequestPayload,
        correlation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create REPOSITORY_SCAN_REQUESTED event envelope.

        Args:
            payload: Request payload with scan parameters
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
                "event_type": f"omninode.{RepositoryCrawlerEventHelpers.DOMAIN}.{RepositoryCrawlerEventHelpers.PATTERN}.repository_scan_requested.{RepositoryCrawlerEventHelpers.VERSION}",
                "service": RepositoryCrawlerEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "repository-crawler-1",
                "causation_id": None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_scan_completed_event(
        payload: ModelRepositoryScanCompletedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create REPOSITORY_SCAN_COMPLETED event envelope.

        Args:
            payload: Completion payload with scan results
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
                "event_type": f"omninode.{RepositoryCrawlerEventHelpers.DOMAIN}.{RepositoryCrawlerEventHelpers.PATTERN}.repository_scan_completed.{RepositoryCrawlerEventHelpers.VERSION}",
                "service": RepositoryCrawlerEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "repository-crawler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def create_scan_failed_event(
        payload: ModelRepositoryScanFailedPayload,
        correlation_id: UUID,
        causation_id: Optional[UUID] = None,
        source_instance: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create REPOSITORY_SCAN_FAILED event envelope.

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
                "event_type": f"omninode.{RepositoryCrawlerEventHelpers.DOMAIN}.{RepositoryCrawlerEventHelpers.PATTERN}.repository_scan_failed.{RepositoryCrawlerEventHelpers.VERSION}",
                "service": RepositoryCrawlerEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "repository-crawler-1",
                "causation_id": str(causation_id) if causation_id else None,
            },
        )

        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(
        event_type: EnumRepositoryCrawlerEventType, environment: str = "development"
    ) -> str:
        """
        Generate Kafka topic name for event type.

        Topic Format: {env}.{service}.{domain}.{event_type}.{version}

        Args:
            event_type: Type of repository crawler event
            environment: Environment (development, staging, production)

        Returns:
            Kafka topic name
        """
        env_prefix = "dev" if environment == "development" else environment
        event_suffix = event_type.value.replace("_", "-").lower()

        return f"{env_prefix}.{RepositoryCrawlerEventHelpers.SERVICE_PREFIX}.{RepositoryCrawlerEventHelpers.DOMAIN}.{event_suffix}.{RepositoryCrawlerEventHelpers.VERSION}"

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
        if "repository_scan_requested" in event_type:
            payload = ModelRepositoryScanRequestPayload(**payload_data)
            return (
                EnumRepositoryCrawlerEventType.REPOSITORY_SCAN_REQUESTED.value,
                payload,
            )

        elif "repository_scan_completed" in event_type:
            payload = ModelRepositoryScanCompletedPayload(**payload_data)
            return (
                EnumRepositoryCrawlerEventType.REPOSITORY_SCAN_COMPLETED.value,
                payload,
            )

        elif "repository_scan_failed" in event_type:
            payload = ModelRepositoryScanFailedPayload(**payload_data)
            return (
                EnumRepositoryCrawlerEventType.REPOSITORY_SCAN_FAILED.value,
                payload,
            )

        else:
            raise ValueError(f"Unknown event type: {event_type}")


# ============================================================================
# Convenience Functions
# ============================================================================


def create_request_event(
    repository_path: str,
    project_id: str,
    scan_scope: EnumScanScope = EnumScanScope.FULL,
    file_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
    batch_size: int = 50,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """
    Convenience function to create REPOSITORY_SCAN_REQUESTED event.

    Args:
        repository_path: Local filesystem path or Git URL
        project_id: Project identifier
        scan_scope: Scope of scan
        file_patterns: Optional glob patterns for files to include
        exclude_patterns: Optional glob patterns for files to exclude
        batch_size: Number of files to process per batch
        correlation_id: Optional correlation ID

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelRepositoryScanRequestPayload(
        repository_path=repository_path,
        project_id=project_id,
        scan_scope=scan_scope,
        file_patterns=file_patterns or ["**/*.py", "**/*.ts", "**/*.rs", "**/*.go"],
        exclude_patterns=exclude_patterns
        or ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"],
        batch_size=batch_size,
    )

    return RepositoryCrawlerEventHelpers.create_scan_requested_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_completed_event(
    repository_path: str,
    project_id: str,
    scan_scope: EnumScanScope,
    files_discovered: int,
    files_published: int,
    batches_created: int,
    processing_time_ms: float,
    correlation_id: UUID,
    files_skipped: int = 0,
    file_summaries: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Convenience function to create REPOSITORY_SCAN_COMPLETED event.

    Args:
        repository_path: Repository that was scanned
        project_id: Project identifier
        scan_scope: Scope of scan performed
        files_discovered: Total files discovered
        files_published: Files published for indexing
        batches_created: Number of batches created
        processing_time_ms: Processing time in milliseconds
        correlation_id: Correlation ID from request
        files_skipped: Optional files skipped count
        file_summaries: Optional file summaries

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelRepositoryScanCompletedPayload(
        repository_path=repository_path,
        project_id=project_id,
        scan_scope=scan_scope,
        files_discovered=files_discovered,
        files_published=files_published,
        files_skipped=files_skipped,
        batches_created=batches_created,
        processing_time_ms=processing_time_ms,
        file_summaries=file_summaries or [],
    )

    return RepositoryCrawlerEventHelpers.create_scan_completed_event(
        payload=payload,
        correlation_id=correlation_id,
    )


def create_failed_event(
    repository_path: str,
    error_message: str,
    error_code: EnumCrawlerErrorCode,
    correlation_id: UUID,
    project_id: Optional[str] = None,
    retry_allowed: bool = True,
    processing_time_ms: float = 0.0,
    error_details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Convenience function to create REPOSITORY_SCAN_FAILED event.

    Args:
        repository_path: Repository that failed to scan
        error_message: Human-readable error message
        error_code: Machine-readable error code
        correlation_id: Correlation ID from request
        project_id: Optional project identifier
        retry_allowed: Whether retry is allowed
        processing_time_ms: Processing time before failure
        error_details: Optional error details

    Returns:
        Event envelope dictionary ready for publishing
    """
    payload = ModelRepositoryScanFailedPayload(
        repository_path=repository_path,
        project_id=project_id,
        error_message=error_message,
        error_code=error_code,
        retry_allowed=retry_allowed,
        processing_time_ms=processing_time_ms,
        error_details=error_details or {},
    )

    return RepositoryCrawlerEventHelpers.create_scan_failed_event(
        payload=payload,
        correlation_id=correlation_id,
    )
