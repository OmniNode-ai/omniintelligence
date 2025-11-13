#!/bin/bash

# Archon Integration Validation Script
# Comprehensive health check for all critical components
# Exit codes: 0 (HEALTHY), 1 (DEGRADED), 2 (UNHEALTHY)

set -uo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INTELLIGENCE_URL="http://localhost:8053"
BRIDGE_URL="http://localhost:8054"
SEARCH_URL="http://localhost:8055"
QDRANT_URL="http://localhost:6333"
KAFKA_CONTAINER="omninode-bridge-redpanda"
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--verbose|-v] [--help|-h]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v    Enable verbose output"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Counters for health tracking
CHECKS_PASSED=0
CHECKS_FAILED=0
CRITICAL_FAILURES=0

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_FAILED++))
}

log_error() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
    ((CRITICAL_FAILURES++))
}

verbose_log() {
    if [ "$VERBOSE" = true ]; then
        echo -e "  ${NC}$1${NC}"
    fi
}

check_http_service() {
    local name=$1
    local url=$2
    local timeout=${3:-5}

    if curl -f -s -m "$timeout" "$url" > /dev/null 2>&1; then
        log_success "$name: healthy"
        return 0
    else
        log_error "$name: unhealthy (no response)"
        return 1
    fi
}

check_http_json_response() {
    local name=$1
    local url=$2
    local timeout=${3:-5}

    local response=$(curl -f -s -m "$timeout" "$url" 2>/dev/null || echo "")

    if [ -n "$response" ]; then
        verbose_log "Response: $response"

        # Try to parse as JSON
        if echo "$response" | jq . > /dev/null 2>&1; then
            log_success "$name: healthy (JSON response valid)"
            return 0
        else
            log_warning "$name: responding but invalid JSON"
            return 1
        fi
    else
        log_error "$name: no response"
        return 1
    fi
}

# Print header
echo "======================================================================"
echo "📊 ARCHON INTEGRATION VALIDATION"
echo "======================================================================"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

# =============================================================================
# SERVICE HEALTH CHECKS
# =============================================================================
echo "🏥 Service Health"
echo "----------------------------------------------------------------------"

check_http_json_response "archon-intelligence" "$INTELLIGENCE_URL/health"
check_http_json_response "archon-bridge" "$BRIDGE_URL/health"
check_http_json_response "archon-search" "$SEARCH_URL/health"

echo ""

# =============================================================================
# DATA STORE CHECKS
# =============================================================================
echo "🔍 Data Stores"
echo "----------------------------------------------------------------------"

# Check Qdrant
QDRANT_CHECK=$(curl -f -s -m 5 "$QDRANT_URL/collections" 2>/dev/null || echo "")
if [ -n "$QDRANT_CHECK" ]; then
    # Try to get archon_vectors collection info
    COLLECTION_INFO=$(curl -f -s -m 5 "$QDRANT_URL/collections/archon_vectors" 2>/dev/null || echo "")

    if echo "$COLLECTION_INFO" | jq . > /dev/null 2>&1; then
        VECTOR_COUNT=$(echo "$COLLECTION_INFO" | jq -r '.result.points_count // 0')
        log_success "Qdrant (archon_vectors): $VECTOR_COUNT vectors indexed"
        verbose_log "Collection status: $(echo "$COLLECTION_INFO" | jq -r '.result.status // "unknown"')"
    else
        log_warning "Qdrant: collection 'archon_vectors' not found or invalid response"
    fi
else
    log_error "Qdrant: service unreachable"
fi

# Check Kafka/Redpanda topics
if docker ps --format '{{.Names}}' | grep -q "^${KAFKA_CONTAINER}$"; then
    TOPIC_COUNT=$(docker exec "$KAFKA_CONTAINER" rpk topic list 2>/dev/null | grep -c "dev.archon-intelligence" || echo "0")

    if [ "$TOPIC_COUNT" -gt 0 ]; then
        log_success "Kafka Topics: $TOPIC_COUNT topics available"

        if [ "$VERBOSE" = true ]; then
            verbose_log "Topic list:"
            docker exec "$KAFKA_CONTAINER" rpk topic list 2>/dev/null | grep "dev.archon-intelligence" | while read -r line; do
                verbose_log "  - $line"
            done
        fi
    else
        log_warning "Kafka Topics: no archon topics found"
    fi
else
    log_error "Kafka: container '$KAFKA_CONTAINER' not running"
fi

echo ""

# =============================================================================
# SEARCH FUNCTIONALITY
# =============================================================================
echo "🔎 Search Functionality"
echo "----------------------------------------------------------------------"

# Test RAG search with a simple query
SEARCH_TEST=$(curl -f -s -m 10 -X POST "$SEARCH_URL/search" \
    -H "Content-Type: application/json" \
    -d '{"query":"ONEX architecture","limit":5}' 2>/dev/null || echo "")

if [ -n "$SEARCH_TEST" ]; then
    if echo "$SEARCH_TEST" | jq . > /dev/null 2>&1; then
        # Check if we got results
        RESULT_COUNT=$(echo "$SEARCH_TEST" | jq -r '.total_results // 0')

        if [ "$RESULT_COUNT" -gt 0 ]; then
            log_success "Test Query: $RESULT_COUNT documents returned"

            if [ "$VERBOSE" = true ]; then
                verbose_log "Sample result titles:"
                echo "$SEARCH_TEST" | jq -r '.results[0:3][].title // "untitled"' 2>/dev/null | while read -r title; do
                    verbose_log "  - $title"
                done
            fi
        else
            log_warning "Test Query: succeeded but no results returned"
        fi
    else
        log_warning "Test Query: invalid JSON response"
    fi
else
    log_warning "Test Query: request failed"
fi

echo ""

# =============================================================================
# KAFKA CONSUMER STATUS
# =============================================================================
echo "📨 Kafka Consumer"
echo "----------------------------------------------------------------------"

if docker ps --format '{{.Names}}' | grep -q "^${KAFKA_CONTAINER}$"; then
    # Check consumer groups
    CONSUMER_GROUPS=$(docker exec "$KAFKA_CONTAINER" rpk group list 2>/dev/null || echo "")

    if [ -n "$CONSUMER_GROUPS" ]; then
        CONSUMER_COUNT=$(echo "$CONSUMER_GROUPS" | grep -c "archon" || echo "0")

        if [ "$CONSUMER_COUNT" -gt 0 ]; then
            log_success "Consumer Groups: $CONSUMER_COUNT active"

            if [ "$VERBOSE" = true ]; then
                verbose_log "Consumer groups:"
                echo "$CONSUMER_GROUPS" | grep "archon" | while read -r group; do
                    verbose_log "  - $group"
                done
            fi
        else
            log_warning "Consumer Groups: no archon consumers found"
        fi
    else
        log_warning "Consumer Groups: unable to list groups"
    fi

    # Check topic statistics
    TREE_DISCOVER_STATS=$(docker exec "$KAFKA_CONTAINER" rpk topic describe dev.archon-intelligence.tree.discover.v1 2>/dev/null || echo "")

    if [ -n "$TREE_DISCOVER_STATS" ]; then
        log_success "Topic Statistics: tree.discover.v1 available"

        if [ "$VERBOSE" = true ]; then
            verbose_log "Topic details:"
            echo "$TREE_DISCOVER_STATS" | head -n 10 | while read -r line; do
                verbose_log "  $line"
            done
        fi
    else
        log_warning "Topic Statistics: unable to describe tree.discover.v1"
    fi
else
    log_error "Kafka Consumer: container not running"
fi

echo ""

# =============================================================================
# SUMMARY
# =============================================================================
echo "======================================================================"
echo "📊 Summary"
echo "----------------------------------------------------------------------"
echo "Checks Passed: $CHECKS_PASSED"
echo "Checks Failed: $CHECKS_FAILED"
echo "Critical Failures: $CRITICAL_FAILURES"
echo ""

# Determine overall status
TOTAL_CHECKS=$((CHECKS_PASSED + CHECKS_FAILED))
SUCCESS_RATE=0

if [ "$TOTAL_CHECKS" -gt 0 ]; then
    SUCCESS_RATE=$((CHECKS_PASSED * 100 / TOTAL_CHECKS))
fi

if [ "$CRITICAL_FAILURES" -gt 0 ] || [ "$SUCCESS_RATE" -lt 50 ]; then
    echo -e "Overall Status: ${RED}UNHEALTHY${NC} (${SUCCESS_RATE}% success rate)"
    echo "======================================================================"
    exit 2
elif [ "$CHECKS_FAILED" -gt 0 ] || [ "$SUCCESS_RATE" -lt 80 ]; then
    echo -e "Overall Status: ${YELLOW}DEGRADED${NC} (${SUCCESS_RATE}% success rate)"
    echo "======================================================================"
    exit 1
else
    echo -e "Overall Status: ${GREEN}HEALTHY${NC} (${SUCCESS_RATE}% success rate)"
    echo "======================================================================"
    exit 0
fi
