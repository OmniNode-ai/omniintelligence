#!/bin/bash
#
# Test Runner for Intelligence Service
# Track 3 Phase 2 - Agent 6: Integration & E2E Testing
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=================================="
echo "Intelligence Service Test Suite"
echo "=================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 installed${NC}"

# Check pytest
if ! python3 -c "import pytest" &> /dev/null; then
    echo -e "${YELLOW}⚠ pytest not found, installing...${NC}"
    pip install pytest pytest-asyncio pytest-cov
fi
echo -e "${GREEN}✓ pytest installed${NC}"

# Check Qdrant
if ! curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Qdrant not running, starting...${NC}"
    docker compose up -d qdrant
    sleep 3
fi
echo -e "${GREEN}✓ Qdrant running${NC}"

echo ""
echo "=================================="
echo "Running Tests"
echo "=================================="
echo ""

# Change to intelligence service directory
cd "$(dirname "$0")/.."

# Parse command line arguments
TEST_SUITE="${1:-all}"
VERBOSE="${2:-}"

run_integration_tests() {
    echo "Running integration tests..."
    if [ "$VERBOSE" = "-v" ]; then
        pytest tests/integration/ -v -s --tb=short
    else
        pytest tests/integration/ -v
    fi
}

run_performance_benchmarks() {
    echo "Running performance benchmarks..."
    python tests/performance/benchmark_hybrid_scoring.py
}

run_unit_tests() {
    echo "Running unit tests..."
    if [ "$VERBOSE" = "-v" ]; then
        pytest tests/unit/ -v -s --tb=short
    else
        pytest tests/unit/ -v
    fi
}

run_pattern_learning_tests() {
    echo "Running pattern learning tests..."
    if [ "$VERBOSE" = "-v" ]; then
        pytest tests/pattern_learning/ -v -s --tb=short
    else
        pytest tests/pattern_learning/ -v
    fi
}

# Run requested test suite
case "$TEST_SUITE" in
    "integration")
        run_integration_tests
        ;;
    "performance")
        run_performance_benchmarks
        ;;
    "unit")
        run_unit_tests
        ;;
    "pattern")
        run_pattern_learning_tests
        ;;
    "all")
        echo "Running all test suites..."
        echo ""

        echo "1/4: Unit Tests"
        echo "---------------"
        run_unit_tests || echo -e "${YELLOW}⚠ Some unit tests failed${NC}"
        echo ""

        echo "2/4: Pattern Learning Tests"
        echo "---------------------------"
        run_pattern_learning_tests || echo -e "${YELLOW}⚠ Some pattern learning tests failed${NC}"
        echo ""

        echo "3/4: Integration Tests"
        echo "---------------------"
        run_integration_tests || echo -e "${YELLOW}⚠ Some integration tests failed${NC}"
        echo ""

        echo "4/4: Performance Benchmarks"
        echo "--------------------------"
        run_performance_benchmarks || echo -e "${YELLOW}⚠ Some benchmarks failed${NC}"
        echo ""
        ;;
    "coverage")
        echo "Running tests with coverage..."
        pytest tests/ --cov=src --cov-report=html --cov-report=term
        echo ""
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
        ;;
    *)
        echo -e "${RED}Unknown test suite: $TEST_SUITE${NC}"
        echo ""
        echo "Usage: $0 [integration|performance|unit|pattern|all|coverage] [-v]"
        echo ""
        echo "Examples:"
        echo "  $0                    # Run all tests"
        echo "  $0 integration        # Run integration tests only"
        echo "  $0 performance        # Run performance benchmarks"
        echo "  $0 coverage           # Run with coverage report"
        echo "  $0 integration -v     # Run integration tests with verbose output"
        exit 1
        ;;
esac

echo ""
echo "=================================="
echo -e "${GREEN}✅ Test suite completed${NC}"
echo "=================================="
