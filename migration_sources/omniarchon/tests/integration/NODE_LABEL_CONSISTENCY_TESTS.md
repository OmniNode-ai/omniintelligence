# Node Label Consistency Tests

**Created**: 2025-11-11
**Test File**: `tests/integration/test_node_label_consistency.py`
**Status**: ✅ Tests created and running (failing as expected)

## Overview

Comprehensive test suite to validate that all Memgraph node labels follow Neo4j/Memgraph best practices:
- **PascalCase** for most labels (`:File`, `:Directory`)
- **Intentional UPPERCASE** for project markers (`:PROJECT`)

## Test Results (Initial Run)

```
✅ test_memgraph_connectivity          - PASSED (connectivity verified)
✅ test_get_all_labels_inventory       - PASSED (inventory complete)
❌ test_no_uppercase_file_labels       - FAILED (4047 :FILE nodes found)
❌ test_all_file_nodes_pascalcase      - FAILED (0 :File nodes, 4047 :FILE nodes)
⏭️  test_directory_labels_consistent   - SKIPPED (no directory nodes)
✅ test_project_labels_consistent      - PASSED (1 :PROJECT node correct)
❌ test_label_migration_summary        - FAILED (1 inconsistency issue)
```

## Current State

**Found Issues**:
- **4047 nodes** with incorrect label `:FILE` (should be `:File`)
- **0 nodes** with correct label `:File`
- **1 PROJECT node** correctly using `:PROJECT` (uppercase by design)
- **No directory nodes** found yet

**Sample Inconsistent Nodes**:
```
SLACK_ALERTING_SUMMARY.md
INGESTION_PIPELINE_FIXES.md
MEMGRAPH_LOGGING_SUMMARY.md
... (4044 more)
```

## Test Coverage

### Test 1: `test_no_uppercase_file_labels`
**Purpose**: Verify no nodes have `:FILE` label (uppercase)
**Expected**: 0 nodes with `:FILE`
**Actual**: 4047 nodes with `:FILE`
**Status**: ❌ FAILING (as expected before migration)

### Test 2: `test_all_file_nodes_pascalcase`
**Purpose**: Verify all file nodes use `:File` label (PascalCase)
**Expected**: All file nodes use `:File`
**Actual**: 0 `:File`, 4047 `:FILE`, 0 `:file`
**Status**: ❌ FAILING (as expected before migration)

### Test 3: `test_directory_labels_consistent`
**Purpose**: Verify directory nodes use `:Directory` (not `:DIRECTORY`)
**Expected**: All directory nodes use `:Directory`
**Actual**: No directory nodes found
**Status**: ⏭️ SKIPPED (no data to test)

### Test 4: `test_project_labels_consistent`
**Purpose**: Verify project nodes use `:PROJECT` (intentionally uppercase)
**Expected**: All project nodes use `:PROJECT`
**Actual**: 1 node with `:PROJECT` ✓
**Status**: ✅ PASSING

### Test 5: `test_label_migration_summary`
**Purpose**: Provide overall label consistency report
**Expected**: All labels consistent
**Actual**: 1 inconsistency issue found
**Status**: ❌ FAILING (as expected before migration)

## Migration Action Items

The tests provide clear migration guidance:

1. **Update `directory_indexer.py`**
   - Change `child_type="FILE"` to `child_type="File"` (lines 164, 172)
   - Change `parent_type="DIRECTORY"` to `parent_type="Directory"` (line 171)

2. **Run Cypher Migration Queries**
   ```cypher
   // Migrate :FILE to :File
   MATCH (n:FILE)
   SET n:File
   REMOVE n:FILE
   RETURN count(n) as migrated_files;

   // Migrate :DIRECTORY to :Directory (when they exist)
   MATCH (n:DIRECTORY)
   SET n:Directory
   REMOVE n:DIRECTORY
   RETURN count(n) as migrated_directories;
   ```

3. **Re-run Tests to Verify**
   ```bash
   python3 -m pytest tests/integration/test_node_label_consistency.py -v
   ```

## Expected Behavior After Migration

After Phase 3 label migration:

```
✅ test_memgraph_connectivity          - PASSED
✅ test_get_all_labels_inventory       - PASSED
✅ test_no_uppercase_file_labels       - PASSED (0 :FILE nodes)
✅ test_all_file_nodes_pascalcase      - PASSED (4047 :File nodes)
✅ test_directory_labels_consistent    - PASSED (all :Directory)
✅ test_project_labels_consistent      - PASSED (:PROJECT intentional)
✅ test_label_migration_summary        - PASSED (all consistent)
```

## Running the Tests

```bash
# Run all label consistency tests
python3 -m pytest tests/integration/test_node_label_consistency.py -v

# Run specific test
python3 -m pytest tests/integration/test_node_label_consistency.py::test_no_uppercase_file_labels -v

# Run with detailed output
python3 -m pytest tests/integration/test_node_label_consistency.py -v --tb=short -s
```

## Benefits

1. **Schema Validation** - Ensures consistent label naming across the graph
2. **Best Practices** - Follows Neo4j/Memgraph conventions
3. **Query Optimization** - Consistent labels improve query performance
4. **Maintainability** - Clear schema makes debugging easier
5. **Documentation** - Tests serve as schema documentation
6. **Regression Prevention** - Catches label inconsistencies early

## Integration with CI/CD

These tests should be run:
- **Before** label migration (to establish baseline)
- **After** label migration (to verify success)
- **In CI/CD** (to prevent regression)

## References

- **Test File**: `/Volumes/PRO-G40/Code/omniarchon/tests/integration/test_node_label_consistency.py`
- **Source File**: `/Volumes/PRO-G40/Code/omniarchon/services/intelligence/src/services/directory_indexer.py:164,172`
- **Neo4j Naming Conventions**: https://neo4j.com/docs/cypher-manual/current/syntax/naming/
- **Memgraph Documentation**: https://memgraph.com/docs/
