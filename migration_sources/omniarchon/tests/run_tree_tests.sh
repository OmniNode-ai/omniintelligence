#!/bin/bash
# Run Tree Building and Orphan Prevention Tests
# Created: 2025-11-10

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}Tree Building & Orphan Prevention Test Suite${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Install with: pip install pytest pytest-asyncio${NC}"
    exit 1
fi

# Check if in project root
if [ ! -f "scripts/bulk_ingest_repository.py" ]; then
    echo -e "${RED}❌ Must run from project root directory${NC}"
    exit 1
fi

# Set Python path
export PYTHONPATH="${PWD}:${PWD}/services/intelligence/src:${PYTHONPATH}"

# Unit tests
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"
echo -e "${YELLOW}Running Unit Tests (tree building logic)${NC}"
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"
pytest tests/unit/scripts/test_tree_building.py -v --tb=short || {
    echo -e "${RED}❌ Unit tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✅ Unit tests passed${NC}"
echo ""

# Integration tests (require Memgraph)
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"
echo -e "${YELLOW}Running Integration Tests (orphan prevention)${NC}"
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"

# Check if Memgraph is running
if ! nc -z localhost 7687 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Memgraph not running on localhost:7687${NC}"
    echo -e "${YELLOW}Skipping integration tests (require Memgraph)${NC}"
else
    pytest tests/integration/test_orphan_prevention.py -v --tb=short -m integration || {
        echo -e "${RED}❌ Integration tests failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ Integration tests passed${NC}"
fi
echo ""

# End-to-end tests (require Memgraph)
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"
echo -e "${YELLOW}Running E2E Tests (full ingestion pipeline)${NC}"
echo -e "${YELLOW}──────────────────────────────────────────────────────────────────────${NC}"

if ! nc -z localhost 7687 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Memgraph not running on localhost:7687${NC}"
    echo -e "${YELLOW}Skipping E2E tests (require Memgraph)${NC}"
else
    pytest tests/e2e/test_ingestion_pipeline.py -v --tb=short -m e2e || {
        echo -e "${RED}❌ E2E tests failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ E2E tests passed${NC}"
fi
echo ""

# Coverage report
echo -e "${BLUE}──────────────────────────────────────────────────────────────────────${NC}"
echo -e "${BLUE}Generating Coverage Report${NC}"
echo -e "${BLUE}──────────────────────────────────────────────────────────────────────${NC}"

pytest tests/unit/scripts/test_tree_building.py \
    tests/integration/test_orphan_prevention.py \
    tests/e2e/test_ingestion_pipeline.py \
    --cov=scripts.bulk_ingest_repository \
    --cov=services.directory_indexer \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/tree_tests \
    -v || {
    echo -e "${YELLOW}⚠️  Coverage report generation failed (non-fatal)${NC}"
}

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}✅ All tests completed successfully!${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
echo -e "Coverage report: ${BLUE}htmlcov/tree_tests/index.html${NC}"
echo ""
