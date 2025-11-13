#!/bin/bash
################################################################################
# Critical Integration Test Pre-Commit Hook
#
# Purpose:
#   Run the critical vectorization test before commits to catch bugs early.
#   Only runs if services are healthy - skips gracefully if services are down.
#
# Test Run:
#   tests/integration/test_post_deployment_smoke.py::test_document_processing_creates_vector
#
# Exit Codes:
#   0 - Test passed OR services not running (allow commit)
#   1 - Test failed AND services running (block commit)
#
# Created: 2025-11-12
################################################################################

set -euo pipefail

# Check if archon-intelligence service is running
check_services() {
    if curl -s http://localhost:8053/health > /dev/null 2>&1; then
        return 0  # Services running
    else
        return 1  # Services not running
    fi
}

# Run the critical integration test
run_test() {
    pytest tests/integration/test_post_deployment_smoke.py::TestPostDeploymentSmoke::test_document_processing_creates_vector \
        -v --tb=short --timeout=60
}

# Main logic
main() {
    echo "🔍 Checking if services are running..."

    if ! check_services; then
        echo "⚠️  Services not running - skipping integration test"
        echo "💡 Tip: Run 'docker compose up -d' to enable integration tests"
        exit 0  # Allow commit
    fi

    echo "✅ Services running - executing critical integration test..."
    echo ""

    if run_test; then
        echo ""
        echo "✅ Critical integration test passed"
        exit 0  # Allow commit
    else
        echo ""
        echo "❌ CRITICAL INTEGRATION TEST FAILED"
        echo ""
        echo "The vectorization pipeline test failed. This indicates a bug that"
        echo "would break the system in production. Please fix the issue before committing."
        echo ""
        echo "To bypass this check (NOT RECOMMENDED):"
        echo "  git commit --no-verify -m \"your message\""
        echo ""
        exit 1  # Block commit
    fi
}

main "$@"
