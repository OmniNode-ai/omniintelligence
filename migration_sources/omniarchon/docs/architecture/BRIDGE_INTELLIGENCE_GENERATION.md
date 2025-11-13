# Bridge Intelligence Generation API

**Version**: 1.0.0
**Status**: Implemented
**API Endpoint**: `POST /api/bridge/generate-intelligence`

## Overview

The Bridge Intelligence Generation API generates **OmniNode Tool Metadata Standard v0.1** compliant metadata enriched with Archon intelligence from multiple sources. This API provides the intelligence layer for the Bridge Metadata Stamping Service.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Bridge Intelligence API                       │
│                  (POST /api/bridge/generate-intelligence)        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ LangExtract  │  │QualityScorer │  │  Pattern     │
    │   (8156)     │  │  (Internal)  │  │  Tracking    │
    │              │  │              │  │  (Database)  │
    └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
           │                 │                  │
           │  Semantic       │  ONEX           │  Usage
           │  Analysis       │  Compliance     │  Analytics
           │                 │                  │
           └─────────────────┴──────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │   OmniNode-Compliant         │
              │   Metadata with Archon       │
              │   Intelligence Enrichment    │
              └──────────────────────────────┘
```

## Intelligence Sources

### 1. LangExtract (Semantic Analysis)

**Service**: http://archon-langextract:8156
**Performance Target**: <500ms

**Provides**:
- **Concepts**: Semantic concepts extracted from code (e.g., "authentication", "api_endpoint")
- **Themes**: High-level themes (e.g., "api_security", "data_processing")
- **Domains**: Domain classifications (e.g., "api_design", "security")
- **Patterns**: Semantic patterns (e.g., "best-practice", "workflow")

**Example Output**:
```json
{
  "concepts": [
    {"concept": "authentication", "score": 0.92, "context": "security"},
    {"concept": "user_management", "score": 0.87, "context": "api_design"}
  ],
  "themes": [
    {"theme": "api_security", "weight": 0.85, "related_concepts": ["authentication", "authorization"]}
  ],
  "domains": [
    {"domain": "api_design", "confidence": 0.91, "subdomain": "security"}
  ],
  "patterns": [
    {"pattern_type": "best-practice", "description": "JWT authentication", "strength": 0.88}
  ]
}
```

### 2. QualityScorer (ONEX Compliance)

**Component**: Internal scoring system
**Performance Target**: <200ms

**Provides**:
- **Quality Score** (0-1): Overall code quality assessment
- **ONEX Compliance** (0-1): Architectural compliance with ONEX patterns
- **Complexity Score** (0-1): Cyclomatic and cognitive complexity assessment
- **Maintainability Score** (0-1): Code structure and readability
- **Documentation Score** (0-1): Documentation coverage and quality
- **Temporal Relevance** (0-1): Freshness and modernity of code patterns

**Scoring Dimensions**:
```
Quality Score = Weighted Average of:
  - Complexity (20%)
  - Maintainability (20%)
  - Documentation (15%)
  - Temporal Relevance (15%)
  - Pattern Compliance (15%)
  - Architectural Compliance (15%)
```

**ONEX Compliance Checks**:
- ❌ Critical Failures: Any type usage, wildcard imports, direct instantiation
- ⚠️  Moderate Issues: camelCase functions, global variables, direct OS imports
- ✅ Modern Patterns: Dependency injection, protocols, proper exceptions

### 3. Pattern Tracking (Usage Analytics)

**Database**: PostgreSQL (pattern_lineage_nodes table)
**Performance Target**: <500ms

**Provides**:
- **Pattern Count**: Number of patterns tracked for the file
- **Total Executions**: Pattern usage count
- **Avg Quality Score**: Average pattern quality from historical data
- **Last Modified**: Last pattern modification timestamp
- **Pattern Types**: Types of patterns tracked (code, config, template, workflow)

**Example Output**:
```json
{
  "pattern_count": 5,
  "total_executions": 42,
  "avg_quality_score": 0.87,
  "last_modified": "2025-10-06T12:00:00Z",
  "pattern_types": ["code", "template"]
}
```

## API Specification

### Endpoint

```
POST /api/bridge/generate-intelligence
```

### Request Schema

```json
{
  "file_path": "string (required)",
  "content": "string (optional)",
  "include_patterns": "boolean (default: true)",
  "include_compliance": "boolean (default: true)",
  "include_semantic": "boolean (default: true)",
  "min_confidence": "float (default: 0.7, range: 0.0-1.0)"
}
```

**Field Descriptions**:
- `file_path`: Full path to file to analyze
- `content`: Optional file content (if not provided, will attempt to read from `file_path`)
- `include_patterns`: Include pattern tracking intelligence enrichment
- `include_compliance`: Include ONEX architectural compliance analysis
- `include_semantic`: Include LangExtract semantic analysis
- `min_confidence`: Minimum confidence threshold for semantic results

### Response Schema

```json
{
  "success": "boolean",
  "metadata": {
    "metadata_version": "0.1",
    "name": "string",
    "namespace": "string",
    "version": "string",
    "entrypoint": "string",
    "protocols_supported": ["string"],
    "classification": {
      "maturity": "alpha|beta|stable|production",
      "trust_score": "integer (0-100)"
    },
    "quality_metrics": {
      "quality_score": "float (0-1)",
      "onex_compliance": "float (0-1)",
      "complexity_score": "float (0-1)",
      "maintainability_score": "float (0-1)",
      "documentation_score": "float (0-1)",
      "temporal_relevance": "float (0-1)"
    },
    "semantic_intelligence": {
      "concepts": [{"concept": "string", "score": "float", "context": "string"}],
      "themes": [{"theme": "string", "weight": "float", "related_concepts": ["string"]}],
      "domains": [{"domain": "string", "confidence": "float", "subdomain": "string"}],
      "patterns": [{"pattern_type": "string", "description": "string", "strength": "float"}],
      "processing_time_ms": "float"
    },
    "pattern_intelligence": {
      "pattern_count": "integer",
      "total_executions": "integer",
      "avg_quality_score": "float",
      "last_modified": "string (ISO datetime)",
      "pattern_types": ["string"]
    },
    "title": "string",
    "description": "string",
    "type": "string",
    "language": "string",
    "tags": ["string"],
    "author": "string"
  },
  "processing_metadata": {
    "processing_time_ms": "float",
    "timestamp": "string (ISO datetime)",
    "file_size_bytes": "integer",
    "language": "string"
  },
  "intelligence_sources": ["string"],
  "recommendations": ["string"],
  "error": "string (if success=false)"
}
```

## OmniNode Protocol Compliance

### Required Fields (Per OmniNode Spec v0.1)

✅ `metadata_version`: Metadata standard version (default: "0.1")
✅ `name`: Tool/component name (extracted from filename)
✅ `namespace`: Namespace (default: "omninode.archon.intelligence")
✅ `version`: Semantic version (default: "1.0.0")
✅ `entrypoint`: Entry point file path (from request)
✅ `protocols_supported`: Supported protocols (default: ["O.N.E. v0.1"])

### Classification Fields (Archon-Enriched)

**Maturity Level**:
- **production**: quality >= 0.9 AND onex_compliance >= 0.9
- **stable**: quality >= 0.8 AND onex_compliance >= 0.8
- **beta**: quality >= 0.6 AND onex_compliance >= 0.6
- **alpha**: quality < 0.6 OR onex_compliance < 0.6

**Trust Score**:
- Calculated as: `quality_score * 100`
- Range: 0-100
- Higher scores indicate higher trust and quality

## Usage Examples

### Example 1: Basic Usage

```bash
curl -X POST http://localhost:8053/api/bridge/generate-intelligence \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/file.py",
    "content": "def example():\n    pass",
    "include_patterns": true,
    "include_compliance": true,
    "include_semantic": true
  }'
```

### Example 2: Python Client

```python
import httpx
import asyncio

async def generate_intelligence():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8053/api/bridge/generate-intelligence",
            json={
                "file_path": "/path/to/file.py",
                "content": "def example():\n    pass",
                "include_patterns": True,
                "include_compliance": True,
                "include_semantic": True,
                "min_confidence": 0.7
            }
        )
        return response.json()

result = asyncio.run(generate_intelligence())
print(f"Trust Score: {result['metadata']['classification']['trust_score']}")
print(f"Quality Score: {result['metadata']['quality_metrics']['quality_score']}")
```

### Example 3: With Pattern Intelligence Only

```bash
curl -X POST http://localhost:8053/api/bridge/generate-intelligence \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/file.py",
    "include_patterns": true,
    "include_compliance": false,
    "include_semantic": false
  }'
```

## Performance

### Targets

| Component | Target | Typical |
|-----------|--------|---------|
| Complete Generation | <2000ms | ~1200ms |
| LangExtract Analysis | <500ms | ~250ms |
| Quality Scoring | <200ms | ~150ms |
| Pattern Queries | <500ms | ~200ms |

### Optimization

The API automatically handles:
- **Parallel Intelligence Gathering**: All sources queried concurrently
- **Graceful Degradation**: Continues if individual sources fail
- **Optional Components**: Can disable semantic/compliance/pattern intelligence
- **Connection Pooling**: Database connections reused efficiently

## Health & Monitoring

### Health Check

```bash
GET /api/bridge/health
```

**Response**:
```json
{
  "status": "healthy|degraded|unhealthy",
  "service": "bridge-intelligence",
  "components": {
    "generator": "operational",
    "langextract": "operational",
    "langextract_url": "http://archon-langextract:8156",
    "quality_scorer": "operational",
    "pattern_tracking_db": "operational|unavailable"
  },
  "response_time_ms": 15.23,
  "timestamp": "2025-10-06T12:00:00Z"
}
```

### Capabilities

```bash
GET /api/bridge/capabilities
```

Returns detailed information about:
- Available intelligence sources
- Supported file types/languages
- Performance targets
- Protocol version compliance
- Maturity level mappings

## Integration with Bridge Service

### Workflow

1. **Bridge Service** receives file for stamping
2. **Bridge Service** calls Bridge Intelligence API
3. **Archon Intelligence Service** gathers intelligence from multiple sources
4. **Archon** returns OmniNode-compliant metadata with enrichment
5. **Bridge Service** stamps file with metadata using BLAKE3 hash

### Example Integration

```python
# Bridge Service code
async def stamp_file(file_path: str, content: str):
    # Step 1: Generate intelligence
    intelligence_response = await call_archon_intelligence_api(
        file_path=file_path,
        content=content
    )

    metadata = intelligence_response["metadata"]

    # Step 2: Stamp file with metadata
    stamped_file = await stamp_with_metadata(
        file_path=file_path,
        content=content,
        metadata=metadata,
        hash_algorithm="blake3"
    )

    return stamped_file
```

## Error Handling

### Common Errors

**503 Service Unavailable**:
- LangExtract service is down
- Database connection unavailable
- Service is initializing

**500 Internal Server Error**:
- Intelligence generation failed
- Quality scoring error
- Semantic analysis timeout

**400 Bad Request**:
- Invalid file_path
- Invalid min_confidence value
- Malformed request

### Graceful Degradation

The API continues to work even if individual components fail:

- **LangExtract unavailable**: Returns metadata without semantic intelligence
- **Database unavailable**: Returns metadata without pattern intelligence
- **Quality scorer error**: Uses default quality scores

## Testing

### Test Script

```bash
cd services/intelligence
python3 test_bridge_intelligence_api.py
```

**Tests**:
1. ✅ Health check validation
2. ✅ Capabilities endpoint
3. ✅ Intelligence generation with sample code
4. ✅ OmniNode protocol compliance validation
5. ✅ Quality metrics validation
6. ✅ Semantic intelligence validation

### Manual Testing

```bash
# Test with simple Python file
curl -X POST http://localhost:8053/api/bridge/generate-intelligence \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/test/simple.py",
    "content": "def hello():\n    print(\"Hello World\")"
  }' | jq
```

## Recommendations

The API provides intelligent recommendations based on quality metrics:

- **Documentation < 0.6**: "Consider adding more comprehensive documentation"
- **Complexity < 0.6**: "Consider reducing cyclomatic complexity"
- **Maintainability < 0.6**: "Consider improving code structure"
- **ONEX Compliance < 0.7**: "Consider improving ONEX compliance"
- **Temporal Relevance < 0.5**: "Code appears outdated - consider updating"

## Future Enhancements

1. **Real-time Pattern Updates**: Subscribe to pattern changes via WebSocket
2. **Historical Trend Analysis**: Show quality score trends over time
3. **AI-Powered Recommendations**: Use LLM to generate specific fix recommendations
4. **Cross-File Intelligence**: Analyze dependencies and related files
5. **Performance Profiling**: Add runtime performance data to intelligence

## References

- **OmniNode Tool Metadata Standard v0.1**: `/Volumes/PRO-G40/Code/Archive/ai-dev/docs/protocol/omninode_tool_metadata_standard_v0_1.md`
- **Bridge Integration Docs**: `docs/implementation/integrations/OMNINODE_BRIDGE_INTEGRATION.md`
- **LangExtract Client**: `services/intelligence/src/services/pattern_learning/phase2_matching/client_langextract_http.py`
- **Quality Scorer**: `services/intelligence/scoring/quality_scorer.py`

---

**Archon Intelligence Service**: Production intelligence provider for AI-driven development via MCP.
