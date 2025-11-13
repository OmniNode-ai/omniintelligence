#!/bin/bash
# ============================================================================
# OmniArchon - Stop All Services
# ============================================================================
# Purpose: Stop all running OmniArchon services (dev, frontend, monitoring)
# Usage: ./stop-all.sh
# ============================================================================

set -e  # Exit on error

echo "🛑 Stopping all OmniArchon services..."

# Stop all compose stacks
docker compose -f docker-compose.yml \
               -f docker-compose.services.yml \
               -f docker-compose.frontend.yml \
               down

# Also try to stop monitoring if it's running
if docker compose -f docker-compose.monitoring.yml ps -q > /dev/null 2>&1; then
  echo "🛑 Stopping monitoring stack..."
  docker compose -f docker-compose.monitoring.yml down
fi

echo ""
echo "✅ All services stopped!"
echo ""
echo "   📋 Optional cleanup:"
echo "   - Remove volumes:    docker compose down -v"
echo "   - Remove images:     docker compose down --rmi all"
echo "   - Prune system:      docker system prune -a"
echo ""
