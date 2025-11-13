#!/bin/bash
# Verify Real Integration Test Setup
# Run this script to check if everything is properly configured

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Real Integration Test Setup Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check functions
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} Found: $1"
        return 0
    else
        echo -e "${RED}✗${NC} Missing: $1"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Found directory: $1"
        return 0
    else
        echo -e "${RED}✗${NC} Missing directory: $1"
        return 1
    fi
}

check_service() {
    if nc -z localhost $2 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $1 (port $2) is accessible"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $1 (port $2) is not accessible"
        return 1
    fi
}

# Track results
ERRORS=0

echo "1. Checking Core Files"
echo "───────────────────────────────────────────────────────"
check_file "python/pytest.ini" || ((ERRORS++))
check_file "python/tests/conftest.py" || ((ERRORS++))
check_file "python/tests/fixtures/real_integration.py" || ((ERRORS++))
check_file "python/tests/utils/test_data_manager.py" || ((ERRORS++))
echo ""

echo "2. Checking Test Suites"
echo "───────────────────────────────────────────────────────"
check_dir "python/tests/real_integration" || ((ERRORS++))
check_file "python/tests/real_integration/test_kafka_event_flow.py" || ((ERRORS++))
check_file "python/tests/real_integration/test_qdrant_vector_search.py" || ((ERRORS++))
check_file "python/tests/real_integration/test_memgraph_knowledge_graph.py" || ((ERRORS++))
check_file "python/tests/real_integration/test_multi_service_orchestration.py" || ((ERRORS++))
echo ""

echo "3. Checking Documentation"
echo "───────────────────────────────────────────────────────"
check_file "python/docs/REAL_INTEGRATION_TESTS.md" || ((ERRORS++))
check_file "python/docs/REAL_INTEGRATION_TESTS_SUMMARY.md" || ((ERRORS++))
echo ""

echo "4. Checking Docker Compose"
echo "───────────────────────────────────────────────────────"
check_file "deployment/docker-compose.test.yml" || ((ERRORS++))
echo ""

echo "5. Checking Services (Optional)"
echo "───────────────────────────────────────────────────────"
echo "Note: These are optional - services can be started later"
check_service "Qdrant" 6334
check_service "Memgraph" 7688
check_service "Kafka/Redpanda" 9092
echo ""

echo "6. Testing pytest Configuration"
echo "───────────────────────────────────────────────────────"
cd python
if poetry run pytest --help | grep -q "real-integration"; then
    echo -e "${GREEN}✓${NC} pytest --real-integration flag is available"
else
    echo -e "${RED}✗${NC} pytest --real-integration flag not found"
    ((ERRORS++))
fi

if poetry run pytest --markers | grep -q "real_integration"; then
    echo -e "${GREEN}✓${NC} real_integration marker is configured"
else
    echo -e "${RED}✗${NC} real_integration marker not found"
    ((ERRORS++))
fi
cd ..
echo ""

echo "7. Counting Tests"
echo "───────────────────────────────────────────────────────"
cd python
TEST_COUNT=$(poetry run pytest --collect-only --real-integration tests/real_integration/ 2>/dev/null | grep "<Function" | wc -l | tr -d ' ')
if [ "$TEST_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $TEST_COUNT real integration tests"
else
    echo -e "${RED}✗${NC} No tests found"
    ((ERRORS++))
fi
cd ..
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ Setup verification complete - all checks passed!${NC}"
    echo ""
    echo "To run tests:"
    echo "  1. Start services: docker compose -f deployment/docker-compose.test.yml up -d"
    echo "  2. Run tests: cd python && pytest --real-integration tests/real_integration/ -v"
else
    echo -e "${RED}✗ Setup verification found $ERRORS issue(s)${NC}"
    echo ""
    echo "Please fix the issues above and run this script again."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

exit $ERRORS
