# POC: Tree + Metadata Stamping Integration for Automatic File Location

**Version**: 1.0.0
**Status**: Planning
**Timeline**: 1-2 weeks
**Priority**: Immediate

## Executive Summary

### Goal
Enable automatic file path resolution across all codebases by integrating OnexTree filesystem discovery with Metadata Stamping intelligence and Archon Intelligence indexing.

### Vision
Agents can access any file in any repository via intelligent path resolution:
- "Find the authentication module in omniarchon"
- "Show me all ONEX Effect nodes across projects"
- "Locate the RAG query implementation"

### Success Criteria
1. ✅ All services healthy (Tree, Stamping, Intelligence, MCP)
2. ✅ Files indexed with full paths and intelligence metadata
3. ✅ MCP tool resolves file locations in <500ms
4. ✅ Cross-project search works seamlessly
5. ✅ 95%+ accuracy for file location queries

### Timeline
- **Week 1**: Service validation + Integration development + Testing
- **Week 2**: Production deployment + Documentation + Performance optimization

---

## Current State Analysis

### Services Running ✅

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| archon-intelligence | 8053 | ✅ Healthy | Core intelligence, quality analysis, pattern learning |
| archon-bridge | 8054 | ✅ Healthy | Bridge integration, metadata generation |
| archon-search | 8055 | ✅ Healthy | RAG queries, semantic search |
| archon-mcp | 8151 | ✅ Healthy | MCP gateway (168+ operations) |
| omninode-bridge-onextree | 8058 | ✅ Healthy | Tree discovery, filesystem traversal |
| omninode-bridge-metadata-stamping | 8057 | ✅ Healthy | Metadata stamping, intelligence enrichment |
| archon-qdrant | 6333 | ✅ Healthy | Vector database |
| archon-memgraph | 7687 | ✅ Healthy | Knowledge graph |
| archon-valkey | 6379 | ✅ Healthy | Distributed cache |

### Available Clients ✅

**OnexTreeClient** (`src/mcp_server/clients/onex_tree_client.py`)
```python
# Tree generation
result = await client.generate_tree(
    project_path="/path/to/project",
    include_tests=True,
    max_depth=None
)

# Path queries
result = await client.query_tree(
    path_pattern="**/auth/*.py",
    include_content=False,
    max_results=100
)

# Pattern enrichment
result = await client.enrich_with_patterns(
    file_paths=["file1.py", "file2.py"],
    patterns={"onex_type": "effect", "domain": "api"}
)
```

**MetadataStampingClient** (`src/mcp_server/clients/metadata_stamping_client.py`)
```python
# Single file stamping
result = await client.stamp_file(
    file_hash="abc123",
    metadata={"path": "/project/file.py", "quality": 0.92}
)

# Intelligence-enriched stamping
result = await client.stamp_with_intelligence(
    file_path="/project/file.py",
    file_hash="abc123",
    content="file content",
    include_semantic=True,
    include_compliance=True
)

# Batch stamping
result = await client.batch_stamp(
    stamps=[
        {"file_hash": "abc123", "metadata": {...}},
        {"file_hash": "def456", "metadata": {...}}
    ],
    batch_size=100
)
```

### Gap Analysis

**What Exists:**
- ✅ Tree discovery service (OnexTree)
- ✅ Metadata stamping service (Stamping)
- ✅ Intelligence generation (Bridge + Intelligence)
- ✅ Vector indexing (Qdrant)
- ✅ Knowledge graph (Memgraph)
- ✅ HTTP clients for Tree and Stamping services

**What's Missing:**
- ❌ Integration between Tree discovery and Stamping
- ❌ Automated pipeline: Tree → Stamp → Index
- ❌ MCP tool for file location search
- ❌ Cross-project file path resolution
- ❌ Caching layer for fast lookups

---

## Technical Architecture

### Component: Tree-Stamping Integration Service

**Location**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Purpose**: Orchestrate the pipeline from tree discovery to searchable intelligence.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Gateway (8151)                          │
│  archon_menu(operation="find_file_location", params={...})      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│         Intelligence Service (8053)                             │
│  /api/intelligence/file-location/search                         │
│  /api/intelligence/file-location/index                          │
└───────────────┬──────────────────┬──────────────────────────────┘
                │                  │
      ┌─────────↓──────────┐      ┌─────────↓────────┐
      │  Tree Discovery    │      │  Intelligence    │
      │  (OnexTree:8058)   │      │  Generation      │
      └─────────┬──────────┘      └─────────┬────────┘
                │                           │
                │                           │
      ┌─────────↓────────────────────────────↓───────┐
      │         Metadata Stamping (8057)             │
      │  • File hash + path                          │
      │  • Intelligence metadata                     │
      │  • Quality scores                            │
      │  • ONEX compliance                           │
      └─────────┬────────────────────────────────────┘
                │
      ┌─────────↓────────────────────────────────────┐
      │  Storage & Indexing                          │
      │  • Qdrant (vectors)                          │
      │  • Memgraph (relationships)                  │
      │  • Valkey (cache)                            │
      └──────────────────────────────────────────────┘
```

### Data Flow

**1. Tree Discovery Phase**
```
Input: Project path
↓
OnexTreeClient.generate_tree()
↓
Output: {
  "files_tracked": 1247,
  "tree_structure": {
    "src/": ["file1.py", "file2.py", ...],
    "tests/": ["test1.py", ...]
  },
  "processing_time_ms": 1200
}
```

**2. Intelligence Generation Phase**
```
For each file in tree:
  ↓
  MetadataStampingClient.generate_intelligence()
  ↓
  Output: {
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "semantic_intelligence": {
      "concepts": ["authentication", "JWT"],
      "themes": ["security", "api"],
      "domains": ["backend.auth"]
    },
    "pattern_intelligence": {
      "pattern_types": ["effect", "orchestrator"]
    }
  }
```

**3. Stamping Phase**
```
Batch stamp all files:
  ↓
  MetadataStampingClient.batch_stamp([
    {
      "file_hash": "hash1",
      "metadata": {
        "absolute_path": "/path/to/project/src/auth.py",
        "relative_path": "src/auth.py",
        "project_name": "omniarchon",
        "quality_score": 0.87,
        "onex_type": "effect",
        "concepts": ["authentication", "JWT"],
        ...
      }
    },
    ...
  ])
```

**4. Indexing Phase**
```
Index in parallel:
  ↓ (Vector)
  Qdrant.index({
    "collection": "file_locations",
    "vector": embedding(file_path + concepts + description),
    "payload": metadata
  })
  ↓ (Graph)
  Memgraph.create_node({
    "type": "File",
    "path": "src/auth.py",
    "project": "omniarchon"
  })
  Memgraph.create_relationship({
    "from": "Project:omniarchon",
    "to": "File:src/auth.py",
    "type": "CONTAINS"
  })
```

**5. Query Phase**
```
Agent query: "Find authentication module in omniarchon"
  ↓
  Search orchestration (RAG + Qdrant + Memgraph)
  ↓
  Results ranked by:
    • Quality score (30%)
    • Semantic relevance (40%)
    • ONEX compliance (20%)
    • Recency (10%)
  ↓
  Output: {
    "file_path": "/path/to/omniarchon/src/services/auth/jwt_handler.py",
    "confidence": 0.94,
    "quality_score": 0.87,
    "onex_type": "effect",
    "why": "High semantic match for 'authentication', ONEX Effect node"
  }
```

### Integration Points

**1. Intelligence Service** (New endpoints)
```python
# POST /api/intelligence/file-location/index
# Index a project's files
{
  "project_path": "/path/to/project",
  "project_name": "omniarchon",
  "include_tests": true,
  "max_depth": null,
  "force_reindex": false
}

# GET /api/intelligence/file-location/search
# Search for files across projects
{
  "query": "authentication module",
  "projects": ["omniarchon", "omninode-bridge"],  # Optional filter
  "file_types": [".py", ".ts"],  # Optional filter
  "min_quality_score": 0.7,  # Optional filter
  "limit": 10
}

# GET /api/intelligence/file-location/status
# Get indexing status for projects
{
  "project_name": "omniarchon"  # Optional filter
}
```

**2. MCP Gateway** (New operation)
```python
# archon_menu(operation="find_file_location", params={...})
{
  "query": "authentication module in omniarchon",
  "filters": {
    "projects": ["omniarchon"],
    "min_quality_score": 0.7
  }
}

# Returns:
{
  "success": true,
  "results": [
    {
      "file_path": "/path/to/omniarchon/src/services/auth/jwt_handler.py",
      "confidence": 0.94,
      "quality_score": 0.87,
      "onex_type": "effect",
      "concepts": ["authentication", "JWT", "security"],
      "why": "High semantic match + ONEX Effect node + quality score"
    }
  ],
  "query_time_ms": 342,
  "cache_hit": false
}
```

**3. Bridge Service** (Leverage existing)
```python
# POST /api/bridge/generate-intelligence
# Already implemented - use for intelligence generation
```

### Storage Schema

**Qdrant Collection: `file_locations`**
```python
{
  "id": "uuid",
  "vector": [0.1, 0.2, ...],  # 1536 dimensions (OpenAI embedding)
  "payload": {
    "absolute_path": "/path/to/project/src/auth.py",
    "relative_path": "src/auth.py",
    "file_hash": "blake3_hash",
    "project_name": "omniarchon",
    "project_root": "/path/to/project",
    "file_type": ".py",
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "onex_type": "effect",
    "concepts": ["authentication", "JWT"],
    "themes": ["security", "api"],
    "domains": ["backend.auth"],
    "pattern_types": ["effect"],
    "indexed_at": "2025-10-24T12:00:00Z",
    "last_modified": "2025-10-23T15:30:00Z"
  }
}
```

**Memgraph Schema**
```cypher
// Nodes
(:Project {name: "omniarchon", path: "/path/to/project"})
(:File {path: "src/auth.py", absolute_path: "/path/to/project/src/auth.py", hash: "..."})
(:Concept {name: "authentication"})
(:Theme {name: "security"})
(:Domain {name: "backend.auth"})
(:ONEXType {name: "effect"})

// Relationships
(:Project)-[:CONTAINS]->(:File)
(:File)-[:HAS_CONCEPT]->(:Concept)
(:File)-[:HAS_THEME]->(:Theme)
(:File)-[:BELONGS_TO_DOMAIN]->(:Domain)
(:File)-[:IS_ONEX_TYPE]->(:ONEXType)
(:File)-[:IMPORTS]->(:File)  // Code dependencies
```

**Valkey Cache**
```
Key pattern: "file_location:query:{query_hash}"
Value: JSON result
TTL: 300 seconds (5 minutes)

Key pattern: "file_location:project:{project_name}:status"
Value: {indexed: true, file_count: 1247, indexed_at: "..."}
TTL: 3600 seconds (1 hour)
```

---

## Implementation Plan

### Phase 1: Service Health Validation (Day 1)
**Objective**: Verify all required services are working correctly.

**Tasks**:
1. ✅ Verify all 12 services are healthy (DONE - see Current State)
2. Test OnexTreeClient operations:
   - Generate tree for test project
   - Query specific path patterns
   - Verify performance (<2s for tree generation)
3. Test MetadataStampingClient operations:
   - Stamp single file with metadata
   - Generate intelligence for file
   - Test batch stamping (100 files)
4. Test Intelligence Service endpoints:
   - Code quality assessment
   - RAG queries
   - Vector search
5. Test MCP gateway:
   - Verify archon_menu operation discovery
   - Test existing operations

**Validation**:
```bash
# Test Tree service
curl http://localhost:8058/health

# Test Stamping service
curl http://localhost:8057/health

# Test Intelligence service
curl http://localhost:8053/health

# Test MCP gateway
curl http://localhost:8151/health

# Integration test
python3 python/tests/integration/test_tree_stamping_health.py
```

**Success Criteria**:
- All services return 200 OK
- Tree generation completes in <2s
- Stamping completes in <100ms per file
- Intelligence generation completes in <3s

---

### Phase 2: Tree + Stamping Integration (Days 2-5)

**Objective**: Build the integration service that orchestrates tree discovery → intelligence → stamping → indexing.

#### Day 2-3: Integration Service Development

**File**: `services/intelligence/src/integrations/tree_stamping_bridge.py`

**Components**:

```python
class TreeStampingBridge:
    """
    Orchestrates the complete pipeline:
    1. Tree discovery (OnexTree)
    2. Intelligence generation (Bridge)
    3. Metadata stamping (Stamping)
    4. Vector indexing (Qdrant)
    5. Graph indexing (Memgraph)
    6. Cache warming (Valkey)
    """

    async def index_project(
        self,
        project_path: str,
        project_name: str,
        include_tests: bool = True,
        force_reindex: bool = False
    ) -> ProjectIndexResult:
        """
        Index entire project with full intelligence pipeline.

        Performance target: <5 minutes for 1000 files
        """
        pass

    async def search_files(
        self,
        query: str,
        projects: list[str] | None = None,
        min_quality_score: float = 0.0,
        limit: int = 10
    ) -> FileSearchResult:
        """
        Search for files across projects.

        Performance target: <500ms with cache, <2s cold
        """
        pass

    async def get_indexing_status(
        self,
        project_name: str | None = None
    ) -> list[ProjectIndexStatus]:
        """
        Get indexing status for projects.
        """
        pass
```

**Implementation Steps**:

1. **Step 1**: Tree Discovery Module
   ```python
   async def _discover_tree(self, project_path: str) -> TreeResult:
       """Generate project tree structure."""
       async with OnexTreeClient() as client:
           return await client.generate_tree(
               project_path=project_path,
               include_tests=True
           )
   ```

2. **Step 2**: Intelligence Generation Module
   ```python
   async def _generate_intelligence_batch(
       self,
       files: list[str]
   ) -> list[IntelligenceResult]:
       """Generate intelligence for batch of files."""
       async with MetadataStampingClient() as client:
           tasks = [
               client.generate_intelligence(
                   file_path=f,
                   include_semantic=True,
                   include_compliance=True
               )
               for f in files
           ]
           return await asyncio.gather(*tasks)
   ```

3. **Step 3**: Stamping Module
   ```python
   async def _stamp_files_batch(
       self,
       stamps: list[dict]
   ) -> BatchStampResult:
       """Stamp files with intelligence metadata."""
       async with MetadataStampingClient() as client:
           return await client.batch_stamp(
               stamps=stamps,
               batch_size=100
           )
   ```

4. **Step 4**: Indexing Module
   ```python
   async def _index_in_storage(
       self,
       files: list[FileMetadata]
   ) -> IndexResult:
       """Index files in Qdrant + Memgraph."""
       # Parallel indexing
       vector_task = self._index_in_qdrant(files)
       graph_task = self._index_in_memgraph(files)

       vector_result, graph_result = await asyncio.gather(
           vector_task,
           graph_task
       )

       return IndexResult(
           vector_indexed=vector_result.count,
           graph_indexed=graph_result.count
       )
   ```

5. **Step 5**: Cache Management Module
   ```python
   async def _warm_cache(
       self,
       project_name: str,
       file_metadata: list[FileMetadata]
   ) -> None:
       """Pre-warm cache with common queries."""
       common_queries = [
           f"{concept} in {project_name}"
           for concept in ["authentication", "api", "database", "config"]
       ]

       for query in common_queries:
           # Pre-compute and cache
           await self.search_files(query, projects=[project_name])
   ```

#### Day 4: REST API Endpoints

**File**: `services/intelligence/src/routers/file_location.py`

```python
@router.post("/api/intelligence/file-location/index")
async def index_project(request: ProjectIndexRequest) -> ProjectIndexResult:
    """
    Index a project's files with full intelligence pipeline.

    Performance: <5 minutes for 1000 files
    """
    bridge = TreeStampingBridge()
    return await bridge.index_project(
        project_path=request.project_path,
        project_name=request.project_name,
        include_tests=request.include_tests,
        force_reindex=request.force_reindex
    )


@router.get("/api/intelligence/file-location/search")
async def search_files(
    query: str,
    projects: str | None = None,  # Comma-separated
    min_quality_score: float = 0.0,
    limit: int = 10
) -> FileSearchResult:
    """
    Search for files across projects.

    Performance: <500ms with cache, <2s cold
    """
    bridge = TreeStampingBridge()
    project_list = projects.split(",") if projects else None

    return await bridge.search_files(
        query=query,
        projects=project_list,
        min_quality_score=min_quality_score,
        limit=limit
    )


@router.get("/api/intelligence/file-location/status")
async def get_status(project_name: str | None = None) -> list[ProjectIndexStatus]:
    """Get indexing status for projects."""
    bridge = TreeStampingBridge()
    return await bridge.get_indexing_status(project_name=project_name)
```

#### Day 5: MCP Gateway Integration

**File**: `python/src/mcp_server/tools/internal/file_location.py`

```python
async def find_file_location(
    query: str,
    projects: list[str] | None = None,
    file_types: list[str] | None = None,
    min_quality_score: float = 0.0,
    limit: int = 10
) -> dict:
    """
    Find files across projects using intelligent search.

    Args:
        query: Natural language search query
        projects: Optional list of project names to filter
        file_types: Optional list of file extensions to filter
        min_quality_score: Minimum quality score threshold
        limit: Maximum results to return

    Returns:
        Search results with file locations, confidence, and metadata

    Example:
        archon_menu(
            operation="find_file_location",
            params={
                "query": "authentication module in omniarchon",
                "min_quality_score": 0.7
            }
        )
    """
    # Call Intelligence Service API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://archon-intelligence:8053/api/intelligence/file-location/search",
            params={
                "query": query,
                "projects": ",".join(projects) if projects else None,
                "min_quality_score": min_quality_score,
                "limit": limit
            },
            timeout=5.0
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {
                "success": False,
                "error": f"Search failed: {response.status_code}"
            }
```

**Register in MCP Gateway**:
```python
# python/src/mcp_server/gateway.py

INTERNAL_OPERATIONS = {
    # ... existing operations ...
    "find_file_location": {
        "category": "file_location",
        "description": "Find files across projects using intelligent search",
        "handler": find_file_location,
        "parameters": {
            "query": "str (required)",
            "projects": "list[str] (optional)",
            "file_types": "list[str] (optional)",
            "min_quality_score": "float (optional, default: 0.0)",
            "limit": "int (optional, default: 10)"
        }
    }
}
```

**Success Criteria**:
- ✅ TreeStampingBridge service implemented
- ✅ REST API endpoints deployed
- ✅ MCP gateway operation registered
- ✅ Unit tests passing (80%+ coverage)

---

### Phase 3: Intelligence API Update (Days 6-7)

**Objective**: Expose file location search through Intelligence Service and MCP Gateway.

#### Day 6: Testing & Validation

**Test Cases**:

1. **Unit Tests** (`tests/unit/test_tree_stamping_bridge.py`)
   ```python
   async def test_index_project():
       """Test project indexing pipeline."""
       pass

   async def test_search_files():
       """Test file search with various queries."""
       pass

   async def test_cache_hit():
       """Test cache warming and hit rate."""
       pass
   ```

2. **Integration Tests** (`tests/integration/test_file_location_e2e.py`)
   ```python
   async def test_index_search_roundtrip():
       """Test complete pipeline: index → search → results."""
       # 1. Index test project
       index_result = await bridge.index_project(
           project_path="/path/to/test/project",
           project_name="test-project"
       )
       assert index_result.success
       assert index_result.files_indexed > 0

       # 2. Search for file
       search_result = await bridge.search_files(
           query="authentication module",
           projects=["test-project"]
       )
       assert search_result.success
       assert len(search_result.results) > 0

       # 3. Verify file found
       top_result = search_result.results[0]
       assert "auth" in top_result.file_path.lower()
       assert top_result.confidence > 0.7
   ```

3. **MCP Integration Tests** (`tests/integration/test_mcp_file_location.py`)
   ```python
   async def test_mcp_find_file_location():
       """Test MCP gateway operation."""
       result = await archon_menu(
           operation="find_file_location",
           params={
               "query": "authentication in test-project",
               "min_quality_score": 0.7
           }
       )
       assert result["success"]
       assert len(result["results"]) > 0
   ```

4. **Performance Tests** (`tests/performance/test_file_location_performance.py`)
   ```python
   async def test_indexing_performance():
       """Verify indexing performance targets."""
       start = time.perf_counter()
       result = await bridge.index_project(
           project_path="/path/to/1000file/project",
           project_name="perf-test"
       )
       duration = time.perf_counter() - start

       assert result.success
       assert result.files_indexed >= 1000
       assert duration < 300  # <5 minutes for 1000 files

   async def test_search_performance_cold():
       """Verify cold search performance."""
       start = time.perf_counter()
       result = await bridge.search_files(
           query="authentication module",
           projects=["perf-test"]
       )
       duration = time.perf_counter() - start

       assert result.success
       assert duration < 2.0  # <2s cold search

   async def test_search_performance_warm():
       """Verify warm cache search performance."""
       # First search (populate cache)
       await bridge.search_files(query="authentication")

       # Second search (cache hit)
       start = time.perf_counter()
       result = await bridge.search_files(query="authentication")
       duration = time.perf_counter() - start

       assert result.success
       assert result.cache_hit
       assert duration < 0.5  # <500ms with cache
   ```

#### Day 7: Performance Optimization

**Optimization Tasks**:

1. **Batch Processing**:
   - Process 100 files at a time during indexing
   - Use asyncio.gather for parallel intelligence generation
   - Batch Qdrant inserts (100 vectors per batch)

2. **Cache Strategy**:
   - Pre-warm cache with common queries during indexing
   - Cache search results for 5 minutes
   - Cache project status for 1 hour
   - Invalidate cache on reindex

3. **Query Optimization**:
   - Parallel execution: RAG + Qdrant + Memgraph
   - Early termination when confidence threshold reached
   - Result ranking optimization (weighted scores)

4. **Connection Pooling**:
   - Reuse httpx clients across requests
   - Connection pool size: 20 connections
   - Keepalive: 30 seconds

**Success Criteria**:
- ✅ All tests passing (unit + integration + performance)
- ✅ Code coverage >80%
- ✅ Performance targets met:
  - Indexing: <5 minutes for 1000 files
  - Cold search: <2s
  - Warm search: <500ms
- ✅ Error handling comprehensive

---

## Testing Strategy

### Test Project Setup

**Test Repository**: `/tmp/archon-test-project`

**Structure**:
```
archon-test-project/
├── src/
│   ├── auth/
│   │   ├── jwt_handler.py          # Effect node
│   │   ├── user_authenticator.py   # Compute node
│   │   └── session_manager.py      # Reducer node
│   ├── api/
│   │   ├── endpoints.py            # Effect node
│   │   ├── validators.py           # Compute node
│   │   └── rate_limiter.py         # Reducer node
│   └── database/
│       ├── connection_pool.py      # Effect node
│       ├── query_builder.py        # Compute node
│       └── result_aggregator.py    # Reducer node
├── tests/
│   ├── test_auth.py
│   ├── test_api.py
│   └── test_database.py
└── README.md
```

**Test Data**: 50 Python files with varying:
- Quality scores (0.6 - 0.95)
- ONEX types (Effect, Compute, Reducer, Orchestrator)
- Semantic concepts (auth, api, database, config, etc.)

### Integration Test: End-to-End

**File**: `tests/integration/test_file_location_e2e.py`

```python
async def test_complete_workflow():
    """
    Test complete workflow:
    1. Index test project
    2. Perform various searches
    3. Verify results accuracy
    4. Test cache behavior
    5. Validate performance
    """

    # Step 1: Index project
    logger.info("Indexing test project...")
    start_time = time.perf_counter()

    index_result = await bridge.index_project(
        project_path="/tmp/archon-test-project",
        project_name="archon-test-project",
        include_tests=True
    )

    index_duration = time.perf_counter() - start_time

    assert index_result.success, "Indexing failed"
    assert index_result.files_indexed == 50, f"Expected 50 files, got {index_result.files_indexed}"
    assert index_duration < 30, f"Indexing took {index_duration:.2f}s (expected <30s)"

    logger.info(f"✅ Indexed 50 files in {index_duration:.2f}s")

    # Step 2: Search for authentication module (cold)
    logger.info("Testing cold search...")
    start_time = time.perf_counter()

    search_result = await bridge.search_files(
        query="authentication module with JWT",
        projects=["archon-test-project"],
        min_quality_score=0.7,
        limit=5
    )

    search_duration = time.perf_counter() - start_time

    assert search_result.success, "Search failed"
    assert len(search_result.results) > 0, "No results found"
    assert search_duration < 2.0, f"Cold search took {search_duration:.2f}s (expected <2s)"

    top_result = search_result.results[0]
    assert "auth" in top_result.file_path.lower(), "Top result not auth-related"
    assert top_result.confidence > 0.7, f"Low confidence: {top_result.confidence}"

    logger.info(f"✅ Cold search: {search_duration:.2f}s, confidence: {top_result.confidence}")

    # Step 3: Same search (cache hit)
    logger.info("Testing warm search...")
    start_time = time.perf_counter()

    search_result_2 = await bridge.search_files(
        query="authentication module with JWT",
        projects=["archon-test-project"],
        min_quality_score=0.7,
        limit=5
    )

    cache_duration = time.perf_counter() - start_time

    assert search_result_2.success
    assert search_result_2.cache_hit, "Cache miss on second query"
    assert cache_duration < 0.5, f"Cache search took {cache_duration:.2f}s (expected <500ms)"

    logger.info(f"✅ Warm search: {cache_duration:.2f}s (cache hit)")

    # Step 4: Test different queries
    test_queries = [
        ("database connection pool", "database", "connection"),
        ("api endpoint validation", "api", "validators"),
        ("rate limiting logic", "api", "rate_limiter"),
    ]

    for query, expected_dir, expected_file in test_queries:
        result = await bridge.search_files(
            query=query,
            projects=["archon-test-project"],
            limit=3
        )

        assert result.success
        assert len(result.results) > 0

        top_match = result.results[0]
        assert expected_dir in top_match.file_path, f"Expected {expected_dir} in path"
        assert expected_file in top_match.file_path, f"Expected {expected_file} in path"

        logger.info(f"✅ Query '{query}' → {top_match.file_path}")

    # Step 5: Test MCP integration
    logger.info("Testing MCP gateway...")
    mcp_result = await archon_menu(
        operation="find_file_location",
        params={
            "query": "authentication in archon-test-project",
            "min_quality_score": 0.7
        }
    )

    assert mcp_result["success"]
    assert len(mcp_result["results"]) > 0
    assert mcp_result["query_time_ms"] < 2000

    logger.info(f"✅ MCP search: {mcp_result['query_time_ms']}ms")

    # Step 6: Verify indexing status
    status = await bridge.get_indexing_status(project_name="archon-test-project")

    assert len(status) == 1
    assert status[0].project_name == "archon-test-project"
    assert status[0].indexed == True
    assert status[0].file_count == 50

    logger.info(f"✅ Status check: {status[0].file_count} files indexed")

    logger.info("🎉 All tests passed!")
```

### Performance Benchmark

**File**: `tests/performance/test_file_location_benchmark.py`

```python
async def test_performance_benchmark():
    """
    Benchmark performance across different project sizes:
    - 50 files (test project)
    - 500 files (medium project)
    - 1000 files (large project)
    """

    test_cases = [
        {"name": "small", "files": 50, "max_index_time": 30},
        {"name": "medium", "files": 500, "max_index_time": 150},
        {"name": "large", "files": 1000, "max_index_time": 300},
    ]

    results = []

    for test_case in test_cases:
        # Generate test project
        project_path = generate_test_project(
            name=f"perf-test-{test_case['name']}",
            file_count=test_case["files"]
        )

        # Benchmark indexing
        start = time.perf_counter()
        index_result = await bridge.index_project(
            project_path=project_path,
            project_name=f"perf-test-{test_case['name']}"
        )
        index_duration = time.perf_counter() - start

        # Benchmark cold search
        start = time.perf_counter()
        search_result = await bridge.search_files(
            query="authentication module",
            projects=[f"perf-test-{test_case['name']}"]
        )
        cold_search_duration = time.perf_counter() - start

        # Benchmark warm search
        start = time.perf_counter()
        search_result_2 = await bridge.search_files(
            query="authentication module",
            projects=[f"perf-test-{test_case['name']}"]
        )
        warm_search_duration = time.perf_counter() - start

        # Record results
        results.append({
            "project_size": test_case["files"],
            "index_time_sec": index_duration,
            "cold_search_ms": cold_search_duration * 1000,
            "warm_search_ms": warm_search_duration * 1000,
            "passed": index_duration < test_case["max_index_time"]
        })

        # Assert performance targets
        assert index_duration < test_case["max_index_time"], \
            f"{test_case['name']} indexing too slow: {index_duration:.2f}s"
        assert cold_search_duration < 2.0, \
            f"{test_case['name']} cold search too slow: {cold_search_duration:.2f}s"
        assert warm_search_duration < 0.5, \
            f"{test_case['name']} warm search too slow: {warm_search_duration:.2f}s"

    # Print benchmark report
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("="*60)
    for result in results:
        print(f"\nProject Size: {result['project_size']} files")
        print(f"  Index Time:       {result['index_time_sec']:.2f}s")
        print(f"  Cold Search:      {result['cold_search_ms']:.0f}ms")
        print(f"  Warm Search:      {result['warm_search_ms']:.0f}ms")
        print(f"  Status:           {'✅ PASS' if result['passed'] else '❌ FAIL'}")
    print("="*60)
```

---

## Success Metrics

### Performance Targets

| Metric | Target | Acceptable | Measurement |
|--------|--------|------------|-------------|
| **Indexing** | | | |
| 50 files | <30s | <60s | End-to-end indexing time |
| 500 files | <2.5min | <5min | End-to-end indexing time |
| 1000 files | <5min | <10min | End-to-end indexing time |
| **Search** | | | |
| Cold search | <500ms | <2s | Query execution time |
| Warm search (cache) | <100ms | <500ms | Query execution time |
| Cross-project search | <1s | <3s | Multi-project query time |
| **Quality** | | | |
| Search accuracy | >95% | >85% | Correct file in top 3 |
| Confidence calibration | ±5% | ±10% | Predicted vs actual relevance |
| Cache hit rate | >60% | >40% | Percentage of cached queries |
| **Availability** | | | |
| Service uptime | 99.9% | 99.0% | Service availability |
| Error rate | <0.1% | <1% | Failed requests / total |

### Functional Success Criteria

**Must Have** (MVP):
- ✅ All 12 services healthy and communicating
- ✅ Project indexing works end-to-end (tree → intelligence → stamp → index)
- ✅ File search returns accurate results (>85% accuracy)
- ✅ MCP tool accessible via archon_menu operation
- ✅ Performance targets met (indexing <5min/1000 files, search <2s cold)
- ✅ Basic caching working (cache hit rate >40%)

**Should Have** (Nice to Have):
- Cross-project search with filtering
- Advanced result ranking (quality + semantic + compliance + recency)
- Cache warming during indexing
- Real-time indexing updates (watch filesystem)

**Could Have** (Future):
- Code dependency graph in Memgraph
- File similarity recommendations
- Historical change tracking
- Multi-language support (beyond Python)

### Quality Gates

**Before Production Deployment**:
1. ✅ All unit tests passing (80%+ coverage)
2. ✅ All integration tests passing
3. ✅ Performance benchmarks passing
4. ✅ Manual testing successful:
   - Index omniarchon project (1200+ files)
   - Search for 20 different file types
   - Verify accuracy >85%
5. ✅ Documentation complete:
   - API documentation
   - MCP tool usage examples
   - Performance tuning guide
6. ✅ Monitoring configured:
   - Service health dashboards
   - Performance metrics tracking
   - Error rate alerting

---

## Dependencies

### Service Dependencies

**Required (MUST be running)**:
- ✅ archon-intelligence (8053) - Core intelligence
- ✅ archon-bridge (8054) - Intelligence generation
- ✅ archon-mcp (8151) - MCP gateway
- ✅ omninode-bridge-onextree (8058) - Tree discovery
- ✅ omninode-bridge-metadata-stamping (8057) - Stamping
- ✅ archon-qdrant (6333) - Vector storage
- ✅ archon-memgraph (7687) - Graph storage
- ✅ archon-valkey (6379) - Cache

**Optional (Performance enhancement)**:
- archon-langextract (8156) - Semantic analysis
- archon-search (8055) - RAG queries

### Library Dependencies

**Python** (`pyproject.toml`):
```toml
[tool.poetry.dependencies]
python = "^3.11"
httpx = "^0.27.0"  # Already installed
pydantic = "^2.9.0"  # Already installed
asyncio = "^3.4.3"  # Built-in
qdrant-client = "^1.11.0"  # Already installed
neo4j = "^5.0.0"  # For Memgraph (compatible)
redis = "^5.0.0"  # For Valkey (compatible)

# New additions (if needed)
blake3 = "^0.3.4"  # For file hashing
```

**Verification**:
```bash
cd python
poetry show | grep -E "httpx|pydantic|qdrant|redis"
```

### External Services

**None required** - All services are internal to Archon ecosystem.

---

## Risk Mitigation

### Potential Risks

**1. Performance Degradation**
- **Risk**: Indexing 1000 files takes >5 minutes
- **Mitigation**:
  - Batch processing (100 files at a time)
  - Parallel intelligence generation
  - Connection pooling
  - Cache warming
- **Fallback**: Reduce batch size, increase timeout

**2. Storage Overhead**
- **Risk**: Qdrant/Memgraph storage fills up with large projects
- **Mitigation**:
  - Monitor storage usage
  - Implement cleanup policy (delete old indexes)
  - Compress metadata before storage
- **Fallback**: Increase storage limits, implement data retention policy

**3. Service Unavailability**
- **Risk**: OnexTree or Stamping service fails during indexing
- **Mitigation**:
  - Retry logic with exponential backoff
  - Circuit breaker pattern (already in clients)
  - Graceful degradation (skip problematic files)
- **Fallback**: Resume indexing from last checkpoint

**4. Search Accuracy Issues**
- **Risk**: Search returns irrelevant files (<85% accuracy)
- **Mitigation**:
  - Test with diverse query types
  - Tune ranking weights (quality, semantic, compliance)
  - Collect user feedback for continuous improvement
- **Fallback**: Manual fallback search, improve training data

**5. Cache Invalidation Problems**
- **Risk**: Stale cache entries return outdated results
- **Mitigation**:
  - TTL-based expiration (5 minutes)
  - Invalidate cache on reindex
  - Version-based cache keys
- **Fallback**: Disable cache, force fresh queries

### Monitoring & Alerts

**Key Metrics to Monitor**:
1. Indexing duration per project
2. Search query latency (p50, p95, p99)
3. Cache hit rate
4. Error rate per service
5. Storage usage (Qdrant, Memgraph)
6. Service health status

**Alerting Rules**:
- Indexing duration >10 minutes → Warning
- Search latency p95 >3s → Warning
- Cache hit rate <30% → Info
- Error rate >1% → Critical
- Storage usage >80% → Warning
- Service unhealthy >5 minutes → Critical

---

## Production Deployment

### Deployment Checklist

**Pre-Deployment**:
- [ ] All services healthy and verified
- [ ] Integration tests passing
- [ ] Performance benchmarks passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Monitoring configured

**Deployment Steps**:

1. **Deploy Integration Service** (Day 8)
   ```bash
   # Add TreeStampingBridge to intelligence service
   cd services/intelligence

   # Verify imports
   python3 -c "from src.integrations.tree_stamping_bridge import TreeStampingBridge"

   # Restart service
   docker compose restart archon-intelligence

   # Verify health
   curl http://localhost:8053/health
   ```

2. **Deploy REST API Endpoints** (Day 8)
   ```bash
   # Add file_location router
   cd services/intelligence

   # Verify endpoint
   curl http://localhost:8053/api/intelligence/file-location/status
   ```

3. **Deploy MCP Gateway Operation** (Day 8)
   ```bash
   # Add find_file_location tool
   cd python

   # Restart MCP server
   docker compose restart archon-mcp

   # Verify operation
   curl http://localhost:8151/mcp -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"archon_menu","arguments":{"operation":"discover"}}}'
   ```

4. **Index Initial Projects** (Day 9)
   ```bash
   # Index omniarchon project
   curl -X POST http://localhost:8053/api/intelligence/file-location/index \
     -H "Content-Type: application/json" \
     -d '{
       "project_path": "/Volumes/PRO-G40/Code/omniarchon",
       "project_name": "omniarchon",
       "include_tests": true
     }'

   # Monitor progress
   curl http://localhost:8053/api/intelligence/file-location/status?project_name=omniarchon
   ```

5. **Validate Deployment** (Day 9)
   ```bash
   # Test search via MCP
   python3 -c "
   import asyncio
   from mcp_client import archon_menu

   async def test():
       result = await archon_menu(
           operation='find_file_location',
           params={'query': 'authentication in omniarchon', 'min_quality_score': 0.7}
       )
       print(result)

   asyncio.run(test())
   "
   ```

**Post-Deployment**:
- [ ] Monitor service health for 24 hours
- [ ] Verify performance metrics
- [ ] Check error logs
- [ ] Validate search accuracy
- [ ] Update CLAUDE.md with new operation

---

## Documentation

### API Documentation

**Location**: `docs/api/file-location-api.md`

**Contents**:
- REST API endpoint specifications
- Request/response schemas
- Error codes and handling
- Performance characteristics
- Usage examples

### MCP Tool Documentation

**Location**: `docs/mcp/find-file-location.md`

**Contents**:
- Tool description and purpose
- Parameter specifications
- Return value schema
- Usage examples (Claude Code)
- Best practices

### Performance Tuning Guide

**Location**: `docs/guides/file-location-performance-tuning.md`

**Contents**:
- Indexing optimization strategies
- Search performance tuning
- Cache configuration
- Batch processing guidelines
- Troubleshooting common issues

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1: Service Validation | Day 1 | All services verified healthy |
| Phase 2: Integration Development | Days 2-5 | TreeStampingBridge + REST API + MCP tool |
| Phase 3: Testing & Optimization | Days 6-7 | All tests passing, performance optimized |
| Production Deployment | Days 8-9 | Live in production, initial projects indexed |
| Documentation | Days 10-11 | Complete documentation |

**Total Duration**: 11 working days (~2 weeks)

---

## Next Steps (Immediate Actions)

### Day 1 Actions

1. **Verify Service Health** (30 minutes)
   ```bash
   # Run health check script
   python3 scripts/verify_services.py
   ```

2. **Test OnexTreeClient** (1 hour)
   ```bash
   # Run client test
   python3 python/tests/integration/test_onex_tree_client.py
   ```

3. **Test MetadataStampingClient** (1 hour)
   ```bash
   # Run client test
   python3 python/tests/integration/test_metadata_stamping_client.py
   ```

4. **Create Test Project** (30 minutes)
   ```bash
   # Generate test project
   python3 scripts/generate_test_project.py \
     --output /tmp/archon-test-project \
     --files 50
   ```

5. **Review Architecture** (1 hour)
   - Review this document with team
   - Validate technical approach
   - Identify any gaps or concerns

### Day 2 Actions

1. **Create Integration Service** (4 hours)
   - Implement TreeStampingBridge class
   - Add tree discovery module
   - Add intelligence generation module
   - Add basic error handling

2. **Set Up Development Environment** (1 hour)
   - Create feature branch
   - Set up testing infrastructure
   - Configure logging

3. **Write Initial Tests** (2 hours)
   - Unit tests for TreeStampingBridge
   - Mock services for testing
   - Basic assertions

---

## Conclusion

This POC provides a comprehensive, actionable plan to integrate OnexTree filesystem discovery with Metadata Stamping intelligence, enabling automatic file path resolution across all codebases. The architecture leverages existing services (Tree, Stamping, Intelligence, MCP) and adds a lightweight orchestration layer (TreeStampingBridge) to coordinate the pipeline.

**Key Success Factors**:
1. ✅ All required services are already running and healthy
2. ✅ HTTP clients exist for Tree and Stamping services
3. ✅ Clear integration points identified
4. ✅ Performance targets realistic and achievable
5. ✅ Comprehensive testing strategy in place

**Expected Outcomes**:
- Agents can find any file across all projects in <500ms
- Cross-project intelligence search works seamlessly
- 95%+ accuracy for file location queries
- Production-ready within 1-2 weeks

**Next Immediate Action**: Execute Day 1 tasks to verify all services and prepare for integration development.

---

**Document Metadata**:
- **Created**: 2025-10-24
- **Author**: Polymorphic Agent (Claude Code)
- **Status**: Planning
- **Next Review**: After Phase 1 completion (Day 1)
