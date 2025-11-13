# Traceability Database Schema

Complete database schema for the traceability and pattern learning system.

## Schema Files

| File | Description | Dependencies |
|------|-------------|--------------|
| 001_execution_traces.sql | Master trace table | None (foundation) |
| 002_agent_routing_decisions.sql | Agent routing logs | execution_traces |
| 003_hook_executions.sql | Hook execution logs | execution_traces |
| 004_endpoint_calls.sql | Endpoint call logs | execution_traces, hook_executions |
| 005_success_patterns.sql | Learned patterns | None (requires pgvector) |
| 006_pattern_usage_log.sql | Pattern usage tracking | success_patterns, execution_traces |
| 007_agent_chaining_patterns.sql | Agent chain patterns | None |
| 008_error_patterns.sql | Error tracking | None |
| 009_indexes.sql | Performance indexes | All tables |
| 010_views.sql | Analytics views | All tables |
| 011_functions.sql | Helper functions | All tables |
| 012_rls_policies.sql | Security policies | All tables |

## Deployment

### Prerequisites

1. **PostgreSQL 15+** with extensions:
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pgvector";
   ```

2. **Supabase Project** configured with:
   - Service role key
   - Database connection string
   - RLS enabled

### Deployment Steps

#### Option 1: Deploy to Supabase (Recommended)

```bash
# Install Supabase CLI
npm install -g supabase

# Login to Supabase
supabase login

# Link to your project
supabase link --project-ref YOUR_PROJECT_REF

# Deploy schema (in order)
for file in schema/*.sql; do
    supabase db execute --file $file
done
```

#### Option 2: Deploy via psql

```bash
# Set connection string
export DATABASE_URL="postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres"

# Deploy in order
psql $DATABASE_URL -f 001_execution_traces.sql
psql $DATABASE_URL -f 002_agent_routing_decisions.sql
psql $DATABASE_URL -f 003_hook_executions.sql
psql $DATABASE_URL -f 004_endpoint_calls.sql
psql $DATABASE_URL -f 005_success_patterns.sql
psql $DATABASE_URL -f 006_pattern_usage_log.sql
psql $DATABASE_URL -f 007_agent_chaining_patterns.sql
psql $DATABASE_URL -f 008_error_patterns.sql
psql $DATABASE_URL -f 009_indexes.sql
psql $DATABASE_URL -f 010_views.sql
psql $DATABASE_URL -f 011_functions.sql
psql $DATABASE_URL -f 012_rls_policies.sql
```

#### Option 3: All-in-one deployment

```bash
# Create combined migration file
cat schema/*.sql > migrations/001_traceability_schema.sql

# Deploy
psql $DATABASE_URL -f migrations/001_traceability_schema.sql
```

### Verification

After deployment, verify the schema:

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE '%trace%' OR table_name LIKE '%pattern%';

-- Check indexes
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%';

-- Check views
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public';

-- Check functions
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public';

-- Test vector extension
SELECT * FROM pg_extension WHERE extname = 'vector';
```

## Database Statistics

| Metric | Count |
|--------|-------|
| Tables | 8 |
| Indexes | 45+ |
| Views | 5 |
| Functions | 6 |
| Triggers | 8 |
| RLS Policies | 16 |

## Performance Tuning

### Recommended PostgreSQL Settings

```sql
-- For better vector search performance
SET max_parallel_workers_per_gather = 4;
SET maintenance_work_mem = '256MB';

-- For better query performance
SET shared_buffers = '256MB';
SET effective_cache_size = '1GB';
SET work_mem = '16MB';
```

### Index Maintenance

```sql
-- Analyze tables for query planner
ANALYZE execution_traces;
ANALYZE agent_routing_decisions;
ANALYZE success_patterns;
ANALYZE pattern_usage_log;

-- Rebuild vector indexes if needed
REINDEX INDEX idx_pattern_embedding;
REINDEX INDEX idx_routing_embedding;
```

## Data Retention

### Recommended Retention Policies

```sql
-- Archive old traces (>90 days) to separate table
CREATE TABLE execution_traces_archive (LIKE execution_traces INCLUDING ALL);

-- Move old data
WITH moved AS (
    DELETE FROM execution_traces
    WHERE started_at < NOW() - INTERVAL '90 days'
    RETURNING *
)
INSERT INTO execution_traces_archive SELECT * FROM moved;

-- Clean up pattern usage logs (>180 days)
DELETE FROM pattern_usage_log WHERE used_at < NOW() - INTERVAL '180 days';

-- Clean up low-value patterns (low usage, low success rate)
DELETE FROM success_patterns
WHERE total_usage_count < 5
AND success_rate < 0.5
AND last_used_at < NOW() - INTERVAL '30 days';
```

## Monitoring Queries

```sql
-- Table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Index usage
SELECT
    schemaname, tablename, indexname, idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan ASC;

-- Recent trace activity
SELECT COUNT(*), status
FROM execution_traces
WHERE started_at > NOW() - INTERVAL '1 hour'
GROUP BY status;

-- Pattern effectiveness
SELECT * FROM pattern_effectiveness
ORDER BY success_rate DESC, total_usage_count DESC
LIMIT 10;
```

## Troubleshooting

### Common Issues

**Issue: pgvector extension not found**
```sql
-- Install pgvector
CREATE EXTENSION vector;

-- Verify installation
\dx vector
```

**Issue: Slow vector queries**
```sql
-- Rebuild vector indexes with more lists
DROP INDEX idx_pattern_embedding;
CREATE INDEX idx_pattern_embedding ON success_patterns
USING ivfflat (prompt_embedding vector_cosine_ops) WITH (lists = 200);
```

**Issue: RLS blocking queries**
```sql
-- Check RLS status
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';

-- Temporarily disable RLS for debugging (don't do in production!)
ALTER TABLE execution_traces DISABLE ROW LEVEL SECURITY;
```

## Next Steps

1. **Deploy schema** to Supabase
2. **Verify all tables** created successfully
3. **Run test queries** to validate views and functions
4. **Set up monitoring** for performance
5. **Configure backups** and retention policies

For integration with the traceability system, see:
- `/Volumes/PRO-G40/Code/Archon/docs/TRACEABILITY_AND_PATTERN_LEARNING_SYSTEM_DESIGN.md`
- `/Volumes/PRO-G40/Code/Archon/docs/PARALLEL_BUILD_QUICKSTART.md`
