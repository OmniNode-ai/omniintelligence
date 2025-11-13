# Test Fix Implementation Checklist

**Correlation ID**: c1a15b64-c12c-49cc-9cac-5b1d3132d1b7
**Goal**: Prevent entity extraction failures from reaching production

---

## ⚠️ Phase 1: Critical Fixes (DO IMMEDIATELY - 1-2 hours)

### ✅ Task 1.1: Add Entity Count Validation to E2E Smoke Test

**File**: `tests/integration/test_e2e_ingestion_smoke.py`
**Location**: After line 718 (after `assert node_found`)

```python
# Step 6: Verify entity extraction (CRITICAL FIX)
logger.info("\n🔍 Step 6: Verifying entity extraction...")

async with memgraph_connection.session() as session:
    result = await session.run("""
        MATCH (f:FILE)
        WHERE f.project_name = $project_name
          AND (f.path CONTAINS $file_path OR f.entity_id CONTAINS $file_path)
        OPTIONAL MATCH (f)-[:DEFINES]->(e:ENTITY)
        RETURN f.entity_count as file_entity_count,
               count(e) as actual_entity_count,
               collect(e.name)[0..5] as entity_names
    """, project_name=test_project_name, file_path=test_file_path)

    record = await result.single()

    if not record:
        pytest.fail(f"CRITICAL: FILE node not found for {test_file_path}")

    file_entity_count = record["file_entity_count"] or 0
    actual_entity_count = record["actual_entity_count"] or 0
    entity_names = record["entity_names"] or []

# CRITICAL: Fail if zero entities
assert actual_entity_count > 0, \
    f"CRITICAL FAILURE: Zero entities extracted from {test_file_path}"

# Fail if count mismatch
assert file_entity_count == actual_entity_count, \
    f"Entity count mismatch: FILE.entity_count={file_entity_count}, actual={actual_entity_count}"

# Verify expected entities for test file
# test_file_content has: AuthenticationManager, DatabaseConnectionPool classes
# plus authenticate, validate_token, initialize, get_connection, get_config
EXPECTED_MIN_ENTITIES = 5

assert actual_entity_count >= EXPECTED_MIN_ENTITIES, \
    f"Expected at least {EXPECTED_MIN_ENTITIES} entities, got {actual_entity_count}"

logger.info(f"  ✅ Entity extraction validated: {actual_entity_count} entities")
logger.info(f"  📊 Sample entities: {', '.join(entity_names)}")
```

**Test**: `poetry run pytest tests/integration/test_e2e_ingestion_smoke.py -v`

---

### ✅ Task 1.2: Fix Weak Assertions in E2E File Indexing

**File**: `tests/integration/test_e2e_file_indexing.py`
**Location**: Lines 378-390 (replace existing assertions)

```python
# Get entity links
entity_links = await file_tree_helper.get_entity_links(project_name)

# CRITICAL: Fail if NO entities extracted from entire project
assert len(entity_links) > 0, "CRITICAL: No entity links found in entire project"

# Verify utils.py specifically
utils_entities = [e for e in entity_links if "utils.py" in e["file_path"]]

# CRITICAL: Fail if utils.py has zero entities
assert len(utils_entities) > 0, \
    f"CRITICAL: Zero entities extracted from utils.py"

# Expected entities in utils.py (from test fixture)
# Update this based on actual test_repo_small/utils.py content
EXPECTED_ENTITY_NAMES = {"helper_function", "HelperClass"}  # Update as needed
EXPECTED_MIN_COUNT = len(EXPECTED_ENTITY_NAMES)

# Fail if count too low
assert len(utils_entities) >= EXPECTED_MIN_COUNT, \
    f"Expected at least {EXPECTED_MIN_COUNT} entities in utils.py, got {len(utils_entities)}"

# Verify specific entity names
entity_names = {e["entity_name"] for e in utils_entities}
missing_entities = EXPECTED_ENTITY_NAMES - entity_names

if missing_entities:
    pytest.fail(f"Missing expected entities from utils.py: {missing_entities}")
```

**Test**: `poetry run pytest tests/integration/test_e2e_file_indexing.py::test_file_node_entity_linking -v`

---

### ✅ Task 1.3: Add Entity Validation to Relationship Extraction Test

**File**: `tests/integration/test_relationship_extraction_fix.py`
**Location**: After line 82 (after relationship assertions)

```python
# Verify entities extracted (CRITICAL FIX)
assert "enriched_entities" in result, "Response missing 'enriched_entities' field"
entities = result["enriched_entities"]

# FAIL if zero entities
assert len(entities) > 0, \
    f"CRITICAL: Zero entities extracted from test code"

# Verify expected entities
entity_names = {e.get("name", "") for e in entities}
expected_entities = {"TestClass", "test_method", "main"}

missing_entities = expected_entities - entity_names
assert len(missing_entities) == 0, \
    f"Missing expected entities: {missing_entities}"

print(f"✅ Verified {len(entities)} entities: {entity_names}")
```

**Test**: `poetry run pytest tests/integration/test_relationship_extraction_fix.py::test_langextract_endpoint_returns_relationships -v`

---

## 🔥 Phase 2: New E2E Test (HIGH PRIORITY - 3-4 hours)

### ✅ Task 2.1: Create Entity Extraction E2E Test

**File**: `tests/integration/test_e2e_entity_extraction.py` (NEW FILE)

```python
#!/usr/bin/env python3
"""
End-to-End Entity Extraction Validation

CRITICAL: Validates complete entity extraction flow with known code.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime

import pytest
from aiokafka import AIOKafkaProducer
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092")
KAFKA_TOPIC = "dev.archon-intelligence.enrich-document.v1"
MEMGRAPH_URI = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")


async def publish_test_event(project_name: str, file_path: str, content: str) -> str:
    """Publish Kafka event and return correlation ID"""
    correlation_id = f"e2e-entity-{uuid.uuid4().hex[:12]}"

    event = {
        "event_type": "enrich_document",
        "event_version": "2.0.0",
        "correlation_id": correlation_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "project_name": project_name,
        "files": [{
            "path": file_path,
            "content": content,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "language": "python",
            "size_bytes": len(content.encode()),
            "last_modified": datetime.now(UTC).isoformat(),
            "entity_id": f"archon://{project_name}/documents/{file_path}"
        }]
    }

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    await producer.start()
    try:
        await producer.send_and_wait(KAFKA_TOPIC, value=event)
        return correlation_id
    finally:
        await producer.stop()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_entity_extraction_with_known_code():
    """
    Test entity extraction with known Python code.

    FAIL CONDITIONS:
    - Zero entities extracted
    - Missing expected entity names
    - Entity count mismatch
    """

    # KNOWN Python code with documented entities
    test_code = '''
import os
import logging
from typing import Optional

class UserManager:
    """User authentication manager"""

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return token"""
        return "token"

    def validate_token(self, token: str) -> bool:
        """Validate authentication token"""
        return True

class DatabasePool:
    """Database connection pool"""

    def get_connection(self):
        """Get database connection"""
        pass

def initialize_app():
    """Initialize application"""
    manager = UserManager()
    pool = DatabasePool()
    return manager, pool

def cleanup_resources():
    """Cleanup application resources"""
    pass
'''

    # EXPECTED ENTITIES (documented)
    EXPECTED_CLASSES = {"UserManager", "DatabasePool"}
    EXPECTED_FUNCTIONS = {
        "authenticate", "validate_token", "get_connection",
        "initialize_app", "cleanup_resources"
    }
    EXPECTED_TOTAL = len(EXPECTED_CLASSES) + len(EXPECTED_FUNCTIONS)  # 7 entities

    project_name = f"test_entity_extraction_{uuid.uuid4().hex[:8]}"
    file_path = "src/auth/manager.py"

    logger.info("=" * 70)
    logger.info("🔍 Testing Entity Extraction with Known Code")
    logger.info("=" * 70)
    logger.info(f"Project: {project_name}")
    logger.info(f"File: {file_path}")
    logger.info(f"Expected entities: {EXPECTED_TOTAL}")
    logger.info(f"  Classes: {EXPECTED_CLASSES}")
    logger.info(f"  Functions: {EXPECTED_FUNCTIONS}")

    # Publish event
    correlation_id = await publish_test_event(project_name, file_path, test_code)
    logger.info(f"Event published: {correlation_id}")

    # Wait for processing
    await asyncio.sleep(5)

    # Query Memgraph
    driver = AsyncGraphDatabase.driver(MEMGRAPH_URI)
    try:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (f:FILE)
                WHERE f.project_name = $project_name
                  AND (f.path = $file_path OR f.path CONTAINS $file_path)
                OPTIONAL MATCH (f)-[:DEFINES]->(e:ENTITY)
                RETURN f.entity_count as file_entity_count,
                       count(e) as actual_entity_count,
                       collect(e.name) as entity_names,
                       collect(e.type) as entity_types
            """, project_name=project_name, file_path=file_path)

            record = await result.single()

            if not record:
                pytest.fail(f"CRITICAL: FILE node not found for {file_path}")

            file_entity_count = record["file_entity_count"] or 0
            actual_entity_count = record["actual_entity_count"] or 0
            entity_names = set(record["entity_names"] or [])
            entity_types = record["entity_types"] or []

    finally:
        await driver.close()

    # CRITICAL ASSERTIONS

    logger.info(f"\nResults:")
    logger.info(f"  File entity_count: {file_entity_count}")
    logger.info(f"  Actual entity count: {actual_entity_count}")
    logger.info(f"  Entity names: {entity_names}")

    # 1. Fail if zero entities
    assert actual_entity_count > 0, \
        f"CRITICAL FAILURE: Zero entities extracted from {file_path}"

    # 2. Fail if count mismatch
    assert file_entity_count == actual_entity_count, \
        f"Entity count mismatch: FILE.entity_count={file_entity_count}, actual={actual_entity_count}"

    # 3. Fail if total count wrong
    assert actual_entity_count == EXPECTED_TOTAL, \
        f"Expected {EXPECTED_TOTAL} entities, got {actual_entity_count}"

    # 4. Fail if missing expected classes
    missing_classes = EXPECTED_CLASSES - entity_names
    assert len(missing_classes) == 0, \
        f"Missing expected classes: {missing_classes}"

    # 5. Fail if missing expected functions
    missing_functions = EXPECTED_FUNCTIONS - entity_names
    assert len(missing_functions) == 0, \
        f"Missing expected functions: {missing_functions}"

    logger.info("✅ Entity extraction test PASSED")
    logger.info("=" * 70)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])
```

**Test**: `poetry run pytest tests/integration/test_e2e_entity_extraction.py -v`

---

### ✅ Task 2.2: Document Test Fixture Entities

**File**: `tests/fixtures/test_repo_small/ENTITIES.md` (NEW FILE)

```markdown
# Expected Entity Counts for Test Fixtures

This file documents the expected entity counts for test repository files.
Tests use these values to validate entity extraction.

## utils.py

**Total Entities**: 3

**Classes** (1):
- `HelperClass`

**Functions** (2):
- `helper_function`
- `another_function`

## main.py

**Total Entities**: 2

**Functions** (2):
- `main`
- `setup`

## orphan.py

**Total Entities**: 1

**Functions** (1):
- `orphaned_function`

---

**Usage in Tests**:

```python
EXPECTED_ENTITIES = {
    "utils.py": {
        "count": 3,
        "classes": ["HelperClass"],
        "functions": ["helper_function", "another_function"]
    },
    "main.py": {
        "count": 2,
        "functions": ["main", "setup"]
    },
    "orphan.py": {
        "count": 1,
        "functions": ["orphaned_function"]
    }
}
```

**Update When**: Modifying test fixture code
**Verified By**: `test_e2e_entity_extraction.py`
```

---

## 📋 Phase 3: Fix Unit Tests (MEDIUM PRIORITY - 2-3 hours)

### ✅ Task 3.1: Replace Fake Mocks with Realistic Data

**File**: `services/intelligence/tests/unit/handlers/test_document_indexing_handler_coverage.py`

**Option A - Use Realistic Mocks** (Lines 214-222):

```python
async def mock_post(url, **kwargs):
    if "stamp-metadata" in url:
        return create_mock_response(
            {"hash": "blake3:abc", "dedupe_status": "new"}
        )
    elif "extract/document" in url:  # Fixed endpoint name
        # REALISTIC mock based on actual LangExtract response
        return create_mock_response({
            "enriched_entities": [
                {
                    "entity_id": "TestClass",
                    "name": "TestClass",
                    "entity_type": "CLASS",
                    "description": "Test class",
                    "confidence_score": 0.9,
                    "properties": {}
                },
                {
                    "entity_id": "test_method",
                    "name": "test_method",
                    "entity_type": "FUNCTION",
                    "description": "Test method",
                    "confidence_score": 0.9,
                    "properties": {}
                }
            ],
            "relationships": [
                {
                    "source_entity_id": "test.py",
                    "target_entity_id": "os",
                    "relationship_type": "IMPORTS",
                    "confidence_score": 1.0
                }
            ]
        })
    elif "assess/code" in url:
        return create_mock_response({"quality_score": 0.8})
    return MagicMock()
```

**Option B - Use Real Service** (Better):

```python
@pytest.mark.integration  # Mark as integration test
async def test_successful_indexing_real_langextract(handler_with_router):
    """Test with REAL LangExtract service (not mocked)"""

    # Don't mock http_client - use real one
    await handler_with_router._ensure_http_client()

    # Real Python code
    sample_content = '''
class TestClass:
    def method(self):
        pass

def test_func():
    pass
'''

    event = MockEventEnvelope(
        event_type="DOCUMENT_INDEX_REQUESTED",
        payload={
            "source_path": "test.py",
            "content": sample_content,
            "language": "python",
        },
    )

    success = await handler_with_router.handle_event(event)
    assert success is True

    # CRITICAL: Verify entities were actually processed
    # (handler should have logged entity count)
    assert handler_with_router.metrics["indexing_successes"] == 1
```

---

## ✅ Validation Steps

### Run All Fixed Tests

```bash
# Run modified E2E smoke test
poetry run pytest tests/integration/test_e2e_ingestion_smoke.py::TestE2EIngestionSmoke::test_single_file_ingestion_complete_pipeline -v

# Run modified file indexing test
poetry run pytest tests/integration/test_e2e_file_indexing.py::test_file_node_entity_linking -v

# Run modified relationship test
poetry run pytest tests/integration/test_relationship_extraction_fix.py::test_langextract_endpoint_returns_relationships -v

# Run new entity extraction test
poetry run pytest tests/integration/test_e2e_entity_extraction.py -v

# Run all integration tests
poetry run pytest tests/integration/ -v -m "not slow"
```

### Verify Tests Would Catch Bug

To verify tests would catch the bug, temporarily break entity extraction:

```bash
# Temporarily disable entity extraction in handler
# (comment out LangExtract call in document_indexing_handler.py)

# Run tests - should FAIL
poetry run pytest tests/integration/test_e2e_entity_extraction.py -v

# Expected output:
# FAILED - CRITICAL FAILURE: Zero entities extracted from src/auth/manager.py
```

---

## 📊 Success Metrics

| Metric | Before | After | Status |
|--------|--------|-------|--------|
| E2E tests check entity count | ❌ No | ✅ Yes | |
| Tests fail on 0 entities | ❌ No | ✅ Yes | |
| Tests use exact count assertions | ⚠️ Partial | ✅ Yes | |
| Unit tests use realistic mocks | ❌ No | ✅ Yes | |
| Test fixtures documented | ❌ No | ✅ Yes | |

---

## 🚀 Final Validation

### Run Complete Test Suite

```bash
# All integration tests
poetry run pytest tests/integration/ -v

# Specific entity extraction tests
poetry run pytest -k "entity" -v

# All tests (unit + integration)
poetry run pytest -v
```

### Verify Against Production Data

```bash
# Re-ingest a known file and verify entity count
python3 scripts/bulk_ingest_repository.py tests/fixtures/test_repo_small \
  --project-name validation_test \
  --kafka-servers 192.168.86.200:29092

# Check entity count
python3 scripts/verify_environment.py --verbose
```

---

## ✅ Completion Checklist

- [ ] Task 1.1: E2E smoke test entity validation (CRITICAL)
- [ ] Task 1.2: E2E file indexing exact assertions (CRITICAL)
- [ ] Task 1.3: Relationship test entity validation (CRITICAL)
- [ ] Task 2.1: New E2E entity extraction test (HIGH)
- [ ] Task 2.2: Document test fixture entities (HIGH)
- [ ] Task 3.1: Fix unit test mocks (MEDIUM)
- [ ] All tests passing
- [ ] Tests verified to catch 0-entity bug
- [ ] Documentation updated

**Estimated Total Time**: 6-9 hours

**Priority Order**:
1. Phase 1 (Tasks 1.1-1.3) - CRITICAL - 1-2 hours
2. Phase 2 (Tasks 2.1-2.2) - HIGH - 3-4 hours
3. Phase 3 (Task 3.1) - MEDIUM - 2-3 hours
