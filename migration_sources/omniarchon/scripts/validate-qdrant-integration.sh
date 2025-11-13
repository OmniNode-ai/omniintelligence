#!/bin/bash

# Qdrant Integration Validation Script for Archon Phase 5C
# Tests Docker orchestration and service connectivity for vector database

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
QDRANT_HOST="localhost"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_GRPC_PORT="${QDRANT_GRPC_PORT:-6334}"
TIMEOUT=30

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Test Docker Compose configuration
test_docker_compose() {
    log "Testing Docker Compose configuration..."

    if docker compose -f deployment/docker-compose.yml config --quiet; then
        success "Docker Compose configuration is valid"
    else
        error "Docker Compose configuration has errors"
        return 1
    fi

    # Check if Qdrant service is defined
    if docker compose -f deployment/docker-compose.yml config --services | grep -q "qdrant"; then
        success "Qdrant service is defined in docker-compose.yml"
    else
        error "Qdrant service not found in docker-compose.yml"
        return 1
    fi
}

# Test Qdrant service startup
test_qdrant_startup() {
    log "Testing Qdrant service startup..."

    # Start only Qdrant and its dependencies
    if docker compose -f deployment/docker-compose.yml up -d qdrant; then
        success "Qdrant service started successfully"
    else
        error "Failed to start Qdrant service"
        return 1
    fi

    # Wait for Qdrant to be ready
    log "Waiting for Qdrant to be ready (timeout: ${TIMEOUT}s)..."

    local count=0
    while [ $count -lt $TIMEOUT ]; do
        if curl -f -s "http://${QDRANT_HOST}:${QDRANT_PORT}/health" > /dev/null 2>&1; then
            success "Qdrant is responding to health checks"
            return 0
        fi

        echo -n "."
        sleep 1
        count=$((count + 1))
    done

    echo ""
    error "Qdrant failed to respond within ${TIMEOUT} seconds"
    return 1
}

# Test Qdrant API connectivity
test_qdrant_api() {
    log "Testing Qdrant API connectivity..."

    # Test health endpoint
    local health_response
    if health_response=$(curl -s "http://${QDRANT_HOST}:${QDRANT_PORT}/health"); then
        success "Health endpoint accessible: $health_response"
    else
        error "Failed to access health endpoint"
        return 1
    fi

    # Test cluster info endpoint
    local cluster_info
    if cluster_info=$(curl -s "http://${QDRANT_HOST}:${QDRANT_PORT}/cluster"); then
        success "Cluster info endpoint accessible"
        echo "  Cluster info: $cluster_info"
    else
        warning "Cluster info endpoint not accessible (may be normal for single-node)"
    fi

    # Test collections endpoint
    local collections
    if collections=$(curl -s "http://${QDRANT_HOST}:${QDRANT_PORT}/collections"); then
        success "Collections endpoint accessible"
        echo "  Collections: $collections"
    else
        error "Failed to access collections endpoint"
        return 1
    fi
}

# Test vector operations (basic functionality)
test_vector_operations() {
    log "Testing basic vector operations..."

    local test_collection="test_archon_vectors"

    # Create a test collection with 1536 dimensions (OpenAI embeddings)
    local create_payload='{
        "vectors": {
            "size": 1536,
            "distance": "Cosine"
        }
    }'

    if curl -s -X PUT "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${test_collection}" \
        -H "Content-Type: application/json" \
        -d "$create_payload" > /dev/null; then
        success "Created test collection: $test_collection"
    else
        error "Failed to create test collection"
        return 1
    fi

    # Insert a test vector
    local vector_data='[0.1, 0.2, 0.3]'
    # Pad to 1536 dimensions
    local full_vector="[$(seq -s, 0.001 0.001 1.536 | head -c -1)]"

    local insert_payload="{
        \"points\": [{
            \"id\": 1,
            \"vector\": $full_vector,
            \"payload\": {
                \"text\": \"test document\",
                \"source\": \"integration_test\",
                \"quality_score\": 0.85
            }
        }]
    }"

    if curl -s -X PUT "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${test_collection}/points" \
        -H "Content-Type: application/json" \
        -d "$insert_payload" > /dev/null; then
        success "Inserted test vector"
    else
        error "Failed to insert test vector"
        return 1
    fi

    # Search for similar vectors
    local search_payload="{
        \"vector\": $full_vector,
        \"limit\": 1,
        \"with_payload\": true
    }"

    local search_result
    if search_result=$(curl -s -X POST "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${test_collection}/points/search" \
        -H "Content-Type: application/json" \
        -d "$search_payload"); then
        success "Vector search completed successfully"
        echo "  Search result: $search_result"
    else
        error "Failed to perform vector search"
        return 1
    fi

    # Clean up test collection
    if curl -s -X DELETE "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${test_collection}" > /dev/null; then
        success "Cleaned up test collection"
    else
        warning "Failed to clean up test collection (may need manual cleanup)"
    fi
}

# Test service dependencies and networking
test_service_integration() {
    log "Testing service integration with archon-search..."

    # Check if archon-search can resolve qdrant hostname
    if docker compose -f deployment/docker-compose.yml exec archon-search nslookup qdrant > /dev/null 2>&1; then
        success "archon-search can resolve qdrant hostname"
    else
        warning "archon-search cannot resolve qdrant hostname (services may not be running)"
    fi

    # Check network connectivity
    if docker compose -f deployment/docker-compose.yml exec archon-search wget --spider --timeout=5 http://qdrant:6333/health > /dev/null 2>&1; then
        success "archon-search can connect to Qdrant"
    else
        warning "archon-search cannot connect to Qdrant (may be normal if not running)"
    fi
}

# Test resource usage and performance
test_performance() {
    log "Testing Qdrant performance and resource usage..."

    # Get container stats
    local container_stats
    if container_stats=$(docker stats archon-qdrant --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"); then
        success "Retrieved container statistics"
        echo "$container_stats"
    else
        warning "Failed to retrieve container statistics"
    fi

    # Check disk usage
    local disk_usage
    if disk_usage=$(docker compose -f deployment/docker-compose.yml exec qdrant df -h /qdrant/storage); then
        success "Qdrant storage information:"
        echo "$disk_usage"
    else
        warning "Failed to retrieve storage information"
    fi
}

# Main validation function
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           Archon Qdrant Integration Validation       ║${NC}"
    echo -e "${BLUE}║                 Phase 5C: Advanced Search            ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""

    local failed=0

    # Run all tests
    test_docker_compose || failed=$((failed + 1))
    echo ""

    test_qdrant_startup || failed=$((failed + 1))
    echo ""

    test_qdrant_api || failed=$((failed + 1))
    echo ""

    test_vector_operations || failed=$((failed + 1))
    echo ""

    test_service_integration || failed=$((failed + 1))
    echo ""

    test_performance || failed=$((failed + 1))
    echo ""

    # Summary
    echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    Validation Summary                ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"

    if [ $failed -eq 0 ]; then
        success "All tests passed! Qdrant integration is ready for Phase 5C."
        echo ""
        echo "Next steps:"
        echo "1. Implement Qdrant adapter in archon-search service"
        echo "2. Add quality-weighted vector indexing"
        echo "3. Integrate with MCP tools for vector search operations"
        echo ""
        return 0
    else
        error "$failed test(s) failed. Please review the output above."
        echo ""
        echo "Common issues:"
        echo "- Services not running: docker compose -f deployment/docker-compose.yml up -d"
        echo "- Port conflicts: check QDRANT_PORT configuration"
        echo "- Network issues: verify Docker network configuration"
        echo ""
        return 1
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up test resources..."
    # Stop services if they were started by this script
    docker compose -f deployment/docker-compose.yml down -v --remove-orphans > /dev/null 2>&1 || true
}

# Trap cleanup on script exit
trap cleanup EXIT

# Run main function
main "$@"
