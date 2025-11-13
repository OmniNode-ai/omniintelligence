#!/bin/bash
# ============================================================================
# OmniArchon - Start Core Services Only
# ============================================================================
# Purpose: Start infrastructure + core services (no frontend, no agents)
# Usage: ./start-services-only.sh
# ============================================================================

set -e  # Exit on error

echo "🚀 Starting OmniArchon Core Services..."

# Check if .env file exists
if [ ! -f "../.env" ]; then
  echo "⚠️  WARNING: .env file not found in parent directory"
  echo "   Copy .env.example to .env and configure required values"
  echo ""
  read -p "Continue without .env file? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Start infrastructure and services only (no frontend)
echo "📦 Building and starting core services..."
docker compose -f docker-compose.yml \
               -f docker-compose.services.yml \
               up --build

echo ""
echo "✅ Core services started!"
echo ""
echo "   📊 Services:"
echo "   - Intelligence: http://localhost:8053"
echo "   - Bridge:       http://localhost:8054"
echo "   - Search:       http://localhost:8055"
echo "   - LangExtract:  http://localhost:8156"
echo ""
echo "   📦 Data Layer:"
echo "   - Qdrant:       http://localhost:6333"
echo "   - Memgraph:     http://localhost:7687"
echo "   - Valkey:       redis://localhost:6379"
echo ""
echo "   🔍 Optional:"
echo "   - Add frontend:     docker compose -f docker-compose.frontend.yml up -d"
echo "   - Start agents:     docker compose --profile agents up -d"
echo "   - View logs:        docker compose logs -f [service]"
echo "   - Stop all:         ./stop-all.sh"
echo ""
