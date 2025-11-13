#!/bin/bash
#
# Create Kafka Topics for Async Intelligence Enrichment
#
# This script creates all required Kafka topics for the async event-driven
# intelligence enrichment architecture.
#
# Author: Archon Architecture Team
# Version: 1.0.0
# Date: 2025-10-30
# Related: docs/ASYNC_INTELLIGENCE_ARCHITECTURE.md

set -e

# Configuration
REDPANDA_HOST=${REDPANDA_HOST:-"omninode-bridge-redpanda"}
REDPANDA_CONTAINER=${REDPANDA_CONTAINER:-"omninode-bridge-redpanda"}
REPLICATION_FACTOR=${REPLICATION_FACTOR:-1}  # Single-node Redpanda uses replication=1

# Topic configurations
ENRICHMENT_TOPIC="dev.archon-intelligence.enrich-document.v1"
DLQ_TOPIC="dev.archon-intelligence.enrich-document-dlq.v1"
COMPLETED_TOPIC="dev.archon-intelligence.enrich-document-completed.v1"
PROGRESS_TOPIC="dev.archon-intelligence.enrichment-progress.v1"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "========================================"
echo "Creating Async Enrichment Kafka Topics"
echo "========================================"
echo ""

# Function to create topic
create_topic() {
    local topic_name=$1
    local partitions=$2
    local retention_ms=$3
    local compression=$4
    local cleanup_policy=${5:-"delete"}
    local replicas=${REPLICATION_FACTOR}

    echo -e "${YELLOW}Creating topic: ${topic_name}${NC}"
    echo "  Partitions: ${partitions}"
    echo "  Replication: ${replicas}"
    echo "  Retention: ${retention_ms}ms"
    echo "  Compression: ${compression}"
    echo "  Cleanup Policy: ${cleanup_policy}"

    # Check if topic exists
    if docker exec ${REDPANDA_CONTAINER} rpk topic list | grep -q "^${topic_name}"; then
        echo -e "${YELLOW}  ⚠️  Topic already exists, skipping...${NC}"
        echo ""
        return 0
    fi

    # Create topic
    docker exec ${REDPANDA_CONTAINER} rpk topic create "${topic_name}" \
        --partitions "${partitions}" \
        --replicas "${replicas}" \
        --config retention.ms="${retention_ms}" \
        --config compression.type="${compression}" \
        --config cleanup.policy="${cleanup_policy}"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✅ Topic created successfully${NC}"
    else
        echo -e "${RED}  ❌ Failed to create topic${NC}"
        exit 1
    fi
    echo ""
}

# 1. Create enrichment request topic
echo "1. Enrichment Request Topic"
echo "   Purpose: Queue of documents awaiting intelligence enrichment"
create_topic \
    "${ENRICHMENT_TOPIC}" \
    4 \
    604800000 \
    "snappy" \
    "delete"

# 2. Create Dead Letter Queue (DLQ) topic
echo "2. Dead Letter Queue (DLQ) Topic"
echo "   Purpose: Failed enrichment requests for manual intervention"
create_topic \
    "${DLQ_TOPIC}" \
    1 \
    2592000000 \
    "gzip" \
    "compact"

# 3. Create enrichment completed topic
echo "3. Enrichment Completed Topic"
echo "   Purpose: Notifications when enrichment completes"
create_topic \
    "${COMPLETED_TOPIC}" \
    4 \
    86400000 \
    "snappy" \
    "delete"

# 4. Create enrichment progress topic (optional)
echo "4. Enrichment Progress Topic (Optional)"
echo "   Purpose: Real-time progress updates for long-running enrichments"
create_topic \
    "${PROGRESS_TOPIC}" \
    4 \
    3600000 \
    "snappy" \
    "delete"

# Verification
echo "========================================"
echo "Verification"
echo "========================================"
echo ""

echo "Listing all enrichment topics:"
docker exec ${REDPANDA_CONTAINER} rpk topic list | grep "enrich-document"
echo ""

echo "Topic details:"
for topic in "${ENRICHMENT_TOPIC}" "${DLQ_TOPIC}" "${COMPLETED_TOPIC}" "${PROGRESS_TOPIC}"; do
    echo ""
    echo -e "${YELLOW}Topic: ${topic}${NC}"
    docker exec ${REDPANDA_CONTAINER} rpk topic describe "${topic}" | head -20
done

echo ""
echo -e "${GREEN}========================================"
echo "✅ All topics created successfully!"
echo "========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Update bridge service configuration (.env)"
echo "  2. Deploy intelligence consumer service"
echo "  3. Enable async enrichment feature flag"
echo ""
echo "See: docs/ASYNC_INTELLIGENCE_QUICK_START.md"
