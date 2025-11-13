#!/bin/bash
#
# Kafka Topic Recreation Script
# Purpose: Fix UnknownTopicOrPartitionError by recreating topic with correct configuration
#
# ONEX Pattern: Effect (external I/O operations with fail-fast validation)
# Created: 2025-11-01
#

set -euo pipefail

# Configuration
REDPANDA_HOST="192.168.86.200"
TOPIC_NAME="dev.archon-intelligence.enrich-document.v1"
PARTITIONS=4
REPLICATION_FACTOR=1
CONSUMER_GROUP="archon-intelligence-consumer-group"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_section() {
    echo ""
    echo "=================================================================="
    echo "$*"
    echo "=================================================================="
}

# Execute command on remote Redpanda
exec_rpk() {
    ssh jonah@${REDPANDA_HOST} "/usr/local/bin/docker exec omninode-bridge-redpanda rpk $*"
}

# Main workflow
main() {
    log_section "KAFKA TOPIC RECREATION WORKFLOW"
    log_info "Topic: ${TOPIC_NAME}"
    log_info "Remote Redpanda: ${REDPANDA_HOST}"

    # Step 1: Check current topic status
    log_section "STEP 1: INSPECT CURRENT TOPIC"
    log_info "Checking if topic exists..."

    if exec_rpk topic list | grep -q "${TOPIC_NAME}"; then
        log_warning "Topic exists - describing current configuration..."
        exec_rpk topic describe "${TOPIC_NAME}" || true

        # Step 2: Delete existing topic
        log_section "STEP 2: DELETE EXISTING TOPIC"
        log_warning "Deleting topic ${TOPIC_NAME}..."

        if exec_rpk topic delete "${TOPIC_NAME}"; then
            log_success "Topic deleted successfully"
        else
            log_error "Failed to delete topic"
            return 1
        fi
    else
        log_info "Topic does not exist - will create new"
    fi

    # Step 3: Create topic with correct configuration
    log_section "STEP 3: CREATE TOPIC"
    log_info "Creating topic with ${PARTITIONS} partitions..."

    if exec_rpk topic create "${TOPIC_NAME}" \
        --partitions ${PARTITIONS} \
        --replicas ${REPLICATION_FACTOR}; then
        log_success "Topic created successfully"
    else
        log_error "Failed to create topic"
        return 1
    fi

    # Step 4: Verify topic creation
    log_section "STEP 4: VERIFY TOPIC"
    log_info "Describing new topic configuration..."
    exec_rpk topic describe "${TOPIC_NAME}"

    # Step 5: Reset consumer group
    log_section "STEP 5: RESET CONSUMER GROUP"
    log_info "Checking consumer group: ${CONSUMER_GROUP}..."

    if exec_rpk group list | grep -q "${CONSUMER_GROUP}"; then
        log_warning "Consumer group exists - deleting to reset offsets..."

        if exec_rpk group delete "${CONSUMER_GROUP}"; then
            log_success "Consumer group deleted"
        else
            log_warning "Failed to delete consumer group (may not exist)"
        fi
    else
        log_info "Consumer group does not exist - will be created on first consume"
    fi

    # Step 6: Verification summary
    log_section "STEP 6: FINAL VERIFICATION"
    log_info "Listing all topics..."
    exec_rpk topic list | grep "archon-intelligence" || true

    log_info "Listing consumer groups..."
    exec_rpk group list | grep "archon" || true

    log_section "TOPIC RECREATION COMPLETE"
    log_success "Topic ${TOPIC_NAME} is ready"
    log_success "Partitions: ${PARTITIONS}"
    log_success "Consumer group reset"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Restart consumer containers: docker restart archon-intelligence-consumer-{1..4}"
    log_info "  2. Monitor consumer logs for successful consumption"
    log_info "  3. Verify Qdrant vector count increases"
}

# Run main workflow
main "$@"
