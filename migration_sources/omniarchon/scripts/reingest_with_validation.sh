#!/bin/bash
#
# Re-ingestion Workflow with Fail-Fast Infrastructure Validation
#
# Purpose: Sequential repository re-ingestion with comprehensive pre-flight checks
#          and post-ingestion verification to prevent false success reports.
#
# Usage:
#   ./scripts/reingest_with_validation.sh REPO1 REPO2 REPO3 ...
#
# Example:
#   ./scripts/reingest_with_validation.sh /path/to/repo1 /path/to/repo2
#
# Exit Codes:
#   0 - Success (all repositories ingested and verified)
#   1 - Infrastructure failure (Redpanda, services down)
#   2 - Partial failure (some repositories failed)
#   3 - Complete failure (all repositories failed)
#
# Created: 2025-11-01
# ONEX Pattern: Effect (external I/O with comprehensive validation)
#

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/bulk_ingest_repository.py"

# Load environment variables from .env
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    log_error "FATAL: .env file not found at $PROJECT_ROOT/.env"
    exit 1
fi

# Kafka/Redpanda configuration (from .env with fallback)
REDPANDA_HOST="${POSTGRES_HOST:-192.168.86.200}"
REDPANDA_PORT="${KAFKA_BOOTSTRAP_SERVERS##*:}"
REDPANDA_PORT="${REDPANDA_PORT:-9092}"

# Local service ports (from .env with fallback)
INTELLIGENCE_PORT="${INTELLIGENCE_SERVICE_PORT:-8053}"
BRIDGE_PORT="${BRIDGE_SERVICE_PORT:-8054}"
SEARCH_PORT="${SEARCH_SERVICE_PORT:-8055}"

# Qdrant configuration (from .env with fallback)
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION_NAME="archon_vectors"

# Minimum expected documents after ingestion
MIN_EXPECTED_DOCS=100

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# Logging Functions
# ==============================================================================

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

log_section() {
    echo ""
    echo "=================================================================="
    echo "$*"
    echo "=================================================================="
}

# ==============================================================================
# Infrastructure Validation Functions
# ==============================================================================

check_redpanda_connectivity() {
    log_info "Checking Redpanda connectivity at ${REDPANDA_HOST}:${REDPANDA_PORT}..."

    if ! nc -zv "$REDPANDA_HOST" "$REDPANDA_PORT" 2>&1 | grep -q "succeeded"; then
        log_error "FATAL: Cannot connect to Redpanda at ${REDPANDA_HOST}:${REDPANDA_PORT}"
        log_error "       Redpanda must be running before ingestion"
        log_error "       Verify Redpanda status on remote server"
        return 1
    fi

    log_success "Redpanda connectivity verified"
    return 0
}

check_redpanda_health() {
    log_info "Checking Redpanda cluster health..."

    # Try to connect to Redpanda container on remote host via SSH
    if ! ssh -o ConnectTimeout=5 jonah@"$REDPANDA_HOST" \
        "docker exec omninode-bridge-redpanda rpk cluster health" &>/dev/null; then
        log_warning "Could not verify Redpanda cluster health via SSH"
        log_warning "Continuing with connectivity check only"
        return 0
    fi

    log_success "Redpanda cluster is healthy"
    return 0
}

check_local_service() {
    local service_name="$1"
    local port="$2"

    log_info "Checking $service_name health (port $port)..."

    if ! curl -f -s -o /dev/null -w "%{http_code}" "http://localhost:$port/health" | grep -q "200"; then
        log_error "FATAL: $service_name on port $port is not healthy"
        log_error "       Service must be running before ingestion"
        log_error "       Run: docker compose up -d"
        return 1
    fi

    log_success "$service_name is healthy"
    return 0
}

check_qdrant_health() {
    log_info "Checking Qdrant health..."

    if ! curl -f -s "$QDRANT_URL/collections" &>/dev/null; then
        log_error "FATAL: Qdrant is not accessible at $QDRANT_URL"
        log_error "       Qdrant must be running before ingestion"
        return 1
    fi

    log_success "Qdrant is healthy"
    return 0
}

get_qdrant_document_count() {
    local count
    count=$(curl -s "$QDRANT_URL/collections/$COLLECTION_NAME" | \
            python3 -c "import sys, json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "0")
    echo "$count"
}

check_python_script_exists() {
    log_info "Checking Python ingestion script..."

    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        log_error "FATAL: Python ingestion script not found at $PYTHON_SCRIPT"
        return 1
    fi

    log_success "Python script found at $PYTHON_SCRIPT"
    return 0
}

# ==============================================================================
# Pre-Flight Infrastructure Validation
# ==============================================================================

run_preflight_checks() {
    log_section "PHASE 0: PRE-FLIGHT INFRASTRUCTURE VALIDATION"

    local failed=0

    # Check Redpanda connectivity
    if ! check_redpanda_connectivity; then
        ((failed++))
    fi

    # Check Redpanda health
    if ! check_redpanda_health; then
        log_warning "Redpanda health check failed (non-fatal)"
    fi

    # Check local services
    if ! check_local_service "Intelligence Service" "$INTELLIGENCE_PORT"; then
        ((failed++))
    fi

    if ! check_local_service "Bridge Service" "$BRIDGE_PORT"; then
        ((failed++))
    fi

    if ! check_local_service "Search Service" "$SEARCH_PORT"; then
        ((failed++))
    fi

    # Check Qdrant
    if ! check_qdrant_health; then
        ((failed++))
    fi

    # Check Python script
    if ! check_python_script_exists; then
        ((failed++))
    fi

    # Summary
    echo ""
    if [[ $failed -eq 0 ]]; then
        log_success "All pre-flight checks passed"
        return 0
    else
        log_error "FATAL: $failed pre-flight check(s) failed"
        log_error "       Fix infrastructure issues before proceeding"
        return 1
    fi
}

# ==============================================================================
# Repository Ingestion
# ==============================================================================

ingest_repository() {
    local repo_path="$1"
    local project_name

    # Extract project name from path
    project_name=$(basename "$repo_path")

    log_section "INGESTING: $project_name"
    log_info "Repository: $repo_path"

    # Check if repository exists
    if [[ ! -d "$repo_path" ]]; then
        log_error "Repository not found: $repo_path"
        return 1
    fi

    # Get initial Qdrant count
    local initial_count
    initial_count=$(get_qdrant_document_count)
    log_info "Qdrant documents before ingestion: $initial_count"

    # Run ingestion script
    log_info "Starting ingestion..."
    if ! python3 "$PYTHON_SCRIPT" "$repo_path" \
        --project-name "$project_name" \
        --kafka-servers "${REDPANDA_HOST}:${REDPANDA_PORT}"; then
        log_error "Ingestion script failed for $project_name"
        return 1
    fi

    # Wait for processing (give consumer time to process events)
    log_info "Waiting 30 seconds for event processing..."
    sleep 30

    # Get final Qdrant count
    local final_count
    final_count=$(get_qdrant_document_count)
    log_info "Qdrant documents after ingestion: $final_count"

    # Verify document count increased
    local new_docs=$((final_count - initial_count))
    if [[ $new_docs -le 0 ]]; then
        log_error "FATAL: No new documents added to Qdrant"
        log_error "       Expected increase, got: $new_docs"
        log_error "       This indicates ingestion FAILED"
        return 1
    fi

    log_success "Successfully ingested $project_name ($new_docs new documents)"
    return 0
}

# ==============================================================================
# Post-Ingestion Verification
# ==============================================================================

run_final_verification() {
    local total_expected="$1"

    log_section "PHASE 3: FINAL VERIFICATION"

    # Get final document count
    local final_count
    final_count=$(get_qdrant_document_count)
    log_info "Total documents in Qdrant: $final_count"
    log_info "Expected minimum: $MIN_EXPECTED_DOCS"

    if [[ $final_count -lt $MIN_EXPECTED_DOCS ]]; then
        log_error "FATAL: Only $final_count documents in Qdrant (expected minimum: $MIN_EXPECTED_DOCS)"
        log_error "       Ingestion FAILED - investigate immediately"
        return 1
    fi

    # Verify all services still healthy
    log_info "Verifying all services still healthy..."

    if ! check_local_service "Intelligence Service" "$INTELLIGENCE_PORT"; then
        log_warning "Intelligence service became unhealthy during ingestion"
    fi

    if ! check_local_service "Bridge Service" "$BRIDGE_PORT"; then
        log_warning "Bridge service became unhealthy during ingestion"
    fi

    if ! check_local_service "Search Service" "$SEARCH_PORT"; then
        log_warning "Search service became unhealthy during ingestion"
    fi

    log_success "Final verification complete - $final_count documents indexed"
    return 0
}

# ==============================================================================
# Main Workflow
# ==============================================================================

main() {
    # Handle help flag
    if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        echo "Usage: $0 REPO1 [REPO2 REPO3 ...]"
        echo ""
        echo "Example:"
        echo "  $0 /path/to/repo1 /path/to/repo2"
        echo ""
        echo "This script performs sequential re-ingestion with comprehensive validation."
        echo ""
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "Exit Codes:"
        echo "  0 - Success (all repositories ingested)"
        echo "  1 - Infrastructure failure (pre-flight checks failed)"
        echo "  2 - Partial failure (some repositories failed)"
        echo "  3 - Complete failure (all repositories failed)"
        exit 0
    fi

    local repositories=("$@")
    local total_repos=${#repositories[@]}
    local successful=0
    local failed=0

    log_section "SEQUENTIAL RE-INGESTION WORKFLOW"
    log_info "Total repositories: $total_repos"
    log_info "Repositories to ingest:"
    for repo in "${repositories[@]}"; do
        log_info "  - $(basename "$repo")"
    done

    # Phase 0: Pre-flight checks
    if ! run_preflight_checks; then
        log_error "Pre-flight checks failed - aborting workflow"
        exit 1
    fi

    # Phase 1: Sequential ingestion
    log_section "PHASE 1: SEQUENTIAL REPOSITORY INGESTION"

    for repo in "${repositories[@]}"; do
        if ingest_repository "$repo"; then
            ((successful++))
        else
            ((failed++))
            log_warning "Failed to ingest $(basename "$repo") - continuing with next repository"
        fi
    done

    # Phase 2: Results summary
    log_section "PHASE 2: RESULTS SUMMARY"
    log_info "Total repositories: $total_repos"
    log_info "Successful: $successful"
    log_info "Failed: $failed"

    # Phase 3: Final verification
    if ! run_final_verification "$total_repos"; then
        log_error "Final verification failed"
        exit 3
    fi

    # Determine exit code
    if [[ $failed -eq 0 ]]; then
        log_success "All repositories ingested successfully!"
        exit 0
    elif [[ $successful -gt 0 ]]; then
        log_warning "Partial success: $successful succeeded, $failed failed"
        exit 2
    else
        log_error "Complete failure: all repositories failed"
        exit 3
    fi
}

# Run main workflow
main "$@"
