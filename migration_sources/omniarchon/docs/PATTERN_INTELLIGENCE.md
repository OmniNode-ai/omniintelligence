# Pattern Intelligence Integration

**Version**: 1.0.0
**Date**: 2025-10-31
**Status**: Production Ready
**Collection**: `archon_vectors` (Qdrant)

## Overview

### Purpose
Pattern intelligence enables intelligent manifest injection in OmniClaude by providing semantic access to ~1000 code and execution patterns indexed in the `archon_vectors` collection. This system allows AI coding assistants to discover and apply proven implementation patterns, ONEX architectural templates, and best practices dynamically during development.

### Architecture
```
┌─────────────────────────────────────────────────────────┐
│                  OMNICLAUDE REQUEST                     │
│  "Need authentication pattern for microservice"         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│              PATTERN INTELLIGENCE LAYER                 │
│  • Semantic search across ~1000 patterns               │
│  • Filter by pattern_type, node_type, confidence       │
│  • Rank by quality_score + onex_compliance             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│                 ARCHON VECTORS (QDRANT)                 │
│  Collection: archon_vectors                             │
│  • Embedding size: 1536 (OpenAI text-embedding-3-large)│
│  • Total patterns: ~976 indexed                         │
│  • Code patterns: ~856 (Python implementations)        │
│  • Execution patterns: ~120 (ONEX templates)           │
└─────────────────────────────────────────────────────────┘
```

### Scale
- **Total Patterns**: ~976 patterns indexed
- **Code Patterns**: ~856 Python implementations (from omniclaude codebase)
- **Execution Patterns**: ~120 ONEX architectural templates
- **Embedding Model**: OpenAI `text-embedding-3-large` (1536 dimensions)
- **Storage**: Qdrant vector database with semantic search

### Key Benefits
1. **Dynamic Pattern Discovery**: Find relevant patterns without hardcoded catalog
2. **Semantic Search**: Natural language queries ("authentication with JWT")
3. **Quality Filtering**: Filter by quality_score, onex_compliance thresholds
4. **Multi-Dimensional**: Filter by pattern_type, node_type, concepts, themes
5. **Manifest Injection**: Automatically inject patterns into OmniClaude context

---

## Schema

### Pattern-Enhanced Fields

The `archon_vectors` collection includes 8 pattern intelligence fields that enable comprehensive pattern search and filtering:

| Field | Type | Description | Example Values | Required |
|-------|------|-------------|----------------|----------|
| `quality_score` | `float` | Code quality assessment (0.0-1.0) | `0.87` | No |
| `onex_compliance` | `float` | ONEX compliance score (0.0-1.0) | `0.92` | No |
| `onex_type` | `str` | ONEX node type | `"compute"`, `"effect"`, `"reducer"`, `"orchestrator"` | No |
| `concepts` | `List[str]` | Extracted semantic concepts | `["authentication", "jwt", "security"]` | No |
| `themes` | `List[str]` | High-level themes | `["backend", "api", "microservices"]` | No |
| `relative_path` | `str` | Path within project | `"src/services/auth.py"` | No |
| `project_name` | `str` | Source project identifier | `"omniclaude"`, `"omniarchon"` | No |
| `content_hash` | `str` | BLAKE3 hash for deduplication | `"blake3_abcdef123456..."` | No |

### Field Constraints

**Quality Scores** (validated at model level):
```python
quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
onex_compliance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
```

**ONEX Types** (enumerated):
- `effect` - External I/O operations (APIs, DB, files)
- `compute` - Pure transformations/algorithms
- `reducer` - Aggregation/persistence logic
- `orchestrator` - Workflow coordination

**Arrays** (unlimited length, stored as-is):
```python
concepts: Optional[List[str]] = Field(default=None)
themes: Optional[List[str]] = Field(default=None)
```

### Backward Compatibility

✅ **All fields are optional** with `Optional[]` typing and `default=None`:
- Existing vectors without pattern fields continue to work
- No migration required for legacy data
- Graceful degradation when fields missing

---

## API Usage

### Base Endpoints

**Search Service**: `http://localhost:8055`
**Intelligence Service**: `http://localhost:8053`

### 1. Search Patterns (POST /search)

**Basic Pattern Search**:
```bash
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication with JWT tokens",
    "mode": "hybrid",
    "limit": 10,
    "include_content": true
  }' | jq '.results[] | {
    title,
    quality_score,
    onex_type,
    concepts,
    relevance_score
  }'
```

**Response**:
```json
{
  "query": "authentication with JWT tokens",
  "mode": "hybrid",
  "total_results": 8,
  "returned_results": 8,
  "results": [
    {
      "entity_id": "/path/to/omniclaude/src/auth/jwt_handler.py",
      "entity_type": "page",
      "title": "jwt_handler.py",
      "content": "class JWTHandler:\n    def validate_token(self, token: str) -> dict:\n        ...",
      "relevance_score": 0.94,
      "quality_score": 0.87,
      "onex_compliance": 0.92,
      "onex_type": "compute",
      "concepts": ["authentication", "jwt", "security", "tokens"],
      "themes": ["backend", "api", "microservices"],
      "relative_path": "src/auth/jwt_handler.py",
      "project_name": "omniclaude"
    }
  ],
  "search_time_ms": 125.4
}
```

### 2. Filter by Pattern Type

**Search ONEX Effect Patterns Only**:
```bash
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection pool",
    "mode": "hybrid",
    "filters": {
      "onex_type": "effect"
    },
    "limit": 5
  }'
```

**Available Filters**:
```json
{
  "filters": {
    "onex_type": "compute",           // Exact match
    "quality_score": {"gte": 0.8},    // Range query
    "onex_compliance": {"gte": 0.9},  // Range query
    "project_name": "omniclaude",     // Exact match
    "concepts": "authentication",     // Array contains
    "themes": "backend"               // Array contains
  }
}
```

### 3. Filter by Node Types

**Search for Multiple ONEX Types**:
```bash
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "async workflow coordination",
    "mode": "semantic",
    "filters": {
      "onex_type": ["orchestrator", "reducer"]
    },
    "limit": 10
  }'
```

### 4. Filter by Minimum Confidence

**High-Quality Patterns Only**:
```bash
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "error handling patterns",
    "mode": "hybrid",
    "filters": {
      "quality_score": {"gte": 0.85},
      "onex_compliance": {"gte": 0.90}
    },
    "limit": 20,
    "include_content": true
  }' | jq '.results | length'
```

### 5. Combined Filters (Advanced)

**Complex Multi-Filter Query**:
```bash
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "real-time data processing pipeline",
    "mode": "hybrid",
    "filters": {
      "onex_type": "orchestrator",
      "quality_score": {"gte": 0.8},
      "onex_compliance": {"gte": 0.85},
      "themes": "backend",
      "project_name": "omniarchon"
    },
    "limit": 10,
    "semantic_threshold": 0.75
  }'
```

---

## Pattern Distribution

### By Pattern Type

| Pattern Type | Count | Percentage | Source |
|-------------|-------|------------|--------|
| **Code Patterns** | ~856 | 87.7% | omniclaude Python implementations |
| **Execution Patterns** | ~120 | 12.3% | ONEX architectural templates |
| **Total** | **~976** | 100% | Combined |

### By ONEX Node Type

| ONEX Type | Count | Description | Use Cases |
|-----------|-------|-------------|-----------|
| `compute` | ~340 | Pure transformations | Algorithms, parsers, validators |
| `effect` | ~285 | External I/O | API clients, DB adapters, file I/O |
| `orchestrator` | ~195 | Workflow coordination | Multi-step processes, pipelines |
| `reducer` | ~156 | Aggregation logic | Data consolidation, state management |

### By Quality Score

| Quality Range | Count | Percentage |
|--------------|-------|------------|
| 0.90 - 1.00 (Excellent) | ~245 | 25.1% |
| 0.80 - 0.89 (Good) | ~387 | 39.7% |
| 0.70 - 0.79 (Fair) | ~294 | 30.1% |
| 0.00 - 0.69 (Poor) | ~50 | 5.1% |

### By Source Project

| Project | Pattern Count | Type Distribution |
|---------|--------------|-------------------|
| omniclaude | ~856 | Code patterns (Python) |
| omniarchon | ~120 | ONEX templates (architectural) |

---

## Ingestion Process

### 1. Pattern Extraction

**Source**: Python codebases (omniclaude, omniarchon)

```bash
# Extract patterns from repository
python3 scripts/bulk_ingest_repository.py /path/to/omniclaude \
  --project-name omniclaude \
  --kafka-servers 192.168.86.200:29092 \
  --extract-patterns
```

**Extraction Pipeline**:
```
File Content
    ↓
┌────────────────────────────────────┐
│  1. AST Analysis                   │
│     • Parse Python AST             │
│     • Extract functions/classes    │
└────────────────┬───────────────────┘
                 ↓
┌────────────────────────────────────┐
│  2. Semantic Analysis              │
│     • Identify concepts            │
│     • Extract themes               │
│     • Detect patterns              │
└────────────────┬───────────────────┘
                 ↓
┌────────────────────────────────────┐
│  3. Quality Assessment             │
│     • Calculate quality_score      │
│     • Assess ONEX compliance       │
│     • Classify ONEX type           │
└────────────────┬───────────────────┘
                 ↓
┌────────────────────────────────────┐
│  4. Pattern Object                 │
│     • Metadata enrichment          │
│     • BLAKE3 hash generation       │
│     • Ready for indexing           │
└────────────────────────────────────┘
```

### 2. Embedding Generation

**Model**: OpenAI `text-embedding-3-large`
**Dimensions**: 1536
**Input Format**:
```python
embedding_text = f"""
Path: {file_path}
Summary: {summary}
Concepts: {', '.join(concepts[:10])}
Themes: {', '.join(themes[:10])}
ONEX Type: {onex_type}
Content: {code_snippet[:2000]}
"""
```

**Generation Process**:
```python
import openai

response = await openai.embeddings.create(
    model="text-embedding-3-large",
    input=embedding_text,
    dimensions=1536
)

embedding = response.data[0].embedding  # 1536-dimensional vector
```

### 3. Qdrant Indexing

**Collection**: `archon_vectors`
**Vector Config**:
```python
from qdrant_client.models import VectorParams, Distance

config = VectorParams(
    size=1536,                    # OpenAI text-embedding-3-large
    distance=Distance.COSINE      # Cosine similarity for semantic search
)
```

**Indexing Payload**:
```python
payload = {
    # Core identification
    "entity_id": absolute_path,
    "entity_type": "page",
    "title": filename,
    "content": file_content[:100000],  # 100K chars max

    # Pattern intelligence fields
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "onex_type": "compute",
    "concepts": ["authentication", "jwt", "security"],
    "themes": ["backend", "api"],
    "relative_path": "src/auth/jwt_handler.py",
    "project_name": "omniclaude",
    "content_hash": "blake3_abcdef123456..."
}

qdrant_client.upsert(
    collection_name="archon_vectors",
    points=[PointStruct(
        id=generate_stable_id(absolute_path),
        vector=embedding,
        payload=payload
    )]
)
```

**Batch Performance**:
- **Batch Size**: 100 files
- **Processing Rate**: ~50ms per file
- **Total Time (1000 files)**: ~5 minutes

---

## Use Cases

### 1. Manifest Injection in OmniClaude

**Scenario**: User asks "How do I implement JWT authentication?"

**OmniClaude Workflow**:
```python
# 1. Extract intent
query = "JWT authentication implementation"

# 2. Search patterns
response = await search_patterns(
    query=query,
    filters={
        "quality_score": {"gte": 0.85},
        "concepts": "authentication"
    },
    limit=5
)

# 3. Inject into manifest
manifest = {
    "task": "implement_jwt_auth",
    "patterns": [
        {
            "source": result.relative_path,
            "content": result.content,
            "quality": result.quality_score,
            "concepts": result.concepts
        }
        for result in response.results
    ]
}

# 4. Generate code with pattern context
code = await generate_code_with_patterns(manifest)
```

### 2. ONEX Compliance Checking

**Scenario**: Validate that new code follows ONEX architecture

```python
# Search for similar ONEX patterns
patterns = await search_patterns(
    query=user_code_description,
    filters={
        "onex_compliance": {"gte": 0.9},
        "onex_type": detected_node_type
    },
    limit=10
)

# Compare user code against high-compliance patterns
compliance_report = {
    "user_onex_type": detected_node_type,
    "user_quality": calculate_quality(user_code),
    "reference_patterns": [
        {
            "path": p.relative_path,
            "onex_compliance": p.onex_compliance,
            "similarity": cosine_similarity(user_embedding, p.embedding)
        }
        for p in patterns
    ],
    "recommendations": generate_recommendations(patterns, user_code)
}
```

### 3. Code Pattern Discovery

**Scenario**: Developer needs error handling pattern for async operations

```bash
# Search for async error handling patterns
curl -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "async error handling with retries and exponential backoff",
    "mode": "hybrid",
    "filters": {
      "quality_score": {"gte": 0.8},
      "concepts": ["error-handling", "async"]
    },
    "limit": 5,
    "include_content": true
  }' | jq -r '.results[] | "\(.title)\nQuality: \(.quality_score)\nPath: \(.relative_path)\n---\n\(.content[:500])\n\n"'
```

### 4. Architectural Template Retrieval

**Scenario**: Need ONEX orchestrator pattern for multi-step workflow

```python
# Search for orchestrator patterns
templates = await search_patterns(
    query="multi-step async workflow with state management",
    filters={
        "onex_type": "orchestrator",
        "onex_compliance": {"gte": 0.85},
        "quality_score": {"gte": 0.80}
    },
    limit=3
)

# Generate scaffold from template
for template in templates:
    print(f"Template: {template.title}")
    print(f"ONEX Compliance: {template.onex_compliance:.2f}")
    print(f"Concepts: {', '.join(template.concepts)}")
    print(f"\nCode:\n{template.content}\n")
```

---

## Validation Examples

### 1. Check Pattern Count

**Verify Total Patterns Indexed**:
```bash
curl -s http://localhost:6333/collections/archon_vectors | \
  jq '.result.points_count'
```

**Expected Output**: `~976` (or more if additional patterns indexed)

### 2. Verify Pattern Distribution

**Check ONEX Type Distribution**:
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Scroll through all points and count by onex_type
distribution = {}
offset = None

while True:
    results, offset = client.scroll(
        collection_name="archon_vectors",
        limit=100,
        offset=offset
    )

    for point in results:
        onex_type = point.payload.get("onex_type", "unknown")
        distribution[onex_type] = distribution.get(onex_type, 0) + 1

    if offset is None:
        break

print("Pattern Distribution by ONEX Type:")
for onex_type, count in sorted(distribution.items(), key=lambda x: -x[1]):
    print(f"  {onex_type}: {count}")
```

### 3. Test Pattern Search API

**Search and Validate Results**:
```bash
#!/bin/bash

echo "Testing Pattern Search API..."

# Test 1: Basic search
echo "1. Basic pattern search"
curl -s -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "limit": 5}' | \
  jq '.total_results'

# Test 2: Filter by quality
echo "2. High-quality patterns (quality >= 0.85)"
curl -s -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pattern",
    "filters": {"quality_score": {"gte": 0.85}},
    "limit": 100
  }' | jq '.total_results'

# Test 3: Filter by ONEX type
echo "3. Compute patterns only"
curl -s -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "pattern",
    "filters": {"onex_type": "compute"},
    "limit": 100
  }' | jq '.total_results'

# Test 4: Combined filters
echo "4. High-quality compute patterns"
curl -s -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "data transformation",
    "filters": {
      "onex_type": "compute",
      "quality_score": {"gte": 0.8}
    },
    "limit": 10
  }' | jq '.results[] | {title, quality_score, onex_type}'

echo "✅ Pattern search validation complete"
```

### 4. Validate Embedding Dimensions

**Check Vector Dimensions**:
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Get collection info
collection_info = client.get_collection("archon_vectors")
print(f"Collection: archon_vectors")
print(f"Vector size: {collection_info.config.params.vectors.size}")
print(f"Distance metric: {collection_info.config.params.vectors.distance}")
print(f"Total points: {collection_info.points_count}")

# Sample a point to verify embedding
points = client.scroll(collection_name="archon_vectors", limit=1)[0]
if points:
    vector = points[0].vector
    print(f"\nSample vector dimensions: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")
    print(f"✅ Embedding validation passed")
```

### 5. Test Quality Filtering

**Verify Quality Score Filtering Works**:
```bash
# Compare results with and without quality filter
echo "Results without quality filter:"
curl -s -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "limit": 100}' | \
  jq '.total_results'

echo "Results with quality >= 0.9:"
curl -s -X POST http://localhost:8055/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication",
    "filters": {"quality_score": {"gte": 0.9}},
    "limit": 100
  }' | jq '.total_results'

# Should show fewer results with quality filter
```

---

## Performance Metrics

### Search Performance
- **Cold cache**: < 200ms
- **Warm cache**: < 50ms
- **Concurrent queries**: 100+ req/s

### Indexing Performance
- **Single file**: ~50ms
- **Batch (100 files)**: ~5s (50ms/file)
- **Full repository (1000 files)**: ~5 minutes

### Storage Metrics
- **Vector storage**: ~6KB per pattern (1536 float32 + payload)
- **Total storage (976 patterns)**: ~5.9MB
- **Payload overhead**: ~500 bytes per pattern (quality fields)

---

## Troubleshooting

### Issue: No results returned

**Check**:
1. Verify collection has patterns:
   ```bash
   curl http://localhost:6333/collections/archon_vectors | jq '.result.points_count'
   ```

2. Check filters aren't too restrictive:
   ```bash
   # Remove filters temporarily
   curl -X POST http://localhost:8055/search \
     -H "Content-Type: application/json" \
     -d '{"query": "your query", "limit": 10}'
   ```

### Issue: Low quality results

**Solutions**:
1. Increase quality threshold:
   ```json
   {"filters": {"quality_score": {"gte": 0.85}}}
   ```

2. Add ONEX compliance filter:
   ```json
   {"filters": {"onex_compliance": {"gte": 0.9}}}
   ```

3. Filter by specific ONEX type:
   ```json
   {"filters": {"onex_type": "compute"}}
   ```

### Issue: Slow search performance

**Optimizations**:
1. Check cache status:
   ```bash
   curl http://localhost:8055/cache/stats
   ```

2. Enable caching in `.env`:
   ```bash
   ENABLE_CACHE=true
   REDIS_URL=redis://archon-valkey:6379/0
   ```

3. Create payload indexes for frequent filters:
   ```python
   client.create_payload_index(
       collection_name="archon_vectors",
       field_name="quality_score",
       field_schema="float"
   )
   ```

---

## Related Documentation

- **Schema Details**: `ARCHON_VECTORS_SCHEMA_ENHANCEMENT.md`
- **Pattern Sync**: `PATTERN_SYNC_QUICKSTART.md`
- **Search Service**: `services/search/README.md`
- **Intelligence Service**: `services/intelligence/README.md`
- **ONEX Architecture**: `docs/onex/ONEX_PATTERNS.md`

---

**Last Updated**: 2025-10-31
**Maintainer**: Archon Intelligence Team
**Questions**: See `docs/FAQ.md` or raise an issue
