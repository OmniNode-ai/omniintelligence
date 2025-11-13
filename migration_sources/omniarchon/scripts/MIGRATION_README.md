# Database Migration Guide

**Purpose**: Production-ready migration scripts for fixing orphaned file nodes and standardizing file labels in Memgraph

**Created**: 2025-11-11
**Status**: Production-ready with comprehensive error handling and rollback capability

---

## Table of Contents

1. [Overview](#overview)
2. [Migration Scripts](#migration-scripts)
3. [Pre-Migration Checklist](#pre-migration-checklist)
4. [Migration Process](#migration-process)
5. [Expected Output](#expected-output)
6. [Troubleshooting](#troubleshooting)
7. [Rollback Procedures](#rollback-procedures)
8. [Post-Migration Verification](#post-migration-verification)

---

## Overview

This guide covers two critical database migrations:

1. **Orphaned File Node Remediation** (`migrate_orphaned_file_nodes.py`)
   - **Problem**: 1,292 File nodes exist without CONTAINS relationships from PROJECT/DIRECTORY
   - **Solution**: Extract project_name from entity_id, create PROJECT nodes, establish CONTAINS relationships
   - **Impact**: Fixes broken file tree hierarchy, enables proper visualization and queries

2. **File Label Standardization** (`migrate_file_labels.py`)
   - **Problem**: 4,047 nodes use :FILE label (UPPERCASE) instead of standardized :File (PascalCase)
   - **Solution**: Migrate all :FILE labels to :File while preserving properties and relationships
   - **Impact**: Schema consistency, prevents query confusion, aligns with codebase standards

### Key Features (Both Scripts)

- ✅ **Transaction batching** (100-1000 nodes per batch)
- ✅ **Retry logic** for TransientErrors (exponential backoff: 1s, 2s, 4s)
- ✅ **Dry-run mode** for safe previewing
- ✅ **Progress reporting** (every 100-1000 nodes)
- ✅ **Comprehensive logging** to `logs/migration_*.log`
- ✅ **Safety checks** (health checks, confirmation prompts)
- ✅ **Rollback capability** (file labels only)

---

## Migration Scripts

### 1. Orphaned File Node Remediation

**Script**: `scripts/migrate_orphaned_file_nodes.py`

**What It Does**:
1. Finds File nodes without CONTAINS relationships
2. Extracts project_name from entity_id pattern (e.g., `file:omniarchon:...` → `omniarchon`)
3. Updates node with project_name property
4. Creates or finds PROJECT node
5. Creates CONTAINS relationship: PROJECT → File

**Usage**:
```bash
# Dry run (preview changes)
python3 scripts/migrate_orphaned_file_nodes.py --dry-run

# Apply fixes
python3 scripts/migrate_orphaned_file_nodes.py --apply

# Apply to specific project
python3 scripts/migrate_orphaned_file_nodes.py --apply --project omniarchon

# Apply with force (skip confirmation)
python3 scripts/migrate_orphaned_file_nodes.py --apply --force
```

**Options**:
- `--apply`: Apply fixes (default: dry-run mode)
- `--dry-run`: Preview changes without applying (default: True)
- `--project NAME`: Filter by project name
- `--batch-size N`: Number of nodes per batch (default: 100)
- `--force`: Skip confirmation prompt
- `--memgraph-uri URI`: Memgraph connection URI (default: bolt://localhost:7687)

### 2. File Label Standardization

**Script**: `scripts/migrate_file_labels.py`

**What It Does**:
1. Finds all nodes with :FILE label (UPPERCASE)
2. For each node:
   - Adds :File label (node temporarily has both)
   - Removes :FILE label (node now has only :File)
3. Preserves all properties and relationships

**Usage**:
```bash
# Dry run (show counts)
python3 scripts/migrate_file_labels.py --dry-run

# Apply migration
python3 scripts/migrate_file_labels.py --apply

# Verify (check for remaining :FILE nodes)
python3 scripts/migrate_file_labels.py --verify

# Rollback (emergency only - reverts :File to :FILE)
python3 scripts/migrate_file_labels.py --rollback

# Apply with force (skip confirmation)
python3 scripts/migrate_file_labels.py --apply --force
```

**Options**:
- `--apply`: Apply migration (default: dry-run mode)
- `--verify`: Verify migration (check for remaining :FILE nodes)
- `--rollback`: Rollback migration (emergency use only)
- `--dry-run`: Preview changes without applying (default: True)
- `--batch-size N`: Number of nodes per batch (default: 1000)
- `--force`: Skip confirmation prompt
- `--memgraph-uri URI`: Memgraph connection URI

---

## Pre-Migration Checklist

**CRITICAL**: Complete these steps before running migrations with `--apply`:

### 1. Backup Your Database

```bash
# Create Memgraph backup (JSON format)
docker exec memgraph mgconsole --output-format=json > backup_$(date +%Y%m%d_%H%M%S).json

# Alternative: Create snapshot (if Memgraph Enterprise)
docker exec memgraph mgconsole -e "CREATE SNAPSHOT;"
```

**Storage**: Keep backups in a safe location outside the container.

### 2. Verify Services Are Running

```bash
# Check Memgraph health
docker ps | grep memgraph

# Test connection
docker exec memgraph mgconsole -e "RETURN 1;"
```

**Expected**: Memgraph container is running and responding to queries.

### 3. Check Current State

```bash
# Count orphaned files
docker exec memgraph mgconsole -e "MATCH (f:File) WHERE NOT (f)<-[:CONTAINS]-(:PROJECT) AND NOT (f)<-[:CONTAINS]-(:DIRECTORY) RETURN count(f);"

# Count :FILE nodes (old label)
docker exec memgraph mgconsole -e "MATCH (n:FILE) RETURN count(n);"

# Count :File nodes (new label)
docker exec memgraph mgconsole -e "MATCH (n:File) RETURN count(n);"
```

**Record**: Note these counts for comparison after migration.

### 4. Test in Dry-Run Mode

```bash
# Test orphan remediation
python3 scripts/migrate_orphaned_file_nodes.py --dry-run

# Test label migration
python3 scripts/migrate_file_labels.py --dry-run
```

**Expected**: Scripts run successfully and show what would be changed.

### 5. Schedule Maintenance Window (Optional)

For production environments:
- Notify users of maintenance window
- Stop or pause services that write to Memgraph
- Ensure no concurrent ingestion operations

---

## Migration Process

### Step-by-Step Execution

#### Phase 1: Orphaned File Node Remediation

**Duration**: ~1-5 minutes for 1,292 nodes (batch size 100, with retries)

```bash
# Step 1: Run dry-run to preview
python3 scripts/migrate_orphaned_file_nodes.py --dry-run

# Step 2: Review output (check logs)
tail -f logs/migration_orphaned_file_nodes.log

# Step 3: Apply fixes
python3 scripts/migrate_orphaned_file_nodes.py --apply

# Step 4: Confirm when prompted
# Enter 'y' to proceed

# Step 5: Monitor progress
# Script will show progress every 100 nodes

# Step 6: Verify completion
# Check summary output for success rate
```

**What to Expect**:
- Detects 1,292 orphaned File nodes
- Creates PROJECT nodes as needed
- Creates CONTAINS relationships
- Reports: Fixed X/Y nodes, Z retries, success rate

#### Phase 2: File Label Standardization

**Duration**: ~2-10 seconds for 4,047 nodes (batch size 1000)

```bash
# Step 1: Run dry-run to preview
python3 scripts/migrate_file_labels.py --dry-run

# Step 2: Apply migration
python3 scripts/migrate_file_labels.py --apply

# Step 3: Confirm when prompted
# Enter 'y' to proceed

# Step 4: Monitor progress
# Script will show progress every 1000 nodes

# Step 5: Verify migration
python3 scripts/migrate_file_labels.py --verify

# Expected: "✅ Verification passed - No :FILE nodes remain!"
```

**What to Expect**:
- Detects 4,047 :FILE nodes
- Migrates in batches of 1000
- Reports: Migrated X nodes, Y batches, success rate
- Verification shows 0 :FILE nodes remain

---

## Expected Output

### Orphaned File Node Remediation

**Dry-Run Mode**:
```
======================================================================
🔧 ORPHANED FILE NODE MIGRATION
======================================================================
Mode: DRY RUN (preview only)
Project filter: All projects
Batch size: 100
Correlation ID: a3b5c7d9
Log file: /path/to/logs/migration_orphaned_file_nodes.log
======================================================================

🏥 Checking Memgraph health...
✅ Memgraph is healthy

🔍 Scanning for orphaned File nodes...
🔍 Found 1292 orphaned File nodes

Found 1292 orphaned nodes:
  1. file:omniarchon:README.md → project_name=omniarchon
  2. file:omniarchon:docs/setup.md → project_name=omniarchon
  3. file:omniclaude:src/main.py → project_name=omniclaude
  ... and 1289 more

🔍 DRY RUN MODE - No changes will be applied. Use --apply to fix orphans.
```

**Apply Mode**:
```
======================================================================
🔧 FIXING ORPHANED NODES
======================================================================

Processing batch 1 (1-100 of 1292)...
  Progress: Fixed 100/1292, Failed: 0, Retries: 0

Processing batch 2 (101-200 of 1292)...
  Progress: Fixed 200/1292, Failed: 0, Retries: 2

...

======================================================================
📊 MIGRATION SUMMARY
======================================================================
Orphaned nodes found: 1292
Nodes fixed: 1292
Nodes failed: 0
Relationships created: 1292
Total retries: 5
Success rate: 100.0%
Duration: 45.3s
Log file: /path/to/logs/migration_orphaned_file_nodes.log
======================================================================
✅ All orphaned nodes successfully migrated!
```

### File Label Migration

**Dry-Run Mode**:
```
======================================================================
🔧 FILE LABEL MIGRATION (:FILE → :File)
======================================================================
Mode: DRY RUN (preview only)
Batch size: 1000
Correlation ID: e4f6g8h0
Log file: /path/to/logs/migration_file_labels.log
======================================================================

🏥 Checking Memgraph health...
✅ Memgraph is healthy

🔍 Counting nodes with :FILE label...
📊 Found 4047 nodes with :FILE label

Found 4047 nodes to migrate

🔍 DRY RUN MODE - No changes will be applied. Use --apply to migrate nodes.
```

**Apply Mode**:
```
======================================================================
🔧 MIGRATING FILE LABELS
======================================================================

Processing batch 1 (offset 0, limit 1000)...
  Progress: 1000/4047 (24.7%), Retries: 0

Processing batch 2 (offset 0, limit 1000)...
  Progress: 2000/4047 (49.4%), Retries: 1

...

🔍 Verifying migration...
📊 Found 0 nodes with :FILE label

======================================================================
📊 MIGRATION SUMMARY
======================================================================
:FILE nodes found: 4047
Nodes migrated: 4047
Nodes remaining: 0
Batches processed: 5
Total retries: 3
Success rate: 100.0%
Duration: 8.7s
Log file: /path/to/logs/migration_file_labels.log
======================================================================
✅ All :FILE nodes successfully migrated to :File!
```

**Verification Mode**:
```
======================================================================
🔍 FILE LABEL VERIFICATION
======================================================================

✅ Memgraph is healthy
📊 Found 0 nodes with :FILE label
📊 Found 4047 nodes with :File label

======================================================================
📊 VERIFICATION RESULTS
======================================================================
:FILE nodes (old): 0
:File nodes (new): 4047
======================================================================
✅ Verification passed - No :FILE nodes remain!
```

---

## Troubleshooting

### Common Issues

#### 1. TransientError: "Cannot resolve conflicting transactions"

**Cause**: Multiple concurrent transactions modifying the same nodes.

**Solution**: Script automatically retries with exponential backoff (1s, 2s, 4s).

**Manual Resolution**:
```bash
# If retries persist, reduce batch size
python3 scripts/migrate_orphaned_file_nodes.py --apply --batch-size 50
python3 scripts/migrate_file_labels.py --apply --batch-size 500
```

#### 2. Connection Refused

**Cause**: Memgraph is not running or not accessible.

**Solution**:
```bash
# Check Memgraph status
docker ps | grep memgraph

# Restart Memgraph if needed
docker restart memgraph

# Verify connection
docker exec memgraph mgconsole -e "RETURN 1;"
```

#### 3. Some Nodes Failed to Migrate

**Cause**: Data inconsistencies or malformed entity_ids.

**Solution**:
```bash
# Check logs for specific errors
tail -100 logs/migration_orphaned_file_nodes.log | grep "❌"

# Manually inspect failed nodes
docker exec memgraph mgconsole

# In mgconsole:
MATCH (f:File)
WHERE NOT (f)<-[:CONTAINS]-(:PROJECT)
  AND NOT (f)<-[:CONTAINS]-(:DIRECTORY)
RETURN f.entity_id, f.path
LIMIT 10;
```

**Manual Fix**:
```cypher
// For specific orphan
MATCH (f:File {entity_id: "file:project:path/to/file.py"})
MERGE (p:PROJECT {entity_id: "project:project"})
MERGE (p)-[:CONTAINS]->(f)
```

#### 4. Migration Interrupted

**Cause**: Script terminated before completion (Ctrl+C, connection loss).

**Solution**: Migrations are idempotent - safe to re-run.
```bash
# Re-run from where it left off
python3 scripts/migrate_orphaned_file_nodes.py --apply
# Script will skip already-fixed nodes and continue
```

#### 5. Performance Issues (Slow Migration)

**Cause**: Large batch size or high retry rate.

**Solution**:
```bash
# Reduce batch size
python3 scripts/migrate_orphaned_file_nodes.py --apply --batch-size 50

# Check Memgraph resource usage
docker stats memgraph
```

---

## Rollback Procedures

### Orphaned File Node Remediation Rollback

**Note**: This migration does NOT have automated rollback. Manual rollback required.

**Rollback Steps**:

1. **Remove CONTAINS relationships created by migration**:
   ```cypher
   // Find relationships created by migration (check timestamp)
   MATCH (p:PROJECT)-[r:CONTAINS]->(f:File)
   WHERE r.created_at >= datetime("2025-11-11T00:00:00Z")
   DELETE r;
   ```

2. **Remove PROJECT nodes created by migration** (optional):
   ```cypher
   // Remove empty PROJECT nodes
   MATCH (p:PROJECT)
   WHERE NOT EXISTS((p)-[:CONTAINS]->())
   DELETE p;
   ```

3. **Remove project_name properties added** (if needed):
   ```cypher
   // This will break queries - only use if reverting completely
   MATCH (f:File)
   WHERE f.project_name IS NOT NULL
   REMOVE f.project_name;
   ```

**Restore from Backup** (preferred):
```bash
# Stop Memgraph
docker stop memgraph

# Restore from backup JSON
docker start memgraph
docker exec -i memgraph mgconsole < backup_20251111_120000.json
```

### File Label Migration Rollback

**Automated Rollback Available**:

```bash
# Rollback :File → :FILE (emergency only)
python3 scripts/migrate_file_labels.py --rollback

# Confirm when prompted
# Enter 'y' to proceed

# Verify rollback
python3 scripts/migrate_file_labels.py --verify
# Expected: Shows :FILE count restored, :File count = 0
```

**When to Rollback**:
- Critical bug discovered in :File label handling
- Schema incompatibility with external systems
- Unexpected query failures after migration

**Warning**: Rollback should only be used in emergencies. The :File label is the standardized schema.

---

## Post-Migration Verification

### 1. Verify Orphan Remediation

```bash
# Check for remaining orphans
docker exec memgraph mgconsole -e "
MATCH (f:File)
WHERE NOT (f)<-[:CONTAINS]-(:PROJECT)
  AND NOT (f)<-[:CONTAINS]-(:DIRECTORY)
RETURN count(f) as orphan_count;
"
# Expected: orphan_count = 0

# Check PROJECT → File relationships
docker exec memgraph mgconsole -e "
MATCH (p:PROJECT)-[:CONTAINS]->(f:File)
RETURN count(f) as connected_files;
"
# Expected: connected_files = total file count
```

### 2. Verify Label Migration

```bash
# Use built-in verification
python3 scripts/migrate_file_labels.py --verify

# Expected output:
# ✅ Verification passed - No :FILE nodes remain!
```

### 3. Verify Data Integrity

```bash
# Check file properties preserved
docker exec memgraph mgconsole -e "
MATCH (f:File)
RETURN count(f) as total,
       count(f.entity_id) as with_entity_id,
       count(f.path) as with_path,
       count(f.project_name) as with_project_name;
"
# Expected: All counts equal (no NULL values)

# Check relationships preserved
docker exec memgraph mgconsole -e "
MATCH (f:File)<-[r]-(n)
RETURN type(r) as rel_type, count(r) as count;
"
# Expected: All relationship types preserved
```

### 4. Run Environment Verification

```bash
# Comprehensive health check
python3 scripts/verify_environment.py --verbose

# Expected: All checks pass (9/9)
```

### 5. Test Application Queries

```bash
# Test file tree queries
curl -s http://localhost:8053/api/pattern-learning/health

# Test RAG queries
curl -s http://localhost:8055/health

# Expected: All services healthy
```

---

## FAQ

### Q: Can I run migrations on a live production system?

**A**: Yes, but with caution:
- Migrations are non-destructive (only add relationships/labels)
- Use dry-run mode first to preview changes
- Consider scheduling during low-traffic period
- Monitor performance during migration
- Have rollback plan ready

### Q: How long do migrations take?

**A**:
- **Orphan remediation**: ~1-5 minutes for 1,292 nodes
- **Label migration**: ~2-10 seconds for 4,047 nodes

Actual time depends on:
- Batch size (smaller = slower but safer)
- Retry rate (more TransientErrors = longer)
- System load (concurrent queries slow migration)

### Q: Are migrations idempotent?

**A**: Yes - safe to re-run if interrupted:
- **Orphan remediation**: Uses MERGE (won't duplicate relationships)
- **Label migration**: Checks for existing labels (won't re-migrate)

### Q: What if my database has different issues?

**A**: These scripts target specific known issues (1,292 orphans, 4,047 :FILE labels).

For custom fixes:
- Modify queries in the scripts
- Test in dry-run mode extensively
- Create backups before applying

### Q: Can I run both migrations simultaneously?

**A**: No - run sequentially:
1. Run orphan remediation first (fixes structure)
2. Run label migration second (fixes schema)

Running simultaneously may cause TransientErrors.

---

## Support & Logs

### Log Files

- **Orphan remediation**: `logs/migration_orphaned_file_nodes.log`
- **Label migration**: `logs/migration_file_labels.log`

### Debug Mode

Add `--verbose` flag for detailed logging (not currently implemented, but logs are comprehensive).

### Report Issues

If migrations fail:
1. Check log files for error details
2. Verify Memgraph health
3. Consult troubleshooting section
4. Review pre-migration checklist

---

## Success Criteria

### Migration Complete When:

- ✅ Orphan remediation: 0 orphaned File nodes remain
- ✅ Label migration: 0 :FILE nodes remain, all migrated to :File
- ✅ All properties preserved (entity_id, path, project_name)
- ✅ All relationships preserved (CONTAINS, etc.)
- ✅ Environment verification passes (9/9 checks)
- ✅ Application queries work correctly

### Performance Targets:

- ✅ Orphan remediation: < 5 minutes for 1,292 nodes
- ✅ Label migration: < 15 seconds for 4,047 nodes
- ✅ Success rate: > 99% (allow for minor data inconsistencies)
- ✅ Retry rate: < 5% of total operations

---

**Migration Complete!** 🎉

After successful migrations, your Memgraph database will have:
- Complete file tree hierarchy (PROJECT → DIRECTORY → FILE)
- Standardized :File labels (PascalCase)
- All properties and relationships intact
- Improved query performance and consistency
