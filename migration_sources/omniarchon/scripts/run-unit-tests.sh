#!/bin/bash

# Unit Test Runner for Archon Document Ingestion Pipeline
# Focuses on content extraction bug detection and validation
# Usage: ./scripts/run-unit-tests.sh [options]

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_RESULTS_DIR="${PROJECT_ROOT}/test-results"
COVERAGE_DIR="${TEST_RESULTS_DIR}/coverage"

# Default options
RUN_COVERAGE=true
PARALLEL_EXECUTION=true
VERBOSE=false
FAIL_FAST=false
TEST_PATTERN="test_*.py"
MAX_WORKERS=4

# Print help
print_help() {
    echo "Unit Test Runner for Archon Document Ingestion Pipeline"
    echo "======================================================"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -v, --verbose           Enable verbose output"
    echo "  -f, --fail-fast         Stop on first failure"
    echo "  --no-coverage           Skip coverage reporting"
    echo "  --no-parallel           Disable parallel execution"
    echo "  --workers N             Set number of parallel workers (default: 4)"
    echo "  --pattern PATTERN       Test file pattern (default: test_*.py)"
    echo "  --subsystem SUBSYSTEM   Run specific subsystem tests only"
    echo "  --content-validation    Run only content extraction validation tests"
    echo ""
    echo "Subsystems:"
    echo "  bridge                  Bridge Service content extraction tests"
    echo "  intelligence            Intelligence Service document processing tests"
    echo "  search                  Search Service vectorization tests"
    echo "  rag                     RAG Service document retrieval tests"
    echo "  mcp                     MCP Server document creation tests"
    echo "  orchestration           Orchestration Service coordination tests"
    echo "  mapping                 Entity Mapper extraction tests"
    echo "  connectors              Memgraph Connector knowledge graph tests"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all unit tests with coverage"
    echo "  $0 --subsystem bridge                # Run only Bridge Service tests"
    echo "  $0 --content-validation              # Run only content validation tests"
    echo "  $0 --verbose --fail-fast             # Run with verbose output, stop on first failure"
    echo "  $0 --no-coverage --workers 2         # Run without coverage, use 2 workers"
}

# Parse command line arguments
parse_args() {
    SUBSYSTEM=""
    CONTENT_VALIDATION_ONLY=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_help
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--fail-fast)
                FAIL_FAST=true
                shift
                ;;
            --no-coverage)
                RUN_COVERAGE=false
                shift
                ;;
            --no-parallel)
                PARALLEL_EXECUTION=false
                shift
                ;;
            --workers)
                MAX_WORKERS="$2"
                shift 2
                ;;
            --pattern)
                TEST_PATTERN="$2"
                shift 2
                ;;
            --subsystem)
                SUBSYSTEM="$2"
                shift 2
                ;;
            --content-validation)
                CONTENT_VALIDATION_ONLY=true
                shift
                ;;
            *)
                echo -e "${RED}Error: Unknown option $1${NC}" >&2
                print_help
                exit 1
                ;;
        esac
    done
}

# Setup test environment
setup_test_environment() {
    echo -e "${BLUE}🔧 Setting up test environment...${NC}"

    # Create test results directories
    mkdir -p "$TEST_RESULTS_DIR"/{coverage,reports,logs}

    # Set environment variables for testing
    export PYTHONPATH="${PROJECT_ROOT}/services:${PROJECT_ROOT}/tests:${PYTHONPATH:-}"
    export ARCHON_TEST_MODE=true
    export LOG_LEVEL=WARNING  # Reduce noise during testing

    # Mock external services for unit tests
    export SUPABASE_URL="http://localhost:54321"
    export SUPABASE_SERVICE_KEY="test_service_key"
    export QDRANT_URL="http://localhost:6333"
    export MEMGRAPH_URI="bolt://localhost:7687"
    export OPENAI_API_KEY="sk-test-key"

    echo -e "${GREEN}✅ Test environment configured${NC}"
}

# Build pytest command with options
build_pytest_command() {
    local pytest_cmd="python -m pytest"
    local test_path="tests/"

    # Determine test path based on subsystem
    if [[ -n "$SUBSYSTEM" ]]; then
        case "$SUBSYSTEM" in
            bridge)
                test_path="tests/bridge/"
                ;;
            intelligence)
                test_path="tests/intelligence/"
                ;;
            search)
                test_path="tests/search/"
                ;;
            rag)
                test_path="tests/rag/"
                ;;
            mcp)
                test_path="tests/mcp/"
                ;;
            orchestration)
                test_path="tests/orchestration/"
                ;;
            mapping)
                test_path="tests/mapping/"
                ;;
            connectors)
                test_path="tests/connectors/"
                ;;
            *)
                echo -e "${RED}Error: Unknown subsystem '$SUBSYSTEM'${NC}" >&2
                exit 1
                ;;
        esac
    fi

    # Content validation specific tests
    if [[ "$CONTENT_VALIDATION_ONLY" == true ]]; then
        pytest_cmd="$pytest_cmd -k \"test_standardized_document_content\" $test_path"
    else
        pytest_cmd="$pytest_cmd $test_path"
    fi

    # Add pytest options
    pytest_cmd="$pytest_cmd --tb=short"

    # Verbose output
    if [[ "$VERBOSE" == true ]]; then
        pytest_cmd="$pytest_cmd -v"
    else
        pytest_cmd="$pytest_cmd -q"
    fi

    # Fail fast
    if [[ "$FAIL_FAST" == true ]]; then
        pytest_cmd="$pytest_cmd --maxfail=1"
    else
        pytest_cmd="$pytest_cmd --maxfail=5"
    fi

    # Parallel execution
    if [[ "$PARALLEL_EXECUTION" == true ]] && [[ "$SUBSYSTEM" == "" ]]; then
        pytest_cmd="$pytest_cmd -n $MAX_WORKERS"
    fi

    # Coverage options
    if [[ "$RUN_COVERAGE" == true ]]; then
        pytest_cmd="$pytest_cmd --cov=services"
        pytest_cmd="$pytest_cmd --cov-report=html:${COVERAGE_DIR}/html"
        pytest_cmd="$pytest_cmd --cov-report=xml:${COVERAGE_DIR}/coverage.xml"
        pytest_cmd="$pytest_cmd --cov-report=term-missing"
        pytest_cmd="$pytest_cmd --cov-branch"
    fi

    # Additional reporting
    pytest_cmd="$pytest_cmd --junitxml=${TEST_RESULTS_DIR}/reports/junit.xml"
    pytest_cmd="$pytest_cmd --html=${TEST_RESULTS_DIR}/reports/report.html"
    pytest_cmd="$pytest_cmd --self-contained-html"

    # Performance benchmarks for specific tests
    if [[ "$SUBSYSTEM" == "intelligence" ]] || [[ "$SUBSYSTEM" == "search" ]] || [[ "$SUBSYSTEM" == "" ]]; then
        pytest_cmd="$pytest_cmd --benchmark-json=${TEST_RESULTS_DIR}/benchmarks.json"
        pytest_cmd="$pytest_cmd --benchmark-autosave"
    fi

    echo "$pytest_cmd"
}

# Run content extraction validation
validate_content_extraction() {
    echo -e "${PURPLE}🔍 Running content extraction validation tests...${NC}"

    # Run specific validation tests that check for the 26-38 character truncation bug
    local validation_cmd="python -m pytest -v"
    validation_cmd="$validation_cmd -k \"test_standardized_document_content or test_content_not_truncated\""
    validation_cmd="$validation_cmd tests/"
    validation_cmd="$validation_cmd --tb=short"
    validation_cmd="$validation_cmd --maxfail=1"

    echo -e "${BLUE}Running: $validation_cmd${NC}"

    if eval "$validation_cmd"; then
        echo -e "${GREEN}✅ Content extraction validation PASSED${NC}"
        echo -e "${GREEN}   All tests successfully validate content length > 38 characters${NC}"
        return 0
    else
        echo -e "${RED}❌ Content extraction validation FAILED${NC}"
        echo -e "${RED}   Content truncation bug may still be present${NC}"
        return 1
    fi
}

# Run main test suite
run_tests() {
    echo -e "${BLUE}🧪 Running unit tests for Archon document ingestion pipeline...${NC}"

    local pytest_cmd
    pytest_cmd=$(build_pytest_command)

    echo -e "${BLUE}Command: $pytest_cmd${NC}"
    echo ""

    # Change to project root
    cd "$PROJECT_ROOT"

    # Start timer
    local start_time
    start_time=$(date +%s)

    # Run tests
    if eval "$pytest_cmd"; then
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))

        echo ""
        echo -e "${GREEN}✅ All tests passed successfully!${NC}"
        echo -e "${GREEN}   Duration: ${duration}s${NC}"

        # Run additional content validation if not already done
        if [[ "$CONTENT_VALIDATION_ONLY" != true ]]; then
            echo ""
            validate_content_extraction
        fi

        return 0
    else
        local end_time
        end_time=$(date +%s)
        local duration=$((end_time - start_time))

        echo ""
        echo -e "${RED}❌ Some tests failed${NC}"
        echo -e "${RED}   Duration: ${duration}s${NC}"

        return 1
    fi
}

# Generate test report
generate_report() {
    echo -e "${BLUE}📊 Generating test report...${NC}"

    local report_file="${TEST_RESULTS_DIR}/summary.txt"

    cat > "$report_file" << EOF
Archon Unit Test Report
======================
Generated: $(date)
Test Pattern: $TEST_PATTERN
Subsystem: ${SUBSYSTEM:-"All"}
Content Validation Only: $CONTENT_VALIDATION_ONLY

Test Results:
- HTML Report: test-results/reports/report.html
- JUnit XML: test-results/reports/junit.xml
- Coverage HTML: test-results/coverage/html/index.html
- Coverage XML: test-results/coverage/coverage.xml

Key Focus:
This test suite specifically validates that the content extraction bug
(where only 26-38 characters were extracted instead of full content)
has been fixed across all pipeline components.

All tests use a standardized test document with 577 characters to
ensure content truncation is detected if it occurs.
EOF

    echo -e "${GREEN}✅ Test report generated: $report_file${NC}"

    # Show coverage summary if available
    if [[ "$RUN_COVERAGE" == true ]] && [[ -f "${COVERAGE_DIR}/coverage.xml" ]]; then
        echo -e "${BLUE}📊 Coverage Summary:${NC}"
        if command -v coverage &> /dev/null; then
            coverage report --data-file="${COVERAGE_DIR}/.coverage" 2>/dev/null || echo "Coverage data not available in expected format"
        else
            echo "Install 'coverage' package to see detailed coverage summary"
        fi
    fi
}

# Main execution
main() {
    echo -e "${PURPLE}Archon Unit Test Runner${NC}"
    echo -e "${PURPLE}======================${NC}"
    echo ""

    parse_args "$@"
    setup_test_environment

    if run_tests; then
        generate_report
        echo ""
        echo -e "${GREEN}🎉 Unit test execution completed successfully!${NC}"
        echo -e "${BLUE}📁 Results available in: $TEST_RESULTS_DIR${NC}"
        exit 0
    else
        generate_report
        echo ""
        echo -e "${RED}💥 Unit test execution failed!${NC}"
        echo -e "${BLUE}📁 Results and logs available in: $TEST_RESULTS_DIR${NC}"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
