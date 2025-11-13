# Event Handler Contracts Specification

**Created**: 2025-10-22
**Purpose**: Contract specification for three parallel event handlers in Intelligence service
**Status**: Phase 1 - Foundation (Ready for Poly implementation)

## Overview

This document defines the event contracts for three new event handlers that will be implemented in parallel:

1. **Document Indexing Handler** - Full intelligence pipeline (metadata, entities, vectors, knowledge graph)
2. **Repository Crawler Handler** - Batch file discovery and indexing orchestration
3. **Search Handler** - Multi-source search aggregation (RAG, Vector, Knowledge Graph)

## ONEX Compliance Requirements

All events must follow the ONEX event bus architecture:

### Event Type Naming Convention
```
omninode.{domain}.{pattern}.{operation}.{version}
```

**Example**: `omninode.intelligence.event.document_index_requested.v1`

### Event Envelope Structure
```json
{
  "event_id": "uuid",
  "event_type": "omninode.intelligence.event.{operation}.v1",
  "correlation_id": "uuid",
  "causation_id": "uuid|null",
  "timestamp": "ISO8601",
  "version": "1.0.0",
  "source": {
    "service": "archon-intelligence",
    "instance_id": "string",
    "hostname": "string|null"
  },
  "metadata": {},
  "payload": {}
}
```

### Kafka Topic Naming Convention
```
{env}.archon-intelligence.intelligence.{event-type}.v1
```

**Example**: `dev.archon-intelligence.intelligence.document-index-requested.v1`

---

## 1. Document Indexing Handler

**Purpose**: Orchestrate full intelligence pipeline for a single document

**Services Integrated**:
- Metadata Stamping (Bridge:8057) - BLAKE3 content hashing
- Entity Extraction (LangExtract:8156) - AST parsing, function/class extraction
- Vector Indexing (Qdrant:6333) - Semantic embeddings for RAG
- Knowledge Graph (Memgraph:7687) - Entity relationships
- Quality Assessment (Intelligence:8053) - ONEX compliance scoring

### 1.1 DOCUMENT_INDEX_REQUESTED

**Event Type**: `omninode.intelligence.event.document_index_requested.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.document-index-requested.v1`
**Publisher**: Repository Crawler, Manual triggers, CI/CD pipelines
**Consumer**: Document Indexing Handler

#### Payload Schema

```python
class ModelDocumentIndexRequestPayload(BaseModel):
    """Payload for DOCUMENT_INDEX_REQUESTED event."""

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
        examples=[{
            "skip_metadata_stamping": False,
            "skip_vector_indexing": False,
            "skip_knowledge_graph": False,
            "skip_quality_assessment": False,
            "force_reindex": False,
            "chunk_size": 1000,
            "chunk_overlap": 200,
        }],
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for authorization and audit",
    )
```

### 1.2 DOCUMENT_INDEX_COMPLETED

**Event Type**: `omninode.intelligence.event.document_index_completed.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.document-index-completed.v1`
**Publisher**: Document Indexing Handler
**Consumer**: Repository Crawler, Analytics services, Monitoring

#### Payload Schema

```python
class ModelDocumentIndexCompletedPayload(BaseModel):
    """Payload for DOCUMENT_INDEX_COMPLETED event."""

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
        examples=[{
            "metadata_stamping_ms": 45.2,
            "entity_extraction_ms": 234.5,
            "vector_indexing_ms": 123.4,
            "knowledge_graph_ms": 89.3,
            "quality_assessment_ms": 156.7,
        }],
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether document was already indexed (deduplication)",
    )

    reindex_required: bool = Field(
        default=False,
        description="Whether future reindexing is recommended",
    )
```

### 1.3 DOCUMENT_INDEX_FAILED

**Event Type**: `omninode.intelligence.event.document_index_failed.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.document-index-failed.v1`
**Publisher**: Document Indexing Handler
**Consumer**: Repository Crawler, Error monitoring, Retry orchestrators

#### Payload Schema

```python
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

class ModelDocumentIndexFailedPayload(BaseModel):
    """Payload for DOCUMENT_INDEX_FAILED event."""

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
        examples=[{
            "metadata_stamping": {"hash": "blake3:..."},
            "entity_extraction": {"entities_count": 12},
        }],
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context and stack trace",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action to resolve the error",
    )
```

---

## 2. Repository Crawler Handler

**Purpose**: Discover and batch-process all files in a repository

**Services Integrated**:
- Filesystem/Git (local)
- Kafka (publish DOCUMENT_INDEX_REQUESTED events)

### 2.1 REPOSITORY_SCAN_REQUESTED

**Event Type**: `omninode.intelligence.event.repository_scan_requested.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.repository-scan-requested.v1`
**Publisher**: CI/CD pipelines, Manual triggers, Scheduled jobs
**Consumer**: Repository Crawler Handler

#### Payload Schema

```python
class EnumScanScope(str, Enum):
    """Scope of repository scan."""

    FULL = "FULL"  # Scan entire repository
    INCREMENTAL = "INCREMENTAL"  # Only scan changed files since last scan
    SELECTIVE = "SELECTIVE"  # Scan specific paths/patterns

class ModelRepositoryScanRequestPayload(BaseModel):
    """Payload for REPOSITORY_SCAN_REQUESTED event."""

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
        default_factory=lambda: ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"],
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
```

### 2.2 REPOSITORY_SCAN_COMPLETED

**Event Type**: `omninode.intelligence.event.repository_scan_completed.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.repository-scan-completed.v1`
**Publisher**: Repository Crawler Handler
**Consumer**: CI/CD pipelines, Analytics, Monitoring

#### Payload Schema

```python
class ModelRepositoryScanCompletedPayload(BaseModel):
    """Payload for REPOSITORY_SCAN_COMPLETED event."""

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
        examples=[[
            {"path": "src/api.py", "size": 12345, "language": "python"},
            {"path": "src/utils.ts", "size": 6789, "language": "typescript"},
        ]],
    )
```

### 2.3 REPOSITORY_SCAN_FAILED

**Event Type**: `omninode.intelligence.event.repository_scan_failed.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.repository-scan-failed.v1`
**Publisher**: Repository Crawler Handler
**Consumer**: CI/CD pipelines, Error monitoring

#### Payload Schema

```python
class EnumScanErrorCode(str, Enum):
    """Error codes for repository scan failures."""

    INVALID_INPUT = "INVALID_INPUT"
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    GIT_ERROR = "GIT_ERROR"
    NO_FILES_FOUND = "NO_FILES_FOUND"
    PATTERN_ERROR = "PATTERN_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class ModelRepositoryScanFailedPayload(BaseModel):
    """Payload for REPOSITORY_SCAN_FAILED event."""

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
        min_length=1,
    )

    error_code: EnumScanErrorCode = Field(
        ...,
        description="Machine-readable error code",
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

    files_processed_before_failure: int = Field(
        default=0,
        description="Number of files successfully processed before failure",
        ge=0,
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action to resolve the error",
    )
```

---

## 3. Search Handler

**Purpose**: Aggregate search results from multiple intelligence sources

**Services Integrated**:
- RAG Search (Search:8055) - Semantic document search
- Vector Search (Qdrant:6333) - Similarity search
- Knowledge Graph (Memgraph:7687) - Entity and relationship queries

### 3.1 SEARCH_REQUESTED

**Event Type**: `omninode.intelligence.event.search_requested.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.search-requested.v1`
**Publisher**: Client applications, MCP server, API gateway
**Consumer**: Search Handler

#### Payload Schema

```python
class EnumSearchType(str, Enum):
    """Type of search to perform."""

    SEMANTIC = "SEMANTIC"  # RAG-based semantic search
    VECTOR = "VECTOR"  # Pure vector similarity search
    KNOWLEDGE_GRAPH = "KNOWLEDGE_GRAPH"  # Entity/relationship search
    HYBRID = "HYBRID"  # All sources combined with ranking

class ModelSearchRequestPayload(BaseModel):
    """Payload for SEARCH_REQUESTED event."""

    query: str = Field(
        ...,
        description="Search query text",
        examples=["authentication patterns", "async transaction handling"],
        min_length=1,
    )

    search_type: EnumSearchType = Field(
        default=EnumSearchType.HYBRID,
        description="Type of search to perform",
    )

    project_id: Optional[str] = Field(
        None,
        description="Optional project filter",
    )

    max_results: int = Field(
        default=10,
        description="Maximum results to return",
        ge=1,
        le=100,
    )

    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Search filters (language, quality_score, etc.)",
        examples=[{
            "language": "python",
            "min_quality_score": 0.7,
            "file_patterns": ["src/**/*.py"],
        }],
    )

    quality_weight: Optional[float] = Field(
        None,
        description="Weight for quality-based ranking (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    include_context: bool = Field(
        default=True,
        description="Include surrounding code context in results",
    )

    enable_caching: bool = Field(
        default=True,
        description="Whether to use cached results if available",
    )

    user_id: Optional[str] = Field(
        None,
        description="User identifier for personalization and audit",
    )
```

### 3.2 SEARCH_COMPLETED

**Event Type**: `omninode.intelligence.event.search_completed.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.search-completed.v1`
**Publisher**: Search Handler
**Consumer**: Client applications, MCP server, Analytics

#### Payload Schema

```python
class ModelSearchResultItem(BaseModel):
    """Single search result item."""

    source_path: str = Field(..., description="File path of result")
    score: float = Field(..., description="Relevance score", ge=0.0, le=1.0)
    content: str = Field(..., description="Matched content or excerpt")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class ModelSearchCompletedPayload(BaseModel):
    """Payload for SEARCH_COMPLETED event."""

    query: str = Field(
        ...,
        description="Original search query",
    )

    search_type: EnumSearchType = Field(
        ...,
        description="Type of search performed",
    )

    total_results: int = Field(
        ...,
        description="Total number of results found",
        ge=0,
    )

    results: list[ModelSearchResultItem] = Field(
        ...,
        description="Search results",
    )

    sources_queried: list[str] = Field(
        ...,
        description="Sources queried (rag, vector, knowledge_graph)",
        examples=[["rag", "vector", "knowledge_graph"]],
    )

    processing_time_ms: float = Field(
        ...,
        description="Total search time in milliseconds",
        ge=0.0,
    )

    service_timings: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown of search time by service",
        examples=[{
            "rag_search_ms": 234.5,
            "vector_search_ms": 123.4,
            "knowledge_graph_ms": 89.3,
            "ranking_ms": 45.2,
        }],
    )

    cache_hit: bool = Field(
        default=False,
        description="Whether results were served from cache",
    )

    aggregation_strategy: Optional[str] = Field(
        None,
        description="How results were aggregated (weighted, ranked, etc.)",
    )
```

### 3.3 SEARCH_FAILED

**Event Type**: `omninode.intelligence.event.search_failed.v1`
**Kafka Topic**: `dev.archon-intelligence.intelligence.search-failed.v1`
**Publisher**: Search Handler
**Consumer**: Client applications, Error monitoring

#### Payload Schema

```python
class EnumSearchErrorCode(str, Enum):
    """Error codes for search failures."""

    INVALID_QUERY = "INVALID_QUERY"
    NO_RESULTS = "NO_RESULTS"
    RAG_SERVICE_ERROR = "RAG_SERVICE_ERROR"
    VECTOR_SERVICE_ERROR = "VECTOR_SERVICE_ERROR"
    KNOWLEDGE_GRAPH_ERROR = "KNOWLEDGE_GRAPH_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class ModelSearchFailedPayload(BaseModel):
    """Payload for SEARCH_FAILED event."""

    query: str = Field(
        ...,
        description="Search query that failed",
    )

    search_type: EnumSearchType = Field(
        ...,
        description="Type of search attempted",
    )

    error_message: str = Field(
        ...,
        description="Human-readable error description",
        min_length=1,
    )

    error_code: EnumSearchErrorCode = Field(
        ...,
        description="Machine-readable error code",
    )

    failed_services: list[str] = Field(
        default_factory=list,
        description="Services that failed",
        examples=[["rag", "vector"]],
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

    partial_results: Optional[list[ModelSearchResultItem]] = Field(
        None,
        description="Partial results if some services succeeded",
    )

    error_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context",
    )

    suggested_action: Optional[str] = Field(
        None,
        description="Recommended action to resolve the error",
    )
```

---

## Service Integration Points

### Document Indexing Handler Services

| Service | Endpoint | Purpose | Response Fields |
|---------|----------|---------|-----------------|
| Bridge Metadata | `POST http://localhost:8057/api/stamp-metadata` | BLAKE3 content hashing | `hash`, `timestamp`, `dedupe_status` |
| LangExtract | `POST http://localhost:8156/extract/code` | Entity extraction | `entities[]`, `relationships[]`, `ast_metadata` |
| Qdrant | `POST http://localhost:6333/collections/{name}/points` | Vector indexing | `ids[]`, `status` |
| Memgraph | Cypher via driver | Knowledge graph | `entity_ids[]`, `relationship_ids[]` |
| Intelligence | `POST http://localhost:8053/assess/code` | Quality assessment | `quality_score`, `onex_compliance` |

### Repository Crawler Handler Services

| Service | Endpoint | Purpose | Response Fields |
|---------|----------|---------|-----------------|
| Filesystem | Local I/O | File discovery | File paths, sizes, modified dates |
| Git | `git` CLI or library | Repository operations | Commit SHAs, branches, diffs |
| Kafka | Producer API | Publish DOCUMENT_INDEX_REQUESTED | Acknowledgements |

### Search Handler Services

| Service | Endpoint | Purpose | Response Fields |
|---------|----------|---------|-----------------|
| RAG Search | `POST http://localhost:8055/search` | Semantic search | `results[]`, `scores[]` |
| Qdrant | `POST http://localhost:6333/collections/{name}/points/search` | Vector similarity | `points[]`, `scores[]` |
| Memgraph | Cypher queries | Entity/relationship search | `entities[]`, `relationships[]`, `paths[]` |

---

## Shared Error Codes

All handlers should use consistent error codes where applicable:

```python
# Common across all handlers
INVALID_INPUT = "INVALID_INPUT"
TIMEOUT = "TIMEOUT"
EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

# Parsing/Language
UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
PARSING_ERROR = "PARSING_ERROR"

# External Services
METADATA_STAMPING_FAILED = "METADATA_STAMPING_FAILED"
ENTITY_EXTRACTION_FAILED = "ENTITY_EXTRACTION_FAILED"
VECTOR_INDEXING_FAILED = "VECTOR_INDEXING_FAILED"
KNOWLEDGE_GRAPH_FAILED = "KNOWLEDGE_GRAPH_FAILED"
```

---

## Testing Requirements

### Unit Tests (per handler)
- Event envelope creation
- Payload validation
- Error code handling
- Service mocking

### Integration Tests (per handler)
- Kafka event publishing/consuming
- Backend service integration
- Error scenarios
- Correlation ID tracking

### End-to-End Tests (after Phase 3)
- Full pipeline: Repository Scan → Document Indexing → Search
- Multi-handler workflows
- Performance under load

---

## Implementation Checklist (Per Handler)

- [ ] Create event model file with payload schemas
- [ ] Implement event envelope helpers
- [ ] Create handler class with can_handle() and handle_event()
- [ ] Implement service orchestration logic
- [ ] Add error handling and retry logic
- [ ] Create convenience functions for event creation
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update Kafka topics configuration
- [ ] Register handler in kafka_consumer.py

---

## Poly Assignment

**Poly 1**: Document Indexing Handler
**Poly 2**: Repository Crawler Handler
**Poly 3**: Search Handler

Each Poly will work independently on their assigned handler following this contract specification.

**Ready for Phase 2: Parallel Implementation** ✅
