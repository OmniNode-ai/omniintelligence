"""
File Location Data Models

Pydantic models for file location indexing and search operations.
Provides request/response models for the Tree-Stamping Integration POC.

Performance Target: <5ms validation overhead per request
ONEX Pattern: Compute (pure data transformation and validation)
"""

from datetime import UTC, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ==============================================================================
# Request Models
# ==============================================================================


class ProjectIndexRequest(BaseModel):
    """
    Request to index a project's files with full intelligence pipeline.

    Pipeline:
    1. Tree discovery (OnexTree)
    2. Intelligence generation (Bridge)
    3. Metadata stamping (Stamping)
    4. Vector indexing (Qdrant)
    5. Graph indexing (Memgraph)
    6. Cache warming (Valkey)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    project_path: str = Field(
        ...,
        description="Absolute path to project directory",
        examples=["/Volumes/PRO-G40/Code/omniarchon"],
        min_length=1,
    )
    project_name: str = Field(
        ...,
        description="Project identifier (unique name)",
        examples=["omniarchon"],
        min_length=2,
    )
    include_tests: bool = Field(
        default=True,
        description="Whether to include test files in indexing",
    )
    force_reindex: bool = Field(
        default=False,
        description="Force reindexing even if already indexed",
    )

    @field_validator("project_path")
    @classmethod
    def validate_project_path(cls, v: str) -> str:
        """Ensure project path is absolute."""
        if not v.startswith("/"):
            raise ValueError("project_path must be absolute path starting with '/'")
        return v

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """Ensure project name is valid identifier."""
        if len(v) < 2:
            raise ValueError("project_name must be at least 2 characters")
        # Ensure no path separators in project name
        if "/" in v or "\\" in v:
            raise ValueError("project_name cannot contain path separators")
        return v


class FileSearchRequest(BaseModel):
    """
    Request to search for files across projects using semantic search.

    Search Strategy:
    - Semantic vector similarity (Qdrant)
    - Quality score filtering
    - Composite ranking (relevance + quality + compliance + recency)
    - Cache-first (5 min TTL)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description="Natural language search query",
        examples=["authentication module in omniarchon", "JWT token validation"],
        min_length=1,
    )
    projects: Optional[List[str]] = Field(
        default=None,
        description="Optional list of project names to filter by",
        examples=[["omniarchon", "omninode-bridge"]],
    )
    file_types: Optional[List[str]] = Field(
        default=None,
        description="Optional list of file extensions to filter by",
        examples=[[".py", ".ts", ".md"]],
    )
    min_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum quality score threshold (0.0-1.0)",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )

    @field_validator("file_types")
    @classmethod
    def validate_file_types(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Ensure file types start with a dot if provided."""
        if v is None:
            return v
        validated = []
        for ft in v:
            if not ft.startswith("."):
                validated.append(f".{ft}")
            else:
                validated.append(ft)
        return validated


class ProjectStatusRequest(BaseModel):
    """Request to get project indexing status."""

    model_config = ConfigDict(str_strip_whitespace=True)

    project_name: Optional[str] = Field(
        default=None,
        description="Optional project name filter (returns all if None)",
    )


# ==============================================================================
# Response Models
# ==============================================================================


class FileMatch(BaseModel):
    """
    Single file search result with ranking and metadata.

    Ranking Components:
    - Semantic relevance (40%)
    - Quality score (30%)
    - ONEX compliance (20%)
    - Recency (10%)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    file_path: str = Field(
        ...,
        description="Absolute path to file",
        examples=["/Volumes/PRO-G40/Code/omniarchon/src/services/auth/jwt_handler.py"],
    )
    relative_path: str = Field(
        ...,
        description="Path relative to project root",
        examples=["src/services/auth/jwt_handler.py"],
    )
    project_name: str = Field(
        ...,
        description="Project this file belongs to",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for match (0.0-1.0)",
    )
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Code quality score (0.0-1.0)",
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type (Effect, Compute, Reducer, Orchestrator)",
        examples=["effect", "compute", "reducer", "orchestrator"],
    )
    concepts: List[str] = Field(
        default_factory=list,
        description="Semantic concepts extracted from file",
        examples=[["authentication", "JWT", "security"]],
    )
    themes: List[str] = Field(
        default_factory=list,
        description="High-level themes",
        examples=[["security", "api"]],
    )
    why: str = Field(
        ...,
        description="Explanation of why this file matches the query",
    )

    @field_validator("onex_type")
    @classmethod
    def validate_onex_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate ONEX type if provided."""
        if v is None:
            return v
        valid_types = ["effect", "compute", "reducer", "orchestrator"]
        v_lower = v.lower()
        if v_lower not in valid_types:
            raise ValueError(f"onex_type must be one of {valid_types}, got '{v}'")
        return v_lower


class FileSearchResult(BaseModel):
    """
    Response from file search operation with ranked results.

    Performance:
    - Target (cold): <2s
    - Target (warm): <500ms
    - Cache TTL: 300s
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    success: bool = Field(
        ...,
        description="Whether search completed successfully",
    )
    results: List[FileMatch] = Field(
        default_factory=list,
        description="List of matching files",
    )
    query_time_ms: int = Field(
        ...,
        ge=0,
        description="Query execution time in milliseconds",
    )
    cache_hit: bool = Field(
        default=False,
        description="Whether result was served from cache",
    )
    total_results: int = Field(
        ...,
        ge=0,
        description="Total matching files (before limit applied)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if success=False",
    )


class ProjectIndexResult(BaseModel):
    """
    Response from project indexing operation.

    Performance Target: <5 minutes for 1000 files
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    success: bool = Field(
        ...,
        description="Whether indexing completed successfully",
    )
    project_name: str = Field(
        ...,
        description="Name of indexed project",
    )
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
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Total indexing duration in milliseconds",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered during indexing",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings (non-fatal issues)",
    )


class ProjectIndexStatus(BaseModel):
    """
    Status of project indexing.

    Data Sources:
    - Valkey cache: "file_location:project:{name}:status" (1 hour TTL)
    - Fallback: Query Qdrant for indexed files
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    project_name: str = Field(
        ...,
        description="Project identifier",
    )
    indexed: bool = Field(
        ...,
        description="Whether project has been indexed",
    )
    file_count: int = Field(
        default=0,
        ge=0,
        description="Number of files indexed",
    )
    indexed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last indexing",
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last update to index",
    )
    status: str = Field(
        default="unknown",
        description="Indexing status: 'indexed', 'in_progress', 'failed', 'unknown'",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of allowed values."""
        valid_statuses = ["indexed", "in_progress", "failed", "unknown"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}, got '{v}'")
        return v


# ==============================================================================
# Error Response Model
# ==============================================================================


class ErrorResponse(BaseModel):
    """
    Standard error response format for all file location operations.

    Example:
        >>> error = ErrorResponse(
        ...     error="Invalid project path",
        ...     error_code="INVALID_PROJECT_PATH",
        ...     details="Project path must be absolute and exist on filesystem"
        ... )
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    success: bool = Field(
        default=False,
        description="Always False for error responses",
    )
    error: str = Field(
        ...,
        description="Error message",
    )
    error_code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["INVALID_PROJECT_PATH", "SERVICE_UNAVAILABLE", "INDEXING_FAILED"],
    )
    details: Optional[str] = Field(
        default=None,
        description="Additional error details",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Error timestamp",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request correlation ID",
    )


# ==============================================================================
# Internal Models (for data exchange between modules)
# ==============================================================================


class FileMetadata(BaseModel):
    """
    Internal model for file metadata used in indexing pipeline.

    This is used between tree discovery, intelligence generation, and indexing modules.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    absolute_path: str = Field(..., description="Full file path")
    relative_path: str = Field(..., description="Path relative to project root")
    file_hash: str = Field(..., description="BLAKE3 hash of file content")
    project_name: str = Field(..., description="Project identifier")
    project_root: str = Field(..., description="Project root directory")
    file_type: str = Field(..., description="File extension (.py, .ts, etc.)")
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Code quality score (0.0-1.0)",
    )
    onex_compliance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="ONEX compliance score (0.0-1.0)",
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type",
    )
    concepts: List[str] = Field(
        default_factory=list,
        description="Semantic concepts",
    )
    themes: List[str] = Field(
        default_factory=list,
        description="High-level themes",
    )
    domains: List[str] = Field(
        default_factory=list,
        description="Domain classification",
    )
    pattern_types: List[str] = Field(
        default_factory=list,
        description="Pattern classifications",
    )
    indexed_at: Optional[datetime] = Field(
        default=None,
        description="Indexing timestamp",
    )
    last_modified: Optional[datetime] = Field(
        default=None,
        description="File modification time",
    )


class IndexingProgress(BaseModel):
    """
    Real-time progress tracking for indexing operations.

    Used for streaming progress updates during long-running indexing tasks.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    project_name: str = Field(..., description="Project being indexed")
    total_files: int = Field(..., ge=0, description="Total files to process")
    processed_files: int = Field(..., ge=0, description="Files processed so far")
    current_phase: str = Field(
        ...,
        description="Current indexing phase",
        examples=[
            "tree_discovery",
            "intelligence_generation",
            "stamping",
            "vector_indexing",
            "graph_indexing",
        ],
    )
    phase_progress: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Progress of current phase (0.0-1.0)",
    )
    estimated_remaining_ms: int = Field(
        ...,
        ge=0,
        description="Estimated time remaining in milliseconds",
    )
    errors_count: int = Field(
        default=0,
        ge=0,
        description="Number of errors encountered",
    )
    warnings_count: int = Field(
        default=0,
        ge=0,
        description="Number of warnings encountered",
    )


__all__ = [
    # Request models
    "ProjectIndexRequest",
    "FileSearchRequest",
    "ProjectStatusRequest",
    # Response models
    "FileSearchResult",
    "ProjectIndexResult",
    "ProjectIndexStatus",
    "ErrorResponse",
    # Result models
    "FileMatch",
    # Internal models
    "FileMetadata",
    "IndexingProgress",
]
