# Poly Implementation Handoff Document

**Phase**: Phase 2 - Parallel Implementation
**Created**: 2025-10-22
**Contract**: See `EVENT_HANDLER_CONTRACTS.md`
**Status**: Ready for Poly spawning

## Mission

Implement three event handlers in parallel to enable:
1. Full intelligence pipeline for document indexing
2. Batch repository processing
3. Multi-source intelligent search

## Poly Assignments

### Poly 1: Document Indexing Handler
**Branch**: `feature/document-indexing-handler`
**Files to create**:
- `services/intelligence/src/events/models/document_indexing_events.py`
- `services/intelligence/src/handlers/document_indexing_handler.py`
- `python/tests/intelligence/integration/test_document_indexing_flow.py`

### Poly 2: Repository Crawler Handler
**Branch**: `feature/repository-crawler-handler`
**Files to create**:
- `services/intelligence/src/events/models/repository_crawler_events.py`
- `services/intelligence/src/handlers/repository_crawler_handler.py`
- `python/tests/intelligence/integration/test_repository_crawler_flow.py`

### Poly 3: Search Handler
**Branch**: `feature/search-handler`
**Files to create**:
- `services/intelligence/src/events/models/search_events.py`
- `services/intelligence/src/handlers/search_handler.py`
- `python/tests/intelligence/integration/test_search_flow.py`

---

## Shared Contract (READ-ONLY)

All Polys must reference `EVENT_HANDLER_CONTRACTS.md` for:
- Event payload schemas
- Error code enums
- Service integration requirements
- Kafka topic naming conventions

**CRITICAL**: Do NOT modify the contract document. If you discover issues, note them for Phase 3 integration discussion.

---

## Implementation Template

Each Poly should follow this implementation sequence:

### Step 1: Create Event Models File (30 mins)

**Pattern**: Follow `services/intelligence/src/events/models/intelligence_adapter_events.py`

**Required Components**:
1. **Enum Definitions**
   - Event types enum
   - Operation types enum (if applicable)
   - Error codes enum

2. **Payload Models** (3 models)
   - Request payload (with validators)
   - Completed payload (frozen=True)
   - Failed payload (frozen=True)

3. **Event Helpers Class**
   - Topic routing configuration
   - `create_{operation}_requested_event()`
   - `create_{operation}_completed_event()`
   - `create_{operation}_failed_event()`
   - `get_kafka_topic()`
   - `deserialize_event()`

4. **Convenience Functions**
   - `create_request_event()`
   - `create_completed_event()`
   - `create_failed_event()`

**Validation**:
```python
# Run type checking
mypy services/intelligence/src/events/models/{your_file}.py

# Test model instantiation
python -c "from services.intelligence.src.events.models.{your_file} import *; print('OK')"
```

### Step 2: Create Event Handler File (2-3 hours)

**Pattern**: Follow `services/intelligence/src/handlers/intelligence_adapter_handler.py`

**Required Components**:

1. **Handler Class** (extends `BaseResponsePublisher`)
```python
class {YourHandler}(BaseResponsePublisher):
    # Topic constants
    REQUEST_TOPIC = "dev.archon-intelligence.intelligence.{event}-requested.v1"
    COMPLETED_TOPIC = "dev.archon-intelligence.intelligence.{event}-completed.v1"
    FAILED_TOPIC = "dev.archon-intelligence.intelligence.{event}-failed.v1"

    def __init__(self, ...):
        super().__init__()
        # Initialize services (scorer, clients, etc.)
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
        }

    def can_handle(self, event_type: str) -> bool:
        """Check if handler can process event type."""
        pass

    async def handle_event(self, event: Any) -> bool:
        """Main event handling logic."""
        pass

    def get_handler_name(self) -> str:
        """Return handler name for registration."""
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Return handler metrics."""
        pass
```

2. **Private Helper Methods**
```python
async def _process_{operation}(...) -> Dict[str, Any]:
    """Core business logic."""
    pass

async def _publish_completed_response(...) -> None:
    """Publish success event."""
    pass

async def _publish_failed_response(...) -> None:
    """Publish failure event."""
    pass

def _get_correlation_id(self, event: Any) -> str:
    """Extract correlation ID."""
    pass

def _get_payload(self, event: Any) -> Dict[str, Any]:
    """Extract payload."""
    pass
```

3. **Service Integration**
   - For Document Indexing: Orchestrate 5 services in parallel
   - For Repository Crawler: File discovery + batch publishing
   - For Search: Aggregate 3 search sources

**Validation**:
```python
# Type checking
mypy services/intelligence/src/handlers/{your_file}.py

# Import check
python -c "from services.intelligence.src.handlers.{your_file} import *; print('OK')"
```

### Step 3: Create Integration Tests (1-2 hours)

**Pattern**: Follow `python/tests/intelligence/integration/test_intelligence_event_flow_real.py`

**Required Test Cases**:

1. **Test End-to-End Success Flow**
```python
async def test_end_to_end_success_flow_real(self):
    """Publish REQUEST → Receive COMPLETED."""
    # 1. Create Kafka producer and consumer
    # 2. Publish REQUEST event
    # 3. Listen for COMPLETED event
    # 4. Verify payload structure
    # 5. Verify correlation ID preserved
```

2. **Test End-to-End Failure Flow**
```python
async def test_end_to_end_failure_flow_real(self):
    """Publish invalid REQUEST → Receive FAILED."""
    # 1. Publish invalid/malformed request
    # 2. Listen for FAILED event
    # 3. Verify error code and message
```

3. **Test Correlation ID Tracking**
```python
async def test_correlation_id_tracking_real(self):
    """Verify correlation ID preserved."""
    # 1. Generate unique correlation ID
    # 2. Publish request with that ID
    # 3. Verify response has same ID
```

**Test Infrastructure**:
```python
async def _create_kafka_producer(self) -> AIOKafkaProducer:
    """Create real Kafka producer (localhost:29102)."""
    pass

async def _create_kafka_consumer(self, topics, group_id) -> AIOKafkaConsumer:
    """Create real Kafka consumer."""
    pass

async def _consume_event_with_correlation_id(
    self, consumer, correlation_id, timeout_seconds
) -> Optional[dict]:
    """Wait for event with matching correlation ID."""
    pass
```

**Validation**:
```bash
# Run integration tests (requires Docker services running)
cd /Volumes/PRO-G40/Code/omniarchon/python
timeout 90 poetry run python tests/intelligence/integration/test_{your}_flow.py
```

### Step 4: Update Configuration (15 mins)

1. **Update Kafka Topics Config** (`services/intelligence/src/kafka_topics_config.py`):
```python
TOPICS = {
    # ... existing topics ...
    "{YOUR_REQUEST}": "dev.archon-intelligence.intelligence.{your}-requested.v1",
    "{YOUR_COMPLETED}": "dev.archon-intelligence.intelligence.{your}-completed.v1",
    "{YOUR_FAILED}": "dev.archon-intelligence.intelligence.{your}-failed.v1",
}
```

2. **Register Handler** (`services/intelligence/src/kafka_consumer.py`):
```python
# Import handler
from src.handlers.{your}_handler import {YourHandler}

# Initialize in __init__()
self.{your}_handler = {YourHandler}(...)

# Register in _register_handlers()
self._router.register_handler(self.{your}_handler)
```

---

## Service Integration Guides

### Document Indexing Handler Services

#### 1. Metadata Stamping (Bridge:8057)
```python
import httpx

async def stamp_metadata(content: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8057/api/stamp-metadata",
            json={"content": content},
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()
    # Returns: {"hash": "blake3:...", "timestamp": "...", "dedupe_status": "..."}
```

#### 2. Entity Extraction (LangExtract:8156)
```python
async def extract_entities(content: str, language: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8156/extract/code",
            json={"content": content, "language": language, "file_path": "..."},
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
    # Returns: {"entities": [...], "relationships": [...], "ast_metadata": {...}}
```

#### 3. Vector Indexing (Qdrant:6333)
```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

async def index_vectors(chunks: list[str], collection_name: str) -> list[str]:
    client = QdrantClient(host="localhost", port=6333)

    # Create collection if needed
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    # Generate embeddings (use OpenAI or other embedding service)
    embeddings = await generate_embeddings(chunks)

    # Upload points
    points = [
        PointStruct(id=idx, vector=emb, payload={"text": chunk})
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    client.upsert(collection_name=collection_name, points=points)

    return [str(idx) for idx in range(len(chunks))]
```

#### 4. Knowledge Graph (Memgraph:7687)
```python
from neo4j import AsyncGraphDatabase

async def index_knowledge_graph(entities: list, relationships: list) -> dict:
    driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7687",
        auth=None,
    )

    async with driver.session() as session:
        # Create entities
        entity_ids = []
        for entity in entities:
            result = await session.run(
                "CREATE (e:Entity {name: $name, type: $type}) RETURN id(e) as id",
                name=entity["name"],
                type=entity["type"],
            )
            record = await result.single()
            entity_ids.append(str(record["id"]))

        # Create relationships
        relationship_ids = []
        for rel in relationships:
            result = await session.run(
                "MATCH (a:Entity), (b:Entity) "
                "WHERE id(a) = $from_id AND id(b) = $to_id "
                "CREATE (a)-[r:RELATES_TO {type: $rel_type}]->(b) "
                "RETURN id(r) as id",
                from_id=rel["from_id"],
                to_id=rel["to_id"],
                rel_type=rel["type"],
            )
            record = await result.single()
            relationship_ids.append(str(record["id"]))

    await driver.close()
    return {"entity_ids": entity_ids, "relationship_ids": relationship_ids}
```

#### 5. Quality Assessment (Intelligence:8053)
```python
async def assess_quality(content: str, source_path: str, language: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8053/assess/code",
            json={
                "content": content,
                "source_path": source_path,
                "language": language,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
    # Returns: {"quality_score": 0.87, "onex_compliance": 0.92, ...}
```

#### Parallel Orchestration Pattern
```python
async def process_document(content: str, source_path: str, language: str) -> dict:
    """Orchestrate all services in parallel."""

    # Check cache first (metadata stamping)
    metadata = await stamp_metadata(content)
    if metadata.get("dedupe_status") == "duplicate":
        return {"cache_hit": True, "document_hash": metadata["hash"]}

    # Run remaining services in parallel
    results = await asyncio.gather(
        extract_entities(content, language),
        assess_quality(content, source_path, language),
        return_exceptions=True,  # Graceful degradation
    )

    entities_result, quality_result = results

    # Check for failures
    if isinstance(entities_result, Exception):
        raise ValueError(f"Entity extraction failed: {entities_result}")
    if isinstance(quality_result, Exception):
        # Continue without quality assessment
        quality_result = {"quality_score": None, "onex_compliance": None}

    # Index vectors and knowledge graph in parallel
    chunks = chunk_content(content, chunk_size=1000, overlap=200)

    vector_result, kg_result = await asyncio.gather(
        index_vectors(chunks, collection_name="code_chunks"),
        index_knowledge_graph(
            entities=entities_result["entities"],
            relationships=entities_result["relationships"],
        ),
        return_exceptions=True,
    )

    return {
        "document_hash": metadata["hash"],
        "entity_ids": kg_result.get("entity_ids", []),
        "vector_ids": vector_result if not isinstance(vector_result, Exception) else [],
        "quality_score": quality_result.get("quality_score"),
        "onex_compliance": quality_result.get("onex_compliance"),
        "entities_extracted": len(entities_result.get("entities", [])),
        "relationships_created": len(kg_result.get("relationship_ids", [])),
        "chunks_indexed": len(vector_result) if not isinstance(vector_result, Exception) else 0,
    }
```

### Repository Crawler Handler Services

#### File Discovery Pattern
```python
import os
from pathlib import Path
from fnmatch import fnmatch

async def discover_files(
    repository_path: str,
    file_patterns: list[str],
    exclude_patterns: list[str],
) -> list[dict]:
    """Discover all matching files in repository."""

    discovered_files = []

    for root, dirs, files in os.walk(repository_path):
        # Filter directories (in-place modification)
        dirs[:] = [
            d for d in dirs
            if not any(fnmatch(os.path.join(root, d), pattern) for pattern in exclude_patterns)
        ]

        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, repository_path)

            # Check if matches include patterns
            if any(fnmatch(relative_path, pattern) for pattern in file_patterns):
                # Check if excluded
                if any(fnmatch(relative_path, pattern) for pattern in exclude_patterns):
                    continue

                discovered_files.append({
                    "path": relative_path,
                    "absolute_path": file_path,
                    "size": os.path.getsize(file_path),
                    "language": detect_language(file_path),
                })

    return discovered_files

def detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext_mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".js": "javascript",
        ".jsx": "javascript",
    }
    ext = Path(file_path).suffix
    return ext_mapping.get(ext, "unknown")
```

#### Batch Publishing Pattern
```python
async def publish_batch(
    files: list[dict],
    project_id: str,
    batch_size: int,
    indexing_options: dict,
    producer: AIOKafkaProducer,
) -> int:
    """Publish files in batches as DOCUMENT_INDEX_REQUESTED events."""

    published_count = 0

    for i in range(0, len(files), batch_size):
        batch = files[i:i+batch_size]

        for file_info in batch:
            # Read file content
            with open(file_info["absolute_path"], "r", encoding="utf-8") as f:
                content = f.read()

            # Create DOCUMENT_INDEX_REQUESTED event
            event = create_request_event(
                source_path=file_info["path"],
                content=content,
                language=file_info["language"],
                project_id=project_id,
                indexing_options=indexing_options,
            )

            # Publish to Kafka
            await producer.send_and_wait(
                "dev.archon-intelligence.intelligence.document-index-requested.v1",
                value=event,
            )

            published_count += 1

        # Log batch progress
        logger.info(f"Published batch {i//batch_size + 1}: {len(batch)} files")

    return published_count
```

### Search Handler Services

#### Multi-Source Aggregation Pattern
```python
async def aggregate_search_results(
    query: str,
    max_results: int,
    filters: dict,
) -> dict:
    """Aggregate results from RAG, Vector, and Knowledge Graph."""

    # Query all sources in parallel
    results = await asyncio.gather(
        search_rag(query, max_results, filters),
        search_vector(query, max_results, filters),
        search_knowledge_graph(query, max_results, filters),
        return_exceptions=True,
    )

    rag_results, vector_results, kg_results = results

    # Handle failures gracefully
    all_results = []
    sources_queried = []

    if not isinstance(rag_results, Exception):
        all_results.extend(rag_results)
        sources_queried.append("rag")

    if not isinstance(vector_results, Exception):
        all_results.extend(vector_results)
        sources_queried.append("vector")

    if not isinstance(kg_results, Exception):
        all_results.extend(kg_results)
        sources_queried.append("knowledge_graph")

    # Deduplicate and rank
    ranked_results = deduplicate_and_rank(all_results, max_results)

    return {
        "results": ranked_results,
        "sources_queried": sources_queried,
        "total_results": len(ranked_results),
    }

async def search_rag(query: str, max_results: int, filters: dict) -> list:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8055/search",
            json={"query": query, "limit": max_results, "filters": filters},
            timeout=5.0,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "source_path": r["path"],
                "score": r["score"],
                "content": r["content"],
                "metadata": r.get("metadata", {}),
            }
            for r in data.get("results", [])
        ]

async def search_vector(query: str, max_results: int, filters: dict) -> list:
    from qdrant_client import QdrantClient

    client = QdrantClient(host="localhost", port=6333)

    # Generate query embedding
    query_embedding = await generate_embedding(query)

    # Search Qdrant
    search_result = client.search(
        collection_name="code_chunks",
        query_vector=query_embedding,
        limit=max_results,
    )

    return [
        {
            "source_path": hit.payload.get("file_path", "unknown"),
            "score": hit.score,
            "content": hit.payload.get("text", ""),
            "metadata": hit.payload,
        }
        for hit in search_result
    ]

async def search_knowledge_graph(query: str, max_results: int, filters: dict) -> list:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=None)

    async with driver.session() as session:
        # Full-text search on entity names
        result = await session.run(
            "MATCH (e:Entity) "
            "WHERE e.name CONTAINS $query "
            "RETURN e.name as name, e.type as type, e.file_path as path "
            "LIMIT $limit",
            query=query,
            limit=max_results,
        )

        records = [record async for record in result]

        return [
            {
                "source_path": record["path"],
                "score": 0.8,  # Fixed score for KG matches
                "content": f"{record['type']}: {record['name']}",
                "metadata": {"entity_type": record["type"]},
            }
            for record in records
        ]

def deduplicate_and_rank(results: list, max_results: int) -> list:
    """Deduplicate by source_path and rank by score."""

    seen_paths = {}

    for result in results:
        path = result["source_path"]
        score = result["score"]

        if path not in seen_paths or seen_paths[path]["score"] < score:
            seen_paths[path] = result

    # Sort by score descending
    ranked = sorted(seen_paths.values(), key=lambda x: x["score"], reverse=True)

    return ranked[:max_results]
```

---

## Testing Checklist (Per Poly)

### Unit Tests
- [ ] Event payload models instantiate correctly
- [ ] Event envelope creation works
- [ ] Error codes are valid enums
- [ ] Validators reject invalid data
- [ ] Convenience functions produce correct payloads

### Integration Tests
- [ ] Handler can consume events from Kafka
- [ ] Handler publishes COMPLETED events on success
- [ ] Handler publishes FAILED events on errors
- [ ] Correlation ID is preserved
- [ ] Event envelopes are ONEX-compliant
- [ ] All three test cases pass

### Service Integration Tests (Optional)
- [ ] Can call backend services (metadata, langextract, etc.)
- [ ] Handles service failures gracefully
- [ ] Parallel execution works
- [ ] Retry logic works

---

## Common Pitfalls to Avoid

### 1. **Event Type Mismatches**
❌ Wrong:
```python
event_type = "CODE_ANALYSIS_REQUESTED"  # Generic enum value
```

✅ Correct:
```python
event_type = "omninode.intelligence.event.code_analysis_requested.v1"  # Qualified name
```

### 2. **Payload Structure**
❌ Wrong:
```python
# Returning raw payload without envelope
return payload.model_dump()
```

✅ Correct:
```python
# Use helper to create envelope
return IntelligenceAdapterEventHelpers.create_analysis_completed_event(
    payload=payload,
    correlation_id=correlation_id,
)
```

### 3. **Error Handling**
❌ Wrong:
```python
# Let exceptions bubble up without publishing FAILED event
result = await risky_operation()
```

✅ Correct:
```python
try:
    result = await risky_operation()
except Exception as e:
    await self._publish_failed_response(
        correlation_id=correlation_id,
        error_code=EnumErrorCode.EXTERNAL_SERVICE_ERROR,
        error_message=str(e),
    )
    return False
```

### 4. **Service Timeouts**
❌ Wrong:
```python
# No timeout, service hangs indefinitely
response = await client.post(url, json=data)
```

✅ Correct:
```python
# Always set reasonable timeout
response = await client.post(url, json=data, timeout=5.0)
```

### 5. **Correlation ID Handling**
❌ Wrong:
```python
# Creating new correlation ID for response
correlation_id = uuid4()
```

✅ Correct:
```python
# Extract from request and preserve
correlation_id = self._get_correlation_id(event)
```

---

## Success Criteria (Per Poly)

Before marking implementation complete:

1. **Code Quality**
   - [ ] Type hints on all functions
   - [ ] Docstrings on all classes and methods
   - [ ] No `mypy` errors
   - [ ] Follows existing code style

2. **Testing**
   - [ ] All 3 integration tests pass
   - [ ] Can run tests independently
   - [ ] Tests use real Kafka (no mocks)

3. **Event Compliance**
   - [ ] Events match contract specification
   - [ ] ONEX envelope structure correct
   - [ ] Qualified event type naming
   - [ ] Correlation ID preserved

4. **Service Integration**
   - [ ] All required services called
   - [ ] Error handling for service failures
   - [ ] Timeout handling
   - [ ] Graceful degradation

5. **Documentation**
   - [ ] Handler docstring explains purpose
   - [ ] Event flow documented
   - [ ] Service integration documented

---

## Phase 2 Timeline

**Total Estimate**: 1.5 days with 3 Polys in parallel

### Poly 1: Document Indexing (Most Complex)
- Event models: 30 mins
- Handler: 3 hours (5 service integrations, parallel orchestration)
- Integration tests: 2 hours
- Configuration: 15 mins
- **Total**: ~6 hours

### Poly 2: Repository Crawler (Medium)
- Event models: 30 mins
- Handler: 2 hours (file discovery, batch publishing)
- Integration tests: 1.5 hours
- Configuration: 15 mins
- **Total**: ~4.5 hours

### Poly 3: Search (Medium)
- Event models: 30 mins
- Handler: 2 hours (3 search sources, aggregation)
- Integration tests: 1.5 hours
- Configuration: 15 mins
- **Total**: ~4.5 hours

**Parallel Execution**: All complete in ~6 hours (slowest Poly)

---

## Ready to Spawn Polys! 🚀

**Phase 1 Complete**: ✅
- Event contracts defined
- Service integration documented
- Shared infrastructure ready

**Next Action**: Spawn 3 Polys to implement handlers in parallel

**Phase 3 Preview**: Integration testing, Docker rebuild, end-to-end validation
