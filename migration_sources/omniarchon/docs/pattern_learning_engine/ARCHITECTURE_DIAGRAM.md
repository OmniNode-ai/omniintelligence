# Pattern Learning Engine: Architecture Diagram

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Pattern Learning Engine Architecture                │
│                      Multi-Model Consensus Design                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐│
│  │   Web UI/CLI    │      │  External API   │      │   AI Agents     ││
│  │   (FastAPI)     │      │    Clients      │      │  (Autonomous)   ││
│  └────────┬────────┘      └────────┬────────┘      └────────┬────────┘│
│           │                        │                        │         │
│           └────────────────────────┼────────────────────────┘         │
│                                    │                                   │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │
                                     │ HTTP/JSON
                                     │
┌────────────────────────────────────┼───────────────────────────────────┐
│                         API LAYER (FastAPI)                             │
├────────────────────────────────────┼───────────────────────────────────┤
│                                    │                                   │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │              Pattern Matching Endpoint                           │ │
│  │  POST /api/v1/patterns/match                                     │ │
│  │  - Validate request (Pydantic schemas)                           │ │
│  │  - Generate embedding (OpenAI)                                   │ │
│  │  - Orchestrate search (Qdrant + PostgreSQL)                      │ │
│  │  - Return matched patterns with confidence                       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │              Pattern Management Endpoints                        │ │
│  │  POST   /api/v1/patterns        (Create)                         │ │
│  │  GET    /api/v1/patterns        (List)                           │ │
│  │  GET    /api/v1/patterns/{id}   (Get)                            │ │
│  │  PATCH  /api/v1/patterns/{id}   (Update)                         │ │
│  │  DELETE /api/v1/patterns/{id}   (Delete)                         │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                    │                                    │
                    │                                    │
        ┌───────────┴─────────┐              ┌──────────┴───────────┐
        │ Embedding Service   │              │  Sync Pipeline       │
        │ (OpenAI API)        │              │  (Event-Driven)      │
        └───────────┬─────────┘              └──────────┬───────────┘
                    │                                    │
                    │ 1536-dim vectors                   │
                    │ (text-embedding-3-small)           │
                    │                                    │
┌───────────────────┴────────────────────────────────────┴───────────────┐
│                         DATA LAYER                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐ │
│  │   PostgreSQL (Source of      │    │   Qdrant (Semantic Index)    │ │
│  │   Truth)                     │    │                              │ │
│  ├──────────────────────────────┤    ├──────────────────────────────┤ │
│  │                              │    │                              │ │
│  │ Table: success_patterns      │◄──►│ Collection: pattern_embeddings│ │
│  │                              │    │                              │ │
│  │ Fields (18):                 │    │ Vector Config:               │ │
│  │ • pattern_id (UUID)          │    │ • Size: 1536                 │ │
│  │ • pattern_type               │    │ • Distance: Cosine           │ │
│  │ • name (UNIQUE)              │    │ • Index: HNSW                │ │
│  │ • description                │    │                              │ │
│  │ • version                    │    │ Payload (10 fields):         │ │
│  │ • parent_pattern_id          │    │ • pattern_id (UUID)          │ │
│  │ • context_hash (INDEXED)     │    │ • pattern_type (indexed)     │ │
│  │ • execution_trace (JSONB)    │    │ • version (indexed)          │ │
│  │ • success_criteria (JSONB)   │    │ • status (indexed)           │ │
│  │ • quality_metrics (JSONB)    │    │ • tags[] (indexed)           │ │
│  │ • performance_data (JSONB)   │    │ • quality_score (indexed)    │ │
│  │ • tags[] (INDEXED)           │    │ • success_rate (indexed)     │ │
│  │ • status (INDEXED)           │    │ • match_count (indexed)      │ │
│  │ • created_at (INDEXED)       │    │ • created_at (indexed)       │ │
│  │ • updated_at                 │    │ • last_matched_at            │ │
│  │ • last_matched_at (INDEXED)  │    │                              │ │
│  │ • match_count                │    │ Performance:                 │ │
│  │ • success_rate               │    │ • Search: <30ms p99          │ │
│  │                              │    │ • Filtering: Payload indexes │ │
│  │ Indexes (10):                │    │ • Scale: 1M+ vectors         │ │
│  │ • Primary: pattern_id        │    │                              │ │
│  │ • B-tree: 5 fields           │    │                              │ │
│  │ • GIN: tags, JSONB fields    │    │                              │ │
│  │ • Composite: type+status     │    │                              │ │
│  │                              │    │                              │ │
│  │ Performance:                 │    │                              │ │
│  │ • Lookup: <20ms by UUID      │    │                              │ │
│  │ • JSONB queries: GIN indexed │    │                              │ │
│  │                              │    │                              │ │
│  └──────────────────────────────┘    └──────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Pattern Matching Query

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Pattern Matching Flow (<50ms)                        │
└─────────────────────────────────────────────────────────────────────────┘

1. Client Request
   │
   ├─► POST /api/v1/patterns/match
   │   {
   │     "intent": "optimize API performance",
   │     "context": "FastAPI + PostgreSQL, 1000 req/sec",
   │     "filters": {
   │       "pattern_types": ["api_optimization"],
   │       "min_quality_score": 0.8
   │     },
   │     "limit": 5
   │   }
   │
   ▼

2. Request Validation (Pydantic)
   │
   ├─► PatternMatchRequest.parse_obj(request)
   │   • Validate intent (1-1000 chars)
   │   • Validate filters (types, scores, etc.)
   │   • Validate limit (1-100)
   │
   ▼

3. Embedding Generation (~100-200ms)
   │
   ├─► OpenAI API: text-embedding-3-small
   │   Input: "optimize API performance FastAPI + PostgreSQL, 1000 req/sec"
   │   Output: [0.023, -0.045, 0.178, ...] (1536 dimensions)
   │
   ▼

4. Qdrant Search (~20-30ms)
   │
   ├─► qdrant.search(
   │     collection="pattern_embeddings",
   │     query_vector=embedding,
   │     filter={
   │       "pattern_type": ["api_optimization"],
   │       "quality_score": {"gte": 0.8}
   │     },
   │     limit=5
   │   )
   │
   │   Returns: [
   │     {id: "uuid-1", score: 0.89, payload: {...}},
   │     {id: "uuid-2", score: 0.85, payload: {...}},
   │     {id: "uuid-3", score: 0.82, payload: {...}}
   │   ]
   │
   ▼

5. PostgreSQL Enrichment (~10-20ms)
   │
   ├─► SELECT * FROM success_patterns
   │   WHERE pattern_id IN ('uuid-1', 'uuid-2', 'uuid-3')
   │
   │   Returns: Full pattern metadata (quality_metrics, execution_trace, etc.)
   │
   ▼

6. Response Construction
   │
   ├─► Combine Qdrant scores with PostgreSQL metadata
   │   • Generate recommendations
   │   • Calculate query metadata (timing, filters applied)
   │
   ▼

7. Client Response
   │
   └─► {
       "matched_patterns": [
         {
           "pattern_id": "uuid-1",
           "name": "Connection Pooling with Read Replicas",
           "confidence_score": 0.89,
           "metadata": {...},
           "recommendations": [...]
         }
       ],
       "total_matches": 3,
       "query_metadata": {
         "query_time_ms": 42,
         "embedding_model": "text-embedding-3-small"
       }
     }

Total Time: ~30-50ms (excluding embedding generation)
```

## Data Synchronization Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  PostgreSQL → Qdrant Synchronization                    │
└─────────────────────────────────────────────────────────────────────────┘

Phase 1: Application-Level Sync (Initial Implementation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Pattern Create/Update Request
   │
   ├─► POST /api/v1/patterns
   │
   ▼
2. PostgreSQL Write Transaction
   │
   ├─► BEGIN TRANSACTION
   │   INSERT INTO success_patterns (...)
   │   COMMIT
   │
   │   Pattern saved with pattern_id
   │
   ▼
3. Generate Embedding
   │
   ├─► embedding_text = f"{pattern_type} {name} {description} {tags}"
   │   vector = openai.embeddings.create(input=embedding_text)
   │
   ▼
4. Qdrant Upsert
   │
   ├─► qdrant.upsert(
   │     collection="pattern_embeddings",
   │     points=[{
   │       id: pattern_id,
   │       vector: embedding_vector,
   │       payload: {
   │         pattern_id, pattern_type, version, status,
   │         tags, quality_score, success_rate, ...
   │       }
   │     }]
   │   )
   │
   ▼
5. Return Response
   │
   └─► Pattern created and indexed

Phase 2: Event-Driven Sync (Production Implementation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. PostgreSQL Write
   │
   ├─► INSERT/UPDATE success_patterns
   │   Trigger: AFTER INSERT/UPDATE
   │
   ▼
2. Event Publisher
   │
   ├─► Publish to Kafka/RabbitMQ
   │   Topic: "pattern.created" / "pattern.updated"
   │   Payload: {pattern_id, event_type, timestamp}
   │
   ▼
3. Sync Worker (Consumer)
   │
   ├─► Consume event
   │   Fetch pattern from PostgreSQL
   │   Generate embedding
   │   Upsert to Qdrant
   │
   ▼
4. Monitoring
   │
   └─► Track sync lag, success rate, failures
```

## Schema Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Pattern Evolution Tracking                           │
└─────────────────────────────────────────────────────────────────────────┘

Pattern Family Tree Example:

┌──────────────────────────────────────────────────────────────────┐
│ Pattern: "Connection Pooling" (v1)                               │
│ pattern_id: uuid-001                                             │
│ parent_pattern_id: NULL                                          │
│ version: 1                                                       │
│ status: deprecated                                               │
│ created_at: 2025-01-01                                           │
│ match_count: 45                                                  │
│ success_rate: 0.82                                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ parent_pattern_id
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Pattern: "Connection Pooling with Read Replicas" (v2)           │
│ pattern_id: uuid-002                                             │
│ parent_pattern_id: uuid-001                                      │
│ version: 2                                                       │
│ status: active                                                   │
│ created_at: 2025-06-01                                           │
│ match_count: 23                                                  │
│ success_rate: 0.91                                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ parent_pattern_id
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Pattern: "Connection Pooling + Read Replicas + Caching" (v3)    │
│ pattern_id: uuid-003                                             │
│ parent_pattern_id: uuid-002                                      │
│ version: 3                                                       │
│ status: active                                                   │
│ created_at: 2025-09-01                                           │
│ match_count: 7                                                   │
│ success_rate: 0.95                                               │
└──────────────────────────────────────────────────────────────────┘

Query: "Get pattern evolution chain"
SELECT * FROM success_patterns
WHERE pattern_id = 'uuid-003'
   OR pattern_id IN (
     SELECT parent_pattern_id FROM success_patterns WHERE pattern_id = 'uuid-003'
   )
ORDER BY version DESC;
```

## Multi-Model Consensus Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│              Multi-Model Consensus Schema Design Process                │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│   Gemini Pro       │     │   Llama 3.2        │     │  Gemini Flash      │
│   (Stance: FOR)    │     │   (Stance: AGAINST)│     │  (Stance: NEUTRAL) │
├────────────────────┤     ├────────────────────┤     ├────────────────────┤
│                    │     │                    │     │                    │
│ Role:              │     │ Role:              │     │ Role:              │
│ • Architectural    │     │ • Implementation   │     │ • Synthesis &      │
│   validation       │     │   details          │     │   balance          │
│ • Strategic review │     │ • Edge cases       │     │ • Comprehensive    │
│                    │     │                    │     │   design           │
│ Output:            │     │ Output:            │     │                    │
│ • Data sync        │     │ • Concrete SQL     │     │ Output:            │
│   critical         │     │ • GIN indexes      │     │ • Complete schema  │
│ • Payload          │     │ • Migration        │     │ • API contracts    │
│   filtering        │     │   strategy         │     │ • Best practices   │
│ • Versioning       │     │                    │     │                    │
│   essential        │     │ Issues Found:      │     │ Enhancements:      │
│                    │     │ • Euclidean dist   │     │ • Cosine distance  │
│ Confidence: 9/10   │     │ • Missing fields   │     │ • UUID PKs         │
│                    │     │ • No versioning    │     │ • Full field set   │
│                    │     │                    │     │                    │
│                    │     │ Confidence: 7/10   │     │ Confidence: 9/10   │
└─────────┬──────────┘     └─────────┬──────────┘     └─────────┬──────────┘
          │                          │                          │
          │                          │                          │
          └──────────────────────────┴──────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │   Consensus Synthesis          │
                    ├────────────────────────────────┤
                    │                                │
                    │ Agreements (10):               │
                    │ ✅ Dual-database architecture  │
                    │ ✅ Data sync critical          │
                    │ ✅ JSONB flexibility           │
                    │ ✅ Versioning essential        │
                    │ ✅ Sub-50ms achievable         │
                    │ ✅ Payload filtering           │
                    │ ✅ UUID primary keys           │
                    │ ✅ Cosine distance             │
                    │ ✅ GIN indexes                 │
                    │ ✅ Industry-standard           │
                    │                                │
                    │ Disagreements Resolved (5):    │
                    │ ❌→✅ Euclidean → Cosine       │
                    │ ❌→✅ SERIAL → UUID            │
                    │ ❌→✅ Minimal → Comprehensive  │
                    │ ❌→✅ No versioning → Required │
                    │ ❌→✅ Custom → SDK format      │
                    │                                │
                    │ Final Confidence: 9/10         │
                    │                                │
                    └────────────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │   Final Implementation         │
                    ├────────────────────────────────┤
                    │ • PostgreSQL migration         │
                    │ • Qdrant configuration         │
                    │ • Pydantic schemas             │
                    │ • SQLAlchemy models            │
                    │ • Documentation                │
                    └────────────────────────────────┘
```

---

## Performance Optimization Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Sub-50ms Performance Strategy                         │
└─────────────────────────────────────────────────────────────────────────┘

Target Breakdown:
• Qdrant semantic search:  20-30ms ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 60%
• PostgreSQL metadata:     10-20ms ━━━━━━━━━━━━━ 30%
• API overhead:             2-5ms  ━━━ 10%
                          ─────────
Total:                     32-55ms (Target: <50ms p99)

Optimization Techniques:

1. Qdrant (20-30ms target)
   ├─► HNSW indexing (m=16, ef_construct=100)
   ├─► Payload filtering (avoid post-search filtering)
   ├─► Quantization (4x memory reduction, minimal accuracy loss)
   └─► On-disk payload (large collections)

2. PostgreSQL (10-20ms target)
   ├─► UUID index for O(log n) lookup
   ├─► Connection pooling (min=10, max=50)
   ├─► Parallel queries for multiple pattern_ids
   └─► Read replicas for load distribution

3. Caching
   ├─► Embedding cache (LRU, 1000 entries)
   ├─► Pattern metadata cache (Redis, 5min TTL)
   └─► Query result cache (30sec TTL for popular queries)

4. Query Orchestration
   ├─► Async parallel execution (Qdrant + PostgreSQL)
   ├─► Early termination on low confidence
   └─► Batch processing for multiple patterns

Monitoring:
• P99 latency: <50ms (target)
• P95 latency: <40ms (stretch goal)
• P50 latency: <30ms (optimal)
```

---

**Architecture Status**: ✅ Complete and Validated
**Multi-Model Consensus**: 9/10 confidence
**Performance Target**: <50ms pattern matching
**Scalability**: 1M+ patterns, 1000+ req/sec
