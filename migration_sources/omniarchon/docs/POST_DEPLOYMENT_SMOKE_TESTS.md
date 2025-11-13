# Post-Deployment Smoke Tests

## Overview

Critical smoke tests that **MUST pass** after any Docker rebuild before starting ingestion or production deployment. These tests validate that all core functionality is working correctly and prevent deploying broken services.

**Historical Context**: These tests were created after discovering a critical vectorization bug where `/process/document` returned success but didn't actually create vectors in Qdrant. The smoke test suite would have caught this bug immediately.

## Quick Start

```bash
# Run all smoke tests (recommended)
./scripts/verify_docker_build.sh

# Quick validation (essential tests only, ~30 seconds)
./scripts/verify_docker_build.sh --quick

# Detailed output for debugging
./scripts/verify_docker_build.sh --verbose
```

## Test Coverage

### 1. Service Health Checks (`test_all_services_healthy`)

**What it tests**: All critical services respond to health endpoints
- archon-intelligence (8053)
- archon-bridge (8054)
- archon-search (8055)

**Pass criteria**:
- All services return 200 OK
- Response time < 5 seconds

**Failure**: Service unreachable or returning errors

---

### 2. Database Accessibility (`test_databases_accessible`)

**What it tests**: All databases are accessible and responsive
- Qdrant (vector database)
- Memgraph (knowledge graph)
- PostgreSQL (pattern traceability)

**Pass criteria**:
- All databases respond to queries
- Query time < 5 seconds
- `archon_vectors` collection exists in Qdrant

**Failure**: Database unreachable or timeout

---

### 3. Kafka Connectivity (`test_kafka_connectivity`)

**What it tests**: Event bus is accessible for async operations
- Connection to Kafka/Redpanda bootstrap servers
- Topic listing (admin operation)
- Critical topics exist

**Pass criteria**:
- Kafka responds to admin queries
- Critical topics present

**Failure**: Kafka unreachable or topics missing

---

### 4. **Document Processing Creates Vector** (`test_document_processing_creates_vector`) ⚠️ CRITICAL

**What it tests**: The bug we had - `/process/document` actually creates vectors

This is **THE MOST CRITICAL TEST** that would have caught the vectorization bug.

**Test Flow**:
1. Create unique test document via `POST /process/document`
2. Verify endpoint returns success (200 OK)
3. Query Qdrant to confirm vector actually exists
4. Verify vector has correct dimensions (1536)
5. Verify vector can be retrieved by document_id

**Pass criteria**:
- `/process/document` returns 200 OK
- Vector exists in Qdrant with correct document_id
- Vector has 1536 dimensions
- Vector retrievable via scroll API

**Failure (THE BUG)**:
```
❌ VECTORIZATION BUG DETECTED: /process/document returned success
but NO vector found in Qdrant for document_id=xxx
```

This failure indicates:
- Endpoint claims success but doesn't actually index
- Embedding generation failing silently
- Qdrant adapter not being called
- Critical data loss occurring

**Immediate Action on Failure**:
1. Check intelligence service logs for embedding errors
2. Verify EMBEDDING_MODEL_URL configuration
3. Test vLLM embedding service directly: `curl http://192.168.86.201:8002/health`
4. Verify Qdrant adapter initialization in logs
5. DO NOT proceed with ingestion until fixed

---

### 5. Basic RAG Query (`test_basic_rag_query_works`)

**What it tests**: End-to-end RAG query functionality
- Search endpoint responds
- Returns valid results
- Performance within threshold

**Pass criteria**:
- `/search/rag` returns 200 OK
- Response contains `results` array
- Query time < 10 seconds

**Failure**: RAG pipeline broken

---

### 6. Performance Baseline (`test_performance_baseline`)

**What it tests**: System meets performance thresholds
- Service health endpoints < 5s
- Database queries < 5s
- Document processing < 30s
- RAG queries < 10s

**Pass criteria**: All operations meet performance thresholds

**Failure**: Performance regression detected

---

### 7. Intelligence → Qdrant Pipeline (`test_intelligence_to_qdrant_pipeline`)

**What it tests**: Complete integration across services
- Document submission to intelligence service
- Vector creation in Qdrant
- Vector searchability via search service

**Pass criteria**:
- Document processed successfully
- Vector exists in Qdrant
- Vector searchable via RAG

**Failure**: Pipeline broken at any stage

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | ✅ All tests passed | Safe to deploy/ingest |
| 1 | ❌ Tests failed | DO NOT DEPLOY - fix issues first |
| 2 | ⚠️  Script error | Check script configuration |

## Performance Thresholds

| Operation | Threshold | Rationale |
|-----------|-----------|-----------|
| Service health check | 5s | Health endpoints should be fast |
| Document processing | 30s | Includes embedding + indexing |
| Vector creation | 10s | Async indexing should be quick |
| RAG query | 10s | User-facing search must be responsive |
| Database query | 5s | Simple queries should be fast |

## Integration with CI/CD

### Docker Build Workflow

```bash
# 1. Build containers
docker compose build

# 2. Start services
docker compose up -d

# 3. Wait for services to be ready (30s)
sleep 30

# 4. Run smoke tests
./scripts/verify_docker_build.sh

# 5. If tests pass, proceed with deployment
# If tests fail, DO NOT DEPLOY
```

### Pre-Ingestion Workflow

```bash
# Before running bulk_ingest_repository.py:

# 1. Verify services are healthy
./scripts/verify_docker_build.sh

# 2. Only proceed if exit code = 0
if [ $? -eq 0 ]; then
    python3 scripts/bulk_ingest_repository.py /path/to/repo
else
    echo "❌ Smoke tests failed - fix issues before ingestion"
    exit 1
fi
```

## Running Individual Tests

```bash
# Run specific test
pytest tests/integration/test_post_deployment_smoke.py::TestPostDeploymentSmoke::test_document_processing_creates_vector -v

# Run only critical tests
pytest tests/integration/test_post_deployment_smoke.py -m critical -v

# Run with detailed logging
pytest tests/integration/test_post_deployment_smoke.py -v --log-cli-level=DEBUG

# Run without timeout (for debugging)
pytest tests/integration/test_post_deployment_smoke.py --timeout=0 -v
```

## Troubleshooting

### Test: `test_document_processing_creates_vector` fails

**Symptom**: Document processed but vector not found in Qdrant

**Possible Causes**:
1. Embedding service unreachable
   - Check: `curl http://192.168.86.201:8002/health`
   - Fix: Verify vLLM service is running

2. EMBEDDING_MODEL_URL misconfigured
   - Check: `docker exec archon-intelligence env | grep EMBEDDING_MODEL_URL`
   - Fix: Update `.env` and rebuild

3. Qdrant adapter not initialized
   - Check: `docker logs archon-intelligence | grep -i qdrant`
   - Fix: Verify Qdrant URL in `.env`

4. Async processing delay
   - Check: Test waits 2s - may need longer
   - Fix: Increase sleep duration in test

### Test: `test_all_services_healthy` fails

**Symptom**: Service returns non-200 status or unreachable

**Action**:
```bash
# Check service logs
docker compose logs archon-intelligence
docker compose logs archon-bridge
docker compose logs archon-search

# Restart specific service
docker compose restart archon-intelligence

# Rebuild if needed
docker compose down
docker compose build
docker compose up -d
```

### Test: `test_databases_accessible` fails

**Symptom**: Database connection timeout or error

**Action**:
```bash
# Check Qdrant
curl http://localhost:6333/collections

# Check Memgraph
docker exec omniarchon-memgraph-1 bash -c "echo 'MATCH (n) RETURN count(n);' | mgconsole"

# Check PostgreSQL
psql -h 192.168.86.200 -p 5436 -U postgres -d omninode_bridge -c "SELECT 1"
```

### Test: `test_performance_baseline` fails

**Symptom**: Operations exceed performance thresholds

**Action**:
1. Check system load: `docker stats`
2. Check logs for errors causing slowdowns
3. May indicate:
   - Resource constraints (CPU/memory)
   - Network issues
   - Database performance degradation
   - Service bottlenecks

## Benefits

1. **Prevents Broken Deployments**: Catches issues before production
2. **Catches Silent Failures**: Would have caught the vectorization bug
3. **Performance Monitoring**: Detects regressions immediately
4. **Integration Validation**: Tests cross-service functionality
5. **Fast Feedback**: Completes in ~60 seconds
6. **CI/CD Ready**: Automatable in deployment pipelines

## Maintenance

### Adding New Tests

When adding new critical functionality:

1. Add smoke test to `test_post_deployment_smoke.py`
2. Mark with `@pytest.mark.smoke` and `@pytest.mark.critical` if essential
3. Ensure test completes within 60s total
4. Document in this file

### Updating Thresholds

If performance thresholds need adjustment:

1. Update `PERFORMANCE_THRESHOLDS` dict in test file
2. Document rationale in this file
3. Ensure thresholds are realistic but strict

---

**Last Updated**: 2025-11-12
**Test File**: `tests/integration/test_post_deployment_smoke.py`
**Script**: `scripts/verify_docker_build.sh`
