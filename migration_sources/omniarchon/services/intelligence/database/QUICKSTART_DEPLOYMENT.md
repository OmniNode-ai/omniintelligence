# 🚀 Quick Start: Deploy Traceability Schema to Supabase

**Time Required**: 5 minutes
**Difficulty**: Easy
**Status**: ✅ Ready to Deploy

---

## 📊 What You're Deploying

| Component | Count | Purpose |
|-----------|-------|---------|
| **Tables** | 8 | Execution traces, patterns, hooks, routing |
| **Indexes** | 60 | High-performance queries |
| **Views** | 5 | Analytics and dashboards |
| **Functions** | 6 | Pattern matching, stats, cleanup |
| **RLS Policies** | 18 | Row-level security |

**Total Size**: ~42 KB SQL code

---

## 🎯 Fastest Deployment (SQL Editor)

### Step 1: Enable pgvector Extension

1. Open **Supabase Dashboard**
2. Go to **Database** → **Extensions**
3. Search for **"vector"**
4. Click **Enable**

### Step 2: Deploy Schema

1. Go to **SQL Editor** → **New query**

2. Copy the consolidated migration file:
   ```bash
   # On your terminal:
   cat /Volumes/PRO-G40/Code/Archon/services/intelligence/database/consolidated_migration.sql
   ```

3. Paste into SQL Editor

4. Click **Run** (▶️)

5. Wait ~30 seconds for completion

### Step 3: Verify Deployment

Run this verification query in SQL Editor:

```sql
-- Should return 8 tables
SELECT COUNT(*) as table_count FROM information_schema.tables
WHERE table_schema = 'public'
AND (table_name LIKE '%trace%' OR table_name LIKE '%pattern%'
     OR table_name LIKE '%hook%' OR table_name LIKE '%routing%');

-- Should return: 8
```

### ✅ Expected Output

```
 table_count
-------------
           8
(1 row)
```

**Done!** Schema deployed successfully.

---

## 🔧 Alternative: Deploy via psql

### Prerequisites

```bash
# Install PostgreSQL client (if not installed)
brew install postgresql
```

### Get Database Password

1. Open **Supabase Dashboard**
2. Go to **Project Settings** → **Database**
3. Copy **Database password** (or reset if needed)

### Deploy

```bash
# Navigate to deployment directory
cd /Volumes/PRO-G40/Code/Archon/services/intelligence/database

# Run deployment script
./deploy_now.sh

# When prompted, enter your database password
```

---

## ✅ Verification Checklist

After deployment, run these queries to verify:

```sql
-- ✓ Check tables (expect 8)
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND (table_name LIKE '%trace%' OR table_name LIKE '%pattern%')
ORDER BY table_name;

-- ✓ Check indexes (expect 60)
SELECT COUNT(*) FROM pg_indexes
WHERE schemaname = 'public' AND indexname LIKE 'idx_%';

-- ✓ Check views (expect 5)
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public';

-- ✓ Check functions (expect 6)
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_type = 'FUNCTION';

-- ✓ Check extensions
SELECT extname FROM pg_extension
WHERE extname IN ('uuid-ossp', 'vector');

-- ✓ Test vector operations
SELECT vector_dims('[1,2,3]'::vector);
-- Should return: 3

-- ✓ Test sample insert
INSERT INTO execution_traces (
    correlation_id, root_id, session_id, source, status
) VALUES (
    gen_random_uuid(), gen_random_uuid(), gen_random_uuid(),
    'deployment_test', 'completed'
) RETURNING id, correlation_id, status;
```

### Expected Results Summary

| Check | Expected | Critical |
|-------|----------|----------|
| Tables | 8 | ✅ Yes |
| Indexes | 60 | ✅ Yes |
| Views | 5 | ⚠️ Nice to have |
| Functions | 6 | ⚠️ Nice to have |
| Extensions | 2 (uuid-ossp, vector) | ✅ Yes |
| Vector test | Returns 3 | ✅ Yes |
| Sample insert | Returns UUID | ✅ Yes |

---

## 🆘 Troubleshooting

### ❌ Error: "extension vector does not exist"

**Solution**: Enable pgvector in Dashboard → Database → Extensions

### ❌ Error: "relation already exists"

**Solution**: You've already deployed! Check with:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';
```

### ❌ Error: "permission denied"

**Solution**:
- Make sure you're using the **service role key** (not anon key)
- Check you're logged into the correct Supabase project

### ⚠️ Warning: "NOTICE: relation already exists, skipping"

**Status**: ✅ This is OK! Some objects already exist.

---

## 📈 Next Steps

### Immediate

1. ✅ Verify deployment (run verification queries above)
2. ✅ Test sample insert/select
3. ✅ Check Supabase logs for errors

### This Week

1. 🔄 Update intelligence service connection strings
2. 🔄 Implement traceability hooks (Track 2)
3. 🔄 Enable pattern learning (Track 3)

### Ongoing

1. 🔄 Monitor table growth
2. 🔄 Set up automated backups
3. 🔄 Configure retention policies

---

## 📞 Need Help?

**Documentation**:
- Full Deployment Report: `DEPLOYMENT_REPORT.md`
- Schema Details: `schema/README.md`
- Design Doc: `/docs/TRACEABILITY_AND_PATTERN_LEARNING_SYSTEM_DESIGN.md`

**Quick Commands**:

```bash
# View consolidated SQL file
cat /Volumes/PRO-G40/Code/Archon/services/intelligence/database/consolidated_migration.sql

# Run Python deployment helper
python3 /Volumes/PRO-G40/Code/Archon/services/intelligence/database/deploy_to_supabase.py

# Re-generate consolidated file
./create_consolidated_migration.sh
```

---

**Total Time**: ~5 minutes
**Success Rate**: High (tested and validated)
**Status**: ✅ Production Ready

🎉 **You're ready to deploy!**
