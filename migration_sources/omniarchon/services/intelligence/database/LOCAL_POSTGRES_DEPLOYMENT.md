# Traceability Schema - Local PostgreSQL Deployment

**Status**: ✅ Successfully Deployed
**Database**: `omninode_bridge` on `omninode-bridge-postgres` container
**Deployment Date**: October 1, 2025

---

## ✅ Deployment Summary

Successfully deployed traceability and pattern learning schema to local PostgreSQL 15.

### Database Connection

**See**: `/Volumes/PRO-G40/Code/Archon/.env` for connection details

```env
POSTGRES_HOST=localhost (or omninode-bridge-postgres from Docker)
POSTGRES_PORT=5436 (external) / 5432 (internal)
POSTGRES_DATABASE=omninode_bridge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=${TRACEABILITY_DB_PASSWORD}  # See .env file
```

### Connection String

```bash
# Use environment variables from .env
${TRACEABILITY_DB_URL_EXTERNAL}  # From host
${TRACEABILITY_DB_URL}           # From Docker
```

---

## 📊 Deployed Objects

| Component | Expected | Deployed | Status |
|-----------|----------|----------|--------|
| Tables | 8 | 8 | ✅ |
| Indexes | 60 | 60 | ✅ |
| Views | 5 | 5 | ✅ |
| Functions | 6 | 6 | ✅ |
| Triggers | 8 | 8 | ✅ |
| Extensions | 2 | 2 | ✅ |

### Core Tables Created

1. ✅ `execution_traces` - Master trace records
2. ✅ `agent_routing_decisions` - Agent routing logs
3. ✅ `hook_executions` - Hook execution logs
4. ✅ `endpoint_calls` - API endpoint calls
5. ✅ `success_patterns` - Learned patterns (with pgvector)
6. ✅ `pattern_usage_log` - Pattern usage tracking
7. ✅ `agent_chaining_patterns` - Multi-agent workflows
8. ✅ `error_patterns` - Error tracking

### Extensions Enabled

- ✅ `vector` (pgvector) - for embeddings
- ✅ `uuid-ossp` - for UUID generation

### Analytics Views

- ✅ `pattern_effectiveness`
- ✅ `trace_summary`
- ✅ `agent_performance`
- ✅ `error_analysis`
- ✅ `dashboard_summary`

---

## ⚠️ RLS Policies Skipped

Row-Level Security (RLS) policies were **not deployed** because they require Supabase-specific roles (`service_role`, `authenticated`, `anon`) that don't exist in standard PostgreSQL.

**For local development**: This is fine - use application-level security.

**For production**: Either:
1. Create the missing roles manually
2. Use Supabase PostgreSQL
3. Modify RLS policies for your auth system

---

## 🧪 Verification Queries

### Test Schema Deployment

```sql
-- Connect to database (use TRACEABILITY_DB_URL_EXTERNAL from .env)
psql $TRACEABILITY_DB_URL_EXTERNAL

-- Verify tables (should return 8)
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
    'execution_traces', 'agent_routing_decisions', 'hook_executions',
    'endpoint_calls', 'success_patterns', 'pattern_usage_log',
    'agent_chaining_patterns', 'error_patterns'
);

-- Verify vector extension (should return 3)
SELECT vector_dims('[1,2,3]'::vector);

-- Test insert
INSERT INTO execution_traces (
    correlation_id, root_id, session_id, source, status
) VALUES (
    gen_random_uuid(), gen_random_uuid(), gen_random_uuid(),
    'local_test', 'completed'
) RETURNING id, correlation_id;
```

### Test Views

```sql
-- Dashboard summary (should work immediately)
SELECT * FROM dashboard_summary;

-- Pattern effectiveness
SELECT * FROM pattern_effectiveness LIMIT 5;

-- Agent performance
SELECT * FROM agent_performance LIMIT 5;
```

---

## 🔌 Integration with Archon Services

### Update Environment Variables

**For Archon Intelligence Service** (`/Volumes/PRO-G40/Code/Archon/.env`):

```env
# These are already set in /Volumes/PRO-G40/Code/Archon/.env
# Use those environment variables
```

### Update Docker Compose

If Archon services need access, add to `docker-compose.yml`:

```yaml
services:
  archon-intelligence:
    environment:
      - TRACEABILITY_DB_URL=${TRACEABILITY_DB_URL}  # From .env
    networks:
      - omninode-network  # Connect to omninode network
```

---

## 🚀 Next Steps

### Immediate (Week 2)

1. ✅ **Database deployed** - Schema ready
2. ⏳ **Update Archon intelligence service** - Add connection pool
3. ⏳ **Track 2: Hook System** - Implement tracing in hooks
4. ⏳ **Track 3: Pattern Learning** - Build extraction engine

### This Week

- [ ] Create database connection module in Archon
- [ ] Test trace insertion from hooks
- [ ] Implement pattern extraction background job
- [ ] Set up monitoring/metrics

### Configuration

```python
# Example: Archon intelligence service connection
import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv("TRACEABILITY_DB_URL")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

---

## 📈 Performance Notes

- **pgvector indexes** use IVFFlat with 100 lists (good for <100K vectors)
- **Partial indexes** optimize recent data queries
- **Materialized views** can be added for heavy analytics
- **Connection pooling** recommended (5-20 connections)

---

## 🛠️ Maintenance

### Data Retention

```sql
-- Archive old traces (>90 days)
DELETE FROM execution_traces
WHERE started_at < NOW() - INTERVAL '90 days';

-- Clean up old pattern usage
DELETE FROM pattern_usage_log
WHERE used_at < NOW() - INTERVAL '180 days';
```

### Index Maintenance

```sql
-- Rebuild vector indexes periodically
REINDEX INDEX idx_pattern_embedding;
REINDEX INDEX idx_routing_embedding;

-- Analyze tables for query planner
ANALYZE execution_traces;
ANALYZE success_patterns;
```

---

## 🆘 Troubleshooting

### Issue: Can't connect from host
```bash
# Use external port 5436 with env var
psql $TRACEABILITY_DB_URL_EXTERNAL
```

### Issue: Vector operations fail
```sql
-- Reinstall extension
DROP EXTENSION vector;
CREATE EXTENSION vector;
```

### Issue: Need to reset schema
```bash
# Drop all tables
docker exec omninode-bridge-postgres psql -U postgres -d omninode_bridge \
  -c "DROP TABLE IF EXISTS execution_traces, agent_routing_decisions, hook_executions, endpoint_calls, success_patterns, pattern_usage_log, agent_chaining_patterns, error_patterns CASCADE;"

# Redeploy
docker exec -i omninode-bridge-postgres psql -U postgres -d omninode_bridge \
  < /Volumes/PRO-G40/Code/Archon/services/intelligence/database/consolidated_migration.sql
```

---

## ✅ Success!

Schema successfully deployed to local PostgreSQL. Ready for:
- Track 2: Hook system integration
- Track 3: Pattern learning engine
- Track 4: Router integration
- Track 5: Analytics dashboard (already has mock data)

**Database is production-ready** for local development and testing!
