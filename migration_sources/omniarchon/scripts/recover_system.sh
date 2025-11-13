#!/bin/bash
#
# Polymorphic Agent - System Recovery Orchestration
# Purpose: Coordinate multi-service recovery from intelligence service overload
#
# ONEX Pattern: Orchestrator (workflow coordination with comprehensive recovery)
# Created: 2025-11-01
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_polly() {
    echo -e "${PURPLE}[POLLY]${NC} $*"
}

log_section() {
    echo ""
    echo "=================================================================="
    echo "$*"
    echo "=================================================================="
}

# Main recovery workflow
main() {
    log_section "POLYMORPHIC AGENT - SYSTEM RECOVERY ORCHESTRATION"
    log_polly "Analyzing system state and coordinating recovery..."

    # Phase 1: Stop consumers to prevent new load
    log_section "PHASE 1: STOP CONSUMERS"
    log_info "Stopping all intelligence consumers..."

    for i in {1..4}; do
        log_info "Stopping consumer $i..."
        docker stop archon-intelligence-consumer-$i
    done

    log_success "All consumers stopped"
    sleep 2

    # Phase 2: Restart Memgraph to clear connection pool
    log_section "PHASE 2: RESTART MEMGRAPH"
    log_warning "Restarting Memgraph to clear connection pool exhaustion..."

    docker restart archon-memgraph
    log_info "Waiting 10 seconds for Memgraph to initialize..."
    sleep 10

    # Verify Memgraph health
    if docker exec archon-memgraph mgconsole --host localhost --port 7687 -e "RETURN 1;" &>/dev/null; then
        log_success "Memgraph is healthy"
    else
        log_warning "Memgraph health check failed (may still be starting)"
    fi

    # Phase 3: Restart intelligence service
    log_section "PHASE 3: RESTART INTELLIGENCE SERVICE"
    log_warning "Restarting intelligence service to clear overload state..."

    docker restart archon-intelligence
    log_info "Waiting 15 seconds for intelligence service to initialize..."
    sleep 15

    # Verify intelligence service health
    if curl -f -s http://localhost:8053/health &>/dev/null; then
        log_success "Intelligence service is healthy"
    else
        log_error "Intelligence service health check failed"
        return 1
    fi

    # Phase 4: Restart consumers
    log_section "PHASE 4: RESTART CONSUMERS"
    log_info "Restarting consumers with fresh state..."

    for i in {1..4}; do
        log_info "Starting consumer $i..."
        docker start archon-intelligence-consumer-$i
    done

    log_success "All consumers restarted"
    sleep 5

    # Phase 5: Verification
    log_section "PHASE 5: SYSTEM VERIFICATION"

    log_info "Checking service health..."

    # Check Memgraph
    if docker ps | grep -q "archon-memgraph.*healthy"; then
        log_success "✓ Memgraph: healthy"
    else
        log_warning "⚠ Memgraph: unhealthy or starting"
    fi

    # Check Intelligence
    if curl -f -s http://localhost:8053/health &>/dev/null; then
        log_success "✓ Intelligence service: healthy"
    else
        log_error "✗ Intelligence service: unhealthy"
    fi

    # Check Consumers
    running_consumers=$(docker ps | grep -c "archon-intelligence-consumer" || true)
    log_info "Consumers running: $running_consumers/4"

    if [[ $running_consumers -eq 4 ]]; then
        log_success "✓ All consumers running"
    else
        log_warning "⚠ Only $running_consumers/4 consumers running"
    fi

    # Check Qdrant
    if curl -f -s http://localhost:6333/collections/archon_vectors &>/dev/null; then
        vector_count=$(curl -s http://localhost:6333/collections/archon_vectors | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "unknown")
        log_success "✓ Qdrant: healthy ($vector_count vectors)"
    else
        log_error "✗ Qdrant: unhealthy"
    fi

    log_section "RECOVERY COMPLETE"
    log_polly "System recovery orchestration finished"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Monitor consumer logs: docker logs -f archon-intelligence-consumer-1"
    log_info "  2. Watch Qdrant vector count: curl -s http://localhost:6333/collections/archon_vectors | python3 -m json.tool | grep points_count"
    log_info "  3. Check for processing errors: docker logs archon-intelligence-consumer-1 --tail 50 | grep error"
    log_info ""
    log_warning "NOTE: If issues persist, consider:"
    log_warning "  - Reducing consumer parallelism (fewer workers)"
    log_warning "  - Increasing intelligence service timeout"
    log_warning "  - Scaling Memgraph resources"
}

# Run main workflow
main "$@"
