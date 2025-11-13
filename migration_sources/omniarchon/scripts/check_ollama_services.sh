#!/bin/bash
# ============================================================================
# Ollama Services Health Check Script
# ============================================================================
# Purpose: Verify connectivity and health of all Ollama embedding services
# Usage: ./scripts/check_ollama_services.sh [--verbose]
#
# Part of Multi-Machine Embedding Architecture (Option A)
# See: docs/MULTI_MACHINE_EMBEDDING.md
# ============================================================================

set -e

# Ollama endpoint configuration (host:port:name)
OLLAMA_ENDPOINTS=(
  "192.168.86.200:11434:Primary_CPU"
  "192.168.86.201:11434:GPU_4090"
  "192.168.86.202:11434:GPU_5090"
)

# ANSI color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
VERBOSE=0
if [ "$1" = "--verbose" ] || [ "$1" = "-v" ]; then
  VERBOSE=1
fi

echo ""
echo "============================================================================"
echo "Ollama Services Health Check"
echo "============================================================================"
echo ""

HEALTHY_COUNT=0
TOTAL_COUNT=${#OLLAMA_ENDPOINTS[@]}

for endpoint in "${OLLAMA_ENDPOINTS[@]}"; do
  host="${endpoint%%:*}"
  port="$(echo $endpoint | cut -d: -f2)"
  name="${endpoint##*:}"

  echo -e "${BLUE}Checking Ollama $name ($host:$port)...${NC}"

  # Test basic connectivity
  if ! curl -s -f --connect-timeout 5 http://$host:$port/api/tags > /dev/null 2>&1; then
    echo -e "${RED}❌ Ollama $name ($host:$port): UNREACHABLE${NC}"
    echo ""
    continue
  fi

  echo -e "${GREEN}✅ Ollama $name ($host:$port): HEALTHY${NC}"
  HEALTHY_COUNT=$((HEALTHY_COUNT + 1))

  # Verbose mode: Show available models
  if [ "$VERBOSE" -eq 1 ]; then
    echo "   Available models:"
    models=$(curl -s --connect-timeout 5 http://$host:$port/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
for model in data.get('models', []):
    print(f\"     - {model['name']} ({model.get('size', 'unknown size')})\")
" 2>/dev/null || echo "     (unable to parse models)")
    echo "$models"

    # Check for required embedding model
    required_model="nomic-embed-text"
    if curl -s --connect-timeout 5 http://$host:$port/api/tags | grep -q "$required_model"; then
      echo -e "   ${GREEN}✓ Required model '$required_model' is available${NC}"
    else
      echo -e "   ${YELLOW}⚠️  Required model '$required_model' NOT FOUND${NC}"
      echo "   Run: ssh $host 'ollama pull $required_model'"
    fi
  fi

  echo ""
done

echo "============================================================================"
echo "Summary: $HEALTHY_COUNT/$TOTAL_COUNT Ollama services healthy"
echo "============================================================================"
echo ""

# Provide recommendations if not all healthy
if [ "$HEALTHY_COUNT" -ne "$TOTAL_COUNT" ]; then
  echo -e "${YELLOW}Troubleshooting Tips:${NC}"
  echo "1. Verify Ollama is running on each machine:"
  for endpoint in "${OLLAMA_ENDPOINTS[@]}"; do
    host="${endpoint%%:*}"
    name="${endpoint##*:}"
    echo "   ssh $host 'systemctl status ollama'"
  done
  echo ""
  echo "2. Check firewall allows port 11434:"
  for endpoint in "${OLLAMA_ENDPOINTS[@]}"; do
    host="${endpoint%%:*}"
    echo "   ssh $host 'sudo ufw status | grep 11434'"
  done
  echo ""
  echo "3. Verify Ollama is listening on all interfaces:"
  for endpoint in "${OLLAMA_ENDPOINTS[@]}"; do
    host="${endpoint%%:*}"
    echo "   ssh $host 'netstat -tlnp | grep 11434'"
  done
  echo ""
  exit 1
fi

echo "All Ollama services are operational! ✨"
echo ""
echo "Next steps:"
echo "1. Start consumer instances: cd deployment && docker compose -f docker-compose.yml -f docker-compose.services.yml up -d"
echo "2. Check consumer health: ./scripts/check_consumers.sh"
echo "3. Monitor ingestion: python3 scripts/monitor_ingestion_pipeline.py"
echo ""

exit 0
