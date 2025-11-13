# Orphan Node Prevention Implementation

**Created**: 2025-11-11
**Correlation ID**: 07f64ef3-3b04-4bc3-94d8-0040fb044276
**Status**: ✅ Partial Implementation Complete

## Overview

This document details the implementation of root cause prevention mechanisms for orphan FILE nodes in Memgraph. Orphan nodes are FILE nodes that lack incoming CONTAINS relationships from DIRECTORY or PROJECT nodes, breaking the file tree hierarchy.

## Completed Work

### 1. fix_orphans.py - Automated Remediation Script ✅

**Location**: `/Volumes/PRO-G40/Code/omniarchon/scripts/fix_orphans.py`

**Features**:
- Automatic orphan detection via Cypher query
- Dry-run mode (default) for safe previewing
- Path parsing to extract directory components
- Automatic DIRECTORY node creation for missing parents
- CONTAINS relationship creation (parent → file)
- Comprehensive logging with correlation IDs
- Batch processing support

**Usage**:
```bash
# Detect orphans (dry-run mode)
python scripts/fix_orphans.py omniarchon

# Fix orphans (apply changes)
python scripts/fix_orphans.py omniarchon --apply

# Verbose logging
python scripts/fix_orphans.py omniarchon --apply --verbose
```

**Key Functions**:
- `detect_orphans()` - Query Memgraph for orphaned FILE nodes
- `parse_file_path()` - Extract directory components from file paths
- `ensure_directory_chain()` - Create missing DIRECTORY nodes recursively
- `ensure_project_node()` - Ensure PROJECT node exists
- `create_contains_relationship()` - Link parent → child with CONTAINS
- `fix_orphan()` - Complete fix workflow for single orphan

**Exit Codes**:
- `0` - Success (no orphans or all fixed)
- `1` - Failure (orphans detected and couldn't fix, or critical error)

### 2. Orphan Detection in bulk_ingest_repository.py ✅

**Location**: `scripts/bulk_ingest_repository.py` (lines 518-594)

The script already has orphan detection logic in `build_directory_tree()`:

```python
# Detect orphaned FILE nodes (files without CONTAINS relationship)
orphan_query = """
MATCH (f:FILE)
WHERE f.project_name = $project_name
AND NOT EXISTS {
    MATCH (d:DIRECTORY)-[:CONTAINS]->(f)
}
AND NOT EXISTS {
    MATCH (p:PROJECT)-[:CONTAINS]->(f)
}
RETURN f.path as file_path, f.entity_id as entity_id
LIMIT 100
"""
```

This logs warnings when orphans are detected (lines 547-583).

## Remaining Work

### 3. Remove --skip-tree Flag (bulk_ingest_repository.py)

**Changes Required**:

1. **Line 16**: Change docstring
   ```python
   # FROM:
   - Automatic directory tree building (can be skipped)

   # TO:
   - Mandatory directory tree building with validation
   ```

2. **Line 29**: Remove --skip-tree example
   ```python
   # DELETE:
   # Skip automatic tree building
   python bulk_ingest_repository.py /path/to/project --skip-tree

   # ADD:
   # Force rebuild of directory tree
   python bulk_ingest_repository.py /path/to/project --rebuild-tree
   ```

3. **Line 48**: Update changelog
   ```python
   # FROM:
   Updated: 2025-11-10 - Added automatic directory tree building

   # TO:
   Updated: 2025-11-11 - Made directory tree building mandatory with validation
   ```

4. **Line 266**: Change parameter
   ```python
   # FROM:
   skip_tree: bool = False,

   # TO:
   rebuild_tree: bool = False,
   strict_validation: bool = False,
   ```

5. **Line 284**: Update docstring
   ```python
   # FROM:
   skip_tree: If True, skip automatic directory tree building

   # TO:
   rebuild_tree: If True, force rebuild of directory tree (even if exists)
   strict_validation: If True, fail ingestion if orphan nodes detected
   ```

6. **Line 296**: Update instance variable
   ```python
   # FROM:
   self.skip_tree = skip_tree

   # TO:
   self.rebuild_tree = rebuild_tree
   self.strict_validation = strict_validation
   ```

7. **Line 321**: Update logging
   ```python
   # FROM:
   self.logger.info(f"Skip tree building: {self.skip_tree}")

   # TO:
   self.logger.info(f"Rebuild tree: {self.rebuild_tree}")
   self.logger.info(f"Strict validation: {self.strict_validation}")
   ```

8. **Line 358-368**: Remove skip logic from build_directory_tree()
   ```python
   # DELETE ENTIRE BLOCK:
   if self.skip_tree:
       log_structured(
           self.logger,
           logging.INFO,
           "⏭️  Skipping directory tree building (--skip-tree enabled)",
           correlation_id,
           phase="tree_building",
           operation="skip",
           project_name=self.project_name,
       )
       return True
   ```

9. **Line 372**: Update header
   ```python
   # FROM:
   self.logger.info("🌳 BUILDING DIRECTORY TREE")

   # TO:
   self.logger.info("🌳 BUILDING DIRECTORY TREE (MANDATORY)")
   ```

10. **Lines 599-633**: Make tree building errors FATAL (not warnings)
    ```python
    # FROM (line 600):
    log_structured(
        self.logger,
        logging.WARNING,
        f"⚠️  Cannot import tree building dependencies: {e}",
        ...
    )
    return False

    # TO:
    error_msg = f"Cannot import tree building dependencies: {e}"
    log_structured(
        self.logger,
        logging.ERROR,
        f"❌ {error_msg}",
        ...
    )
    if self.strict_validation:
        raise Exception(error_msg) from e
    return False

    # Same for Exception handler (lines 613-633)
    ```

11. **Line 644**: Update workflow docstring
    ```python
    # FROM:
    5. Build directory tree (optional, controlled by skip_tree flag)

    # TO:
    5. Build directory tree (MANDATORY - prevents orphan nodes)
    6. Validate no orphan nodes exist
    ```

12. **Line 780**: Add validation after tree building
    ```python
    # FROM:
    # Build directory tree (non-fatal if it fails)
    await self.build_directory_tree(correlation_id)

    # TO:
    # Build directory tree (MANDATORY - prevents orphan nodes)
    tree_success = await self.build_directory_tree(correlation_id)

    if not tree_success:
        error_msg = (
            f"❌ Directory tree building FAILED. This will cause orphan FILE nodes. "
            f"Ingestion cannot proceed without tree structure."
        )
        self.logger.error(error_msg, extra={"correlation_id": correlation_id})
        if self.strict_validation:
            return 1  # Fail ingestion if tree building failed
        else:
            self.logger.warning(
                f"⚠️  Continuing despite tree building failure (strict validation disabled)"
            )

    # Validate no orphan nodes exist
    validation_passed, orphan_count = await self.validate_orphan_nodes(correlation_id)

    if not validation_passed and orphan_count > 0:
        if self.strict_validation:
            self.logger.error(
                f"❌ STRICT VALIDATION FAILED: Found {orphan_count} orphan nodes. "
                f"Ingestion failed.",
                extra={"correlation_id": correlation_id, "orphan_count": orphan_count},
            )
            return 1  # Fail ingestion
        else:
            self.logger.warning(
                f"⚠️  Found {orphan_count} orphan nodes but continuing "
                f"(strict validation disabled). "
                f"Run 'python scripts/fix_orphans.py {self.project_name}' to fix.",
                extra={"correlation_id": correlation_id, "orphan_count": orphan_count},
            )
    ```

13. **Line 898**: Update CLI help
    ```python
    # FROM:
    # Skip automatic tree building
    %(prog)s /path/to/project --skip-tree

    # TO:
    # Force rebuild of directory tree
    %(prog)s /path/to/project --rebuild-tree

    # Strict validation (fail if orphans detected)
    %(prog)s /path/to/project --strict
    ```

14. **Lines 973-977**: Replace --skip-tree argument
    ```python
    # DELETE:
    parser.add_argument(
        "--skip-tree",
        action="store_true",
        help="Skip automatic directory tree building after indexing",
    )

    # ADD:
    parser.add_argument(
        "--rebuild-tree",
        action="store_true",
        help="Force rebuild of directory tree (even if already exists)",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        dest="strict_validation",
        help="Strict validation mode (fail ingestion if orphan nodes detected)",
    )
    ```

15. **Line 1028**: Update app initialization
    ```python
    # FROM:
    skip_tree=args.skip_tree,

    # TO:
    rebuild_tree=args.rebuild_tree,
    strict_validation=args.strict_validation,
    ```

### 4. Add validate_orphan_nodes() Method

**Add after build_directory_tree() method** (~line 634):

```python
async def validate_orphan_nodes(self, correlation_id: str) -> tuple[bool, int]:
    """
    Validate no orphan FILE nodes exist after ingestion.

    Orphan nodes are FILE nodes without incoming CONTAINS relationships.
    This indicates tree building failed or relationships weren't created.

    Args:
        correlation_id: Correlation ID for logging

    Returns:
        Tuple of (validation_passed, orphan_count)
        - validation_passed: True if no orphans found
        - orphan_count: Number of orphan FILE nodes detected
    """
    try:
        from storage.memgraph_adapter import MemgraphKnowledgeAdapter

        memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        memgraph_adapter = MemgraphKnowledgeAdapter(
            uri=memgraph_uri, username=None, password=None
        )
        await memgraph_adapter.initialize()

        # Query for orphan FILE nodes
        query = """
        MATCH (f:FILE)
        WHERE f.project_name = $project_name
          AND NOT EXISTS((f)<-[:CONTAINS]-())
        RETURN count(f) as orphan_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query, project_name=self.project_name)
            record = await result.single()

            orphan_count = record["orphan_count"] if record else 0

            if orphan_count > 0:
                self.logger.error(
                    f"❌ ORPHAN VALIDATION FAILED: Found {orphan_count} orphan FILE nodes "
                    f"without CONTAINS relationships",
                    extra={
                        "correlation_id": correlation_id,
                        "phase": "validation",
                        "orphan_count": orphan_count,
                        "project_name": self.project_name,
                    },
                )
            else:
                self.logger.info(
                    f"✅ Orphan validation passed: No orphan FILE nodes detected",
                    extra={
                        "correlation_id": correlation_id,
                        "phase": "validation",
                        "project_name": self.project_name,
                    },
                )

        await memgraph_adapter.close()
        return (orphan_count == 0, orphan_count)

    except Exception as e:
        self.logger.error(
            f"❌ Orphan validation failed: {e}",
            extra={"correlation_id": correlation_id, "error": str(e)},
        )
        if self.verbose:
            self.logger.debug("Validation error details:", exc_info=True)
        return (False, -1)  # -1 indicates validation error
```

## Testing Strategy

### Phase 1: Test fix_orphans.py

```bash
# 1. Detect existing orphans
python scripts/fix_orphans.py omniarchon

# 2. Fix orphans (apply mode)
python scripts/fix_orphans.py omniarchon --apply --verbose

# 3. Verify no orphans remain
python scripts/fix_orphans.py omniarchon
```

### Phase 2: Test Modified bulk_ingest_repository.py

```bash
# 1. Test with strict validation (should fail if orphans detected)
python scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
    --project-name omniarchon \
    --kafka-servers 192.168.86.200:29092 \
    --strict \
    --verbose

# 2. Test rebuild tree flag
python scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
    --project-name omniarchon \
    --kafka-servers 192.168.86.200:29092 \
    --rebuild-tree \
    --verbose

# 3. Verify tree structure
python scripts/verify_environment.py --verbose
```

### Phase 3: Integration Testing

```bash
# 1. Clear databases
./scripts/clear_databases.sh --force

# 2. Fresh ingestion with strict validation
python scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \
    --project-name omniarchon \
    --kafka-servers 192.168.86.200:29092 \
    --strict \
    --verbose

# 3. Verify no orphans
python scripts/fix_orphans.py omniarchon

# 4. Verify environment health
python scripts/verify_environment.py --verbose
```

## Success Criteria

- ✅ fix_orphans.py created and executable
- ⏳ --skip-tree flag removed from bulk_ingest_repository.py
- ⏳ --rebuild-tree flag added
- ⏳ --strict flag added for validation enforcement
- ⏳ Tree building is mandatory (no skip option)
- ⏳ validate_orphan_nodes() method added
- ⏳ Ingestion fails in strict mode if orphans detected
- ⏳ All tests passing

## Database Constraints (Future Work)

Memgraph doesn't support declarative constraints like PostgreSQL, so we rely on application-level validation:

**Current Approach** (Application-Level):
- Validation hooks in `bulk_ingest_repository.py`
- Post-ingestion orphan detection
- Automatic remediation via `fix_orphans.py`

**Future Enhancement** (Trigger-Based):
Implement Memgraph triggers to prevent orphan creation:
```cypher
CREATE TRIGGER prevent_orphan_files
ON --> CREATE
BEFORE COMMIT
EXECUTE
  MATCH (f:FILE)
  WHERE NOT EXISTS((f)<-[:CONTAINS]-())
  THROW "Cannot create FILE node without CONTAINS relationship";
```

Note: Memgraph trigger syntax may vary - consult documentation.

## Architecture Benefits

1. **Prevention over Remediation**: Tree building is now mandatory
2. **Fail-Fast Validation**: Detects orphans immediately after ingestion
3. **Automated Remediation**: fix_orphans.py provides easy recovery path
4. **Flexible Enforcement**: --strict flag allows gradual rollout
5. **Backward Compatibility**: Default mode warns but doesn't fail
6. **Observable**: Comprehensive logging with correlation IDs

## Migration Path

1. **Phase 1** (Current): Deploy fix_orphans.py, fix existing orphans
2. **Phase 2**: Update bulk_ingest_repository.py with validation
3. **Phase 3**: Test with --strict on new ingestion (gradual rollout)
4. **Phase 4**: Enable --strict by default once validated
5. **Phase 5**: Consider Memgraph triggers for enforcement

## References

- Original issue: Tree Graph Fix 2025-11-10 (TREE_GRAPH_FIX_2025-11-10.md)
- Correlation ID: 07f64ef3-3b04-4bc3-94d8-0040fb044276
- Agent: debug-intelligence
- DirectoryIndexer: services/intelligence/src/services/directory_indexer.py
