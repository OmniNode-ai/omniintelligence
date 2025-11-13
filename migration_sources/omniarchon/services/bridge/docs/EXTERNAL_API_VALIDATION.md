# External API Response Validation

## Overview

The Bridge service implements **strict Pydantic validation** for all external API responses to prevent crashes, data corruption, and security vulnerabilities from malformed or malicious data. This document describes the validation architecture, usage patterns, and security considerations.

## Motivation

**Problem**: External APIs (Intelligence service, Supabase, Memgraph) can return malformed data due to:
- Network errors causing incomplete responses
- Service bugs producing incorrect data structures
- Version mismatches between services
- Malicious injection attacks
- Database schema changes

**Solution**: Validate all external API responses at the boundary using Pydantic models with strict type checking, constraint validation, and meaningful error messages.

## Architecture

### Validation Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Bridge Service                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         External API Validation Layer                │  │
│  │                                                       │  │
│  │  • Pydantic models with strict validation            │  │
│  │  • Type checking (str, int, float, etc.)             │  │
│  │  • Constraint validation (min/max, ranges)           │  │
│  │  • Required field enforcement                        │  │
│  │  • Custom validators for business logic              │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Validation Points (Before Processing)         │  │
│  │                                                       │  │
│  │  • EntityMapper.extract_and_map_content()            │  │
│  │  • app._process_document_sync_background()           │  │
│  │  • SupabaseConnector (all query results)             │  │
│  │  • MemgraphConnector (all Cypher results)            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   External Services                         │
│  • Intelligence (HTTP/JSON)                                 │
│  • Supabase (PostgreSQL client)                             │
│  • Memgraph (Neo4j Bolt protocol)                           │
└─────────────────────────────────────────────────────────────┘
```

## Validation Models

### Intelligence Service Models

Located in: `models/external_api_models.py`

#### 1. `IntelligenceEntityResponse`

Validates individual entities returned by `/extract/code` and `/extract/document` endpoints.

**Fields**:
- `entity_id` (str, required): Unique identifier, min_length=1, non-empty
- `entity_type` (str, required): Entity type (e.g., "function", "class"), non-empty
- `name` (str, required): Entity name
- `confidence_score` (float, required): Confidence 0.0-1.0 (inclusive)
- `properties` (dict, optional): Additional entity properties

**Validation Rules**:
- All string fields cannot be empty or whitespace-only
- `confidence_score` must be between 0.0 and 1.0
- Extra fields are **forbidden** (strict mode)
- All required fields must be present

**Example**:
```python
from models.external_api_models import IntelligenceEntityResponse

# Valid entity
valid_data = {
    "entity_id": "entity_123",
    "entity_type": "function",
    "name": "process_data",
    "confidence_score": 0.95,
    "properties": {"language": "python"}
}
entity = IntelligenceEntityResponse.model_validate(valid_data)

# Invalid entity (confidence out of range) - raises ValidationError
invalid_data = {
    "entity_id": "entity_123",
    "entity_type": "function",
    "name": "process_data",
    "confidence_score": 1.5  # ERROR: > 1.0
}
```

#### 2. `IntelligenceExtractionResponse`

Validates responses from `/extract/code` and `/extract/document` endpoints.

**Fields**:
- `entities` (List[IntelligenceEntityResponse], required): Extracted entities
- `entities_extracted` (int, optional): Entity count (must match array length if provided)
- `status` (str, optional): Operation status
- `message` (str, optional): Status message

**Validation Rules**:
- Each entity in `entities` array is validated via `IntelligenceEntityResponse`
- If `entities_extracted` is provided, it must match `len(entities)`
- `entities_extracted` must be >= 0 if provided

**Example**:
```python
from models.external_api_models import validate_intelligence_response

response_data = {
    "entities": [
        {
            "entity_id": "entity_1",
            "entity_type": "function",
            "name": "func_1",
            "confidence_score": 0.9
        }
    ],
    "entities_extracted": 1,
    "status": "success"
}

# Validate response
validated = validate_intelligence_response(response_data, "/extract/code")
```

#### 3. `IntelligenceDocumentProcessingResponse`

Validates responses from `/process/document` endpoint.

**Fields**:
- `entities_extracted` (int, required): Number of entities extracted (>= 0)
- `status` (str, required): Processing status, min_length=1
- `message` (str, optional): Status message
- `document_id` (str, optional): Document identifier
- `project_id` (str, optional): Project identifier
- `vectorization_status` (str, optional): Vectorization status
- `error` (str, optional): Error message if failed

**Example**:
```python
response_data = {
    "entities_extracted": 10,
    "status": "completed",
    "document_id": "doc_123"
}
validated = validate_intelligence_response(response_data, "/process/document")
```

#### 4. `IntelligenceHealthResponse`

Validates responses from `/health` endpoint.

**Fields**:
- `status` (str, required): One of "healthy", "degraded", "unhealthy", "ok" (case-insensitive)
- `service` (str, optional): Service name
- `version` (str, optional): Service version
- `uptime_seconds` (float, optional): Uptime (>= 0.0)

**Validation Rules**:
- Status is normalized to lowercase
- Status must be one of valid values

### Supabase Models

#### 1. `SupabaseQueryResultData`

Validates Supabase query result structure.

**Fields**:
- `data` (List[Dict[str, Any]], required): Query result rows
- `count` (Optional[int]): Total count if requested (>= 0)
- `error` (Optional[Dict[str, Any]]): Error information if query failed

**Validation Rules**:
- `count` cannot be less than `len(data)` (handles pagination)
- `count` must be >= 0 if provided

#### 2. `SupabaseRowData`

Base model for Supabase row data with common fields.

**Fields**:
- `id` (Union[str, int], required): Primary key
- `created_at` (str, required): Creation timestamp (ISO format)
- `updated_at` (Optional[str]): Update timestamp (ISO format)

**Validation Rules**:
- Timestamps must be valid ISO 8601 format
- Extra fields are **allowed** (for entity-specific fields)

### Memgraph Models

#### 1. `MemgraphQueryResult`

Validates Memgraph Cypher query results.

**Fields**:
- `records` (List[Dict[str, Any]], required): Query result records
- `summary` (Optional[Dict[str, Any]]): Query execution summary

**Validation Rules**:
- Each record must be a dictionary
- Extra fields in records are allowed

#### 2. `MemgraphSingleRecordResult`

Validates single-record Memgraph results.

**Fields**:
- `record` (Optional[Dict[str, Any]]): Single record (None if no result)

**Validation Rules**:
- If record is present, it must be a dictionary
- None is valid (represents no result found)

## Usage Patterns

### 1. Intelligence Service Validation

**Location**: `mapping/entity_mapper.py` - `extract_and_map_content()` method

```python
from models.external_api_models import validate_intelligence_response, IntelligenceExtractionResponse
from pydantic import ValidationError

# Call intelligence service
response = await self.http_client.post(endpoint, json=request_data)

if response.status_code == 200:
    try:
        # SECURITY: Validate response structure before processing
        raw_result = response.json()
        validated_response = validate_intelligence_response(raw_result, endpoint)

        if not isinstance(validated_response, IntelligenceExtractionResponse):
            logger.error(f"Unexpected response type from {endpoint}")
            return []

        # Extract validated entities (safe to use)
        entities = [
            {
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "confidence_score": entity.confidence_score,
                "properties": entity.properties,
            }
            for entity in validated_response.entities
        ]

    except ValidationError as ve:
        logger.error(f"Response validation failed: {ve}")
        return []
```

### 2. Document Processing Validation

**Location**: `app.py` - `_process_document_sync_background()` function

```python
from models.external_api_models import validate_intelligence_response
from pydantic import ValidationError

response = await pooled_http_client.post("/process/document", json=data)

if response.status_code == 200:
    try:
        # SECURITY: Validate response structure before processing
        raw_result = response.json()
        validated_response = validate_intelligence_response(raw_result, "/process/document")

        entities_count = validated_response.entities_extracted
        logger.info(f"Intelligence service completed: {entities_count} entities")

    except ValidationError as ve:
        logger.error(f"Response validation failed: {ve}")
        raise
```

### 3. Supabase Result Validation

**Location**: `connectors/supabase_connector.py` - All query methods

```python
from models.external_api_models import validate_supabase_result

# Execute Supabase query
result = self.client.table("archon_sources").select("*").execute()

# Validate result structure
validated_result = validate_supabase_result(result, expected_fields=["id", "created_at"])

# Safe to process validated data
for row in validated_result.data:
    # Convert to domain model
    source = ArchonSource.model_validate(row)
```

### 4. Memgraph Result Validation

**Location**: `connectors/memgraph_connector.py` - Cypher query methods

```python
from models.external_api_models import validate_memgraph_result

# Execute Cypher query
result = await session.run(query, params)
records = await result.data()

# Validate result structure
validated_result = validate_memgraph_result(records, expected_keys=["id", "name"])

# Safe to process validated records
for record in validated_result.records:
    entity_id = record["id"]
    name = record["name"]
```

## Error Handling

### Validation Error Types

1. **Missing Required Fields**:
```python
# Missing entity_type field
ValidationError: 1 validation error for IntelligenceEntityResponse
entity_type
  Field required [type=missing, input_value={...}, input_type=dict]
```

2. **Type Mismatch**:
```python
# entity_id should be string, got int
ValidationError: 1 validation error for IntelligenceEntityResponse
entity_type
  Input should be a valid string [type=string_type, input_value=123, input_type=int]
```

3. **Constraint Violation**:
```python
# confidence_score out of range
ValidationError: 1 validation error for IntelligenceEntityResponse
confidence_score
  Input should be less than or equal to 1.0 [type=less_than_equal, input_value=1.5, input_type=float]
```

4. **Custom Validation Error**:
```python
# Empty string field
ValidationError: 1 validation error for IntelligenceEntityResponse
entity_id
  entity_id cannot be empty or whitespace [type=value_error, input_value='', input_type=str]
```

### Error Handling Pattern

```python
try:
    validated_response = validate_intelligence_response(raw_result, endpoint)
    # Process validated data safely

except ValidationError as ve:
    # Log detailed validation errors
    logger.error(f"Response validation failed for {endpoint}: {ve}")

    # Log raw data for debugging (be careful with sensitive data)
    logger.debug(f"Invalid response data: {raw_result}")

    # Return safe default or raise exception
    return []  # or raise

except ValueError as e:
    # Handle validation utility errors (e.g., unknown endpoint)
    logger.error(f"Validation error: {e}")
    return []
```

## Security Considerations

### 1. Prevent Injection Attacks

**Note**: Pydantic validates **structure and types**, not **content safety**. Additional layers are needed:

```python
# Pydantic validates type is string, but not content
entity_id = "entity'; DROP TABLE users; --"  # Passes validation

# Protection layers:
# 1. Database layer: Use parameterized queries (Supabase/Memgraph clients handle this)
# 2. Output layer: Escape HTML/JS when rendering (FastAPI/Jinja2 handle this)
# 3. Business logic: Additional content validation if needed
```

### 2. Prevent Denial of Service (DoS)

**Size Limits**: Currently no explicit size limits on arrays or strings. Consider adding:

```python
# Add to models if needed
class IntelligenceExtractionResponse(BaseModel):
    entities: List[IntelligenceEntityResponse] = Field(
        ...,
        max_length=1000  # Limit array size
    )

class IntelligenceEntityResponse(BaseModel):
    entity_id: str = Field(
        ...,
        min_length=1,
        max_length=256  # Limit string length
    )
```

### 3. Prevent Data Exfiltration

**Redact Sensitive Data in Error Logs**:

```python
try:
    validated = validate_intelligence_response(raw_result, endpoint)
except ValidationError as ve:
    # Don't log full response if it might contain sensitive data
    logger.error(f"Validation failed: {ve}")
    # Redact sensitive fields if logging raw data
    # logger.debug(f"Invalid data: {redact_sensitive(raw_result)}")
```

### 4. Strict Mode vs Permissive Mode

**Current Configuration**:
- **Intelligence models**: `extra="forbid"` + `strict=True` (strict mode)
  - Rejects extra fields
  - Rejects type coercion (e.g., "123" to int)

- **Supabase/Memgraph models**: `extra="allow"` (permissive mode)
  - Allows extra fields (for flexibility)
  - Type coercion enabled (for compatibility)

**Rationale**: Intelligence service is fully controlled, so we can enforce strict contracts. Database clients may have additional fields we don't care about.

## Testing

### Unit Tests

**Location**: `tests/unit/test_external_api_validation.py`

**Coverage** (74 tests):
- Valid responses for all models ✅
- Missing required fields ✅
- Invalid types ✅
- Constraint violations (ranges, lengths) ✅
- Edge cases (empty arrays, null values, boundary conditions) ✅
- Security scenarios (injection attempts, large data) ✅
- Utility function validation ✅

**Run Tests**:
```bash
# Run all validation tests
pytest services/bridge/tests/unit/test_external_api_validation.py -v

# Run specific test class
pytest services/bridge/tests/unit/test_external_api_validation.py::TestIntelligenceEntityResponse -v

# Run with coverage
pytest services/bridge/tests/unit/test_external_api_validation.py --cov=models.external_api_models
```

### Integration Tests

Consider adding integration tests that:
1. Mock external services returning malformed data
2. Verify bridge service handles validation errors gracefully
3. Test end-to-end flows with validation enabled

## Performance Considerations

### Validation Overhead

**Pydantic Validation Cost**: ~100-500μs per validation (negligible compared to network I/O)

**Optimization Strategies**:
1. **Validate once at boundary**: Don't re-validate internal data
2. **Batch validation**: Validate arrays efficiently (Pydantic optimized for this)
3. **Lazy validation**: Only validate if response.status_code == 200
4. **Cache validated models**: Reuse validated instances when possible

### Benchmarks

```python
# Example: Validate 100 entities
import time
from models.external_api_models import IntelligenceEntityResponse

entities = [generate_entity_data() for _ in range(100)]

start = time.time()
validated = [IntelligenceEntityResponse.model_validate(e) for e in entities]
duration = time.time() - start

print(f"Validated 100 entities in {duration*1000:.2f}ms")  # ~10-20ms
```

## Future Improvements

### 1. Response Schema Versioning

Support multiple API versions:

```python
class IntelligenceEntityResponseV1(BaseModel):
    # v1 schema

class IntelligenceEntityResponseV2(BaseModel):
    # v2 schema with new fields

def validate_intelligence_response(data, endpoint, api_version="v1"):
    if api_version == "v1":
        return IntelligenceEntityResponseV1.model_validate(data)
    elif api_version == "v2":
        return IntelligenceEntityResponseV2.model_validate(data)
```

### 2. Automatic Schema Generation

Generate OpenAPI/JSON Schema from Pydantic models:

```python
# Export schemas for documentation
from models.external_api_models import IntelligenceEntityResponse

schema = IntelligenceEntityResponse.model_json_schema()
# Use in API docs, client generation, etc.
```

### 3. Contract Testing

Implement contract tests between bridge and intelligence service:

```python
# Ensure intelligence service responses match expected schemas
def test_intelligence_service_contract():
    response = requests.post(f"{intelligence_url}/extract/code", json=payload)
    # Assert response matches IntelligenceExtractionResponse schema
    validated = IntelligenceExtractionResponse.model_validate(response.json())
```

### 4. Metrics and Monitoring

Track validation failures:

```python
from prometheus_client import Counter

validation_errors = Counter(
    'bridge_validation_errors_total',
    'Total validation errors by service and endpoint',
    ['service', 'endpoint', 'error_type']
)

try:
    validated = validate_intelligence_response(data, endpoint)
except ValidationError as ve:
    validation_errors.labels(
        service='intelligence',
        endpoint=endpoint,
        error_type='validation_error'
    ).inc()
    raise
```

## References

- **Pydantic Documentation**: https://docs.pydantic.dev/latest/
- **Pydantic Validation**: https://docs.pydantic.dev/latest/concepts/validators/
- **FastAPI Data Validation**: https://fastapi.tiangolo.com/tutorial/body/
- **OWASP Input Validation**: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html

## Changelog

### Version 1.0 (2025-01-XX)
- Initial implementation of external API validation
- Intelligence service models (entity, extraction, document processing, health)
- Supabase query result models
- Memgraph query result models
- Validation utility functions
- Comprehensive unit tests (74 tests)
- Documentation and usage examples
