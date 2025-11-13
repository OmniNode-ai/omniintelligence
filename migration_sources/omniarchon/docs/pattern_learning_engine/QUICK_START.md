# Pattern Learning Engine: Quick Start Guide

## 🚀 Setup Instructions

### 1. Run Database Migration

```bash
# From intelligence-service directory
cd /Volumes/PRO-G40/Code/Archon/intelligence-service

# Apply migration
poetry run alembic upgrade head

# Verify table created
poetry run alembic current
```

### 2. Create Qdrant Collection

```python
from qdrant_client import QdrantClient
from app.config.qdrant_pattern_collection import PatternCollectionConfig

# Initialize client
client = QdrantClient(url="http://qdrant:6333")

# Get collection config
config = PatternCollectionConfig.get_collection_config()

# Create collection
client.create_collection(
    collection_name=config["collection_name"],
    vectors_config=config["vectors_config"],
    optimizers_config=config["optimizers_config"],
    on_disk_payload=True
)

print("✅ Qdrant collection created!")
```

### 3. Test Schema Validation

```python
from app.models.pattern_learning import PatternMatchRequest, PatternMatchFilters

# Test request validation
request = PatternMatchRequest(
    intent="optimize database query performance",
    context="FastAPI + PostgreSQL, 1000 req/sec",
    requirements=["low latency", "high availability"],
    filters=PatternMatchFilters(
        pattern_types=["api_optimization"],
        min_quality_score=0.8,
        tags=["postgresql", "optimization"]
    ),
    limit=5,
    min_confidence=0.7
)

print("✅ Request schema validated!")
print(request.json(indent=2))
```

---

## 📋 Usage Examples

### Create a Pattern

```python
from app.models.pattern_learning import SuccessPattern
from sqlalchemy.orm import Session
import hashlib
import json

# Create session (pseudo-code - use your session manager)
session = Session()

# Calculate context hash
context = {
    "intent": "optimize API performance",
    "environment": "FastAPI + PostgreSQL"
}
context_hash = hashlib.sha256(
    json.dumps(context, sort_keys=True).encode()
).hexdigest()

# Create pattern
pattern = SuccessPattern(
    pattern_type="api_optimization",
    name="Connection Pooling with Read Replicas",
    description="Optimize database queries using connection pooling and read replicas",
    context_hash=context_hash,
    execution_trace={
        "steps": [
            "Configure connection pool (min=10, max=50)",
            "Setup read replicas (2 instances)",
            "Route read queries to replicas"
        ]
    },
    success_criteria={
        "metric": "p99_latency_ms",
        "threshold": 50,
        "operator": "<"
    },
    quality_metrics={
        "accuracy": 0.95,
        "latency_p99_ms": 45,
        "reliability": 0.99
    },
    performance_data={
        "avg_runtime_ms": 38,
        "memory_mb": 128,
        "cpu_usage_pct": 15
    },
    tags=["postgresql", "optimization", "scaling", "replication"],
    status="active"
)

session.add(pattern)
session.commit()

print(f"✅ Pattern created: {pattern.pattern_id}")
```

### Synchronize to Qdrant

```python
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from app.config.qdrant_pattern_collection import create_pattern_payload
import openai

# Initialize clients
qdrant = QdrantClient(url="http://qdrant:6333")
openai.api_key = "your-api-key"

# Generate embedding
embedding_text = f"""
Pattern Type: {pattern.pattern_type}
Name: {pattern.name}
Description: {pattern.description}
Tags: {', '.join(pattern.tags)}
"""

response = openai.embeddings.create(
    model="text-embedding-3-small",
    input=embedding_text
)
embedding_vector = response.data[0].embedding

# Create Qdrant payload
payload = create_pattern_payload(
    pattern_id=str(pattern.pattern_id),
    pattern_type=pattern.pattern_type,
    version=pattern.version,
    status=pattern.status,
    tags=pattern.tags,
    quality_score=pattern.calculate_quality_score() or 0.0,
    success_rate=float(pattern.success_rate) if pattern.success_rate else None,
    match_count=pattern.match_count,
    created_at=int(pattern.created_at.timestamp()),
    last_matched_at=int(pattern.last_matched_at.timestamp()) if pattern.last_matched_at else None
)

# Upsert to Qdrant
qdrant.upsert(
    collection_name="pattern_embeddings",
    points=[
        PointStruct(
            id=str(pattern.pattern_id),
            vector=embedding_vector,
            payload=payload
        )
    ]
)

print("✅ Pattern synchronized to Qdrant!")
```

### Search for Patterns

```python
from app.models.pattern_learning import PatternMatchRequest
from app.config.qdrant_pattern_collection import PatternSearchFilters

# Create search request
request = PatternMatchRequest(
    intent="optimize API performance under high load",
    context="FastAPI application, 1000 req/sec, p99 latency 500ms",
    requirements=["low latency", "horizontal scaling"],
    filters={
        "pattern_types": ["api_optimization", "performance_tuning"],
        "min_quality_score": 0.8,
        "min_success_rate": 0.75,
        "tags": ["fastapi", "postgresql"]
    },
    limit=5,
    min_confidence=0.7
)

# Generate query embedding
response = openai.embeddings.create(
    model="text-embedding-3-small",
    input=f"{request.intent} {request.context or ''}"
)
query_vector = response.data[0].embedding

# Build Qdrant filter
search_filter = PatternSearchFilters.build_filter(
    pattern_types=request.filters.pattern_types,
    statuses=request.filters.statuses,
    tags=request.filters.tags,
    min_quality_score=request.filters.min_quality_score,
    min_success_rate=request.filters.min_success_rate,
)

# Search Qdrant
results = qdrant.search(
    collection_name="pattern_embeddings",
    query_vector=query_vector,
    query_filter=search_filter,
    limit=request.limit,
    score_threshold=request.min_confidence
)

# Fetch full metadata from PostgreSQL
pattern_ids = [result.id for result in results]
patterns = session.query(SuccessPattern).filter(
    SuccessPattern.pattern_id.in_(pattern_ids)
).all()

# Combine results
matched_patterns = []
for result in results:
    pattern = next(p for p in patterns if str(p.pattern_id) == result.id)
    matched_patterns.append({
        "pattern_id": pattern.pattern_id,
        "name": pattern.name,
        "confidence_score": result.score,
        "metadata": {
            "version": pattern.version,
            "quality_metrics": pattern.quality_metrics,
            "success_rate": float(pattern.success_rate) if pattern.success_rate else None,
            "match_count": pattern.match_count
        }
    })

print(f"✅ Found {len(matched_patterns)} matching patterns!")
for mp in matched_patterns:
    print(f"  - {mp['name']}: {mp['confidence_score']:.2f}")
```

### Update Pattern Statistics

```python
# After successfully using a pattern
pattern = session.query(SuccessPattern).filter_by(
    pattern_id=pattern_id
).first()

# Increment usage
pattern.increment_match_count()

# Update success rate (example: 15 successes out of 17 uses)
pattern.success_rate = 15 / 17

session.commit()

# Sync to Qdrant (update payload)
qdrant.set_payload(
    collection_name="pattern_embeddings",
    payload={
        "match_count": pattern.match_count,
        "success_rate": float(pattern.success_rate),
        "last_matched_at": int(pattern.last_matched_at.timestamp())
    },
    points=[str(pattern.pattern_id)]
)

print("✅ Pattern statistics updated!")
```

---

## 🔧 API Endpoints (To Be Implemented)

### Pattern Matching

```http
POST /api/v1/patterns/match
Content-Type: application/json

{
  "intent": "optimize API performance under high load",
  "context": "FastAPI application, 1000 req/sec",
  "requirements": ["low latency", "horizontal scaling"],
  "filters": {
    "pattern_types": ["api_optimization"],
    "min_quality_score": 0.8,
    "tags": ["fastapi", "postgresql"]
  },
  "limit": 5,
  "min_confidence": 0.7
}
```

Response:
```json
{
  "matched_patterns": [
    {
      "pattern_id": "550e8400-e29b-41d4-a716-446655440000",
      "pattern_type": "api_optimization",
      "name": "Connection Pooling with Read Replicas",
      "description": "Optimize database queries...",
      "confidence_score": 0.89,
      "metadata": {
        "version": 2,
        "quality_metrics": {"accuracy": 0.95, "latency_p99_ms": 45},
        "success_rate": 0.87,
        "match_count": 23
      },
      "recommendations": [
        "Configure connection pool size based on workload",
        "Route read queries to replicas"
      ]
    }
  ],
  "total_matches": 1,
  "query_metadata": {
    "query_time_ms": 42,
    "embedding_model": "text-embedding-3-small"
  }
}
```

### Pattern Management

```http
# Create pattern
POST /api/v1/patterns
Content-Type: application/json

{
  "pattern_type": "api_optimization",
  "name": "Connection Pooling Pattern",
  "description": "Optimize database connections...",
  "execution_trace": {...},
  "quality_metrics": {...},
  "tags": ["postgresql", "optimization"]
}

# List patterns
GET /api/v1/patterns?pattern_type=api_optimization&status=active

# Get pattern
GET /api/v1/patterns/{pattern_id}

# Update pattern
PATCH /api/v1/patterns/{pattern_id}

# Delete pattern
DELETE /api/v1/patterns/{pattern_id}
```

---

## 🎯 Performance Optimization Tips

### 1. PostgreSQL Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE
SELECT * FROM success_patterns
WHERE pattern_type = 'api_optimization'
  AND status = 'active'
  AND tags && ARRAY['postgresql', 'optimization'];

-- Vacuum and analyze regularly
VACUUM ANALYZE success_patterns;

-- Monitor index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE tablename = 'success_patterns'
ORDER BY idx_scan DESC;
```

### 2. Qdrant Optimization

```python
# Optimize HNSW parameters for your workload
client.update_collection(
    collection_name="pattern_embeddings",
    hnsw_config={
        "m": 16,  # Higher = better accuracy, more memory
        "ef_construct": 100  # Higher = slower indexing, better quality
    }
)

# Enable quantization for memory efficiency
client.update_collection(
    collection_name="pattern_embeddings",
    quantization_config={
        "scalar": {
            "type": "int8",
            "quantile": 0.99,
            "always_ram": True
        }
    }
)

# Monitor collection stats
info = client.get_collection("pattern_embeddings")
print(f"Vectors: {info.vectors_count}")
print(f"Indexed: {info.indexed_vectors_count}")
print(f"Status: {info.status}")
```

### 3. Embedding Caching

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def get_cached_embedding(text: str) -> list[float]:
    """Cache embeddings for frequently used queries."""
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

---

## 📊 Monitoring & Observability

### Key Metrics to Track

```python
# Pattern matching latency
latency_histogram = Histogram(
    "pattern_match_latency_seconds",
    "Pattern matching request latency",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# Qdrant search performance
qdrant_search_duration = Histogram(
    "qdrant_search_duration_seconds",
    "Qdrant semantic search latency"
)

# PostgreSQL lookup performance
postgres_lookup_duration = Histogram(
    "postgres_lookup_duration_seconds",
    "PostgreSQL metadata lookup latency"
)

# Sync lag
sync_lag_gauge = Gauge(
    "pattern_sync_lag_seconds",
    "Time between PostgreSQL write and Qdrant update"
)

# Pattern usage
pattern_matches_counter = Counter(
    "pattern_matches_total",
    "Total pattern matches",
    ["pattern_type", "status"]
)
```

### Health Checks

```python
async def check_pattern_system_health():
    """Comprehensive health check for pattern learning system."""
    health = {
        "postgresql": False,
        "qdrant": False,
        "sync": False,
        "embedding": False
    }

    # PostgreSQL
    try:
        session.execute("SELECT 1")
        health["postgresql"] = True
    except Exception as e:
        print(f"PostgreSQL health check failed: {e}")

    # Qdrant
    try:
        qdrant.get_collection("pattern_embeddings")
        health["qdrant"] = True
    except Exception as e:
        print(f"Qdrant health check failed: {e}")

    # Sync (check for lag > 60 seconds)
    try:
        recent = session.query(SuccessPattern).order_by(
            SuccessPattern.created_at.desc()
        ).first()
        if recent:
            qdrant_point = qdrant.retrieve(
                collection_name="pattern_embeddings",
                ids=[str(recent.pattern_id)]
            )
            health["sync"] = len(qdrant_point) > 0
    except Exception as e:
        print(f"Sync health check failed: {e}")

    # Embedding service
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input="health check"
        )
        health["embedding"] = len(response.data) > 0
    except Exception as e:
        print(f"Embedding health check failed: {e}")

    return health
```

---

## 🐛 Troubleshooting

### Issue: Slow Pattern Matching (>50ms)

1. Check Qdrant index status:
   ```python
   info = qdrant.get_collection("pattern_embeddings")
   if info.indexed_vectors_count < info.vectors_count:
       print("⚠️ Indexing in progress, search will be slow")
   ```

2. Verify PostgreSQL indexes:
   ```sql
   SELECT * FROM pg_stat_user_indexes
   WHERE tablename = 'success_patterns' AND idx_scan = 0;
   ```

3. Check query plan:
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM success_patterns WHERE pattern_id IN ('uuid1', 'uuid2');
   ```

### Issue: Sync Lag Between PostgreSQL and Qdrant

1. Monitor sync queue depth
2. Check embedding service latency
3. Verify Qdrant write performance
4. Implement reconciliation job

### Issue: Out of Memory

1. Enable Qdrant quantization
2. Move payload to disk: `on_disk_payload=True`
3. Reduce `hnsw_config.m` parameter
4. Use smaller embedding model

---

## 📚 Additional Resources

- **Consensus Report**: `/docs/pattern_learning_engine/SCHEMA_DESIGN_CONSENSUS_REPORT.md`
- **Migration**: `/intelligence-service/alembic/versions/001_create_success_patterns_table.py`
- **Qdrant Config**: `/intelligence-service/app/config/qdrant_pattern_collection.py`
- **Schemas**: `/intelligence-service/app/models/pattern_learning/schemas.py`
- **ORM Models**: `/intelligence-service/app/models/pattern_learning/models.py`

---

**Next Steps**: Implement pattern matching API endpoint and synchronization pipeline!
