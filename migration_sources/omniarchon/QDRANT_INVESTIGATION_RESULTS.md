# Qdrant Vector Investigation Results

**Date**: 2025-11-12  
**Collection**: archon_vectors  
**Investigation**: Test failure debugging - vectors not found by document_id

## Collection Status

- **Total Vectors**: 17,994
- **Indexed Vectors**: 17,934
- **Collection Status**: ✅ Green (healthy)
- **Vector Dimensions**: 1,536 (Cosine distance)

## Payload Structure Analysis

### Available Payload Fields (29 total)

Based on sampling 50+ vectors, the following fields are present:

```
- absolute_path        ✅ PRIMARY IDENTIFIER
- chunk_number
- concepts             (array)
- content
- content_hash
- created_at
- entity_id
- entity_type
- examples
- file_path
- indexed_at           ✅ Always present
- language             ✅ Always present
- node_types
- onex_compliance      ✅ Always present
- onex_type
- pattern_confidence
- pattern_name
- pattern_type
- project_id
- project_name         ✅ Always present
- project_root         ✅ Always present
- quality_score        ✅ Always present
- relative_path        ✅ Always present
- source_id
- themes               (array)
- title
- updated_at
- url
- use_cases
```

### ⚠️ CRITICAL FINDING: No `document_id` Field

**Result**: ❌ **ZERO** vectors have a `document_id` field across 17,994 vectors

**Impact**: Tests searching for `document_id` will ALWAYS fail because this field doesn't exist in Qdrant.

## Test Documents Present

Found **7 smoke_test documents** in Qdrant:

1. `smoke_test_c07bc8a6` - indexed 2025-11-12 15:40:03
2. `smoke_test_fb69a19d` - indexed 2025-11-12 17:03:26
3. `smoke_test_ed79112a` - indexed 2025-11-12 17:02:18
4. `smoke_test_81266718` - indexed 2025-11-12 15:47:13
5. `smoke_test_c6247780` - indexed 2025-11-12 15:39:16
6. `smoke_test_6293484e` - indexed 2025-11-12 15:47:42
7. `smoke_test_48c0dc7a` - indexed 2025-11-12 17:01:55

All have `project_name: "smoke_test"` and language: "unknown"

## Sample Payload Structure

```json
{
  "id": 844465138769397505,
  "payload": {
    "absolute_path": "archon://projects/smoke_test/documents/smoke_test_c07bc8a6",
    "concepts": [],
    "indexed_at": "2025-11-12T15:40:03.781683+00:00",
    "language": "unknown",
    "onex_compliance": 0.0,
    "onex_type": null,
    "project_name": "smoke_test",
    "project_root": "",
    "quality_score": 0.0,
    "relative_path": "",
    "themes": []
  }
}
```

## absolute_path URI Patterns

The `absolute_path` field contains the document identifier:

```
archon://projects/{project_name}/documents/{document_id}
```

**Examples**:
- `archon://projects/smoke_test/documents/smoke_test_c07bc8a6`
- `archon://projects/integration_test/documents/integration_test_d7022816`
- `archon://projects/test_project/documents/test_pipeline_fix_1731430000`

The document ID (e.g., `smoke_test_c07bc8a6`) is embedded in the URI path.

## Root Cause Analysis

### Why Tests Fail

**Test Code** (from `test_e2e_ingestion_smoke.py`):
```python
search_results = qdrant_client.search(
    collection_name="archon_vectors",
    query_vector=query_vector,
    limit=5,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",           # ❌ This field doesn't exist!
                match=models.MatchValue(value=doc_id),
            )
        ]
    ),
)
```

**Qdrant Reality**:
- Field name: ❌ `document_id` (doesn't exist)
- Should be: ✅ `absolute_path` (contains URI with embedded doc_id)

### Why This Happened

1. **Field Naming Mismatch**:
   - Test assumes `document_id` field
   - Actual field is `absolute_path` with URI format

2. **No Schema Validation**:
   - No enforcement of required payload fields
   - Tests don't verify field existence before searching

3. **URI Format Not Documented**:
   - Tests expect flat document_id
   - Actual format is hierarchical URI

## Solution Options

### Option 1: Fix Test to Use absolute_path ✅ RECOMMENDED

**Change**:
```python
# Before (BROKEN)
filter=models.Filter(
    must=[
        models.FieldCondition(
            key="document_id",
            match=models.MatchValue(value=doc_id),
        )
    ]
)

# After (WORKING)
filter=models.Filter(
    must=[
        models.FieldCondition(
            key="absolute_path",
            match=models.MatchValue(
                value=f"archon://projects/{project_name}/documents/{doc_id}"
            ),
        )
    ]
)
```

**Pros**:
- Matches actual Qdrant schema
- No indexing changes needed
- Leverages existing URI structure

**Cons**:
- Requires URI formatting in tests
- String matching instead of exact ID match

### Option 2: Add document_id Field During Indexing

Add a separate `document_id` payload field that extracts the ID from the URI.

**Indexing Change**:
```python
# Extract document_id from absolute_path
document_id = absolute_path.split("/documents/")[-1]

payload = {
    "absolute_path": absolute_path,
    "document_id": document_id,  # Add this field
    "project_name": project_name,
    # ... other fields
}
```

**Pros**:
- Cleaner test queries
- Direct ID matching
- Better query performance (no string prefix matching)

**Cons**:
- Requires reindexing all 17,994 vectors
- Data duplication (ID in both fields)
- Migration overhead

### Option 3: Hybrid Approach ✅ BEST LONG-TERM

1. Add `document_id` field to new vectors during indexing
2. Update tests to check both fields (backwards compatible):

```python
filter=models.Filter(
    should=[  # OR condition
        models.FieldCondition(
            key="document_id",
            match=models.MatchValue(value=doc_id),
        ),
        models.FieldCondition(
            key="absolute_path",
            match=models.MatchValue(
                value=f"archon://projects/{project_name}/documents/{doc_id}"
            ),
        ),
    ]
)
```

3. Gradually backfill `document_id` for existing vectors

**Pros**:
- Backwards compatible
- Graceful migration
- Best query performance for new vectors

**Cons**:
- Temporary code complexity
- Mixed query patterns during migration

## Immediate Action Required

1. ✅ Update `test_e2e_ingestion_smoke.py` to use `absolute_path` filter
2. ✅ Update `test_kafka_consumer_vectorization.py` similarly
3. ✅ Document URI format in schema documentation
4. 🔄 Consider adding `document_id` field to indexing pipeline
5. 🔄 Add schema validation tests to catch field mismatches early

## Verification Commands

```bash
# Check collection status
curl http://localhost:6333/collections/archon_vectors | python3 -m json.tool

# Search for specific document by absolute_path
curl -X POST http://localhost:6333/collections/archon_vectors/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10,
    "with_payload": true,
    "with_vector": false,
    "filter": {
      "must": [
        {
          "key": "absolute_path",
          "match": {
            "value": "archon://projects/smoke_test/documents/smoke_test_c07bc8a6"
          }
        }
      ]
    }
  }' | python3 -m json.tool

# List all smoke_test documents
curl -X POST http://localhost:6333/collections/archon_vectors/points/scroll \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 100,
    "with_payload": true,
    "with_vector": false,
    "filter": {
      "must": [
        {
          "key": "project_name",
          "match": {
            "value": "smoke_test"
          }
        }
      ]
    }
  }' | python3 -m json.tool
```

## Related Files to Update

- `tests/integration/test_e2e_ingestion_smoke.py` - Fix document_id → absolute_path
- `tests/integration/test_kafka_consumer_vectorization.py` - Fix document_id → absolute_path  
- `services/intelligence/src/services/embeddings/embedding_service.py` - Consider adding document_id field
- `services/bridge/src/consumers/kafka_consumers.py` - Consider adding document_id field
- `docs/QDRANT_SCHEMA.md` - Document actual payload structure and URI format

---

**Investigation Complete**: The root cause is clear - tests search for a `document_id` field that doesn't exist in Qdrant. The field is actually `absolute_path` with a URI format.
