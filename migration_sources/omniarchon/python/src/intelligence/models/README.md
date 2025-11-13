# Intelligence Models

Domain models for Intelligence Adapter Effect Node operations, including configuration and output contracts.

## Overview

This package provides strongly-typed Pydantic models for all Intelligence Service operations, ensuring consistent configuration and response structure across:

- Code quality assessment
- ONEX compliance validation
- Performance optimization identification
- RAG intelligence gathering
- Document freshness analysis
- Pattern detection and learning

## Models

### ModelIntelligenceConfig

**Status**: ✅ Implemented (2025-10-21)

Configuration contract for Intelligence Adapter Effect Node. Provides comprehensive settings for:

**Service Configuration**:
- `base_url`: Intelligence service URL (default: `http://localhost:8053`)
- `timeout_seconds`: API timeout (5.0-300.0s, default: 30.0)
- `max_retries`: Retry attempts (0-10, default: 3)
- `retry_delay_ms`: Retry delay (100-10000ms, default: 1000)

**Circuit Breaker Settings**:
- `circuit_breaker_enabled`: Enable/disable (default: True)
- `circuit_breaker_threshold`: Failures before open (1-100, default: 5)
- `circuit_breaker_timeout_seconds`: Recovery timeout (10.0-600.0s, default: 60.0)

**Event Bus Settings**:
- `enable_event_publishing`: Enable Kafka events (default: True)
- `input_topics`: List of input topics (ONEX naming convention required)
- `output_topics`: Event type → topic mapping
- `consumer_group_id`: Kafka consumer group

**Environment Factory Methods**:
```python
# Environment-based configuration
dev_config = ModelIntelligenceConfig.for_environment("development")
staging_config = ModelIntelligenceConfig.for_environment("staging")
prod_config = ModelIntelligenceConfig.for_environment("production")

# Automatic environment detection
config = ModelIntelligenceConfig.from_environment_variable()
```

**URL Helpers**:
```python
config = ModelIntelligenceConfig()
health_url = config.get_health_check_url()
assess_url = config.get_assess_code_url()
baseline_url = config.get_performance_baseline_url()
```

**Event Topic Resolution**:
```python
topic = config.get_output_topic_for_event("quality_assessed")
if topic:
    await kafka_producer.send(topic, event_data)
```

**Examples**: See `examples_intelligence_config.py` for comprehensive usage patterns

### ModelIntelligenceOutput

Main output contract for all intelligence operations. Provides:

**Core Response Fields**:
- `success`: Operation success status
- `operation_type`: Intelligence operation performed
- `correlation_id`: UUID for end-to-end tracking
- `processing_time_ms`: Total execution time

**Intelligence Scoring**:
- `quality_score`: Overall quality (0.0-1.0)
- `onex_compliance`: ONEX compliance (0.0-1.0)
- `complexity_score`: Code complexity (0.0-1.0)

**Analysis Results**:
- `issues`: Detected issues requiring attention
- `recommendations`: Actionable improvement suggestions
- `patterns`: Detected patterns (architectural, quality, security)

**Error Handling**:
- `error_code`: Machine-readable error code
- `error_message`: Human-readable description
- `retry_allowed`: Whether retry is safe

**Execution Metrics**:
- `metrics`: Detailed performance tracking
- `result_data`: Operation-specific data
- `metadata`: Extensible additional context

### ModelPatternDetection

Detected pattern structure:

- `pattern_type`: Category (architectural, quality, security, performance)
- `pattern_name`: Human-readable pattern name
- `confidence`: Detection confidence (0.0-1.0)
- `description`: Pattern description and context
- `location`: Source location (file:line)
- `severity`: Pattern severity (info, warning, error, critical)
- `recommendation`: Suggested action

### ModelIntelligenceMetrics

Execution metrics for performance tracking:

- `rag_service_ms`: RAG service execution time
- `vector_service_ms`: Vector search (Qdrant) time
- `knowledge_service_ms`: Knowledge graph (Memgraph) time
- `cache_hit`: Whether served from cache
- `cache_key`: Cache key used
- `services_invoked`: Backend services called
- `total_api_calls`: Total API calls made

## Usage

### Basic Success Response

```python
from intelligence.models import ModelIntelligenceOutput

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

### From API Response

```python
api_response = {
    "quality_score": 0.87,
    "onex_compliance": 0.92,
    "issues": ["Missing docstrings"],
    "recommendations": ["Add type hints"],
}

output = ModelIntelligenceOutput.from_api_response(
    api_response=api_response,
    operation_type="assess_code_quality",
    correlation_id=uuid4(),
    processing_time_ms=1234,
)
```

### Error Response

```python
error = ModelIntelligenceOutput.create_error(
    operation_type="assess_code_quality",
    correlation_id=uuid4(),
    processing_time_ms=150,
    error_code="INTELLIGENCE_SERVICE_TIMEOUT",
    error_message="Service did not respond within 10s",
    retry_allowed=True,
)
```

### Serialization

```python
output = ModelIntelligenceOutput(...)

# Convert to JSON-serializable dict
result_dict = output.to_dict()

# UUIDs converted to strings, datetime to ISO 8601
import json
json_str = json.dumps(result_dict)
```

## Intelligence Operations

### Code Quality Assessment

**Operation**: `assess_code_quality`

**Returns**:
- `quality_score`: Overall quality (0.0-1.0)
- `onex_compliance`: ONEX compliance (0.0-1.0)
- `complexity_score`: Code complexity (0.0-1.0)
- `issues`: List of detected issues
- `recommendations`: Improvement suggestions
- `patterns`: Detected patterns (architectural, quality, security)

**Example**:
```python
output = ModelIntelligenceOutput(
    success=True,
    operation_type="assess_code_quality",
    quality_score=0.87,
    onex_compliance=0.92,
    complexity_score=0.65,
    issues=["Missing docstrings", "High complexity"],
    recommendations=["Add type hints", "Reduce complexity"],
    patterns=[
        ModelPatternDetection(
            pattern_type="architectural",
            pattern_name="ONEX_EFFECT_NODE",
            confidence=0.95,
            description="Proper Effect node implementation",
            severity="info",
        )
    ],
)
```

### RAG Intelligence Gathering

**Operation**: `perform_rag_query`

**Returns**:
- `result_data`: Query results with sources
- `recommendations`: Related patterns and references
- `metrics`: Service timing and cache stats

**Example**:
```python
output = ModelIntelligenceOutput(
    success=True,
    operation_type="perform_rag_query",
    processing_time_ms=45,
    recommendations=["See similar patterns in project X"],
    result_data={
        "query": "ONEX Effect node patterns",
        "total_results": 42,
        "top_confidence": 0.94,
    },
    metrics=ModelIntelligenceMetrics(
        cache_hit=True,
        cache_key="research:rag:onex_patterns",
        services_invoked=["cache"],
    ),
)
```

### Performance Optimization

**Operation**: `identify_optimization_opportunities`

**Returns**:
- `recommendations`: ROI-ranked optimization suggestions
- `result_data`: Opportunities with impact/effort analysis

**Example**:
```python
output = ModelIntelligenceOutput(
    success=True,
    operation_type="identify_optimization_opportunities",
    recommendations=[
        "Add database index (50% improvement)",
        "Implement caching (40% cache hit rate)",
    ],
    result_data={
        "opportunities": [
            {
                "type": "database_index",
                "impact": "high",
                "effort": "low",
                "roi_score": 0.95,
            }
        ],
    },
)
```

## Error Codes

Common error codes returned by intelligence operations:

- `INTELLIGENCE_SERVICE_TIMEOUT`: Service timeout (retry allowed)
- `INVALID_INPUT_SYNTAX`: Malformed input (no retry)
- `ONEX_COMPLIANCE_FAILED`: ONEX validation failed
- `CACHE_CONNECTION_ERROR`: Cache unavailable (retry allowed)
- `SERVICE_UNAVAILABLE`: Backend service down (retry allowed)

## ONEX Compliance

This model follows ONEX patterns:

✅ **Naming Convention**: Suffix-based (`ModelIntelligenceOutput`)  
✅ **Structured Fields**: All fields use `Field()` with descriptions  
✅ **Type Safety**: Strong typing with UUID preservation  
✅ **Examples**: Comprehensive JSON schema examples  
✅ **Serialization**: `to_dict()` for JSON compatibility  
✅ **Factory Methods**: `from_api_response()`, `create_error()`  

## Testing

Run usage examples:

```bash
# Set Python path
export PYTHONPATH=/Volumes/PRO-G40/Code/omniarchon/python/src

# Run configuration examples (NEW)
python -m intelligence.models.examples_intelligence_config

# Run output model examples
cd /Volumes/PRO-G40/Code/omniarchon/python/src/intelligence/models
python usage_examples.py
```

## References

- **Pattern Source**: `omninode_bridge/nodes/database_adapter_effect/v1_0_0/models/outputs/`
- **ONEX Guide**: `/Volumes/PRO-G40/Code/omniarchon/docs/onex/ONEX_GUIDE.md`
- **Event Envelope**: `/Volumes/PRO-G40/Code/omniarchon/python/src/events/models/model_event_envelope.py`
- **Intelligence Service**: `http://localhost:8053` (Intelligence APIs)

## File Structure

```
intelligence/models/
├── __init__.py                          # Package exports
├── model_intelligence_config.py         # Configuration contract ✅ NEW
├── model_intelligence_output.py         # Main output contract
├── examples_intelligence_config.py      # Config usage examples (runnable) ✅ NEW
├── usage_examples.py                    # Output usage examples (runnable)
└── README.md                            # This file
```

## Integration

This output model is designed for use with:

1. **Intelligence Adapter Effect Node**: Return type for `execute_effect()`
2. **MCP Server Tools**: Response structure for intelligence operations
3. **Event Payloads**: Serialization for event bus publishing
4. **API Responses**: JSON responses from intelligence service
5. **Logging & Metrics**: Structured logging with correlation tracking

## License

Part of the Archon Intelligence Platform.
