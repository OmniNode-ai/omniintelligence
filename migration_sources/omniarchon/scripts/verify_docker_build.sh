#!/usr/bin/env bash
#
# Post-Deployment Smoke Test Runner
#
# Runs critical smoke tests after Docker rebuild to verify services are functional.
# This script MUST pass before starting any ingestion or production deployment.
#
# Usage:
#   ./scripts/verify_docker_build.sh           # Run all smoke tests
#   ./scripts/verify_docker_build.sh --quick   # Quick validation (essential tests only)
#   ./scripts/verify_docker_build.sh --verbose # Detailed output
#
# Exit Codes:
#   0 - All smoke tests passed (safe to deploy)
#   1 - One or more smoke tests failed (DO NOT DEPLOY)
#   2 - Script error or invalid usage

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_FILE="${PROJECT_ROOT}/tests/integration/test_post_deployment_smoke.py"
LOG_FILE="${PROJECT_ROOT}/logs/smoke_test_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if it doesn't exist
mkdir -p "${PROJECT_ROOT}/logs"

# Parse arguments
QUICK_MODE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Run post-deployment smoke tests to verify Docker services."
            echo ""
            echo "Options:"
            echo "  --quick      Run only critical tests (faster)"
            echo "  --verbose    Show detailed test output"
            echo "  --help       Show this help message"
            echo ""
            echo "Exit Codes:"
            echo "  0 - All tests passed (safe to deploy)"
            echo "  1 - Tests failed (DO NOT DEPLOY)"
            echo "  2 - Script error"
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 2
            ;;
    esac
done

# Print header
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          POST-DEPLOYMENT SMOKE TEST VALIDATION                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "Log file:  ${LOG_FILE}"
echo ""

# Check if test file exists
if [[ ! -f "${TEST_FILE}" ]]; then
    echo -e "${RED}❌ Test file not found: ${TEST_FILE}${NC}"
    exit 2
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Please install: pip install pytest pytest-asyncio${NC}"
    exit 2
fi

# Load environment variables
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    echo -e "${GREEN}✓${NC} Loading environment from .env"
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
else
    echo -e "${YELLOW}⚠${NC}  No .env file found, using defaults"
fi

# Verify critical services are running
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Pre-Flight Checks${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

INTELLIGENCE_URL="${INTELLIGENCE_URL:-http://localhost:8053}"
BRIDGE_URL="${BRIDGE_URL:-http://localhost:8054}"
SEARCH_URL="${SEARCH_URL:-http://localhost:8055}"

echo -n "Checking archon-intelligence (8053)... "
if curl -sf "${INTELLIGENCE_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Online${NC}"
else
    echo -e "${RED}✗ Offline${NC}"
    echo -e "${RED}❌ Intelligence service not responding. Start Docker services first.${NC}"
    echo "   Command: docker compose up -d"
    exit 1
fi

echo -n "Checking archon-bridge (8054)...       "
if curl -sf "${BRIDGE_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Online${NC}"
else
    echo -e "${RED}✗ Offline${NC}"
    echo -e "${RED}❌ Bridge service not responding. Start Docker services first.${NC}"
    exit 1
fi

echo -n "Checking archon-search (8055)...       "
if curl -sf "${SEARCH_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Online${NC}"
else
    echo -e "${RED}✗ Offline${NC}"
    echo -e "${RED}❌ Search service not responding. Start Docker services first.${NC}"
    exit 1
fi

# Build pytest command
PYTEST_ARGS=(
    "${TEST_FILE}"
    "-v"
    "-m" "smoke"
    "--tb=short"
    "--maxfail=3"
    "--timeout=60"
)

if [[ "${QUICK_MODE}" == "true" ]]; then
    # Quick mode: only critical tests
    PYTEST_ARGS+=("-m" "critical")
    echo ""
    echo -e "${YELLOW}ℹ  Quick mode: Running only critical tests${NC}"
fi

if [[ "${VERBOSE}" == "true" ]]; then
    PYTEST_ARGS+=("-vv" "--tb=long")
fi

# Add logging
PYTEST_ARGS+=("--log-file=${LOG_FILE}")

# Run smoke tests
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Running Smoke Tests${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Run tests and capture exit code
set +e
if [[ "${VERBOSE}" == "true" ]]; then
    pytest "${PYTEST_ARGS[@]}" 2>&1 | tee -a "${LOG_FILE}"
else
    pytest "${PYTEST_ARGS[@]}" 2>&1 | tee -a "${LOG_FILE}" | grep -E '(PASSED|FAILED|ERROR|test_.*|━━━|═══|✓|✗|❌|✅|⚠️)'
fi
EXIT_CODE=$?
set -e

# Print results
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Results${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo -e "${GREEN}✅ ALL SMOKE TESTS PASSED${NC}"
    echo ""
    echo -e "   Status: ${GREEN}SAFE TO DEPLOY${NC}"
    echo "   Services are healthy and functional"
    echo "   You can proceed with:"
    echo "     - Repository ingestion (bulk_ingest_repository.py)"
    echo "     - Production deployment"
    echo ""
    echo -e "   Log: ${LOG_FILE}"
    exit 0
else
    echo -e "${RED}❌ SMOKE TESTS FAILED${NC}"
    echo ""
    echo -e "   Status: ${RED}DO NOT DEPLOY${NC}"
    echo "   One or more critical tests failed"
    echo ""
    echo "   Action Required:"
    echo "     1. Review test failures above"
    echo "     2. Check service logs:"
    echo "        docker compose logs archon-intelligence"
    echo "        docker compose logs archon-bridge"
    echo "        docker compose logs archon-search"
    echo "     3. Fix issues and rebuild:"
    echo "        docker compose down"
    echo "        docker compose build"
    echo "        docker compose up -d"
    echo "     4. Re-run smoke tests:"
    echo "        ./scripts/verify_docker_build.sh"
    echo ""
    echo -e "   Log: ${LOG_FILE}"
    exit 1
fi
