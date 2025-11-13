# Pipeline Verification & Diagnostic Scripts

**Purpose**: Automated verification and diagnosis of the Archon intelligence pipeline.

**Problem Solved**: Eliminates manual verification and provides single source of truth for pipeline status.

## Scripts Overview

### 1. `verify_pipeline_status.py` - Main Status Script

**What it does**: Checks ALL data sources to verify pipeline health in one command.

**Checks performed**:
- ✅ **Kafka**: Messages published, consumer lag, topics health
- ✅ **Memgraph**: Document counts, language field %, file_extension field %
- ✅ **Qdrant**: Vector counts, collection health
- ✅ **Consumers**: Processing status, error rates
- ✅ **Services**: Health endpoints (intelligence, bridge, search, vLLM)

**Usage**:
```bash
# Quick status check
python3 scripts/verify_pipeline_status.py

# Verbose output with diagnostics
python3 scripts/verify_pipeline_status.py --verbose

# JSON output for CI/CD integration
python3 scripts/verify_pipeline_status.py --json

# Continuous monitoring
watch -n 30 python3 scripts/verify_pipeline_status.py
```

**Example Output**:
```
============================================================
PIPELINE STATUS VERIFICATION
============================================================
Timestamp: 2025-11-08 13:17:00

📊 DATA SOURCES
------------------------------------------------------------
✅ Kafka Messages Published:        2,025
   Consumer Lag:                    0
✅ Memgraph Files:                  3,232
   ├─ Language field:             40.13%  ❌ (target: >90%)
   └─ Extension field:             0.00%  ❌ (target: 100%)
✅ Qdrant Vectors:                  2,145
✅ Consumer Error Rate:             0.0%

🚦 SERVICES
------------------------------------------------------------
✅ archon-intelligence          http://localhost:8053 (45ms)
✅ archon-bridge                http://localhost:8054 (32ms)
✅ archon-search                http://localhost:8055 (28ms)
✅ vLLM Embeddings              http://192.168.86.201:8002 (120ms)

🔍 PIPELINE HEALTH: ⚠️  DEGRADED
   Issue: file_extension field not reaching Memgraph
   Language coverage below target (40.13% < 90%)

RECOMMENDATIONS:
  - Run diagnostic: python3 scripts/diagnose_pipeline_issue.py --field file_extension
  - Run diagnostic: python3 scripts/diagnose_pipeline_issue.py --field language
============================================================
```

**Exit Codes**:
- `0` - HEALTHY (all systems operational)
- `1` - DEGRADED (some issues, still functional)
- `2` - UNHEALTHY (critical failures)

**Integration with CI/CD**:
```bash
# In your CI/CD pipeline
python3 scripts/verify_pipeline_status.py --json > status.json

# Check exit code
if [ $? -eq 0 ]; then
  echo "Pipeline healthy ✅"
elif [ $? -eq 1 ]; then
  echo "Pipeline degraded ⚠️"
  # Send alert but continue
else
  echo "Pipeline unhealthy ❌"
  # Fail the build
  exit 1
fi
```

---

### 2. `diagnose_pipeline_issue.py` - Deep Diagnostic Tool

**What it does**: Traces a test document through the ENTIRE pipeline to identify exactly where data is lost.

**Pipeline steps traced**:
1. **Read File** - Load file content
2. **Extract Metadata** - Get language, file_extension, etc.
3. **Intelligence Service** - Call `/process/document` endpoint
4. **Memgraph Storage** - Verify FILE node has field
5. **Qdrant Vectors** - Check vector metadata has field

**Usage**:
```bash
# Diagnose why file_extension isn't reaching Memgraph
python3 scripts/diagnose_pipeline_issue.py --field file_extension

# Diagnose language field issue
python3 scripts/diagnose_pipeline_issue.py --field language

# Test with specific file
python3 scripts/diagnose_pipeline_issue.py --field file_extension --file-path /path/to/test.py
```

**Example Output**:
```
================================================================================
PIPELINE DIAGNOSTIC: Tracing field 'file_extension'
================================================================================
Test file: /Volumes/PRO-G40/Code/omniarchon/README.md
Timestamp: 2025-11-08 13:20:00

✅ Step 1: Read File
   Status: PASS
   file_path: /Volumes/PRO-G40/Code/omniarchon/README.md
   content_length: 15234
   content_preview: # Archon - Intelligence Provider...

✅ Step 2: Extract Metadata
   Status: PASS
   extracted_metadata: {'file_name': 'README.md', 'file_extension': '.md', 'language': 'markdown', 'size_bytes': 15234}
   file_extension_present: True
   file_extension_value: .md

⚠️  Step 3: Intelligence Service
   Status: WARN
   endpoint: /process/document
   status_code: 200
   file_extension_present: False
   file_extension_value: (missing)
   response_keys: ['file_path', 'content', 'language', 'entities']

❌ Step 4: Memgraph Storage
   Status: FAIL
   file_path: /Volumes/PRO-G40/Code/omniarchon/README.md
   node_found: True
   file_extension_present: False
   file_extension_value: (missing)
   all_properties: ['file_path', 'content', 'language', 'created_at']

================================================================================
DIAGNOSTIC SUMMARY
================================================================================

Results: 2 PASS | 1 FAIL | 1 WARN

Field Tracking:
  Field: file_extension
  Last seen: Step 2: Extract Metadata
  Lost at: Step 3: Intelligence Service

RECOMMENDATIONS:
  1. Field 'file_extension' lost at intelligence service
  2. Check /process/document endpoint implementation
  3. Verify intelligence service passes metadata through
  4. Review: services/intelligence/src/api/endpoints/extraction_router.py
================================================================================
```

**What this tells you**:
- ✅ Field **WAS** extracted correctly (Step 2)
- ❌ Field **LOST** at intelligence service (Step 3)
- 🎯 **ROOT CAUSE**: Intelligence service not passing file_extension through
- 📝 **ACTION**: Review extraction_router.py line where /process/document is defined

---

## Typical Workflows

### Workflow 1: Daily Health Check

```bash
# Morning check - is everything working?
python3 scripts/verify_pipeline_status.py

# If issues found, run diagnostic
python3 scripts/diagnose_pipeline_issue.py --field file_extension
```

### Workflow 2: After Code Changes

```bash
# 1. Make code changes
# 2. Restart services
docker compose restart archon-intelligence archon-bridge

# 3. Verify pipeline health
python3 scripts/verify_pipeline_status.py --verbose

# 4. If issues, diagnose
python3 scripts/diagnose_pipeline_issue.py --field <problematic_field>
```

### Workflow 3: After Bulk Ingestion

```bash
# 1. Ingest repository
python3 scripts/bulk_ingest_repository.py /path/to/project \
  --project-name my-project \
  --kafka-servers 192.168.86.200:29092

# 2. Wait for processing (check consumer lag)
python3 scripts/verify_pipeline_status.py

# 3. Verify field coverage meets targets
# Target: language >= 90%, file_extension = 100%
```

### Workflow 4: Continuous Monitoring

```bash
# Terminal 1: Real-time status monitoring
watch -n 30 python3 scripts/verify_pipeline_status.py

# Terminal 2: Service logs
docker compose logs -f archon-intelligence archon-bridge archon-kafka-consumer

# Terminal 3: Consumer metrics
watch -n 10 'docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumer-group'
```

---

## Understanding Pipeline Health States

### ✅ HEALTHY
- All services responding
- Kafka consumer lag = 0
- Language coverage >= 90%
- Extension coverage >= 90%
- No errors in logs

**Action**: None needed

### ⚠️  DEGRADED
- Most services responding (2-3 of 4)
- Language coverage 50-90%
- Extension coverage 50-90%
- Some consumer lag (< 100)

**Action**:
- Run diagnostic to identify issue
- Review recent code changes
- Check service logs

### ❌ UNHEALTHY
- Multiple services down (< 2 of 4)
- Language/extension coverage < 50%
- High consumer lag (> 100)
- Critical errors in logs

**Action**:
- Check Docker services: `docker ps`
- Restart unhealthy services
- Review error logs
- Consider full system restart

---

## Troubleshooting Common Issues

### Issue: "file_extension field not reaching Memgraph"

**Diagnosis**:
```bash
python3 scripts/diagnose_pipeline_issue.py --field file_extension
```

**Common causes**:
1. Intelligence service not passing field through
2. Memgraph write missing field
3. Consumer not extracting field

**Fix locations**:
- `services/intelligence/src/api/endpoints/extraction_router.py`
- `services/intelligence/src/integrations/tree_stamping_bridge.py`
- `services/intelligence/src/services/directory_indexer.py`

### Issue: "Language coverage below target"

**Diagnosis**:
```bash
python3 scripts/diagnose_pipeline_issue.py --field language
```

**Common causes**:
1. Language detection logic missing
2. Unsupported file extensions
3. Metadata not enriched

**Fix locations**:
- `services/bridge/src/enrichment/metadata_enrichment.py`
- `services/intelligence/src/services/directory_indexer.py`

### Issue: "High consumer lag"

**Check**:
```bash
docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumer-group
```

**Common causes**:
1. Consumer instances not running
2. Processing too slow
3. Too many messages queued

**Fixes**:
```bash
# Restart consumers
docker compose restart archon-kafka-consumer

# Check consumer logs
docker logs archon-kafka-consumer --tail 100

# Scale consumers (if needed)
docker compose up -d --scale archon-kafka-consumer=4
```

### Issue: "Service health check failed"

**Check**:
```bash
# View service logs
docker logs archon-intelligence --tail 50
docker logs archon-bridge --tail 50

# Restart service
docker compose restart archon-intelligence
```

---

## Dependencies

**Python packages** (already in project):
- `requests` - HTTP calls to services
- `neo4j` - Memgraph driver
- `subprocess` - Docker/rpk commands

**External services required**:
- Docker & docker-compose
- Redpanda (omninode-bridge-redpanda)
- Memgraph (archon-memgraph)
- Qdrant (archon-qdrant)
- Intelligence service (archon-intelligence)
- Bridge service (archon-bridge)
- Search service (archon-search)

---

## Integration with Existing Tools

### Works with existing monitoring

These scripts complement existing tools:

- `scripts/validate_data_integrity.py` - Data layer validation
- `scripts/validate_integrations.sh` - Integration testing
- `scripts/health_monitor.py` - Real-time monitoring
- `scripts/view_pipeline_logs.py` - Log aggregation

### Recommended monitoring stack

```bash
# Terminal 1: Real-time status
watch -n 30 python3 scripts/verify_pipeline_status.py

# Terminal 2: Health monitoring dashboard
python3 scripts/health_monitor.py --dashboard

# Terminal 3: Pipeline logs
./scripts/logs.sh follow

# Terminal 4: Kafka consumer metrics
watch -n 10 'docker exec omninode-bridge-redpanda rpk group describe archon-intelligence-consumer-group'
```

---

## Automation & CI/CD

### Cron job example

```bash
# Add to crontab for automated checks
# Check pipeline health every 30 minutes
*/30 * * * * cd /Volumes/PRO-G40/Code/omniarchon && python3 scripts/verify_pipeline_status.py --json > /tmp/pipeline_status.json

# Email on degraded status
*/30 * * * * cd /Volumes/PRO-G40/Code/omniarchon && python3 scripts/verify_pipeline_status.py || echo "Pipeline degraded" | mail -s "Archon Alert" admin@example.com
```

### GitHub Actions integration

```yaml
- name: Verify Pipeline Health
  run: |
    python3 scripts/verify_pipeline_status.py --json > status.json

- name: Upload Status
  uses: actions/upload-artifact@v2
  with:
    name: pipeline-status
    path: status.json

- name: Fail on Unhealthy
  run: |
    if [ $? -eq 2 ]; then
      echo "Pipeline unhealthy - failing build"
      exit 1
    fi
```

---

## Questions?

**For pipeline issues**: Run diagnostic first, then check service logs
**For service failures**: Check Docker logs and restart services
**For data issues**: Run data integrity validation script

**Related documentation**:
- `docs/OBSERVABILITY.md` - Complete observability guide
- `docs/VALIDATION_SCRIPT.md` - Data integrity validation
- `docs/LOG_VIEWER.md` - Log aggregation guide
- `scripts/MONITORING_GUIDE.md` - Monitoring best practices
