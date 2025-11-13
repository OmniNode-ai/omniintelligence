# ModelIntelligenceOutput - Quick Reference

## Import

```python
from intelligence.models import (
    ModelIntelligenceOutput,
    ModelPatternDetection,
    ModelIntelligenceMetrics,
)
from uuid import UUID, uuid4
```

## Basic Usage

### Success Response
```python
output = ModelIntelligenceOutput(
    success=True,
    operation_type="assess_code_quality",
    correlation_id=uuid4(),
    processing_time_ms=1234,
    quality_score=0.87,
    onex_compliance=0.92,
    issues=["Missing docstrings"],
    recommendations=["Add type hints"],
)
```

### Error Response
```python
error = ModelIntelligenceOutput.create_error(
    operation_type="assess_code_quality",
    correlation_id=uuid4(),
    processing_time_ms=150,
    error_code="INTELLIGENCE_SERVICE_TIMEOUT",
    error_message="Service timeout",
    retry_allowed=True,
)
```

### From API Response
```python
output = ModelIntelligenceOutput.from_api_response(
    api_response=api_data,
    operation_type="assess_code_quality",
    correlation_id=uuid4(),
    processing_time_ms=1234,
)
```

### Serialization
```python
result_dict = output.to_dict()  # JSON-serializable
json_str = json.dumps(result_dict)
```

## Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | `bool` | ✅ | Operation success status |
| `operation_type` | `str` | ✅ | Intelligence operation type |
| `correlation_id` | `UUID` | ✅ | Request correlation ID |
| `processing_time_ms` | `int` | ✅ | Processing time (ms) |
| `quality_score` | `Optional[float]` | ❌ | Quality score (0.0-1.0) |
| `onex_compliance` | `Optional[float]` | ❌ | ONEX compliance (0.0-1.0) |
| `complexity_score` | `Optional[float]` | ❌ | Complexity (0.0-1.0) |
| `issues` | `list[str]` | ❌ | Detected issues |
| `recommendations` | `list[str]` | ❌ | Improvement suggestions |
| `patterns` | `Optional[list]` | ❌ | Detected patterns |
| `error_code` | `Optional[str]` | ❌ | Error code |
| `error_message` | `Optional[str]` | ❌ | Error description |
| `retry_allowed` | `bool` | ❌ | Safe to retry |
| `metrics` | `Optional[ModelIntelligenceMetrics]` | ❌ | Execution metrics |

## Intelligence Operations

### Code Quality Assessment
**Operation**: `assess_code_quality`

**Returns**:
- `quality_score` (0.0-1.0)
- `onex_compliance` (0.0-1.0)
- `complexity_score` (0.0-1.0)
- `issues` (list)
- `recommendations` (list)
- `patterns` (list)

### RAG Intelligence Gathering
**Operation**: `perform_rag_query`

**Returns**:
- `result_data` (query results)
- `recommendations` (related patterns)
- `metrics` (service timing, cache stats)

### Performance Optimization
**Operation**: `identify_optimization_opportunities`

**Returns**:
- `recommendations` (ROI-ranked)
- `result_data` (opportunities with impact/effort)

## Error Codes

| Code | Retry? | Description |
|------|--------|-------------|
| `INTELLIGENCE_SERVICE_TIMEOUT` | ✅ | Service timeout |
| `INVALID_INPUT_SYNTAX` | ❌ | Malformed input |
| `ONEX_COMPLIANCE_FAILED` | ❌ | ONEX validation failed |
| `CACHE_CONNECTION_ERROR` | ✅ | Cache unavailable |
| `SERVICE_UNAVAILABLE` | ✅ | Backend service down |

## Pattern Detection

```python
pattern = ModelPatternDetection(
    pattern_type="architectural",
    pattern_name="ONEX_EFFECT_NODE",
    confidence=0.95,
    description="Proper Effect node implementation",
    location="src/nodes/effect/node_api_effect.py:42",
    severity="info",
    recommendation="Continue using this pattern",
)
```

**Pattern Types**:
- `architectural` - ONEX patterns
- `quality` - Code quality patterns
- `security` - Security issues
- `performance` - Performance patterns

**Severity Levels**:
- `info` - Informational
- `warning` - Requires attention
- `error` - Must fix
- `critical` - Urgent fix required

## Execution Metrics

```python
metrics = ModelIntelligenceMetrics(
    rag_service_ms=300,
    vector_service_ms=250,
    knowledge_service_ms=450,
    cache_hit=True,
    cache_key="research:rag:pattern_abc",
    services_invoked=["cache"],
    total_api_calls=1,
)
```

## Helper Methods

### to_dict()
Convert to JSON-serializable dictionary:
- UUIDs → strings
- datetime → ISO 8601
- Nested models → dicts

### from_api_response(api_response, operation_type, correlation_id, processing_time_ms)
Parse Intelligence Service API responses into typed models.

### create_error(operation_type, correlation_id, processing_time_ms, error_code, error_message, retry_allowed, metadata)
Create consistent error responses.

## Integration

**Intelligence Adapter Effect Node**:
```python
async def execute_effect(self, contract: ModelContractEffect) -> ModelIntelligenceOutput:
    # Implementation
    return ModelIntelligenceOutput(...)
```

**MCP Server Tool**:
```python
@tool
def assess_code_quality(...) -> dict:
    output = ModelIntelligenceOutput(...)
    return output.to_dict()
```

**Event Publishing**:
```python
event = ModelEventEnvelope(
    event_type="omninode.intelligence.response.quality_assessed.v1",
    correlation_id=output.correlation_id,
    payload=output.to_dict(),
)
```

## Files

- `model_intelligence_output.py` - Main contract (649 lines)
- `usage_examples.py` - Runnable examples (365 lines)
- `README.md` - Full documentation (289 lines)
- `DELIVERY_SUMMARY.md` - Complete delivery docs
- `QUICK_REFERENCE.md` - This file

## Location

```
/Volumes/PRO-G40/Code/omniarchon/python/src/intelligence/models/
```

## Test

```bash
# Import test
python -c "from intelligence.models import ModelIntelligenceOutput; print('✅ Success')"

# Run examples
python usage_examples.py
```
