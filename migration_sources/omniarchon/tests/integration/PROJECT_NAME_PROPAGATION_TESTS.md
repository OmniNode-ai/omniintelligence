# Project Name Propagation Tests

**File**: `tests/integration/test_project_name_propagation.py`
**Created**: 2025-11-11
**Status**: ✅ Ready for TDD (Test-Driven Development)

## Overview

Comprehensive integration tests for validating `project_name` property propagation across all node types (PROJECT, DIRECTORY, FILE) in the Memgraph file tree graph.

## Critical Bug Being Tested

**Issue**: 1,292+ orphaned FILE nodes due to missing `project_name` property

**Root Cause**: `DirectoryIndexer._create_contains_relationship()` (lines 316-322) creates stub nodes via MERGE without properly setting `project_name` property.

**Impact**:
- FILE nodes exist in database but are "invisible" to queries filtering by `project_name`
- Files appear orphaned even though they have correct `entity_id`
- Tree traversal from PROJECT root fails to find these files
- Breaks file discovery and tree navigation

## Test Suite Structure

### 9 Comprehensive Tests

#### TestProjectNamePropagation (7 tests)

1. **test_project_node_has_project_name**
   - Validates PROJECT nodes have `project_name` property
   - Base case - should always pass

2. **test_directory_nodes_have_project_name**
   - Validates DIRECTORY nodes have `project_name` property
   - Tests `_create_directory_node()` method

3. **test_stub_nodes_have_project_name** ⭐ **CRITICAL**
   - Tests stub FILE nodes created during MERGE operations
   - **This test exposes the primary bug**
   - Expected to FAIL until DirectoryIndexer is fixed

4. **test_file_nodes_have_project_name**
   - Validates all FILE nodes are queryable via `project_name`
   - Tests complete file visibility

5. **test_merge_updates_project_name**
   - Validates MERGE operations update existing nodes
   - Tests re-ingestion scenarios

6. **test_no_orphans_after_ingestion** ⭐ **CRITICAL**
   - End-to-end validation: 0 orphaned files after ingestion
   - Three-pronged orphan detection:
     - Files with no incoming CONTAINS relationship
     - Files unreachable from PROJECT root
     - File count verification

7. **test_all_nodes_reachable_via_project_name_filter**
   - Validates all nodes findable via `project_name` filtering
   - Tests tree connectivity with filtering

#### TestProjectNameEdgeCases (2 tests)

8. **test_multiple_projects_isolated**
   - Tests project isolation via `project_name`
   - Validates no cross-project interference

9. **test_empty_project_name_handling**
   - Tests error handling for invalid `project_name`

## Running the Tests

### All Tests
```bash
pytest tests/integration/test_project_name_propagation.py -v
```

### Specific Test
```bash
pytest tests/integration/test_project_name_propagation.py::TestProjectNamePropagation::test_stub_nodes_have_project_name -v
```

### With Detailed Output
```bash
pytest tests/integration/test_project_name_propagation.py -v -s
```

### Stop on First Failure
```bash
pytest tests/integration/test_project_name_propagation.py -v -x
```

### Integration Tests Only
```bash
pytest tests/integration/test_project_name_propagation.py -v -m integration
```

## Expected Test Results

### Phase 1: Before Code Fixes (Current State)
**Expected**: Most tests will FAIL

Critical failures expected:
- ❌ `test_stub_nodes_have_project_name` - Stub nodes lack `project_name`
- ❌ `test_file_nodes_have_project_name` - Files not findable via filtering
- ❌ `test_no_orphans_after_ingestion` - Orphaned files detected

### Phase 2: After DirectoryIndexer Fixes
**Expected**: All tests should PASS

Required fixes in `services/intelligence/src/services/directory_indexer.py`:

1. **Line 316-322**: Update `_create_contains_relationship()` MERGE logic
   ```python
   # Current (BUG):
   MERGE (child:{child_type} {{entity_id: $child_id}})

   # Fixed:
   MERGE (child:{child_type} {{entity_id: $child_id}})
   ON CREATE SET child.project_name = $project_name,
                 child.path = $child_path,
                 child.created_at = $timestamp
   ```

2. Ensure `project_name` is extracted from `entity_id` and passed to query

## Test Coverage

**Target**: 95%+ coverage of `DirectoryIndexer` methods

**Covered Scenarios**:
- ✅ Simple project structures
- ✅ Nested directory hierarchies (3+ levels deep)
- ✅ Root-level files (linked to PROJECT)
- ✅ Mixed file locations (root + subdirectories)
- ✅ MERGE operations (re-ingestion)
- ✅ Multiple projects (isolation testing)
- ✅ Edge cases (empty project names)

## Assertion Messages

Tests provide clear, actionable assertion messages:

```
BUG DETECTED: Stub FILE node created without project_name property!
entity_id: file:project:path/to/file.py
path: /path/to/file.py
project_name: MISSING

This is the root cause of orphaned files - nodes exist but are unreachable
via project_name queries.
```

## Integration with CI/CD

Recommended CI pipeline:
1. Run tests BEFORE code changes (verify they fail as expected)
2. Apply DirectoryIndexer fixes
3. Run tests AFTER code changes (verify they pass)
4. Deploy only if all tests pass

## Dependencies

Required packages (already in environment):
- `pytest >= 7.0.0`
- `pytest-asyncio >= 0.21.0`
- `neo4j >= 5.0.0` (Memgraph driver)

Required services:
- Memgraph database at `bolt://localhost:7687`
- Or set `MEMGRAPH_URI` environment variable

## Test Data Cleanup

Each test includes automatic cleanup:
- `test_project_cleanup` fixture removes all test data
- Runs before AND after each test
- No manual cleanup required

## Related Files

- **Source**: `services/intelligence/src/services/directory_indexer.py`
- **Related Tests**: `tests/integration/test_orphan_prevention.py`
- **Documentation**: `TREE_GRAPH_FIX_2025-11-10.md`

## Debugging Failed Tests

### If test_stub_nodes_have_project_name fails:
1. Check Memgraph query in `_create_contains_relationship()`
2. Verify `project_name` is extracted from `entity_id`
3. Ensure MERGE includes `ON CREATE SET project_name = $project_name`

### If test_no_orphans_after_ingestion fails:
1. Run orphan query manually:
   ```cypher
   MATCH (f:FILE)
   WHERE f.project_name = 'test_project_name_propagation'
   OPTIONAL MATCH (parent)-[:CONTAINS]->(f)
   WHERE parent IS NULL
   RETURN f.path, f.entity_id, f.project_name
   ```
2. Check which files are orphaned and why
3. Trace back to their creation in DirectoryIndexer

### If tests hang:
- Check Memgraph is running: `docker ps | grep memgraph`
- Verify connection: `bolt://localhost:7687`
- Check logs: `docker logs memgraph`

## Success Criteria

**Definition of Done**:
- ✅ All 9 tests pass
- ✅ 0 orphaned files in test scenarios
- ✅ All nodes have `project_name` property
- ✅ Tree traversal works with `project_name` filtering
- ✅ Re-ingestion (MERGE) preserves `project_name`

## Next Steps

### Phase 1: Validate Tests (Current)
```bash
# 1. Run tests to verify they fail as expected
pytest tests/integration/test_project_name_propagation.py -v

# 2. Document which tests fail and why
pytest tests/integration/test_project_name_propagation.py -v --tb=short > test_results_before_fix.txt
```

### Phase 2: Fix Code
```bash
# 1. Apply fixes to DirectoryIndexer
# 2. Run tests to verify fixes work
pytest tests/integration/test_project_name_propagation.py -v

# 3. Document passing tests
pytest tests/integration/test_project_name_propagation.py -v --tb=short > test_results_after_fix.txt
```

### Phase 3: Validate on Real Data
```bash
# 1. Clear existing data
./scripts/clear_databases.sh --force

# 2. Re-ingest repository
python3 scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
  --project-name omniarchon \
  --kafka-servers 192.168.86.200:29092

# 3. Verify environment health
python3 scripts/verify_environment.py --verbose
```

## Questions or Issues?

If tests fail unexpectedly:
1. Check Memgraph connection and health
2. Verify test data cleanup is working
3. Review assertion messages for debugging hints
4. Check `DirectoryIndexer` implementation changes

---

**Test Development Approach**: Test-Driven Development (TDD)
**Expected Initial State**: Tests FAIL (exposing bugs)
**Expected Final State**: Tests PASS (bugs fixed)
