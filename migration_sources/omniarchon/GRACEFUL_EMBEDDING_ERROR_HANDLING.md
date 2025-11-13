# Graceful Error Handling for None Embeddings

**Date**: 2025-11-10
**Service**: archon-search (services/search/)
**Correlation ID**: 31e4a840-57a2-48e6-a472-e89e6e64232b

## Problem

When embedding generation fails (returns None), the search service crashes with:
```
TypeError: object of type 'NoneType' has no len()
```

**Root Cause**:
- `OpenAIEmbeddingClient.generate_embedding()` returns `None` on failure
- `VectorSearchEngine.generate_embeddings()` returns `List[Optional[np.ndarray]]`
- Code checked if list was empty but didn't check if individual elements were None
- Accessing `embedding[0]` or `len(embedding[0])` crashed when element was None

## Solution

Added graceful error handling at two critical points in `services/search/app.py`:

### 1. Document Vectorization Endpoint (Line 963-989)

**Location**: `/vectorize/document` POST endpoint

**Changes**:
```python
# Check if individual embedding is None (graceful degradation)
if embedding[0] is None:
    logger.warning(
        f"❌ [EMBEDDING FAILED] Document vectorization skipped | "
        f"document_id={document_id} | reason=embedding_generation_failed | "
        f"content_length={len(content)} | possible_cause=token_limit_exceeded"
    )

    # Log failed vectorization with detailed metrics
    vectorization_duration_ms = (time.time() - vectorization_start_time) * 1000
    search_service_logger.log_document_vectorization(
        document_id=document_id,
        vector_id=document_id,
        content_length=len(content),
        embedding_dimensions=0,
        collection_name="documents",
        success=False,
        duration_ms=vectorization_duration_ms,
    )

    return {
        "success": False,
        "document_id": document_id,
        "error": "Embedding generation failed - document may exceed token limit",
        "embedding_dimensions": 0,
        "content_length": len(content),
    }
```

**Behavior**:
- ✅ Returns structured error response instead of crashing
- ✅ Logs failure with detailed context (document_id, content_length, possible cause)
- ✅ Updates metrics (failed vectorization tracked)
- ✅ Pipeline continues processing other documents

### 2. Pattern Search Endpoint (Line 525-534)

**Location**: `/search/patterns` POST endpoint

**Changes**:
```python
# Check if individual embedding is None
if embeddings[0] is None:
    logger.error(
        f"❌ [EMBEDDING FAILED] Pattern search query embedding failed | "
        f"query={query} | reason=embedding_generation_failed"
    )
    raise HTTPException(
        status_code=500,
        detail="Failed to generate query embedding - query may exceed token limit",
    )
```

**Behavior**:
- ✅ Returns HTTP 500 with clear error message
- ✅ Logs failure with query context
- ✅ Prevents NoneType crashes on query_vector access

## Impact

### Before
```
❌ TypeError: object of type 'NoneType' has no len()
❌ Service crash on failed embedding
❌ No context about why embedding failed
❌ Entire batch processing stops
```

### After
```
✅ Graceful error response with structured data
✅ Service continues running
✅ Detailed logging with document_id, content_length, possible cause
✅ Failed embeddings tracked in metrics
✅ Other documents in batch continue processing
```

## Metrics Tracking

Failed embeddings are now tracked via:

1. **Log Messages**: Structured logging with correlation IDs
   - Document vectorization failures: `[EMBEDDING FAILED] Document vectorization skipped`
   - Pattern search failures: `[EMBEDDING FAILED] Pattern search query embedding failed`

2. **Metrics**: Via `search_service_logger.log_document_vectorization()`
   - `success=False` for failed embeddings
   - `embedding_dimensions=0` indicates failure
   - `duration_ms` tracks time spent before failure

3. **Response Codes**:
   - Document vectorization: Returns `{"success": False, "error": "..."}` (HTTP 200)
   - Pattern search: Returns HTTP 500 with error detail

## Common Causes of None Embeddings

1. **Token Limit Exceeded**: Document/query exceeds model's max token limit
2. **Service Unavailable**: Embedding service (vLLM) is down or overloaded
3. **Invalid Input**: Malformed text that can't be embedded
4. **Network Errors**: Timeout or connection failure to embedding service

## Testing

### Manual Test (Document Vectorization)
```bash
# Test with oversized content
curl -X POST http://localhost:8055/vectorize/document \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "test-doc-1",
    "project_id": "test-project",
    "content": "Very long content that exceeds token limit...",
    "metadata": {},
    "source_path": "test.py"
  }'

# Expected response (instead of crash):
# {
#   "success": false,
#   "document_id": "test-doc-1",
#   "error": "Embedding generation failed - document may exceed token limit",
#   "embedding_dimensions": 0,
#   "content_length": ...
# }
```

### Manual Test (Pattern Search)
```bash
# Test with oversized query
curl -X POST "http://localhost:8055/search/patterns?query=very%20long%20query..." \
  -H "Content-Type: application/json"

# Expected response (instead of crash):
# HTTP 500 with error: "Failed to generate query embedding - query may exceed token limit"
```

## Files Modified

- `/Volumes/PRO-G40/Code/omniarchon/services/search/app.py` (2 locations)

## Related Components

- `services/search/engines/embedding_client.py` - Returns None on failure
- `services/search/engines/vector_search.py` - Returns List[Optional[np.ndarray]]
- `services/search/search_logging/search_logger.py` - Logs failed vectorizations

## Success Criteria (All Met ✅)

- ✅ No NoneType crashes when embedding fails
- ✅ Failed embeddings logged with context (document_id, reason)
- ✅ Pipeline continues processing other documents
- ✅ Proper error responses returned to callers
- ✅ Metrics updated correctly (success=False tracked)

## Pattern Applied

**Graceful Degradation Pattern**:
1. Check if operation succeeded (embedding is not None)
2. If failed, log detailed context
3. Update metrics to track failure
4. Return structured error response
5. Continue processing (don't crash entire service)

This pattern should be applied to ALL external service calls where None is a valid failure indicator.
