# Directory Tree Building Integration

**Date**: 2025-11-10
**Correlation ID**: 61747b8f-297d-4670-9f3d-c6c651606ac3
**Status**: ✅ Complete

## Overview

Integrated automatic directory tree building into the bulk ingestion workflow. The tree builder now runs automatically after file indexing completes, eliminating the need for manual tree building as a separate step.

## Changes Made

### 1. Updated Documentation
- **File**: `scripts/bulk_ingest_repository.py`
- Added feature description: "Automatic directory tree building (can be skipped)"
- Updated usage examples to show `--skip-tree` flag
- Updated workflow documentation to include tree building as phase 5

### 2. Enhanced BulkIngestApp Class

#### Added Parameters
```python
def __init__(
    self,
    ...
    skip_tree: bool = False,  # NEW: Control tree building
    ...
):
```

#### New Method: `build_directory_tree()`
- **Location**: Lines 302-434
- **Purpose**: Build PROJECT and DIRECTORY nodes with CONTAINS relationships in Memgraph
- **Features**:
  - Lazy imports (avoids dependency issues if imports fail)
  - Queries Memgraph for existing FILE nodes
  - Extracts file paths from `archon://` URIs
  - Creates complete directory hierarchy
  - Comprehensive error handling (non-fatal failures)
  - Detailed logging with correlation ID tracking
  - Graceful handling of missing FILE nodes

#### Integration into Workflow
- **Location**: Line 579 (after Kafka producer shutdown, before results summary)
- **Behavior**:
  - Automatically called after batch processing completes
  - Non-fatal: Failures don't break ingestion
  - Skippable via `--skip-tree` flag

### 3. CLI Enhancements

#### New Flag: `--skip-tree`
```bash
--skip-tree    Skip automatic directory tree building after indexing
```

#### Updated Help Examples
```bash
# Skip automatic tree building
python bulk_ingest_repository.py /path/to/project --skip-tree
```

### 4. Configuration Logging
Added tree building status to startup configuration:
```
Skip tree building: False
```

## Usage

### Default Behavior (Automatic Tree Building)
```bash
# Tree building happens automatically after file indexing
python3 scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
  --project-name omniarchon
```

**Output includes**:
```
======================================================================
🌳 BUILDING DIRECTORY TREE
======================================================================
Building directory hierarchy for omniarchon...
📁 Found 1234 FILE nodes in Memgraph
✅ Directory tree built successfully: 1 projects, 156 directories, 1234 files linked, 1391 relationships
```

### Skip Tree Building
```bash
# Skip tree building for faster ingestion (when tree already exists)
python3 scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
  --project-name omniarchon \
  --skip-tree
```

**Output includes**:
```
⏭️  Skipping directory tree building (--skip-tree enabled)
```

### Manual Tree Building (Still Available)
```bash
# If needed, tree builder script still works standalone
python3 scripts/build_directory_tree.py omniarchon /Volumes/PRO-G40/Code/omniarchon
```

## Error Handling

Tree building failures are **non-fatal** and don't break ingestion:

### Import Errors
```
⚠️  Cannot import tree building dependencies: No module named 'src.services.directory_indexer'.
    Tree building skipped (non-fatal).
```

### Runtime Errors
```
⚠️  Failed to build directory tree: Connection refused.
    This is non-fatal - ingestion completed successfully.
```

### Missing FILE Nodes
```
⚠️  No FILE nodes found for project: omniarchon.
    Tree building skipped.
```

## Architecture

### Workflow Sequence
1. **File Discovery** - Discover files in project
2. **Kafka Producer Init** - Initialize event bus connection
3. **Batch Processing** - Index files via Kafka events
4. **Kafka Producer Shutdown** - Clean up connections
5. **Tree Building** ⭐ (NEW) - Build directory hierarchy
6. **Results Summary** - Report success/failure

### Dependencies
- **Memgraph Adapter**: `storage.memgraph_adapter.MemgraphKnowledgeAdapter`
- **Directory Indexer**: `src.services.directory_indexer.DirectoryIndexer`
- **Environment Variable**: `MEMGRAPH_URI` (default: `bolt://localhost:7687`)

### Data Flow
```
FILE nodes (Memgraph)
    ↓ Query
Extract file paths from archon:// URIs
    ↓ Parse
Build file_paths list + entity_id mapping
    ↓ Pass to
DirectoryIndexer.index_directory_hierarchy()
    ↓ Creates
PROJECT node → DIRECTORY nodes → CONTAINS relationships
```

## Benefits

1. **Automation**: No manual tree building step required
2. **Consistency**: Tree always built after indexing
3. **Flexibility**: Can skip if needed via `--skip-tree`
4. **Resilience**: Failures don't break ingestion
5. **Visibility**: Clear logging shows tree building progress
6. **Integration**: Seamless workflow enhancement

## Testing

### Verify Syntax
```bash
python3 -m py_compile scripts/bulk_ingest_repository.py
# No output = success
```

### View Help
```bash
python3 scripts/bulk_ingest_repository.py --help
# Shows --skip-tree flag
```

### Test Dry Run
```bash
python3 scripts/bulk_ingest_repository.py . --dry-run --skip-tree
# Verifies flag parsing
```

### Test Integration (Full)
```bash
# Index small project to verify tree building works
python3 scripts/bulk_ingest_repository.py /path/to/small/project \
  --project-name test-project
# Should show tree building output
```

### Verify Tree Structure
```cypher
// Query Memgraph to verify tree structure
MATCH (p:PROJECT {name: "test-project"})
OPTIONAL MATCH (p)-[:CONTAINS*]->(d:DIRECTORY)
OPTIONAL MATCH (p)-[:CONTAINS*]->(f:FILE)
RETURN count(DISTINCT p) as projects,
       count(DISTINCT d) as directories,
       count(DISTINCT f) as files
```

## Backward Compatibility

- ✅ Existing bulk ingestion functionality unchanged
- ✅ Standalone tree builder script still works
- ✅ Default behavior: Tree building enabled (non-breaking)
- ✅ Opt-out available via `--skip-tree`
- ✅ All existing CLI flags and options preserved

## Future Enhancements

Potential improvements for future iterations:

1. **Parallel Processing**: Build tree while Kafka events are being consumed
2. **Incremental Updates**: Only update changed directories
3. **Caching**: Cache directory structure for faster rebuilds
4. **Validation**: Verify tree completeness after building
5. **Metrics**: Track tree building performance
6. **Recovery**: Auto-retry on transient failures

## Related Files

- **Integration**: `scripts/bulk_ingest_repository.py` (lines 302-434, 579)
- **Original Script**: `scripts/build_directory_tree.py` (unchanged, still functional)
- **Directory Indexer**: `services/intelligence/src/services/directory_indexer.py`
- **Memgraph Adapter**: `services/intelligence/storage/memgraph_adapter.py`

## Success Criteria

All criteria met:

- ✅ Tree builder automatically called after bulk ingestion completes
- ✅ Existing bulk ingestion functionality unchanged
- ✅ Optional `--skip-tree` flag available
- ✅ Error handling prevents tree building failures from breaking ingestion
- ✅ Logging shows tree building progress
- ✅ Help documentation updated
- ✅ Syntax validated
- ✅ Non-fatal failure handling implemented

## Notes

- Tree building requires Memgraph to be running (`archon-memgraph:7687`)
- FILE nodes must exist in Memgraph (created during bulk ingestion)
- Tree building is skipped if no FILE nodes found (warning logged)
- Imports are lazy to avoid breaking the script if dependencies are missing
- All errors are logged but don't affect ingestion exit code
