#!/bin/bash
#
# Test Runner Script - Ensures tests always use the virtual environment
#
# Usage:
#   ./run_tests.sh                          # Run all tests with coverage
#   ./run_tests.sh tests/test_*.py          # Run specific files with coverage
#   ./run_tests.sh -v --cov=src             # Pass custom pytest options
#   ./run_tests.sh --no-cov                 # Run without coverage
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

# Check if virtual environment exists
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo -e "${RED}Error: Virtual environment not found at .venv/${NC}"
    echo "Please create virtual environment first:"
    echo "  uv venv"
    echo "  uv sync --all-groups"
    exit 1
fi

# Check if dependencies are installed
if ! "$VENV_PYTHON" -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Warning: pytest not found in virtual environment${NC}"
    echo "Installing dependencies..."
    uv sync --all-groups
fi

# Verify critical dependencies
echo -e "${GREEN}Verifying dependencies...${NC}"
DEPS_OK=true

if ! "$VENV_PYTHON" -c "import crawl4ai" 2>/dev/null; then
    echo -e "${RED}Missing: crawl4ai${NC}"
    DEPS_OK=false
fi

if ! "$VENV_PYTHON" -c "import omnibase_core" 2>/dev/null; then
    echo -e "${RED}Missing: omnibase_core${NC}"
    DEPS_OK=false
fi

if [[ "$DEPS_OK" == "false" ]]; then
    echo -e "${YELLOW}Installing missing dependencies...${NC}"
    uv sync --all-groups
fi

# Show Python version
PYTHON_VERSION=$("$VENV_PYTHON" --version)
echo -e "${GREEN}Using: $PYTHON_VERSION${NC}"
echo -e "${GREEN}From: $VENV_PYTHON${NC}"
echo ""

# Check if user wants to skip coverage
SKIP_COVERAGE=false
for arg in "$@"; do
    if [[ "$arg" == "--no-cov" ]]; then
        SKIP_COVERAGE=true
        break
    fi
done

# Default coverage flags (unless explicitly disabled or custom --cov provided)
COVERAGE_FLAGS=""
if [[ "$SKIP_COVERAGE" == "false" ]] && [[ ! "$*" =~ "--cov" ]]; then
    COVERAGE_FLAGS="--cov=src --cov-report=term-missing --cov-report=html --cov-report=xml"
    echo -e "${GREEN}Coverage enabled (reports: terminal, HTML, XML)${NC}"
    echo -e "${GREEN}Use --no-cov to disable coverage${NC}"
    echo ""
fi

# Filter out --no-cov flag before passing to pytest
FILTERED_ARGS=()
for arg in "$@"; do
    if [[ "$arg" != "--no-cov" ]]; then
        FILTERED_ARGS+=("$arg")
    fi
done

# Run pytest with coverage flags + filtered arguments
"$VENV_PYTHON" -m pytest $COVERAGE_FLAGS "${FILTERED_ARGS[@]}"

# Capture exit code
EXIT_CODE=$?

# Print summary
echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}✓ Tests passed successfully${NC}"
    if [[ "$SKIP_COVERAGE" == "false" ]] && [[ ! "$*" =~ "--cov" ]]; then
        echo ""
        echo -e "${GREEN}Coverage reports generated:${NC}"
        echo -e "  ${GREEN}→${NC} Terminal output (above)"
        echo -e "  ${GREEN}→${NC} HTML: htmlcov/index.html"
        echo -e "  ${GREEN}→${NC} XML: coverage.xml"
        echo ""
        echo -e "${GREEN}View HTML report:${NC} open htmlcov/index.html"
    fi
else
    echo -e "${RED}✗ Tests failed (exit code: $EXIT_CODE)${NC}"
fi

exit $EXIT_CODE
