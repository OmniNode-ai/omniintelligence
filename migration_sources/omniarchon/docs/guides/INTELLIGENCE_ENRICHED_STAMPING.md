# Intelligence-Enriched Metadata Stamping

**Version**: 1.0.0
**Status**: Production Ready
**Last Updated**: 2025-10-06

## Overview

Integration of Archon Intelligence Generation with Bridge Metadata Stamping Client enables intelligence-enriched file stamping with OmniNode Tool Metadata Standard v0.1 compliant metadata.

### Key Features

- **Multi-Source Intelligence**: Combines LangExtract semantic analysis, QualityScorer ONEX compliance, and Pattern Tracking data
- **Protocol Compliance**: Generates OmniNode Tool Metadata Standard v0.1 compliant metadata
- **Graceful Fallback**: Continues with basic stamping if intelligence generation fails
- **Performance Optimized**: <3000ms end-to-end for intelligence + stamping (target: <2500ms)
- **Comprehensive Metrics**: Tracks intelligence requests, successes, failures, and enriched stamps

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          MCP Tools (Claude Code)                    │
│  • stamp_file_metadata (with use_intelligence)     │
│  • stamp_with_archon_intelligence (dedicated)      │
└──────────────────┬──────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────┐
│      MetadataStampingClient (Enhanced)              │
│  • generate_intelligence()                          │
│  • stamp_with_intelligence()                        │
│  • _flatten_intelligence_metadata()                 │
└──────────────────┬──────────────────────────────────┘
                   ↓
        ┌──────────┴───────────┐
        ↓                      ↓
┌────────────────────┐  ┌──────────────────────┐
│ Intelligence (8053)│  │ Stamping (8057)      │
│ • Semantic Analysis│  │ • Metadata Storage   │
│ • Quality Scoring  │  │ • BLAKE3 Hashing     │
│ • Pattern Intel    │  │ • Stamp Validation   │
└────────────────────┘  └──────────────────────┘
```

---

## Components

### 1. MetadataStampingClient (Enhanced)

**Location**: `/python/src/mcp_server/clients/metadata_stamping_client.py`

#### New Methods

**`generate_intelligence()`**
```python
async def generate_intelligence(
    file_path: str,
    content: Optional[str] = None,
    include_semantic: bool = True,
    include_compliance: bool = True,
    include_patterns: bool = True,
    min_confidence: float = 0.7,
) -> Dict[str, Any]
```

Calls Archon Intelligence API to generate enriched metadata.

**Returns**:
```json
{
  "success": true,
  "metadata": {
    "metadata_version": "0.1",
    "name": "example_module",
    "namespace": "omninode.archon.intelligence",
    "classification": {
      "maturity": "beta",
      "trust_score": 87
    },
    "quality_metrics": {
      "quality_score": 0.87,
      "onex_compliance": 0.92,
      "complexity_score": 0.75
    },
    "semantic_intelligence": { ... },
    "pattern_intelligence": { ... }
  },
  "intelligence_sources": ["langextract", "quality_scorer", "pattern_tracking"],
  "recommendations": ["Add more documentation", "Reduce complexity"]
}
```

**`stamp_with_intelligence()`**
```python
async def stamp_with_intelligence(
    file_path: str,
    file_hash: str,
    content: Optional[str] = None,
    overwrite: bool = False,
    include_semantic: bool = True,
    include_compliance: bool = True,
    include_patterns: bool = True,
    min_confidence: float = 0.7,
    fallback_on_intelligence_failure: bool = True,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> StampResult
```

Orchestrates intelligence generation + metadata enrichment + file stamping.

**Workflow**:
1. Generate intelligence via HTTP
2. Flatten OmniNodeToolMetadata structure
3. Enrich metadata Dict with intelligence
4. Stamp file with enriched metadata
5. Track metrics

**`_flatten_intelligence_metadata()`**
```python
def _flatten_intelligence_metadata(
    intelligence_metadata: Dict[str, Any]
) -> Dict[str, Any]
```

Converts nested OmniNodeToolMetadata to flat Dict for stamping.

#### New Constructor Parameters

```python
MetadataStampingClient(
    base_url: str = "http://omninode-bridge-metadata-stamping:8057",
    intelligence_url: str = "http://archon-intelligence:8053",  # NEW
    intelligence_timeout_seconds: float = 3.0,  # NEW
    ...
)
```

#### New Metrics

```python
{
    "intelligence_requests": 0,         # Total intelligence API calls
    "intelligence_successes": 0,        # Successful intelligence generations
    "intelligence_failures": 0,         # Failed intelligence generations
    "intelligence_enriched_stamps": 0,  # Stamps with intelligence enrichment
}
```

---

### 2. MCP Tools (Updated)

**Location**: `/python/src/mcp_server/features/intelligence/omninode_bridge_tools.py`

#### Tool: `stamp_file_metadata` (Updated)

**Parameters**:
```python
file_path: str                          # Absolute path to file
file_hash: str                          # BLAKE3 hash
custom_metadata: Optional[Dict] = None  # Additional metadata
overwrite: bool = False                 # Overwrite existing stamp
use_intelligence: bool = False          # NEW: Enable intelligence enrichment
```

**Usage**:
```python
# Basic stamping
result = await stamp_file_metadata(
    file_path="/path/to/file.py",
    file_hash="blake3_hash_here",
    custom_metadata={"project": "myproject"}
)

# Intelligence-enriched stamping
result = await stamp_file_metadata(
    file_path="/path/to/file.py",
    file_hash="blake3_hash_here",
    use_intelligence=True  # Enable intelligence enrichment
)
```

#### Tool: `stamp_with_archon_intelligence` (NEW)

**Parameters**:
```python
file_path: str                          # Absolute path to file
file_hash: str                          # BLAKE3 hash
content: Optional[str] = None           # Optional file content for analysis
include_semantic: bool = True           # Include semantic analysis
include_compliance: bool = True         # Include ONEX compliance
include_patterns: bool = True           # Include pattern intelligence
min_confidence: float = 0.7             # Min confidence for semantic results
overwrite: bool = False                 # Overwrite existing stamp
custom_metadata: Optional[Dict] = None  # Additional metadata
```

**Returns**:
```json
{
  "success": true,
  "file_path": "/path/to/file.py",
  "file_hash": "blake3_hash",
  "stamped_at": "2025-10-06T12:00:00Z",
  "processing_time_ms": 2450,
  "intelligence_metadata": {
    "omninode_metadata_version": "0.1",
    "omninode_namespace": "omninode.archon.intelligence",
    "omninode_protocols": ["O.N.E. v0.1"]
  },
  "quality_metrics": {
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "complexity_score": 0.75,
    "maintainability_score": 0.85,
    "documentation_score": 0.80,
    "temporal_relevance": 0.90
  },
  "classification": {
    "maturity": "beta",
    "trust_score": 87
  },
  "semantic_intelligence": {
    "concepts_count": 12,
    "themes_count": 3,
    "domains": ["data_processing", "validation"],
    "patterns_count": 5
  },
  "pattern_intelligence": {
    "pattern_count": 8,
    "pattern_executions": 42,
    "pattern_avg_quality": 0.85,
    "pattern_types": ["compute", "validation"]
  },
  "intelligence_sources": ["langextract", "quality_scorer", "pattern_tracking"],
  "recommendations": [
    "Consider adding more documentation",
    "Reduce cyclomatic complexity"
  ],
  "service_url": "http://omninode-bridge-metadata-stamping:8057"
}
```

---

## Usage Examples

### Example 1: Basic Intelligence Generation

```python
from src.mcp_server.clients.metadata_stamping_client import MetadataStampingClient

async with MetadataStampingClient(
    base_url="http://localhost:8057",
    intelligence_url="http://localhost:8053"
) as client:
    # Generate intelligence
    result = await client.generate_intelligence(
        file_path="/path/to/file.py",
        include_semantic=True,
        include_compliance=True,
        include_patterns=True,
    )

    if result["success"]:
        metadata = result["metadata"]
        quality = metadata["quality_metrics"]

        print(f"Quality Score: {quality['quality_score']}")
        print(f"ONEX Compliance: {quality['onex_compliance']}")
        print(f"Maturity: {metadata['classification']['maturity']}")
```

### Example 2: Intelligence-Enriched Stamping

```python
async with MetadataStampingClient() as client:
    # Stamp with intelligence enrichment
    result = await client.stamp_with_intelligence(
        file_path="/path/to/file.py",
        file_hash="blake3_hash_here",
        content=open("/path/to/file.py").read(),  # Optional
        overwrite=True,
        include_semantic=True,
        include_compliance=True,
        include_patterns=True,
    )

    print(f"Stamped with intelligence!")
    print(f"Quality Score: {result.metadata['quality_score']}")
    print(f"Trust Score: {result.metadata['trust_score']}/100")
```

### Example 3: MCP Tool Usage (Claude Code)

```python
# Basic stamping with intelligence flag
result = await stamp_file_metadata(
    file_path="python/src/example.py",
    file_hash="blake3_abc123...",
    use_intelligence=True
)

# Dedicated intelligence-enriched stamping
result = await stamp_with_archon_intelligence(
    file_path="python/src/example.py",
    file_hash="blake3_abc123...",
    include_semantic=True,
    include_compliance=True,
    include_patterns=True,
    min_confidence=0.7
)
```

### Example 4: Graceful Fallback

```python
# Intelligence fails, but stamping continues with basic metadata
result = await client.stamp_with_intelligence(
    file_path="/path/to/file.py",
    file_hash="blake3_hash",
    fallback_on_intelligence_failure=True,  # Enable fallback
)

# Check if fallback was used
if result.metadata.get("intelligence_error"):
    print(f"Fallback used: {result.metadata['intelligence_error']}")
else:
    print("Intelligence enrichment successful!")
```

---

## Error Handling

### Intelligence Generation Errors

**Timeout** (intelligence_timeout_seconds exceeded):
```json
{
  "success": false,
  "error": "Intelligence generation timed out after 3.0s",
  "intelligence_sources": []
}
```

**Service Unavailable**:
```json
{
  "success": false,
  "error": "Intelligence service returned 503",
  "intelligence_sources": []
}
```

**With Fallback Enabled**:
```python
# Intelligence fails, but stamping continues
result = await client.stamp_with_intelligence(
    file_path="/path/to/file.py",
    file_hash="hash",
    fallback_on_intelligence_failure=True,
)

# Check metadata
if result.metadata.get("intelligence_error"):
    # Fallback was used - basic metadata only
    print("Basic stamping applied")
else:
    # Intelligence succeeded
    print("Intelligence enrichment applied")
```

---

## Performance

### Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Intelligence Generation | <2000ms | ~1200ms |
| Basic Stamping | <100ms | ~50ms |
| Intelligence-Enriched Stamping | <2500ms | ~1400ms |
| Metadata Flattening | <10ms | ~2ms |

### Performance Breakdown

**Intelligence-Enriched Stamping (1400ms typical)**:
- Intelligence Generation: ~1200ms
  - LangExtract Semantic: ~500ms
  - QualityScorer: ~200ms
  - Pattern Queries: ~500ms
- Metadata Flattening: ~2ms
- Stamping: ~50ms
- Overhead: ~148ms

### Optimization Tips

1. **Use content parameter**: Pass file content directly to avoid file I/O
2. **Selective intelligence**: Disable unused intelligence sources
3. **Adjust min_confidence**: Higher thresholds = faster semantic analysis
4. **Batch operations**: Use batch_stamp for multiple files
5. **Cache results**: Intelligence results can be cached by file hash

---

## Testing

### Run Tests

```bash
# Run integration tests
cd python
python test_intelligence_stamping.py
```

### Test Coverage

1. **Intelligence Generation**: Verify API call and response parsing
2. **Basic Stamping**: Verify stamping without intelligence
3. **Intelligence-Enriched Stamping**: Verify complete workflow
4. **Client Metrics**: Verify metrics tracking
5. **Graceful Fallback**: Verify fallback behavior
6. **Error Handling**: Verify timeout and service unavailable handling

---

## Monitoring

### Metrics Available

```python
metrics = client.get_client_metrics()

{
    # Standard metrics
    "total_requests": 100,
    "successful_requests": 98,
    "failed_requests": 2,
    "success_rate": 0.98,
    "avg_duration_ms": 75.5,

    # Intelligence metrics
    "intelligence_requests": 50,
    "intelligence_successes": 48,
    "intelligence_failures": 2,
    "intelligence_enriched_stamps": 48,

    # Stamping metrics
    "total_stamps_created": 98,
    "batch_operations": 5,
}
```

### Health Checks

```python
# Check stamping service health
health = await client.check_health()

# Check intelligence service health
# (Add to client if needed)
```

---

## Migration Guide

### Migrating Existing Code

**Before** (Old API - BROKEN):
```python
result = await client.stamp_file(
    request=StampRequest(
        file_path=file_path,
        compliance_level="effect",
        metadata=custom_metadata
    )
)
```

**After** (Fixed + Intelligence):
```python
# Basic stamping (fixed)
result = await client.stamp_file(
    file_hash=calculate_hash(file_path),
    metadata={
        "file_path": file_path,
        **custom_metadata
    },
    overwrite=False
)

# Intelligence-enriched stamping (new)
result = await client.stamp_with_intelligence(
    file_path=file_path,
    file_hash=calculate_hash(file_path),
    additional_metadata=custom_metadata,
    overwrite=False
)
```

---

## Configuration

### Environment Variables

```bash
# Stamping service URL (Docker)
METADATA_STAMPING_URL=http://omninode-bridge-metadata-stamping:8057

# Intelligence service URL (Docker)
INTELLIGENCE_URL=http://archon-intelligence:8053

# Local development
METADATA_STAMPING_URL=http://localhost:8057
INTELLIGENCE_URL=http://localhost:8053
```

### Client Configuration

```python
client = MetadataStampingClient(
    base_url="http://localhost:8057",
    intelligence_url="http://localhost:8053",
    timeout_seconds=2.0,                    # Standard stamping timeout
    intelligence_timeout_seconds=3.0,       # Intelligence generation timeout
    max_retries=3,                          # Retry attempts
    circuit_breaker_enabled=False,          # Circuit breaker (disabled)
)
```

---

## Best Practices

### 1. Use Intelligence Selectively

```python
# High-value files (production code)
result = await client.stamp_with_intelligence(
    file_path="/src/core/engine.py",
    file_hash=hash,
    include_semantic=True,
    include_compliance=True,
    include_patterns=True,
)

# Low-value files (tests, configs)
result = await client.stamp_file(
    file_hash=hash,
    metadata={"file_path": path},
)
```

### 2. Handle Failures Gracefully

```python
# Always enable fallback for production
result = await client.stamp_with_intelligence(
    file_path=path,
    file_hash=hash,
    fallback_on_intelligence_failure=True,  # ✅ Always enable
)
```

### 3. Monitor Performance

```python
# Track metrics regularly
metrics = client.get_client_metrics()

if metrics["intelligence_failures"] / metrics["intelligence_requests"] > 0.1:
    logger.warning("High intelligence failure rate!")
```

### 4. Optimize for Performance

```python
# Pass content directly to avoid I/O
content = Path(file_path).read_text()

result = await client.stamp_with_intelligence(
    file_path=file_path,
    file_hash=hash,
    content=content,  # ✅ Avoid service file I/O
)
```

---

## Troubleshooting

### Intelligence Generation Fails

**Symptom**: `intelligence_error` in metadata

**Solutions**:
1. Check intelligence service health: `curl http://localhost:8053/api/bridge/health`
2. Verify LangExtract connectivity: `curl http://localhost:8156/health`
3. Check database connectivity for pattern intelligence
4. Review logs: `docker logs archon-intelligence`

### Timeout Errors

**Symptom**: `Intelligence generation timed out after 3.0s`

**Solutions**:
1. Increase timeout: `intelligence_timeout_seconds=5.0`
2. Reduce intelligence scope: `include_patterns=False`
3. Check service performance: Review processing_time_ms in logs

### Quality Scores Low

**Symptom**: quality_score < 0.5, onex_compliance < 0.6

**Review**:
- Check recommendations in response
- Review code against ONEX patterns
- Verify documentation completeness
- Check temporal relevance (outdated patterns)

---

## Future Enhancements

### Phase 2 (Planned)

1. **Caching Layer**: Cache intelligence results by file hash
2. **Async Intelligence**: Non-blocking intelligence generation
3. **Batch Intelligence**: Generate intelligence for multiple files in parallel
4. **Intelligence Versioning**: Track intelligence metadata versions
5. **Custom Intelligence Profiles**: Configurable intelligence sources per project

---

## References

- **OmniNode Tool Metadata Standard**: v0.1
- **Archon Intelligence API**: `POST /api/bridge/generate-intelligence`
- **Bridge Metadata Stamping**: `POST /api/v1/metadata-stamping/stamp`
- **LangExtract Service**: Semantic analysis provider
- **QualityScorer**: ONEX compliance assessment
- **Pattern Tracking**: Usage analytics and intelligence

---

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: 2025-10-06
