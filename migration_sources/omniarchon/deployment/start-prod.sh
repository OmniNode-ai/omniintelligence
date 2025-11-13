#!/bin/bash
# ============================================================================
# OmniArchon - Start Production Environment
# ============================================================================
# Purpose: Start production stack in detached mode with production settings
# Usage: ./start-prod.sh
# ============================================================================

set -e  # Exit on error

echo "🚀 Starting OmniArchon Production Environment..."

# Check required secrets
if [ -z "$POSTGRES_PASSWORD" ] || [ -z "$VALKEY_PASSWORD" ] || [ -z "$GH_PAT" ]; then
  echo "❌ ERROR: Required secrets not set"
  echo ""
  echo "   Please set the following environment variables:"
  echo "   - POSTGRES_PASSWORD (PostgreSQL database password)"
  echo "   - VALKEY_PASSWORD (Valkey/Redis cache password)"
  echo "   - GH_PAT (GitHub Personal Access Token for omnibase_core)"
  echo ""
  echo "   You can set them in .env.production or export them:"
  echo "   export POSTGRES_PASSWORD='your-password'"
  echo "   export VALKEY_PASSWORD='your-password'"
  echo "   export GH_PAT='your-github-token'"
  echo ""
  exit 1
fi

# Check if .env.production exists
if [ ! -f "../.env.production" ]; then
  echo "⚠️  WARNING: .env.production file not found"
  echo "   Using default .env file"
  ENV_FILE="../.env"
else
  ENV_FILE="../.env.production"
  echo "✅ Using production environment file: $ENV_FILE"
fi

# Start services in detached mode
echo "📦 Building and starting production services..."
docker compose -f docker-compose.yml \
               -f docker-compose.services.yml \
               -f docker-compose.frontend.yml \
               --env-file "$ENV_FILE" \
               up -d --build

echo ""
echo "✅ Production environment started!"
echo ""
echo "   📊 Service Status:"
docker compose ps
echo ""
echo "   📋 Commands:"
echo "   - View logs:     docker compose logs -f [service]"
echo "   - Check health:  docker compose ps"
echo "   - Stop all:      ./stop-all.sh"
echo ""
