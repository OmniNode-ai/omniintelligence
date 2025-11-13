#!/bin/bash
# Run Entity ID Schema Validation Tests
#
# Purpose: Execute comprehensive entity_id format validation tests
# Reference: tests/integration/RUN_ENTITY_ID_VALIDATION_TESTS.md

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Entity ID Schema Validation Tests${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Change to repository root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Check if services are running
echo -e "${YELLOW}⏳ Checking service health...${NC}"

check_service() {
    local service_name=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ $service_name${NC}"
        return 0
    else
        echo -e "  ${RED}❌ $service_name (not responding at $url)${NC}"
        return 1
    fi
}

# Check all required services
services_ok=true
check_service "Intelligence" "http://localhost:8053/health" || services_ok=false
check_service "Bridge" "http://localhost:8054/health" || services_ok=false
check_service "Search" "http://localhost:8055/health" || services_ok=false
check_service "Qdrant" "http://localhost:6333/readyz" || services_ok=false

# Check Memgraph via docker
if docker ps | grep -q memgraph; then
    echo -e "  ${GREEN}✅ Memgraph${NC}"
else
    echo -e "  ${RED}❌ Memgraph (container not running)${NC}"
    services_ok=false
fi

echo ""

if [ "$services_ok" = false ]; then
    echo -e "${RED}⚠️  Some services are not running!${NC}"
    echo -e "${YELLOW}   Start services with: docker compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All required services are running${NC}"
echo ""

# Parse command line arguments
RUN_MODE="all"
VERBOSE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            RUN_MODE="quick"
            shift
            ;;
        --full)
            RUN_MODE="full"
            shift
            ;;
        --verbose|-v)
            VERBOSE="-vv -s"
            shift
            ;;
        --coverage)
            RUN_MODE="coverage"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--quick|--full|--coverage] [--verbose|-v]"
            exit 1
            ;;
    esac
done

# Set pytest command based on mode
case $RUN_MODE in
    quick)
        echo -e "${BLUE}🚀 Running Quick Validation (5 core tests)${NC}"
        PYTEST_CMD="pytest tests/integration/test_entity_id_schema_validation.py \
            -k 'not consistency and not orphaned' \
            -v $VERBOSE \
            --maxfail=1"
        ;;
    full)
        echo -e "${BLUE}🔬 Running Full Test Suite (all 7 tests)${NC}"
        PYTEST_CMD="pytest tests/integration/test_entity_id_schema_validation.py \
            -v $VERBOSE"
        ;;
    coverage)
        echo -e "${BLUE}📊 Running with Coverage Analysis${NC}"
        PYTEST_CMD="pytest tests/integration/test_entity_id_schema_validation.py \
            --cov=services/intelligence/storage \
            --cov-report=html:test-reports/entity-id-coverage \
            --cov-report=term-missing \
            -v $VERBOSE"
        ;;
    all)
        echo -e "${BLUE}🧪 Running All Entity ID Validation Tests${NC}"
        PYTEST_CMD="pytest tests/integration/test_entity_id_schema_validation.py -v $VERBOSE"
        ;;
esac

echo ""
echo -e "${YELLOW}Command: $PYTEST_CMD${NC}"
echo ""

# Run tests
if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✅ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

    if [ "$RUN_MODE" = "coverage" ]; then
        echo ""
        echo -e "${BLUE}📊 Coverage report generated:${NC}"
        echo -e "   file://$(pwd)/test-reports/entity-id-coverage/index.html"
    fi

    exit 0
else
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}   ❌ TESTS FAILED${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Possible issues:${NC}"
    echo "  1. PLACEHOLDER nodes exist (path-based entity_ids)"
    echo "  2. Relationships point to non-existent nodes"
    echo "  3. Entity_id format doesn't match expected pattern"
    echo ""
    echo -e "${YELLOW}Debug with:${NC}"
    echo "  - Check Memgraph: docker exec memgraph mgconsole"
    echo "  - View logs: docker logs archon-intelligence"
    echo "  - See: tests/integration/RUN_ENTITY_ID_VALIDATION_TESTS.md"
    echo ""
    exit 1
fi
