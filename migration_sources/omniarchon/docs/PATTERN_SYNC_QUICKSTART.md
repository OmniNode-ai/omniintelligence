# Pattern Sync Quick Start Guide

**Goal**: Sync 971 code patterns from PostgreSQL to Qdrant in 5 minutes

## TL;DR

```bash
# 1. Rebuild container (includes new sync script)
docker compose build archon-intelligence

# 2. Run sync (dry-run first to verify)
docker exec archon-intelligence python3 /app/scripts/sync_patterns_to_qdrant.py --dry-run

# 3. Run actual sync
docker exec archon-intelligence python3 /app/scripts/sync_patterns_to_qdrant.py

# 4. Verify results
curl http://localhost:6333/collections/code_patterns | jq '.result.points_count'
```

## What This Does

- ✅ Syncs 971 code patterns from PostgreSQL → Qdrant
- ✅ Creates new `code_patterns` collection (separate from `execution_patterns`)
- ✅ Preserves existing 20 manual ONEX patterns
- ✅ Enables code similarity search across entire codebase

## Step-by-Step

### 1. Rebuild Container (Include New Script)

```bash
cd /Volumes/PRO-G40/Code/omniarchon

# Rebuild intelligence service
docker compose build archon-intelligence

# Verify script exists in container
docker exec archon-intelligence ls -lh /app/scripts/sync_patterns_to_qdrant.py
```

### 2. Test with Dry Run

```bash
# Dry run (no changes, just shows what would happen)
docker exec archon-intelligence python3 /app/scripts/sync_patterns_to_qdrant.py --dry-run

# Expected output:
# ======================================================================
# PostgreSQL to Qdrant Pattern Sync
# ======================================================================
# Mode: Full Sync
# Dry Run: True
# Collection: code_patterns
# ...
# [DRY RUN] Would sync 971 patterns
# ✅ Sync complete!
```

### 3. Run Full Sync

```bash
# Actual sync (creates collection and indexes patterns)
docker exec archon-intelligence python3 /app/scripts/sync_patterns_to_qdrant.py

# Expected output:
# Initializing connections...
# ✅ Connections initialized
# Fetching all code patterns...
# ✅ Found 971 patterns to sync
# Processing batch 1/10 (100 patterns)...
# ✅ Synced batch: 100 patterns in 5234.56ms
# ...
# ✅ Sync complete!
#    Total patterns: 971
#    Synced patterns: 971
#    Duration: 93456.78ms
#    Rate: 10.39 patterns/sec
```

**Note**: First sync takes ~60-120 seconds due to embedding generation

### 4. Verify Results

```bash
# Check both collections exist
curl http://localhost:6333/collections | jq '.result.collections[].name'
# Output: ["execution_patterns", "code_patterns"]

# Check code_patterns stats
curl http://localhost:6333/collections/code_patterns | jq '{
  status: .result.status,
  points: .result.points_count,
  vectors: .result.vectors_count
}'
# Output: {status: "green", points: 971, vectors: 971}

# Compare with PostgreSQL count
docker exec omninode-bridge-postgres psql -U postgres -d omninode_bridge \
  -c "SELECT COUNT(*) FROM pattern_lineage_nodes WHERE pattern_type = 'code';"
# Output: 971 (should match Qdrant)
```

### 5. Test Search

```bash
# Search for Python test files
curl -X POST http://localhost:6333/collections/code_patterns/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{
    "limit": 3,
    "with_payload": true,
    "with_vectors": false,
    "filter": {
      "must": [
        {"key": "language", "match": {"value": "python"}},
        {"key": "pattern_name", "match": {"text": "test"}}
      ]
    }
  }' | jq '.result.points[].payload | {name: .pattern_name, language: .language}'

# Expected output:
# {name: "test_file_location_performance.py", language: "python"}
# {name: "test_file_location_e2e.py", language: "python"}
# {name: "test_tree_stamping_bridge.py", language: "python"}
```

## Troubleshooting

### Container Build Fails

```bash
# Check Dockerfile exists
ls services/intelligence/Dockerfile

# View build logs
docker compose build --no-cache archon-intelligence
```

### Script Not Found in Container

```bash
# Verify script exists on host
ls -lh scripts/sync_patterns_to_qdrant.py

# Check if mounted or copied
docker exec archon-intelligence ls -lh /app/scripts/
```

### PostgreSQL Connection Failed

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
docker exec omninode-bridge-postgres psql -U postgres -d omninode_bridge -c "SELECT 1;"
```

### Qdrant Connection Failed

```bash
# Check Qdrant is running
docker ps | grep qdrant

# Test connection
curl http://localhost:6333/health
```

### Sync Hangs on Embedding Generation

```bash
# Check Ollama is running
curl http://192.168.86.200:11434/api/tags

# Test embedding speed
time curl http://192.168.86.200:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "test"}'
```

## What's Next?

### For Production (Optional)

Add scheduled sync to `docker-compose.yml`:

```yaml
services:
  pattern-sync-init:
    build:
      context: .
      dockerfile: services/intelligence/Dockerfile
    command: /bin/bash /app/scripts/docker-entrypoint-pattern-sync.sh
    depends_on:
      - qdrant
      - omninode-bridge-postgres
    restart: "no"  # Run once on startup
```

Then:

```bash
# Add service to docker-compose
docker compose up pattern-sync-init

# View logs
docker logs archon-pattern-sync-init
```

## Summary

You now have:

- ✅ **971 code patterns** searchable in Qdrant (`code_patterns` collection)
- ✅ **20 ONEX patterns** preserved in `execution_patterns` collection
- ✅ **Automated sync script** for future updates
- ✅ **Code similarity search** across entire codebase

## More Info

- **Comprehensive Analysis**: `docs/PATTERN_SYNC_ANALYSIS.md`
- **Deployment Guide**: `docs/PATTERN_SYNC_DEPLOYMENT.md`
- **Full Summary**: `docs/PATTERN_SYNC_SUMMARY.md`
- **Sync Script**: `scripts/sync_patterns_to_qdrant.py`
