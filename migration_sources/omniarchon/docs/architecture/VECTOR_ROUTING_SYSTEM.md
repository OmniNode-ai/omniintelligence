# Vector Routing System Documentation

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Routing Strategies](#routing-strategies)
4. [Configuration Management](#configuration-management)
5. [Performance Optimization](#performance-optimization)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance and Scaling](#maintenance-and-scaling)
8. [API Reference](#api-reference)

---

## Architecture Overview

The Archon Vector Routing System is a sophisticated multi-engine search architecture that intelligently routes queries across different search backends to provide optimal results. It combines vector similarity search, graph traversal, and traditional relational queries through a unified hybrid orchestrator.

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Vector Routing System                        │
├─────────────────┬─────────────────┬─────────────────────────────────┤
│  Query Router   │  Search Engines │        Storage Layer           │
├─────────────────┼─────────────────┼─────────────────────────────────┤
│ • Mode Detection│ • Vector Search │ • Qdrant Vector DB             │
│ • Load Balancing│ • Graph Search  │ • Memgraph Knowledge Graph     │
│ • Query Analysis│ • Relational    │ • Supabase PostgreSQL          │
│ • Result Fusion │ • Hybrid Engine │ • Collection Routing           │
├─────────────────┼─────────────────┼─────────────────────────────────┤
│  Intelligence   │  Optimization   │     Service Discovery          │
├─────────────────┼─────────────────┼─────────────────────────────────┤
│ • Quality Score │ • Caching       │ • Docker Service Mesh          │
│ • ONEX Scoring  │ • Performance   │ • Health Monitoring             │
│ • Embedding     │ • Auto-scaling  │ • Circuit Breakers              │
│ • Classification│ • Index Refresh │ • Load Balancing                │
└─────────────────┴─────────────────┴─────────────────────────────────┘
```

### Key Features

- **Sub-100ms Response Times**: Optimized for high-performance vector operations
- **Multi-Modal Search**: Semantic, structural, hybrid, and relational search modes
- **Quality-Weighted Routing**: Documents routed based on quality scores and ONEX compliance
- **Intelligent Load Balancing**: Automatic routing based on query type and system load
- **Collection-Based Routing**: Documents automatically routed to appropriate Qdrant collections
- **Graceful Degradation**: Continues operation even when individual components fail
- **Real-time Indexing**: Immediate availability of newly indexed content

---

## Core Components

### 1. Hybrid Search Orchestrator

**Location**: `/services/search/orchestration/hybrid_search.py`

The central routing component that coordinates all search operations.

#### Responsibilities:
- Query analysis and routing strategy selection
- Parallel execution of multiple search engines
- Result ranking and deduplication
- Performance monitoring and optimization

#### Key Methods:
```python
async def search(request: SearchRequest) -> SearchResponse
async def _hybrid_search(request: SearchRequest) -> Tuple[List[SearchResult], float, float, float]
async def _semantic_only_search(request: SearchRequest) -> List[SearchResult]
async def _structural_only_search(request: SearchRequest) -> List[SearchResult]
async def _relational_only_search(request: SearchRequest) -> List[SearchResult]
```

### 2. Vector Search Engine

**Location**: `/services/search/engines/vector_search.py`

Handles semantic similarity search using Ollama embeddings and Qdrant vector database.

#### Key Features:
- **Embedding Generation**: Uses `rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest` model
- **Vector Dimensions**: 1536-dimensional embeddings
- **Batch Processing**: Efficient batch embedding generation with throttling
- **Quality Scoring**: Integration with ONEX compliance scoring

#### Configuration:
```python
VectorSearchEngine(
    ollama_base_url="http://192.168.86.200:11434",
    embedding_model="rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest",
    embedding_dim=1536,
    qdrant_url="http://qdrant:6333",
    use_qdrant=True
)
```

### 3. Qdrant Adapter

**Location**: `/services/search/engines/qdrant_adapter.py`

High-performance vector database adapter for Qdrant operations.

#### Performance Optimizations:
- **HNSW Index Configuration**:
  - M=16 connections
  - ef_construct=200 for construction
  - ef=128 for search
- **Collection Segmentation**: Optimized for parallel processing
- **Batch Indexing**: Up to 50 entities per batch
- **Memory Management**: Configurable memory mapping thresholds

#### Collections Structure:
```python
collections = {
    "archon_vectors": "Main document embeddings with metadata",
    "quality_vectors": "Quality-weighted vectors with ONEX compliance scores"
}
```

### 4. Document Collection Router

**Location**: `/services/search/app.py` (new function)

Routes documents to appropriate Qdrant collections based on document type.

#### Routing Logic:
```python
def determine_collection_for_document(metadata: Dict[str, Any]) -> str:
    document_type = metadata.get("document_type", "").lower()

    quality_document_types = {
        "technical_diagnosis", "quality_assessment", "code_review",
        "execution_report", "quality_report", "compliance_check",
        "performance_analysis"
    }

    if document_type in quality_document_types:
        return "quality_vectors"
    return "archon_vectors"
```

### 5. Graph Search Engine

**Location**: `/services/search/engines/graph_search.py`

Provides structural search through Memgraph knowledge graph traversal.

#### Capabilities:
- Entity relationship discovery
- Shortest path finding
- Multi-hop relationship traversal
- Relationship type filtering

---

## Routing Strategies

### 1. Search Mode Routing

The system supports four primary search modes, each with specific routing logic:

#### Semantic Mode
- **Route**: Vector Search Engine only
- **Use Case**: When semantic similarity is most important
- **Performance**: ~50-100ms
- **Best For**: Natural language queries, concept matching

#### Structural Mode
- **Route**: Graph Search Engine only
- **Use Case**: When entity relationships are critical
- **Performance**: ~100-200ms
- **Best For**: Entity discovery, relationship mapping

#### Relational Mode
- **Route**: Supabase PostgreSQL only
- **Use Case**: When exact matches and metadata filtering needed
- **Performance**: ~20-50ms
- **Best For**: Exact text matching, metadata queries

#### Hybrid Mode (Default)
- **Route**: All engines in parallel
- **Use Case**: Comprehensive search with best overall results
- **Performance**: ~150-300ms
- **Best For**: Most search scenarios requiring comprehensive results

### 2. Collection Routing Strategy

Documents are automatically routed to different Qdrant collections based on their type and quality characteristics:

#### Main Collection (`archon_vectors`)
- **Purpose**: General document storage
- **Document Types**: Standard documents, pages, code examples
- **Optimization**: Balanced for general search performance

#### Quality Collection (`quality_vectors`)
- **Purpose**: Quality-assessed documents with ONEX compliance scores
- **Document Types**: Technical diagnoses, quality reports, code reviews
- **Optimization**: Enhanced with quality-weighted scoring

### 3. Load Balancing Strategy

#### Connection Pool Management
```python
# Qdrant client configuration
QdrantClient(
    url=qdrant_url,
    timeout=30.0,
    prefer_grpc=False  # HTTP for better load balancing
)
```

#### Health Check Routing
```python
async def health_check() -> Dict[str, bool]:
    health_status = {
        "ollama_connected": False,
        "qdrant_connected": False,
        "memgraph_connected": False,
        "supabase_connected": False
    }
    # Route traffic only to healthy services
```

---

## Configuration Management

### 1. Environment Variables

#### Core Configuration
```bash
# Search Service Configuration
SEARCH_SERVICE_PORT=8055
OLLAMA_BASE_URL=http://192.168.86.200:11434
MEMGRAPH_URI=bolt://memgraph:7687
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key

# Qdrant Configuration
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_URL=http://qdrant:6333
VECTOR_DIMENSIONS=1536
QDRANT_COLLECTION_NAME=archon_vectors
QDRANT_QUALITY_COLLECTION=quality_vectors

# Performance Tuning
AUTO_REFRESH_ENABLED=true
MAX_CONCURRENT_EXTRACTIONS=5
EXTRACTION_TIMEOUT_SECONDS=300
```

#### Qdrant Performance Configuration
```bash
# Service Configuration
QDRANT__SERVICE__HTTP_PORT=6333
QDRANT__SERVICE__GRPC_PORT=6334
QDRANT__SERVICE__MAX_REQUEST_SIZE_MB=32

# Performance Optimization
QDRANT__SERVICE__MAX_WORKERS=0  # Auto-detect CPU cores
QDRANT__STORAGE__WAL__WAL_CAPACITY_MB=32
QDRANT__STORAGE__OPTIMIZERS__DEFAULT_SEGMENT_NUMBER=0

# Memory Management
QDRANT__STORAGE__OPTIMIZERS__MEMMAP_THRESHOLD_KB=200000
QDRANT__STORAGE__OPTIMIZERS__INDEXING_THRESHOLD_KB=20000
```

### 2. Docker Compose Configuration

#### Service Dependencies
```yaml
archon-search:
  depends_on:
    qdrant:
      condition: service_healthy
    memgraph:
      condition: service_healthy
    archon-intelligence:
      condition: service_healthy
    archon-bridge:
      condition: service_healthy
```

#### Resource Limits
```yaml
qdrant:
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 512M
```

### 3. Search Request Configuration

#### Default Search Parameters
```python
SearchRequest(
    query="your query",
    mode=SearchMode.HYBRID,
    semantic_threshold=0.15,
    max_semantic_results=50,
    max_graph_depth=3,
    limit=20,
    include_content=True
)
```

#### Quality-Weighted Search
```python
quality_weighted_search(
    query_vector,
    request,
    quality_weight=0.3  # 30% quality, 70% semantic
)
```

---

## Performance Optimization

### 1. Vector Index Optimization

#### HNSW Parameters
```python
hnsw_config=models.HnswConfigDiff(
    m=16,                    # Number of connections (16 = good balance)
    ef_construct=200,        # Search width during construction
    full_scan_threshold=10000,  # Use brute force for small datasets
    max_indexing_threads=0   # Use all available cores
)
```

#### Batch Processing
```python
async def batch_index_entities(
    entities: List[Tuple[str, str, Dict[str, Any]]],
    batch_size: int = 50,  # Optimized batch size
    quality_scorer=None
) -> int:
```

### 2. Search Performance

#### Target Performance Metrics
- **Semantic Search**: <100ms for 10K+ vectors
- **Graph Search**: <200ms for 3-hop traversal
- **Hybrid Search**: <300ms for combined results
- **Index Refresh**: <500ms for new documents

#### Performance Monitoring
```python
@app.get("/search/stats")
async def get_search_stats():
    return {
        "vector_index": vector_stats,
        "search_capabilities": capabilities,
        "performance_metrics": {
            "average_search_time_ms": avg_time,
            "cache_hit_rate": hit_rate
        }
    }
```

### 3. Caching Strategy

#### Vector Cache
```python
def get_cache_stats(self) -> Dict[str, Any]:
    return {
        "in_memory_entities": len(self._vector_cache),
        "memory_usage_mb": memory_usage,
        "cache_hit_rate": hit_rate
    }
```

#### Auto-Refresh Strategy
```python
async def _auto_refresh_vector_index():
    if auto_refresh_enabled:
        await vector_engine.refresh_cache()
        await qdrant_adapter.optimize_collection()
```

---

## Troubleshooting

### 1. Common Issues and Solutions

#### Vector Search Issues

**Problem**: Slow semantic search performance (>500ms)
```bash
# Diagnosis
curl http://localhost:8055/search/stats
```
**Solutions**:
1. Check Qdrant collection optimization
2. Verify HNSW parameters
3. Monitor memory usage
4. Check Ollama embedding service health

**Problem**: Embedding generation failures
```bash
# Check Ollama service
curl http://192.168.86.200:11434/api/tags
```
**Solutions**:
1. Verify Ollama model availability
2. Check network connectivity
3. Increase timeout settings
4. Monitor resource usage

#### Collection Routing Issues

**Problem**: Documents going to wrong collection
```python
# Debug collection routing
def determine_collection_for_document(metadata):
    document_type = metadata.get("document_type", "").lower()
    print(f"Document type: {document_type}")
    # Add debugging logic
```

**Problem**: Collection not found errors
```bash
# Check Qdrant collections
curl http://localhost:6333/collections
```

### 2. Health Check Procedures

#### Service Health Verification
```bash
# Search service health
curl http://localhost:8055/health

# Qdrant health
curl http://localhost:6333/readyz

# Memgraph health
curl http://localhost:7444/

# Ollama health
curl http://192.168.86.200:11434/api/tags
```

#### Performance Health Checks
```bash
# Check search performance
curl "http://localhost:8055/search?q=test&limit=5"

# Check vector index stats
curl http://localhost:8055/search/stats

# Monitor collection statistics
curl http://localhost:6333/collections/archon_vectors
```

### 3. Debugging Tools

#### Log Analysis
```bash
# Search service logs
docker logs archon-search --follow

# Qdrant logs
docker logs archon-qdrant --follow

# Filter for performance issues
docker logs archon-search 2>&1 | grep -E "(slow|timeout|error)"
```

#### Performance Profiling
```python
import time

async def profile_search(query: str):
    start_time = time.time()

    # Semantic search timing
    semantic_start = time.time()
    semantic_results = await vector_engine.semantic_search(query, request)
    semantic_time = (time.time() - semantic_start) * 1000

    # Graph search timing
    graph_start = time.time()
    graph_results = await graph_engine.structural_search(query, request)
    graph_time = (time.time() - graph_start) * 1000

    total_time = (time.time() - start_time) * 1000

    print(f"Semantic: {semantic_time:.2f}ms, Graph: {graph_time:.2f}ms, Total: {total_time:.2f}ms")
```

---

## Maintenance and Scaling

### 1. Index Maintenance

#### Regular Optimization
```python
# Schedule regular optimization
async def optimize_collections():
    await qdrant_adapter.optimize_collection("archon_vectors")
    await qdrant_adapter.optimize_collection("quality_vectors")

# Run weekly via cron job
0 2 * * 0 /app/scripts/optimize_indexes.py
```

#### Collection Statistics Monitoring
```python
async def monitor_collection_health():
    for collection in ["archon_vectors", "quality_vectors"]:
        stats = await qdrant_adapter.get_collection_stats(collection)

        # Alert if index is fragmented
        if stats["segments_count"] > 10:
            alert_high_fragmentation(collection)

        # Alert if disk usage is high
        if stats["disk_data_size"] > MAX_DISK_SIZE:
            alert_disk_usage(collection)
```

### 2. Scaling Strategies

#### Horizontal Scaling

**Qdrant Clustering**:
```yaml
# Multi-node Qdrant configuration
qdrant-node-1:
  image: qdrant/qdrant:v1.7.4
  environment:
    - QDRANT__CLUSTER__ENABLED=true
    - QDRANT__CLUSTER__NODE_ID=1

qdrant-node-2:
  image: qdrant/qdrant:v1.7.4
  environment:
    - QDRANT__CLUSTER__ENABLED=true
    - QDRANT__CLUSTER__NODE_ID=2
```

**Search Service Scaling**:
```yaml
archon-search:
  deploy:
    replicas: 3
    resources:
      limits:
        memory: 1G
      reservations:
        memory: 512M
```

#### Vertical Scaling

**Resource Allocation**:
```yaml
# Production resource limits
qdrant:
  deploy:
    resources:
      limits:
        memory: 8G
        cpus: '4.0'
      reservations:
        memory: 2G
        cpus: '1.0'

archon-search:
  deploy:
    resources:
      limits:
        memory: 4G
        cpus: '2.0'
```

### 3. Backup and Recovery

#### Vector Data Backup
```bash
# Create Qdrant snapshot
curl -X POST http://localhost:6333/collections/archon_vectors/snapshots

# Download snapshot
curl http://localhost:6333/collections/archon_vectors/snapshots/snapshot_name

# Restore from snapshot
curl -X PUT http://localhost:6333/collections/archon_vectors/snapshots/upload \
  -H "Content-Type: application/octet-stream" \
  --data-binary @snapshot_name
```

#### Configuration Backup
```bash
# Backup environment configuration
cp .env .env.backup.$(date +%Y%m%d)

# Backup docker-compose configuration
cp docker-compose.yml docker-compose.backup.$(date +%Y%m%d).yml

# Version control critical configurations
git add docs/VECTOR_ROUTING_SYSTEM.md .env.example docker-compose.yml
git commit -m "Backup vector routing configuration"
```

### 4. Monitoring and Alerting

#### Key Metrics to Monitor
```python
monitoring_metrics = {
    "search_latency": "P95 < 500ms",
    "indexing_throughput": "> 100 docs/minute",
    "error_rate": "< 1%",
    "memory_usage": "< 80%",
    "disk_usage": "< 85%",
    "cache_hit_rate": "> 90%"
}
```

#### Alert Thresholds
```yaml
alerts:
  - name: high_search_latency
    condition: search_time_ms > 1000
    action: scale_search_service

  - name: qdrant_memory_high
    condition: memory_usage > 90%
    action: restart_qdrant_service

  - name: embedding_service_down
    condition: ollama_connected == false
    action: restart_ollama_service
```

---

## API Reference

### 1. Search Endpoints

#### POST /search
Perform enhanced search with multiple modes.

**Request**:
```json
{
  "query": "authentication patterns",
  "mode": "hybrid",
  "entity_types": ["page", "code_example"],
  "semantic_threshold": 0.15,
  "limit": 20,
  "include_content": true
}
```

**Response**:
```json
{
  "query": "authentication patterns",
  "mode": "hybrid",
  "total_results": 45,
  "returned_results": 20,
  "search_time_ms": 234.5,
  "semantic_search_time_ms": 89.2,
  "graph_search_time_ms": 145.3,
  "results": [...],
  "entity_type_counts": {"page": 12, "code_example": 8},
  "has_more": true
}
```

#### GET /search/similar/{entity_id}
Find entities similar to a reference entity.

**Parameters**:
- `entity_id`: Reference entity ID
- `limit`: Maximum results (default: 10)
- `threshold`: Similarity threshold (default: 0.7)

#### POST /vectorize/document
Index a document for real-time search availability.

**Request**:
```json
{
  "document_id": "doc_123",
  "project_id": "proj_456",
  "content": "Document content...",
  "metadata": {
    "title": "Document Title",
    "document_type": "technical_diagnosis",
    "source_path": "/path/to/doc"
  }
}
```

### 2. Administrative Endpoints

#### GET /health
Service health check with component status.

#### GET /search/stats
Current search service statistics and performance metrics.

#### POST /search/index/refresh
Refresh vector search index with latest data.

---

## Best Practices

### 1. Query Optimization
- Use specific entity type filters when possible
- Set appropriate similarity thresholds (0.1-0.3 for broad search, 0.7+ for exact matches)
- Limit result sets to reasonable sizes (20-50 results)
- Use hybrid mode for comprehensive searches, specific modes for targeted searches

### 2. Index Management
- Index documents in batches of 50-100 for optimal performance
- Use quality scoring for important documents
- Route documents to appropriate collections based on type
- Schedule regular index optimization during low-usage periods

### 3. Performance Monitoring
- Monitor search latency and set alerts for >500ms responses
- Track memory usage and optimize when >80% utilized
- Monitor embedding generation performance
- Set up health checks for all dependent services

### 4. Scaling Considerations
- Plan for 10x growth in vector storage capacity
- Use collection sharding for large datasets (>1M vectors)
- Implement read replicas for high-query workloads
- Consider geographic distribution for global deployments

---

*This documentation covers the complete vector routing system architecture, configuration, and operational procedures for the Archon AI Agent Orchestration Platform.*
