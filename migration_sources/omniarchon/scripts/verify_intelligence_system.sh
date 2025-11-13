#!/bin/bash
#
# Verify Intelligence Request System Deployment
#
# This script verifies that the intelligence request system is properly deployed
# and ready to handle requests from omniclaude manifest_injector.
#
# Usage: ./scripts/verify_intelligence_system.sh

set -e

echo "======================================================================="
echo "Intelligence Request System Deployment Verification"
echo "======================================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
FAILURES=0

check_service() {
    local service=$1
    local port=$2
    echo -n "Checking $service (port $port)... "
    if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${RED}✗ Not running${NC}"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

check_kafka_topic() {
    local topic=$1
    echo -n "Checking Kafka topic '$topic'... "
    if docker exec omninode-bridge-redpanda rpk topic list 2>/dev/null | grep -q "$topic"; then
        echo -e "${GREEN}✓ Exists${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Not found (will be auto-created)${NC}"
        return 0
    fi
}

check_handler_registration() {
    echo -n "Checking IntelligenceAdapterHandler registration... "
    if docker compose logs archon-intelligence 2>/dev/null | grep -q "Registered IntelligenceAdapterHandler"; then
        echo -e "${GREEN}✓ Registered${NC}"
        return 0
    else
        echo -e "${RED}✗ Not registered${NC}"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

echo "1. Service Health Checks"
echo "------------------------"
check_service "archon-intelligence" 8053
check_service "archon-bridge" 8054
check_service "archon-search" 8055
echo ""

echo "2. Kafka Infrastructure"
echo "-----------------------"
check_kafka_topic "dev.archon-intelligence.intelligence.code-analysis-requested.v1"
check_kafka_topic "dev.archon-intelligence.intelligence.code-analysis-completed.v1"
check_kafka_topic "dev.archon-intelligence.intelligence.code-analysis-failed.v1"
echo ""

echo "3. Handler Registration"
echo "-----------------------"
check_handler_registration
echo ""

echo "4. Backend Services"
echo "-------------------"
echo -n "Checking PostgreSQL... "
if docker compose exec -T archon-intelligence sh -c 'psql $DATABASE_URL -c "SELECT 1" > /dev/null 2>&1'; then
    echo -e "${GREEN}✓ Connected${NC}"
else
    echo -e "${YELLOW}⚠ Cannot connect (may not affect all operations)${NC}"
fi

echo -n "Checking Qdrant... "
if curl -s -f "http://localhost:6333/collections" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${YELLOW}⚠ Not running${NC}"
fi

echo -n "Checking Kafka/Redpanda... "
if docker exec omninode-bridge-redpanda rpk cluster info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    FAILURES=$((FAILURES + 1))
fi
echo ""

echo "5. Operation Handler Files"
echo "--------------------------"
for handler in pattern_extraction infrastructure_scan model_discovery schema_discovery; do
    file="services/intelligence/src/handlers/operations/${handler}_handler.py"
    echo -n "Checking $handler... "
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ Present${NC}"
    else
        echo -e "${RED}✗ Missing${NC}"
        FAILURES=$((FAILURES + 1))
    fi
done
echo ""

echo "======================================================================="
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Intelligence Request System is ready.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Test from omniclaude:"
    echo "   cd /Volumes/PRO-G40/Code/omniclaude"
    echo "   python3 claude_hooks/lib/manifest_loader.py"
    echo ""
    echo "2. Monitor logs:"
    echo "   docker compose logs -f archon-intelligence | grep 'CODE_ANALYSIS'"
    exit 0
else
    echo -e "${RED}✗ $FAILURES check(s) failed. Please review errors above.${NC}"
    echo ""
    echo "To restart services:"
    echo "   docker compose restart archon-intelligence"
    exit 1
fi
