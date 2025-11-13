# Running Entity ID Schema Validation Tests

## Overview

Comprehensive integration tests for validating entity_id format consistency across the Memgraph knowledge graph. These tests prevent regression of the entity_id schema mismatch bug where PLACEHOLDER nodes were created instead of linking to REAL indexed files.

**Test File**: `tests/integration/test_entity_id_schema_validation.py`

## Prerequisites

1. **Services Running**:
   - Memgraph (bolt://localhost:7687)
   - Kafka/Redpanda (192.168.86.200:29092)
   - archon-intelligence (localhost:8053)
   - archon-bridge (localhost:8054)
   - archon-search (localhost:8055)
   - Qdrant (localhost:6333)

2. **Start Services**:
   ```bash
   docker compose up -d
   ```

3. **Verify Health**:
   ```bash
   curl http://localhost:8053/health
   curl http://localhost:8054/health
   curl http://localhost:8055/health
   ```

## Running Tests

### Run All Entity ID Validation Tests

```bash
# From repository root
pytest tests/integration/test_entity_id_schema_validation.py -v

# With detailed output
pytest tests/integration/test_entity_id_schema_validation.py -vv -s

# With markers
pytest tests/integration/test_entity_id_schema_validation.py -v -m "slow"
```

### Run Individual Test Cases

```bash
# Test 1: Hash-based entity_id format validation
pytest tests/integration/test_entity_id_schema_validation.py::test_all_file_nodes_use_hash_based_entity_ids -v

# Test 2: No PLACEHOLDER nodes
pytest tests/integration/test_entity_id_schema_validation.py::test_no_placeholder_nodes_exist -v

# Test 3: Relationship integrity
pytest tests/integration/test_entity_id_schema_validation.py::test_all_relationships_connect_to_real_nodes -v

# Test 4: Graph traversal
pytest tests/integration/test_entity_id_schema_validation.py::test_graph_traversal_through_imports -v

# Test 5: Format validation logic
pytest tests/integration/test_entity_id_schema_validation.py::test_entity_id_format_validation -v

# Test 6: Orphan detection
pytest tests/integration/test_entity_id_schema_validation.py::test_orphaned_file_detection -v

# Test 7: Consistency across operations
pytest tests/integration/test_entity_id_schema_validation.py::test_entity_id_consistency_across_operations -v
```

### Run with Coverage

```bash
pytest tests/integration/test_entity_id_schema_validation.py \
  --cov=services/intelligence/storage \
  --cov-report=html \
  --cov-report=term-missing \
  -v
```

### Run in CI/CD Pipeline

The tests are automatically included in the CI pipeline:

```yaml
# .github/workflows/ci.yml
- name: Run test suite
  run: |
    poetry run pytest tests/ \
      -n auto \
      --tb=short \
      --junitxml=junit.xml
```

## Test Coverage

### Test Cases (7 comprehensive tests)

1. **test_all_file_nodes_use_hash_based_entity_ids**
   - Validates ALL FILE nodes use `file_{hash12}` format
   - Ensures ZERO nodes contain ':' character
   - Regex validation: `^file_[a-f0-9]{12}$`

2. **test_no_placeholder_nodes_exist**
   - Ensures no PLACEHOLDER stub nodes after indexing
   - Checks for `file:project:module` format nodes
   - Validates against path-based entity_ids

3. **test_all_relationships_connect_to_real_nodes**
   - Validates relationship source/target entity_ids
   - Checks for full properties (>4) on connected nodes
   - Ensures no relationships to `name='unknown'` nodes

4. **test_graph_traversal_through_imports**
   - Verifies graph traversal via IMPORTS relationships
   - Validates all nodes in paths have hash-based IDs
   - Tests multi-hop path traversal (up to 5 hops)

5. **test_entity_id_format_validation**
   - Tests entity_id validator function
   - Validates against 12+ test cases
   - Clear error messages for violations

6. **test_orphaned_file_detection**
   - Detects REAL FILE nodes without relationships
   - Distinguishes expected vs unexpected orphans
   - Validates schema fixes don't create orphans

7. **test_entity_id_consistency_across_operations**
   - Tests re-indexing produces same entity_ids
   - Validates format consistency across updates
   - Ensures deterministic entity_id generation

## Success Criteria

All tests must pass for schema compliance:

- ✅ All FILE nodes use `file_{hash}` format
- ✅ Zero PLACEHOLDER nodes exist
- ✅ All relationships connect to REAL nodes
- ✅ Graph traversal works correctly
- ✅ Entity_id format validation passes
- ✅ No unexpected orphaned nodes
- ✅ Consistent entity_ids across operations

## Test Data

### Test Fixtures

Located in `tests/fixtures/`:
- `test_repo_small/` - 3 files (main.py, utils.py, orphan.py)
- `test_repo_complex/` - 6+ files with nested imports

### Expected Entity_ID Formats

**Valid FILE nodes**:
```
file_91f521860bc3  ✅
file_abc123def456  ✅
file_000000000000  ✅
```

**Invalid PLACEHOLDER nodes**:
```
file:omniarchon:asyncio              ❌
file:omniarchon:archon://projects... ❌
file:project:module.submodule        ❌
```

## Debugging Failed Tests

### Common Failures

1. **"Found X placeholder nodes"**
   - Issue: Relationship creation creating stubs
   - Fix: Update relationship code to lookup existing nodes
   - Check: `services/intelligence/storage/memgraph_adapter.py`

2. **"Entity_id doesn't match hash pattern"**
   - Issue: Entity_id generation using wrong format
   - Fix: Ensure `file_{hash[:12]}` format used
   - Check: `_create_file_node()` method

3. **"Relationships to PLACEHOLDER nodes"**
   - Issue: Relationships not resolving to indexed files
   - Fix: Implement entity_id lookup before creating relationship
   - Check: Import resolution logic

### Inspection Queries

```bash
# Count PLACEHOLDER nodes
docker exec memgraph bash -c "echo \"
  MATCH (f:FILE)
  WHERE f.entity_id CONTAINS ':'
  RETURN count(f) as placeholder_count
\" | mgconsole"

# Show all entity_id formats
docker exec memgraph bash -c "echo \"
  MATCH (f:FILE)
  RETURN f.entity_id, f.path
  ORDER BY f.entity_id
  LIMIT 20
\" | mgconsole"

# Find orphaned REAL nodes
docker exec memgraph bash -c "echo \"
  MATCH (f:FILE)
  WHERE f.entity_id STARTS WITH 'file_'
  WITH f, size([(f)-[]-() | 1]) as rel_count
  WHERE rel_count = 0
  RETURN f.entity_id, f.path, rel_count
\" | mgconsole"
```

## Integration with Existing Tests

These tests complement existing integration tests:

- `test_e2e_file_indexing.py` - End-to-end workflow validation
- `test_data_consistency.py` - Data integrity checks
- `test_cross_service.py` - Cross-service communication

**Key Difference**: This test suite focuses specifically on **entity_id schema compliance** to prevent regression.

## Performance

- **Test Duration**: ~2-3 minutes (all 7 tests)
- **Timeout**: 30 seconds per test
- **Parallelization**: Compatible with `pytest -n auto`
- **Resource Usage**: Requires Memgraph + Kafka (managed externally)

## CI/CD Integration

### Automatic Execution

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

### Required Checks

All 7 tests must pass for PR approval:
```bash
✅ test_all_file_nodes_use_hash_based_entity_ids
✅ test_no_placeholder_nodes_exist
✅ test_all_relationships_connect_to_real_nodes
✅ test_graph_traversal_through_imports
✅ test_entity_id_format_validation
✅ test_orphaned_file_detection
✅ test_entity_id_consistency_across_operations
```

## References

- **Format Spec**: `ENTITY_ID_FORMAT_REFERENCE.md`
- **Analysis Report**: `MEMGRAPH_SCHEMA_ANALYSIS_REPORT.md`
- **Fix Documentation**: [Link to fix PR/commit]
- **Existing Tests**: `tests/integration/test_e2e_file_indexing.py`

## Troubleshooting

### Services Not Running

```bash
# Check service health
docker compose ps

# Start missing services
docker compose up -d memgraph qdrant

# Check logs
docker logs archon-intelligence
docker logs archon-bridge
```

### Test Fixtures Missing

```bash
# Verify fixtures exist
ls -la tests/fixtures/test_repo_small/
ls -la tests/fixtures/test_repo_complex/

# If missing, check repository
git status tests/fixtures/
```

### Environment Variables

```bash
# Required environment variables
export MEMGRAPH_URI="bolt://localhost:7687"
export KAFKA_BOOTSTRAP_SERVERS="192.168.86.200:29092"
export INTELLIGENCE_URL="http://localhost:8053"
export BRIDGE_URL="http://localhost:8054"
export SEARCH_URL="http://localhost:8055"
export QDRANT_URL="http://localhost:6333"
```

## Contributing

When modifying entity_id generation code:

1. **Run these tests FIRST** to establish baseline
2. Make your changes
3. **Run these tests AGAIN** to verify no regression
4. Add new test cases if new entity_id formats added
5. Update this documentation if behavior changes

---

**Created**: 2025-11-09
**Purpose**: Prevent entity_id schema mismatch regression
**Maintainer**: Archon Intelligence Team
