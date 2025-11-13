#!/bin/bash
################################################################################
# Setup Pre-Commit Hooks for Integration Testing
#
# Purpose:
#   Install and configure pre-commit hooks to run critical integration tests
#   before commits. Prevents broken code from being committed by catching
#   vectorization and pipeline issues during development.
#
# Hooks Installed:
#   1. Black/isort formatting
#   2. Unit test smoke tests (quick feedback)
#   3. Critical integration test (vectorization pipeline validation)
#   4. Incremental tree stamping
#
# Requirements:
#   - Python 3.12+
#   - Poetry (for Python dependency management)
#   - Docker (for running services)
#   - Git repository
#
# Usage:
#   ./scripts/setup_pre_commit_hooks.sh
#
# Testing Hooks:
#   # Test all hooks manually
#   pre-commit run --all-files
#
#   # Test only integration test hook
#   pre-commit run critical-integration-test --all-files
#
#   # Bypass hooks (emergency use only)
#   git commit --no-verify -m "message"
#
# Exit Codes:
#   0 - Success
#   1 - Error (missing dependencies, installation failed)
#
# Created: 2025-11-12
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

################################################################################
# Pre-flight Checks
################################################################################

log_info "Starting pre-commit hooks setup..."
echo ""

# Check if we're in a git repository
if [ ! -d "${PROJECT_ROOT}/.git" ]; then
    log_error "Not in a git repository. Please run from project root."
    exit 1
fi

log_success "Git repository detected"

# Check for Python
if ! check_command python3; then
    log_error "Python 3 not found. Please install Python 3.12+."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
log_success "Python ${PYTHON_VERSION} found"

# Check for Poetry
if ! check_command poetry; then
    log_warning "Poetry not found. Install with: curl -sSL https://install.python-poetry.org | python3 -"
    log_info "Continuing anyway (some hooks may not work)..."
else
    POETRY_VERSION=$(poetry --version | awk '{print $3}')
    log_success "Poetry ${POETRY_VERSION} found"
fi

# Check for Docker
if ! check_command docker; then
    log_warning "Docker not found. Integration tests require running services."
    log_info "Install Docker from: https://docs.docker.com/get-docker/"
    log_info "Continuing anyway (integration tests will be skipped)..."
else
    log_success "Docker found"
fi

echo ""

################################################################################
# Install pre-commit
################################################################################

log_info "Checking for pre-commit..."

if ! check_command pre-commit; then
    log_info "Installing pre-commit..."

    if check_command pip3; then
        pip3 install pre-commit || {
            log_error "Failed to install pre-commit with pip3"
            exit 1
        }
    elif check_command pip; then
        pip install pre-commit || {
            log_error "Failed to install pre-commit with pip"
            exit 1
        }
    else
        log_error "pip not found. Cannot install pre-commit."
        exit 1
    fi

    log_success "pre-commit installed"
else
    PRE_COMMIT_VERSION=$(pre-commit --version | awk '{print $2}')
    log_success "pre-commit ${PRE_COMMIT_VERSION} already installed"
fi

echo ""

################################################################################
# Verify Configuration File
################################################################################

log_info "Verifying .pre-commit-config.yaml..."

CONFIG_FILE="${PROJECT_ROOT}/.pre-commit-config.yaml"

if [ ! -f "${CONFIG_FILE}" ]; then
    log_error "Configuration file not found: ${CONFIG_FILE}"
    exit 1
fi

log_success "Configuration file found"

# Verify critical hooks are present
if grep -q "critical-integration-test" "${CONFIG_FILE}"; then
    log_success "Critical integration test hook configured"
else
    log_warning "Critical integration test hook not found in config"
fi

if grep -q "pytest-smoke-tests" "${CONFIG_FILE}"; then
    log_success "Unit test smoke tests hook configured"
else
    log_warning "Unit test smoke tests hook not found in config"
fi

echo ""

################################################################################
# Install Hooks
################################################################################

log_info "Installing pre-commit hooks..."

cd "${PROJECT_ROOT}"

# Install hooks
if pre-commit install; then
    log_success "Pre-commit hooks installed successfully"
else
    log_error "Failed to install pre-commit hooks"
    exit 1
fi

# Install commit-msg hook (optional, for future use)
if pre-commit install --hook-type commit-msg 2>/dev/null; then
    log_success "commit-msg hook installed"
else
    log_warning "commit-msg hook not installed (optional)"
fi

echo ""

################################################################################
# Test Installation
################################################################################

log_info "Testing hook installation..."

# Run pre-commit on a single file to verify installation
if pre-commit run --files "${CONFIG_FILE}" &>/dev/null; then
    log_success "Hooks are working correctly"
else
    log_warning "Hook test produced warnings (this may be normal)"
fi

echo ""

################################################################################
# Summary and Usage Instructions
################################################################################

log_success "Pre-commit hooks setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Installed Hooks:"
echo "  1. ✨ Black/isort formatting (automatic)"
echo "  2. 🧪 Unit test smoke tests (always runs)"
echo "  3. 🔍 Critical integration test (runs on service/test changes)"
echo "  4. 🏷️  Incremental tree stamping (always runs)"
echo ""
echo "🚀 Usage:"
echo "  # Normal commit (hooks run automatically)"
echo "  git commit -m \"your message\""
echo ""
echo "  # Test all hooks manually"
echo "  pre-commit run --all-files"
echo ""
echo "  # Test only integration test"
echo "  pre-commit run critical-integration-test --all-files"
echo ""
echo "  # Bypass hooks (EMERGENCY USE ONLY)"
echo "  git commit --no-verify -m \"emergency fix\""
echo ""
echo "⚡ Performance:"
echo "  • Unit tests: ~5-10 seconds"
echo "  • Integration test: ~30-60 seconds (only on service changes)"
echo "  • Formatting: ~1-2 seconds"
echo ""
echo "🔧 Requirements for Integration Tests:"
echo "  • Services must be running: docker compose up -d"
echo "  • If services are down, integration tests will be skipped"
echo ""
echo "📚 Documentation:"
echo "  • Pre-commit config: .pre-commit-config.yaml"
echo "  • Integration tests: tests/integration/test_post_deployment_smoke.py"
echo "  • Smoke test docs: docs/VALIDATION_SCRIPT.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_success "Ready to commit with confidence! 🎉"
