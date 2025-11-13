#!/bin/bash

# Wait for services to be ready
# Used in CI/CD pipeline and local development

set -e

echo "🚀 Waiting for services to be ready..."

# Function to wait for HTTP service
wait_for_http() {
    local name="$1"
    local url="$2"
    local timeout="${3:-60}"

    echo "⏳ Waiting for $name at $url (timeout: ${timeout}s)"

    for i in $(seq 1 $timeout); do
        if curl -f -s "$url" >/dev/null 2>&1; then
            echo "✅ $name is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo "❌ Timeout waiting for $name"
    return 1
}

# Function to wait for TCP service
wait_for_tcp() {
    local name="$1"
    local host="$2"
    local port="$3"
    local timeout="${4:-60}"

    echo "⏳ Waiting for $name at $host:$port (timeout: ${timeout}s)"

    for i in $(seq 1 $timeout); do
        if nc -z "$host" "$port" 2>/dev/null; then
            echo "✅ $name is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo "❌ Timeout waiting for $name"
    return 1
}

# Set environment-specific URLs
if [[ "${ENVIRONMENT:-}" == "test" ]]; then
    BASE_URL="http://localhost"
    BACKEND_PORT="${ARCHON_SERVER_PORT:-8181}"
    FRONTEND_PORT="${ARCHON_UI_PORT:-3737}"
    MCP_PORT="${ARCHON_MCP_PORT:-8051}"
    INTEL_PORT="${INTELLIGENCE_SERVICE_PORT:-8053}"
    BRIDGE_PORT="${BRIDGE_SERVICE_PORT:-8054}"
    SEARCH_PORT="${SEARCH_SERVICE_PORT:-8055}"
elif [[ "${ENVIRONMENT:-}" == "staging" ]]; then
    BASE_URL="https://staging.yourdomain.com"
    BACKEND_PORT="443"
    FRONTEND_PORT="443"
    MCP_PORT="443"
    INTEL_PORT="443"
    BRIDGE_PORT="443"
    SEARCH_PORT="443"
else
    BASE_URL="http://localhost"
    BACKEND_PORT="${ARCHON_SERVER_PORT:-8181}"
    FRONTEND_PORT="${ARCHON_UI_PORT:-3737}"
    MCP_PORT="${ARCHON_MCP_PORT:-8051}"
    INTEL_PORT="${INTELLIGENCE_SERVICE_PORT:-8053}"
    BRIDGE_PORT="${BRIDGE_SERVICE_PORT:-8054}"
    SEARCH_PORT="${SEARCH_SERVICE_PORT:-8055}"
fi

# Wait for databases first
echo "🔍 Waiting for databases..."
wait_for_tcp "PostgreSQL" "localhost" "5432" 30
wait_for_tcp "Redis" "localhost" "6379" 30
wait_for_tcp "Memgraph" "localhost" "7687" 30
wait_for_http "Qdrant" "http://localhost:6333/health" 60

# Wait for core services
echo "🔍 Waiting for core services..."
wait_for_http "Archon Backend" "$BASE_URL:$BACKEND_PORT/health" 90
wait_for_http "Archon MCP" "$BASE_URL:$MCP_PORT/health" 60

# Wait for intelligence services
echo "🔍 Waiting for intelligence services..."
wait_for_http "Intelligence Service" "$BASE_URL:$INTEL_PORT/health" 60
wait_for_http "Bridge Service" "$BASE_URL:$BRIDGE_PORT/health" 60
wait_for_http "Search Service" "$BASE_URL:$SEARCH_PORT/health" 60

# Wait for frontend
echo "🔍 Waiting for frontend..."
wait_for_http "Archon Frontend" "$BASE_URL:$FRONTEND_PORT/health" 30

echo "🎉 All services are ready!"

# Run basic health checks
echo "🩺 Running health checks..."

check_service() {
    local name="$1"
    local url="$2"

    echo -n "Checking $name... "
    if response=$(curl -f -s "$url" 2>/dev/null); then
        echo "✅ OK"
        return 0
    else
        echo "❌ FAILED"
        return 1
    fi
}

# Health check all services
FAILED=0

check_service "Backend Health" "$BASE_URL:$BACKEND_PORT/health" || FAILED=1
check_service "MCP Health" "$BASE_URL:$MCP_PORT/health" || FAILED=1
check_service "Intelligence Health" "$BASE_URL:$INTEL_PORT/health" || FAILED=1
check_service "Bridge Health" "$BASE_URL:$BRIDGE_PORT/health" || FAILED=1
check_service "Search Health" "$BASE_URL:$SEARCH_PORT/health" || FAILED=1
check_service "Frontend Health" "$BASE_URL:$FRONTEND_PORT/health" || FAILED=1
check_service "Qdrant Health" "http://localhost:6333/health" || FAILED=1

if [[ $FAILED -eq 0 ]]; then
    echo "🎉 All health checks passed!"
    exit 0
else
    echo "❌ Some health checks failed!"
    exit 1
fi
