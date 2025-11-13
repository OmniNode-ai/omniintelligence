#!/bin/bash
# Test Runner for Pattern Learning Tests
# AI-Generated with agent-testing methodology
# Usage: ./run_tests.sh [category] [options]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COVERAGE_TARGET=95

# Print banner
echo -e "${GREEN}"
echo "========================================="
echo "  Pattern Learning Test Suite"
echo "  Coverage Target: ${COVERAGE_TARGET}%"
echo "========================================="
echo -e "${NC}"

# Function to run tests
run_tests() {
    local category=$1
    local extra_args="${@:2}"

    echo -e "${YELLOW}Running ${category} tests...${NC}"

    if [ "$category" == "all" ]; then
        pytest "$TEST_DIR" \
            --cov=services/intelligence/src/services/pattern_learning \
            --cov-report=html \
            --cov-report=term-missing \
            --cov-report=json \
            --cov-fail-under=$COVERAGE_TARGET \
            -v \
            $extra_args
    else
        pytest "$TEST_DIR/${category}" \
            -v \
            $extra_args
    fi
}

# Function to run coverage report
run_coverage() {
    echo -e "${YELLOW}Generating coverage report...${NC}"

    pytest "$TEST_DIR" \
        --cov=services/intelligence/src/services/pattern_learning \
        --cov-report=html \
        --cov-report=term-missing \
        --cov-report=json \
        --cov-fail-under=$COVERAGE_TARGET \
        --quiet

    echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"

    # Print coverage summary
    if [ -f coverage.json ]; then
        python3 << EOF
import json
with open('coverage.json') as f:
    data = json.load(f)
    total_coverage = data['totals']['percent_covered']
    print(f"\n{'='*50}")
    print(f"Total Coverage: {total_coverage:.2f}%")
    print(f"Target: ${COVERAGE_TARGET}%")
    if total_coverage >= $COVERAGE_TARGET:
        print("✓ Coverage target MET")
    else:
        print(f"✗ Coverage target MISSED by {$COVERAGE_TARGET - total_coverage:.2f}%")
    print(f"{'='*50}\n")
EOF
    fi
}

# Function to run performance benchmarks
run_benchmarks() {
    echo -e "${YELLOW}Running performance benchmarks...${NC}"

    pytest "$TEST_DIR/performance" \
        -m performance \
        -v \
        --tb=short \
        --durations=0

    echo -e "${GREEN}Performance benchmarks complete${NC}"
}

# Function to run quick tests (skip slow tests)
run_quick() {
    echo -e "${YELLOW}Running quick tests (excluding slow tests)...${NC}"

    pytest "$TEST_DIR" \
        -m "not slow" \
        -v \
        --tb=short
}

# Main command handling
case "${1:-all}" in
    unit)
        run_tests "unit" "${@:2}"
        ;;
    integration)
        run_tests "integration" "${@:2}"
        ;;
    performance)
        run_benchmarks
        ;;
    edge_cases)
        run_tests "edge_cases" "${@:2}"
        ;;
    coverage)
        run_coverage
        ;;
    quick)
        run_quick
        ;;
    all)
        run_tests "all" "${@:2}"
        ;;
    *)
        echo "Usage: $0 {all|unit|integration|performance|edge_cases|coverage|quick} [pytest-options]"
        echo ""
        echo "Examples:"
        echo "  $0 all                    # Run all tests with coverage"
        echo "  $0 unit                   # Run unit tests only"
        echo "  $0 integration            # Run integration tests"
        echo "  $0 performance            # Run performance benchmarks"
        echo "  $0 edge_cases             # Run edge case tests"
        echo "  $0 coverage               # Generate coverage report"
        echo "  $0 quick                  # Run quick tests (skip slow)"
        echo "  $0 all -k test_specific   # Run specific test pattern"
        exit 1
        ;;
esac

# Exit with test status
exit $?
