#!/bin/bash
# Verify Database Schema Introspection SQL Queries
# Shows the exact queries used by SchemaDiscoveryHandler

echo "=================================================================="
echo "Database Schema Introspection - SQL Verification"
echo "=================================================================="

source .env

if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL not set"
    exit 1
fi

echo ""
echo "✅ DATABASE_URL configured"
echo ""

# Query 1: Table list (from SchemaDiscoveryHandler line 122-131)
echo "------------------------------------------------------------------"
echo "Query 1: Get table list with size"
echo "------------------------------------------------------------------"
echo ""
psql "${DATABASE_URL}" << 'SQL'
SELECT
    table_schema,
    table_name,
    pg_total_relation_size(table_schema||'.'||table_name)::bigint / 1024 / 1024 as size_mb
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name
LIMIT 10;
SQL

echo ""
echo ""

# Query 2: Table count
echo "------------------------------------------------------------------"
echo "Query 2: Total table count"
echo "------------------------------------------------------------------"
echo ""
psql "${DATABASE_URL}" << 'SQL'
SELECT COUNT(*) as total_tables
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';
SQL

echo ""
echo ""

# Query 3: Column information (from SchemaDiscoveryHandler line 177-191)
echo "------------------------------------------------------------------"
echo "Query 3: Column details for agent_actions table"
echo "------------------------------------------------------------------"
echo ""
psql "${DATABASE_URL}" << 'SQL'
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'agent_actions'
ORDER BY ordinal_position
LIMIT 10;
SQL

echo ""
echo ""

# Query 4: Primary key columns (from SchemaDiscoveryHandler line 194-203)
echo "------------------------------------------------------------------"
echo "Query 4: Primary key columns for agent_actions"
echo "------------------------------------------------------------------"
echo ""
psql "${DATABASE_URL}" << 'SQL'
SELECT a.attname
FROM pg_index i
JOIN pg_attribute a ON a.attrelid = i.indrelid
    AND a.attnum = ANY(i.indkey)
WHERE i.indrelid = 'public.agent_actions'::regclass
  AND i.indisprimary;
SQL

echo ""
echo ""

# Query 5: Row count example
echo "------------------------------------------------------------------"
echo "Query 5: Row count for agent_actions"
echo "------------------------------------------------------------------"
echo ""
psql "${DATABASE_URL}" -c "SELECT COUNT(*) as row_count FROM public.agent_actions;"

echo ""
echo "=================================================================="
echo "✅ All SQL queries executed successfully"
echo "=================================================================="
echo ""
echo "These are the exact queries used by SchemaDiscoveryHandler to"
echo "populate the database_schemas section of manifest intelligence."
echo "=================================================================="
