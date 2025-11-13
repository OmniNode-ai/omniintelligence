# Graph Health Validation

Permanent monitoring system for Memgraph knowledge graph integrity.

## Quick Start

```bash
# Validate entire graph
python3 scripts/validate_graph_health.py

# Validate specific project
python3 scripts/validate_graph_health.py --project omnidash

# Fail on warnings (for CI/CD)
python3 scripts/validate_graph_health.py --fail-on-warn
```

## What It Checks

### 1. Relationship Creation ✅
- **Critical**: Detects if relationships are being created at all
- **Warning**: Flags low relationship density (<0.5 per file)
- **Why**: Catches bugs like the `/extract/code` endpoint issue

### 2. File Tree Structure ✅
- **Critical**: Validates PROJECT and DIRECTORY nodes exist
- **Critical**: Detects orphaned files (>10 orphaned = broken tree)
- **Warning**: Flags incomplete tree coverage (<95%)
- **Why**: Catches label case mismatches and timing issues

### 3. Graph Connectivity ✅
- **Critical**: Detects completely disconnected graphs (0 relationships)
- **Warning**: Flags sparse graphs (<0.3 relationships per node)
- **Why**: Catches relationship creation pipeline failures

### 4. Relationship Types ✅
- **Warning**: Detects missing expected relationship types
- **Expected Types**: IMPORTS, DEFINES, CALLS, CONTAINS
- **Why**: Catches extraction service failures

## Exit Codes

- `0`: All checks passed
- `1`: Warnings found (with `--fail-on-warn`)
- `2`: Critical issues found

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/validate-graph.yml
name: Validate Graph Health

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Start Memgraph
        run: docker-compose up -d memgraph
      - name: Wait for Memgraph
        run: sleep 10
      - name: Run ingestion
        run: python3 scripts/bulk_ingest_repository.py . --project-name test
      - name: Validate graph
        run: python3 scripts/validate_graph_health.py --fail-on-warn
```

### Pre-commit Hook

```bash
# .git/hooks/pre-push
#!/bin/bash
python3 scripts/validate_graph_health.py --fail-on-warn
if [ $? -ne 0 ]; then
    echo "❌ Graph validation failed! Fix issues before pushing."
    exit 1
fi
```

### Cron Job (Production Monitoring)

```bash
# Add to crontab for hourly validation
0 * * * * cd /path/to/omniarchon && python3 scripts/validate_graph_health.py --fail-on-warn || echo "Graph validation failed!" | mail -s "ALERT: Graph Health Issue" team@example.com
```

## Integration with Existing Scripts

### verify_environment.py

The validation script complements `verify_environment.py`:

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `verify_environment.py` | Service health + data counts | After deployment, daily checks |
| `validate_graph_health.py` | **Graph integrity** validation | After ingestion, CI/CD, pre-push |

**Combined workflow**:
```bash
# After ingestion
python3 scripts/bulk_ingest_repository.py /path/to/repo --project-name myproject

# Verify services are healthy
python3 scripts/verify_environment.py

# Validate graph integrity ✅ NEW
python3 scripts/validate_graph_health.py --fail-on-warn
```

## Thresholds (Configurable)

Edit `scripts/validate_graph_health.py` to adjust:

```python
THRESHOLDS = {
    "min_relationships_per_file": 0.5,  # Increase for stricter validation
    "min_tree_coverage": 0.95,          # 95% of files must be in tree
    "max_orphaned_files": 10,           # Max acceptable orphaned files
    "min_project_nodes": 1,             # Must have at least 1 PROJECT
}
```

## Example Output

### ✅ Healthy Graph

```
======================================================================
🔍 GRAPH HEALTH VALIDATION
======================================================================

======================================================================
📊 RESULTS
======================================================================

✅ PASSING CHECKS:
  ✅ Relationship creation healthy: 1247 relationships for 346 files (3.60 per file)
  ✅ File tree complete: 1 PROJECT, 67 DIRECTORY, 346/346 files in tree
  ✅ Graph connectivity healthy: 2.45 relationships per node
  ✅ Relationship types: IMPORTS: 856, DEFINES: 234, CALLS: 123, CONTAINS: 34

======================================================================
🎉 STATUS: ALL CHECKS PASSED
======================================================================
```

### ❌ Broken Graph (What We Caught Today)

```
======================================================================
🔍 GRAPH HEALTH VALIDATION
======================================================================

======================================================================
📊 RESULTS
======================================================================

❌ CRITICAL ISSUES:
  ❌ CRITICAL: 0 relationships found for 346 files! Relationship creation is broken.
  ❌ CRITICAL: No PROJECT nodes found! Tree structure missing.
  ❌ CRITICAL: 346 orphaned files (max: 10)

======================================================================
🚨 STATUS: CRITICAL ISSUES FOUND
======================================================================
```

## Troubleshooting

### Issue: Script finds problems after fresh ingestion

**Likely causes**:
1. **Timing**: Consumer hasn't finished processing yet
   - **Fix**: Wait 30s and re-run validation

2. **Code bugs**: Relationship/tree creation broken
   - **Fix**: Check consumer logs for errors
   - **Fix**: Review recent code changes to graph creation logic

3. **Configuration**: Wrong Memgraph instance
   - **Fix**: Verify `--uri bolt://localhost:7687`

### Issue: Script always passes but manual checks fail

**Likely causes**:
1. **Thresholds too lenient**: Adjust `THRESHOLDS` in script
2. **Wrong project filter**: Validate correct project with `--project`

## Why This Matters

**Before permanent validation**:
- ✗ Relied on manual spot checks
- ✗ Issues discovered in production
- ✗ No automated regression detection

**After permanent validation**:
- ✅ Automatic validation after every ingestion
- ✅ CI/CD catches regressions before merge
- ✅ Production monitoring with alerts
- ✅ Clear, actionable error messages

## Future Enhancements

1. **Slack/email alerts** when validation fails
2. **Historical tracking** of validation metrics over time
3. **Per-project validation** with different thresholds
4. **Performance regression** detection (ingestion time)
5. **Data quality scores** (completeness, accuracy)

## Questions?

See also:
- `docs/OBSERVABILITY.md` - Complete monitoring guide
- `docs/VALIDATION_SCRIPT.md` - Data integrity validation
- `scripts/verify_environment.py` - Service health checks
