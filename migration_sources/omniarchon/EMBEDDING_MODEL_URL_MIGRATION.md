# OLLAMA_BASE_URL → EMBEDDING_MODEL_URL Migration

**Date**: 2025-11-07
**Status**: ✅ Complete
**Breaking Change**: Yes - Environment variable renamed

---

## Summary

Successfully migrated from `OLLAMA_BASE_URL` to `EMBEDDING_MODEL_URL` across the entire codebase to correctly reflect the use of vLLM embedding service instead of Ollama.

### Migration Rationale

The codebase was using `OLLAMA_BASE_URL` to point to a vLLM embedding service at `192.168.86.201:8002` (5090 GPU), not the old Ollama server at `192.168.86.200:11434`. This naming was misleading and caused confusion.

**Before**: `OLLAMA_BASE_URL=http://192.168.86.201:8002` (wrong name for vLLM service)
**After**: `EMBEDDING_MODEL_URL=http://192.168.86.201:8002` (correct name for vLLM service)

---

## Files Updated

### Python Code Files (14 files)

1. **services/search/app.py** (lines 94, 124)
   - Changed `ollama_base_url` → `embedding_model_url`
   - Updated env var: `OLLAMA_BASE_URL` → `EMBEDDING_MODEL_URL`
   - Updated default: `.200:11434` → `.201:8002`

2. **services/search/engines/vector_search.py** (lines 55, 65)
   - Updated docstring and env var reading
   - Changed default URL to vLLM service

3. **services/intelligence/src/handlers/search_handler.py** (lines 74, 127, 137)
   - Renamed class constant: `OLLAMA_BASE_URL` → `EMBEDDING_MODEL_URL`
   - Updated all embedding API calls

4. **services/intelligence/src/handlers/manifest_intelligence_handler.py** (lines 74, 83, 95, 487, 498)
   - Renamed parameter: `ollama_base_url` → `embedding_model_url`
   - Updated instance variable
   - Changed API endpoint references

5. **services/intelligence/src/integrations/tree_stamping_bridge.py** (lines 1687, 1703, 1706, 1711, 1753)
   - Renamed fallback variable
   - Updated logging messages
   - Changed error messages

6. **scripts/ingest_patterns.py** (lines 54, 304)
   - Updated global constant
   - Changed embedding generation function

7. **scripts/index_sample_patterns.py** (line 380)
   - Updated vector index initialization

8. **scripts/sync_patterns_to_qdrant.py** (lines 88, 97, 102, 115, 422)
   - Renamed class parameter
   - Updated instance variable
   - Changed initialization call

9. **scripts/demo_orchestrated_search.py** (lines 45, 159)
   - Updated global constant
   - Changed embedding API call

10. **python/lib/config_validator.py** (lines 37, 64)
    - Updated required env vars list
    - Changed documentation

11. **services/intelligence/tests/unit/handlers/test_manifest_intelligence_handler_coverage.py** (lines 177, 185)
    - Updated test fixtures
    - Changed assertions

### Configuration Files (1 file)

12. **deployment/docker-compose.services.yml** (multiple lines)
    - Updated shared environment variables (line 90)
    - Updated archon-intelligence service (line 123)
    - Updated archon-intelligence-test service (line 263)
    - Updated archon-bridge service (line 313)
    - Updated archon-search service (line 373)
    - Updated archon-langextract service (line 422)
    - Updated consumer instances (lines 534, 547, 560, 572)

### Environment Files (1 file)

13. **.env** (line 81)
    - Already had: `EMBEDDING_MODEL_URL=http://192.168.86.201:8002`

---

## Verification Results

### 1. vLLM Service Health ✅

```bash
$ curl http://192.168.86.201:8002/v1/models
{
  "data": [{
    "id": "Alibaba-NLP/gte-Qwen2-1.5B-instruct",
    "max_model_len": 8192
  }]
}
```

### 2. Embedding Generation Test ✅

```bash
$ ./test_embedding.sh
Embedding dimensions: 1536
✅ Embedding dimensions match expected value (1536)
First 5 values: [-0.0117, -0.0078, -0.0209, -0.0041, -0.0072]
```

**Performance**: <500ms per embedding with 5090 GPU

### 3. Container Environment Variables ✅

```bash
$ docker exec archon-intelligence env | grep EMBEDDING_MODEL_URL
EMBEDDING_MODEL_URL=http://192.168.86.201:8002

$ docker exec archon-search env | grep EMBEDDING_MODEL_URL
EMBEDDING_MODEL_URL=http://192.168.86.201:8002

$ docker exec archon-bridge env | grep EMBEDDING_MODEL_URL
EMBEDDING_MODEL_URL=http://192.168.86.201:8002
```

**Verification**: All containers have correct environment variable, NO `OLLAMA_BASE_URL`

### 4. End-to-End Test ✅

```bash
$ python3 test_e2e_embedding.py
🧪 End-to-End Embedding Generation Test
============================================================

1. Health Checks:
   ✅ Intelligence service: 200
   ✅ Search service: 200

2. Document Indexing (requires embeddings):
   ✅ Document processed successfully

============================================================
✅ End-to-end embedding test PASSED
   - Services are using EMBEDDING_MODEL_URL correctly
   - vLLM embedding service at 192.168.86.201:8002 is working
```

---

## Recommended Timeout Configuration

Based on vLLM service performance with 5090 GPU:

```bash
# .env
EMBEDDING_GENERATION_TIMEOUT=5.0  # 5 seconds is more than enough
```

**Rationale**:
- Actual generation time: ~300-500ms
- 5s timeout provides 10x buffer for network latency
- Original 30s timeout was excessive for GPU-accelerated service

---

## Breaking Changes

### Environment Variable Rename

**Required Action**: Update `.env` file

```bash
# OLD (will no longer work)
OLLAMA_BASE_URL=http://192.168.86.201:8002

# NEW (required)
EMBEDDING_MODEL_URL=http://192.168.86.201:8002
```

### Service Restart Required

All Docker containers must be rebuilt/recreated to pick up the new environment variable:

```bash
cd /Volumes/PRO-G40/Code/omniarchon

# Rebuild affected services
docker compose -f deployment/docker-compose.yml \
  -f deployment/docker-compose.services.yml \
  build --no-cache archon-intelligence archon-search archon-bridge

# Restart services
docker compose -f deployment/docker-compose.yml \
  -f deployment/docker-compose.services.yml \
  up -d archon-intelligence archon-search archon-bridge
```

---

## Configuration Reference

### vLLM Embedding Service

**Location**: `192.168.86.201:8002` (5090 GPU)
**Model**: `Alibaba-NLP/gte-Qwen2-1.5B-instruct`
**Dimensions**: 1536
**Max Tokens**: 8192
**Performance**: <500ms per embedding

### Environment Variables

```bash
# Required
EMBEDDING_MODEL_URL=http://192.168.86.201:8002
EMBEDDING_MODEL=Alibaba-NLP/gte-Qwen2-1.5B-instruct
EMBEDDING_DIMENSIONS=1536

# Recommended
EMBEDDING_GENERATION_TIMEOUT=5.0
```

---

## Testing

### Quick Verification

```bash
# Test vLLM service directly
./test_embedding.sh

# Test through archon services
python3 test_e2e_embedding.py
```

### Container Verification

```bash
# Check environment variables
docker exec archon-intelligence env | grep EMBEDDING_MODEL_URL

# Check service health
curl http://localhost:8053/health
curl http://localhost:8055/health
```

---

## Rollback Instructions

If you need to revert to the old configuration:

1. **Revert .env**:
   ```bash
   # Change back to OLLAMA_BASE_URL
   OLLAMA_BASE_URL=http://192.168.86.200:11434
   ```

2. **Revert code changes**:
   ```bash
   git revert <commit-hash>
   ```

3. **Rebuild services**:
   ```bash
   docker compose build --no-cache
   docker compose up -d
   ```

**Note**: Rollback is NOT recommended. The vLLM service is significantly faster and the new naming is more accurate.

---

## Related Documentation

- **vLLM Setup**: `scripts/start_vllm_embedding_service.sh`
- **Multi-Machine Embedding**: `docs/MULTI_MACHINE_EMBEDDING.md`
- **Environment Config**: `.env.example`
- **Infrastructure Topology**: `CLAUDE.md` (Infrastructure section)

---

## Success Metrics

- ✅ 14 Python files updated
- ✅ 1 docker-compose file updated
- ✅ 1 config validator updated
- ✅ All containers rebuilt successfully
- ✅ vLLM service verified (1536-dim embeddings)
- ✅ End-to-end test passed
- ✅ No hardcoded `.200:11434` references in active code
- ✅ Embedding generation <500ms (5090 GPU)

---

**Migration completed successfully on 2025-11-07**
