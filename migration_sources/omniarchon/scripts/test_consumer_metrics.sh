#!/bin/bash
#
# Test script for intelligence-consumer metrics endpoint
# Verifies that consumer lag metrics include topic-partition details
#

set -e

CONSUMER_PORT="${CONSUMER_PORT:-8063}"
BASE_URL="http://localhost:${CONSUMER_PORT}"

echo "==================================="
echo "Consumer Metrics Verification Test"
echo "==================================="
echo ""

# Check if service is running
echo "1. Checking if consumer service is running..."
if ! docker ps --filter "name=archon-intelligence-consumer" --format "{{.Names}}" | grep -q "archon-intelligence-consumer"; then
    echo "❌ ERROR: archon-intelligence-consumer is not running"
    exit 1
fi
echo "✅ Service is running"
echo ""

# Check health endpoint
echo "2. Checking health endpoint..."
HEALTH_RESPONSE=$(curl -s "${BASE_URL}/health")
if [ -z "$HEALTH_RESPONSE" ]; then
    echo "❌ ERROR: Health endpoint not responding"
    exit 1
fi

HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status')
if [ "$HEALTH_STATUS" != "healthy" ]; then
    echo "❌ ERROR: Service not healthy: $HEALTH_STATUS"
    exit 1
fi
echo "✅ Health endpoint OK (status: $HEALTH_STATUS)"
echo ""

# Check readiness endpoint
echo "3. Checking readiness endpoint..."
READY_RESPONSE=$(curl -s "${BASE_URL}/ready")
READY_STATUS=$(echo "$READY_RESPONSE" | jq -r '.ready')
if [ "$READY_STATUS" != "true" ]; then
    echo "⚠️  WARNING: Service not ready"
    echo "$READY_RESPONSE" | jq
else
    echo "✅ Readiness OK"
fi
echo ""

# Check metrics endpoint
echo "4. Checking metrics endpoint..."
METRICS_RESPONSE=$(curl -s "${BASE_URL}/metrics")
if [ -z "$METRICS_RESPONSE" ]; then
    echo "❌ ERROR: Metrics endpoint not responding"
    exit 1
fi
echo "✅ Metrics endpoint responding"
echo ""

# Validate lag_by_partition format
echo "5. Validating lag_by_partition format..."
LAG_DATA=$(echo "$METRICS_RESPONSE" | jq -r '.consumer.lag_by_partition')

if [ "$LAG_DATA" == "null" ] || [ "$LAG_DATA" == "{}" ]; then
    echo "⚠️  WARNING: No lag data available (consumer may be starting)"
else
    # Check if partition keys include topic names
    SAMPLE_KEY=$(echo "$METRICS_RESPONSE" | jq -r '.consumer.lag_by_partition | keys[0]')

    if [[ "$SAMPLE_KEY" == *"-"* ]]; then
        echo "✅ Partition keys include topic names"
        echo "   Sample key: $SAMPLE_KEY"
    else
        echo "❌ ERROR: Partition keys are numbers only (old format)"
        echo "   Sample key: $SAMPLE_KEY"
        exit 1
    fi
fi
echo ""

# Check all metric fields
echo "6. Checking metric structure..."
REQUIRED_FIELDS=("service" "uptime_seconds" "consumer" "errors" "circuit_breaker" "timestamp")
for field in "${REQUIRED_FIELDS[@]}"; do
    VALUE=$(echo "$METRICS_RESPONSE" | jq -r ".$field")
    if [ "$VALUE" == "null" ]; then
        echo "❌ ERROR: Missing field: $field"
        exit 1
    fi
    echo "✅ Field present: $field"
done
echo ""

# Display full metrics
echo "7. Full metrics output:"
echo "----------------------"
echo "$METRICS_RESPONSE" | jq
echo ""

# Summary
echo "==================================="
echo "✅ All metrics tests passed!"
echo "==================================="
echo ""
echo "Key Metrics:"
PARTITION_COUNT=$(echo "$METRICS_RESPONSE" | jq -r '.consumer.partition_count')
TOTAL_LAG=$(echo "$METRICS_RESPONSE" | jq -r '.consumer.total_lag')
ACTIVE_RETRIES=$(echo "$METRICS_RESPONSE" | jq -r '.errors.active_retries')
CIRCUIT_STATE=$(echo "$METRICS_RESPONSE" | jq -r '.circuit_breaker.state')

echo "  • Partitions: $PARTITION_COUNT"
echo "  • Total lag: $TOTAL_LAG"
echo "  • Active retries: $ACTIVE_RETRIES"
echo "  • Circuit breaker: $CIRCUIT_STATE"
echo ""

if [ "$LAG_DATA" != "null" ] && [ "$LAG_DATA" != "{}" ]; then
    echo "Per-Partition Lag:"
    echo "$METRICS_RESPONSE" | jq -r '.consumer.lag_by_partition | to_entries[] | "  • \(.key): \(.value)"'
fi
