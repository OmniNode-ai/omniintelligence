# Omniarchon Migration Inventory

**Document Version**: 1.0  
**Project**: Omniintelligence / ONEX Migration  
**Source**: `/home/user/omniintelligence/migration_sources/omniarchon/`  
**Analysis Date**: 2025-11-14  

---

## Executive Summary

Omniarchon is a comprehensive intelligence platform that provides code quality analysis, pattern learning, RAG capabilities, and ONEX compliance validation via an event-driven microservices architecture. The system comprises 9 local services, 4 remote services (on 192.168.86.200), with 78+ intelligence APIs, 4 pattern learning phases, and sophisticated event-driven processing.

**Key Statistics**:
- **Services**: 9 local Docker services + 4 remote services (13 total)
- **APIs**: 78+ endpoints across intelligence, search, bridge, and langextract services
- **Event Handlers**: 20+ Kafka consumer handlers
- **Pattern Learning Phases**: 4 phases (Foundation, Matching, Validation, Traceability)
- **Event Topics**: 8+ Kafka topics for event distribution
- **Databases**: Qdrant (vectors), Memgraph (knowledge graph), PostgreSQL (patterns), Valkey (cache)

---

## Table of Contents

1. [Service Architecture](#service-architecture)
2. [Main Entry Points](#main-entry-points)
3. [Service Responsibilities](#service-responsibilities)
4. [Event Handlers & Kafka Consumers](#event-handlers--kafka-consumers)
5. [API Endpoints & Contracts](#api-endpoints--contracts)
6. [Database Interaction Patterns](#database-interaction-patterns)
7. [Shared Models & Utilities](#shared-models--utilities)
8. [Migration Considerations](#migration-considerations)

---

## Service Architecture

### Network Topology

```
LOCAL SERVICES (Docker Network):
- archon-intelligence    :8053  (Core intelligence, 78 APIs)
- archon-search         :8055  (RAG + vector search)
- archon-bridge         :8054  (Event translation + Kafka)
- archon-langextract    :8156  (ML extraction)
- archon-agents         :8052  (AI orchestration)
- archon-frontend       :3737  (React UI)
- archon-valkey         :6379  (Distributed cache, 512MB LRU)
- qdrant                :6333  (Vector database)
- memgraph              :7687  (Knowledge graph)

REMOTE SERVICES (192.168.86.200):
- omninode-bridge-redpanda           :9092/:29092  (Kafka/Redpanda)
- omninode-bridge-postgres           :5432/:5436   (Pattern DB)
- omninode-bridge-onextree           :8058         (Tree indexing)
- omninode-bridge-metadata-stamping  :8057         (ONEX stamping)
```

### Service Dependencies

```
Intelligence Service (8053)
├── Memgraph (7687) - Knowledge graph
├── Qdrant (6333) - Vector DB
├── Valkey (6379) - Cache
└── PostgreSQL (5436/remote) - Pattern traceability

Search Service (8055)
├── Qdrant (6333) - Vector search
├── Memgraph (7687) - Graph search
├── Ollama (11434/remote) - Embeddings
└── Bridge Service (8054) - Metadata

Bridge Service (8054)
├── Memgraph (7687) - Sync target
├── Intelligence (8053) - Enrichment
├── Kafka (9092) - Event bus
└── PostgreSQL (5436/remote) - Logging

LangExtract Service (8156)
├── Memgraph (7687) - Storage
├── Kafka (9092) - Events
└── Code analysis extractors
```

---

## Main Entry Points

### 1. Intelligence Consumer Service
**File**: `/services/intelligence-consumer/src/main.py`  
**Port**: Kafka consumer (no HTTP)  
**Purpose**: Consume enrichment events from Kafka and call intelligence service

**Entry Class**: `IntelligenceConsumerService`

**Responsibilities**:
- Kafka consumer setup with retry logic
- Event routing (enrichment, code-analysis, manifest-intelligence)
- Error handling with DLQ routing
- Health monitoring and graceful shutdown
- Consumer lag tracking

**Key Methods**:
```python
async def start()              # Initialize service
async def stop()               # Graceful shutdown
async def run()                # Main event loop
async def _process_message()   # Route messages to handlers
async def _process_enrichment_event()
async def _process_code_analysis_event()
async def _process_manifest_intelligence_event()
async def _handle_processing_error()  # Retry + DLQ logic
```

**Event Processing Flow**:
```
Kafka Message
    ↓ (validate schema)
    ├→ Enrichment Event → _process_enrichment_event()
    │  ├→ Batch event (files array) → concurrent processing
    │  └→ Individual file → single processing
    ├→ Code Analysis Event → _process_code_analysis_event()
    └→ Manifest Intelligence → _process_manifest_intelligence_event()
```

### 2. Intelligence Service
**File**: `/services/intelligence/app.py`  
**Port**: 8053  
**Purpose**: Core intelligence APIs (78 endpoints)

**Entry Point**: FastAPI application with lifespan management

**Key Features**:
- 78+ REST APIs across 12+ modules
- Entity extraction and semantic analysis
- Pattern learning with 4 phases
- Quality scoring and trend analysis
- Performance optimization recommendations
- Document freshness monitoring
- ONEX compliance validation

### 3. Search Service
**File**: `/services/search/app.py`  
**Port**: 8055  
**Purpose**: Hybrid search combining vectors, graphs, and relations

**Search Modes**:
- SEMANTIC: Vector similarity (Qdrant)
- STRUCTURAL: Graph traversal (Memgraph)
- RELATIONAL: Database queries
- HYBRID: Combination of all

**Key Endpoints**:
- `/search` (POST/GET) - Main search
- `/search/patterns` - Pattern search
- `/search/relationships` - Graph relationships
- `/vectorize/document` - Index documents
- `/search/similar/{entity_id}` - Similarity search

### 4. Bridge Service
**File**: `/services/bridge/app.py`  
**Port**: 8054  
**Purpose**: Event translation, Kafka producer/consumer, metadata stamping

**Key Responsibilities**:
- PostgreSQL ↔ Memgraph synchronization
- Kafka event production/consumption
- Metadata enrichment and stamping
- Entity mapping
- Real-time document sync
- Tree index event handling

### 5. LangExtract Service
**File**: `/services/langextract/app.py`  
**Port**: 8156  
**Purpose**: ML-based code extraction and relationship detection

**Capabilities**:
- Code relationship detection
- Semantic enrichment
- Language-aware extraction
- Structured data extraction
- Integration with intelligence service

---

## Service Responsibilities

### Intelligence Service (8053) - 78 APIs

#### Bridge Intelligence (3 APIs)
```python
POST /api/bridge/generate-intelligence      # Generate OmniNode metadata
GET  /api/bridge/health                     # Service health
GET  /api/bridge/capabilities               # Capabilities list
```

#### Code Intelligence (4 APIs)
```python
POST /extract/code                          # Code entity extraction
POST /assess/code                           # Code quality assessment
POST /process/document                      # Document processing
POST /batch-index                           # Batch indexing
```

#### Pattern Learning (Phase 2) (7 APIs)
```python
POST /api/pattern-learning/pattern/match              # Pattern matching
POST /api/pattern-learning/hybrid/score               # Hybrid scoring
POST /api/pattern-learning/semantic/analyze           # Semantic analysis
GET  /api/pattern-learning/metrics                    # Metrics
GET  /api/pattern-learning/cache/stats                # Cache stats
POST /api/pattern-learning/cache/clear                # Clear cache
GET  /api/pattern-learning/health                     # Health check
```

#### Pattern Traceability (Phase 4) (11 APIs)
```python
POST /api/pattern-traceability/lineage/track          # Track lineage
POST /api/pattern-traceability/lineage/track/batch    # Batch track
GET  /api/pattern-traceability/lineage/{pattern_id}   # Get lineage
GET  /api/pattern-traceability/lineage/{id}/evolution # Evolution
GET  /api/pattern-traceability/executions/logs        # Execution logs
GET  /api/pattern-traceability/executions/summary     # Summary
GET  /api/pattern-traceability/analytics/{pattern_id} # Analytics
POST /api/pattern-traceability/analytics/compute      # Compute analytics
POST /api/pattern-traceability/feedback/analyze       # Analyze feedback
POST /api/pattern-traceability/feedback/apply         # Apply feedback
GET  /api/pattern-traceability/health                 # Health
```

#### Quality Scoring (6 APIs)
```python
POST /assess/code                           # ONEX compliance + quality
POST /assess/document                       # Document quality
POST /patterns/extract                      # Pattern extraction
POST /compliance/check                      # Architectural compliance
POST /quality/evaluate                      # Quality evaluation
POST /quality/bulk-assess                   # Bulk assessment
```

#### Performance Optimization (5 APIs)
```python
POST /performance/baseline                  # Establish baselines
GET  /performance/opportunities/{op_name}   # Optimization opportunities
POST /performance/optimize                  # Apply optimizations
GET  /performance/report                    # Reports
GET  /performance/trends                    # Trend monitoring
```

#### Document Freshness (9 APIs)
```python
POST /freshness/analyze                     # Analyze freshness
GET  /freshness/stale                       # Get stale docs
POST /freshness/refresh                     # Refresh docs
GET  /freshness/stats                       # Statistics
GET  /freshness/document/{path}             # Single doc
POST /freshness/cleanup                     # Cleanup old data
POST /freshness/events/document-update      # Document update events
GET  /freshness/events/stats                # Event stats
GET  /freshness/analyses                    # Analysis history
```

#### Pattern Analytics (5 APIs)
```python
GET  /api/pattern-analytics/health                    # Health
GET  /api/pattern-analytics/success-rates             # Success rates
GET  /api/pattern-analytics/top-patterns              # Top patterns
GET  /api/pattern-analytics/emerging-patterns         # Emerging patterns
GET  /api/pattern-analytics/pattern/{id}/history      # Pattern history
```

#### Custom Quality Rules (8 APIs)
```python
POST /api/custom-rules/evaluate                                 # Evaluate
GET  /api/custom-rules/project/{project_id}/rules               # Get rules
POST /api/custom-rules/project/{project_id}/load-config         # Load config
POST /api/custom-rules/project/{project_id}/rule                # Create rule
PUT  /api/custom-rules/project/{project_id}/rule/{rule_id}/enable
PUT  /api/custom-rules/project/{project_id}/rule/{rule_id}/disable
GET  /api/custom-rules/health                                   # Health
DELETE /api/custom-rules/project/{project_id}/rules             # Delete all
```

#### Quality Trends (7 APIs)
```python
POST /api/quality-trends/snapshot                               # Create snapshot
GET  /api/quality-trends/project/{project_id}/trend             # Trend
GET  /api/quality-trends/project/{id}/file/{path}/trend         # File trend
GET  /api/quality-trends/project/{id}/file/{path}/history       # History
POST /api/quality-trends/detect-regression                      # Regression
GET  /api/quality-trends/stats                                  # Stats
DELETE /api/quality-trends/project/{project_id}/snapshots       # Delete
```

#### Performance Analytics (6 APIs)
```python
GET  /api/performance-analytics/baselines                       # Baselines
GET  /api/performance-analytics/operations/{op}/metrics         # Metrics
GET  /api/performance-analytics/optimization-opportunities      # Opportunities
POST /api/performance-analytics/operations/{op}/anomaly-check   # Anomaly
GET  /api/performance-analytics/trends                          # Trends
GET  /api/performance-analytics/health                          # Health
```

#### Autonomous Learning (7 APIs)
```python
POST /api/autonomous/patterns/ingest                  # Ingest patterns
POST /api/autonomous/patterns/success                 # Record success
POST /api/autonomous/predict/agent                    # Predict agent
POST /api/autonomous/predict/time                     # Predict time
GET  /api/autonomous/calculate/safety                 # Safety score
GET  /api/autonomous/stats                            # Stats
GET  /api/autonomous/health                           # Health
```

#### Entity & Knowledge (6 APIs)
```python
POST /extract/code                          # Code entity extraction
POST /extract/document                      # Document entity extraction
POST /process/document                      # Document processing
GET  /entities/search                       # Entity search
GET  /relationships/{entity_id}             # Entity relationships
POST /batch-index                           # Batch indexing
```

### Search Service (8055) - 15+ Endpoints

**Core Search**:
```python
POST /search                                # Hybrid search
GET  /search                                # Quick search
POST /search/patterns                       # Pattern search
POST /search/relationships                  # Relationship search
GET  /search/similar/{entity_id}            # Similar entities
GET  /search/related/{entity_id}            # Related entities
GET  /search/path/{source_id}/{target_id}   # Shortest path
```

**Vector Management**:
```python
POST /vectorize/document                    # Index document
POST /search/index/refresh                  # Refresh index
GET  /search/stats                          # Service stats
GET  /search/analytics                      # Analytics
```

**Cache Management**:
```python
GET  /cache/stats                           # Cache stats
POST /cache/invalidate                      # Invalidate cache
POST /cache/optimize                        # Optimize cache
```

### Bridge Service (8054) - 10+ Endpoints

**Synchronization**:
```python
POST /sync/full                             # Full sync
POST /sync/incremental                      # Incremental sync
GET  /sync/status                           # Sync status
POST /sync/realtime-document                # Real-time sync
```

**Entity Management**:
```python
POST /mapping/create                        # Create mapping
GET  /mapping/stats                         # Mapping stats
POST /intelligence/extract                  # Extract & map
```

**Webhook Handling**:
```python
POST /webhook/document-trigger              # Document webhook
POST /api/events/tree-index                 # Tree index events
```

**Health**:
```python
GET  /health                                # Service health
GET  /health/producer                       # Producer health
```

---

## Event Handlers & Kafka Consumers

### Handler Architecture

All handlers inherit from `BaseResponsePublisher` which provides:
- Response publishing to Kafka (DLQ, completion events)
- Error handling
- Logging infrastructure
- State management

### Core Handlers (20+)

| Handler | Responsibility | Input Event | Output Topics |
|---------|---|---|---|
| **QualityAssessmentHandler** | Code quality scoring, ONEX validation | Code-analysis-requested | quality-assessed |
| **PerformanceHandler** | Performance baseline, optimization | performance-analysis | perf-analyzed |
| **FreshnessHandler** | Document freshness analysis | document-update | freshness-analyzed |
| **DocumentProcessingHandler** | Document entity extraction | enrichment | doc-processed |
| **DocumentIndexingHandler** | Vector indexing | doc-processed | doc-indexed |
| **EntityExtractionHandler** | Code entity extraction | code-analysis-requested | entities-extracted |
| **PatternLearningHandler** | Pattern matching & scoring | pattern-match-request | pattern-matched |
| **PatternTraceabilityHandler** | Pattern lineage tracking | lineage-track | lineage-tracked |
| **PatternAnalyticsHandler** | Pattern usage analytics | pattern-usage | analytics-updated |
| **PerformanceAnalyticsHandler** | Performance metrics | perf-complete | perf-metrics |
| **CustomQualityRulesHandler** | Custom rule evaluation | quality-evaluate | rules-evaluated |
| **QualityTrendsHandler** | Quality trend analysis | quality-snapshot | trends-updated |
| **CodegenAnalysisHandler** | Codegen validation | codegen-request | codegen-validated |
| **CodegenPatternHandler** | Pattern-based codegen | pattern-codegen | pattern-codegen-done |
| **CodegenValidationHandler** | Validation for codegen | validation-request | validation-complete |
| **CodegenMixinHandler** | Mixin analysis | mixin-analysis | mixin-analyzed |
| **BridgeIntelligenceHandler** | OmniNode metadata generation | manifest-requested | manifest-completed |
| **AutonomousLearningHandler** | Autonomous pattern learning | autonomous-request | autonomous-learned |
| **TreeStampingHandler** | ONEX metadata stamping | tree-discovery | tree-stamped |
| **IntelligenceAdapterHandler** | Adapter/connector pattern | adapter-request | adapter-analyzed |

### Kafka Topics (Event Bus)

**Topic Naming Convention**: `dev.archon-intelligence.{domain}.{action}.v1`

| Topic | Purpose | Producers | Consumers |
|-------|---------|-----------|-----------|
| `dev.archon-intelligence.enrichment.requested.v1` | Document enrichment | Bridge | Intelligence-Consumer |
| `dev.archon-intelligence.code-analysis.requested.v1` | Code analysis | Bridge | Intelligence-Consumer |
| `dev.archon-intelligence.enrichment.completed.v1` | Enrichment complete | Intelligence-Consumer | Bridge, Search |
| `dev.archon-intelligence.quality.assessed.v1` | Quality assessment | Intelligence | Analytics |
| `dev.archon-intelligence.pattern.matched.v1` | Pattern matching | Intelligence | Analytics |
| `dev.archon-intelligence.lineage.tracked.v1` | Lineage tracking | Intelligence | Analytics |
| `dev.archon-intelligence.tree.discover.v1` | Tree discovery | OmniNode | Intelligence |
| `dev.archon-intelligence.tree.index.v1` | Tree indexing | OmniNode | Bridge |
| `dev.archon-intelligence.stamping.generate.v1` | ONEX stamping | OmniNode | Intelligence |

### Consumer Architecture

**Kafka Consumer Configuration** (`settings.kafka_*`):
```python
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "omninode-bridge-redpanda:9092")
KAFKA_CONSUMER_GROUP = "archon-intelligence-consumer"
KAFKA_AUTO_OFFSET_RESET = "earliest"
KAFKA_ENABLE_AUTO_COMMIT = False  # Manual offset management
KAFKA_SESSION_TIMEOUT_MS = 30000
KAFKA_HEARTBEAT_INTERVAL_MS = 10000
KAFKA_MAX_POLL_RECORDS = 100
KAFKA_FETCH_MAX_BYTES = 52428800  # 50MB
KAFKA_FETCH_MIN_BYTES = 1024
KAFKA_FETCH_MAX_WAIT_MS = 5000
```

**Consumer Loop Pattern**:
```python
async def consume_loop():
    while running:
        message = consumer.poll(timeout=1.0)
        if message:
            try:
                event_data = json.loads(message.value())
                await route_to_handler(event_data)
                consumer.commit(asynchronous=False)
            except Exception as e:
                await publish_to_dlq(message, e)
                consumer.commit(asynchronous=False)
```

---

## API Endpoints & Contracts

### Authentication & Security
- **No API Key Required** (development)
- **CORS Enabled** (configurable per environment)
- **Rate Limiting**: Via infrastructure (not in-service)
- **URL Validation**: Strict validation for all external URLs
- **DLQ Routing**: All processing errors route to DLQ topics

### Response Format

All APIs follow consistent response pattern:

```python
# Success Response (200)
{
    "success": bool,
    "status": str,
    "data": Any,
    "timestamp": str (ISO-8601),
    "correlation_id": str
}

# Error Response (4xx/5xx)
{
    "error": str,
    "status_code": int,
    "detail": str,
    "timestamp": str,
    "correlation_id": str
}
```

### Quality Assessment Endpoint

```python
POST /assess/code

Request:
{
    "file_path": str,
    "content": str,
    "language": str,
    "project_name": str,
    "options": {
        "include_recommendations": bool,
        "check_onex_compliance": bool,
        "include_patterns": bool
    }
}

Response:
{
    "success": bool,
    "quality_score": float (0-1),
    "issues": [
        {
            "type": str,
            "severity": str,
            "message": str,
            "line": int,
            "code": str
        }
    ],
    "recommendations": [str],
    "onex_compliance": {
        "compliant": bool,
        "violations": [str],
        "recommendations": [str]
    },
    "patterns": [
        {
            "name": str,
            "confidence": float,
            "description": str
        }
    ],
    "processing_time_ms": int
}
```

### Pattern Learning Endpoint

```python
POST /api/pattern-learning/pattern/match

Request:
{
    "code_snippet": str,
    "project_name": str,
    "context": {
        "file_path": str,
        "language": str,
        "framework": str
    }
}

Response:
{
    "matches": [
        {
            "pattern_id": str,
            "name": str,
            "confidence": float,
            "match_score": float,
            "description": str,
            "recommendations": [str]
        }
    ],
    "metadata": {
        "total_matches": int,
        "search_time_ms": int,
        "top_framework": str
    }
}
```

### Search Endpoint

```python
POST /search

Request:
{
    "query": str,
    "mode": SearchMode,  # SEMANTIC|STRUCTURAL|RELATIONAL|HYBRID
    "entity_types": [EntityType],
    "limit": int,
    "offset": int,
    "filters": {
        "project_name": str,
        "file_path": str,
        "language": str,
        "min_quality_score": float,
        "onex_compliant": bool
    }
}

Response:
{
    "results": [
        {
            "entity_id": str,
            "entity_type": str,
            "name": str,
            "content": str,
            "score": float,
            "similarity_score": float,  # Vector search
            "relationships": [],        # Graph search
            "metadata": {}
        }
    ],
    "total_count": int,
    "search_time_ms": int
}
```

### Document Processing Endpoint

```python
POST /process/document

Request:
{
    "document_id": str,
    "project_id": str,
    "title": str,
    "content": str|dict,
    "document_type": str,
    "metadata": dict
}

Response:
{
    "success": bool,
    "document_id": str,
    "entities_extracted": int,
    "relationships_created": int,
    "quality_score": float,
    "processing_time_ms": int,
    "entities": [
        {
            "entity_id": str,
            "entity_type": str,
            "name": str,
            "confidence": float
        }
    ]
}
```

### Vector Indexing Endpoint

```python
POST /vectorize/document

Request:
{
    "document_id": str,
    "project_id": str,
    "content": str,
    "metadata": {
        "document_type": str,
        "source_path": str,
        "file_extension": str,
        "quality_score": float,
        "onex_compliance": dict
    },
    "source_path": str,
    "entities": [dict]
}

Response:
{
    "success": bool,
    "document_id": str,
    "vector_id": str,
    "embedding_dimension": int,
    "indexed": bool,
    "index_refreshed": bool,
    "chunked": bool,
    "total_chunks": int,
    "indexed_chunks": int,
    "message": str
}
```

---

## Database Interaction Patterns

### 1. Qdrant Vector Database

**Purpose**: Semantic search via embeddings

**Collections**:
- `archon_vectors` - Main document vectors (1536 dimensions)
- `quality_vectors` - Quality assessment results
- `pattern_vectors` - Pattern embeddings

**Operations**:
```python
# Index document
await qdrant.upsert(
    collection_name="archon_vectors",
    points=[
        Point(
            id=document_id,
            vector=embedding,  # 1536D vector
            payload={
                "document_id": str,
                "entity_type": str,
                "source_path": str,
                "content": str[:100000],
                "quality_score": float,
                "onex_compliance": dict,
                "language": str,
                "project_name": str
            }
        )
    ]
)

# Search vectors
results = await qdrant.search(
    collection_name="archon_vectors",
    query_vector=query_embedding,
    limit=20,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="project_name",
                match=MatchValue(value="my-project")
            )
        ]
    )
)
```

**Adapter**: `/services/search/engines/qdrant_adapter.py`

### 2. Memgraph Knowledge Graph

**Purpose**: Entity relationships and graph traversal

**Node Types**:
- `DOCUMENT` - Files/documents
- `ENTITY` - Code entities (function, class, method, etc.)
- `PATTERN` - Detected patterns
- `PROJECT` - Project root nodes
- `DIRECTORY` - File tree structure

**Relationship Types**:
- `CONTAINS_ENTITY` - Document contains entity
- `IMPORTS` - Code imports
- `IMPLEMENTS` - Interface implementation
- `EXTENDS` - Class inheritance
- `DEPENDS_ON` - Dependency relationship
- `CONTAINS` - Directory containment
- `SIMILAR_TO` - Pattern similarity

**Operations**:
```python
# Create nodes and relationships
async def store_entities(entities):
    for entity in entities:
        await memgraph.query(f"""
            CREATE (n:ENTITY {{
                id: '{entity.entity_id}',
                name: '{entity.name}',
                type: '{entity.entity_type}',
                confidence: {entity.confidence_score}
            }})
        """)

# Traverse graph
async def find_related(entity_id):
    result = await memgraph.query(f"""
        MATCH (n)-[r:DEPENDS_ON|IMPORTS|IMPLEMENTS]->(m)
        WHERE n.id = '{entity_id}'
        RETURN m, r
    """)
```

**Adapter**: `/services/intelligence/storage/memgraph_adapter.py`

### 3. PostgreSQL Pattern Database (Remote)

**Purpose**: Pattern traceability, lineage, execution logs

**Schemas**:
- `patterns` - Pattern definitions
- `pattern_executions` - Execution history
- `pattern_feedback` - User feedback
- `lineage_tracking` - Pattern lineage

**Connection**:
```python
POSTGRES_HOST = 192.168.86.200
POSTGRES_PORT = 5436  # External port (5432 internal)
POSTGRES_DATABASE = omninode_bridge
POSTGRES_URL = postgresql://user:pass@192.168.86.200:5436/omninode_bridge
```

**Operations**:
```python
# Track pattern execution
INSERT INTO pattern_executions (
    pattern_id, executed_at, success, duration_ms, context
) VALUES (...)

# Record feedback
INSERT INTO pattern_feedback (
    pattern_id, feedback_type, rating, comment
) VALUES (...)

# Lineage tracking
INSERT INTO lineage_tracking (
    pattern_id, derived_from, transformation_type, metadata
) VALUES (...)
```

### 4. Valkey Cache (Redis Fork)

**Purpose**: Performance optimization with LRU eviction

**Configuration**:
- **Address**: `archon-valkey:6379` (Docker)
- **Memory**: 512MB
- **Eviction**: LRU (least recently used)
- **TTL**: 300s (5 minutes) default

**Cache Keys**:
- `research:rag:*` - RAG search results
- `research:vector:*` - Vector search results
- `research:knowledge:*` - Knowledge graph results
- `pattern:*` - Pattern data
- `entity:*` - Entity data
- `embedding:*` - Embedding cache (24-hour TTL)

**Operations**:
```python
# Cache research result
cache.set(f"research:rag:{query_hash}", result, ttl=300)

# Get cached result
result = cache.get(f"research:rag:{query_hash}")

# Invalidate pattern cache
cache.delete_pattern("pattern:*")
```

---

## Shared Models & Utilities

### Entity Models

**File**: `/shared/models/entity_types.py`

```python
class EntityType(str, Enum):
    # Document & Content
    DOCUMENT = "document"
    PAGE = "page"
    CODE_EXAMPLE = "code_example"

    # Code Structure
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    INTERFACE = "interface"
    COMPONENT = "component"

    # System
    API_ENDPOINT = "api_endpoint"
    SERVICE = "service"
    CONFIG_SETTING = "config_setting"

    # Knowledge
    CONCEPT = "concept"
    PATTERN = "pattern"
    VARIABLE = "variable"
    CONSTANT = "constant"
```

### Base Models

**File**: `/shared/models/base_models.py`

```python
class EntityMetadata(BaseModel):
    created_at: datetime
    updated_at: datetime
    created_by: str
    version: int
    extraction_confidence: float
    quality_score: float
    validation_status: str
    source_path: str
    source_hash: str
    line_number: int
    service_metadata: dict
    tags: List[str]

class BaseEntity(BaseModel):
    entity_id: str
    entity_type: EntityType
    name: str
    description: str
    content: Optional[str]
    summary: Optional[str]
    parent_id: Optional[str]
    project_id: Optional[str]
    source_id: Optional[str]
    embedding: Optional[List[float]]
    metadata: EntityMetadata
    properties: Dict[str, Any]

class BaseRelationship(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    properties: Dict[str, Any]
    confidence_score: float
    metadata: EntityMetadata
```

### Communication Models

**File**: `/shared/models/communication.py`

```python
class ServiceRequest(BaseModel):
    request_id: str
    correlation_id: str
    timestamp: datetime
    service_name: str
    operation: str
    payload: Dict[str, Any]

class ServiceResponse(BaseModel):
    success: bool
    request_id: str
    correlation_id: str
    status_code: int
    data: Dict[str, Any]
    errors: List[str]
    timestamp: datetime

class EntitySyncRequest(BaseModel):
    entities: List[BaseEntity]
    relationships: List[BaseRelationship]
    sync_type: str  # full, incremental

class EntitySyncResponse(BaseModel):
    success: bool
    synced_entities: int
    synced_relationships: int
    sync_id: str
    timestamp: datetime
```

### Pattern Models

**File**: `/services/intelligence/src/archon_services/pattern_learning/phase1_foundation/models/model_pattern.py`

```python
class Pattern(BaseModel):
    pattern_id: str
    name: str
    description: str
    pattern_type: str  # code, execution, document
    intent: str        # what problem it solves

    # Structure
    keywords: List[str]
    tags: List[str]
    frameworks: List[str]

    # Quality metrics
    confidence_score: float
    success_rate: float
    usage_count: int

    # Metadata
    discovered_at: datetime
    last_used_at: datetime
    use_cases: List[str]
    examples: List[str]
    anti_patterns: List[str]
```

### Quality Metrics Models

**Quality Scoring Dimensions**:
```python
class QualityScore(BaseModel):
    overall_score: float          # 0-100
    complexity: float             # 20% weight
    maintainability: float        # 20% weight
    documentation: float          # 15% weight
    temporal_relevance: float     # 15% weight
    pattern_compliance: float     # 15% weight
    architectural_compliance: float # 15% weight
```

### Freshness Models

**File**: `/services/intelligence/freshness/models.py`

```python
class FreshnessLevel(str, Enum):
    FRESH = "fresh"              # <7 days
    STALE = "stale"              # 7-30 days
    VERY_STALE = "very_stale"    # 30+ days
    ORPHANED = "orphaned"        # No references

class FreshnessAnalysis(BaseModel):
    document_id: str
    freshness_level: FreshnessLevel
    last_accessed: datetime
    last_modified: datetime
    days_since_access: int
    refresh_priority: RefreshPriority
    recommendations: List[str]
```

### ONEX Compliance Models

**File**: `/services/intelligence/onex/config.py`

```python
class ONEXCompliance(BaseModel):
    compliant: bool
    score: float (0-100)
    violations: List[str]
    recommendations: List[str]
    patterns_detected: List[str]

    # Metadata
    checked_at: datetime
    checker_version: str
    framework_versions: Dict[str, str]
```

---

## Migration Considerations

### 1. State & Statelessness

**Stateless Components** (easily portable):
- API endpoints and routes
- Entity extraction logic
- Scoring algorithms
- Pattern matching logic
- Quality assessment

**Stateful Components** (require careful migration):
- Event consumers (offset management)
- Caching layers (requires cache-aside pattern)
- Database connections (connection pooling)
- Pattern discovery state (learning phases)

### 2. Event-Driven Dependencies

**Kafka Dependency**:
- Intelligence consumer requires Kafka for event processing
- Must handle **graceful degradation** if Kafka unavailable
- DLQ routing essential for production reliability
- Offset management critical for exactly-once semantics

**Mitigation**:
- Implement circuit breaker pattern for Kafka
- Health check endpoints for dependency monitoring
- Async processing with timeout handling
- Comprehensive error logging and recovery

### 3. Database Migration

**Qdrant Migration**:
- Export collections with vectors and metadata
- Recreate collections in target environment
- Validate vector dimensions (1536D standard)
- Test similarity search relevance

**Memgraph Migration**:
- Export all nodes and relationships
- Validate graph integrity (no orphaned nodes)
- Recreate indexes
- Test traversal queries

**PostgreSQL Migration**:
- Backup pattern tables
- Migrate schemas and data
- Update connection strings to target database
- Validate referential integrity

### 4. Configuration Management

**Environment Variables** (required):
```
# Service URLs
INTELLIGENCE_SERVICE_URL=http://localhost:8053
BRIDGE_SERVICE_URL=http://localhost:8054
SEARCH_SERVICE_URL=http://localhost:8055

# Databases
MEMGRAPH_URI=bolt://memgraph:7687
QDRANT_URL=http://qdrant:6333
POSTGRES_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://archon-valkey:6379

# Event Bus
KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092  # (host scripts)
# or omninode-bridge-redpanda:9092             # (Docker services)

# Configuration
LOG_LEVEL=INFO
ENVIRONMENT=production
CACHE_TTL=300
```

### 5. API Contract Stability

**Backwards Compatibility**:
- All APIs support both snake_case and camelCase
- Entity type enum values backward compatible
- Response format stable (no breaking changes)
- Deprecation warnings for legacy endpoints

**Migration Path**:
- Run old + new systems in parallel
- Gradual traffic shift from old → new
- Keep legacy API endpoints for grace period
- Monitor error rates and metrics during migration

### 6. Performance Characteristics

**Typical Latencies** (production):
- Quality assessment: 500-1000ms
- Vector search: 50-100ms (with cache)
- Graph traversal: 200-500ms
- Pattern matching: 300-800ms
- Document processing: 2-5s

**Scaling Considerations**:
- Qdrant: Scales to millions of vectors
- Memgraph: 100k+ nodes in-memory graphs
- Valkey: 512MB cache for distributed systems
- Kafka: Scales horizontally via partitions

### 7. Testing Strategy

**Unit Tests**:
- Entity extraction logic
- Quality scoring algorithms
- Pattern matching logic
- Database adapters

**Integration Tests**:
- API endpoints with mocked services
- Event handler chains
- Database operations
- Cache behavior

**End-to-End Tests**:
- Full pipeline: Document → Entities → Graph → Search
- Event-driven workflows
- Error handling and DLQ
- Concurrent operations

### 8. Logging & Observability

**Correlation Tracing**:
- `correlation_id` propagated through all layers
- `request_id` for API request tracking
- Pipeline stages logged with timing
- Structured JSON logging for parsing

**Metrics**:
- Prometheus endpoints for scraping
- Custom metrics for quality scores
- Event processing metrics (lag, throughput)
- Cache hit/miss rates

**Health Endpoints**:
- `/health` - Service health
- `/health/producer` - Kafka producer health
- `/api/*/health` - Module-specific health

---

## Key Implementation Patterns

### Error Handling Pattern

```python
try:
    result = await process_event(event)
    await publish_completion_event(result)

except ErrorClassifier.NonRetryable as e:
    # Route to DLQ immediately
    await publish_to_dlq(event, e, retry_count=0)

except Exception as e:
    # Retry with exponential backoff
    if retry_count < MAX_RETRIES:
        await reschedule_with_backoff(event, retry_count + 1)
    else:
        await publish_to_dlq(event, e, retry_count)
```

### Async Processing Pattern

```python
async def process_batch(items: List[Item]):
    tasks = [process_single_item(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    log_metrics(len(successes), len(failures))
    return BatchResult(successes, failures)
```

### Caching Pattern (Cache-Aside)

```python
async def get_entity(entity_id: str):
    # 1. Check cache
    cached = await cache.get(f"entity:{entity_id}")
    if cached:
        return cached

    # 2. Load from database
    entity = await db.get_entity(entity_id)

    # 3. Update cache
    await cache.set(f"entity:{entity_id}", entity, ttl=300)

    return entity
```

### Circuit Breaker Pattern

```python
@circuit_breaker(failure_threshold=5, timeout=60)
async def call_external_service(request):
    # Auto-fail if failure_threshold breached
    # Retry after timeout seconds
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=request)
        return response.json()
```

---

## Summary

The Omniarchon system is a sophisticated, event-driven microservices architecture that provides comprehensive code intelligence, pattern learning, and quality assessment capabilities. Its modular design allows for partial migrations and gradual adoption into ONEX.

**Key Strengths for Migration**:
- Stateless API design (easily containerized)
- Event-driven architecture (decouples services)
- Comprehensive error handling (DLQ pattern)
- Rich shared models (consistent contracts)

**Challenges to Address**:
- Kafka dependency (requires event bus)
- Multiple database systems (requires coordination)
- Complex pattern learning state (4 phases)
- Performance optimization needs (caching critical)

**Recommended Approach**:
1. Start with stateless APIs (quality assessment, entity extraction)
2. Migrate databases (Qdrant, Memgraph, PostgreSQL)
3. Integrate event bus (Kafka/Redpanda)
4. Migrate pattern learning system (phases 1-4)
5. Integrate with ONEX node infrastructure
