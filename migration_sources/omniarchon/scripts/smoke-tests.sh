#!/bin/bash

# Smoke tests for deployment validation
# Tests critical functionality after deployment

set -e

ENVIRONMENT="${1:-production}"

echo "🧪 Running smoke tests for $ENVIRONMENT environment..."

# Set environment-specific configuration
case "$ENVIRONMENT" in
    "staging")
        BASE_URL="https://staging.yourdomain.com"
        ;;
    "production")
        BASE_URL="https://archon.yourdomain.com"
        ;;
    *)
        BASE_URL="http://localhost"
        ;;
esac

FAILED=0

# Function to run a test
run_test() {
    local name="$1"
    local command="$2"

    echo -n "Testing $name... "
    if eval "$command" >/dev/null 2>&1; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
        FAILED=1
    fi
}

# Function to test API endpoint
test_api() {
    local endpoint="$1"
    local expected_status="${2:-200}"

    local status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
    [[ "$status" == "$expected_status" ]]
}

# Function to test API with JSON response
test_api_json() {
    local endpoint="$1"
    local json_path="$2"
    local expected_value="$3"

    local response=$(curl -s "$BASE_URL$endpoint")
    local actual=$(echo "$response" | jq -r "$json_path")
    [[ "$actual" == "$expected_value" ]]
}

echo "🔍 Testing core functionality..."

# Health checks
run_test "Frontend Health" "test_api '/health'"
run_test "Backend Health" "test_api '/api/health'"
run_test "MCP Health" "curl -s -f $BASE_URL:8051/health"

# API functionality tests
run_test "Projects API List" "test_api '/api/projects'"
run_test "Tasks API List" "test_api '/api/tasks'"
run_test "RAG Sources API" "test_api '/api/rag/sources'"

# Database connectivity tests
run_test "Database Connection" "test_api_json '/api/health' '.database' 'healthy'"
run_test "Redis Connection" "test_api_json '/api/health' '.redis' 'healthy'"
run_test "Vector DB Connection" "test_api_json '/api/health' '.vector_db' 'healthy'"

# Intelligence services
run_test "Intelligence Service" "curl -s -f http://localhost:8053/health"
run_test "Bridge Service" "curl -s -f http://localhost:8054/health"
run_test "Search Service" "curl -s -f http://localhost:8055/health"

# Frontend loading
run_test "Frontend Loading" "curl -s -f $BASE_URL/ | grep -q 'Archon'"
run_test "Static Assets" "test_api '/assets/index.js' '200'"

# WebSocket connectivity (basic test)
run_test "WebSocket Available" "curl -s -f $BASE_URL/socket.io/socket.io.js"

# Create and test a project (functional test)
echo "🎯 Testing project creation workflow..."

PROJECT_DATA='{"title":"Smoke Test Project","description":"Automated test project"}'
CREATE_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$PROJECT_DATA" \
    "$BASE_URL/api/projects")

if echo "$CREATE_RESPONSE" | jq -e '.success' >/dev/null 2>&1; then
    PROJECT_ID=$(echo "$CREATE_RESPONSE" | jq -r '.project_id')
    echo "✅ Project creation: PASS (ID: $PROJECT_ID)"

    # Test project retrieval
    if curl -s -f "$BASE_URL/api/projects/$PROJECT_ID" >/dev/null; then
        echo "✅ Project retrieval: PASS"

        # Clean up test project
        curl -s -X DELETE "$BASE_URL/api/projects/$PROJECT_ID" >/dev/null
        echo "✅ Project cleanup: PASS"
    else
        echo "❌ Project retrieval: FAIL"
        FAILED=1
    fi
else
    echo "❌ Project creation: FAIL"
    FAILED=1
fi

# Test RAG query functionality
echo "🔍 Testing RAG query functionality..."

RAG_QUERY='{"query":"test query","match_count":1}'
RAG_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$RAG_QUERY" \
    "$BASE_URL/api/rag/query")

if echo "$RAG_RESPONSE" | jq -e '.success' >/dev/null 2>&1; then
    echo "✅ RAG Query: PASS"
else
    echo "❌ RAG Query: FAIL"
    FAILED=1
fi

# Performance tests
echo "⚡ Running performance tests..."

# Response time test
RESPONSE_TIME=$(curl -o /dev/null -s -w "%{time_total}" "$BASE_URL/api/health")
if (( $(echo "$RESPONSE_TIME < 2.0" | bc -l) )); then
    echo "✅ Response time: PASS (${RESPONSE_TIME}s)"
else
    echo "⚠️  Response time: SLOW (${RESPONSE_TIME}s)"
fi

# Load test (simple)
echo -n "Testing concurrent requests... "
for i in {1..10}; do
    curl -s -f "$BASE_URL/api/health" >/dev/null &
done
wait

if [[ $? -eq 0 ]]; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
    FAILED=1
fi

# Security tests
echo "🛡️  Running security tests..."

# Test for common security headers
run_test "Security Headers" "curl -s -I $BASE_URL | grep -q 'X-Frame-Options'"
run_test "HTTPS Redirect" "test_api_json '/api/health' '.secure' 'true'"

# Test for information disclosure
if curl -s "$BASE_URL/api/debug" | grep -q "error"; then
    echo "❌ Information disclosure: FAIL"
    FAILED=1
else
    echo "✅ Information disclosure: PASS"
fi

echo ""
echo "📊 Smoke Test Summary"
echo "===================="

if [[ $FAILED -eq 0 ]]; then
    echo "🎉 All smoke tests passed!"
    echo "✅ Deployment is healthy and functional"
    exit 0
else
    echo "❌ Some smoke tests failed!"
    echo "🚨 Deployment may have issues"
    exit 1
fi
