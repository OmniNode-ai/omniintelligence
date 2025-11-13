#!/bin/bash

# Archon MCP Integration Test Runner
# Comprehensive script for running integration tests locally or in CI/CD

set -euo pipefail

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly COMPOSE_FILE="${PROJECT_DIR}/deployment/docker-compose.integration-tests.yml"
readonly RESULTS_DIR="${PROJECT_DIR}/test-results"
readonly LOG_FILE="${RESULTS_DIR}/test-execution.log"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Default configuration
CLEANUP_AFTER=true
VERBOSE=false
TEST_SUITE="fast"
TIMEOUT=1800
MAX_RETRIES=3
PARALLEL_JOBS=2
GENERATE_REPORT=true
OPEN_REPORT=false
CI_MODE=false

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS] [TEST_SUITE]

Archon MCP Integration Test Runner

TEST_SUITES:
    fast        Essential tests for quick validation (5-10 minutes) [default]
    full        Complete test suite (15-30 minutes)
    happy-path  Happy path tests only
    errors      Error handling tests only
    performance Performance and benchmark tests only
    consistency Data consistency validation tests only
    smoke       Minimal smoke tests for deployment validation

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -c, --ci                CI mode (quieter output, optimized for automation)
    --no-cleanup            Don't clean up test environment after completion
    --no-report             Don't generate HTML test report
    --open-report           Open test report in browser after completion
    --timeout SECONDS       Test timeout in seconds (default: 1800)
    --retries NUMBER        Maximum test retries on failure (default: 3)
    --parallel-jobs NUMBER  Number of parallel test jobs (default: 2)

EXAMPLES:
    $0                      # Run fast test suite with defaults
    $0 full                 # Run complete test suite
    $0 -v performance       # Run performance tests with verbose output
    $0 --ci --no-cleanup    # CI mode without cleanup
    $0 --timeout 3600 full  # Full suite with extended timeout

ENVIRONMENT:
    DOCKER_BUILDKIT=1       Enable BuildKit for faster builds
    COMPOSE_PARALLEL_LIMIT  Limit Docker Compose parallel operations
    PYTEST_ARGS            Additional pytest arguments

EOF
}

# Logging functions
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case "$level" in
        INFO)  echo -e "${CYAN}[INFO]${NC}  $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC}  $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        DEBUG) [[ "$VERBOSE" == "true" ]] && echo -e "${PURPLE}[DEBUG]${NC} $message" ;;
    esac

    # Also log to file if results directory exists
    if [[ -d "$RESULTS_DIR" ]]; then
        echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    fi
}

# Error handling
error_exit() {
    log ERROR "$1"
    cleanup_on_error
    exit 1
}

cleanup_on_error() {
    log WARN "Cleaning up after error..."
    if [[ "$CLEANUP_AFTER" == "true" ]]; then
        docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
    fi
}

# Signal handling
trap 'error_exit "Script interrupted"' INT TERM

# Validation functions
validate_dependencies() {
    log INFO "Validating dependencies..."

    # Check Docker
    if ! command -v docker >/dev/null 2>&1; then
        error_exit "Docker is not installed or not in PATH"
    fi

    # Check Docker Compose
    if ! docker compose version >/dev/null 2>&1; then
        error_exit "Docker Compose is not installed or not working"
    fi

    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        error_exit "Docker daemon is not running"
    fi

    # Check disk space (need at least 2GB)
    local available_space
    available_space=$(df . | tail -1 | awk '{print $4}')
    if [[ $available_space -lt 2097152 ]]; then
        error_exit "Insufficient disk space. Need at least 2GB free."
    fi

    log SUCCESS "All dependencies validated"
}

# Environment setup
setup_environment() {
    log INFO "Setting up test environment..."

    # Create results directory
    mkdir -p "$RESULTS_DIR"/{logs,reports,coverage,benchmarks}

    # Create test environment file if it doesn't exist
    if [[ ! -f "$PROJECT_DIR/.env.test" ]]; then
        log INFO "Creating test environment configuration..."
        cat > "$PROJECT_DIR/.env.test" << EOF
# Test Environment Configuration
POSTGRES_HOST=postgres-test
POSTGRES_PORT=5432
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_password
POSTGRES_DB=archon_test

QDRANT_URL=http://qdrant-test:6333
QDRANT_COLLECTION_NAME=archon_test

MEMGRAPH_URI=bolt://memgraph-test:7687
MEMGRAPH_USERNAME=
MEMGRAPH_PASSWORD=

SUPABASE_URL=http://postgres-test:5432
SUPABASE_SERVICE_KEY=test_service_key

OPENAI_API_KEY=sk-test-key-for-local-testing
INTELLIGENCE_SERVICE_PORT=18053
SEARCH_SERVICE_PORT=18055

LOG_LEVEL=INFO
ENVIRONMENT=test
EOF
    fi

    # Set Docker BuildKit for faster builds
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1

    log SUCCESS "Environment setup completed"
}

# Service management
start_services() {
    log INFO "Starting test services..."

    # Clean up any existing test environment
    docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true

    # Build and start services
    log DEBUG "Building test images..."
    docker compose -f "$COMPOSE_FILE" build --no-cache

    log DEBUG "Starting test services..."
    docker compose -f "$COMPOSE_FILE" up -d

    log SUCCESS "Test services started"
}

wait_for_services() {
    log INFO "Waiting for services to be ready..."
    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        log DEBUG "Health check attempt $attempt/$max_attempts..."

        if check_service_health; then
            log SUCCESS "All services are ready!"
            return 0
        fi

        if [[ $attempt -eq $max_attempts ]]; then
            log ERROR "Services failed to become ready within timeout"
            show_service_status
            return 1
        fi

        log DEBUG "Services not ready yet, waiting 10 seconds..."
        sleep 10
        attempt=$((attempt + 1))
    done
}

check_service_health() {
    local services=(
        "http://localhost:18181/health"
        "http://localhost:18051/health"
        "http://localhost:18053/health"
    )

    for service in "${services[@]}"; do
        if ! curl -sf "$service" >/dev/null 2>&1; then
            log DEBUG "Service not ready: $service"
            return 1
        fi
    done

    return 0
}

show_service_status() {
    log INFO "Current service status:"
    docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}" || true

    log INFO "Recent service logs:"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 || true
}

# Test execution
run_tests() {
    local test_suite="$1"
    log INFO "Running $test_suite test suite..."

    local pytest_args=""
    local test_paths=""
    local test_markers=""

    # Configure test arguments based on mode
    if [[ "$CI_MODE" == "true" ]]; then
        pytest_args="--tb=short -q --maxfail=5 --timeout=$TIMEOUT"
    elif [[ "$VERBOSE" == "true" ]]; then
        pytest_args="--tb=long -v -s --timeout=$TIMEOUT"
    else
        pytest_args="--tb=short --timeout=$TIMEOUT"
    fi

    # Add parallel execution if specified
    if [[ $PARALLEL_JOBS -gt 1 ]]; then
        pytest_args="$pytest_args -n $PARALLEL_JOBS --dist=worksteal"
    fi

    # Configure test paths and markers based on suite
    case "$test_suite" in
        "fast")
            test_paths="tests/integration/test_happy_path.py::test_complete_pipeline_single_document tests/integration/test_error_handling.py::TestServiceFailureScenarios::test_intelligence_service_unavailable tests/integration/test_performance.py::TestLatencyBenchmarks::test_document_creation_latency tests/integration/test_data_consistency.py::TestCrossServiceDataConsistency::test_document_creation_consistency"
            ;;
        "full")
            test_paths="tests/integration/"
            ;;
        "happy-path")
            test_paths="tests/integration/test_happy_path.py"
            ;;
        "errors")
            test_paths="tests/integration/test_error_handling.py"
            ;;
        "performance")
            test_paths="tests/integration/test_performance.py"
            pytest_args="$pytest_args --benchmark-json=$RESULTS_DIR/benchmarks/benchmark.json"
            ;;
        "consistency")
            test_paths="tests/integration/test_data_consistency.py"
            ;;
        "smoke")
            test_markers="-m smoke"
            test_paths="tests/integration/"
            ;;
        *)
            error_exit "Unknown test suite: $test_suite"
            ;;
    esac

    # Add coverage reporting for full runs
    if [[ "$test_suite" == "full" || "$test_suite" == "fast" ]]; then
        pytest_args="$pytest_args --cov=tests/integration --cov-report=html:$RESULTS_DIR/coverage/html --cov-report=xml:$RESULTS_DIR/coverage/coverage.xml --cov-report=term-missing"
    fi

    # Add report generation
    if [[ "$GENERATE_REPORT" == "true" ]]; then
        pytest_args="$pytest_args --junitxml=$RESULTS_DIR/reports/junit.xml --html=$RESULTS_DIR/reports/report.html --self-contained-html"
    fi

    # Add any additional pytest arguments from environment
    if [[ -n "${PYTEST_ARGS:-}" ]]; then
        pytest_args="$pytest_args $PYTEST_ARGS"
    fi

    # Execute tests with retries
    local attempt=1
    while [[ $attempt -le $MAX_RETRIES ]]; do
        log INFO "Test execution attempt $attempt/$MAX_RETRIES"

        if docker compose -f "$COMPOSE_FILE" run --rm test-runner \
            pytest $test_paths $test_markers $pytest_args; then
            log SUCCESS "Tests completed successfully!"
            return 0
        else
            local exit_code=$?
            log WARN "Test attempt $attempt failed with exit code $exit_code"

            if [[ $attempt -eq $MAX_RETRIES ]]; then
                log ERROR "All test attempts failed"
                return $exit_code
            fi

            log INFO "Retrying in 30 seconds..."
            sleep 30
            attempt=$((attempt + 1))
        fi
    done
}

# Report generation
generate_comprehensive_report() {
    if [[ "$GENERATE_REPORT" != "true" ]]; then
        return 0
    fi

    log INFO "Generating comprehensive test report..."

    local report_file="$RESULTS_DIR/reports/comprehensive-report.html"

    cat > "$report_file" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archon MCP Integration Test Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; line-height: 1.6; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .metric { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #007bff; }
        .metric-value { font-size: 24px; font-weight: bold; color: #007bff; }
        .section { background: white; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 20px; overflow: hidden; }
        .section-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #dee2e6; font-weight: bold; }
        .section-content { padding: 15px; }
        .status-success { color: #28a745; }
        .status-failure { color: #dc3545; }
        .status-warning { color: #ffc107; }
        .log-entry { font-family: monospace; background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 5px 0; }
        .artifact-link { display: inline-block; background: #007bff; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none; margin: 5px; }
        .artifact-link:hover { background: #0056b3; text-decoration: none; color: white; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 Archon MCP Integration Test Report</h1>
        <p>Comprehensive test results for the MCP document indexing pipeline</p>
        <p><strong>Generated:</strong> <span id="timestamp"></span></p>
    </div>

    <div class="summary">
        <div class="metric">
            <div class="metric-value" id="test-status">Loading...</div>
            <div>Overall Status</div>
        </div>
        <div class="metric">
            <div class="metric-value" id="test-count">-</div>
            <div>Tests Executed</div>
        </div>
        <div class="metric">
            <div class="metric-value" id="duration">-</div>
            <div>Duration</div>
        </div>
        <div class="metric">
            <div class="metric-value" id="coverage">-</div>
            <div>Coverage</div>
        </div>
    </div>

    <div class="section">
        <div class="section-header">📊 Test Results</div>
        <div class="section-content" id="test-results">
            <p>Loading test results...</p>
        </div>
    </div>

    <div class="section">
        <div class="section-header">⚡ Performance Metrics</div>
        <div class="section-content" id="performance-metrics">
            <p>Loading performance data...</p>
        </div>
    </div>

    <div class="section">
        <div class="section-header">🔗 Artifacts</div>
        <div class="section-content">
            <a href="report.html" class="artifact-link">📄 Detailed Test Report</a>
            <a href="../coverage/html/index.html" class="artifact-link">📊 Coverage Report</a>
            <a href="../benchmarks/benchmark.json" class="artifact-link">⚡ Benchmark Data</a>
            <a href="../logs/" class="artifact-link">📋 Service Logs</a>
        </div>
    </div>

    <div class="section">
        <div class="section-header">📝 Execution Log</div>
        <div class="section-content">
            <div id="execution-log">Loading execution log...</div>
        </div>
    </div>

    <script>
        // Set timestamp
        document.getElementById('timestamp').textContent = new Date().toLocaleString();

        // Load test results if available
        fetch('junit.xml')
            .then(response => response.text())
            .then(data => {
                // Parse basic metrics from JUnit XML
                const parser = new DOMParser();
                const xml = parser.parseFromString(data, 'text/xml');
                const testsuites = xml.getElementsByTagName('testsuite')[0];

                if (testsuites) {
                    const tests = testsuites.getAttribute('tests') || 0;
                    const failures = testsuites.getAttribute('failures') || 0;
                    const errors = testsuites.getAttribute('errors') || 0;
                    const time = parseFloat(testsuites.getAttribute('time') || 0);

                    document.getElementById('test-count').textContent = tests;
                    document.getElementById('duration').textContent = time.toFixed(1) + 's';

                    const failed = parseInt(failures) + parseInt(errors);
                    if (failed === 0) {
                        document.getElementById('test-status').textContent = 'PASSED';
                        document.getElementById('test-status').className = 'metric-value status-success';
                    } else {
                        document.getElementById('test-status').textContent = 'FAILED';
                        document.getElementById('test-status').className = 'metric-value status-failure';
                    }

                    // Update test results section
                    document.getElementById('test-results').innerHTML = `
                        <p><strong>Total Tests:</strong> ${tests}</p>
                        <p><strong>Passed:</strong> <span class="status-success">${tests - failed}</span></p>
                        <p><strong>Failed:</strong> <span class="status-failure">${failed}</span></p>
                        <p><strong>Duration:</strong> ${time.toFixed(1)} seconds</p>
                    `;
                }
            })
            .catch(() => {
                document.getElementById('test-results').innerHTML = '<p>Test results not available</p>';
            });

        // Load execution log
        fetch('../test-execution.log')
            .then(response => response.text())
            .then(data => {
                const lines = data.split('\n').slice(-20); // Show last 20 lines
                document.getElementById('execution-log').innerHTML = lines
                    .map(line => `<div class="log-entry">${line}</div>`)
                    .join('');
            })
            .catch(() => {
                document.getElementById('execution-log').innerHTML = '<p>Execution log not available</p>';
            });
    </script>
</body>
</html>
EOF

    log SUCCESS "Comprehensive report generated: $report_file"

    if [[ "$OPEN_REPORT" == "true" && -x "$(command -v open)" ]]; then
        log INFO "Opening report in browser..."
        open "$report_file"
    fi
}

# Cleanup
cleanup() {
    if [[ "$CLEANUP_AFTER" == "true" ]]; then
        log INFO "Cleaning up test environment..."
        docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
        log SUCCESS "Cleanup completed"
    else
        log INFO "Skipping cleanup (--no-cleanup specified)"
        log INFO "To manually clean up later, run: docker compose -f $COMPOSE_FILE down --volumes --remove-orphans"
    fi
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -c|--ci)
                CI_MODE=true
                VERBOSE=false
                shift
                ;;
            --no-cleanup)
                CLEANUP_AFTER=false
                shift
                ;;
            --no-report)
                GENERATE_REPORT=false
                shift
                ;;
            --open-report)
                OPEN_REPORT=true
                shift
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            --parallel-jobs)
                PARALLEL_JOBS="$2"
                shift 2
                ;;
            fast|full|happy-path|errors|performance|consistency|smoke)
                TEST_SUITE="$1"
                shift
                ;;
            *)
                error_exit "Unknown option: $1"
                ;;
        esac
    done

    # Main execution flow
    log INFO "Starting Archon MCP Integration Tests"
    log INFO "Test suite: $TEST_SUITE"
    log INFO "Timeout: ${TIMEOUT}s"
    log INFO "Max retries: $MAX_RETRIES"
    log INFO "Parallel jobs: $PARALLEL_JOBS"

    cd "$PROJECT_DIR"

    validate_dependencies
    setup_environment
    start_services
    wait_for_services

    if run_tests "$TEST_SUITE"; then
        log SUCCESS "All tests completed successfully!"
        generate_comprehensive_report
        cleanup
        exit 0
    else
        log ERROR "Tests failed!"

        # Collect logs for debugging
        log INFO "Collecting service logs for debugging..."
        docker compose -f "$COMPOSE_FILE" logs --no-color > "$RESULTS_DIR/logs/services.log" 2>&1 || true

        generate_comprehensive_report
        cleanup
        exit 1
    fi
}

# Execute main function with all arguments
main "$@"
