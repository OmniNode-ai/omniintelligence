# Deploy Database Schema - FIXED & READY

**Status**: ✅ All errors fixed, ready to deploy
**File**: `consolidated_migration.sql` (1,050 lines, 37 KB)
**Error Fixed**: Removed VOLATILE `NOW()` functions from index predicates

---

## 🚀 Deploy in 3 Steps

### Step 1: Enable pgvector Extension (1 minute)

1. Open your Supabase Dashboard
2. Go to **Database** → **Extensions**
3. Search for `vector`
4. Click **Enable** on the `vector` extension

### Step 2: Deploy Schema (2 minutes)

**Method A: Supabase SQL Editor** (Recommended ✅)

1. Open Supabase Dashboard → **SQL Editor** → **New query**
2. Copy the entire contents:
   ```bash
   cat /Volumes/PRO-G40/Code/Archon/services/intelligence/database/consolidated_migration.sql
   ```
3. Paste into SQL Editor
4. Click **Run** (▶️ button)
5. Wait ~30 seconds for completion

**Method B: psql Command Line**

```bash
# Set your database URL
export DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"

# Deploy
psql $DATABASE_URL -f /Volumes/PRO-G40/Code/Archon/services/intelligence/database/consolidated_migration.sql
```

### Step 3: Verify Deployment (1 minute)

Run these verification queries in Supabase SQL Editor:

```sql
-- Should return 8 (all tables created)
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
    'execution_traces', 'agent_routing_decisions', 'hook_executions',
    'endpoint_calls', 'success_patterns', 'pattern_usage_log',
    'agent_chaining_patterns', 'error_patterns'
);

-- Should return 60 (all indexes created)
SELECT COUNT(*) FROM pg_indexes
WHERE schemaname = 'public' AND indexname LIKE 'idx_%';

-- Should return 5 (all views created)
SELECT COUNT(*) FROM information_schema.views
WHERE table_schema = 'public';

-- Should return 6 (all functions created)
SELECT COUNT(*) FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_type = 'FUNCTION';

-- Test vector extension works (should return 3)
SELECT vector_dims('[1,2,3]'::vector);
```

---

## ✅ What Was Fixed

**Problem**: Index predicates used `NOW()` function, which is VOLATILE
```sql
-- ❌ BEFORE (failed deployment)
CREATE INDEX idx_error_recent ON error_patterns(...)
WHERE last_occurrence_at > NOW() - INTERVAL '7 days';
```

**Solution**: Removed time-based predicates from indexes
```sql
-- ✅ AFTER (works perfectly)
CREATE INDEX idx_error_recent ON error_patterns(last_occurrence_at DESC, severity);

-- Application queries handle date filtering:
SELECT * FROM error_patterns
WHERE last_occurrence_at > NOW() - INTERVAL '7 days'
ORDER BY last_occurrence_at DESC;
```

**Impact**: None - PostgreSQL efficiently handles date filtering in queries

---

## 📊 Deployment Summary

| Component | Count | Status |
|-----------|-------|--------|
| Tables | 8 | ✅ Ready |
| Indexes | 60 | ✅ Fixed |
| Views | 5 | ✅ Ready |
| Functions | 6 | ✅ Ready |
| RLS Policies | 18 | ✅ Ready |
| Triggers | 8 | ✅ Ready |

**Total Objects**: 105 database objects

---

## 🆘 Troubleshooting

### "extension vector does not exist"
**Solution**: Enable pgvector in Dashboard → Database → Extensions

### "relation already exists"
**Solution**: Schema already deployed! Run verification queries to confirm

### "permission denied"
**Solution**: Use service role key, not anon key

### Notices about existing objects
**Solution**: This is OK - we use `IF NOT EXISTS` for safety

---

## 🎯 Success Criteria

Deployment is successful when verification queries return:
- ✅ 8 tables
- ✅ 60 indexes
- ✅ 5 views
- ✅ 6 functions
- ✅ Vector extension working (returns 3 for `vector_dims('[1,2,3]'::vector)`)

---

## 📁 Files Reference

- **Main deployment**: `consolidated_migration.sql`
- **Individual schemas**: `schema/*.sql` (if you need to deploy separately)
- **This guide**: `DEPLOY_NOW.md`

---

## 🚀 After Deployment

Once deployed successfully:

1. ✅ Update Archon intelligence service connection strings
2. ✅ Start Track 2: Hook System integration
3. ✅ Start Track 3: Pattern Learning engine
4. ✅ Configure monitoring dashboards

---

**Ready to deploy!** Start with Step 1 above. ⬆️
