# Pattern Sync Deployment Guide

**Date**: 2025-10-26
**Purpose**: Deploy automated PostgreSQL-to-Qdrant pattern sync

## Overview

This guide covers deployment strategies for automatic syncing of code patterns from PostgreSQL `pattern_lineage_nodes` table to Qdrant `code_patterns` collection.

## Deployment Options

### Option A: Init Container (Recommended for MVP)

**Use Case**: One-time sync on container startup
**Pros**: Simple, no scheduling needed, automatic on restart
**Cons**: Only runs on container startup, not continuous

**Implementation**:

Add to `docker-compose.yml`:

```yaml
services:
  pattern-sync-init:
    build:
      context: .
      dockerfile: services/intelligence/Dockerfile
    container_name: archon-pattern-sync-init
    image: archon-intelligence:latest
    command: /bin/bash /app/scripts/docker-entrypoint-pattern-sync.sh
    environment:
      - DATABASE_URL=postgresql://postgres:omninode-bridge-postgres-dev-2024@192.168.86.200:5436/omninode_bridge
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_BASE_URL=http://192.168.86.200:11434
    depends_on:
      - qdrant
      - omninode-bridge-postgres
    restart: "no"  # Run once, don't restart
    networks:
      - archon-network
```

**Usage**:
```bash
# Sync runs automatically on startup
docker compose up pattern-sync-init

# View logs
docker logs archon-pattern-sync-init

# Manual trigger (restart container)
docker compose restart pattern-sync-init
```

### Option B: Scheduled Service (Recommended for Production)

**Use Case**: Periodic sync (hourly/daily)
**Pros**: Continuous sync, handles new patterns automatically
**Cons**: More complex, requires cron/scheduler

**Implementation**:

Create `scripts/pattern-sync-crontab`:

```cron
# Sync patterns every hour
0 * * * * python3 /app/scripts/sync_patterns_to_qdrant.py --incremental >> /var/log/pattern-sync.log 2>&1

# Full sync daily at 2 AM
0 2 * * * python3 /app/scripts/sync_patterns_to_qdrant.py >> /var/log/pattern-sync-full.log 2>&1
```

Add to `docker-compose.yml`:

```yaml
services:
  pattern-sync-cron:
    build:
      context: .
      dockerfile: services/intelligence/Dockerfile
    container_name: archon-pattern-sync-cron
    image: archon-intelligence:latest
    command: crond -f -l 2
    environment:
      - DATABASE_URL=postgresql://postgres:omninode-bridge-postgres-dev-2024@192.168.86.200:5436/omninode_bridge
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_BASE_URL=http://192.168.86.200:11434
    volumes:
      - ./scripts/pattern-sync-crontab:/etc/crontabs/root:ro
      - pattern-sync-logs:/var/log
    depends_on:
      - qdrant
      - omninode-bridge-postgres
    restart: unless-stopped
    networks:
      - archon-network

volumes:
  pattern-sync-logs:
```

**Usage**:
```bash
# Start scheduled sync
docker compose up -d pattern-sync-cron

# View logs
docker logs -f archon-pattern-sync-cron

# Check cron status
docker exec archon-pattern-sync-cron crontab -l
```

### Option C: Event-Driven Sync (Future Enhancement)

**Use Case**: Real-time sync on new pattern creation
**Pros**: Instant sync, no lag
**Cons**: Complex, requires Kafka integration

**Implementation Concept**:

1. Listen to Kafka topic: `dev.archon-intelligence.pattern.created.v1`
2. On new pattern event, trigger sync for that pattern
3. Uses existing event bus infrastructure

```python
# Future: services/intelligence/src/handlers/pattern_sync_handler.py
class PatternSyncHandler:
    async def on_pattern_created(self, event: PatternCreatedEvent):
        """Sync newly created pattern to Qdrant."""
        pattern = await self.fetch_pattern(event.pattern_id)
        await self.sync_to_qdrant(pattern)
```

## Manual Sync

Run sync script directly without Docker:

```bash
# Full sync
python3 scripts/sync_patterns_to_qdrant.py

# Incremental sync (only new patterns)
python3 scripts/sync_patterns_to_qdrant.py --incremental

# Dry run (no changes)
python3 scripts/sync_patterns_to_qdrant.py --dry-run

# Help
python3 scripts/sync_patterns_to_qdrant.py --help
```

## Environment Configuration

Required environment variables:

```bash
# PostgreSQL
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:PORT/DATABASE

# Qdrant
QDRANT_URL=http://qdrant:6333

# Ollama (for embeddings)
OLLAMA_BASE_URL=http://192.168.86.200:11434
```

## Monitoring & Verification

### Check Sync Status

```bash
# View sync logs (init container)
docker logs archon-pattern-sync-init

# View sync logs (cron service)
docker logs -f archon-pattern-sync-cron

# Check Qdrant collection
curl http://localhost:6333/collections/code_patterns | jq
```

### Verify Collection

```bash
# Check collection exists
curl http://localhost:6333/collections/code_patterns | jq '.result.status'

# Check point count
curl http://localhost:6333/collections/code_patterns | jq '.result.points_count'

# Sample search
curl -X POST http://localhost:6333/collections/code_patterns/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit": 3, "with_payload": true, "with_vectors": false}' | jq
```

### PostgreSQL Comparison

```bash
# Count patterns in PostgreSQL
docker exec omninode-bridge-postgres psql -U postgres -d omninode_bridge \
  -c "SELECT COUNT(*) FROM pattern_lineage_nodes WHERE pattern_type = 'code';"

# Count points in Qdrant
curl -s http://localhost:6333/collections/code_patterns | jq '.result.points_count'
```

## Performance Expectations

### Initial Sync (971 patterns)

- **Duration**: ~60-120 seconds
- **Embedding Generation**: ~50-100ms per pattern
- **Batch Upsert**: ~500ms per 100 patterns
- **Rate**: ~10-15 patterns/second

### Incremental Sync (new patterns only)

- **Duration**: <10 seconds for 1-10 new patterns
- **Frequency**: Every hour (if scheduled)

### Resource Usage

- **CPU**: Moderate during sync (embedding generation)
- **Memory**: ~100-200MB peak
- **Network**: ~1KB per pattern (embeddings)
- **Disk**: ~768 bytes per vector (Qdrant)

## Troubleshooting

### Sync Fails to Start

**Symptom**: Container exits immediately

**Causes**:
- PostgreSQL not ready
- Qdrant not ready
- Invalid credentials

**Solution**:
```bash
# Check PostgreSQL
pg_isready -h 192.168.86.200 -p 5436 -U postgres

# Check Qdrant
curl http://localhost:6333/health

# Check environment variables
docker compose config | grep -A 5 pattern-sync-init
```

### Embedding Generation Slow

**Symptom**: >200ms per pattern

**Causes**:
- Ollama server overloaded
- Network latency
- Model not loaded

**Solution**:
```bash
# Check Ollama status
curl http://192.168.86.200:11434/api/tags

# Test embedding speed
time curl http://192.168.86.200:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "test"}'
```

### Collection Not Created

**Symptom**: 404 on code_patterns collection

**Causes**:
- Sync script not run yet
- Qdrant permission issues
- Wrong collection name

**Solution**:
```bash
# List all collections
curl http://localhost:6333/collections | jq '.result.collections[].name'

# Manually create collection (if needed)
python3 scripts/sync_patterns_to_qdrant.py --dry-run
```

### Duplicate Points

**Symptom**: More points in Qdrant than patterns in PostgreSQL

**Causes**:
- Multiple sync runs without idempotency
- Pattern ID changes

**Solution**:
```bash
# Script uses PostgreSQL UUID as point ID for idempotency
# Re-running sync should NOT create duplicates

# Verify idempotency
python3 scripts/sync_patterns_to_qdrant.py  # Run 1
python3 scripts/sync_patterns_to_qdrant.py  # Run 2 (should update, not duplicate)
```

## Rollback Strategy

### Delete Collection and Resync

```bash
# Delete code_patterns collection
curl -X DELETE http://localhost:6333/collections/code_patterns

# Verify deletion
curl http://localhost:6333/collections | jq '.result.collections[].name'

# Re-run sync
docker compose restart pattern-sync-init
# OR
python3 scripts/sync_patterns_to_qdrant.py
```

### Keep Manual Patterns Safe

**Important**: `execution_patterns` collection is NOT affected by this sync script.

- Manual ONEX patterns: **SAFE** (in execution_patterns)
- Code patterns: **SYNCED** (in code_patterns)
- No overlap, no conflicts

## Migration Checklist

- [ ] Create sync script: `scripts/sync_patterns_to_qdrant.py`
- [ ] Create entrypoint: `scripts/docker-entrypoint-pattern-sync.sh`
- [ ] Make entrypoint executable: `chmod +x`
- [ ] Add init container to `docker-compose.yml`
- [ ] Test sync locally: `python3 scripts/sync_patterns_to_qdrant.py --dry-run`
- [ ] Run full sync: `docker compose up pattern-sync-init`
- [ ] Verify collection: `curl http://localhost:6333/collections/code_patterns`
- [ ] Verify point count matches PostgreSQL
- [ ] Test search on new collection
- [ ] (Optional) Add scheduled sync for production

## Next Steps

1. **Test MVP** (Init Container):
   ```bash
   docker compose up pattern-sync-init
   ```

2. **Verify Results**:
   ```bash
   # Check logs
   docker logs archon-pattern-sync-init

   # Check collection
   curl http://localhost:6333/collections/code_patterns | jq
   ```

3. **Production Deployment** (Scheduled Sync):
   - Add cron service to docker-compose
   - Monitor sync logs
   - Set up alerting for failures

## References

- Analysis: `docs/PATTERN_SYNC_ANALYSIS.md`
- Script: `scripts/sync_patterns_to_qdrant.py`
- Entrypoint: `scripts/docker-entrypoint-pattern-sync.sh`
- Original Manual Script: `scripts/index_sample_patterns.py`
