#!/bin/bash
# Direct deployment to Supabase using psql
# Automatically constructs connection string from environment variables

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_DIR="$SCRIPT_DIR/schema"

echo -e "${BLUE}=== Traceability Database Schema Deployment ===${NC}"
echo ""

# Check environment variables
if [ -z "$SUPABASE_URL" ]; then
    echo -e "${RED}Error: SUPABASE_URL not set${NC}"
    exit 1
fi

if [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo -e "${RED}Error: SUPABASE_SERVICE_KEY not set${NC}"
    exit 1
fi

# Extract database connection info from SUPABASE_URL
# Format: https://PROJECT_REF.supabase.co
PROJECT_REF=$(echo "$SUPABASE_URL" | sed -E 's|https://([^.]+)\.supabase\.co.*|\1|')

echo -e "${BLUE}Project Reference: ${PROJECT_REF}${NC}"
echo ""

# Construct database URL
# Note: Password needs to be provided separately or fetched from project settings
echo -e "${YELLOW}Please enter your Supabase database password:${NC}"
read -s DB_PASSWORD
echo ""

DATABASE_URL="postgresql://postgres:${DB_PASSWORD}@db.${PROJECT_REF}.supabase.co:5432/postgres"

# Test connection
echo -e "${BLUE}Testing connection...${NC}"
if ! psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${RED}Connection failed. Please check your password and project reference.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Connection successful${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}=== Checking Prerequisites ===${NC}"
echo -e "${BLUE}Installing required extensions...${NC}"
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>&1 | sed 's/^/  /'
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>&1 | sed 's/^/  /'
echo -e "${GREEN}✓ Extensions ready${NC}"
echo ""

# Deploy schema files
echo -e "${BLUE}=== Deploying Schema Files ===${NC}"
echo ""

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

TOTAL=${#SCHEMA_FILES[@]}
SUCCESS=0
FAILED=0

for i in "${!SCHEMA_FILES[@]}"; do
    FILE="${SCHEMA_FILES[$i]}"
    NUM=$((i + 1))

    echo -e "${BLUE}[$NUM/$TOTAL] Deploying $FILE...${NC}"

    if psql "$DATABASE_URL" -f "$SCHEMA_DIR/$FILE" >/dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Success${NC}"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${RED}  ✗ Failed${NC}"
        FAILED=$((FAILED + 1))

        # Show error details
        echo -e "${YELLOW}  Error details:${NC}"
        psql "$DATABASE_URL" -f "$SCHEMA_DIR/$FILE" 2>&1 | sed 's/^/    /'

        # Ask to continue
        echo -e "${YELLOW}  Continue with remaining files? (y/n)${NC}"
        read -r RESPONSE
        if [ "$RESPONSE" != "y" ]; then
            echo -e "${RED}Deployment aborted${NC}"
            exit 1
        fi
    fi
    echo ""
done

# Print summary
echo -e "${BLUE}=== Deployment Summary ===${NC}"
echo -e "Total Files: $TOTAL"
echo -e "${GREEN}Successful: $SUCCESS${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
else
    echo -e "${GREEN}Failed: $FAILED${NC}"
fi
echo ""

# Verification
echo -e "${BLUE}=== Verification ===${NC}"
echo ""

echo -e "${BLUE}Tables created:${NC}"
psql "$DATABASE_URL" -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND (table_name LIKE '%trace%' OR table_name LIKE '%pattern%' OR table_name LIKE '%hook%' OR table_name LIKE '%endpoint%' OR table_name LIKE '%routing%')
ORDER BY table_name;
" 2>&1 | sed 's/^/  /'

echo ""
echo -e "${BLUE}Indexes created:${NC}"
psql "$DATABASE_URL" -c "
SELECT COUNT(*) as index_count FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%';
" 2>&1 | sed 's/^/  /'

echo ""
echo -e "${BLUE}Views created:${NC}"
psql "$DATABASE_URL" -c "
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public'
ORDER BY table_name;
" 2>&1 | sed 's/^/  /'

echo ""
echo -e "${BLUE}Functions created:${NC}"
psql "$DATABASE_URL" -c "
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_type = 'FUNCTION'
ORDER BY routine_name;
" 2>&1 | sed 's/^/  /'

echo ""
echo -e "${BLUE}Extensions installed:${NC}"
psql "$DATABASE_URL" -c "
SELECT extname, extversion FROM pg_extension
WHERE extname IN ('uuid-ossp', 'vector');
" 2>&1 | sed 's/^/  /'

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}=== ✓ Deployment Complete and Verified ===${NC}"
else
    echo -e "${YELLOW}=== ⚠ Deployment Complete with Errors ===${NC}"
fi
