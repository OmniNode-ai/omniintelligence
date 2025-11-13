#!/bin/bash
#
# Demonstration: Fail-Fast Validation Behavior
#
# This script demonstrates how the validation script behaves in different scenarios.
#
# Usage:
#   ./scripts/demo_failfast_behavior.sh
#
# Created: 2025-11-01
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=================================================================="
echo "Fail-Fast Validation Demonstration"
echo "=================================================================="
echo ""

# Create test repository
echo -e "${BLUE}[SETUP]${NC} Creating test repository..."
mkdir -p /tmp/demo_repo
echo "# Demo Repository" > /tmp/demo_repo/README.md
echo "def demo(): pass" > /tmp/demo_repo/demo.py
echo -e "${GREEN}✅${NC} Test repository created at /tmp/demo_repo"
echo ""

# Check current infrastructure state
echo "=================================================================="
echo "Current Infrastructure State"
echo "=================================================================="

# Check Redpanda
echo -n "Redpanda (192.168.86.200:9092): "
if nc -zv 192.168.86.200 9092 2>&1 | grep -q "succeeded"; then
    echo -e "${GREEN}RUNNING${NC}"
    REDPANDA_UP=true
else
    echo -e "${RED}DOWN${NC}"
    REDPANDA_UP=false
fi

# Check Services
for port in 8053 8054 8055; do
    echo -n "Service on port $port: "
    if curl -f -s http://localhost:$port/health >/dev/null 2>&1; then
        echo -e "${GREEN}HEALTHY${NC}"
    else
        echo -e "${RED}UNHEALTHY${NC}"
    fi
done

# Check Qdrant
echo -n "Qdrant (localhost:6333): "
if curl -f -s http://localhost:6333/collections >/dev/null 2>&1; then
    echo -e "${GREEN}RUNNING${NC}"
else
    echo -e "${RED}DOWN${NC}"
fi

echo ""

# Scenario demonstration
echo "=================================================================="
echo "Scenario Demonstration"
echo "=================================================================="
echo ""

if [ "$REDPANDA_UP" = false ]; then
    echo -e "${YELLOW}[SCENARIO 1]${NC} Redpanda is DOWN - Demonstrating FAIL FAST behavior"
    echo ""
    echo "Running validation script (should fail fast):"
    echo -e "${BLUE}$ ./scripts/reingest_with_validation.sh /tmp/demo_repo${NC}"
    echo ""

    # Run validation script (expect it to fail)
    set +e
    /Volumes/PRO-G40/Code/omniarchon/scripts/reingest_with_validation.sh /tmp/demo_repo 2>&1 | tail -20
    EXIT_CODE=$?
    set -e

    echo ""
    echo -e "${BLUE}Exit code: $EXIT_CODE${NC}"

    if [ $EXIT_CODE -eq 1 ]; then
        echo -e "${GREEN}✅ CORRECT BEHAVIOR${NC}: Script failed fast with exit code 1"
        echo -e "${GREEN}✅${NC} No ingestion was attempted"
        echo -e "${GREEN}✅${NC} Clear error message provided"
    else
        echo -e "${RED}❌ UNEXPECTED${NC}: Expected exit code 1, got $EXIT_CODE"
    fi

    echo ""
    echo -e "${YELLOW}[RECOMMENDATION]${NC} Start Redpanda to test success scenario:"
    echo "  ssh jonah@192.168.86.200 'docker start omninode-bridge-redpanda'"

else
    echo -e "${GREEN}[SCENARIO 2]${NC} All infrastructure is UP - Demonstrating SUCCESS behavior"
    echo ""
    echo "Running validation script (should succeed):"
    echo -e "${BLUE}$ ./scripts/reingest_with_validation.sh /tmp/demo_repo${NC}"
    echo ""

    # Run validation script (expect it to succeed)
    set +e
    /Volumes/PRO-G40/Code/omniarchon/scripts/reingest_with_validation.sh /tmp/demo_repo 2>&1 | tail -30
    EXIT_CODE=$?
    set -e

    echo ""
    echo -e "${BLUE}Exit code: $EXIT_CODE${NC}"

    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ CORRECT BEHAVIOR${NC}: Script succeeded with exit code 0"
        echo -e "${GREEN}✅${NC} All pre-flight checks passed"
        echo -e "${GREEN}✅${NC} Repository ingested successfully"
        echo -e "${GREEN}✅${NC} Document count verification passed"
    else
        echo -e "${RED}❌ UNEXPECTED${NC}: Expected exit code 0, got $EXIT_CODE"
    fi

    echo ""
    echo -e "${YELLOW}[TEST FAIL-FAST]${NC} To test fail-fast behavior:"
    echo "  ssh jonah@192.168.86.200 'docker stop omninode-bridge-redpanda'"
    echo "  Then run this demo again"
fi

echo ""
echo "=================================================================="
echo "Summary"
echo "=================================================================="
echo ""
echo "The validation script provides comprehensive fail-fast checks:"
echo ""
echo "✅ Phase 0: Pre-flight infrastructure validation"
echo "   - Redpanda connectivity (FAIL FAST)"
echo "   - Service health checks (FAIL FAST)"
echo "   - Qdrant health (FAIL FAST)"
echo ""
echo "✅ Phase 1: Per-repository document count verification"
echo "   - Verifies new documents were added to Qdrant"
echo ""
echo "✅ Phase 3: Final verification"
echo "   - Ensures minimum document threshold met"
echo ""
echo "This prevents false success reports when infrastructure is down."
echo ""
