"""
Tree Stamping Event Contracts - ONEX Compliant Kafka Event Schemas

Event schemas for Tree + Stamping integration operations:
- INDEX_PROJECT_REQUESTED/COMPLETED/FAILED: Project indexing with full pipeline
- TREE_DISCOVERED/FAILED: Tree discovery phase (Phase 3 intermediate event)
- TREE_STAMPED/FAILED: Intelligence generation phase (Phase 3 intermediate event)
- TREE_INDEXED/FAILED: Vector/graph indexing phase (Phase 3 intermediate event)
- SEARCH_FILES_REQUESTED/COMPLETED/FAILED: Semantic file search
- GET_STATUS_REQUESTED/COMPLETED/FAILED: Project indexing status check

Event Flow (Phase 3 Decoupled Pipeline):
    INDEX_PROJECT_REQUESTED
      ↓
    TREE_DISCOVERED (discovery: <5s for 1K files)
      ↓
    TREE_STAMPED (stamping: <30s for 1K files)
      ↓
    TREE_INDEXED (indexing: <60s for 1K files)
      ↓
    INDEX_PROJECT_COMPLETED

Performance Targets (1000 files):
- Tree Discovery: <5s (OnexTree file enumeration)
- Intelligence Generation: <30s (quality scoring, ONEX classification, semantic analysis)
- Vector/Graph Indexing: <60s (Qdrant + Memgraph + cache warming)
- Total Pipeline: <95s end-to-end (excludes network I/O)

ONEX Compliance:
- Model-based naming: ModelTreeStamping{Operation}{Type}Payload
- Strong typing with Pydantic v2
- Event envelope integration with ModelEventEnvelope
- Kafka topic routing following event bus architecture
- Serialization/deserialization helpers
- Comprehensive validation
- Schema versioning (v1 suffix in topics)

Created: 2025-10-24
Updated: 2025-10-26 (Phase 3 intermediate events)
Purpose: Tree + Stamping Integration Event Adapter
Reference: EVENT_BUS_ARCHITECTURE.md, bridge_intelligence_events.py pattern
"""

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ModelEventEnvelope imported locally in methods to avoid circular import issue
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Enums
# ============================================================================


class EnumTreeStampingEventType(str, Enum):
    """Event types for tree stamping operations."""

    # Index Project
    INDEX_PROJECT_REQUESTED = "INDEX_PROJECT_REQUESTED"
    INDEX_PROJECT_COMPLETED = "INDEX_PROJECT_COMPLETED"
    INDEX_PROJECT_FAILED = "INDEX_PROJECT_FAILED"

    # Intermediate Pipeline Events (Phase 3)
    TREE_DISCOVERED = "TREE_DISCOVERED"
    TREE_DISCOVERED_FAILED = "TREE_DISCOVERED_FAILED"
    TREE_STAMPED = "TREE_STAMPED"
    TREE_STAMPED_FAILED = "TREE_STAMPED_FAILED"
    TREE_INDEXED = "TREE_INDEXED"
    TREE_INDEXED_FAILED = "TREE_INDEXED_FAILED"

    # Search Files
    SEARCH_FILES_REQUESTED = "SEARCH_FILES_REQUESTED"
    SEARCH_FILES_COMPLETED = "SEARCH_FILES_COMPLETED"
    SEARCH_FILES_FAILED = "SEARCH_FILES_FAILED"

    # Get Status
    GET_STATUS_REQUESTED = "GET_STATUS_REQUESTED"
    GET_STATUS_COMPLETED = "GET_STATUS_COMPLETED"
    GET_STATUS_FAILED = "GET_STATUS_FAILED"

    def __str__(self) -> str:
        """Return just the enum value when converted to string."""
        return self.value


class EnumTreeStampingOperationType(str, Enum):
    """Type of tree stamping operation."""

    PROJECT_INDEXING = "PROJECT_INDEXING"
    FILE_SEARCH = "FILE_SEARCH"
    STATUS_CHECK = "STATUS_CHECK"


class EnumIndexingErrorCode(str, Enum):
    """Error codes for indexing operations."""

    INVALID_INPUT = "INVALID_INPUT"
    TREE_DISCOVERY_FAILED = "TREE_DISCOVERY_FAILED"
    INTELLIGENCE_GENERATION_FAILED = "INTELLIGENCE_GENERATION_FAILED"
    STAMPING_FAILED = "STAMPING_FAILED"
    INDEXING_FAILED = "INDEXING_FAILED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class EnumIndexingStatus(str, Enum):
    """Status of project indexing."""

    INDEXED = "INDEXED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# Index Project Event Payloads
# ============================================================================


class ModelTreeStampingIndexProjectRequestPayload(BaseModel):
    """
    Payload for INDEX_PROJECT_REQUESTED event.

    Triggers full project indexing pipeline:
    1. Tree discovery (OnexTree) → File enumeration
    2. Intelligence generation (MetadataStamping) → Semantic analysis + quality scoring
    3. Metadata stamping (Stamping) → Metadata enrichment
    4. Vector indexing (Qdrant) → Semantic search
    5. Graph indexing (Memgraph) → Relationship mapping
    6. Cache warming (Valkey) → Fast lookups

    Attributes:
        project_path: Absolute path to project root directory
        project_name: Unique project identifier (slug)
        include_tests: Include test files in indexing
        force_reindex: Force reindex even if already indexed
    """

    project_path: str = Field(
        ...,
        description="Absolute path to project root directory",
        examples=["/Volumes/PRO-G40/Code/omniarchon"],
        min_length=1,
    )

    project_name: str = Field(
        ...,
        description="Unique project identifier (slug)",
        examples=["omniarchon", "omninode-bridge"],
        min_length=1,
        max_length=100,
    )

    include_tests: bool = Field(
        default=True,
        description="Include test files in indexing",
    )

    force_reindex: bool = Field(
        default=False,
        description="Force reindex even if already indexed",
    )

    @field_validator("project_path")
    @classmethod
    def validate_project_path(cls, v: str) -> str:
        """
        Validate path format to prevent path traversal attacks.

        This validator performs format-only validation without filesystem I/O:
        1. Ensures path is absolute (starts with "/")
        2. Prevents path traversal patterns (no ".." components)

        Security: Protects against paths like /tmp/./../../etc/passwd
        Note: Events must be portable - no filesystem dependencies

        Args:
            v: Path string to validate

        Returns:
            Validated path string

        Raises:
            ValueError: If path format is invalid or contains security risks
        """
        # Ensure path is absolute (format validation only)
        if not v.startswith("/"):
            raise ValueError(f"project_path must be an absolute path, got: {v}")

        # Prevent path traversal patterns (security validation)
        if ".." in v:
            raise ValueError(
                f"project_path must not contain path traversal (..) patterns, got: {v}"
            )

        # Path format is valid - no filesystem I/O required
        return v

    model_config = ConfigDict(frozen=False)


class ModelTreeStampingIndexProjectCompletedPayload(BaseModel):
    """
    Payload for INDEX_PROJECT_COMPLETED event.

    Attributes:
        project_name: Name of indexed project
        files_discovered: Number of files discovered by tree service
        files_indexed: Number of files successfully indexed
        vector_indexed: Number of vectors indexed in Qdrant
        graph_indexed: Number of nodes/edges created in Memgraph
        cache_warmed: Whether cache was pre-warmed
        duration_ms: Total indexing duration in milliseconds
        errors: List of errors encountered (non-fatal)
        warnings: List of warnings (non-fatal issues)
    """

    project_name: str = Field(..., description="Name of indexed project")

    files_discovered: int = Field(
        default=0,
        ge=0,
        description="Number of files discovered by tree service",
    )

    files_indexed: int = Field(
        default=0,
        ge=0,
        description="Number of files successfully indexed",
    )

    vector_indexed: int = Field(
        default=0,
        ge=0,
        description="Number of vectors indexed in Qdrant",
    )

    graph_indexed: int = Field(
        default=0,
        ge=0,
        description="Number of nodes/edges created in Memgraph",
    )

    cache_warmed: bool = Field(
        default=False,
        description="Whether cache was pre-warmed with common queries",
    )

    duration_ms: float = Field(
        ..., description="Total indexing duration in milliseconds", ge=0.0
    )

    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered during indexing (non-fatal)",
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings (non-fatal issues)",
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingIndexProjectFailedPayload(BaseModel):
    """
    Payload for INDEX_PROJECT_FAILED event.

    Attributes:
        project_name: Name of project that failed to index
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context
    """

    project_name: str = Field(..., description="Name of project that failed to index")

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Error code for classification"
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        min_length=1,
    )

    duration_ms: float = Field(
        ..., description="Processing time before failure (ms)", ge=0.0
    )

    retry_recommended: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    retry_after_seconds: int = Field(
        default=60,
        ge=0,
        description="Recommended retry delay in seconds",
    )

    error_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context (exception type, stack trace, etc.)",
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Intermediate Pipeline Event Payloads (Phase 3)
# ============================================================================


class ModelTreeStampingFileInfo(BaseModel):
    """
    Information about a discovered file.

    Attributes:
        file_path: Absolute path to file
        relative_path: Path relative to project root
        language: Programming language detected
        size_bytes: File size in bytes
        last_modified: Last modification timestamp
    """

    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field(..., description="Path relative to project root")
    language: str = Field(..., description="Programming language detected")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    last_modified: datetime = Field(..., description="Last modification timestamp")

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingStampedFileInfo(BaseModel):
    """
    Information about a file that has been stamped with intelligence.

    Attributes:
        file_path: Absolute path to file
        relative_path: Path relative to project root
        quality_score: Code quality score (0.0-1.0)
        onex_type: ONEX node type (Effect, Compute, Reducer, Orchestrator)
        complexity_score: Code complexity score (0.0-1.0)
        concepts: Semantic concepts extracted
        stamping_duration_ms: Time taken to generate intelligence
    """

    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field(..., description="Path relative to project root")
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Code quality score (0.0-1.0)"
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type (Effect, Compute, Reducer, Orchestrator)",
    )
    complexity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Code complexity score (0.0-1.0)"
    )
    concepts: List[str] = Field(
        default_factory=list, description="Semantic concepts extracted"
    )
    stamping_duration_ms: float = Field(
        ..., ge=0.0, description="Time taken to generate intelligence (ms)"
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingTreeDiscoveredPayload(BaseModel):
    """
    Payload for TREE_DISCOVERED event.

    Emitted after tree discovery phase completes successfully.
    Contains complete file enumeration and language breakdown.

    Timing Target: <5s for projects with <1000 files

    Expected Consumer Behavior:
    - Intelligence service picks up for stamping phase
    - Validates file list before proceeding
    - May filter files based on language or size

    Attributes:
        project_name: Unique project identifier
        project_path: Absolute path to project root
        files_discovered: List of discovered file information
        discovery_duration_ms: Tree discovery execution time
        total_files: Total number of files discovered
        language_breakdown: File counts per language
    """

    project_name: str = Field(..., description="Unique project identifier")

    project_path: str = Field(
        ...,
        description="Absolute path to project root directory",
        min_length=1,
    )

    files_discovered: List[ModelTreeStampingFileInfo] = Field(
        ..., description="List of discovered file information"
    )

    discovery_duration_ms: float = Field(
        ..., ge=0.0, description="Tree discovery execution time (ms)"
    )

    total_files: int = Field(..., ge=0, description="Total number of files discovered")

    language_breakdown: Dict[str, int] = Field(
        ...,
        description="File counts per language (e.g., {'python': 42, 'typescript': 18})",
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingTreeDiscoveredFailedPayload(BaseModel):
    """
    Payload for TREE_DISCOVERED_FAILED event.

    Attributes:
        project_name: Name of project that failed discovery
        project_path: Path that was being discovered
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context
    """

    project_name: str = Field(..., description="Name of project that failed discovery")

    project_path: str = Field(..., description="Path that was being discovered")

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Error code for classification"
    )

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    duration_ms: float = Field(
        ..., description="Processing time before failure (ms)", ge=0.0
    )

    retry_recommended: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    retry_after_seconds: int = Field(
        default=60, ge=0, description="Recommended retry delay in seconds"
    )

    error_details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingTreeStampedPayload(BaseModel):
    """
    Payload for TREE_STAMPED event.

    Emitted after intelligence generation and stamping phase completes.
    Contains quality scores, ONEX classifications, and semantic analysis.

    Timing Target: <30s for projects with <1000 files

    Expected Consumer Behavior:
    - Indexing service picks up for vector/graph indexing
    - Uses quality scores for ranking
    - Stores ONEX types for architectural queries

    Attributes:
        project_name: Unique project identifier
        files_stamped: Number of files successfully stamped
        stamped_files: List of stamped file information
        stamping_duration_ms: Intelligence generation execution time
        intelligence_summary: Aggregate intelligence metrics
    """

    project_name: str = Field(..., description="Unique project identifier")

    files_stamped: int = Field(
        ..., ge=0, description="Number of files successfully stamped"
    )

    stamped_files: List[ModelTreeStampingStampedFileInfo] = Field(
        ..., description="List of stamped file information"
    )

    stamping_duration_ms: float = Field(
        ..., ge=0.0, description="Intelligence generation execution time (ms)"
    )

    intelligence_summary: Dict[str, Any] = Field(
        ...,
        description="Aggregate intelligence metrics (avg_quality, onex_distribution, etc.)",
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingTreeStampedFailedPayload(BaseModel):
    """
    Payload for TREE_STAMPED_FAILED event.

    Attributes:
        project_name: Name of project that failed stamping
        files_attempted: Number of files attempted
        files_succeeded: Number of files successfully stamped before failure
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context
    """

    project_name: str = Field(..., description="Name of project that failed stamping")

    files_attempted: int = Field(..., ge=0, description="Number of files attempted")

    files_succeeded: int = Field(
        ..., ge=0, description="Number of files successfully stamped before failure"
    )

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Error code for classification"
    )

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    duration_ms: float = Field(
        ..., description="Processing time before failure (ms)", ge=0.0
    )

    retry_recommended: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    retry_after_seconds: int = Field(
        default=60, ge=0, description="Recommended retry delay in seconds"
    )

    error_details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingTreeIndexedPayload(BaseModel):
    """
    Payload for TREE_INDEXED event.

    Emitted after vector and graph indexing phase completes.
    Contains indexing statistics and cache warming status.

    Timing Target: <60s for projects with <1000 files

    Expected Consumer Behavior:
    - Search service can now query indexed project
    - Status endpoint shows project as fully indexed
    - Cache is pre-warmed for common queries

    Attributes:
        project_name: Unique project identifier
        vector_indexed: Number of vectors indexed in Qdrant
        graph_indexed: Number of graph nodes/edges created in Memgraph
        cache_warmed: Whether cache was pre-warmed
        indexing_duration_ms: Indexing execution time
        qdrant_points_created: Qdrant vector points created
        memgraph_nodes_created: Memgraph nodes created
    """

    project_name: str = Field(..., description="Unique project identifier")

    vector_indexed: int = Field(
        ..., ge=0, description="Number of vectors indexed in Qdrant"
    )

    graph_indexed: int = Field(
        ..., ge=0, description="Number of graph nodes/edges created in Memgraph"
    )

    cache_warmed: bool = Field(
        default=False, description="Whether cache was pre-warmed with common queries"
    )

    indexing_duration_ms: float = Field(
        ..., ge=0.0, description="Indexing execution time (ms)"
    )

    qdrant_points_created: int = Field(
        ..., ge=0, description="Qdrant vector points created"
    )

    memgraph_nodes_created: int = Field(..., ge=0, description="Memgraph nodes created")

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingTreeIndexedFailedPayload(BaseModel):
    """
    Payload for TREE_INDEXED_FAILED event.

    Attributes:
        project_name: Name of project that failed indexing
        vectors_attempted: Number of vectors attempted
        vectors_succeeded: Number of vectors successfully indexed before failure
        graph_items_attempted: Number of graph items attempted
        graph_items_succeeded: Number of graph items successfully created before failure
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context
    """

    project_name: str = Field(..., description="Name of project that failed indexing")

    vectors_attempted: int = Field(..., ge=0, description="Number of vectors attempted")

    vectors_succeeded: int = Field(
        ..., ge=0, description="Number of vectors successfully indexed before failure"
    )

    graph_items_attempted: int = Field(
        ..., ge=0, description="Number of graph items attempted"
    )

    graph_items_succeeded: int = Field(
        ...,
        ge=0,
        description="Number of graph items successfully created before failure",
    )

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Error code for classification"
    )

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    duration_ms: float = Field(
        ..., description="Processing time before failure (ms)", ge=0.0
    )

    retry_recommended: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    retry_after_seconds: int = Field(
        default=60, ge=0, description="Recommended retry delay in seconds"
    )

    error_details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Search Files Event Payloads
# ============================================================================


class ModelTreeStampingSearchFilesRequestPayload(BaseModel):
    """
    Payload for SEARCH_FILES_REQUESTED event.

    Search strategy:
    1. Check cache (Valkey) → fast lookup
    2. If miss: Query Qdrant (vector similarity)
    3. Filter by quality score
    4. Rank by composite score (semantic + quality + compliance)
    5. Cache result (TTL: 5 minutes)

    Attributes:
        query: Natural language search query
        projects: Optional list of project filters
        min_quality_score: Minimum quality threshold (0.0-1.0)
        limit: Maximum results to return (1-100)
    """

    query: str = Field(
        ...,
        description="Natural language search query",
        examples=["authentication patterns", "JWT token validation"],
        min_length=1,
    )

    projects: Optional[List[str]] = Field(
        default=None,
        description="Optional list of project names to filter by",
        examples=[["omniarchon", "omninode-bridge"]],
    )

    min_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum quality threshold (0.0-1.0)",
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum results to return",
    )

    model_config = ConfigDict(frozen=False)


class ModelTreeStampingFileMatch(BaseModel):
    """
    Single file search result with ranking and metadata.

    Attributes:
        file_path: Absolute path to file
        relative_path: Path relative to project root
        project_name: Project this file belongs to
        confidence: Confidence score for match (0.0-1.0)
        quality_score: Code quality score (0.0-1.0)
        onex_type: ONEX node type (Effect, Compute, Reducer, Orchestrator)
        concepts: Semantic concepts extracted from file
        themes: High-level themes
        why: Explanation of why this file matches the query
    """

    file_path: str = Field(..., description="Absolute path to file")
    relative_path: str = Field(..., description="Path relative to project root")
    project_name: str = Field(..., description="Project this file belongs to")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for match (0.0-1.0)"
    )
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Code quality score (0.0-1.0)"
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type (Effect, Compute, Reducer, Orchestrator)",
    )
    concepts: List[str] = Field(
        default_factory=list, description="Semantic concepts extracted from file"
    )
    themes: List[str] = Field(default_factory=list, description="High-level themes")
    why: str = Field(..., description="Explanation of why this file matches the query")

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingSearchFilesCompletedPayload(BaseModel):
    """
    Payload for SEARCH_FILES_COMPLETED event.

    Attributes:
        results: List of matching files
        query_time_ms: Query execution time in milliseconds
        cache_hit: Whether result was served from cache
        total_results: Total matching files (before limit applied)
    """

    results: List[ModelTreeStampingFileMatch] = Field(
        default_factory=list, description="List of matching files"
    )

    query_time_ms: float = Field(
        ..., description="Query execution time in milliseconds", ge=0.0
    )

    cache_hit: bool = Field(
        default=False, description="Whether result was served from cache"
    )

    total_results: int = Field(
        ..., ge=0, description="Total matching files (before limit applied)"
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingSearchFilesFailedPayload(BaseModel):
    """
    Payload for SEARCH_FILES_FAILED event.

    Attributes:
        error_code: Error code for classification
        error_message: Human-readable error description
        query_time_ms: Processing time before failure
        retry_recommended: Whether retry is recommended
        error_details: Additional error context
    """

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Error code for classification"
    )

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    query_time_ms: float = Field(
        ..., description="Processing time before failure (ms)", ge=0.0
    )

    retry_recommended: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    error_details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error context"
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Get Status Event Payloads
# ============================================================================


class ModelTreeStampingGetStatusRequestPayload(BaseModel):
    """
    Payload for GET_STATUS_REQUESTED event.

    Attributes:
        project_name: Optional project name filter (returns all if None)
    """

    project_name: Optional[str] = Field(
        default=None,
        description="Optional project name filter (returns all if None)",
    )

    model_config = ConfigDict(frozen=False)


class ModelTreeStampingProjectStatus(BaseModel):
    """
    Status of a single project.

    Attributes:
        project_name: Project identifier
        indexed: Whether project has been indexed
        file_count: Number of files indexed
        status: Indexing status (indexed, in_progress, failed, unknown)
        last_indexed_at: Timestamp of last indexing
    """

    project_name: str = Field(..., description="Project identifier")
    indexed: bool = Field(..., description="Whether project has been indexed")
    file_count: int = Field(default=0, ge=0, description="Number of files indexed")
    status: EnumIndexingStatus = Field(
        default=EnumIndexingStatus.UNKNOWN,
        description="Indexing status",
    )
    last_indexed_at: Optional[datetime] = Field(
        default=None, description="Timestamp of last indexing"
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingGetStatusCompletedPayload(BaseModel):
    """
    Payload for GET_STATUS_COMPLETED event.

    Attributes:
        projects: List of project statuses
        query_time_ms: Query execution time in milliseconds
    """

    projects: List[ModelTreeStampingProjectStatus] = Field(
        default_factory=list, description="List of project statuses"
    )

    query_time_ms: float = Field(
        ..., description="Query execution time in milliseconds", ge=0.0
    )

    model_config = ConfigDict(frozen=True)


class ModelTreeStampingGetStatusFailedPayload(BaseModel):
    """
    Payload for GET_STATUS_FAILED event.

    Attributes:
        error_code: Error code for classification
        error_message: Human-readable error description
        query_time_ms: Processing time before failure
        retry_recommended: Whether retry is recommended
    """

    error_code: EnumIndexingErrorCode = Field(
        ..., description="Error code for classification"
    )

    error_message: str = Field(
        ..., description="Human-readable error description", min_length=1
    )

    query_time_ms: float = Field(
        ..., description="Processing time before failure (ms)", ge=0.0
    )

    retry_recommended: bool = Field(
        default=True, description="Whether retry is recommended"
    )

    model_config = ConfigDict(frozen=True)


# ============================================================================
# Event Envelope Helper Functions
# ============================================================================


def create_index_project_completed(
    project_name: str,
    files_discovered: int,
    files_indexed: int,
    vector_indexed: int,
    graph_indexed: int,
    cache_warmed: bool,
    duration_ms: float,
    correlation_id: UUID,
    errors: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> "ModelEventEnvelope":
    """Create INDEX_PROJECT_COMPLETED event envelope."""
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingIndexProjectCompletedPayload(
        project_name=project_name,
        files_discovered=files_discovered,
        files_indexed=files_indexed,
        vector_indexed=vector_indexed,
        graph_indexed=graph_indexed,
        cache_warmed=cache_warmed,
        duration_ms=duration_ms,
        errors=errors or [],
        warnings=warnings or [],
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.INDEX_PROJECT_COMPLETED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
        }
    )


def create_index_project_failed(
    project_name: str,
    error_code: EnumIndexingErrorCode,
    error_message: str,
    duration_ms: float,
    correlation_id: UUID,
    retry_recommended: bool = True,
    retry_after_seconds: int = 60,
    error_details: Optional[Dict[str, Any]] = None,
) -> "ModelEventEnvelope":
    """Create INDEX_PROJECT_FAILED event envelope."""
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingIndexProjectFailedPayload(
        project_name=project_name,
        error_code=error_code,
        error_message=error_message,
        duration_ms=duration_ms,
        retry_recommended=retry_recommended,
        retry_after_seconds=retry_after_seconds,
        error_details=error_details or {},
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.INDEX_PROJECT_FAILED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
        }
    )


def create_search_files_completed(
    results: List[Dict[str, Any]],
    query_time_ms: float,
    total_results: int,
    correlation_id: UUID,
    cache_hit: bool = False,
) -> "ModelEventEnvelope":
    """Create SEARCH_FILES_COMPLETED event envelope."""
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    file_matches = [ModelTreeStampingFileMatch(**result) for result in results]

    payload = ModelTreeStampingSearchFilesCompletedPayload(
        results=file_matches,
        query_time_ms=query_time_ms,
        cache_hit=cache_hit,
        total_results=total_results,
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.SEARCH_FILES_COMPLETED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
        }
    )


def create_search_files_failed(
    error_code: EnumIndexingErrorCode,
    error_message: str,
    query_time_ms: float,
    correlation_id: UUID,
    retry_recommended: bool = True,
    error_details: Optional[Dict[str, Any]] = None,
) -> "ModelEventEnvelope":
    """Create SEARCH_FILES_FAILED event envelope."""
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingSearchFilesFailedPayload(
        error_code=error_code,
        error_message=error_message,
        query_time_ms=query_time_ms,
        retry_recommended=retry_recommended,
        error_details=error_details or {},
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.SEARCH_FILES_FAILED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
        }
    )


def create_get_status_completed(
    projects: List[Dict[str, Any]],
    query_time_ms: float,
    correlation_id: UUID,
) -> "ModelEventEnvelope":
    """Create GET_STATUS_COMPLETED event envelope."""
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    project_statuses = [
        ModelTreeStampingProjectStatus(**project) for project in projects
    ]

    payload = ModelTreeStampingGetStatusCompletedPayload(
        projects=project_statuses,
        query_time_ms=query_time_ms,
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.GET_STATUS_COMPLETED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
        }
    )


def create_get_status_failed(
    error_code: EnumIndexingErrorCode,
    error_message: str,
    query_time_ms: float,
    correlation_id: UUID,
    retry_recommended: bool = True,
) -> "ModelEventEnvelope":
    """Create GET_STATUS_FAILED event envelope."""
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingGetStatusFailedPayload(
        error_code=error_code,
        error_message=error_message,
        query_time_ms=query_time_ms,
        retry_recommended=retry_recommended,
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.GET_STATUS_FAILED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
        }
    )


# ============================================================================
# Intermediate Pipeline Event Factory Functions (Phase 3)
# ============================================================================


def create_tree_discovered(
    project_name: str,
    project_path: str,
    files_discovered: List[Dict[str, Any]],
    discovery_duration_ms: float,
    total_files: int,
    language_breakdown: Dict[str, int],
    correlation_id: UUID,
) -> "ModelEventEnvelope":
    """
    Create TREE_DISCOVERED event envelope.

    Emitted after tree discovery phase completes successfully.
    Schema version: v1 (topic: dev.archon-intelligence.tree.discovered.v1)

    Args:
        project_name: Unique project identifier
        project_path: Absolute path to project root
        files_discovered: List of discovered file information dicts
        discovery_duration_ms: Tree discovery execution time
        total_files: Total number of files discovered
        language_breakdown: File counts per language
        correlation_id: Request correlation ID

    Returns:
        Event envelope ready for Kafka publishing
    """
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    file_info_list = [ModelTreeStampingFileInfo(**file) for file in files_discovered]

    payload = ModelTreeStampingTreeDiscoveredPayload(
        project_name=project_name,
        project_path=project_path,
        files_discovered=file_info_list,
        discovery_duration_ms=discovery_duration_ms,
        total_files=total_files,
        language_breakdown=language_breakdown,
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.TREE_DISCOVERED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
            "metadata": {
                "schema_version": "v1",
                "topic": "dev.archon-intelligence.tree.discovered.v1",
            },
        }
    )


def create_tree_discovered_failed(
    project_name: str,
    project_path: str,
    error_code: EnumIndexingErrorCode,
    error_message: str,
    duration_ms: float,
    correlation_id: UUID,
    retry_recommended: bool = True,
    retry_after_seconds: int = 60,
    error_details: Optional[Dict[str, Any]] = None,
) -> "ModelEventEnvelope":
    """
    Create TREE_DISCOVERED_FAILED event envelope.

    Emitted when tree discovery phase fails.
    Schema version: v1 (topic: dev.archon-intelligence.tree.discovered.failed.v1)

    Args:
        project_name: Name of project that failed discovery
        project_path: Path that was being discovered
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        correlation_id: Request correlation ID
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context

    Returns:
        Event envelope ready for Kafka publishing
    """
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingTreeDiscoveredFailedPayload(
        project_name=project_name,
        project_path=project_path,
        error_code=error_code,
        error_message=error_message,
        duration_ms=duration_ms,
        retry_recommended=retry_recommended,
        retry_after_seconds=retry_after_seconds,
        error_details=error_details or {},
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.TREE_DISCOVERED_FAILED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
            "metadata": {
                "schema_version": "v1",
                "topic": "dev.archon-intelligence.tree.discovered.failed.v1",
            },
        }
    )


def create_tree_stamped(
    project_name: str,
    files_stamped: int,
    stamped_files: List[Dict[str, Any]],
    stamping_duration_ms: float,
    intelligence_summary: Dict[str, Any],
    correlation_id: UUID,
) -> "ModelEventEnvelope":
    """
    Create TREE_STAMPED event envelope.

    Emitted after intelligence generation and stamping phase completes.
    Schema version: v1 (topic: dev.archon-intelligence.tree.stamped.v1)

    Args:
        project_name: Unique project identifier
        files_stamped: Number of files successfully stamped
        stamped_files: List of stamped file information dicts
        stamping_duration_ms: Intelligence generation execution time
        intelligence_summary: Aggregate intelligence metrics
        correlation_id: Request correlation ID

    Returns:
        Event envelope ready for Kafka publishing
    """
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    stamped_file_list = [
        ModelTreeStampingStampedFileInfo(**file) for file in stamped_files
    ]

    payload = ModelTreeStampingTreeStampedPayload(
        project_name=project_name,
        files_stamped=files_stamped,
        stamped_files=stamped_file_list,
        stamping_duration_ms=stamping_duration_ms,
        intelligence_summary=intelligence_summary,
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.TREE_STAMPED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
            "metadata": {
                "schema_version": "v1",
                "topic": "dev.archon-intelligence.tree.stamped.v1",
            },
        }
    )


def create_tree_stamped_failed(
    project_name: str,
    files_attempted: int,
    files_succeeded: int,
    error_code: EnumIndexingErrorCode,
    error_message: str,
    duration_ms: float,
    correlation_id: UUID,
    retry_recommended: bool = True,
    retry_after_seconds: int = 60,
    error_details: Optional[Dict[str, Any]] = None,
) -> "ModelEventEnvelope":
    """
    Create TREE_STAMPED_FAILED event envelope.

    Emitted when intelligence generation/stamping phase fails.
    Schema version: v1 (topic: dev.archon-intelligence.tree.stamped.failed.v1)

    Args:
        project_name: Name of project that failed stamping
        files_attempted: Number of files attempted
        files_succeeded: Number of files successfully stamped before failure
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        correlation_id: Request correlation ID
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context

    Returns:
        Event envelope ready for Kafka publishing
    """
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingTreeStampedFailedPayload(
        project_name=project_name,
        files_attempted=files_attempted,
        files_succeeded=files_succeeded,
        error_code=error_code,
        error_message=error_message,
        duration_ms=duration_ms,
        retry_recommended=retry_recommended,
        retry_after_seconds=retry_after_seconds,
        error_details=error_details or {},
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.TREE_STAMPED_FAILED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
            "metadata": {
                "schema_version": "v1",
                "topic": "dev.archon-intelligence.tree.stamped.failed.v1",
            },
        }
    )


def create_tree_indexed(
    project_name: str,
    vector_indexed: int,
    graph_indexed: int,
    cache_warmed: bool,
    indexing_duration_ms: float,
    qdrant_points_created: int,
    memgraph_nodes_created: int,
    correlation_id: UUID,
) -> "ModelEventEnvelope":
    """
    Create TREE_INDEXED event envelope.

    Emitted after vector and graph indexing phase completes.
    Schema version: v1 (topic: dev.archon-intelligence.tree.indexed.v1)

    Args:
        project_name: Unique project identifier
        vector_indexed: Number of vectors indexed in Qdrant
        graph_indexed: Number of graph nodes/edges created in Memgraph
        cache_warmed: Whether cache was pre-warmed
        indexing_duration_ms: Indexing execution time
        qdrant_points_created: Qdrant vector points created
        memgraph_nodes_created: Memgraph nodes created
        correlation_id: Request correlation ID

    Returns:
        Event envelope ready for Kafka publishing
    """
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingTreeIndexedPayload(
        project_name=project_name,
        vector_indexed=vector_indexed,
        graph_indexed=graph_indexed,
        cache_warmed=cache_warmed,
        indexing_duration_ms=indexing_duration_ms,
        qdrant_points_created=qdrant_points_created,
        memgraph_nodes_created=memgraph_nodes_created,
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.TREE_INDEXED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
            "metadata": {
                "schema_version": "v1",
                "topic": "dev.archon-intelligence.tree.indexed.v1",
            },
        }
    )


def create_tree_indexed_failed(
    project_name: str,
    vectors_attempted: int,
    vectors_succeeded: int,
    graph_items_attempted: int,
    graph_items_succeeded: int,
    error_code: EnumIndexingErrorCode,
    error_message: str,
    duration_ms: float,
    correlation_id: UUID,
    retry_recommended: bool = True,
    retry_after_seconds: int = 60,
    error_details: Optional[Dict[str, Any]] = None,
) -> "ModelEventEnvelope":
    """
    Create TREE_INDEXED_FAILED event envelope.

    Emitted when vector/graph indexing phase fails.
    Schema version: v1 (topic: dev.archon-intelligence.tree.indexed.failed.v1)

    Args:
        project_name: Name of project that failed indexing
        vectors_attempted: Number of vectors attempted
        vectors_succeeded: Number of vectors successfully indexed before failure
        graph_items_attempted: Number of graph items attempted
        graph_items_succeeded: Number of graph items successfully created before failure
        error_code: Error code for classification
        error_message: Human-readable error description
        duration_ms: Processing time before failure
        correlation_id: Request correlation ID
        retry_recommended: Whether retry is recommended
        retry_after_seconds: Recommended retry delay
        error_details: Additional error context

    Returns:
        Event envelope ready for Kafka publishing
    """
    # Local import to avoid circular dependency
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    payload = ModelTreeStampingTreeIndexedFailedPayload(
        project_name=project_name,
        vectors_attempted=vectors_attempted,
        vectors_succeeded=vectors_succeeded,
        graph_items_attempted=graph_items_attempted,
        graph_items_succeeded=graph_items_succeeded,
        error_code=error_code,
        error_message=error_message,
        duration_ms=duration_ms,
        retry_recommended=retry_recommended,
        retry_after_seconds=retry_after_seconds,
        error_details=error_details or {},
    )

    return ModelEventEnvelope.model_validate(
        {
            "event_id": uuid4(),
            "correlation_id": correlation_id,
            "event_type": EnumTreeStampingEventType.TREE_INDEXED_FAILED.value,
            "timestamp": datetime.now(UTC),
            "source": {
                "service": "archon-intelligence",
                "instance_id": "tree-stamping-handler",
            },
            "payload": payload.model_dump(),
            "metadata": {
                "schema_version": "v1",
                "topic": "dev.archon-intelligence.tree.indexed.failed.v1",
            },
        }
    )


__all__ = [
    # Enums
    "EnumTreeStampingEventType",
    "EnumTreeStampingOperationType",
    "EnumIndexingErrorCode",
    "EnumIndexingStatus",
    # Request Payloads
    "ModelTreeStampingIndexProjectRequestPayload",
    "ModelTreeStampingSearchFilesRequestPayload",
    "ModelTreeStampingGetStatusRequestPayload",
    # Response Payloads
    "ModelTreeStampingIndexProjectCompletedPayload",
    "ModelTreeStampingIndexProjectFailedPayload",
    "ModelTreeStampingSearchFilesCompletedPayload",
    "ModelTreeStampingSearchFilesFailedPayload",
    "ModelTreeStampingGetStatusCompletedPayload",
    "ModelTreeStampingGetStatusFailedPayload",
    # Intermediate Pipeline Payloads (Phase 3)
    "ModelTreeStampingFileInfo",
    "ModelTreeStampingStampedFileInfo",
    "ModelTreeStampingTreeDiscoveredPayload",
    "ModelTreeStampingTreeDiscoveredFailedPayload",
    "ModelTreeStampingTreeStampedPayload",
    "ModelTreeStampingTreeStampedFailedPayload",
    "ModelTreeStampingTreeIndexedPayload",
    "ModelTreeStampingTreeIndexedFailedPayload",
    # Sub-models
    "ModelTreeStampingFileMatch",
    "ModelTreeStampingProjectStatus",
    # Helper Functions
    "create_index_project_completed",
    "create_index_project_failed",
    "create_search_files_completed",
    "create_search_files_failed",
    "create_get_status_completed",
    "create_get_status_failed",
    # Intermediate Pipeline Factory Functions (Phase 3)
    "create_tree_discovered",
    "create_tree_discovered_failed",
    "create_tree_stamped",
    "create_tree_stamped_failed",
    "create_tree_indexed",
    "create_tree_indexed_failed",
]
