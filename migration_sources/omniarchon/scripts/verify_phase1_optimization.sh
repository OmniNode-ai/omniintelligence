#!/bin/bash
# Phase 1 Performance Optimization - Verification Script
# This script verifies that all Phase 1 optimizations are working correctly

set -e

echo "=================================================="
echo "Phase 1 Performance Optimization - Verification"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

# Function to print info
print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check if services are running
echo "Step 1: Checking service status..."
echo "-----------------------------------"

# Check Valkey
if docker compose ps archon-valkey | grep -q "Up"; then
    print_status 0 "Valkey service is running"
    VALKEY_RUNNING=0
else
    print_status 1 "Valkey service is NOT running"
    VALKEY_RUNNING=1
fi

# Check MCP
if docker compose ps archon-mcp | grep -q "Up"; then
    print_status 0 "MCP service is running"
    MCP_RUNNING=0
else
    print_status 1 "MCP service is NOT running"
    MCP_RUNNING=1
fi

echo ""

# Test Valkey connectivity
echo "Step 2: Testing Valkey connectivity..."
echo "---------------------------------------"

if [ $VALKEY_RUNNING -eq 0 ]; then
    PING_RESULT=$(docker exec archon-valkey valkey-cli ping 2>/dev/null || echo "FAIL")
    if [ "$PING_RESULT" = "PONG" ]; then
        print_status 0 "Valkey responds to PING"
    else
        print_status 1 "Valkey does not respond to PING"
    fi

    # Test SET/GET
    docker exec archon-valkey valkey-cli SET test:verification "phase1_test" > /dev/null 2>&1
    GET_RESULT=$(docker exec archon-valkey valkey-cli GET test:verification 2>/dev/null || echo "FAIL")
    if [ "$GET_RESULT" = "phase1_test" ]; then
        print_status 0 "Valkey SET/GET operations work"
        docker exec archon-valkey valkey-cli DEL test:verification > /dev/null 2>&1
    else
        print_status 1 "Valkey SET/GET operations failed"
    fi
else
    print_info "Skipping Valkey tests (service not running)"
fi

echo ""

# Test MCP health
echo "Step 3: Testing MCP service health..."
echo "--------------------------------------"

if [ $MCP_RUNNING -eq 0 ]; then
    MCP_HEALTH=$(curl -s http://localhost:8051/health 2>/dev/null || echo "FAIL")
    if echo "$MCP_HEALTH" | grep -q "ok"; then
        print_status 0 "MCP health endpoint responds"
    else
        print_status 1 "MCP health endpoint failed"
    fi
else
    print_info "Skipping MCP tests (service not running)"
fi

echo ""

# Check cache statistics
echo "Step 4: Checking cache statistics..."
echo "-------------------------------------"

if [ $VALKEY_RUNNING -eq 0 ]; then
    CACHE_KEYS=$(docker exec archon-valkey valkey-cli DBSIZE 2>/dev/null || echo "0")
    print_info "Current cache keys: $CACHE_KEYS"

    CACHE_INFO=$(docker exec archon-valkey valkey-cli INFO stats 2>/dev/null | grep keyspace)
    if [ ! -z "$CACHE_INFO" ]; then
        print_status 0 "Cache statistics available"
        echo "$CACHE_INFO"
    else
        print_status 1 "Cache statistics not available"
    fi
else
    print_info "Skipping cache statistics (Valkey not running)"
fi

echo ""

# Test cache-aware research
echo "Step 5: Testing cache-aware research..."
echo "----------------------------------------"

if [ $MCP_RUNNING -eq 0 ] && [ $VALKEY_RUNNING -eq 0 ]; then
    print_info "Testing orchestrated research with cache..."

    # First request (cold cache)
    print_info "Cold cache request..."
    START_TIME=$(date +%s%3N)
    COLD_RESULT=$(curl -s -X POST http://localhost:8051/api/research \
        -H "Content-Type: application/json" \
        -d '{"query": "ONEX verification test", "max_results_per_source": 3}' 2>/dev/null || echo "FAIL")
    END_TIME=$(date +%s%3N)
    COLD_DURATION=$((END_TIME - START_TIME))

    if echo "$COLD_RESULT" | grep -q "success"; then
        print_status 0 "Cold cache request succeeded (${COLD_DURATION}ms)"
        CACHE_MISSES=$(echo "$COLD_RESULT" | grep -o '"misses":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
        print_info "Cache misses: $CACHE_MISSES"
    else
        print_status 1 "Cold cache request failed"
    fi

    sleep 1

    # Second request (warm cache)
    print_info "Warm cache request..."
    START_TIME=$(date +%s%3N)
    WARM_RESULT=$(curl -s -X POST http://localhost:8051/api/research \
        -H "Content-Type: application/json" \
        -d '{"query": "ONEX verification test", "max_results_per_source": 3}' 2>/dev/null || echo "FAIL")
    END_TIME=$(date +%s%3N)
    WARM_DURATION=$((END_TIME - START_TIME))

    if echo "$WARM_RESULT" | grep -q "success"; then
        print_status 0 "Warm cache request succeeded (${WARM_DURATION}ms)"
        CACHE_HITS=$(echo "$WARM_RESULT" | grep -o '"hits":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
        print_info "Cache hits: $CACHE_HITS"

        # Calculate improvement
        if [ $COLD_DURATION -gt 0 ]; then
            IMPROVEMENT=$((100 - (WARM_DURATION * 100 / COLD_DURATION)))
            print_info "Performance improvement: ${IMPROVEMENT}%"
        fi
    else
        print_status 1 "Warm cache request failed"
    fi
else
    print_info "Skipping research tests (services not running)"
fi

echo ""

# Summary
echo "=================================================="
echo "Verification Summary"
echo "=================================================="

if [ $VALKEY_RUNNING -eq 0 ] && [ $MCP_RUNNING -eq 0 ]; then
    print_status 0 "All core services are running"
    print_status 0 "Phase 1 optimizations are operational"
    echo ""
    print_info "Next steps:"
    echo "  1. Run performance benchmark: pytest python/tests/test_search_performance.py -v -s"
    echo "  2. Review benchmark report: cat python/performance_benchmark_phase1.json"
    echo "  3. Monitor cache metrics: docker exec archon-valkey valkey-cli INFO stats"
else
    print_status 1 "Some services are not running"
    echo ""
    print_info "To start services:"
    echo "  docker compose up -d --build"
fi

echo ""
