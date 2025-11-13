#!/bin/bash
# Quick start script for pattern integration with OmniNode Bridge

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Pattern Integration with OmniNode Bridge${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Configuration
DB_URL="${DB_URL:-postgresql://postgres:postgres@localhost:5436/omninode_bridge}"
BATCH_SIZE="${BATCH_SIZE:-100}"
PARALLEL_BATCHES="${PARALLEL_BATCHES:-3}"
MAX_PATTERNS="${MAX_PATTERNS:-}" # Empty means all patterns

# Check if services are running
echo -e "${YELLOW}[1/4] Checking service availability...${NC}"

check_service() {
    local name=$1
    local url=$2

    if curl -s -f "${url}/health" > /dev/null 2>&1; then
        echo -e "  ✓ ${name} is available"
        return 0
    else
        echo -e "  ${RED}✗ ${name} is not available at ${url}${NC}"
        return 1
    fi
}

SERVICES_OK=true
check_service "Metadata Stamping" "http://localhost:8057" || SERVICES_OK=false
check_service "OnexTree" "http://localhost:8058" || SERVICES_OK=false

if [ "$SERVICES_OK" = false ]; then
    echo
    echo -e "${RED}Error: Required services are not running${NC}"
    echo "Please start OmniNode Bridge services:"
    echo "  cd /Volumes/PRO-G40/Code/omninode_bridge"
    echo "  docker compose -f deployment/docker-compose.yml up -d"
    exit 1
fi

echo
echo -e "${YELLOW}[2/4] Checking database connection...${NC}"

# Check PostgreSQL connection
if python3 -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('${DB_URL}', timeout=5))" 2>/dev/null; then
    echo -e "  ✓ Database connection successful"
else
    echo -e "  ${RED}✗ Database connection failed${NC}"
    echo "  Please ensure PostgreSQL is running on port 5436"
    exit 1
fi

echo
echo -e "${YELLOW}[3/4] Running pattern integration...${NC}"
echo "  Configuration:"
echo "    - Database: ${DB_URL}"
echo "    - Batch size: ${BATCH_SIZE} patterns/batch"
echo "    - Parallel batches: ${PARALLEL_BATCHES}"
if [ -n "$MAX_PATTERNS" ]; then
    echo "    - Max patterns: ${MAX_PATTERNS}"
else
    echo "    - Max patterns: ALL (24,982 expected)"
fi
echo

# Run integration script
cd "$(dirname "$0")"

python3 integrate_patterns_with_bridge.py \
    --db-url "$DB_URL" \
    --batch-size "$BATCH_SIZE" \
    --parallel-batches "$PARALLEL_BATCHES" \
    ${MAX_PATTERNS:+--max-patterns "$MAX_PATTERNS"}

INTEGRATION_STATUS=$?

echo
if [ $INTEGRATION_STATUS -eq 0 ]; then
    echo -e "${GREEN}[4/4] Integration completed successfully! ✓${NC}"
    echo
    echo "Next steps:"
    echo "  1. View the integration report in the current directory"
    echo "  2. Check the log file for detailed execution trace"
    echo "  3. Query patterns via MCP tools or API endpoints"
else
    echo -e "${RED}[4/4] Integration completed with errors ✗${NC}"
    echo
    echo "Please review the log file for error details"
fi

exit $INTEGRATION_STATUS
