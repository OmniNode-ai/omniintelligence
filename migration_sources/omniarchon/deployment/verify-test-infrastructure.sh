#!/bin/bash
# Test Infrastructure Verification Script
# Purpose: Verify docker-compose.test.yml and all test services
# Usage: ./verify-test-infrastructure.sh

set -e

echo "=================================================="
echo "Archon Test Infrastructure Verification"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the deployment directory
if [ ! -f "docker-compose.test.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.test.yml not found${NC}"
    echo "Please run this script from the deployment directory"
    exit 1
fi

echo "Step 1: Validate docker-compose.test.yml syntax..."
if docker compose -f docker-compose.test.yml config --services > /dev/null 2>&1; then
    echo -e "${GREEN}✓ docker-compose.test.yml syntax valid${NC}"
    echo ""
else
    echo -e "${RED}❌ docker-compose.test.yml has syntax errors${NC}"
    exit 1
fi

echo "Step 2: List configured services..."
SERVICES=$(docker compose -f docker-compose.test.yml config --services)
echo "$SERVICES" | while read -r service; do
    echo -e "  ${GREEN}✓${NC} $service"
done
echo ""

echo "Step 3: Check .env.test configuration..."
if [ -f ".env.test" ]; then
    echo -e "${GREEN}✓ .env.test exists${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠ .env.test not found (optional)${NC}"
    echo ""
fi

echo "Step 4: Start test infrastructure..."
docker compose -f docker-compose.test.yml --env-file .env.test up -d

echo ""
echo "Step 5: Wait for services to be healthy (max 180s)..."
timeout 180 bash -c '
    while true; do
        STATUS=$(docker compose -f docker-compose.test.yml ps --format json 2>/dev/null | jq -r ".[].Health" 2>/dev/null || echo "starting")
        if echo "$STATUS" | grep -q "healthy"; then
            HEALTHY=$(echo "$STATUS" | grep -c "healthy" || echo "0")
            TOTAL=$(echo "$STATUS" | wc -l | tr -d " ")
            echo -ne "\r  Healthy: $HEALTHY/$TOTAL services"
            if [ "$HEALTHY" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
                echo ""
                break
            fi
        fi
        sleep 2
    done
' || echo -e "${YELLOW}⚠ Timeout waiting for health (may still be starting)${NC}"

echo ""
echo "Step 6: Verify service health..."

# PostgreSQL
echo -n "  PostgreSQL (test-postgres): "
if docker exec archon-test-postgres pg_isready -U archon_test > /dev/null 2>&1; then
    echo -e "${GREEN}✓ healthy${NC}"
else
    echo -e "${RED}❌ unhealthy${NC}"
fi

# Qdrant
echo -n "  Qdrant (test-qdrant): "
if curl -sf http://localhost:6334/readyz > /dev/null 2>&1; then
    echo -e "${GREEN}✓ healthy${NC}"
else
    echo -e "${RED}❌ unhealthy${NC}"
fi

# Memgraph
echo -n "  Memgraph (test-memgraph): "
if curl -sf http://localhost:7445/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ healthy${NC}"
else
    echo -e "${RED}❌ unhealthy${NC}"
fi

# Valkey
echo -n "  Valkey (test-valkey): "
if docker exec archon-test-valkey valkey-cli --no-auth-warning -a archon_test_cache_2025 ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ healthy${NC}"
else
    echo -e "${RED}❌ unhealthy${NC}"
fi

echo ""
echo "Step 7: Verify test ports..."

# Check ports are listening
check_port() {
    local port=$1
    local service=$2
    echo -n "  Port $port ($service): "
    if nc -z localhost "$port" 2>/dev/null; then
        echo -e "${GREEN}✓ listening${NC}"
    else
        echo -e "${RED}❌ not listening${NC}"
    fi
}

check_port 5433 "PostgreSQL"
check_port 6334 "Qdrant REST"
check_port 6335 "Qdrant gRPC"
check_port 7688 "Memgraph Bolt"
check_port 7445 "Memgraph HTTP"
check_port 6380 "Valkey"

echo ""
echo "Step 8: Display service status..."
docker compose -f docker-compose.test.yml ps

echo ""
echo "=================================================="
echo "Verification Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Run tests: cd ../python && pytest tests/ -v"
echo "  2. View logs: docker compose -f docker-compose.test.yml logs -f"
echo "  3. Cleanup: docker compose -f docker-compose.test.yml down -v"
echo ""
echo "Documentation:"
echo "  - Test Infrastructure: ./TEST_INFRASTRUCTURE.md"
echo "  - Test Suite: ../python/tests/README.md"
echo "  - CI/CD Setup: ./CI_CD_SETUP_SUMMARY.md"
echo ""
