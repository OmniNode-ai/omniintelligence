#!/bin/bash
# Run bulk ingestion on the remote Docker host where Redpanda is accessible
#
# This script SSH's to 192.168.86.200 and runs ingestion from there,
# where the Kafka internal network is accessible.

set -e

REMOTE_HOST="192.168.86.200"
PROJECT_PATH="/Volumes/PRO-G40/Code/omniarchon"
PROJECT_NAME="omniarchon"
BATCH_SIZE="${1:-50}"

echo "=========================================="
echo "Remote Bulk Ingestion via SSH"
echo "=========================================="
echo "Remote host: $REMOTE_HOST"
echo "Project: $PROJECT_NAME"
echo "Path: $PROJECT_PATH"
echo "Batch size: $BATCH_SIZE"
echo ""

# Check if SSH is available
if ! command -v ssh &> /dev/null; then
    echo "Error: ssh command not found"
    exit 1
fi

# Check if path exists locally (assuming it's NFS mounted on both machines)
if [ ! -d "$PROJECT_PATH" ]; then
    echo "Error: Project path does not exist: $PROJECT_PATH"
    exit 1
fi

echo "Running bulk ingestion on remote host..."
echo ""

# Run the ingestion via SSH
ssh "$REMOTE_HOST" "cd '$PROJECT_PATH' && python3 scripts/bulk_ingest_repository.py '$PROJECT_PATH' \
  --project-name '$PROJECT_NAME' \
  --batch-size $BATCH_SIZE \
  --kafka-servers omninode-bridge-redpanda:9092 \
  --verbose"

echo ""
echo "=========================================="
echo "Ingestion completed!"
echo "=========================================="
