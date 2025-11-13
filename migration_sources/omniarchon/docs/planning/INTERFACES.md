# POC Tree Stamping Integration: Interface Definitions

**Status**: Contract Specification
**Purpose**: Define all interfaces BEFORE parallel execution
**Consumers**: All 5 parallel work streams (A, B, C, D, E)

---

## Overview

This document defines ALL interfaces and contracts for the POC Tree Stamping Integration. By defining these upfront, all 5 work streams can execute in parallel without blocking dependencies.

**Design Principle**: Interface-first, implementation-later

---

## 1. Data Models (Pydantic)

**Location**: `services/intelligence/src/models/file_location.py`

### Request Models

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


class ProjectIndexRequest(BaseModel):
    """Request to index a project's files."""

    project_path: str = Field(
        ...,
        description="Absolute path to project directory",
        example="/Volumes/PRO-G40/Code/omniarchon"
    )
    project_name: str = Field(
        ...,
        description="Project identifier (unique name)",
        example="omniarchon"
    )
    include_tests: bool = Field(
        default=True,
        description="Whether to include test files in indexing"
    )
    force_reindex: bool = Field(
        default=False,
        description="Force reindexing even if already indexed"
    )

    @validator("project_path")
    def validate_project_path(cls, v):
        """Ensure project path is absolute."""
        if not v.startswith("/"):
            raise ValueError("project_path must be absolute path")
        return v

    @validator("project_name")
    def validate_project_name(cls, v):
        """Ensure project name is valid identifier."""
        if not v or len(v) < 2:
            raise ValueError("project_name must be at least 2 characters")
        return v


class FileSearchRequest(BaseModel):
    """Request to search for files across projects."""

    query: str = Field(
        ...,
        description="Natural language search query",
        example="authentication module in omniarchon"
    )
    projects: Optional[List[str]] = Field(
        default=None,
        description="Optional list of project names to filter by",
        example=["omniarchon", "omninode-bridge"]
    )
    file_types: Optional[List[str]] = Field(
        default=None,
        description="Optional list of file extensions to filter by",
        example=[".py", ".ts", ".md"]
    )
    min_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum quality score threshold (0.0-1.0)"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )


class ProjectStatusRequest(BaseModel):
    """Request to get project indexing status."""

    project_name: Optional[str] = Field(
        default=None,
        description="Optional project name filter (returns all if None)"
    )
```

### Response Models

```python
class FileMatch(BaseModel):
    """Single file search result."""

    file_path: str = Field(
        ...,
        description="Absolute path to file",
        example="src/services/auth/jwt_handler.py"
    )
    relative_path: str = Field(
        ...,
        description="Path relative to project root",
        example="src/services/auth/jwt_handler.py"
    )
    project_name: str = Field(
        ...,
        description="Project this file belongs to"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for match (0.0-1.0)"
    )
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Code quality score (0.0-1.0)"
    )
    onex_type: Optional[str] = Field(
        default=None,
        description="ONEX node type (Effect, Compute, Reducer, Orchestrator)"
    )
    concepts: List[str] = Field(
        default_factory=list,
        description="Semantic concepts extracted from file",
        example=["authentication", "JWT", "security"]
    )
    themes: List[str] = Field(
        default_factory=list,
        description="High-level themes",
        example=["security", "api"]
    )
    why: str = Field(
        ...,
        description="Explanation of why this file matches the query"
    )


class FileSearchResult(BaseModel):
    """Response from file search operation."""

    success: bool = Field(..., description="Whether search completed successfully")
    results: List[FileMatch] = Field(
        default_factory=list,
        description="List of matching files"
    )
    query_time_ms: int = Field(
        ...,
        description="Query execution time in milliseconds"
    )
    cache_hit: bool = Field(
        default=False,
        description="Whether result was served from cache"
    )
    total_results: int = Field(
        ...,
        description="Total matching files (before limit applied)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if success=False"
    )


class ProjectIndexResult(BaseModel):
    """Response from project indexing operation."""

    success: bool = Field(..., description="Whether indexing completed successfully")
    project_name: str = Field(..., description="Name of indexed project")
    files_discovered: int = Field(
        default=0,
        description="Number of files discovered by tree service"
    )
    files_indexed: int = Field(
        default=0,
        description="Number of files successfully indexed"
    )
    vector_indexed: int = Field(
        default=0,
        description="Number of vectors indexed in Qdrant"
    )
    graph_indexed: int = Field(
        default=0,
        description="Number of nodes/edges created in Memgraph"
    )
    cache_warmed: bool = Field(
        default=False,
        description="Whether cache was pre-warmed with common queries"
    )
    duration_ms: int = Field(
        ...,
        description="Total indexing duration in milliseconds"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered during indexing"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings (non-fatal issues)"
    )


class ProjectIndexStatus(BaseModel):
    """Status of project indexing."""

    project_name: str = Field(..., description="Project identifier")
    indexed: bool = Field(..., description="Whether project has been indexed")
    file_count: int = Field(
        default=0,
        description="Number of files indexed"
    )
    indexed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last indexing"
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last update to index"
    )
    status: str = Field(
        default="unknown",
        description="Indexing status: 'indexed', 'in_progress', 'failed', 'unknown'"
    )
```

---

## 2. TreeStampingBridge Interface

**Location**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

### Main Interface

```python
from typing import List, Optional
from models.file_location import (
    ProjectIndexRequest,
    ProjectIndexResult,
    FileSearchRequest,
    FileSearchResult,
    ProjectIndexStatus
)


class TreeStampingBridge:
    """
    Integration service that orchestrates the complete pipeline:
    1. Tree discovery (OnexTree)
    2. Intelligence generation (Bridge)
    3. Metadata stamping (Stamping)
    4. Vector indexing (Qdrant)
    5. Graph indexing (Memgraph)
    6. Cache warming (Valkey)

    Performance Targets:
    - Indexing: <5 minutes for 1000 files
    - Search (cold): <2s
    - Search (warm): <500ms
    """

    def __init__(
        self,
        intelligence_url: str = "http://archon-intelligence:8053",
        tree_url: str = "http://omninode-bridge-onextree:8058",
        stamping_url: str = "http://omninode-bridge-metadata-stamping:8057",
        qdrant_url: str = "http://archon-qdrant:6333",
        memgraph_uri: str = "bolt://archon-memgraph:7687",
        valkey_url: str = "redis://archon-valkey:6379/0"
    ):
        """Initialize bridge with service URLs."""
        pass

    async def index_project(
        self,
        project_path: str,
        project_name: str,
        include_tests: bool = True,
        force_reindex: bool = False
    ) -> ProjectIndexResult:
        """
        Index entire project with full intelligence pipeline.

        Pipeline:
        1. Discover files (OnexTreeClient)
        2. Generate intelligence (MetadataStampingClient)
        3. Batch stamp files (100 files/batch)
        4. Index in Qdrant (parallel)
        5. Index in Memgraph (parallel)
        6. Warm cache (common queries)

        Args:
            project_path: Absolute path to project directory
            project_name: Unique project identifier
            include_tests: Whether to include test files
            force_reindex: Force reindexing even if already indexed

        Returns:
            ProjectIndexResult with indexing statistics

        Raises:
            ValueError: If project_path is invalid
            ConnectionError: If required services are unavailable

        Performance:
            - Target: <5 minutes for 1000 files
            - Batch size: 100 files
            - Parallel: Vector + Graph indexing
        """
        pass

    async def search_files(
        self,
        query: str,
        projects: Optional[List[str]] = None,
        min_quality_score: float = 0.0,
        limit: int = 10
    ) -> FileSearchResult:
        """
        Search for files across projects using semantic + quality ranking.

        Search Strategy:
        1. Check cache (Valkey)
        2. If miss: Query Qdrant (vector similarity)
        3. Filter by quality score
        4. Rank by composite score:
           - Semantic relevance (40%)
           - Quality score (30%)
           - ONEX compliance (20%)
           - Recency (10%)
        5. Cache result (TTL: 5 minutes)

        Args:
            query: Natural language search query
            projects: Optional list of project filters
            min_quality_score: Minimum quality threshold (0.0-1.0)
            limit: Maximum results to return

        Returns:
            FileSearchResult with ranked matches

        Performance:
            - Target (cold): <2s
            - Target (warm): <500ms
            - Cache TTL: 300s
        """
        pass

    async def get_indexing_status(
        self,
        project_name: Optional[str] = None
    ) -> List[ProjectIndexStatus]:
        """
        Get indexing status for projects.

        Data Source:
        - Valkey cache: "file_location:project:{name}:status"
        - Fallback: Query Qdrant for indexed files

        Args:
            project_name: Optional filter for specific project

        Returns:
            List of ProjectIndexStatus (all projects if name=None)

        Performance:
            - Target: <100ms (from cache)
            - Cache TTL: 3600s
        """
        pass
```

### Internal Module Interfaces

```python
# Tree Discovery Module
async def _discover_tree(self, project_path: str) -> dict:
    """
    Discover project files using OnexTreeClient.

    Returns:
        {
            "files": List[str],  # Absolute paths
            "file_count": int,
            "tree_structure": dict,
            "processing_time_ms": int
        }
    """
    pass


# Intelligence Generation Module
async def _generate_intelligence_batch(
    self,
    files: List[str]
) -> List[dict]:
    """
    Generate intelligence for batch of files (parallel).

    Returns:
        List of intelligence metadata dictionaries
    """
    pass


# Stamping Module
async def _stamp_files_batch(
    self,
    stamps: List[dict]
) -> dict:
    """
    Stamp files with intelligence metadata (batch of 100).

    Returns:
        {
            "success": int,
            "failed": int,
            "stamps": List[dict]
        }
    """
    pass


# Indexing Module
async def _index_in_storage(
    self,
    files: List[dict]
) -> dict:
    """
    Index files in Qdrant + Memgraph (parallel).

    Returns:
        {
            "vector_indexed": int,
            "graph_indexed": int,
            "errors": List[str]
        }
    """
    pass


# Cache Management Module
async def _warm_cache(
    self,
    project_name: str,
    file_metadata: List[dict]
) -> None:
    """
    Pre-warm cache with common queries.

    Common queries:
    - "{concept} in {project_name}" for each major concept
    - Generic file type searches
    """
    pass
```

---

## 3. REST API Endpoints (FastAPI)

**Location**: `services/intelligence/src/routers/file_location.py`

### Router Definition

```python
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from models.file_location import (
    ProjectIndexRequest,
    ProjectIndexResult,
    FileSearchResult,
    ProjectIndexStatus
)
from integrations.tree_stamping_bridge import TreeStampingBridge

router = APIRouter(
    prefix="/api/intelligence/file-location",
    tags=["file_location"]
)


@router.post("/index", response_model=ProjectIndexResult)
async def index_project(request: ProjectIndexRequest) -> ProjectIndexResult:
    """
    Index a project's files with full intelligence pipeline.

    **Pipeline Steps**:
    1. Tree discovery (OnexTree)
    2. Intelligence generation (Bridge)
    3. Metadata stamping (Stamping)
    4. Vector indexing (Qdrant)
    5. Graph indexing (Memgraph)
    6. Cache warming (Valkey)

    **Performance**:
    - Target: <5 minutes for 1000 files
    - Batch size: 100 files

    **Returns**:
    - ProjectIndexResult with statistics

    **Errors**:
    - 400: Invalid request (bad project path)
    - 500: Indexing failed (service error)
    - 503: Required services unavailable
    """
    pass


@router.get("/search", response_model=FileSearchResult)
async def search_files(
    query: str = Query(..., description="Search query"),
    projects: Optional[str] = Query(None, description="Comma-separated project names"),
    min_quality_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(10, ge=1, le=100)
) -> FileSearchResult:
    """
    Search for files across projects using semantic + quality ranking.

    **Search Strategy**:
    - Semantic vector similarity (Qdrant)
    - Quality score filtering
    - Composite ranking (relevance + quality + compliance + recency)
    - Cache-first (5 min TTL)

    **Performance**:
    - Target (cold): <2s
    - Target (warm): <500ms

    **Returns**:
    - FileSearchResult with ranked matches

    **Errors**:
    - 400: Invalid query parameters
    - 500: Search failed
    - 503: Required services unavailable
    """
    pass


@router.get("/status", response_model=List[ProjectIndexStatus])
async def get_status(
    project_name: Optional[str] = Query(None, description="Project name filter")
) -> List[ProjectIndexStatus]:
    """
    Get indexing status for projects.

    **Data Source**:
    - Valkey cache (1 hour TTL)
    - Fallback: Qdrant query

    **Performance**:
    - Target: <100ms (from cache)

    **Returns**:
    - List of ProjectIndexStatus (all projects if name=None)

    **Errors**:
    - 500: Status check failed
    - 503: Required services unavailable
    """
    pass
```

---

## 4. MCP Tool Interface

**Location**: `python/src/mcp_server/tools/internal/file_location.py`

### Tool Function

```python
import httpx
from typing import List, Optional, Dict, Any


async def find_file_location(
    query: str,
    projects: Optional[List[str]] = None,
    file_types: Optional[List[str]] = None,
    min_quality_score: float = 0.0,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Find files across projects using intelligent search.

    This tool provides natural language file search across all indexed
    projects, using semantic understanding + quality ranking.

    **Args**:
        query: Natural language search query
            Examples:
            - "authentication module in omniarchon"
            - "database connection pooling"
            - "JWT token validation"
        projects: Optional list of project names to filter
            Example: ["omniarchon", "omninode-bridge"]
        file_types: Optional list of file extensions to filter
            Example: [".py", ".ts", ".md"]
        min_quality_score: Minimum quality score threshold (0.0-1.0)
            Default: 0.0 (no filtering)
        limit: Maximum results to return (1-100)
            Default: 10

    **Returns**:
        {
            "success": bool,
            "results": [
                {
                    "file_path": str,  # Absolute path
                    "confidence": float,  # Match confidence (0.0-1.0)
                    "quality_score": float,  # Code quality (0.0-1.0)
                    "onex_type": str | None,  # ONEX node type
                    "concepts": List[str],  # Semantic concepts
                    "why": str  # Explanation of match
                },
                ...
            ],
            "query_time_ms": int,
            "cache_hit": bool,
            "total_results": int
        }

    **Error Response**:
        {
            "success": false,
            "error": str,
            "details": str
        }

    **Examples**:
        >>> # Find authentication files
        >>> result = await archon_menu(
        ...     operation="find_file_location",
        ...     params={
        ...         "query": "authentication module",
        ...         "min_quality_score": 0.7
        ...     }
        ... )

        >>> # Find high-quality Python files in specific project
        >>> result = await archon_menu(
        ...     operation="find_file_location",
        ...     params={
        ...         "query": "database query optimization",
        ...         "projects": ["omniarchon"],
        ...         "file_types": [".py"],
        ...         "min_quality_score": 0.8,
        ...         "limit": 5
        ...     }
        ... )

    **Performance**:
        - Cold search: <2s
        - Warm search (cache hit): <500ms
        - Cache TTL: 5 minutes

    **Raises**:
        No exceptions raised - errors returned in response dict
    """
    pass
```

### Gateway Registration

```python
# python/src/mcp_server/gateway.py

INTERNAL_OPERATIONS = {
    # ... existing operations ...

    "find_file_location": {
        "category": "file_location",
        "description": "Find files across projects using intelligent search",
        "handler": find_file_location,
        "parameters": {
            "query": {
                "type": "str",
                "required": True,
                "description": "Natural language search query"
            },
            "projects": {
                "type": "list[str]",
                "required": False,
                "description": "Optional project name filters"
            },
            "file_types": {
                "type": "list[str]",
                "required": False,
                "description": "Optional file extension filters"
            },
            "min_quality_score": {
                "type": "float",
                "required": False,
                "default": 0.0,
                "description": "Minimum quality score (0.0-1.0)"
            },
            "limit": {
                "type": "int",
                "required": False,
                "default": 10,
                "description": "Maximum results (1-100)"
            }
        },
        "returns": {
            "type": "dict",
            "schema": {
                "success": "bool",
                "results": "list[FileMatch]",
                "query_time_ms": "int",
                "cache_hit": "bool"
            }
        },
        "examples": [
            {
                "query": "authentication module in omniarchon",
                "min_quality_score": 0.7
            },
            {
                "query": "database connection pooling",
                "projects": ["omniarchon"],
                "file_types": [".py"]
            }
        ]
    }
}
```

---

## 5. Storage Schemas

### Qdrant Collection Schema

**Collection**: `file_locations`

```python
from qdrant_client.models import Distance, VectorParams

collection_config = {
    "collection_name": "file_locations",
    "vectors_config": VectorParams(
        size=1536,  # OpenAI text-embedding-3-small
        distance=Distance.COSINE
    )
}

# Payload Schema
payload_schema = {
    "absolute_path": "keyword",      # Full file path
    "relative_path": "keyword",      # Path relative to project root
    "file_hash": "keyword",          # BLAKE3 hash
    "project_name": "keyword",       # Project identifier
    "project_root": "keyword",       # Project root directory
    "file_type": "keyword",          # File extension (.py, .ts, etc.)
    "quality_score": "float",        # 0.0-1.0
    "onex_compliance": "float",      # 0.0-1.0
    "onex_type": "keyword",          # Effect|Compute|Reducer|Orchestrator
    "concepts": "keyword[]",         # Semantic concepts
    "themes": "keyword[]",           # High-level themes
    "domains": "keyword[]",          # Domain classification
    "pattern_types": "keyword[]",    # Pattern classifications
    "indexed_at": "datetime",        # Indexing timestamp
    "last_modified": "datetime"      # File modification time
}

# Example Payload
example_payload = {
    "absolute_path": "src/services/auth/jwt_handler.py",
    "relative_path": "src/services/auth/jwt_handler.py",
    "file_hash": "blake3_abc123def456",
    "project_name": "omniarchon",
    "project_root": "/Volumes/PRO-G40/Code/omniarchon",
    "file_type": ".py",
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "onex_type": "effect",
    "concepts": ["authentication", "JWT", "token", "security"],
    "themes": ["security", "api"],
    "domains": ["backend.auth"],
    "pattern_types": ["effect"],
    "indexed_at": "2025-10-24T12:00:00Z",
    "last_modified": "2025-10-23T15:30:00Z"
}
```

### Memgraph Schema

**Cypher Queries**:

```cypher
-- Node: Project
CREATE (p:Project {
    name: 'omniarchon',
    path: '/Volumes/PRO-G40/Code/omniarchon',
    indexed_at: datetime(),
    file_count: 1247
});

-- Node: File
CREATE (f:File {
    path: 'src/services/auth/jwt_handler.py',
    absolute_path: 'src/services/auth/jwt_handler.py',
    hash: 'blake3_abc123def456',
    quality_score: 0.87,
    onex_type: 'effect',
    file_type: '.py',
    indexed_at: datetime()
});

-- Node: Concept
CREATE (c:Concept {
    name: 'authentication'
});

-- Node: Theme
CREATE (t:Theme {
    name: 'security'
});

-- Node: Domain
CREATE (d:Domain {
    name: 'backend.auth'
});

-- Node: ONEXType
CREATE (o:ONEXType {
    name: 'effect'
});

-- Relationship: CONTAINS
CREATE (p:Project {name: 'omniarchon'})
-[:CONTAINS {indexed_at: datetime()}]->
(f:File {path: 'src/services/auth/jwt_handler.py'});

-- Relationship: HAS_CONCEPT
CREATE (f:File {path: 'src/services/auth/jwt_handler.py'})
-[:HAS_CONCEPT {confidence: 0.92}]->
(c:Concept {name: 'authentication'});

-- Relationship: HAS_THEME
CREATE (f:File {path: 'src/services/auth/jwt_handler.py'})
-[:HAS_THEME]->
(t:Theme {name: 'security'});

-- Relationship: BELONGS_TO_DOMAIN
CREATE (f:File {path: 'src/services/auth/jwt_handler.py'})
-[:BELONGS_TO_DOMAIN]->
(d:Domain {name: 'backend.auth'});

-- Relationship: IS_ONEX_TYPE
CREATE (f:File {path: 'src/services/auth/jwt_handler.py'})
-[:IS_ONEX_TYPE]->
(o:ONEXType {name: 'effect'});
```

**Query Examples**:

```cypher
-- Find all files in a project
MATCH (p:Project {name: 'omniarchon'})-[:CONTAINS]->(f:File)
RETURN f;

-- Find files by concept
MATCH (f:File)-[:HAS_CONCEPT]->(c:Concept {name: 'authentication'})
RETURN f;

-- Find files by ONEX type
MATCH (f:File)-[:IS_ONEX_TYPE]->(o:ONEXType {name: 'effect'})
RETURN f;

-- Complex query: high-quality auth files
MATCH (f:File)-[:HAS_CONCEPT]->(c:Concept {name: 'authentication'})
WHERE f.quality_score > 0.7
RETURN f
ORDER BY f.quality_score DESC
LIMIT 10;
```

### Valkey Cache Schema

**Key Patterns**:

```python
# Search result cache
key_pattern = "file_location:query:{query_hash}"
value_type = "JSON"
ttl = 300  # 5 minutes
example_key = "file_location:query:sha256_abc123"
example_value = {
    "success": True,
    "results": [...],
    "query_time_ms": 342,
    "cache_hit": False,
    "total_results": 15,
    "cached_at": "2025-10-24T12:00:00Z"
}

# Project status cache
key_pattern = "file_location:project:{project_name}:status"
value_type = "JSON"
ttl = 3600  # 1 hour
example_key = "file_location:project:omniarchon:status"
example_value = {
    "indexed": True,
    "file_count": 1247,
    "indexed_at": "2025-10-24T10:00:00Z",
    "last_updated": "2025-10-24T11:30:00Z",
    "status": "indexed"
}

# Cache invalidation keys
project_invalidation_key = "file_location:project:{project_name}:invalidate"
global_invalidation_key = "file_location:invalidate_all"
```

**Cache Operations**:

```python
import redis.asyncio as redis

# Initialize Valkey client
valkey = redis.from_url("redis://archon-valkey:6379/0")

# Cache search result
async def cache_search_result(query: str, result: dict) -> None:
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    key = f"file_location:query:{query_hash}"
    result["cached_at"] = datetime.now().isoformat()
    await valkey.setex(key, 300, json.dumps(result))

# Get cached search result
async def get_cached_search_result(query: str) -> dict | None:
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    key = f"file_location:query:{query_hash}"
    cached = await valkey.get(key)
    if cached:
        return json.loads(cached)
    return None

# Cache project status
async def cache_project_status(project_name: str, status: dict) -> None:
    key = f"file_location:project:{project_name}:status"
    await valkey.setex(key, 3600, json.dumps(status))

# Invalidate project cache
async def invalidate_project_cache(project_name: str) -> None:
    # Invalidate status
    status_key = f"file_location:project:{project_name}:status"
    await valkey.delete(status_key)

    # Invalidate related queries (scan pattern)
    pattern = f"file_location:query:*{project_name}*"
    async for key in valkey.scan_iter(match=pattern):
        await valkey.delete(key)
```

---

## 6. Error Handling Standards

### Error Response Format

All services should return errors in this consistent format:

```python
class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Machine-readable error code")
    details: Optional[str] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = Field(default=None, description="Request correlation ID")


# Example error responses
validation_error = ErrorResponse(
    error="Invalid project path",
    error_code="INVALID_PROJECT_PATH",
    details="Project path must be absolute and exist on filesystem"
)

service_unavailable = ErrorResponse(
    error="OnexTree service unavailable",
    error_code="SERVICE_UNAVAILABLE",
    details="Failed to connect to http://omninode-bridge-onextree:8058"
)

indexing_failed = ErrorResponse(
    error="Indexing failed for project 'omniarchon'",
    error_code="INDEXING_FAILED",
    details="Failed to index 15 files due to stamping service timeout"
)
```

### HTTP Status Codes

```python
# Success
200: "OK - Request successful"
201: "Created - Resource created"

# Client Errors
400: "Bad Request - Invalid input parameters"
404: "Not Found - Resource not found"
422: "Unprocessable Entity - Validation error"

# Server Errors
500: "Internal Server Error - Unexpected error"
503: "Service Unavailable - Required service down"
504: "Gateway Timeout - Service timeout"
```

---

## 7. Logging Standards

### Log Format

```python
import logging
from datetime import datetime

# Structured logging format
log_format = {
    "timestamp": datetime.now().isoformat(),
    "level": "INFO",
    "service": "tree-stamping-bridge",
    "operation": "index_project",
    "message": "Indexing project",
    "context": {
        "project_name": "omniarchon",
        "file_count": 1247,
        "duration_ms": 45000
    },
    "request_id": "uuid-abc123"
}

# Log levels
logging.DEBUG: "Detailed diagnostic information"
logging.INFO: "General informational messages"
logging.WARNING: "Warning messages (non-fatal issues)"
logging.ERROR: "Error messages (recoverable failures)"
logging.CRITICAL: "Critical errors (service down)"
```

---

## 8. Performance Monitoring

### Metrics to Track

```python
from prometheus_client import Counter, Histogram, Gauge

# Request counters
indexing_requests_total = Counter(
    "file_location_indexing_requests_total",
    "Total indexing requests",
    ["project_name", "status"]
)

search_requests_total = Counter(
    "file_location_search_requests_total",
    "Total search requests",
    ["cache_hit"]
)

# Latency histograms
indexing_duration_seconds = Histogram(
    "file_location_indexing_duration_seconds",
    "Indexing duration in seconds",
    buckets=[10, 30, 60, 120, 300]
)

search_duration_seconds = Histogram(
    "file_location_search_duration_seconds",
    "Search duration in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# Gauges
files_indexed_total = Gauge(
    "file_location_files_indexed_total",
    "Total files indexed",
    ["project_name"]
)

cache_hit_rate = Gauge(
    "file_location_cache_hit_rate",
    "Cache hit rate (0.0-1.0)"
)
```

---

## Contract Validation Checklist

**Before parallel execution begins, verify**:

- [ ] All data models defined with complete type hints
- [ ] All service interfaces defined with clear method signatures
- [ ] All API endpoints defined with request/response schemas
- [ ] All MCP tools defined with parameter specifications
- [ ] All storage schemas defined (Qdrant, Memgraph, Valkey)
- [ ] Error handling standards documented
- [ ] Logging standards documented
- [ ] Performance monitoring standards documented
- [ ] No implementation details in interfaces (signatures only)
- [ ] All type hints compatible with Python 3.11+

**Success Criteria**:
- All 5 work streams can start immediately without waiting
- No ambiguity in interfaces
- Clear success criteria for each contract

---

**Status**: Contract Definition Complete
**Ready for Parallel Execution**: YES
**Next Action**: Dispatch 5 polymorphic agents to implement contracts

---

**Document Owner**: Polymorphic Agent (Coordinator)
**Last Updated**: 2025-10-24
**Version**: 1.0
