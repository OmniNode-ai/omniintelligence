# Data Integrity Validation Script

Automated script for checking Archon intelligence platform data integrity.

## Location

`/Volumes/PRO-G40/Code/omniarchon/scripts/validate_data_integrity.py`

## Usage

### Basic validation (human-readable report):
```bash
python3 scripts/validate_data_integrity.py
```

### Verbose output (includes collection details):
```bash
python3 scripts/validate_data_integrity.py --verbose
```

### JSON output (for automation and CI/CD):
```bash
python3 scripts/validate_data_integrity.py --json
```

### Example output (human-readable):
```
======================================================================
📊 ARCHON DATA INTEGRITY VALIDATION REPORT
======================================================================
Timestamp: 2025-10-29T11:04:20.197330

🟢 Overall Health: HEALTHY
   4/4 components healthy

📊 Memgraph Knowledge Graph
   Status: healthy
   Document nodes: 25,249

🔍 Qdrant Vector Database
   Status: healthy
   Total vectors: 25,249
   Collections: 6
   File collections:
      - file_locations: 25,249 points
      - omniarchon_documents: 12,500 points

📁 File Path Retrieval
   Status: working
   Paths found: 10/10
   Retrieval rate: 100.0%

🏷️  Metadata Filtering
   Status: working
   Filter test: 5/5 correct
   Accuracy: 100.0%
======================================================================
```

## What it checks

### 1. Memgraph Knowledge Graph
- **Check**: Count of Document nodes in Memgraph
- **Healthy**: Document count > 0
- **Command**: `docker exec memgraph mgconsole --command "MATCH (n:Document) RETURN count(n)"`

### 2. Qdrant Vector Database
- **Check**: Vector collection coverage and point counts
- **Healthy**: Total points > 0
- **Details**: Lists all collections and file-related collections
- **Endpoint**: `GET http://localhost:6333/collections`

### 3. File Path Retrieval
- **Check**: Search service can retrieve file paths from metadata
- **Healthy**: Paths found in search results
- **Test**: RAG search for "python code" with 10 results
- **Endpoint**: `POST http://localhost:8055/search/rag`

### 4. Metadata Filtering
- **Check**: Metadata filtering functionality works correctly
- **Healthy**: Language filter returns correctly filtered results
- **Test**: Filter by language="python" and verify results
- **Endpoint**: `POST http://localhost:8055/search/rag` with filters

## Exit codes

The script returns exit codes based on overall system health:

- **0**: Healthy (3-4 components working)
- **1**: Degraded (2 components working)
- **2**: Unhealthy (0-1 components working)

This makes the script suitable for CI/CD integration and automated monitoring.

## Integration examples

### Cron job for periodic validation:
```bash
# Check every hour and log results
0 * * * * /path/to/scripts/validate_data_integrity.py --json >> /var/log/archon_validation.log 2>&1

# Alert on degraded health (exit code 1 or 2)
0 * * * * /path/to/scripts/validate_data_integrity.py --json || echo "Archon health check failed" | mail -s "Alert" admin@example.com
```

### CI/CD pipeline integration:
```yaml
# GitHub Actions example
- name: Validate Data Integrity
  run: |
    python3 scripts/validate_data_integrity.py --json > validation_report.json
    cat validation_report.json

- name: Check exit code
  run: |
    python3 scripts/validate_data_integrity.py || exit 1
```

### Docker healthcheck:
```dockerfile
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
  CMD python3 /app/scripts/validate_data_integrity.py --json || exit 1
```

### Monitoring script:
```bash
#!/bin/bash
# Monitor Archon health and send alerts

REPORT=$(python3 scripts/validate_data_integrity.py --json)
STATUS=$?

if [ $STATUS -eq 2 ]; then
  echo "CRITICAL: Archon unhealthy"
  echo "$REPORT" | jq '.overall_health'
  # Send critical alert (Slack, PagerDuty, etc.)
elif [ $STATUS -eq 1 ]; then
  echo "WARNING: Archon degraded"
  echo "$REPORT" | jq '.overall_health'
  # Send warning notification
else
  echo "OK: Archon healthy"
fi
```

## Troubleshooting

### All components show "error" status
**Problem**: Services are not running or not accessible
**Solution**: Start services with `docker compose up -d` and verify with `docker ps`

### Memgraph shows "empty" status
**Problem**: No documents indexed in knowledge graph
**Solution**: Run ingestion with `python3 scripts/bulk_ingest_repository.py`

### Qdrant shows "empty" status
**Problem**: Vector collections exist but have no points
**Solution**: Check indexing pipeline and verify event bus is processing stamping requests

### Search service shows 404 errors
**Problem**: Search service (port 8055) is not running
**Solution**: Check service with `curl http://localhost:8055/health` and restart if needed

### Metadata filtering shows low accuracy
**Problem**: Metadata not properly stored or filters not working
**Solution**: Verify metadata extraction in bridge service and check stamping configuration

## Configuration

The script uses these default endpoints:

```python
QDRANT_URL = "http://localhost:6333"
SEARCH_URL = "http://localhost:8055"
MEMGRAPH_CONTAINER = "memgraph"
```

To use different endpoints, modify these constants at the top of the script.

## Related Documentation

- `/docs/AUTO_INDEXING_GUIDE.md` - Automated indexing and ingestion
- `/docs/METADATA_EXTRACTION_SUMMARY.md` - Metadata extraction details
- `/scripts/BULK_INGEST_README.md` - Bulk ingestion documentation
- `/docs/guides/SEARCH_SERVICE_GUIDE.md` - Search service configuration

## Requirements

- Python 3.8+
- `requests` library
- Docker (for Memgraph check)
- Running Archon services (for full validation)

## Development

To modify the script or add new checks:

1. Add new check function following the pattern:
   ```python
   def check_new_component() -> Dict[str, Any]:
       """Check new component"""
       try:
           # Perform check
           return {
               "status": "healthy" | "working" | "empty" | "error",
               "metric_name": value,
               "error": None
           }
       except Exception as e:
           return {"status": "error", "error": str(e)}
   ```

2. Add to `generate_report()`:
   ```python
   report["new_component"] = check_new_component()
   ```

3. Add to `print_report()`:
   ```python
   nc = report["new_component"]
   print(f"🔧 New Component")
   print(f"   Status: {nc['status']}")
   # ... print metrics
   ```

4. Update health calculation if needed:
   ```python
   healthy_count = sum(
       1 for component in [report["memgraph"], report["qdrant"],
                          report["search_paths"], report["metadata_filtering"],
                          report["new_component"]]  # Add new component
       if component["status"] in ["healthy", "working"]
   )
   ```

## Version History

- **v1.0** (2025-10-29): Initial release with 4 core checks
  - Memgraph document count
  - Qdrant vector collections
  - File path retrieval
  - Metadata filtering
