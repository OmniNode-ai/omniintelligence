#!/bin/bash
# ============================================================================
# Consumer Health Check Script
# ============================================================================
# Purpose: Verify health status of all intelligence consumer instances
# Usage: ./scripts/check_consumers.sh
#
# Part of Multi-Machine Embedding Architecture (Option A)
# See: docs/MULTI_MACHINE_EMBEDDING.md
# ============================================================================

set -e

# Consumer instance configuration (name:port)
CONSUMERS=(
  "archon-intelligence-consumer-1:8090"
  "archon-intelligence-consumer-2:8091"
  "archon-intelligence-consumer-3:8092"
  "archon-intelligence-consumer-4:8063"
)

# ANSI color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "============================================================================"
echo "Intelligence Consumer Health Check"
echo "============================================================================"
echo ""

HEALTHY_COUNT=0
TOTAL_COUNT=${#CONSUMERS[@]}

for consumer in "${CONSUMERS[@]}"; do
  name="${consumer%%:*}"
  port="${consumer##*:}"

  # Check if container is running
  if ! docker ps --format "{{.Names}}" | grep -q "^${name}$"; then
    echo -e "${RED}❌ $name (port $port): CONTAINER NOT RUNNING${NC}"
    continue
  fi

  # Check health endpoint
  status=$(curl -s --connect-timeout 5 --max-time 10 -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null || echo "000")

  if [ "$status" = "200" ]; then
    echo -e "${GREEN}✅ $name (port $port): HEALTHY${NC}"
    HEALTHY_COUNT=$((HEALTHY_COUNT + 1))

    # Fetch additional health info if available
    health_info=$(curl -s --connect-timeout 5 --max-time 10 http://localhost:$port/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "")
    if [ -n "$health_info" ]; then
      echo "   Status: $(echo "$health_info" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)"
    fi
  elif [ "$status" = "000" ]; then
    echo -e "${RED}❌ $name (port $port): CONNECTION REFUSED${NC}"
  else
    echo -e "${YELLOW}⚠️  $name (port $port): UNHEALTHY (HTTP $status)${NC}"
  fi
done

echo ""
echo "============================================================================"
echo "Summary: $HEALTHY_COUNT/$TOTAL_COUNT consumers healthy"
echo "============================================================================"
echo ""

# Exit with error if not all healthy
if [ "$HEALTHY_COUNT" -ne "$TOTAL_COUNT" ]; then
  exit 1
fi

exit 0
