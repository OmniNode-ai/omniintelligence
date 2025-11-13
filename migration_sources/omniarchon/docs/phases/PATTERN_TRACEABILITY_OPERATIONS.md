# Phase 4 Operations Runbook
# Track 3: Pattern Learning Engine - Pattern Traceability & Feedback Loop

**Version**: 1.0.0
**Last Updated**: 2025-10-03
**Team**: Archon Intelligence Team

---

## Table of Contents

1. [Deployment Procedures](#deployment-procedures)
2. [Database Maintenance](#database-maintenance)
3. [Backup and Recovery](#backup-and-recovery)
4. [Performance Tuning](#performance-tuning)
5. [Monitoring and Alerting](#monitoring-and-alerting)
6. [Common Issues and Solutions](#common-issues-and-solutions)
7. [Escalation Procedures](#escalation-procedures)

---

## Deployment Procedures

### Initial Deployment

**Prerequisites**:
- PostgreSQL 15+ running (omninode_bridge database)
- Python 3.12+ environment
- Track 2 Intelligence Hooks operational

**Deployment Steps**:

```bash
# 1. Deploy database schema
cd services/intelligence
psql $TRACEABILITY_DB_URL_EXTERNAL -f database/schema/phase4_lineage_schema.sql

# 2. Verify schema deployment
psql $TRACEABILITY_DB_URL_EXTERNAL -c '\dt lineage_*'
# Expected output: lineage_nodes, lineage_edges, lineage_events

# 3. Create indexes for performance
psql $TRACEABILITY_DB_URL_EXTERNAL -f database/schema/phase4_lineage_indexes.sql

# 4. Verify indexes
psql $TRACEABILITY_DB_URL_EXTERNAL -c '\di lineage_*'

# 5. Run integration tests
cd src/services/pattern_learning/phase4_traceability
pytest tests/ -v --cov=. --cov-report=html

# 6. Verify test coverage >95%
# Check htmlcov/index.html

# 7. Start Intelligence Service
# Docker: docker compose up archon-intelligence -d
# OR Manual: poetry run python app.py

# 8. Verify service health
curl http://localhost:8053/health
# Expected: {"status": "healthy", ...}

# 9. Test Phase 4 endpoints
curl http://localhost:8053/api/analytics/health
curl http://localhost:8053/api/lineage/health
curl http://localhost:8053/api/feedback-loop/health
```

### Production Deployment Checklist

- [ ] Database schema deployed and verified
- [ ] All indexes created and analyzed
- [ ] Integration tests passing (>95% coverage)
- [ ] Health endpoints responding
- [ ] Monitoring configured (Prometheus + Grafana)
- [ ] Alerting rules deployed
- [ ] Backup procedures tested
- [ ] Rollback plan documented
- [ ] Team notification sent
- [ ] Documentation updated

### Rolling Updates

```bash
# Zero-downtime deployment procedure

# 1. Deploy new version to staging
docker build -t archon-intelligence:v1.1.0 .
docker tag archon-intelligence:v1.1.0 archon-intelligence:staging

# 2. Test in staging
./scripts/smoke_test_phase4.sh staging

# 3. Tag for production
docker tag archon-intelligence:v1.1.0 archon-intelligence:latest

# 4. Rolling update
docker compose up -d --no-deps --scale archon-intelligence=2 archon-intelligence
# Wait for health checks
sleep 30
curl http://localhost:8053/health

# 5. Scale down old version
docker compose up -d --no-deps --scale archon-intelligence=1 archon-intelligence

# 6. Verify deployment
./scripts/smoke_test_phase4.sh production
```

### Rollback Procedure

```bash
# If deployment fails, rollback to previous version

# 1. Identify last known good version
docker images archon-intelligence --format "{{.Tag}}\t{{.CreatedAt}}"

# 2. Rollback docker image
docker tag archon-intelligence:v1.0.9 archon-intelligence:latest

# 3. Restart service
docker compose restart archon-intelligence

# 4. Verify health
curl http://localhost:8053/health

# 5. Check lineage integrity (no data loss)
psql $TRACEABILITY_DB_URL_EXTERNAL -c "
  SELECT COUNT(*) FROM lineage_nodes;
  SELECT COUNT(*) FROM lineage_edges;
"

# 6. Notify team of rollback
./scripts/notify_rollback.sh "Phase 4 rolled back to v1.0.9"
```

---

## Database Maintenance

### Daily Maintenance

```bash
#!/bin/bash
# daily_maintenance_phase4.sh

# Vacuum and analyze lineage tables
psql $TRACEABILITY_DB_URL_EXTERNAL <<EOF
VACUUM ANALYZE lineage_nodes;
VACUUM ANALYZE lineage_edges;
VACUUM ANALYZE lineage_events;

-- Check table sizes
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'lineage_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT
  indexrelname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexrelname LIKE 'idx_lineage_%'
ORDER BY idx_scan DESC;
EOF
```

### Weekly Maintenance

```bash
#!/bin/bash
# weekly_maintenance_phase4.sh

# Full vacuum and reindex
psql $TRACEABILITY_DB_URL_EXTERNAL <<EOF
-- Full vacuum (requires low activity period)
VACUUM FULL lineage_events;  -- Events table grows fastest

-- Reindex for performance
REINDEX TABLE lineage_nodes;
REINDEX TABLE lineage_edges;
REINDEX TABLE lineage_events;

-- Update statistics
ANALYZE lineage_nodes;
ANALYZE lineage_edges;
ANALYZE lineage_events;

-- Check for bloat
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
  round(100 * pg_relation_size(schemaname||'.'||tablename) /
    NULLIF(pg_total_relation_size(schemaname||'.'||tablename), 0), 2) AS table_pct
FROM pg_tables
WHERE tablename LIKE 'lineage_%';
EOF
```

### Data Archival

Archive old lineage events to reduce table size:

```sql
-- Archive events older than 90 days
BEGIN;

-- Create archive table if not exists
CREATE TABLE IF NOT EXISTS lineage_events_archive (LIKE lineage_events INCLUDING ALL);

-- Move old events to archive
INSERT INTO lineage_events_archive
SELECT * FROM lineage_events
WHERE timestamp < CURRENT_DATE - INTERVAL '90 days';

-- Delete archived events from main table
DELETE FROM lineage_events
WHERE timestamp < CURRENT_DATE - INTERVAL '90 days';

-- Vacuum after deletion
VACUUM FULL lineage_events;

COMMIT;
```

---

## Backup and Recovery

### Automated Backups

```bash
#!/bin/bash
# backup_phase4_data.sh

# NOTE: Customize BACKUP_DIR for your environment
# Default: /var/backups/archon/phase4 (ensure directory exists and has appropriate permissions)
BACKUP_DIR="${ARCHON_BACKUP_DIR:-/var/backups/archon/phase4}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup lineage tables
pg_dump $TRACEABILITY_DB_URL_EXTERNAL \
  --table=lineage_nodes \
  --table=lineage_edges \
  --table=lineage_events \
  --format=custom \
  --file=$BACKUP_DIR/phase4_lineage_$TIMESTAMP.dump

# Backup schema only
pg_dump $TRACEABILITY_DB_URL_EXTERNAL \
  --schema-only \
  --table=lineage_* \
  --file=$BACKUP_DIR/phase4_schema_$TIMESTAMP.sql

# Compress backups
gzip $BACKUP_DIR/phase4_schema_$TIMESTAMP.sql

# Upload to S3 (or backup storage)
# aws s3 cp $BACKUP_DIR/phase4_lineage_$TIMESTAMP.dump s3://archon-backups/phase4/

# Keep only last 30 days of backups locally
find $BACKUP_DIR -name "phase4_*.dump" -mtime +30 -delete

echo "✅ Phase 4 backup completed: phase4_lineage_$TIMESTAMP.dump"
```

**Schedule**: Daily at 2 AM via cron
```cron
# NOTE: Customize paths for your environment:
# - Script path: /opt/archon/scripts/backup_phase4_data.sh
# - Log path: /var/log/archon/phase4_backup.log (ensure log directory exists)
0 2 * * * /opt/archon/scripts/backup_phase4_data.sh >> /var/log/archon/phase4_backup.log 2>&1
```

### Recovery Procedures

**Scenario 1: Recover Deleted Lineage Data**

```bash
# 1. Identify latest backup
ls -lht /var/backups/archon/phase4/phase4_lineage_*.dump | head -1

# 2. Create temporary recovery database
# Note: Uses connection parameters from TRACEABILITY_DB_URL_EXTERNAL
createdb phase4_recovery

# 3. Restore backup to temporary database
# Security: Modify connection string inline without storing credentials in variables
pg_restore \
  --dbname="$(echo $TRACEABILITY_DB_URL_EXTERNAL | sed 's/omninode_bridge$/phase4_recovery/')" \
  --verbose \
  /var/backups/archon/phase4/phase4_lineage_20251003_020000.dump

# 4. Verify recovered data
psql "$(echo $TRACEABILITY_DB_URL_EXTERNAL | sed 's/omninode_bridge$/phase4_recovery/')" -c "
  SELECT COUNT(*) FROM lineage_nodes;
  SELECT COUNT(*) FROM lineage_edges;
"

# 5. Selective restore to production
# Option A: Restore specific lineage path
psql $TRACEABILITY_DB_URL_EXTERNAL <<EOF
BEGIN;

-- Insert missing nodes from recovery DB
INSERT INTO lineage_nodes
SELECT * FROM dblink(
  'dbname=phase4_recovery',
  'SELECT * FROM lineage_nodes WHERE pattern_id = ''<missing-pattern-id>'''
) AS t(
  node_id UUID,
  pattern_id UUID,
  version_number INTEGER,
  -- ... all columns
)
ON CONFLICT (node_id) DO NOTHING;

-- Insert missing edges
INSERT INTO lineage_edges
SELECT * FROM dblink(
  'dbname=phase4_recovery',
  'SELECT * FROM lineage_edges WHERE source_node_id IN (SELECT node_id FROM lineage_nodes WHERE pattern_id = ''<missing-pattern-id>'')'
) AS t(
  edge_id UUID,
  source_node_id UUID,
  target_node_id UUID,
  -- ... all columns
)
ON CONFLICT (edge_id) DO NOTHING;

COMMIT;
EOF

# 6. Verify restoration
psql $TRACEABILITY_DB_URL_EXTERNAL -c "
  SELECT * FROM lineage_nodes WHERE pattern_id = '<missing-pattern-id>';
"

# 7. Clean up temporary database
dropdb phase4_recovery
```

**Scenario 2: Full Database Corruption**

```bash
# 1. Stop Intelligence Service
docker compose stop archon-intelligence

# 2. Drop corrupted tables
psql $TRACEABILITY_DB_URL_EXTERNAL -c "
  DROP TABLE IF EXISTS lineage_events CASCADE;
  DROP TABLE IF EXISTS lineage_edges CASCADE;
  DROP TABLE IF EXISTS lineage_nodes CASCADE;
"

# 3. Restore schema
psql $TRACEABILITY_DB_URL_EXTERNAL -f /var/backups/archon/phase4/phase4_schema_20251003_020000.sql

# 4. Restore data
pg_restore \
  --dbname=$TRACEABILITY_DB_URL_EXTERNAL \
  --verbose \
  /var/backups/archon/phase4/phase4_lineage_20251003_020000.dump

# 5. Verify restoration
psql $TRACEABILITY_DB_URL_EXTERNAL -c "
  SELECT COUNT(*) FROM lineage_nodes;
  SELECT COUNT(*) FROM lineage_edges;
  SELECT COUNT(*) FROM lineage_events;
"

# 6. Rebuild indexes
psql $TRACEABILITY_DB_URL_EXTERNAL -f database/schema/phase4_lineage_indexes.sql

# 7. Restart service
docker compose start archon-intelligence

# 8. Run smoke tests
./scripts/smoke_test_phase4.sh production
```

---

## Performance Tuning

### Database Performance

**Index Optimization**:

```sql
-- Check for missing indexes
SELECT
  schemaname,
  tablename,
  attname,
  n_distinct,
  correlation
FROM pg_stats
WHERE tablename LIKE 'lineage_%'
  AND n_distinct > 100
  AND correlation < 0.1
ORDER BY n_distinct DESC;

-- Add selective indexes based on query patterns
CREATE INDEX CONCURRENTLY idx_lineage_nodes_pattern_version
  ON lineage_nodes(pattern_id, version_number);

CREATE INDEX CONCURRENTLY idx_lineage_edges_type_created
  ON lineage_edges(edge_type, created_at DESC);

CREATE INDEX CONCURRENTLY idx_lineage_events_correlation
  ON lineage_events(correlation_id) WHERE correlation_id IS NOT NULL;
```

**Query Performance Tuning**:

```sql
-- Identify slow queries
SELECT
  query,
  calls,
  total_exec_time,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%lineage_%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Analyze query plan for slow lineage path query
EXPLAIN (ANALYZE, BUFFERS)
WITH RECURSIVE lineage_path AS (
  SELECT node_id, pattern_id, parent_node_id, 1 as depth
  FROM lineage_nodes
  WHERE node_id = '<target-node-id>'

  UNION ALL

  SELECT n.node_id, n.pattern_id, n.parent_node_id, lp.depth + 1
  FROM lineage_nodes n
  INNER JOIN lineage_path lp ON n.node_id = lp.parent_node_id
  WHERE lp.depth < 100
)
SELECT * FROM lineage_path;
```

### Application Performance

**Connection Pooling**:

```python
# Optimal connection pool settings for Phase 4
import asyncpg

pool = await asyncpg.create_pool(
    dsn=TRACEABILITY_DB_URL_EXTERNAL,
    min_size=5,      # Minimum connections
    max_size=20,     # Maximum connections
    max_queries=10000,  # Recycle after 10k queries
    max_inactive_connection_lifetime=300,  # 5 minutes
    command_timeout=60  # Query timeout
)
```

**Caching Strategy**:

```python
from functools import lru_cache
from datetime import timedelta
import time

# Cache analytics results for 5 minutes
class AnalyticsCache:
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, pattern_id, time_window):
        key = f"{pattern_id}:{time_window}"
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None

    def set(self, pattern_id, time_window, result):
        key = f"{pattern_id}:{time_window}"
        self.cache[key] = (result, time.time())

# Usage
analytics_cache = AnalyticsCache(ttl_seconds=300)

async def get_pattern_analytics(pattern_id, time_window):
    # Check cache first
    cached = analytics_cache.get(pattern_id, time_window)
    if cached:
        return cached

    # Compute if not cached
    result = await compute_analytics(pattern_id, time_window)
    analytics_cache.set(pattern_id, time_window, result)
    return result
```

---

## Monitoring and Alerting

### Prometheus Metrics

**Key Metrics to Monitor**:

```yaml
# /monitoring/prometheus/rules/phase4_alerts.yml

groups:
  - name: phase4_lineage
    interval: 30s
    rules:
      # Lineage tracker performance
      - record: phase4:lineage_tracker:insert_duration_seconds
        expr: histogram_quantile(0.95, rate(lineage_insert_duration_seconds_bucket[5m]))

      - alert: Phase4LineageTrackerSlow
        expr: phase4:lineage_tracker:insert_duration_seconds > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Lineage tracker insert operations slow"
          description: "P95 insert duration {{ $value }}s exceeds 50ms threshold"

      # Analytics reducer performance
      - record: phase4:analytics:computation_duration_seconds
        expr: histogram_quantile(0.95, rate(analytics_computation_duration_seconds_bucket[5m]))

      - alert: Phase4AnalyticsSlow
        expr: phase4:analytics:computation_duration_seconds > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Analytics computation slow"
          description: "P95 computation duration {{ $value }}s exceeds 500ms threshold"

      # Feedback loop success rate
      - record: phase4:feedback_loop:success_rate
        expr: rate(feedback_loop_success_total[5m]) / rate(feedback_loop_total[5m])

      - alert: Phase4FeedbackLoopFailures
        expr: phase4:feedback_loop:success_rate < 0.95
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "High feedback loop failure rate"
          description: "Success rate {{ $value | humanizePercentage }} below 95%"

      # Database connection pool
      - alert: Phase4DatabasePoolExhausted
        expr: db_pool_connections_available{service="phase4"} < 2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "Only {{ $value }} connections available"
```

### Grafana Dashboards

**Phase 4 Monitoring Dashboard**:

```json
{
  "dashboard": {
    "title": "Phase 4 - Pattern Traceability",
    "panels": [
      {
        "title": "Lineage Operations",
        "targets": [
          {
            "expr": "rate(lineage_operations_total[5m])",
            "legendFormat": "{{operation}}"
          }
        ]
      },
      {
        "title": "Analytics Computation Time",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(analytics_computation_duration_seconds_bucket[5m]))",
            "legendFormat": "P50"
          },
          {
            "expr": "histogram_quantile(0.95, rate(analytics_computation_duration_seconds_bucket[5m]))",
            "legendFormat": "P95"
          }
        ]
      },
      {
        "title": "Feedback Loop Workflow Duration",
        "targets": [
          {
            "expr": "feedback_loop_workflow_duration_seconds",
            "legendFormat": "{{stage}}"
          }
        ]
      }
    ]
  }
}
```

### Health Check Scripts

```bash
#!/bin/bash
# health_check_phase4.sh

SERVICE_URL="${ARCHON_SERVICE_URL:-http://localhost:8053}"

echo "Checking Phase 4 Health..."

# 1. Database connectivity
if psql $TRACEABILITY_DB_URL_EXTERNAL -c "SELECT 1" > /dev/null 2>&1; then
  echo "✅ Database: Connected"
else
  echo "❌ Database: Connection failed"
  exit 1
fi

# 2. Table existence
TABLES=$(psql $TRACEABILITY_DB_URL_EXTERNAL -t -c "
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_name IN ('lineage_nodes', 'lineage_edges', 'lineage_events')
")
if [ "$TABLES" -eq 3 ]; then
  echo "✅ Tables: All present"
else
  echo "❌ Tables: Missing tables"
  exit 1
fi

# 3. Service health endpoints
if curl -s "$SERVICE_URL/health" | grep -q '"status":"healthy"'; then
  echo "✅ Service: Healthy"
else
  echo "❌ Service: Unhealthy"
  exit 1
fi

# 4. Lineage data integrity
ORPHANED_EDGES=$(psql $TRACEABILITY_DB_URL_EXTERNAL -t -c "
  SELECT COUNT(*) FROM lineage_edges e
  WHERE NOT EXISTS (SELECT 1 FROM lineage_nodes WHERE node_id = e.source_node_id)
     OR NOT EXISTS (SELECT 1 FROM lineage_nodes WHERE node_id = e.target_node_id)
")
if [ "$ORPHANED_EDGES" -eq 0 ]; then
  echo "✅ Data Integrity: No orphaned edges"
else
  echo "⚠️  Data Integrity: $ORPHANED_EDGES orphaned edges found"
fi

echo "Phase 4 health check completed"
```

---

## Common Issues and Solutions

### Issue 1: High Lineage Query Latency

**Symptoms**:
- Lineage path queries taking >1 second
- Dashboard loading slowly

**Diagnosis**:
```sql
-- Check query performance
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM get_lineage_path('<node-id>');

-- Check missing indexes
SELECT * FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname LIKE 'idx_lineage_%';
```

**Solutions**:
1. Ensure indexes exist: `idx_lineage_nodes_parent`, `idx_lineage_edges_source`
2. Run `ANALYZE lineage_nodes; ANALYZE lineage_edges;`
3. Limit traversal depth in queries
4. Cache frequently accessed lineage paths

---

### Issue 2: Feedback Loop Timeout

**Symptoms**:
- Feedback loop workflows timing out
- `WORKFLOW_TIMEOUT` errors

**Diagnosis**:
```bash
# Check current workflows
curl http://localhost:8053/api/feedback-loop/status | jq '.active_workflows'

# Check database query performance
psql $TRACEABILITY_DB_URL_EXTERNAL -c "
  SELECT query, mean_exec_time
  FROM pg_stat_statements
  WHERE query LIKE '%hook_executions%'
  ORDER BY mean_exec_time DESC LIMIT 5;
"
```

**Solutions**:
1. Increase workflow timeout: `workflow_timeout_seconds=120`
2. Reduce `time_window_days` to collect less data
3. Optimize Track 2 `hook_executions` queries
4. Scale Intelligence Service horizontally

---

### Issue 3: Database Connection Pool Exhausted

**Symptoms**:
- `could not obtain connection from pool` errors
- High latency on all operations

**Diagnosis**:
```sql
-- Check current connections
SELECT count(*) FROM pg_stat_activity
WHERE datname = 'omninode_bridge'
  AND application_name LIKE '%intelligence%';

-- Check long-running queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 seconds'
ORDER BY duration DESC;
```

**Solutions**:
1. Increase pool size: `max_size=30`
2. Reduce query timeout: `command_timeout=30`
3. Kill long-running queries: `SELECT pg_terminate_backend(pid)`
4. Implement connection pooling at application level

---

## Escalation Procedures

### Severity Levels

| Severity | Response Time | Examples |
|----------|--------------|----------|
| **P1 - Critical** | 15 minutes | Complete service down, data corruption |
| **P2 - High** | 1 hour | Performance degraded >50%, partial outage |
| **P3 - Medium** | 4 hours | Minor performance issues, non-critical bugs |
| **P4 - Low** | Next business day | Feature requests, documentation updates |

### Escalation Path

```
P4 (Low)        → Engineering Team → Weekly Review
P3 (Medium)     → Team Lead → Review within 4 hours
P2 (High)       → Team Lead → Immediate attention → Engineering Manager if unresolved in 2 hours
P1 (Critical)   → On-Call Engineer → Team Lead → Engineering Manager → CTO (if >1 hour)
```

### Contact Information

**⚠️ IMPORTANT**: Customize all contact information below with your actual team details before use.

**On-Call Rotation**:
- PagerDuty: `archon-intelligence-oncall`
- Slack: `#archon-alerts`
- Email: `archon-oncall@example.com` *(replace with your team's on-call email)*

**Escalation Contacts**:
- **Team Lead**: team-lead@example.com *(replace with actual team lead email)*
- **Engineering Manager**: eng-manager@example.com *(replace with actual engineering manager email)*
- **Database Admin**: dba@example.com *(replace with actual DBA email - for P1 database issues)*

---

## Support & Resources

**Documentation**:
- User Guide: [PATTERN_TRACEABILITY_USER_GUIDE.md](PATTERN_TRACEABILITY_USER_GUIDE.md)
- API Reference: [PATTERN_TRACEABILITY_API_REFERENCE.md](PATTERN_TRACEABILITY_API_REFERENCE.md)

**Tools**:
- Grafana: http://grafana.internal/d/phase4
- Prometheus: http://prometheus.internal/graph
- Logs: http://kibana.internal (search: `service:archon-intelligence phase:4`)

**Runbooks**:
- `/ops/runbooks/phase4_deployment.md`
- `/ops/runbooks/phase4_recovery.md`
- `/ops/runbooks/phase4_performance_tuning.md`

---

**Version**: 1.0.0
**Last Updated**: 2025-10-03
**Maintainer**: Archon Intelligence Team - Operations
