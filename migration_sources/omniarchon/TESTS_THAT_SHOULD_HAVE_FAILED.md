# Tests That Should Have Failed (But Didn't)

**Correlation ID**: c1a15b64-c12c-49cc-9cac-5b1d3132d1b7
**Production Issue**: 350 files with 0 entities extracted
**Test Results**: All tests passed ✅ (incorrectly)

---

## Test #1: E2E Ingestion Smoke Test
**File**: `tests/integration/test_e2e_ingestion_smoke.py`
**Function**: `test_single_file_ingestion_complete_pipeline`

### Why It Should Have Failed

Test ingests Python file with known classes and functions:

```python
# test_file_content (lines 87-208)
class AuthenticationManager:
    def __init__(self, api_key: str, token_expiry: int = 3600):
        ...
    def authenticate(self, username: str, password: str) -> Optional[str]:
        ...
    def validate_token(self, token: str) -> bool:
        ...

class DatabaseConnectionPool:
    def __init__(self, host: str, port: int, database: str, pool_size: int = 10):
        ...
    async def initialize(self):
        ...
    async def get_connection(self):
        ...

def get_config(key: str, default: Any = None) -> Any:
    ...
```

**Expected Entities**: 7
- 2 classes: `AuthenticationManager`, `DatabaseConnectionPool`
- 5 methods/functions: `authenticate`, `validate_token`, `initialize`, `get_connection`, `get_config`

**Actual Entities**: 0 (production failure)

### What The Test Checks

```python
# Line 708-715
node_found = await wait_for_node_in_memgraph(
    memgraph_driver=memgraph_connection,
    project_name=test_project_name,
    file_path=test_file_path,
    timeout=TEST_TIMEOUT_SECONDS
)

assert node_found, f"Node not found in Memgraph after {TEST_TIMEOUT_SECONDS}s"
```

**Result**: Test PASSES ✅
- FILE node exists in Memgraph ✅
- But entity_count = 0 ❌ (NOT CHECKED)
- No DEFINES relationships ❌ (NOT CHECKED)

### What It SHOULD Check

```python
# After line 718, add:
async with memgraph_connection.session() as session:
    result = await session.run("""
        MATCH (f:FILE)
        WHERE f.project_name = $project AND f.path CONTAINS $file_path
        OPTIONAL MATCH (f)-[:DEFINES]->(e:ENTITY)
        RETURN f.entity_count as file_entity_count,
               count(e) as actual_entity_count,
               collect(e.name) as entity_names
    """, project=test_project_name, file_path=test_file_path)

    record = await result.single()
    entity_count = record["actual_entity_count"] or 0

    # FAIL on zero entities
    assert entity_count > 0, \
        f"CRITICAL: Zero entities extracted from {test_file_path}"

    # FAIL on count mismatch
    assert entity_count >= 7, \
        f"Expected at least 7 entities (2 classes + 5 methods), got {entity_count}"
```

---

## Test #2: E2E File Indexing (Entity Links)
**File**: `tests/integration/test_e2e_file_indexing.py`
**Function**: `test_file_node_entity_linking`

### Why It Should Have Failed

Test uses `test_repo_small/utils.py` which should have:
- `HelperClass` (class)
- `helper_function` (function)
- `another_function` (function)

**Expected**: 3+ entities
**Actual**: 0 entities (production failure)

### What The Test Checks

```python
# Lines 378-390
entity_links = await file_tree_helper.get_entity_links(project_name)
assert len(entity_links) > 0, "Should have entity links"

utils_entities = [e for e in entity_links if "utils.py" in e["file_path"]]
assert len(utils_entities) >= 2, "utils.py should define at least 2 entities"

entity_names = [e["entity_name"] for e in utils_entities]
assert (
    "helper_function" in entity_names or "HelperClass" in entity_names
), "Should find function or class entities"
```

**Result**: Test PASSES ✅
- `len(entity_links) > 0` passes if ANY file has entities (not necessarily utils.py)
- `len(utils_entities) >= 2` uses weak assertion (could be from different project)
- `"helper_function" in entity_names or "HelperClass" in entity_names` uses OR logic (only needs one)

### What It SHOULD Check

```python
# Replace lines 383-390
utils_entities = [e for e in entity_links if "utils.py" in e["file_path"]]

# FAIL if zero entities for utils.py specifically
assert len(utils_entities) > 0, \
    f"CRITICAL: Zero entities extracted from utils.py"

# FAIL if exact count mismatch
EXPECTED_ENTITIES = {"HelperClass", "helper_function", "another_function"}
assert len(utils_entities) == len(EXPECTED_ENTITIES), \
    f"Expected {len(EXPECTED_ENTITIES)} entities, got {len(utils_entities)}"

# FAIL if specific entities missing
entity_names = set(e["entity_name"] for e in utils_entities)
missing_entities = EXPECTED_ENTITIES - entity_names

assert len(missing_entities) == 0, \
    f"Missing expected entities: {missing_entities}"
```

---

## Test #3: Relationship Extraction Fix
**File**: `tests/integration/test_relationship_extraction_fix.py`
**Function**: `test_langextract_endpoint_returns_relationships`

### Why It Should Have Failed

Test calls LangExtract with Python code:

```python
# Lines 27-40
test_code = '''import os
import sys
from pathlib import Path

class TestClass:
    def test_method(self):
        result = os.path.exists("test")
        return result

def main():
    obj = TestClass()
    obj.test_method()
    sys.exit(0)
'''
```

**Expected Entities**: 3
- `TestClass` (class)
- `test_method` (method)
- `main` (function)

**Actual**: 0 entities (if LangExtract broken)

### What The Test Checks

```python
# Lines 64-76
assert "relationships" in result, "Response missing 'relationships' field"
relationships = result["relationships"]

assert len(relationships) > 0, "Expected relationships to be extracted"

# Verify relationship types
rel_types = {r["relationship_type"] for r in relationships}
assert "IMPORTS" in rel_types, "Expected IMPORTS relationships to be detected"

# Verify import relationships
import_rels = [r for r in relationships if r["relationship_type"] == "IMPORTS"]
assert len(import_rels) >= 3, f"Expected at least 3 import relationships, got {len(import_rels)}"
```

**Result**: Test PASSES ✅ (only checks relationships, not entities)

### What It SHOULD Check

```python
# After line 82, add:

# Verify entities extracted
assert "enriched_entities" in result, "Response missing 'enriched_entities' field"
entities = result["enriched_entities"]

# FAIL if zero entities
assert len(entities) > 0, \
    f"CRITICAL: Zero entities extracted from test code"

# FAIL if expected entities missing
entity_names = {e["name"] for e in entities}
expected_names = {"TestClass", "test_method", "main"}

assert entity_names >= expected_names, \
    f"Missing expected entities: {expected_names - entity_names}"
```

---

## Test #4: Unit Test (Handler Coverage)
**File**: `services/intelligence/tests/unit/handlers/test_document_indexing_handler_coverage.py`
**Function**: `test_successful_indexing`

### Why It Should Have Failed

Test mocks LangExtract response:

```python
# Lines 214-222
async def mock_post(url, **kwargs):
    if "stamp-metadata" in url:
        return create_mock_response(
            {"hash": "blake3:abc", "dedupe_status": "new"}
        )
    elif "extract/code" in url:
        return create_mock_response({"entities": [], "relationships": []})  # ← ZERO ENTITIES!
    elif "assess/code" in url:
        return create_mock_response({"quality_score": 0.8})
    return MagicMock()
```

**Mocked Entities**: 0 (same as production failure)
**Test Result**: PASSES ✅

### Problem

- Mock returns 0 entities (line 219)
- Handler processes 0 entities successfully
- Test never checks if 0 entities is wrong
- **This is the EXACT production failure, but test passes!**

### What It SHOULD Do

```python
# Option 1: Use realistic mock data
elif "extract/document" in url:  # Fixed endpoint
    return create_mock_response({
        "enriched_entities": [
            {"entity_id": "TestClass", "name": "TestClass", "entity_type": "CLASS"},
            {"entity_id": "test_method", "name": "test_method", "entity_type": "FUNCTION"}
        ],
        "relationships": [
            {"source_entity_id": "test.py", "target_entity_id": "os", "relationship_type": "IMPORTS"}
        ]
    })

# Option 2: Call real LangExtract service
# Don't mock - use real HTTP client and verify actual extraction
```

---

## Test #5: Memgraph Entity Verification (Missing)
**Expected File**: `tests/integration/test_memgraph_entity_count.py`
**Status**: ❌ DOES NOT EXIST

### What This Test Should Do

```python
@pytest.mark.asyncio
async def test_memgraph_entity_count_after_ingestion():
    """
    Verify that Memgraph entity_count matches actual DEFINES relationships.

    This test would have caught the production failure.
    """

    project_name = "test_entity_count_validation"

    # Ingest known file
    test_code = '''
class Manager:
    def login(self): pass
    def logout(self): pass

def init(): pass
'''

    await publish_kafka_event(project_name, "test.py", test_code)
    await asyncio.sleep(5)

    # Query Memgraph
    async with memgraph_driver.session() as session:
        result = await session.run("""
            MATCH (f:FILE {project_name: $project, path: "test.py"})
            OPTIONAL MATCH (f)-[:DEFINES]->(e:ENTITY)
            RETURN f.entity_count as stored_count,
                   count(e) as actual_count
        """, project=project_name)

        record = await result.single()

        stored_count = record["stored_count"] or 0
        actual_count = record["actual_count"] or 0

    # CRITICAL: Fail if counts don't match
    assert stored_count > 0, "CRITICAL: Stored entity_count is zero"
    assert actual_count > 0, "CRITICAL: No DEFINES relationships found"
    assert stored_count == actual_count, \
        f"Entity count mismatch: stored={stored_count}, actual={actual_count}"

    # Fail if below expected
    assert actual_count >= 3, f"Expected 3 entities (1 class + 2 methods), got {actual_count}"
```

**Why This Would Have Caught The Bug**:
- Queries actual DEFINES relationships (would be 0)
- Compares stored count vs actual count (would mismatch)
- Fails on 0 entities
- **This test doesn't exist, so bug wasn't caught**

---

## Summary

| Test | Current Check | Should Check | Would Catch Bug? |
|------|--------------|--------------|-----------------|
| E2E Ingestion Smoke | FILE node exists | `entity_count > 0` | ✅ YES |
| E2E File Indexing | `entity_links > 0` | Exact count per file | ✅ YES |
| Relationship Fix | Relationships exist | Entities extracted | ✅ YES |
| Handler Coverage (unit) | HTTP 200 | Real/realistic entities | ✅ YES |
| Memgraph Entity Count | ❌ Doesn't exist | Count match validation | ✅ YES |

**Conclusion**: Every test listed above should have failed but passed because they check **service availability** instead of **data correctness**.

**Fix**: Add the assertions shown above to catch future failures.
