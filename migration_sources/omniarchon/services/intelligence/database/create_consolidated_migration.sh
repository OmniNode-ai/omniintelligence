#!/bin/bash
# Create a single consolidated SQL file for easy deployment via Supabase SQL Editor

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_DIR="$SCRIPT_DIR/schema"
OUTPUT_FILE="$SCRIPT_DIR/consolidated_migration.sql"

echo "Creating consolidated migration file..."

# Create header
cat > "$OUTPUT_FILE" << 'EOF'
-- ============================================================================
-- Archon Traceability & Pattern Learning Database Schema
-- Consolidated Migration File
--
-- This file contains all schema objects for the traceability system:
-- - 8 tables (execution_traces, routing_decisions, hooks, endpoints, patterns)
-- - 45+ indexes for query optimization
-- - 5 views for analytics
-- - 6 functions for pattern matching and analysis
-- - 12 RLS policies for security
--
-- Deployment Instructions:
-- 1. Open Supabase SQL Editor
-- 2. Copy and paste this entire file
-- 3. Execute the query
-- 4. Verify with: SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
--
-- Prerequisites:
-- - uuid-ossp extension (auto-installed by Supabase)
-- - pgvector extension (must be enabled in Supabase dashboard)
--
-- ============================================================================

-- Ensure required extensions are available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

EOF

# Add each schema file
SCHEMA_FILES=(
    "001_execution_traces.sql"
    "002_agent_routing_decisions.sql"
    "003_hook_executions.sql"
    "004_endpoint_calls.sql"
    "005_success_patterns.sql"
    "006_pattern_usage_log.sql"
    "007_agent_chaining_patterns.sql"
    "008_error_patterns.sql"
    "009_indexes.sql"
    "010_views.sql"
    "011_functions.sql"
    "012_rls_policies.sql"
)

for FILE in "${SCHEMA_FILES[@]}"; do
    echo "" >> "$OUTPUT_FILE"
    echo "-- ============================================================================" >> "$OUTPUT_FILE"
    echo "-- File: $FILE" >> "$OUTPUT_FILE"
    echo "-- ============================================================================" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    cat "$SCHEMA_DIR/$FILE" >> "$OUTPUT_FILE"
done

# Add footer
cat >> "$OUTPUT_FILE" << 'EOF'

-- ============================================================================
-- Deployment Complete
-- ============================================================================

-- Verification Queries
-- Run these to confirm successful deployment:

-- Tables (should show 8)
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_name LIKE '%trace%' OR table_name LIKE '%pattern%') ORDER BY table_name;

-- Indexes (should show 45+)
-- SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%';

-- Views (should show 5)
-- SELECT table_name FROM information_schema.views WHERE table_schema = 'public' ORDER BY table_name;

-- Functions (should show 6)
-- SELECT routine_name FROM information_schema.routines WHERE routine_schema = 'public' ORDER BY routine_name;

-- Extensions
-- SELECT extname, extversion FROM pg_extension WHERE extname IN ('uuid-ossp', 'vector');

EOF

echo "✓ Created: $OUTPUT_FILE"
echo ""
echo "To deploy:"
echo "1. Open Supabase Dashboard → SQL Editor"
echo "2. Create new query"
echo "3. Copy contents of: $OUTPUT_FILE"
echo "4. Paste and execute"
echo ""
echo "File size: $(wc -l < "$OUTPUT_FILE") lines"
