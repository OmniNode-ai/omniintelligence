# Testing Protocol - Mandatory Pre-Deployment Validation

**Version**: 1.0.0
**Last Updated**: 2025-11-12
**Status**: MANDATORY for all deployments, commits, and ingestion operations

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Hierarchy](#testing-hierarchy)
3. [Before ANY Commit](#before-any-commit-mandatory)
4. [Before ANY Deployment](#before-any-deployment-mandatory)
5. [Before Bulk Ingestion](#before-bulk-ingestion-mandatory)
6. [After Docker Rebuild](#after-docker-rebuild-mandatory)
7. [CI/CD Integration](#cicd-integration)
8. [Test Execution Time Budgets](#test-execution-time-budgets)
9. [Debugging Failed Tests](#debugging-failed-tests)
10. [The Vectorization Bug Case Study](#the-vectorization-bug-case-study)
11. [Enforcement](#enforcement)
12. [Test Maintenance](#test-maintenance)
13. [Memgraph Label Constants](#memgraph-label-constants)

---

## Overview

### Why Testing is Critical

**The Vectorization Bug (November 2025)** demonstrated the catastrophic impact of insufficient testing:

- ✅ **Symptom**: `/process/document` endpoint returned `200 OK`
- ✅ **Symptom**: Response JSON claimed "document processed successfully"
- ❌ **Reality**: NO vector was actually created in Qdrant
- ❌ **Impact**: 25,249 documents indexed but ZERO vectors stored
- ❌ **Root Cause**: No test verified that successful API response → actual vector creation

**Result**: Complete ingestion pipeline appeared functional but was silently failing at the critical vectorization step.

### Core Testing Principle

> **Success response ≠ Successful execution**
>
> Always verify end state, not just API response codes.

This protocol ensures that every deployment, commit, and bulk operation is validated against **actual data state**, not just HTTP status codes.

---

## Testing Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│ Level 1: Pre-Commit Tests (< 60s)                              │
│ Purpose: Fast feedback loop during development                  │
│ Scope: Unit tests for changed components + smoke tests         │
│ Execution: Automated via pre-commit hooks                       │
│ Requirement: MUST pass before commit                            │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ Level 2: Pre-Deployment Tests (< 5min)                         │
│ Purpose: Smoke tests to validate service health                 │
│ Scope: Critical integration paths + service connectivity        │
│ Execution: Manual via ./scripts/verify_docker_build.sh          │
│ Requirement: MUST pass before any deployment                    │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ Level 3: Full Integration Tests (< 30min)                      │
│ Purpose: Complete validation of all services and data flow      │
│ Scope: All integration tests including Kafka → Vector → Graph   │
│ Execution: Manual via pytest or CI/CD                           │
│ Requirement: MUST pass before production release                │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ Level 4: E2E System Tests (< 1hr)                              │
│ Purpose: End-to-end validation with real data volumes           │
│ Scope: Complete ingestion pipeline with multi-file repos        │
│ Execution: Manual via test suite or staging environment         │
│ Requirement: MUST pass before bulk ingestion operations         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Before ANY Commit (Mandatory)

### Automated Pre-Commit Validation

Pre-commit hooks automatically run essential tests before every commit:

```bash
# Automated via Git pre-commit hook (already configured)
# Runs automatically on: git commit

# Manual execution to verify:
pre-commit run --all-files
```

**What Gets Tested** (see `.pre-commit-config.yaml`):

1. ✅ **Code Formatting**: Black + isort for consistent style
2. ✅ **File Hygiene**: Trailing whitespace, EOF fixers, merge conflict detection
3. ✅ **Smoke Tests**: Unit tests for intelligence + services (`tests/unit/intelligence`, `tests/unit/services`)
4. ✅ **Incremental Stamping**: ONEX metadata updates for changed files

### Manual Verification (Critical Path)

**Before committing changes to document processing, vectorization, or Kafka consumers**:

```bash
# 1. Run the CRITICAL vectorization test
pytest tests/integration/test_post_deployment_smoke.py::TestPostDeploymentSmoke::test_document_processing_creates_vector -v

# Expected output:
# ✅ Document processed successfully
# ✅ Vector found in Qdrant (dimensions: 1536)
# ✅ Vector metadata correct: document_id=<id>
# ✅ Document processing creates vector (CRITICAL TEST PASSED)

# 2. If test FAILS: DO NOT COMMIT
# Fix the issue first, then re-run the test
```

### Time Budget

- **Target**: 30 seconds
- **Maximum**: 60 seconds
- **Exceeded?**: Optimize slow tests or move to integration suite

---

## Before ANY Deployment (Mandatory)

### Step 1: Run Unit Tests

```bash
# Fast unit tests (< 30s)
pytest tests/unit -v

# Expected: All tests pass
# If ANY fail: Fix before proceeding
```

### Step 2: Run Deployment Smoke Tests

```bash
# Automated smoke test runner (< 5 min)
./scripts/verify_docker_build.sh

# Alternative: Direct pytest execution
pytest tests/integration/test_post_deployment_smoke.py -v -m smoke

# Expected output:
# ✅ ALL SMOKE TESTS PASSED
# Status: SAFE TO DEPLOY
```

**What This Validates**:

1. ✅ All services respond to health checks (`/health` endpoints)
2. ✅ All databases accessible (Qdrant, Memgraph, PostgreSQL)
3. ✅ Kafka/Redpanda connectivity
4. ✅ **CRITICAL**: Document processing creates vectors (the bug we had)
5. ✅ Basic RAG query functionality
6. ✅ Performance baselines met

### Step 3: Run Critical Integration Tests

```bash
# Kafka consumer vectorization tests (< 10 min)
pytest tests/integration/test_kafka_consumer_vectorization.py -v

# Expected tests:
# ✅ test_consumer_creates_vector_and_node
# ✅ test_consumer_handles_vectorization_failure
# ✅ test_idempotency_same_event_twice
# ✅ test_multiple_files_batch_processing
# ✅ test_vector_dimensions_correctness

# Verify environment health (< 2 min)
python3 scripts/verify_environment.py --verbose

# Expected output:
# ✅ vLLM Embedding Service          Service healthy (33ms)
# ✅ archon-intelligence             Healthy (278ms)
# ✅ archon-bridge                   Healthy (196ms)
# ✅ archon-search                   Healthy (264ms)
# ✅ Memgraph Graph Structure        Graph healthy: 67,277 nodes, 15,666 relationships
# ✅ Language Field Coverage         Language coverage excellent: 100.0% overall
# ✅ project_name Consistency        All files have project_name
# ✅ Qdrant Vector Coverage          Vectors present
# ✅ File Tree Graph                 Tree graph healthy: 0 orphans
# 🎉 Overall Status: PASS
```

### Step 4: Decision Point

```bash
# If ALL tests pass:
echo "✅ SAFE TO DEPLOY"
# Proceed with deployment

# If ANY test fails:
echo "❌ DO NOT DEPLOY"
# 1. Review failure logs
# 2. Check service logs: docker compose logs <service-name>
# 3. Fix issues
# 4. Rebuild: docker compose build && docker compose up -d
# 5. Re-run ALL tests from Step 1
```

---

## Before Bulk Ingestion (Mandatory)

**CRITICAL**: Never run bulk ingestion without validating the pipeline first!

### Step 1: Run Deployment Checks

```bash
# Run complete deployment validation (see "Before ANY Deployment" section)
./scripts/verify_docker_build.sh
pytest tests/integration/test_kafka_consumer_vectorization.py -v
python3 scripts/verify_environment.py --verbose

# ALL must pass before proceeding
```

### Step 2: Run E2E Smoke Test with Single File

```bash
# End-to-end ingestion smoke test (< 2 min)
pytest tests/integration/test_e2e_ingestion_smoke.py::TestE2EIngestionSmoke::test_single_file_ingestion_complete_pipeline -v

# Expected flow:
# 📋 Step 1: Verifying service health...
#   ✅ intelligence: healthy
#   ✅ bridge: healthy
#   ✅ search: healthy
# 📤 Step 2: Publishing Kafka event...
#   ✅ Event published: correlation_id=<id>
# 🔍 Step 3: Waiting for vector in Qdrant...
#   ✅ Vector found in 4.23s
# 🔬 Step 4: Verifying vector dimensions...
#   ✅ Vector dimensions correct: 1536
# 🔍 Step 5: Waiting for node in Memgraph...
#   ✅ Node found in 5.67s
# 🌳 Step 6: Verifying file tree structure...
#   ✅ File tree structure is valid
# ⏱️  Step 7: Performance summary:
#   ✅ Performance target met
# ✅ E2E Ingestion Smoke Test PASSED
```

### Step 3: Proceed with Bulk Ingestion (Only if Step 1 & 2 Pass)

```bash
# Small repository test first (< 100 files)
python3 scripts/bulk_ingest_repository.py /path/to/small/repo \
  --project-name test-project \
  --kafka-servers 192.168.86.200:29092

# Monitor progress:
# - Check logs: tail -f logs/bulk_ingest_*.log
# - Watch consumer: docker logs -f archon-kafka-consumer
# - Verify vectors: curl http://localhost:6333/collections/archon_vectors

# If successful, proceed with full repository ingestion
python3 scripts/bulk_ingest_repository.py /path/to/full/repo \
  --project-name production-project \
  --kafka-servers 192.168.86.200:29092
```

### Step 4: Post-Ingestion Validation

```bash
# Verify data integrity after ingestion
python3 scripts/validate_data_integrity.py --verbose

# Expected:
# ✅ Memgraph: Document nodes found
# ✅ Qdrant: Vector collection coverage
# ✅ Search: File path retrieval working
# ✅ Metadata: Filtering functional
# Overall Status: Healthy (4/4 components working)

# Check for orphaned files
python3 scripts/verify_environment.py --verbose | grep -i orphan

# Expected: 0 orphans
```

---

## After Docker Rebuild (Mandatory)

**Any time you run `docker compose build` or change service configurations**:

### Step 1: Rebuild Services

```bash
# Rebuild Docker images
docker compose build

# Start services
docker compose up -d

# Wait for services to stabilize (30 seconds minimum)
sleep 30

# Verify all containers running
docker ps --filter "name=archon" --format "table {{.Names}}\t{{.Status}}"

# Expected: All services show "Up" status
```

### Step 2: Validate Before Use

```bash
# MANDATORY validation script
./scripts/verify_docker_build.sh

# Expected output:
# ✅ ALL SMOKE TESTS PASSED
# Status: SAFE TO DEPLOY

# If fails:
# ❌ SMOKE TESTS FAILED
# Status: DO NOT DEPLOY
# → DO NOT PROCEED - fix issues first
```

### Step 3: Verify Data Layer Health

```bash
# Check Qdrant collection
curl http://localhost:6333/collections/archon_vectors

# Expected: Collection exists with correct configuration

# Check Memgraph connectivity
docker exec archon-memgraph echo "RETURN 1;" | cypher-shell

# Expected: Returns 1

# Verify embedding service
curl http://localhost:8053/health

# Expected: {"status": "healthy"}
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Pre-Merge Validation

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Run unit tests
        run: |
          poetry run pytest tests/unit -v --timeout=60
        timeout-minutes: 2

      - name: Start services
        run: |
          docker compose up -d
          sleep 30

      - name: Run smoke tests
        run: |
          ./scripts/verify_docker_build.sh
        timeout-minutes: 5

      - name: Run integration tests
        run: |
          poetry run pytest tests/integration -v --timeout=300
        timeout-minutes: 10

      - name: Upload test logs
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: test-logs
          path: logs/
```

### GitLab CI Pipeline

```yaml
stages:
  - test-unit
  - test-smoke
  - test-integration

variables:
  KAFKA_BOOTSTRAP_SERVERS: "192.168.86.200:29092"
  QDRANT_URL: "http://localhost:6333"

unit-tests:
  stage: test-unit
  script:
    - poetry install
    - poetry run pytest tests/unit -v --timeout=60
  timeout: 2m
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == "main"'

smoke-tests:
  stage: test-smoke
  services:
    - docker:dind
  script:
    - docker compose up -d
    - sleep 30
    - ./scripts/verify_docker_build.sh
  timeout: 5m
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'

integration-tests:
  stage: test-integration
  services:
    - docker:dind
  script:
    - docker compose up -d
    - sleep 30
    - poetry run pytest tests/integration -v --timeout=300
  timeout: 10m
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
    - when: manual
      allow_failure: true
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any

    stages {
        stage('Unit Tests') {
            steps {
                sh 'poetry run pytest tests/unit -v --timeout=60'
            }
            timeout(time: 2, unit: 'MINUTES')
        }

        stage('Start Services') {
            steps {
                sh 'docker compose up -d'
                sh 'sleep 30'
            }
        }

        stage('Smoke Tests') {
            steps {
                sh './scripts/verify_docker_build.sh'
            }
            timeout(time: 5, unit: 'MINUTES')
        }

        stage('Integration Tests') {
            steps {
                sh 'poetry run pytest tests/integration -v --timeout=300'
            }
            timeout(time: 10, unit: 'MINUTES')
        }
    }

    post {
        failure {
            archiveArtifacts artifacts: 'logs/**', allowEmptyArchive: true
        }
        always {
            sh 'docker compose down'
        }
    }
}
```

---

## Test Execution Time Budgets

| Test Suite | Target Time | Max Time | Timeout Action |
|------------|-------------|----------|----------------|
| **Pre-commit hooks** | 30s | 60s | Fail commit, optimize tests |
| **Unit tests** | 20s | 60s | Fail fast, investigate slow tests |
| **Smoke tests** | 2min | 5min | Fail deployment, check service health |
| **Integration tests** | 10min | 30min | Skip non-critical tests, investigate |
| **Full E2E tests** | 30min | 1hr | Run in background, get coffee |
| **Bulk ingestion validation** | 5min | 10min | Test with smaller sample first |

### Performance Thresholds (from `test_post_deployment_smoke.py`)

```python
PERFORMANCE_THRESHOLDS = {
    "service_health_check": 5.0,   # Health endpoint response time (seconds)
    "document_processing": 30.0,   # /process/document complete time
    "vector_creation": 10.0,       # Time for vector to appear in Qdrant
    "rag_query": 10.0,             # RAG query response time
    "database_query": 5.0,         # Database query response time
}
```

### What to Do When Tests Are Too Slow

1. **Identify bottleneck**:
   ```bash
   pytest tests/ -v --durations=10
   ```

2. **Optimize or skip**:
   ```python
   @pytest.mark.slow
   @pytest.mark.skipif(os.getenv("SKIP_SLOW_TESTS"), reason="Slow test skipped")
   def test_expensive_operation():
       ...
   ```

3. **Move to appropriate level**:
   - Pre-commit: Only critical unit tests
   - Smoke: Only essential integration paths
   - Full integration: Everything else

---

## Debugging Failed Tests

### Common Failures and Solutions

#### 1. Service Health Check Failed

```bash
# Symptom:
# ❌ archon-intelligence: Connection failed

# Debug:
docker ps --filter "name=archon-intelligence"
docker logs archon-intelligence --tail 100

# Solution:
docker compose restart archon-intelligence
sleep 10
./scripts/verify_docker_build.sh
```

#### 2. Vector Not Created in Qdrant

```bash
# Symptom:
# ❌ VECTORIZATION BUG DETECTED: /process/document returned success
#    but NO vector found in Qdrant

# Debug:
# 1. Check intelligence service logs
docker logs archon-intelligence --tail 200 | grep -i "vector\|qdrant\|embedding"

# 2. Check Qdrant collection
curl http://localhost:6333/collections/archon_vectors

# 3. Verify embedding service
curl http://localhost:8053/health

# Common causes:
# - Embedding service not running
# - Qdrant connection failed
# - Document processing error not logged
# - Async vectorization not awaited

# Solution:
# 1. Restart embedding service
# 2. Check EMBEDDING_DIMENSIONS in .env matches Qdrant collection
# 3. Review intelligence service code for async/await issues
```

#### 3. Kafka Consumer Not Processing Events

```bash
# Symptom:
# Events published but not consumed within timeout

# Debug:
# 1. Check consumer logs
docker logs archon-kafka-consumer --tail 200

# 2. Verify Kafka connectivity
docker exec archon-kafka-consumer sh -c \
  'rpk topic list --brokers omninode-bridge-redpanda:9092'

# 3. Check consumer group lag
docker exec omninode-bridge-redpanda \
  rpk group describe archon-consumer-group

# Common causes:
# - Consumer not running
# - Wrong Kafka topic configuration
# - Consumer group stuck
# - Event deserialization error

# Solution:
# 1. Restart consumer: docker compose restart archon-kafka-consumer
# 2. Reset consumer offset if stuck
# 3. Verify KAFKA_BOOTSTRAP_SERVERS configuration
```

#### 4. File Tree Not Built (Orphaned Files)

```bash
# Symptom:
# ⚠️ File tree structure incomplete (may still be building)
# Or: Found X orphaned files

# Debug:
python3 scripts/verify_environment.py --verbose | grep -A 10 "File Tree Graph"

# Solution:
# 1. Tree building is async - wait longer (30s)
# 2. Check DirectoryIndexer logs
# 3. Manually trigger tree rebuild if needed
```

### Log Locations

| Component | Log Location | Command |
|-----------|-------------|---------|
| **Intelligence Service** | Docker logs | `docker logs archon-intelligence -f` |
| **Bridge Service** | Docker logs | `docker logs archon-bridge -f` |
| **Kafka Consumer** | Docker logs | `docker logs archon-kafka-consumer -f` |
| **Smoke Tests** | `logs/smoke_test_*.log` | `tail -f logs/smoke_test_*.log` |
| **Integration Tests** | pytest output + `logs/` | `pytest -v --log-file=logs/test.log` |
| **Bulk Ingestion** | `logs/bulk_ingest_*.log` | `tail -f logs/bulk_ingest_*.log` |
| **Aggregated Logs** | All services | `./scripts/logs.sh all` |

### Service Health Checks

```bash
# Quick health check all services
for service in intelligence bridge search; do
  echo -n "$service: "
  curl -sf http://localhost:805${service:0:1}/health && echo "✅" || echo "❌"
done

# Database connectivity
curl -sf http://localhost:6333/collections && echo "✅ Qdrant" || echo "❌ Qdrant"
docker exec archon-memgraph echo "RETURN 1;" | cypher-shell && echo "✅ Memgraph" || echo "❌ Memgraph"

# Kafka connectivity
docker exec omninode-bridge-redpanda rpk cluster info && echo "✅ Kafka" || echo "❌ Kafka"
```

---

## The Vectorization Bug Case Study

### What Happened

**Timeline**:
- **Date**: November 2025
- **Symptom**: Bulk ingestion completed successfully, but RAG queries returned empty results
- **Investigation**: Qdrant collection had 0 vectors despite 25,249 documents processed
- **Root Cause**: `/process/document` endpoint returned `200 OK` without actually creating vectors

### The Bug in Detail

**Faulty Code Pattern** (simplified):

```python
@app.post("/process/document")
async def process_document(document: DocumentRequest):
    try:
        # Step 1: Validate document ✅
        validate_document(document)

        # Step 2: Extract entities ✅
        entities = extract_entities(document.content)

        # Step 3: Create Memgraph node ✅
        await create_node_in_memgraph(document, entities)

        # Step 4: Generate embedding ❌ (SKIPPED DUE TO ERROR)
        embedding = await generate_embedding(document.content)
        # ↑ This call failed silently, but exception was caught

        # Step 5: Store in Qdrant ❌ (NEVER EXECUTED)
        if embedding:  # ← This condition was False, so skipped
            await qdrant_client.upsert(embedding)

        # Return success regardless ❌
        return {"status": "success", "message": "Document processed"}

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        # Still returned success! ❌
        return {"status": "success", "message": "Document processed"}
```

**Why It Happened**:
1. Exception handling was too broad - caught embedding generation failures
2. Success response sent even when vectorization failed
3. No verification that vector actually exists in Qdrant
4. Logging existed but wasn't checked during bulk operations
5. **NO TEST** validated that success response = vector in Qdrant

### Why Existing Tests Didn't Catch It

**Tests that existed** ✅:
- ✅ Unit tests for embedding generation (passed)
- ✅ Unit tests for Qdrant client (passed)
- ✅ Integration test for `/process/document` endpoint (passed - only checked HTTP 200)

**Tests that were missing** ❌:
- ❌ No test verifying: API success → vector in Qdrant
- ❌ No test checking: Qdrant vector count after processing
- ❌ No test validating: Vector dimensions match expected
- ❌ No test confirming: Vector metadata correctness

### What Tests Would Have Caught It

**Test 1: Critical Smoke Test** (now exists in `test_post_deployment_smoke.py`)

```python
async def test_document_processing_creates_vector(self):
    """
    **THE CRITICAL TEST** - Verify /process/document actually creates vectors.
    """
    # Step 1: Call POST /process/document
    response = await client.post(
        f"{INTELLIGENCE_URL}/process/document",
        json=test_document,
    )
    assert response.status_code == 200

    # Step 2: Wait briefly for async processing
    await asyncio.sleep(2)

    # Step 3: Query Qdrant to verify vector ACTUALLY exists
    response = await client.post(
        f"{QDRANT_URL}/collections/archon_vectors/points/scroll",
        json={
            "filter": {
                "must": [{"key": "document_id", "match": {"value": test_id}}]
            },
            "limit": 10,
            "with_payload": True,
            "with_vector": True,
        },
    )

    points = response.json().get("result", {}).get("points", [])

    # THE CRITICAL ASSERTION - Vector must exist
    assert len(points) > 0, (
        f"❌ VECTORIZATION BUG DETECTED: /process/document returned success "
        f"but NO vector found in Qdrant for document_id={test_id}"
    )

    # Verify vector dimensions
    vector = points[0].get("vector")
    assert len(vector) == 1536, f"Vector has wrong dimensions: {len(vector)} != 1536"
```

**This test would have**:
- ❌ Failed immediately after the bug was introduced
- ❌ Blocked deployment via `./scripts/verify_docker_build.sh`
- ❌ Prevented 25,249 documents from being ingested without vectors
- ✅ Saved hours of debugging and data recovery

**Test 2: E2E Ingestion Validation** (now exists in `test_e2e_ingestion_smoke.py`)

```python
async def test_single_file_ingestion_complete_pipeline(self):
    """
    Test complete ingestion of single file through entire pipeline.

    Validates:
    1. Kafka event publishing ✅
    2. Consumer processing ✅
    3. Intelligence service processing ✅
    4. Vector storage in Qdrant (1536 dimensions) ✅
    5. Node storage in Memgraph ✅
    6. Metadata correctness ✅
    """
    # Publish Kafka event
    correlation_id = await publish_kafka_event(...)

    # Wait for vector in Qdrant (30s timeout)
    vector_found = await wait_for_vector_in_qdrant(...)
    assert vector_found, "Vector not found in Qdrant after 30s"

    # Verify vector dimensions
    vector_info = await verify_vector_dimensions(...)
    assert vector_info["correct_dimensions"], (
        f"Vector has {vector_info['vector_size']} dimensions, expected 1536"
    )

    # Verify node in Memgraph
    node_found = await wait_for_node_in_memgraph(...)
    assert node_found, "Node not found in Memgraph"
```

**Test 3: Kafka Consumer Pipeline** (now exists in `test_kafka_consumer_vectorization.py`)

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_consumer_creates_vector_and_node(pipeline_helper):
    """
    Test that Kafka consumer processes event and creates both vector and node.
    """
    # Publish Kafka event
    await pipeline_helper.publish_process_document_event(...)

    # Wait for vector creation
    vectors = await pipeline_helper.wait_for_vector_creation(...)
    assert vectors is not None, "Vector not created"

    # Verify vector content
    has_expected_content = await pipeline_helper.verify_vector_content(...)
    assert has_expected_content, "Vector content missing"

    # Wait for node creation
    node = await pipeline_helper.wait_for_node_creation(...)
    assert node is not None, "FILE node not created"

    # Verify entities extracted
    entities = await pipeline_helper.get_entities_for_file(...)
    assert len(entities) >= 2, "Entities not extracted"
```

### How New Protocol Prevents Recurrence

**Mandatory checkpoints** now in place:

1. ✅ **Before ANY commit**: Pre-commit hook runs critical unit tests
2. ✅ **Before ANY deployment**: `./scripts/verify_docker_build.sh` runs smoke tests
3. ✅ **Before bulk ingestion**: E2E smoke test validates single file first
4. ✅ **After Docker rebuild**: Mandatory smoke test validation
5. ✅ **In CI/CD**: Automated test suite blocks merge if tests fail

**New tests prevent recurrence**:

| Test | File | What It Validates |
|------|------|-------------------|
| `test_document_processing_creates_vector` | `test_post_deployment_smoke.py` | API success → Vector exists |
| `test_single_file_ingestion_complete_pipeline` | `test_e2e_ingestion_smoke.py` | Kafka → Vector → Node complete |
| `test_consumer_creates_vector_and_node` | `test_kafka_consumer_vectorization.py` | Consumer processes correctly |
| `test_vector_dimensions_correctness` | `test_kafka_consumer_vectorization.py` | Vector dimensions = 1536 |

**Before the bug**: No test validated end-to-end vectorization
**After the fix**: 4+ tests validate every step of the pipeline
**Result**: Bug cannot reoccur without test failures blocking deployment

---

## Enforcement

### Mandatory vs Optional Tests

#### MANDATORY (Never Skip)

| Test Suite | When | Command | Enforcement |
|------------|------|---------|-------------|
| **Pre-commit hooks** | Every commit | `pre-commit run --all-files` | Git hook (automatic) |
| **Smoke tests** | Before deployment | `./scripts/verify_docker_build.sh` | Manual (blocking) |
| **Critical integration** | Before bulk ingestion | `pytest tests/integration/test_post_deployment_smoke.py -v -m critical` | Manual (blocking) |
| **E2E single file** | Before bulk ingestion | `pytest tests/integration/test_e2e_ingestion_smoke.py::TestE2EIngestionSmoke::test_single_file_ingestion_complete_pipeline -v` | Manual (blocking) |

#### OPTIONAL (Can Skip for Non-Critical Changes)

| Test Suite | When | Skip Condition |
|------------|------|----------------|
| **Full integration suite** | Before release | Documentation-only changes |
| **Performance benchmarks** | Weekly | No performance-related code changes |
| **Slow E2E tests** | On-demand | Local development (run in CI) |

### When to Skip Tests (Rare Exceptions)

**NEVER skip for**:
- ❌ Changes to document processing
- ❌ Changes to vectorization logic
- ❌ Changes to Kafka consumers
- ❌ Changes to database interactions
- ❌ Docker image rebuilds
- ❌ Bulk ingestion operations

**CAN skip for** (with caution):
- ✅ Documentation-only changes (README, CLAUDE.md, etc.)
- ✅ Comment-only changes
- ✅ Non-functional config changes (logging levels, etc.)

**How to skip**:
```bash
# Skip pre-commit hooks (use sparingly!)
git commit --no-verify -m "docs: Update README"

# Skip slow tests during local development
export SKIP_SLOW_TESTS=1
pytest tests/integration -v
```

### Review Checklist for PRs

**Before approving any pull request, verify**:

- [ ] All CI/CD tests passed (GitHub Actions / GitLab CI / Jenkins)
- [ ] Pre-commit hooks ran successfully (check commit history)
- [ ] Smoke tests passed (require evidence in PR description)
- [ ] No test files were deleted without justification
- [ ] New features have corresponding tests
- [ ] Critical paths are covered by integration tests
- [ ] Test coverage didn't decrease (check coverage report)

**For critical path changes (document processing, vectorization, Kafka)**:

- [ ] Smoke tests executed manually (screenshot or log excerpt)
- [ ] E2E ingestion test passed (proof required)
- [ ] Verify environment script shows all healthy
- [ ] Manual inspection of Qdrant + Memgraph data

---

## Test Maintenance

### When to Update Tests

**Immediately update tests when**:

1. **API contract changes**:
   - Update request/response schemas
   - Update expected status codes
   - Update timeout thresholds

2. **Service configuration changes**:
   - Update service URLs
   - Update port numbers
   - Update environment variables

3. **Data model changes**:
   - Update expected vector dimensions
   - Update Memgraph node labels/properties
   - Update Qdrant metadata fields

4. **Performance requirements change**:
   - Update timeout thresholds in `PERFORMANCE_THRESHOLDS`
   - Update time budgets in test suite

### How to Add New Critical Path Tests

**Template for adding vectorization-style tests**:

```python
# tests/integration/test_new_critical_path.py

import pytest
import asyncio
from typing import Dict, Any

@pytest.mark.asyncio
@pytest.mark.smoke
@pytest.mark.critical  # Mark as critical for smoke test filtering
class TestNewCriticalPath:
    """
    Critical test for [feature name].

    This test validates that [operation] actually [creates expected state],
    not just returns success response.
    """

    async def test_operation_creates_expected_state(self):
        """
        Verify [operation] creates [expected state].

        This test prevents a bug where [operation] returned success
        but didn't actually [create expected state].

        Test Flow:
        1. Call [operation] API endpoint
        2. Verify endpoint returns success (200 OK)
        3. Query [data store] to confirm [expected state] actually exists
        4. Verify [expected state] has correct properties

        PASS: [Expected state] exists with correct properties
        FAIL: [Expected state] not found or incorrect (THE BUG)
        """
        # Step 1: Call operation
        response = await client.post(f"{SERVICE_URL}/operation", json=payload)
        assert response.status_code == 200

        # Step 2: Wait for async processing
        await asyncio.sleep(2)

        # Step 3: Verify expected state exists
        result = await verify_expected_state_exists(...)
        assert result is not None, (
            f"❌ BUG DETECTED: /operation returned success "
            f"but expected state not found"
        )

        # Step 4: Verify properties
        assert result["property"] == expected_value, "Property mismatch"

        logger.info("✅ Operation creates expected state (CRITICAL TEST PASSED)")
```

**Add to smoke test suite**:

```bash
# Update ./scripts/verify_docker_build.sh
# Add new test to pytest execution:

pytest \
  tests/integration/test_post_deployment_smoke.py \
  tests/integration/test_new_critical_path.py \
  -v -m smoke --timeout=60
```

### Test Coverage Goals

**Target coverage** by test type:

| Code Area | Unit Tests | Integration Tests | E2E Tests |
|-----------|-----------|-------------------|-----------|
| **Document processing** | 90%+ | 100% critical paths | Single file ingestion |
| **Vectorization** | 85%+ | 100% vector creation | Batch processing |
| **Knowledge graph** | 80%+ | 100% node creation | Tree structure |
| **Kafka consumers** | 75%+ | 100% event handling | Event → Data flow |
| **API endpoints** | 90%+ | 100% critical endpoints | End-to-end requests |

**How to check coverage**:

```bash
# Generate coverage report
pytest tests/ --cov=services --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Check coverage for specific module
pytest tests/ --cov=services.intelligence --cov-report=term-missing
```

### Updating Performance Thresholds

**When performance improves or degrades**:

1. **Measure new baselines**:
   ```bash
   pytest tests/integration/test_post_deployment_smoke.py::TestPostDeploymentSmoke::test_performance_baseline -v --durations=0
   ```

2. **Update thresholds** in `tests/integration/test_post_deployment_smoke.py`:
   ```python
   PERFORMANCE_THRESHOLDS = {
       "service_health_check": 5.0,   # Update if consistently faster/slower
       "document_processing": 30.0,   # Update based on actual measurements
       "vector_creation": 10.0,       # Update if indexing time changes
       "rag_query": 10.0,             # Update if search performance changes
       "database_query": 5.0,         # Update if DB performance changes
   }
   ```

3. **Document why thresholds changed**:
   ```markdown
   ## Performance Threshold Updates

   **Date**: 2025-11-12
   **Change**: Increased `vector_creation` from 10s → 15s
   **Reason**: Added more comprehensive entity extraction, increases processing time
   **Justification**: Trade-off for better data quality, still within acceptable limits
   ```

---

## Memgraph Label Constants

### Critical Rule: Always Use Label Constants

**DO NOT** use raw string labels in Cypher queries:

```python
# ❌ WRONG - Raw string labels
query = "MATCH (f:FILE) RETURN f"  # Wrong case!
query = "MATCH (f:File) RETURN f"  # Easy to typo
query = "CREATE (d:DIRECTORY)"     # Inconsistent casing
```

**DO** use `MemgraphLabels` enum constants:

```python
# ✅ CORRECT - Label constants
from src.constants import MemgraphLabels

query = f"MATCH (f:{MemgraphLabels.FILE}) RETURN f"
query = f"CREATE (d:{MemgraphLabels.DIRECTORY})"
query = f"MATCH (p:{MemgraphLabels.PROJECT})-[:{MemgraphRelationships.CONTAINS}]->(f:{MemgraphLabels.FILE})"
```

### Why This Matters

**Historical Bug** (November 2025): We discovered **79% of tests** were using `:FILE` (all caps) while production code creates `:File` (capital F only) nodes. This caused:

- ✅ **Tests passed** with mock data (wrong labels)
- ❌ **Production queries returned 0 results** (silent failures)
- ❌ **6 production queries in `orphan_detector.py` failed completely**
- ❌ **No developer knew the correct label case** (inconsistent docs)

**Example of the Bug**:

```python
# Test code (WRONG)
query = "MATCH (f:FILE) RETURN count(f)"  # Returns 100 in test
# Production creates nodes as `:File`, not `:FILE`
# Same query in production returns 0 (silent failure!)
```

**Root Cause**:
- Cypher is **case-sensitive** for node labels (`:File` ≠ `:FILE` ≠ `:file`)
- Without constants, developers had **no way to know** the correct case
- Tests used different labels than production code
- **False positive tests** - passed with wrong labels, failed in production

### Available Constants

```python
from src.constants import MemgraphLabels, MemgraphRelationships

# Primary node types (CRITICAL - use these!)
MemgraphLabels.FILE          # → "File" (capital F only)
MemgraphLabels.PROJECT        # → "PROJECT" (all caps)
MemgraphLabels.DIRECTORY      # → "Directory" (capital D only)
MemgraphLabels.ENTITY         # → "Entity"

# Semantic nodes
MemgraphLabels.CONCEPT        # → "Concept"
MemgraphLabels.THEME          # → "Theme"
MemgraphLabels.ONEX_TYPE      # → "ONEXType"
MemgraphLabels.DOMAIN         # → "Domain"

# Relationships (use for consistent relationship types)
MemgraphRelationships.CONTAINS       # → "CONTAINS"
MemgraphRelationships.IMPORTS        # → "IMPORTS"
MemgraphRelationships.REFERENCES     # → "REFERENCES"
MemgraphRelationships.CHILD_OF       # → "CHILD_OF"
```

### Pre-commit Hook Enforcement

A pre-commit hook (`scripts/validate_memgraph_labels.py`) automatically detects raw label strings and **prevents commits** with violations.

**Hook Configuration** (`.pre-commit-config.yaml`):

```yaml
- repo: local
  hooks:
    - id: validate-memgraph-labels
      name: Validate Memgraph Label Constants
      entry: python scripts/validate_memgraph_labels.py
      language: python
      pass_filenames: false
      always_run: true
```

**What It Detects**:

```bash
# Example violation:
❌ Memgraph label validation FAILED:
  services/intelligence/src/handlers/tree_handler.py:42
    - Raw label ':FILE' found. Use MemgraphLabels.FILE instead.
  tests/integration/test_orphan_detector.py:78
    - Raw label ':DIRECTORY' found. Use MemgraphLabels.DIRECTORY instead.
```

**How to Fix Violations**:

```python
# Before (WRONG - blocked by hook):
query = "MATCH (f:FILE) WHERE f.path = $path RETURN f"

# After (CORRECT - passes hook):
from src.constants import MemgraphLabels
query = f"MATCH (f:{MemgraphLabels.FILE}) WHERE f.path = $path RETURN f"
```

**Manual Validation** (run before committing):

```bash
# Check all files for violations
python scripts/validate_memgraph_labels.py

# Expected output if violations found:
# ❌ Found 3 files with raw Memgraph labels
# → Fix violations before committing

# Expected output if clean:
# ✅ All Memgraph labels use constants correctly
```

### Testing Label Consistency

**Integration Test**: `tests/integration/test_label_case_consistency.py`

Validates:
- ✅ Constants match production label case
- ✅ Memgraph has correct label case (`:File` not `:FILE`)
- ✅ No incorrect label nodes exist in database
- ✅ All production queries use correct labels

**Run this test to verify label consistency**:

```bash
# Validate label consistency
pytest tests/integration/test_label_case_consistency.py -v

# Expected output:
# ✅ test_file_label_is_correct_case - Constants match production
# ✅ test_no_uppercase_file_nodes - No :FILE nodes in Memgraph
# ✅ test_production_queries_use_constants - All queries use MemgraphLabels
```

**What This Test Catches**:

1. **Wrong label case in Memgraph**:
   ```python
   # Test fails if production code creates :FILE instead of :File
   assert uppercase_files == 0, "Found :FILE nodes, should be :File"
   ```

2. **Constants don't match production**:
   ```python
   # Test fails if MemgraphLabels.FILE = "FILE" but production uses "File"
   assert MemgraphLabels.FILE == "File", "Constant doesn't match production label"
   ```

3. **Production queries use raw strings**:
   ```python
   # Test scans production code for raw label usage
   assert no_raw_labels, "Production code uses raw labels instead of constants"
   ```

### Common Scenarios

#### Scenario 1: Writing a New Query

```python
# ❌ WRONG - Will be blocked by pre-commit hook
def get_file_by_path(path: str):
    query = "MATCH (f:FILE) WHERE f.path = $path RETURN f"
    return graph.run(query, path=path)

# ✅ CORRECT - Uses constants
from src.constants import MemgraphLabels

def get_file_by_path(path: str):
    query = f"MATCH (f:{MemgraphLabels.FILE}) WHERE f.path = $path RETURN f"
    return graph.run(query, path=path)
```

#### Scenario 2: Writing a Test

```python
# ❌ WRONG - Test will pass but production will fail
@pytest.mark.asyncio
async def test_file_count():
    # Creates test node with wrong label
    await graph.run("CREATE (f:FILE {path: '/test.py'})")

    # Query returns 1 in test, but 0 in production!
    result = await graph.run("MATCH (f:FILE) RETURN count(f)")
    assert result == 1  # FALSE POSITIVE - passes but wrong

# ✅ CORRECT - Test uses production labels
from src.constants import MemgraphLabels

@pytest.mark.asyncio
async def test_file_count():
    # Creates node with correct label (matches production)
    await graph.run(f"CREATE (f:{MemgraphLabels.FILE} {{path: '/test.py'}})")

    # Query uses same label as production
    result = await graph.run(f"MATCH (f:{MemgraphLabels.FILE}) RETURN count(f)")
    assert result == 1  # TRUE POSITIVE - matches production behavior
```

#### Scenario 3: Complex Query with Multiple Labels

```python
# ❌ WRONG - Multiple opportunities for typos
query = """
MATCH (p:PROJECT)-[:CONTAINS]->(d:Directory)-[:CONTAINS]->(f:File)
WHERE p.name = $project_name
RETURN f
"""

# ✅ CORRECT - All labels from constants
from src.constants import MemgraphLabels, MemgraphRelationships

query = f"""
MATCH (p:{MemgraphLabels.PROJECT})
  -[:{MemgraphRelationships.CONTAINS}]->(d:{MemgraphLabels.DIRECTORY})
  -[:{MemgraphRelationships.CONTAINS}]->(f:{MemgraphLabels.FILE})
WHERE p.name = $project_name
RETURN f
"""
```

### Migration Guide for Existing Code

**Step 1: Find violations**

```bash
# Scan codebase for raw labels
python scripts/validate_memgraph_labels.py

# Or use grep (less comprehensive)
grep -r ":FILE\|:DIRECTORY\|:PROJECT" services/ tests/ --include="*.py"
```

**Step 2: Import constants**

```python
# Add to imports at top of file
from src.constants import MemgraphLabels, MemgraphRelationships
```

**Step 3: Replace raw strings**

```python
# Before:
query = "MATCH (f:FILE) RETURN f"

# After:
query = f"MATCH (f:{MemgraphLabels.FILE}) RETURN f"
```

**Step 4: Verify**

```bash
# Run pre-commit hook manually
pre-commit run validate-memgraph-labels --all-files

# Run label consistency test
pytest tests/integration/test_label_case_consistency.py -v

# If both pass, commit your changes
git add .
git commit -m "fix: Use MemgraphLabels constants instead of raw strings"
```

### Why Pre-commit Hook Is Critical

**Without Hook**:
- 😰 Developer uses `:FILE` in new code
- ✅ Tests pass (using same wrong label)
- 🚀 Code deployed to production
- ❌ Production queries return 0 results
- 🔥 **Silent failure - no errors, just no data**

**With Hook**:
- 😊 Developer uses `:FILE` in new code
- ❌ Pre-commit hook **blocks commit**
- 🛠️ Developer fixes to use `MemgraphLabels.FILE`
- ✅ Commit succeeds with correct labels
- 🚀 Code works in production

**Time Saved**: Hours of debugging production issues prevented by 30 seconds of pre-commit validation.

### Summary

**DO**:
- ✅ Always use `MemgraphLabels.*` constants for node labels
- ✅ Always use `MemgraphRelationships.*` constants for relationships
- ✅ Run `python scripts/validate_memgraph_labels.py` before committing
- ✅ Check pre-commit hook output for violations
- ✅ Write tests using same labels as production (via constants)

**DON'T**:
- ❌ Use raw strings like `:FILE`, `:Directory`, `:PROJECT` in queries
- ❌ Assume label case from documentation (might be outdated)
- ❌ Skip pre-commit hooks (especially for label validation)
- ❌ Mix label cases in different parts of codebase

**Remember**: Cypher is case-sensitive. Constants enforce consistency. Tests verify correctness.

---

## Quick Reference Commands

### Pre-Commit Validation

```bash
# Run all pre-commit checks
pre-commit run --all-files

# Run specific check
pre-commit run black --all-files
pre-commit run pytest-smoke-tests
```

### Pre-Deployment Validation

```bash
# Complete deployment validation
./scripts/verify_docker_build.sh

# Quick critical tests only
./scripts/verify_docker_build.sh --quick

# Detailed output
./scripts/verify_docker_build.sh --verbose
```

### Pre-Ingestion Validation

```bash
# E2E smoke test
pytest tests/integration/test_e2e_ingestion_smoke.py::TestE2EIngestionSmoke::test_single_file_ingestion_complete_pipeline -v

# Kafka consumer tests
pytest tests/integration/test_kafka_consumer_vectorization.py -v

# Environment health
python3 scripts/verify_environment.py --verbose
```

### Post-Ingestion Validation

```bash
# Data integrity validation
python3 scripts/validate_data_integrity.py --verbose

# Check for orphans
python3 scripts/verify_environment.py --verbose | grep -i orphan
```

### Debugging

```bash
# View service logs
docker logs archon-intelligence -f
docker logs archon-kafka-consumer -f

# Aggregate all logs
./scripts/logs.sh all

# Health checks
curl http://localhost:8053/health
curl http://localhost:6333/collections/archon_vectors
```

---

## Summary

**Testing is not optional. Testing is deployment.**

Every deployment, every commit to critical paths, and every bulk ingestion operation **MUST** pass validation tests. The vectorization bug proved that success responses don't guarantee successful execution.

**Key Principles**:

1. ✅ **Verify end state, not just API responses**
2. ✅ **Test the critical path: API → Database → Verification**
3. ✅ **Never skip smoke tests before deployment**
4. ✅ **Always validate with single file before bulk ingestion**
5. ✅ **When in doubt, run the tests**

**Remember**: 5 minutes of testing prevents 5 hours of debugging.

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-12
**Next Review**: 2025-12-12 or after any critical bug discovery
