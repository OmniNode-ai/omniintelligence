# Archon Search Service

**Version**: 1.0.0
**Status**: Production
**Port**: 8055
**Architecture**: Hybrid Search Orchestration

Enhanced search service for Archon. Combines vector similarity search (Qdrant), graph traversal (Memgraph), and relational queries (Supabase) to provide intelligent and comprehensive search capabilities with distributed caching.

## Overview

The Search Service provides unified access to Archon's multi-modal search capabilities:
- **Vector Search**: Semantic similarity via Qdrant embeddings (Ollama/OpenAI)
- **Graph Traversal**: Entity relationships and knowledge graph navigation (Memgraph)
- **Relational Search**: Document metadata and structured queries (Supabase)
- **Hybrid Orchestration**: Combined results from all sources with intelligent ranking
- **Performance Optimization**: Distributed caching (Valkey/Redis), connection pooling, retry logic

### Key Features

- ✅ **Hybrid Search**: Combines vector + graph + relational search
- ✅ **Semantic Similarity**: Embedding-based document search
- ✅ **Relationship Discovery**: Graph-based entity relationship queries
- ✅ **Path Finding**: Shortest path between entities in knowledge graph
- ✅ **Distributed Caching**: Valkey (Redis fork) with 512MB LRU eviction
- ✅ **Real-time Indexing**: Document vectorization and indexing on-the-fly
- ✅ **Cache Management**: Invalidation, optimization, and metrics APIs

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           SEARCH SERVICE (8055)                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │   HybridSearchOrchestrator                   │  │
│  │  - ResearchOrchestrator (RAG + Vector + KG)  │  │
│  │  - VectorSearchEngine (Qdrant)               │  │
│  │  - GraphSearchEngine (Memgraph)              │  │
│  │  - RelationalSearchEngine (Supabase)         │  │
│  └──────────────────────────────────────────────┘  │
│                      ↓                              │
│  ┌──────────────────────────────────────────────┐  │
│  │   SearchCache (Valkey/Redis)                 │  │
│  │  - 512MB LRU cache, 5min TTL                 │  │
│  │  - Cache hit rate >60%                       │  │
│  │  - Per-service result caching                │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
           ↓           ↓           ↓
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Qdrant   │  │ Memgraph │  │ Supabase │
   │ (6333)   │  │ (7687)   │  │ (5432)   │
   └──────────┘  └──────────┘  └──────────┘
```

## API Endpoints

### Search Operations

**`POST /search`**
- **Description**: Unified hybrid search across all sources
- **Request**: `SearchRequest`
  - `query`: Search query text
  - `mode`: `hybrid`, `vector`, `graph`, `relational`
  - `filters`: Entity type, date range, quality score
  - `limit`: Max results (default: 10)
  - `quality_weight`: Quality score influence (0.0-1.0)
- **Response**: `SearchResponse`
  - `results`: Ranked search results with scores
  - `metadata`: Search mode, sources used, cache hit
  - `analytics`: Performance metrics, result counts
- **Performance**: <1200ms (cold), <100ms (warm cache)

**`GET /search`**
- **Description**: Simple search via query parameters
- **Query Params**: `q`, `mode`, `entity_type`, `limit`
- **Response**: `SearchResponse`

**`POST /search/relationships`**
- **Description**: Find entity relationships in knowledge graph
- **Request**: `RelationshipSearchRequest`
  - `entity_id`: Source entity
  - `relationship_types`: Filter by relationship types
  - `depth`: Traversal depth (1-3)
- **Response**: `RelationshipSearchResponse`

**`GET /search/similar/{entity_id}`**
- **Description**: Find similar entities via vector similarity
- **Path Params**: `entity_id`
- **Query Params**: `limit`, `min_similarity`
- **Response**: Similar entities ranked by cosine similarity

**`GET /search/related/{entity_id}`**
- **Description**: Find related entities via graph traversal
- **Path Params**: `entity_id`
- **Query Params**: `relationship_type`, `depth`
- **Response**: Related entities with relationship paths

**`GET /search/path/{source_id}/{target_id}`**
- **Description**: Find shortest path between two entities
- **Path Params**: `source_id`, `target_id`
- **Query Params**: `max_depth`
- **Response**: Shortest path with nodes and relationships

### Indexing & Vectorization

**`POST /vectorize/document`**
- **Description**: Vectorize and index document in Qdrant
- **Request**: Document content and metadata
- **Response**: Vector ID and indexing confirmation
- **Collection Selection**: Automatic based on document type
  - `quality_vectors`: Quality/diagnostic documents
  - `archon_vectors`: General documents

**`POST /search/index/refresh`**
- **Description**: Refresh search indexes (full rebuild)
- **Response**: Index refresh status and counts
- **Use Case**: Post-migration, data corruption recovery

### Analytics & Monitoring

**`GET /search/analytics`**
- **Description**: Search analytics and usage statistics
- **Response**: `SearchAnalytics`
  - Total searches, average response time
  - Search mode distribution
  - Cache hit rate, error rate

**`GET /search/stats`**
- **Description**: Search service statistics
- **Response**: Collection counts, index sizes, health status

**`GET /health`**
- **Description**: Service health check
- **Response**: `HealthStatus`
  - Service status, dependencies connected
  - Qdrant, Memgraph, Supabase connectivity
  - Cache status and metrics

### Cache Management

**`GET /cache/stats`**
- **Description**: Cache statistics and performance metrics
- **Response**:
  - `hit_rate`: Cache hit percentage
  - `hits`, `misses`: Cache access counts
  - `memory_usage`: Current memory consumption
  - `eviction_count`: LRU evictions
  - `operations_per_sec`: Cache throughput

**`POST /cache/invalidate`**
- **Description**: Invalidate cache entries
- **Request**:
  - `pattern`: Cache key pattern (e.g., `research:rag:*`)
  - `key`: Specific cache key (optional)
- **Response**: Keys invalidated count

**`POST /cache/optimize`**
- **Description**: Optimize cache performance
- **Response**: Optimization results and recommendations

## Configuration

### Environment Variables

**Required**:
- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_KEY`: Supabase service role key
- `MEMGRAPH_URI`: Memgraph connection URI (default: `bolt://memgraph:7687`)
- `OLLAMA_BASE_URL`: Ollama endpoint for embeddings (default: `http://192.168.86.200:11434`)

**Optional**:
- `REDIS_URL`: Redis/Valkey URL for distributed caching (default: `redis://archon-valkey:6379/0`)
- `ENABLE_CACHE`: Enable distributed caching (default: `true`)
- `QDRANT_URL`: Qdrant URL (default: `http://qdrant:6333`)
- `OPENAI_API_KEY`: OpenAI API key (alternative to Ollama)
- `BRIDGE_SERVICE_URL`: Bridge service URL (default: `http://archon-bridge:8054`)
- `INTELLIGENCE_SERVICE_URL`: Intelligence service URL (default: `http://archon-intelligence:8053`)

### Docker Compose

```yaml
archon-search:
  build:
    context: ./services/search
    dockerfile: Dockerfile
  ports:
    - "8055:8055"
  environment:
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
    - MEMGRAPH_URI=bolt://memgraph:7687
    - OLLAMA_BASE_URL=http://192.168.86.200:11434
    - REDIS_URL=redis://archon-valkey:6379/0
    - ENABLE_CACHE=true
  depends_on:
    - qdrant
    - memgraph
    - archon-valkey
    - archon-bridge
    - archon-intelligence
```

## Usage Examples

### Python Client

```python
import httpx

search_url = "http://localhost:8055"

# Hybrid search (vector + graph + relational)
response = httpx.post(
    f"{search_url}/search",
    json={
        "query": "ONEX architecture patterns",
        "mode": "hybrid",
        "limit": 10,
        "filters": {"entity_type": "document"},
        "quality_weight": 0.3
    }
)
results = response.json()
print(f"Found {len(results['results'])} results")
print(f"Cache hit: {results['metadata']['cache_hit']}")

# Find similar documents
response = httpx.get(
    f"{search_url}/search/similar/doc-123",
    params={"limit": 5, "min_similarity": 0.7}
)
similar = response.json()

# Relationship search
response = httpx.post(
    f"{search_url}/search/relationships",
    json={
        "entity_id": "entity-456",
        "relationship_types": ["implements", "references"],
        "depth": 2
    }
)
relationships = response.json()

# Cache management
stats = httpx.get(f"{search_url}/cache/stats").json()
print(f"Cache hit rate: {stats['hit_rate']:.1%}")

# Invalidate stale cache
httpx.post(
    f"{search_url}/cache/invalidate",
    json={"pattern": "research:rag:*"}
)
```

### cURL

```bash
# Hybrid search
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "performance optimization",
    "mode": "hybrid",
    "limit": 10
  }'

# Health check
curl http://localhost:8055/health

# Cache statistics
curl http://localhost:8055/cache/stats

# Invalidate cache pattern
curl -X POST http://localhost:8055/cache/invalidate \
  -H "Content-Type: application/json" \
  -d '{"pattern": "research:vector:*"}'
```

## Development

### Running Locally

```bash
# Install dependencies
poetry install

# Set environment variables
export SUPABASE_URL="your-supabase-url"
export SUPABASE_SERVICE_KEY="your-service-key"
export MEMGRAPH_URI="bolt://localhost:7687"
export REDIS_URL="redis://localhost:6379/0"
export ENABLE_CACHE=true

# Run service
poetry run python app.py
```

### Testing

```bash
# Run all tests
poetry run pytest tests/ -v

# Performance benchmarks
poetry run pytest tests/test_search_performance.py -v -s

# Cache performance tests
poetry run pytest tests/test_cache.py -v
```

## Performance Optimization (Phase 1)

### Distributed Caching

**Valkey (Redis fork)**:
- **Cache Size**: 512MB LRU eviction
- **TTL**: 5 minutes (300s) for search results
- **Hit Rate Target**: >60%
- **Performance**: Warm cache hits <100ms (95%+ improvement)

**Cache Patterns**:
- `research:rag:*`: RAG search results
- `research:vector:*`: Vector search results
- `research:knowledge:*`: Knowledge graph results

**Configuration**:
```bash
# Enable caching (default)
ENABLE_CACHE=true

# Disable for debugging
ENABLE_CACHE=false
```

### HTTP/2 Connection Pooling

- **Max Connections**: 100 total, 20 keepalive
- **Keepalive**: 30s expiry
- **Timeout**: 5s connect, 10s read, 5s write
- **Impact**: 30-50% latency reduction for service calls

### Retry Logic

- **Attempts**: 3 retries max
- **Backoff**: Exponential (1s → 2s → 4s)
- **Scope**: All backend service calls (RAG, Qdrant, Memgraph)

### Performance Targets

| Metric | Cold Cache | Warm Cache | Target |
|--------|-----------|------------|--------|
| Hybrid Search | ~7-9s | <100ms | <1200ms |
| Vector Search | ~250ms | <50ms | <100ms |
| Graph Traversal | ~450ms | <80ms | <200ms |
| Cache Hit Rate | N/A | >60% | >60% |

## Search Modes

### Hybrid Mode (Default)
Combines all search engines with intelligent result ranking:
1. **Vector Search**: Semantic similarity (Qdrant)
2. **Graph Traversal**: Entity relationships (Memgraph)
3. **Relational Search**: Metadata filtering (Supabase)
4. **Result Fusion**: Ranked by relevance + quality + recency

### Vector Mode
Pure semantic similarity search:
- Embedding-based (Ollama or OpenAI)
- Cosine similarity ranking
- Fast for large document collections

### Graph Mode
Knowledge graph traversal only:
- Relationship-based discovery
- Entity path finding
- Useful for exploring connections

### Relational Mode
Structured queries on document metadata:
- Filter by type, quality, date range
- SQL-based precision
- Fast for known criteria

## Logging

The Search service uses comprehensive structured logging:

```python
from search_logging.search_logger import SearchLogger

# Initialize logger
search_logger = SearchLogger("search_orchestrator")

# Log search operations
search_logger.log_search_request(query, mode, filters)
search_logger.log_search_results(results_count, duration_ms)
search_logger.log_cache_hit(cache_key, hit_type)

# Error tracking
search_logger.log_error("search_failed", error_details)
```

## Integration with Other Services

### Intelligence Service
- **RAG Queries**: Orchestrated multi-service research
- **Quality Weighting**: Quality scores influence search ranking
- **Entity Extraction**: Document entities indexed for graph search

### Bridge Service
- **Entity Sync**: Real-time entity updates trigger index refresh
- **Graph Updates**: Knowledge graph changes propagated to search

### MCP Server
- **Unified Gateway**: Search operations exposed via MCP tools
- **Research Orchestration**: Multi-service RAG queries via `perform_rag_query`

## Monitoring

### Health Checks

```bash
# Service health
curl http://localhost:8055/health

# Dependency status
curl http://localhost:8055/health | jq '.qdrant_connected, .memgraph_connected'

# Search statistics
curl http://localhost:8055/search/stats

# Cache health
curl http://localhost:8055/cache/stats
```

### Performance Metrics

```bash
# Search analytics
curl http://localhost:8055/search/analytics

# Cache performance
curl http://localhost:8055/cache/stats | jq '.hit_rate, .operations_per_sec'
```

## Troubleshooting

### Common Issues

**1. Low Cache Hit Rate**
```bash
# Check cache stats
curl http://localhost:8055/cache/stats

# Solutions:
# - Increase cache size (REDIS_MAXMEMORY)
# - Increase TTL (modify cache configuration)
# - Warm up cache with common queries
```

**2. Slow Search Queries**
```bash
# Check which source is slow
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "mode": "hybrid"}' \
  | jq '.analytics'

# Solutions:
# - Enable caching (ENABLE_CACHE=true)
# - Reduce search depth for graph queries
# - Use vector mode for large result sets
```

**3. Qdrant Connection Failed**
```bash
# Check Qdrant health
curl http://localhost:6333/health

# Check Qdrant collections
curl http://localhost:6333/collections

# Restart Qdrant
docker restart qdrant
```

**4. Memgraph Connection Failed**
```bash
# Check Memgraph status
docker ps | grep memgraph

# Test Memgraph connection
docker exec memgraph mgconsole --host memgraph --port 7687

# Restart Memgraph
docker restart memgraph
```

## Architecture Details

### Components

**`HybridSearchOrchestrator`**
- Coordinates all search engines
- Result fusion and ranking
- Cache management and optimization

**`ResearchOrchestrator`**
- Multi-service RAG queries
- Parallel execution (RAG + Qdrant + Memgraph)
- Intelligent synthesis and recommendations

**`VectorSearchEngine`**
- Qdrant client wrapper
- Embedding generation (Ollama/OpenAI)
- Similarity search and ranking

**`GraphSearchEngine`**
- Memgraph Bolt client
- Cypher query execution
- Relationship traversal and path finding

**`RelationalSearchEngine`**
- Supabase PostgreSQL client
- SQL query generation
- Metadata filtering and pagination

**`SearchCache`**
- Valkey/Redis client
- LRU eviction policy (512MB)
- TTL-based expiration (5min)
- Cache key patterns and invalidation

### Data Models

**`SearchRequest`**: Search query and filters
**`SearchResponse`**: Unified search results with analytics
**`SearchMode`**: Enum (hybrid, vector, graph, relational)
**`EntityType`**: Enum (document, code_entity, pattern, etc.)
**`RelationshipSearchRequest`**: Graph relationship query
**`RelationshipSearchResponse`**: Relationship results
**`SearchAnalytics`**: Search performance and usage metrics
**`HealthStatus`**: Service health and dependency status

## Related Documentation

- **Intelligence Service**: [services/intelligence/README.md](../intelligence/README.md)
- **Bridge Service**: [services/bridge/README.md](../bridge/README.md)
- **Database Schema**: [services/intelligence/database/schema/README.md](../intelligence/database/schema/README.md)
- **HTTP Connection Pooling**: [services/intelligence/docs/HTTP_CONNECTION_POOLING.md](../intelligence/docs/HTTP_CONNECTION_POOLING.md)
- **Kafka Configuration**: [services/intelligence/docs/KAFKA_CONFIGURATION.md](../intelligence/docs/KAFKA_CONFIGURATION.md)

---

**Search Service**: Production-ready hybrid search with distributed caching and multi-source intelligence.
