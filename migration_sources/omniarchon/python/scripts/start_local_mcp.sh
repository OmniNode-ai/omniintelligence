#!/usr/bin/env bash

# Start Local MCP Server with External Gateway
#
# This script starts an MCP server on the host (port 8151) with the external
# MCP gateway enabled for testing zen, context7, codanna, serena, and
# sequential-thinking integrations.
#
# Runs in parallel with Docker MCP server (port 8051)

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Local MCP Server with External Gateway${NC}"
echo ""

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${GREEN}📂 Project root: $PROJECT_ROOT${NC}"

# Load secrets from main .env file
ENV_FILE="$PROJECT_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found at $ENV_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}🔐 Loading secrets from $ENV_FILE${NC}"

# Export critical secrets (filter out comments and empty lines)
export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | grep 'SUPABASE_URL\|SUPABASE_SERVICE_KEY\|SERVICE_AUTH_TOKEN\|LOGFIRE_TOKEN\|OPENAI_API_KEY' | xargs)

# Override with local MCP configuration
export ARCHON_ENABLE_EXTERNAL_GATEWAY=true
export ARCHON_MCP_PORT=8151

# All required service ports (localhost since we're on host)
export ARCHON_SERVER_PORT=8181
export ARCHON_AGENTS_PORT=8052
export INTELLIGENCE_SERVICE_PORT=8053
export BRIDGE_SERVICE_PORT=8054
export SEARCH_SERVICE_PORT=8055

# Additional required ports
export LANGEXTRACT_SERVICE_PORT=8156

# Backend service URLs
export INTELLIGENCE_SERVICE_URL=http://localhost:8053
export API_SERVICE_URL=http://localhost:8181
export MEMGRAPH_URI=bolt://localhost:7687
export VALKEY_URL=redis://:archon_cache_2025@localhost:6379/0
export ENABLE_CACHE=true

# Logging
export LOG_LEVEL=INFO

# Enable menu system
export ARCHON_ENABLE_MENU=1

echo ""
echo -e "${GREEN}⚙️  Configuration:${NC}"
echo "   ARCHON_MCP_PORT: $ARCHON_MCP_PORT"
echo "   ARCHON_ENABLE_EXTERNAL_GATEWAY: $ARCHON_ENABLE_EXTERNAL_GATEWAY"
echo "   INTELLIGENCE_SERVICE_URL: $INTELLIGENCE_SERVICE_URL"
echo "   API_SERVICE_URL: $API_SERVICE_URL"
echo "   MEMGRAPH_URI: $MEMGRAPH_URI"
echo "   VALKEY_URL: $VALKEY_URL"
echo "   ENABLE_CACHE: $ENABLE_CACHE"
echo ""

# Change to python directory
cd "$PROJECT_ROOT/python"

echo -e "${GREEN}📦 Python environment: $(pwd)${NC}"

# Check for virtual environment
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python3"
    if [ ! -f "$PYTHON_BIN" ]; then
        echo -e "${RED}❌ Error: Python executable not found at $PYTHON_BIN${NC}"
        exit 1
    fi
    echo -e "${GREEN}🐍 Using virtual environment Python: $PYTHON_BIN${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: No .venv directory found${NC}"
    echo -e "${YELLOW}   Consider running: poetry install --no-root${NC}"
    exit 1
fi

# Start MCP server
echo -e "${GREEN}🌉 Starting MCP server on port $ARCHON_MCP_PORT with external gateway enabled...${NC}"
echo -e "${GREEN}   External services config: $(pwd)/config/mcp_services.yaml${NC}"
echo ""
echo -e "${YELLOW}📋 Expected external services:${NC}"
echo "   - zen (Multi-model reasoning)"
echo "   - context7 (Library docs)"
echo "   - codanna (Code intelligence)"
echo "   - serena (Codebase analysis)"
echo "   - sequential-thinking (Advanced reasoning)"
echo ""
echo -e "${GREEN}🔄 Starting server...${NC}"
echo ""

# Start the MCP server with direct Python path
exec "$PYTHON_BIN" -m src.mcp_server.mcp_server
