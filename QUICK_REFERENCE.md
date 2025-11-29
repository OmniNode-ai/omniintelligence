# Omniarchon Components - Quick Reference

## File Locations

| Component | Path | Purpose |
|-----------|------|---------|
| **Intelligence Service** | `/services/intelligence/app.py` | 78+ APIs for code analysis |
| **Search Service** | `/services/search/app.py` | Hybrid search (vector+graph+relational) |
| **Bridge Service** | `/services/bridge/app.py` | Event translation & Kafka bridge |
| **Consumer Service** | `/services/intelligence-consumer/src/main.py` | Kafka event consumer |
| **LangExtract** | `/services/langextract/app.py` | Code extraction & relationships |
| **Shared Models** | `/shared/models/` | Unified data contracts |
| **Handlers** | `/services/intelligence/src/handlers/` | 20+ event handlers |
| **Pattern Learning** | `/services/intelligence/src/archon_services/pattern_learning/` | 4-phase pattern engine |

## Critical Entry Points

```python
# Intelligence Consumer (Kafka → Intelligence)
from services.intelligence-consumer.src.main import IntelligenceConsumerService

# Intelligence APIs (REST)
from services.intelligence.app import FastAPI app

# Search Service (Hybrid search)
from services.search.app import FastAPI app with HybridSearchOrchestrator

# Bridge Service (PostgreSQL ↔ Memgraph)
from services.bridge.app import FastAPI app with MemgraphConnector

# Shared Models (Data contracts)
from shared.models import EntityType, BaseEntity, BaseRelationship
```

## Key Classes

### Handlers (All inherit BaseResponsePublisher)
- `QualityAssessmentHandler` - Quality scoring + ONEX validation
- `PatternLearningHandler` - Pattern matching
- `DocumentProcessingHandler` - Entity extraction
- `PerformanceHandler` - Performance optimization
- `FreshnessHandler` - Document freshness
- `PatternTraceabilityHandler` - Lineage tracking
- `CodegenValidationHandler` - Codegen validation
- `AutonomousLearningHandler` - Autonomous patterns

### Services
- `HybridSearchOrchestrator` - Multi-mode search coordination
- `MemgraphConnector` - Knowledge graph access
- `QualityScorer` - Quality assessment engine
- `DocumentFreshnessMonitor` - Freshness tracking
- `PatternLearningService` - Pattern matching & scoring

### Models
- `EntityType` - 15+ entity type enum
- `BaseEntity` - Standard entity model
- `Pattern` - Pattern representation
- `QualityScore` - Quality assessment results
- `FreshnessAnalysis` - Freshness metrics

## Databases

| Database | Port | Purpose | Collections/Tables |
|----------|------|---------|-------------------|
| **Qdrant** | 6333 | Vector search | archon_vectors, quality_vectors |
| **Memgraph** | 7687 | Knowledge graph | NODE types: DOCUMENT, ENTITY, PATTERN, PROJECT |
| **PostgreSQL** | 5436 | Patterns (remote) | patterns, pattern_executions, lineage_tracking |
| **Valkey** | 6379 | Cache | research:*, pattern:*, entity:*, embedding:* |

## Kafka Topics (Format: `dev.archon-intelligence.{domain}.{action}.v1`)

| Topic | Producers | Consumers | Purpose |
|-------|-----------|-----------|---------|
| `enrichment.requested.v1` | Bridge | Consumer | Document enrichment |
| `code-analysis.requested.v1` | Bridge | Consumer | Code analysis |
| `quality.assessed.v1` | Intelligence | Analytics | Quality assessment |
| `pattern.matched.v1` | Intelligence | Analytics | Pattern matching |
| `tree.discover.v1` | OmniNode | Intelligence | Tree discovery |
| `tree.index.v1` | OmniNode | Bridge | Tree indexing |
| `stamping.generate.v1` | OmniNode | Intelligence | ONEX stamping |

## APIs by Domain

### Quality Assessment (6 APIs)
- `POST /assess/code` → Quality score + ONEX compliance
- `POST /assess/document` → Document quality
- `POST /patterns/extract` → Pattern detection
- `POST /compliance/check` → Architectural compliance
- `POST /quality/evaluate` → Quality evaluation
- `POST /quality/bulk-assess` → Bulk assessment

### Pattern Learning (7 APIs)
- `POST /api/pattern-learning/pattern/match` → Pattern matching
- `POST /api/pattern-learning/hybrid/score` → Hybrid scoring
- `POST /api/pattern-learning/semantic/analyze` → Semantic analysis
- `GET /api/pattern-learning/metrics` → Metrics
- `GET /api/pattern-learning/cache/stats` → Cache stats
- `POST /api/pattern-learning/cache/clear` → Clear cache
- `GET /api/pattern-learning/health` → Health check

### Search (7 APIs)
- `POST /search` → Hybrid search
- `GET /search` → Quick search
- `POST /search/patterns` → Pattern search
- `POST /search/relationships` → Relationship search
- `GET /search/similar/{id}` → Similar entities
- `GET /search/related/{id}` → Related entities
- `GET /search/path/{src}/{tgt}` → Shortest path

### Vectorization
- `POST /vectorize/document` → Index document
- `POST /search/index/refresh` → Refresh index
- `GET /cache/stats` → Cache statistics
- `POST /cache/invalidate` → Invalidate cache

## Event Flow

```
Kafka Message
    ↓ [enrichment/code-analysis/manifest-intelligence]
    ├→ EnrichmentConsumer.consume_loop()
    │  ├→ _process_enrichment_event()
    │  │  ├→ Batch processing (files array)
    │  │  └→ Individual file processing
    │  ├→ _process_code_analysis_event()
    │  └→ _process_manifest_intelligence_event()
    ├→ DocumentProcessingHandler
    ├→ QualityAssessmentHandler
    ├→ PatternLearningHandler
    ├→ VectorizationHandler
    └→ Publish completion/error events
```

## Configuration Variables

### Service URLs
```bash
INTELLIGENCE_SERVICE_URL=http://localhost:8053
SEARCH_SERVICE_URL=http://localhost:8055
BRIDGE_SERVICE_URL=http://localhost:8054
```

### Databases
```bash
MEMGRAPH_URI=bolt://memgraph:7687
QDRANT_URL=http://qdrant:6333
POSTGRES_URL=postgresql://user:pass@host:5436/omninode_bridge
REDIS_URL=redis://archon-valkey:6379
```

### Event Bus
```bash
# Docker services
KAFKA_BOOTSTRAP_SERVERS=omninode-bridge-redpanda:9092
# Host scripts
KAFKA_BOOTSTRAP_SERVERS=192.168.86.200:29092
```

## Common Patterns

### Error Handling
```python
try:
    result = await process_event(event)
except ErrorClassifier.NonRetryable:
    await publish_to_dlq(event, e)  # No retry
except Exception:
    await publish_to_dlq(event, e, retry_count)  # With retry
```

### Async Batch Processing
```python
tasks = [process_single_item(item) for item in items]
results = await asyncio.gather(*tasks, return_exceptions=False)
successes = [r for r in results if r.success]
```

### Cache-Aside Pattern
```python
cached = await cache.get(f"key:{id}")
if cached: return cached
entity = await db.get(id)
await cache.set(f"key:{id}", entity, ttl=300)
return entity
```

## Health Checks

```bash
# Service Health
curl http://localhost:8053/health          # Intelligence
curl http://localhost:8055/health          # Search
curl http://localhost:8054/health          # Bridge

# Component Health
curl http://localhost:8053/api/pattern-learning/health
curl http://localhost:8053/api/pattern-traceability/health
curl http://localhost:8054/health/producer
```

## Testing Entry Points

```python
# Test quality assessment
POST /assess/code
{
    "file_path": "src/main.py",
    "content": "def foo(): pass",
    "language": "python",
    "project_name": "test"
}

# Test pattern matching
POST /api/pattern-learning/pattern/match
{
    "code_snippet": "class MyClass: ...",
    "project_name": "test",
    "context": {"language": "python"}
}

# Test search
POST /search
{
    "query": "authentication logic",
    "mode": "HYBRID",
    "limit": 20
}
```

## Migration Checklist

- [ ] Review full inventory document
- [ ] Map all service dependencies
- [ ] Identify blocking components
- [ ] Set up local test environment
- [ ] Create detailed migration plan
- [ ] Begin Phase 1 (Foundation)
- [ ] Establish monitoring/metrics
- [ ] Set up CI/CD pipeline
- [ ] Create integration tests
- [ ] Plan production deployment

---

**Quick Reference Version**: 1.0
**Last Updated**: 2025-11-14
**For Details**: See OMNIARCHON_MIGRATION_INVENTORY.md
