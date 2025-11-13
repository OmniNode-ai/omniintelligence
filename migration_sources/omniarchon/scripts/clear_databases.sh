#!/bin/bash
################################################################################
# Database Clear Script - Archon Intelligence Platform
################################################################################
#
# Purpose: Clear all data from Qdrant (vectors) and Memgraph (knowledge graph)
#          to enable fresh ingestion without stale data.
#
# Usage:
#   ./scripts/clear_databases.sh                  # Interactive (asks for confirmation)
#   ./scripts/clear_databases.sh --force          # Non-interactive (auto-confirms)
#   ./scripts/clear_databases.sh --dry-run        # Show what would be deleted (no action)
#
# What Gets Cleared:
#   - Qdrant: Deletes and recreates 'archon_vectors' collection (1536 dimensions)
#   - Memgraph: Deletes ALL nodes and relationships (DETACH DELETE)
#
# Exit Codes:
#   0 - Success
#   1 - Error (service unreachable, operation failed, user cancelled)
#
# Created: 2025-11-10
# ONEX Pattern: Orchestrator (infrastructure management CLI)
################################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_FILE="${PROJECT_ROOT}/logs/clear_databases_$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p "${PROJECT_ROOT}/logs"

# Default flags
DRY_RUN=false
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be deleted (no action taken)"
            echo "  --force      Skip confirmation prompts"
            echo "  -h, --help   Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

################################################################################
# Logging Function
################################################################################

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Log to file
    echo "[${timestamp}] [${level}] ${message}" >> "${LOG_FILE}"

    # Log to console with colors
    case ${level} in
        INFO)
            echo -e "${BLUE}ℹ${NC} ${message}"
            ;;
        SUCCESS)
            echo -e "${GREEN}✅${NC} ${message}"
            ;;
        WARNING)
            echo -e "${YELLOW}⚠${NC} ${message}"
            ;;
        ERROR)
            echo -e "${RED}❌${NC} ${message}"
            ;;
        *)
            echo "${message}"
            ;;
    esac
}

################################################################################
# Service Health Checks
################################################################################

check_qdrant() {
    log INFO "Checking Qdrant connectivity (localhost:6333)..."

    # Qdrant doesn't have /health endpoint, check root endpoint instead
    local response=$(curl -s http://localhost:6333/ 2>/dev/null)

    if echo "${response}" | grep -q "qdrant"; then
        log SUCCESS "Qdrant is reachable"
        return 0
    else
        log ERROR "Qdrant is not reachable at localhost:6333"
        log ERROR "Start services with: docker compose -f deployment/docker-compose.yml up -d"
        return 1
    fi
}

check_memgraph() {
    log INFO "Checking Memgraph connectivity (bolt://localhost:7687)..."

    # Check if memgraph container is running
    if docker ps --format '{{.Names}}' | grep -q "memgraph"; then
        log SUCCESS "Memgraph container is running"
        return 0
    else
        log ERROR "Memgraph container is not running"
        log ERROR "Start services with: docker compose up -d"
        return 1
    fi
}

################################################################################
# Clear Operations
################################################################################

clear_qdrant() {
    local collection="archon_vectors"
    local dimensions=1536

    log INFO "Clearing Qdrant collection: ${collection}"

    if [ "${DRY_RUN}" = true ]; then
        log WARNING "[DRY-RUN] Would delete collection: ${collection}"
        log WARNING "[DRY-RUN] Would recreate collection with ${dimensions} dimensions"
        return 0
    fi

    # Get current collection info (if exists)
    local collection_response=$(curl -s http://localhost:6333/collections/${collection})

    if echo "${collection_response}" | grep -q '"status":"ok"'; then
        log INFO "Collection exists. Checking vector count..."
        local count=$(curl -s http://localhost:6333/collections/${collection} | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('result', {}).get('points_count', 0))" 2>/dev/null || echo "0")
        log INFO "Current vector count: ${count}"

        # Delete existing collection
        log INFO "Deleting collection: ${collection}"
        local delete_response=$(curl -s -X DELETE http://localhost:6333/collections/${collection})

        if echo "${delete_response}" | grep -q '"status":"ok"'; then
            log SUCCESS "Collection deleted successfully"
        else
            log ERROR "Failed to delete collection"
            log ERROR "Response: ${delete_response}"
            return 1
        fi
    else
        log INFO "Collection does not exist (will create fresh)"
    fi

    # Recreate collection
    log INFO "Creating fresh collection: ${collection} (dimensions=${dimensions})"

    local create_response=$(curl -s -X PUT http://localhost:6333/collections/${collection} \
        -H "Content-Type: application/json" \
        -d "{
            \"vectors\": {
                \"size\": ${dimensions},
                \"distance\": \"Cosine\"
            },
            \"optimizers_config\": {
                \"indexing_threshold\": 10000
            }
        }")

    if echo "${create_response}" | grep -q '"status":"ok"'; then
        log SUCCESS "Collection created successfully (${dimensions} dimensions)"
    else
        log ERROR "Failed to create collection"
        log ERROR "Response: ${create_response}"
        return 1
    fi
}

clear_memgraph() {
    log INFO "Clearing Memgraph knowledge graph..."

    if [ "${DRY_RUN}" = true ]; then
        log WARNING "[DRY-RUN] Would execute: MATCH (n) DETACH DELETE n"
        return 0
    fi

    # Count nodes before deletion
    log INFO "Counting nodes before deletion..."
    local before_count=$(echo "MATCH (n) RETURN count(n) as count;" | \
        docker exec -i archon-memgraph mgconsole --use-ssl=false --output-format=csv 2>/dev/null | \
        tail -n 1 | tr -d '"' || echo "0")

    log INFO "Current node count: ${before_count}"

    # Delete all nodes and relationships
    log INFO "Executing: MATCH (n) DETACH DELETE n"
    echo "MATCH (n) DETACH DELETE n;" | \
        docker exec -i archon-memgraph mgconsole --use-ssl=false > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log SUCCESS "All nodes and relationships deleted"
    else
        log ERROR "Failed to delete nodes"
        return 1
    fi

    # Verify deletion
    log INFO "Verifying deletion..."
    local after_count=$(echo "MATCH (n) RETURN count(n) as count;" | \
        docker exec -i archon-memgraph mgconsole --use-ssl=false --output-format=csv 2>/dev/null | \
        tail -n 1 | tr -d '"' || echo "0")

    log INFO "Remaining node count: ${after_count}"

    if [ "${after_count}" -eq 0 ]; then
        log SUCCESS "Memgraph successfully cleared"
    else
        log WARNING "Memgraph may not be fully cleared (${after_count} nodes remaining)"
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    log INFO "================================================"
    log INFO "Archon Database Clear Script"
    log INFO "================================================"
    log INFO "Log file: ${LOG_FILE}"
    log INFO ""

    if [ "${DRY_RUN}" = true ]; then
        log WARNING "DRY-RUN MODE: No changes will be made"
        log INFO ""
    fi

    # Check service health
    log INFO "Step 1: Health Checks"
    log INFO "----------------------------"

    if ! check_qdrant; then
        exit 1
    fi

    if ! check_memgraph; then
        exit 1
    fi

    log INFO ""

    # Confirmation prompt (unless --force or --dry-run)
    if [ "${FORCE}" = false ] && [ "${DRY_RUN}" = false ]; then
        log WARNING "⚠️  WARNING: This will DELETE ALL DATA from:"
        log WARNING "    - Qdrant: All vectors in 'archon_vectors' collection"
        log WARNING "    - Memgraph: All nodes and relationships"
        log WARNING ""
        read -p "$(echo -e ${YELLOW}Type \'YES\' to continue:${NC} )" confirm

        if [ "${confirm}" != "YES" ]; then
            log WARNING "Operation cancelled by user"
            exit 1
        fi
        log INFO ""
    fi

    # Clear Qdrant
    log INFO "Step 2: Clear Qdrant"
    log INFO "----------------------------"

    if clear_qdrant; then
        log SUCCESS "Qdrant cleared successfully"
    else
        log ERROR "Failed to clear Qdrant"
        exit 1
    fi

    log INFO ""

    # Clear Memgraph
    log INFO "Step 3: Clear Memgraph"
    log INFO "----------------------------"

    if clear_memgraph; then
        log SUCCESS "Memgraph cleared successfully"
    else
        log ERROR "Failed to clear Memgraph"
        exit 1
    fi

    log INFO ""
    log INFO "================================================"

    if [ "${DRY_RUN}" = true ]; then
        log SUCCESS "DRY-RUN COMPLETE: No changes made"
    else
        log SUCCESS "DATABASE CLEAR COMPLETE"
        log INFO ""
        log INFO "Next Steps:"
        log INFO "  1. Run full repository ingestion:"
        log INFO "     python3 scripts/bulk_ingest_repository.py /Volumes/PRO-G40/Code/omniarchon \\"
        log INFO "       --project-name omniarchon \\"
        log INFO "       --kafka-servers 192.168.86.200:29092"
        log INFO ""
        log INFO "  2. Verify environment health:"
        log INFO "     python3 scripts/verify_environment.py --verbose"
    fi

    log INFO "================================================"
    log INFO "Log saved to: ${LOG_FILE}"
}

# Execute main function
main
