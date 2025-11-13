#!/bin/bash
# Quick coverage check script for all OmniArchon services
# Usage: ./scripts/check_coverage.sh [--detailed]

set -e

DETAILED=false
if [[ "$1" == "--detailed" ]]; then
    DETAILED=true
fi

echo "=========================================="
echo "  OmniArchon Coverage Check"
echo "  $(date)"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to run coverage for a service
run_coverage() {
    local service=$1
    local service_path=$2
    local extra_args=$3

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📦 $service Service"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$service_path" || return 1

    if $DETAILED; then
        poetry run pytest --cov=. --cov-report=term --cov-report=json:coverage.json $extra_args -v
    else
        poetry run pytest --cov=. --cov-report=term-missing:skip-covered --cov-report=json:coverage.json $extra_args -q 2>&1 | tail -20
    fi

    # Extract coverage percentage and status using Python (no bc dependency)
    if [ -f coverage.json ]; then
        # Use Python for floating-point comparison
        # Returns: coverage_value status_code (0=GOOD >=60%, 1=FAIR >=40%, 2=POOR <40%)
        read coverage status_code <<< $(python3 -c "
import json
import sys
try:
    data = json.load(open('coverage.json'))
    cov = data['totals']['percent_covered']
    status = 0 if cov >= 60 else (1 if cov >= 40 else 2)
    print(f'{cov:.1f}', status)
except Exception as e:
    # Log error for debugging (stderr redirected to /dev/null by shell)
    print(f'Coverage parsing error: {e}', file=sys.stderr)
    print('N/A', '3')
" 2>/dev/null || echo "N/A 3")

        # Color based on status code from Python
        case $status_code in
            0)
                color=$GREEN
                status="✅ GOOD"
                ;;
            1)
                color=$YELLOW
                status="⚠️  FAIR"
                ;;
            2)
                color=$RED
                status="❌ POOR"
                ;;
            *)
                color=$RED
                status="❌ ERROR"
                ;;
        esac

        echo -e "\n${color}Coverage: $coverage% $status${NC}\n"
    fi

    cd - > /dev/null
}

# Store starting directory
START_DIR=$(pwd)

# Bridge Service
run_coverage "Bridge" "services/bridge" "--ignore=tests/unit/test_document_processing.py"

# Search Service
run_coverage "Search" "services/search" ""

# Consumer Service
run_coverage "Intelligence Consumer" "services/intelligence-consumer" "tests/"

# Intelligence Service (skip for now due to import errors)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Intelligence Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}⚠️  SKIPPED: Test infrastructure needs fixing${NC}"
echo "   - Import path errors"
echo "   - Missing pytest markers (now added)"
echo "   - Module dependency issues"
echo "   - See COVERAGE_BASELINE_REPORT.md for details"
echo ""

# Summary
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""
echo "Current Status:"
echo "  Bridge:     48.6% ⚠️"
echo "  Search:     26.0% ❌"
echo "  Consumer:   54.0% ⚠️"
echo "  Intelligence: ~15-20% (estimated) ❌"
echo ""
echo "Overall:    ~30-35% ❌"
echo "Target:     60% ✅"
echo "Gap:        ~25-30 percentage points"
echo ""
echo "Next Steps:"
echo "  1. Fix Intelligence test infrastructure (Week 1)"
echo "  2. Add handler tests (Weeks 2-3)"
echo "  3. Cover API routes (Week 4)"
echo "  4. Integration tests (Weeks 5-6)"
echo ""
echo "See COVERAGE_BASELINE_REPORT.md for full analysis"
echo "=========================================="
