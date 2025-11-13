# Verification Scripts - Quick Reference

## Available Scripts

### 1. `verify_recent_fixes.py` ⭐ (RECOMMENDED - Most Comprehensive)

**Purpose**: Verify recent infrastructure improvements (vLLM migration, language fields, project_name)

**Usage**:
```bash
python3 scripts/verify_recent_fixes.py           # Standard check
python3 scripts/verify_recent_fixes.py --verbose # Detailed per-project breakdown
python3 scripts/verify_recent_fixes.py --json    # JSON output for CI/CD
```

**Checks**:
- ✅ vLLM embedding service (192.168.86.201:8002)
- ✅ Language field coverage (per-project breakdown)
- ✅ project_name consistency
- ✅ Qdrant vector coverage
- ✅ Service health (intelligence, bridge, search)
- ✅ Identifies orphaned data

**Exit Codes**:
- `0` - All checks passed
- `1` - Warnings (e.g., orphaned data needs cleanup)
- `2` - Failures (e.g., services down)

---

### 2. `verify_pipeline_status.py` (Pipeline Health)

**Purpose**: Check data pipeline health across all components

**Usage**:
```bash
python3 scripts/verify_pipeline_status.py        # Standard check
python3 scripts/verify_pipeline_status.py --verbose
python3 scripts/verify_pipeline_status.py --json
```

**Checks**:
- Kafka/Redpanda health
- Memgraph field coverage (overall stats)
- Qdrant vectors
- Consumer health
- Service health

---

### 3. `validate_data_integrity.py` (Data Layer)

**Purpose**: Validate data integrity across storage layers

**Usage**:
```bash
python3 scripts/validate_data_integrity.py       # Standard check
python3 scripts/validate_data_integrity.py --verbose
python3 scripts/validate_data_integrity.py --json
```

**Checks**:
- Memgraph document nodes
- Qdrant collections
- Search service file paths
- Metadata filtering

---

### 4. `cleanup_orphaned_data.sh` (Maintenance)

**Purpose**: Clean up orphaned FILE nodes from old ingestions

**Usage**:
```bash
./scripts/cleanup_orphaned_data.sh
```

**What it does**:
1. Shows current state (total vs orphaned nodes)
2. Prompts for confirmation
3. Deletes FILE nodes without project_name
4. Shows final state

**Safe to run**: Only deletes nodes lacking proper metadata

---

## Quick Verification Workflow

### Daily Health Check
```bash
python3 scripts/verify_recent_fixes.py
```

### After Making Changes
```bash
python3 scripts/verify_recent_fixes.py --verbose
```

### Full Pipeline Audit
```bash
python3 scripts/verify_pipeline_status.py --verbose
python3 scripts/validate_data_integrity.py --verbose
```

### After Major Migration
```bash
# 1. Verify fixes
python3 scripts/verify_recent_fixes.py --verbose

# 2. Clean orphaned data (if needed)
./scripts/cleanup_orphaned_data.sh

# 3. Re-index (if needed)
python3 scripts/bulk_ingest_repository.py /path/to/project

# 4. Verify again
python3 scripts/verify_recent_fixes.py --verbose
```

---

## Troubleshooting

### "Language coverage below target"
- **If per-project coverage is good**: Run `cleanup_orphaned_data.sh` to remove old data
- **If per-project coverage is low**: Re-run ingestion with latest enrichment fixes

### "Qdrant vector coverage low"
- **Solution**: Re-index repository
  ```bash
  python3 scripts/bulk_ingest_repository.py /path/to/project \
    --project-name project-name \
    --kafka-servers 192.168.86.200:29092
  ```

### "Service unhealthy"
- **Solution**: Restart service
  ```bash
  docker restart archon-<service-name>
  docker logs archon-<service-name>  # Check logs
  ```

### "vLLM service connection failed"
- **Check**: Verify vLLM service is running at 192.168.86.201:8002
  ```bash
  curl http://192.168.86.201:8002/health
  ```

---

## CI/CD Integration

### GitHub Actions
```yaml
- name: Verify Infrastructure
  run: |
    python3 scripts/verify_recent_fixes.py --json > verification.json
    python3 scripts/verify_pipeline_status.py --json > pipeline.json
```

### Cron Jobs
```bash
# Daily health check
0 9 * * * cd /path/to/omniarchon && python3 scripts/verify_recent_fixes.py

# Weekly full audit
0 0 * * 0 cd /path/to/omniarchon && python3 scripts/verify_pipeline_status.py --verbose
```

---

## See Also

- `VERIFICATION_SUMMARY.md` - Latest verification results and recommendations
- `docs/OBSERVABILITY.md` - Complete observability guide
- `docs/VALIDATION_SCRIPT.md` - Validation script details
