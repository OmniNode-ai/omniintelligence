# Qdrant Vector Search API Fix

**Date**: 2025-11-05
**Issue**: 400 Bad Request errors when querying Qdrant vector database
**Root Cause**: Embedding dimension mismatch (768 vs 1536)
**Status**: ✅ Fixed

---

## Problem

The `scripts/demo_orchestrated_search.py` script was failing with 400 errors when querying Qdrant:

```
Client error '400 Bad Request' for url 'http://localhost:6333/collections/archon_vectors/points/search'
```

## Root Cause Analysis

The issue was **NOT with the Qdrant API format** - it was with the embedding dimensions:

- **Qdrant Collection**: Configured for 1536 dimensions (Cosine distance)
- **Demo Script**: Hardcoded to use `nomic-embed-text` model → **768 dimensions**
- **Expected Model** (from .env): `rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest` → **1536 dimensions**

### The Architecture Issue

This violated the **Environment Variable Configuration Policy** documented in CLAUDE.md:

> ❌ **NEVER**: Hardcoded model names (use `EMBEDDING_MODEL` from env)
> ❌ **NEVER**: Hardcoded dimensions (use `EMBEDDING_DIMENSIONS` from env)

The script had **hardcoded values** instead of reading from environment:

```python
# WRONG - Hardcoded
ollama_url = "http://192.168.86.200:11434"
model = "nomic-embed-text"  # 768 dims
```

## Solution

### Changes Made

1. **Added Environment Variable Imports** (lines 29-32):
   ```python
   # Load configuration from environment (CRITICAL: No hardcoded values)
   EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest")
   EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
   OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.86.200:11434")
   ```

2. **Updated `_query_vector_search()` Method** (lines 126-199):
   - Use `EMBEDDING_MODEL` from environment instead of hardcoded `nomic-embed-text`
   - Use `OLLAMA_BASE_URL` from environment
   - Added dimension verification with clear error message
   - Use `QDRANT_URL` from environment
   - Added diagnostic fields to output: `embedding_model`, `dimension_verification`

3. **Enhanced Output Formatting** (lines 304-333):
   - Display embedding model being used
   - Display embedding dimensions
   - Show dimension verification status (✅ PASS / ❌ FAIL)
   - Handle empty content gracefully

### Key Code Changes

**Before**:
```python
ollama_url = "http://192.168.86.200:11434"
embed_response = await client.post(
    f"{ollama_url}/api/embeddings",
    json={"model": "nomic-embed-text", "prompt": query},
)
```

**After**:
```python
embed_response = await client.post(
    f"{OLLAMA_BASE_URL}/api/embeddings",
    json={"model": EMBEDDING_MODEL, "prompt": query},
)

# Verify dimensions
if len(embedding) != EMBEDDING_DIMENSIONS:
    raise ValueError(
        f"Embedding dimension mismatch: got {len(embedding)}, "
        f"expected {EMBEDDING_DIMENSIONS}. "
        f"Check EMBEDDING_MODEL and EMBEDDING_DIMENSIONS in .env"
    )
```

## Verification

### Test Results

```bash
$ source .env && python3 scripts/demo_orchestrated_search.py --query "orchestrator node"
```

**Output**:
```
🔢 QDRANT VECTOR DATABASE (Semantic Similarity)
--------------------------------------------------------------------------------
Status: ✅ Success
Results: 10 documents
Response Time: 453.98ms
Embedding Model: rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest
Embedding Dimensions: 1536
Dimension Check: ✅ PASS

Top Results:
  1. Unknown
     Score: 0.5847
     Preview: (No content in payload)

  2. Unknown
     Score: 0.5846
     Preview: (No content in payload)

  3. Unknown
     Score: 0.5409
     Preview: (No content in payload)
```

### Success Metrics

✅ **No 400 errors** - API calls succeed
✅ **10 results returned** - Real vector search results
✅ **Proper cosine similarity scores** - 0.5847, 0.5846, 0.5409, etc.
✅ **Correct dimensions** - 1536 (matches collection configuration)
✅ **Environment-driven** - Uses .env configuration, no hardcoded values
✅ **Dimension verification** - Automatic validation with clear error messages

### API Format Confirmation

The Qdrant search API format was **already correct**:

```python
POST http://localhost:6333/collections/archon_vectors/points/search
Content-Type: application/json

{
  "vector": [0.1, 0.2, ...],  # 1536 dimensions
  "limit": 10,
  "with_payload": true
}
```

The issue was **not the API format** - it was the **embedding dimensions**.

## Remaining Data Issue (Separate)

Some Qdrant vectors have **empty payloads** (file_path="Unknown", content=""). This is a **separate data indexing issue**, not an API issue:

- **Cause**: Documents were indexed without payload data
- **Impact**: Results show correct scores but missing metadata
- **Solution**: Re-index documents with complete payloads
- **Status**: Not addressed in this fix (API fix only)

**Note**: Some vectors DO have payloads (e.g., `model_service_orchestrator.py`, `README.md`), so the payload issue is partial, not complete.

## Configuration Files

### .env (Correct Configuration)
```bash
EMBEDDING_MODEL=rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest
EMBEDDING_DIMENSIONS=1536
OLLAMA_BASE_URL=http://192.168.86.200:11434
QDRANT_URL=http://localhost:6333
```

### Qdrant Collection Info
```json
{
  "vectors_count": 6508,
  "config": {
    "params": {
      "vectors": {
        "size": 1536,
        "distance": "Cosine"
      }
    }
  }
}
```

## Lessons Learned

1. **Always Check Environment Variables First**: The .env file contained the correct configuration all along
2. **Hardcoded Values Break Configurability**: Hardcoded model names prevent environment-specific configuration
3. **Dimension Mismatches Are Silent**: Qdrant returns generic 400 errors, not dimension-specific errors
4. **Architecture Policies Exist For A Reason**: The Environment Variable Configuration Policy prevented this exact issue
5. **Test With Correct Tools**: Using curl with the correct model confirmed the API format was fine

## Related Documentation

- **Environment Variable Policy**: `CLAUDE.md` (lines 13-48)
- **ONEX Configuration**: `.env.example` (comprehensive template)
- **Infrastructure Topology**: `CLAUDE.md` (lines 171+)

---

**Fix Applied**: 2025-11-05
**File Modified**: `/Volumes/PRO-G40/Code/omniarchon/scripts/demo_orchestrated_search.py`
**Test Status**: ✅ Passing (no 400 errors, 10 results with valid scores)
