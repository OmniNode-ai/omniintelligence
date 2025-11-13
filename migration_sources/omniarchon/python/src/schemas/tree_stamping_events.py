"""
Tree Stamping Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for automated tree discovery, metadata stamping, and indexing:
- TREE_DISCOVERY_REQUESTED/COMPLETED/FAILED: Discover project file structure
- STAMPING_GENERATE_REQUESTED/COMPLETED/FAILED: Generate metadata and intelligence
- TREE_INDEX_REQUESTED/COMPLETED/FAILED: Index metadata in Qdrant and Memgraph

ONEX Compliance:
- Model-based naming: ModelTree{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation

Created: 2025-10-27
Purpose: Event-driven tree stamping automation
Reference: EVENT_BUS_ARCHITECTURE.md, AUTOMATED_TREE_STAMPING.md
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import event envelope (adjust path based on actual location)
try:
    from ...events.models.model_event_envelope import ModelEventEnvelope
except ImportError:
    # Fallback for different import structures
    try:
        from events.models.model_event_envelope import ModelEventEnvelope
    except ImportError:
        # Stub for development
        class ModelEventEnvelope(BaseModel):
            payload: Any
            correlation_id: UUID
            source_tool: str
            metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Enums
# ============================================================================


class EnumTreeEventType(str, Enum):
    """Event types for tree stamping operations."""

    # Tree Discovery
    TREE_DISCOVERY_REQUESTED = "TREE_DISCOVERY_REQUESTED"
    TREE_DISCOVERY_COMPLETED = "TREE_DISCOVERY_COMPLETED"
    TREE_DISCOVERY_FAILED = "TREE_DISCOVERY_FAILED"

    # Stamping Generation
    STAMPING_GENERATE_REQUESTED = "STAMPING_GENERATE_REQUESTED"
    STAMPING_GENERATE_COMPLETED = "STAMPING_GENERATE_COMPLETED"
    STAMPING_GENERATE_FAILED = "STAMPING_GENERATE_FAILED"

    # Tree Indexing
    TREE_INDEX_REQUESTED = "TREE_INDEX_REQUESTED"
    TREE_INDEX_COMPLETED = "TREE_INDEX_COMPLETED"
    TREE_INDEX_FAILED = "TREE_INDEX_FAILED"


class EnumTreeErrorCode(str, Enum):
    """Error codes for tree discovery operations."""

    INVALID_PATH = "INVALID_PATH"
    PATH_NOT_FOUND = "PATH_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    MAX_FILES_EXCEEDED = "MAX_FILES_EXCEEDED"
    MAX_DEPTH_EXCEEDED = "MAX_DEPTH_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class EnumStampingErrorCode(str, Enum):
    """Error codes for stamping generation operations."""

    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_EMPTY = "FILE_EMPTY"
    INVALID_CONTENT = "INVALID_CONTENT"
    ENCODING_ERROR = "ENCODING_ERROR"
    HASHING_FAILED = "HASHING_FAILED"
    INTELLIGENCE_SERVICE_ERROR = "INTELLIGENCE_SERVICE_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class EnumIndexingErrorCode(str, Enum):
    """Error codes for indexing operations."""

    QDRANT_UNAVAILABLE = "QDRANT_UNAVAILABLE"
    MEMGRAPH_UNAVAILABLE = "MEMGRAPH_UNAVAILABLE"
    INVALID_METADATA = "INVALID_METADATA"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    VECTOR_GENERATION_FAILED = "VECTOR_GENERATION_FAILED"
    GRAPH_CREATION_FAILED = "GRAPH_CREATION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================================
# Tree Discovery Event Payloads
# ============================================================================


class ModelTreeDiscoveryRequestedPayload(BaseModel):
    """
    Payload for TREE_DISCOVERY_REQUESTED event.

    Attributes:
        project_path: Absolute path to project root directory
        project_name: Human-readable project identifier
        include_tests: Include test files in discovery
        include_hidden: Include hidden files/directories (starting with .)
        exclude_patterns: Glob patterns to exclude (e.g., *.pyc, node_modules)
        max_depth: Maximum directory depth to traverse
        max_files: Maximum number of files to discover
        correlation_id: Unique ID for tracking this request across events
    """

    project_path: str = Field(
        ...,
        description="Absolute path to project root directory",
        examples=["/Users/dev/projects/omniarchon", "/home/user/code/myproject"],
        min_length=1,
    )

    project_name: str = Field(
        ...,
        description="Human-readable project identifier",
        examples=["omniarchon", "my-api-project"],
        min_length=1,
        max_length=255,
    )

    include_tests: bool = Field(
        default=True, description="Include test files in discovery"
    )

    include_hidden: bool = Field(
        default=False, description="Include hidden files/directories (starting with .)"
    )

    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.pyc",
            "__pycache__",
            "node_modules",
            ".git",
            "*.log",
        ],
        description="Glob patterns to exclude from discovery",
        examples=[["*.pyc", "__pycache__", "node_modules", ".git"]],
    )

    max_depth: int = Field(
        default=100,
        description="Maximum directory depth to traverse",
        ge=1,
        le=1000,
    )

    max_files: int = Field(
        default=10000,
        description="Maximum number of files to discover",
        ge=1,
        le=100000,
    )

    correlation_id: UUID = Field(
        default_factory=uuid4, description="Unique ID for tracking this request"
    )

    @field_validator("project_path", "project_name")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelFileInfo(BaseModel):
    """Metadata for a discovered file (v2.0.0 with Phase 1 inline content support).

    Phase 0 (path-based): Only path fields populated, handler reads from filesystem
    Phase 1 (inline content): content field populated, handler uses provided content
    """

    # Core file metadata (Phase 0 - path-based)
    path: str = Field(..., description="Absolute file path")
    relative_path: str = Field(..., description="Path relative to project root")
    size_bytes: int = Field(..., description="File size in bytes", ge=0)
    extension: str = Field(..., description="File extension (e.g., .py, .ts)")
    language: Optional[str] = Field(
        None,
        description="Detected programming language",
        examples=["python", "typescript"],
    )
    last_modified: datetime = Field(..., description="Last modification timestamp")

    # Phase 1 inline content fields (optional for backward compatibility)
    content: Optional[str] = Field(
        None,
        description="File content for inline processing (Phase 1)",
    )
    content_strategy: Optional[str] = Field(
        "path",
        description="Content delivery strategy: 'inline' (Phase 1) or 'path' (Phase 0)",
        examples=["inline", "path"],
    )
    content_encoding: Optional[str] = Field(
        "utf-8",
        description="Content encoding (for inline content)",
    )
    checksum: Optional[str] = Field(
        None,
        description="SHA256 checksum for content integrity validation",
        examples=["abc123def456789..."],
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeDiscoveryCompletedPayload(BaseModel):
    """
    Payload for TREE_DISCOVERY_COMPLETED event.

    Attributes:
        project_path: Project root path that was discovered
        project_name: Project identifier
        files_discovered: Total number of files discovered
        files_tracked: List of file metadata (limited to first 1000 for payload size)
        total_size_bytes: Total size of all discovered files
        discovery_time_ms: Time taken to complete discovery
        cache_hit: Whether results were retrieved from cache
        correlation_id: Tracking ID from original request
    """

    project_path: str = Field(..., description="Project root path that was discovered")

    project_name: str = Field(..., description="Project identifier")

    files_discovered: int = Field(
        ..., description="Total number of files discovered", ge=0
    )

    files_tracked: list[ModelFileInfo] = Field(
        default_factory=list,
        description="List of discovered file metadata (limited to 1000 for payload size)",
        max_length=1000,
    )

    total_size_bytes: int = Field(
        ..., description="Total size of all discovered files", ge=0
    )

    discovery_time_ms: float = Field(
        ..., description="Time taken to complete discovery", ge=0.0
    )

    cache_hit: bool = Field(
        default=False, description="Whether results were retrieved from cache"
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    model_config = ConfigDict(frozen=True)


class ModelTreeDiscoveryFailedPayload(BaseModel):
    """
    Payload for TREE_DISCOVERY_FAILED event.

    Attributes:
        project_path: Project path that failed discovery
        project_name: Project identifier
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed for this failure
        processing_time_ms: Time taken before failure
        error_details: Additional error context (stack trace, etc.)
        correlation_id: Tracking ID from original request
    """

    project_path: str = Field(..., description="Project path that failed discovery")

    project_name: str = Field(..., description="Project identifier")

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    error_code: EnumTreeErrorCode = Field(
        ..., description="Machine-readable error code"
    )

    retry_allowed: bool = Field(
        ..., description="Whether retry is allowed for this failure"
    )

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Stamping Generation Event Payloads
# ============================================================================


class ModelStampingGenerateRequestedPayload(BaseModel):
    """
    Payload for STAMPING_GENERATE_REQUESTED event.

    Attributes:
        file_path: Absolute path to file for stamping
        project_name: Project context for the file
        content_hash: Pre-computed content hash (optional, computed if not provided)
        force_regenerate: Bypass cache and force regeneration
        include_intelligence: Include quality scoring and ONEX compliance
        correlation_id: Tracking ID linking to tree discovery
    """

    file_path: str = Field(
        ...,
        description="Absolute path to file for stamping",
        examples=["/project/src/main.py"],
        min_length=1,
    )

    project_name: str = Field(
        ..., description="Project context for the file", min_length=1, max_length=255
    )

    content_hash: Optional[str] = Field(
        None,
        description="Pre-computed content hash (BLAKE3)",
        examples=["abc123def456..."],
        min_length=64,
        max_length=64,
    )

    force_regenerate: bool = Field(
        default=False, description="Bypass cache and force regeneration"
    )

    include_intelligence: bool = Field(
        default=True, description="Include quality scoring and ONEX compliance"
    )

    correlation_id: UUID = Field(
        ..., description="Tracking ID linking to tree discovery"
    )

    @field_validator("file_path", "project_name")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    model_config = ConfigDict(frozen=False)


class ModelStampingGenerateCompletedPayload(BaseModel):
    """
    Payload for STAMPING_GENERATE_COMPLETED event.

    Attributes:
        file_path: File path that was stamped
        blake3_hash: BLAKE3 content hash for deduplication
        metadata: Generated file metadata (language, entities, etc.)
        intelligence_score: Quality score from intelligence service (0.0-1.0)
        onex_compliance: ONEX architectural compliance score (0.0-1.0)
        processing_time_ms: Time taken to generate stamping
        cache_hit: Whether result was retrieved from cache
        correlation_id: Tracking ID from original request
    """

    file_path: str = Field(..., description="File path that was stamped")

    blake3_hash: str = Field(
        ...,
        description="BLAKE3 content hash for deduplication",
        examples=["abc123def456..."],
        min_length=64,
        max_length=64,
    )

    metadata: dict[str, Any] = Field(
        ...,
        description="Generated file metadata",
        examples=[
            {
                "language": "python",
                "entity_count": 15,
                "dependency_count": 8,
                "complexity": {"cyclomatic": 12, "cognitive": 8},
            }
        ],
    )

    intelligence_score: float = Field(
        ..., description="Quality score from intelligence service", ge=0.0, le=1.0
    )

    onex_compliance: float = Field(
        ..., description="ONEX architectural compliance score", ge=0.0, le=1.0
    )

    processing_time_ms: float = Field(
        ..., description="Time taken to generate stamping", ge=0.0
    )

    cache_hit: bool = Field(
        default=False, description="Whether result was retrieved from cache"
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    model_config = ConfigDict(frozen=True)


class ModelStampingGenerateFailedPayload(BaseModel):
    """
    Payload for STAMPING_GENERATE_FAILED event.

    Attributes:
        file_path: File path that failed stamping
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
        error_details: Additional error context
        correlation_id: Tracking ID from original request
    """

    file_path: str = Field(..., description="File path that failed stamping")

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    error_code: EnumStampingErrorCode = Field(
        ..., description="Machine-readable error code"
    )

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Tree Indexing Event Payloads
# ============================================================================


class ModelTreeIndexRequestedPayload(BaseModel):
    """
    Payload for TREE_INDEX_REQUESTED event.

    Attributes:
        file_path: File path to index
        blake3_hash: BLAKE3 content hash
        metadata: File metadata from stamping
        intelligence_score: Quality score
        onex_compliance: ONEX compliance score
        project_name: Project context
        index_targets: Which indexes to update (qdrant, memgraph, both)
        correlation_id: Tracking ID from original request
    """

    file_path: str = Field(..., description="File path to index")

    blake3_hash: str = Field(
        ..., description="BLAKE3 content hash", min_length=64, max_length=64
    )

    metadata: dict[str, Any] = Field(..., description="File metadata from stamping")

    intelligence_score: float = Field(..., description="Quality score", ge=0.0, le=1.0)

    onex_compliance: float = Field(
        ..., description="ONEX compliance score", ge=0.0, le=1.0
    )

    project_name: str = Field(..., description="Project context")

    index_targets: list[str] = Field(
        default_factory=lambda: ["qdrant", "memgraph"],
        description="Which indexes to update",
        examples=[["qdrant", "memgraph"], ["qdrant"], ["memgraph"]],
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    @field_validator("index_targets")
    @classmethod
    def validate_targets(cls, v: list[str]) -> list[str]:
        """Ensure valid index targets."""
        valid_targets = {"qdrant", "memgraph"}
        for target in v:
            if target not in valid_targets:
                raise ValueError(
                    f"Invalid index target: {target}. Must be one of {valid_targets}"
                )
        return v

    model_config = ConfigDict(frozen=False)


class ModelTreeIndexCompletedPayload(BaseModel):
    """
    Payload for TREE_INDEX_COMPLETED event.

    Attributes:
        file_path: File path that was indexed
        blake3_hash: BLAKE3 content hash
        indexed_in: List of indexes updated
        qdrant_point_id: Qdrant point ID (if indexed in Qdrant)
        memgraph_node_id: Memgraph node ID (if indexed in Memgraph)
        processing_time_ms: Time taken to complete indexing
        correlation_id: Tracking ID from original request
    """

    file_path: str = Field(..., description="File path that was indexed")

    blake3_hash: str = Field(
        ..., description="BLAKE3 content hash", min_length=64, max_length=64
    )

    indexed_in: list[str] = Field(
        ..., description="List of indexes updated", examples=[["qdrant", "memgraph"]]
    )

    qdrant_point_id: Optional[UUID] = Field(
        None, description="Qdrant point ID (if indexed in Qdrant)"
    )

    memgraph_node_id: Optional[int] = Field(
        None, description="Memgraph node ID (if indexed in Memgraph)"
    )

    processing_time_ms: float = Field(
        ..., description="Time taken to complete indexing", ge=0.0
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    model_config = ConfigDict(frozen=True)


class ModelTreeIndexFailedPayload(BaseModel):
    """
    Payload for TREE_INDEX_FAILED event.

    Attributes:
        file_path: File path that failed indexing
        blake3_hash: BLAKE3 content hash
        error_message: Human-readable error description
        error_code: Machine-readable error code
        retry_allowed: Whether retry is allowed
        processing_time_ms: Time taken before failure
        error_details: Additional error context
        correlation_id: Tracking ID from original request
    """

    file_path: str = Field(..., description="File path that failed indexing")

    blake3_hash: str = Field(
        ..., description="BLAKE3 content hash", min_length=64, max_length=64
    )

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Machine-readable error code"
    )

    retry_allowed: bool = Field(..., description="Whether retry is allowed")

    processing_time_ms: float = Field(
        ..., description="Time taken before failure", ge=0.0
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    correlation_id: UUID = Field(..., description="Tracking ID from original request")

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Event Helpers
# ============================================================================


class TreeStampingEventHelpers:
    """Helper methods for creating tree stamping events."""

    SERVICE_PREFIX = "archon-intelligence"
    DOMAIN_TREE = "tree"
    DOMAIN_STAMPING = "stamping"
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
        """Create event envelope following ONEX pattern."""
        envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="archon-intelligence",
            metadata={
                "event_type": event_type,
                "service": TreeStampingEventHelpers.SERVICE_PREFIX,
                "instance_id": source_instance or "tree-stamping-1",
                "causation_id": str(causation_id) if causation_id else None,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        return envelope.model_dump()

    @staticmethod
    def get_kafka_topic(event_type: EnumTreeEventType, environment: str = "dev") -> str:
        """
        Generate Kafka topic name for event type.

        Args:
            event_type: Event type enum
            environment: Environment prefix (dev, staging, prod)

        Returns:
            Fully-qualified Kafka topic name

        Examples:
            >>> TreeStampingEventHelpers.get_kafka_topic(
            ...     EnumTreeEventType.TREE_DISCOVERY_REQUESTED
            ... )
            'dev.archon-intelligence.tree.discover.v1'
        """
        # Map event type to topic suffix
        topic_map = {
            EnumTreeEventType.TREE_DISCOVERY_REQUESTED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.tree.discover.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.TREE_DISCOVERY_COMPLETED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.tree.discover-completed.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.TREE_DISCOVERY_FAILED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.tree.discover-failed.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.STAMPING_GENERATE_REQUESTED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.stamping.generate.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.STAMPING_GENERATE_COMPLETED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.stamping.generate-completed.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.STAMPING_GENERATE_FAILED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.stamping.generate-failed.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.TREE_INDEX_REQUESTED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.tree.index.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.TREE_INDEX_COMPLETED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.tree.index-completed.{TreeStampingEventHelpers.VERSION}",
            EnumTreeEventType.TREE_INDEX_FAILED: f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.tree.index-failed.{TreeStampingEventHelpers.VERSION}",
        }

        return topic_map.get(
            event_type,
            f"{environment}.{TreeStampingEventHelpers.SERVICE_PREFIX}.unknown.{TreeStampingEventHelpers.VERSION}",
        )


# ============================================================================
# Convenience Functions
# ============================================================================


def create_tree_discovery_request(
    project_path: str,
    project_name: str,
    include_tests: bool = True,
    include_hidden: bool = False,
    exclude_patterns: Optional[list[str]] = None,
    correlation_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """
    Create TREE_DISCOVERY_REQUESTED event.

    Args:
        project_path: Absolute path to project root
        project_name: Project identifier
        include_tests: Include test files
        include_hidden: Include hidden files
        exclude_patterns: Glob patterns to exclude
        correlation_id: Tracking ID (generated if not provided)

    Returns:
        Event envelope dict ready for Kafka publishing

    Example:
        >>> event = create_tree_discovery_request(
        ...     project_path='/home/dev/myproject',
        ...     project_name='myproject'
        ... )
        >>> # Publish to Kafka
        >>> await producer.send(
        ...     'dev.archon-intelligence.tree.discover.v1',
        ...     value=json.dumps(event).encode()
        ... )
    """
    payload = ModelTreeDiscoveryRequestedPayload(
        project_path=project_path,
        project_name=project_name,
        include_tests=include_tests,
        include_hidden=include_hidden,
        exclude_patterns=exclude_patterns or [],
        correlation_id=correlation_id or uuid4(),
    )

    event_type = TreeStampingEventHelpers.get_kafka_topic(
        EnumTreeEventType.TREE_DISCOVERY_REQUESTED
    )

    return TreeStampingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=payload.correlation_id
    )


def create_stamping_generate_request(
    file_path: str,
    project_name: str,
    correlation_id: UUID,
    content_hash: Optional[str] = None,
    force_regenerate: bool = False,
    include_intelligence: bool = True,
) -> dict[str, Any]:
    """
    Create STAMPING_GENERATE_REQUESTED event.

    Args:
        file_path: Absolute path to file
        project_name: Project context
        correlation_id: Tracking ID from tree discovery
        content_hash: Pre-computed BLAKE3 hash (optional)
        force_regenerate: Bypass cache
        include_intelligence: Include quality scoring

    Returns:
        Event envelope dict ready for Kafka publishing
    """
    payload = ModelStampingGenerateRequestedPayload(
        file_path=file_path,
        project_name=project_name,
        content_hash=content_hash,
        force_regenerate=force_regenerate,
        include_intelligence=include_intelligence,
        correlation_id=correlation_id,
    )

    event_type = TreeStampingEventHelpers.get_kafka_topic(
        EnumTreeEventType.STAMPING_GENERATE_REQUESTED
    )

    return TreeStampingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


def create_tree_index_request(
    file_path: str,
    blake3_hash: str,
    metadata: dict[str, Any],
    intelligence_score: float,
    onex_compliance: float,
    project_name: str,
    correlation_id: UUID,
    index_targets: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Create TREE_INDEX_REQUESTED event.

    Args:
        file_path: File path to index
        blake3_hash: BLAKE3 content hash
        metadata: File metadata from stamping
        intelligence_score: Quality score
        onex_compliance: ONEX compliance score
        project_name: Project context
        correlation_id: Tracking ID
        index_targets: Which indexes to update

    Returns:
        Event envelope dict ready for Kafka publishing
    """
    payload = ModelTreeIndexRequestedPayload(
        file_path=file_path,
        blake3_hash=blake3_hash,
        metadata=metadata,
        intelligence_score=intelligence_score,
        onex_compliance=onex_compliance,
        project_name=project_name,
        index_targets=index_targets or ["qdrant", "memgraph"],
        correlation_id=correlation_id,
    )

    event_type = TreeStampingEventHelpers.get_kafka_topic(
        EnumTreeEventType.TREE_INDEX_REQUESTED
    )

    return TreeStampingEventHelpers._create_envelope(
        event_type=event_type, payload=payload, correlation_id=correlation_id
    )


# ============================================================================
# DLQ (Dead Letter Queue) Helpers
# ============================================================================


class DLQEvent(BaseModel):
    """Dead Letter Queue event wrapper for failed events."""

    original_topic: str = Field(..., description="Original Kafka topic")
    original_partition: int = Field(..., description="Original partition number")
    original_offset: int = Field(..., description="Original offset")
    original_payload: dict[str, Any] = Field(..., description="Original event payload")
    error_type: str = Field(..., description="Exception class name")
    error_message: str = Field(..., description="Error message")
    error_stack_trace: Optional[str] = Field(None, description="Full stack trace")
    retry_count: int = Field(..., description="Number of retry attempts")
    failed_at: datetime = Field(..., description="Timestamp of final failure")
    consumer_group: str = Field(..., description="Consumer group that failed")
    consumer_instance: str = Field(..., description="Consumer instance ID")
    correlation_id: UUID = Field(..., description="Original correlation ID for tracing")

    model_config = ConfigDict(frozen=True)


def create_dlq_event(
    original_topic: str,
    original_partition: int,
    original_offset: int,
    original_payload: dict[str, Any],
    error: Exception,
    retry_count: int,
    consumer_group: str,
    consumer_instance: str,
    correlation_id: UUID,
) -> DLQEvent:
    """
    Create Dead Letter Queue event for failed processing.

    Args:
        original_topic: Kafka topic where event originated
        original_partition: Partition number
        original_offset: Offset in partition
        original_payload: Original event data
        error: Exception that caused failure
        retry_count: Number of retries attempted
        consumer_group: Consumer group name
        consumer_instance: Consumer instance ID
        correlation_id: Original correlation ID

    Returns:
        DLQEvent ready for publishing to {original_topic}.dlq
    """
    import traceback

    return DLQEvent(
        original_topic=original_topic,
        original_partition=original_partition,
        original_offset=original_offset,
        original_payload=original_payload,
        error_type=type(error).__name__,
        error_message=str(error),
        error_stack_trace=traceback.format_exc(),
        retry_count=retry_count,
        failed_at=datetime.now(UTC),
        consumer_group=consumer_group,
        consumer_instance=consumer_instance,
        correlation_id=correlation_id,
    )
