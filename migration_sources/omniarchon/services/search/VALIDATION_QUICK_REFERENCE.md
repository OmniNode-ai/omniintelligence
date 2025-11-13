# Validation Quick Reference

## Import Validators

```python
from utils.response_validator import (
    validate_ollama_embedding,
    validate_ollama_health,
    validate_qdrant_search,
    validate_qdrant_points,
    validate_bridge_mapping_stats,
    validate_bridge_health,
    validate_intelligence_quality,
    validate_intelligence_health,
    validate_memgraph_results,
)
from models.external_validation import ValidationStatus
```

## Basic Usage Pattern

```python
# 1. Fetch response
response = await http_client.post(url, json=data)
result = response.json()

# 2. Validate
validation_result = validate_service_response(result, allow_partial=True)

# 3. Check status
if validation_result.status == ValidationStatus.FAILED:
    logger.error(f"Validation failed: {validation_result.errors}")
    return None

if validation_result.status == ValidationStatus.PARTIAL:
    logger.warning(f"Partial validation (confidence: {validation_result.confidence:.2f})")

# 4. Use validated data
validated_data = validation_result.validated_data
```

## Validation Status Decision Tree

```
validation_result.status
├─ VALID (confidence = 1.0)
│  └─ Use data normally
├─ PARTIAL (confidence 0.5-0.9)
│  ├─ confidence >= 0.8 → Use with logging
│  └─ confidence < 0.8 → Use with caution
├─ INVALID (confidence < 0.5)
│  └─ Use fallback or default
└─ FAILED (confidence = 0.0)
   └─ Return error or retry
```

## Service-Specific Examples

### Ollama (Embeddings)

```python
response = await http_client.post("/api/embeddings", json={...})
result = response.json()

validation_result = validate_ollama_embedding(result, allow_partial=True)
if validation_result.status != ValidationStatus.FAILED:
    embedding = validation_result.validated_data.embedding
    embedding_array = np.array(embedding, dtype=np.float32)
```

### Qdrant (Vector Search)

```python
response = await qdrant_client.search(...)
result = response.json()

validation_result = validate_qdrant_search(result, allow_partial=True)
if validation_result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]:
    search_results = validation_result.validated_data.result
    for point in search_results:
        process_point(point.id, point.score, point.payload)
```

### Bridge Service (Metadata)

```python
response = await http_client.get("/mapping/stats")
stats = response.json()

validation_result = validate_bridge_mapping_stats(stats, allow_partial=True)
if validation_result.confidence >= 0.7:
    supabase_entities = validation_result.validated_data.supabase_entities
    pages_count = supabase_entities.get("pages", 0)
```

### Intelligence Service (Quality)

```python
response = await http_client.post("/assess/code", json={...})
result = response.json()

validation_result = validate_intelligence_quality(result, allow_partial=True)
if validation_result.status == ValidationStatus.VALID:
    quality_score = validation_result.validated_data.quality_score
    onex_compliance = validation_result.validated_data.onex_compliance
```

## Confidence-Based Decision Making

```python
validation_result = validate_response(data, allow_partial=True)

if validation_result.confidence >= 0.9:
    # High confidence - critical operations
    perform_critical_operation()
elif validation_result.confidence >= 0.7:
    # Good confidence - normal operations
    perform_normal_operation()
elif validation_result.confidence >= 0.5:
    # Moderate confidence - use with logging
    logger.warning(f"Low confidence: {validation_result.confidence}")
    perform_operation_with_caution()
else:
    # Low confidence - use fallback
    use_fallback()
```

## List Validation

```python
points = [...]  # List of points from Qdrant

validation_result = validate_qdrant_points(points, allow_partial=True)

# Partial validation returns only valid items
valid_points = validation_result.validated_data
logger.info(f"Validated {len(valid_points)}/{len(points)} points")

for point in valid_points:
    process_point(point)
```

## Health Check Pattern

```python
response = await http_client.get("/health")
result = response.json()

validation_result = validate_service_health(result, allow_partial=True)

# Accept both VALID and PARTIAL for health checks
health_ok = validation_result.status in [
    ValidationStatus.VALID,
    ValidationStatus.PARTIAL
]

if health_ok and validation_result.confidence >= 0.5:
    return True
else:
    logger.error(f"Health check failed: {validation_result.errors}")
    return False
```

## Error Handling

```python
try:
    response = await http_client.post(url, json=data)
    result = response.json()

    validation_result = validate_response(result, allow_partial=True)

    if validation_result.status == ValidationStatus.FAILED:
        raise ValueError(f"Invalid response: {validation_result.errors}")

    return validation_result.validated_data

except httpx.HTTPError as e:
    logger.error(f"HTTP error: {e}")
    return None
except ValueError as e:
    logger.error(f"Validation error: {e}")
    return None
```

## Logging Best Practices

```python
validation_result = validate_response(data, allow_partial=True)

# Log based on status
if validation_result.status == ValidationStatus.FAILED:
    logger.error(
        f"❌ {service_name} validation FAILED: {validation_result.errors}"
    )
elif validation_result.status == ValidationStatus.INVALID:
    logger.warning(
        f"⚠️  {service_name} validation INVALID "
        f"(confidence: {validation_result.confidence:.2f})"
    )
elif validation_result.status == ValidationStatus.PARTIAL:
    logger.info(
        f"✓ {service_name} validation PARTIAL "
        f"(confidence: {validation_result.confidence:.2f}): {validation_result.warnings}"
    )
else:  # VALID
    logger.debug(f"✅ {service_name} validation VALID")
```

## Testing Pattern

```python
def test_valid_response():
    """Test validation of valid response"""
    response = {
        "required_field": "value",
        "optional_field": "value",
    }

    result = validate_response(response, allow_partial=True)

    assert result.status == ValidationStatus.VALID
    assert result.confidence == 1.0
    assert result.validated_data is not None
    assert len(result.errors) == 0

def test_partial_response():
    """Test partial validation with missing optional fields"""
    response = {
        "required_field": "value",
        # Missing optional_field
    }

    result = validate_response(response, allow_partial=True)

    assert result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]
    assert result.confidence >= 0.5
    assert result.validated_data is not None

def test_invalid_response():
    """Test validation failure with missing required field"""
    response = {
        # Missing required_field
        "optional_field": "value",
    }

    result = validate_response(response, allow_partial=True)

    assert result.status == ValidationStatus.INVALID
    assert result.confidence < 0.5
    assert len(result.errors) > 0
```

## Common Pitfalls

### ❌ Not checking validation status

```python
# BAD: Assumes validation always succeeds
validation_result = validate_response(data)
data = validation_result.validated_data  # Might be None!
```

### ✅ Always check status

```python
# GOOD: Check status before using data
validation_result = validate_response(data)
if validation_result.status != ValidationStatus.FAILED:
    data = validation_result.validated_data
```

### ❌ Ignoring partial validation

```python
# BAD: Only accepts perfect validation
if validation_result.status == ValidationStatus.VALID:
    process(data)
# Misses PARTIAL data that's still usable!
```

### ✅ Handle partial validation

```python
# GOOD: Accept partial validation
if validation_result.status in [ValidationStatus.VALID, ValidationStatus.PARTIAL]:
    process(validation_result.validated_data)
```

### ❌ Not logging validation issues

```python
# BAD: Silent failures
validation_result = validate_response(data)
if validation_result.status == ValidationStatus.FAILED:
    return None
```

### ✅ Log validation issues

```python
# GOOD: Log for debugging
validation_result = validate_response(data)
if validation_result.status == ValidationStatus.FAILED:
    logger.error(f"Validation failed: {validation_result.errors}")
    return None
```

## Performance Tips

1. **Cache validated responses**: Don't re-validate the same response
2. **Use partial validation**: Set `allow_partial=True` for resilience
3. **Validate early**: Validate immediately after fetching
4. **Selective validation**: For large responses, validate only critical fields

## Troubleshooting

### Validation Always Fails

**Check**:
- Response structure matches model definition
- Required fields are present
- Field types match (str, int, float, etc.)
- Value ranges are valid (scores 0-1, counts ≥0)

### Low Confidence Scores

**Causes**:
- Missing optional fields (warnings)
- Extra fields in response (usually OK)
- Minor validation issues

**Solution**: Review warnings in `validation_result.warnings`

### Partial Validation Issues

**Check**:
- `allow_partial=True` is set
- Model has defaults for optional fields
- Response has at least some valid data

## Quick Checklist

- [ ] Import validation function
- [ ] Fetch response and parse JSON
- [ ] Call validation function with `allow_partial=True`
- [ ] Check validation status before using data
- [ ] Log validation issues (errors/warnings)
- [ ] Use confidence score for decision-making
- [ ] Handle FAILED status gracefully
- [ ] Extract validated data from result
- [ ] Process validated data safely

## Need Help?

1. Check `/docs/VALIDATION_GUIDE.md` for detailed documentation
2. Review test cases in `/tests/test_response_validation.py`
3. Examine model definitions in `/models/external_validation.py`
4. Look at integration examples in VectorSearchEngine and HybridSearchOrchestrator
