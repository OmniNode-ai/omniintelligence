#!/bin/bash
#
# Verify Invalid Event Detection Fix
#
# This script verifies that the invalid event detection and skipping
# feature is working correctly after deployment.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONSUMER_CONTAINER="archon-kafka-consumer"
HEALTH_PORT="8900"
METRICS_URL="http://localhost:${HEALTH_PORT}/metrics"
READY_URL="http://localhost:${HEALTH_PORT}/ready"
HEALTH_URL="http://localhost:${HEALTH_PORT}/health"

echo ""
echo "=========================================="
echo "Invalid Event Detection Verification"
echo "=========================================="
echo ""

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✅ OK${NC} - $message"
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}⚠️  WARN${NC} - $message"
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}❌ FAIL${NC} - $message"
    else
        echo -e "${BLUE}ℹ️  INFO${NC} - $message"
    fi
}

# Check if consumer container is running
echo "1. Checking consumer container status..."
if docker ps --filter "name=$CONSUMER_CONTAINER" --format "{{.Names}}" | grep -q "$CONSUMER_CONTAINER"; then
    print_status "OK" "Consumer container is running"
else
    print_status "FAIL" "Consumer container is not running"
    echo ""
    echo "Please start the consumer with:"
    echo "  docker compose restart $CONSUMER_CONTAINER"
    exit 1
fi

# Check health endpoint
echo ""
echo "2. Checking health endpoint..."
if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
    print_status "OK" "Health endpoint responding"
else
    print_status "FAIL" "Health endpoint not responding"
    exit 1
fi

# Check readiness endpoint
echo ""
echo "3. Checking consumer readiness..."
READY_RESPONSE=$(curl -s "$READY_URL")
READY_STATUS=$(echo "$READY_RESPONSE" | jq -r '.ready' 2>/dev/null || echo "false")

if [ "$READY_STATUS" = "true" ]; then
    print_status "OK" "Consumer is ready"
else
    print_status "WARN" "Consumer is not ready yet (may still be starting up)"
    echo "Response: $READY_RESPONSE"
fi

# Check if metrics endpoint includes invalid_events
echo ""
echo "4. Checking metrics endpoint for invalid_events..."
METRICS_RESPONSE=$(curl -s "$METRICS_URL")

if echo "$METRICS_RESPONSE" | jq -e '.invalid_events' > /dev/null 2>&1; then
    print_status "OK" "invalid_events metrics are exposed"

    TOTAL_SKIPPED=$(echo "$METRICS_RESPONSE" | jq -r '.invalid_events.total_skipped' 2>/dev/null || echo "0")
    echo "   Total invalid events skipped: $TOTAL_SKIPPED"

    if [ "$TOTAL_SKIPPED" -gt 0 ]; then
        print_status "INFO" "Invalid events have been detected and skipped"
        echo ""
        echo "   Breakdown by reason:"
        echo "$METRICS_RESPONSE" | jq -r '.invalid_events.by_reason | to_entries[] | "     - \(.key | .[0:80]): \(.value)"'
    else
        print_status "INFO" "No invalid events skipped yet"
    fi
else
    print_status "FAIL" "invalid_events metrics not found in response"
    echo "Response: $METRICS_RESPONSE"
    exit 1
fi

# Check consumer lag
echo ""
echo "5. Checking consumer lag..."
TOTAL_LAG=$(echo "$METRICS_RESPONSE" | jq -r '.consumer.total_lag' 2>/dev/null || echo "-1")

if [ "$TOTAL_LAG" -ge 0 ]; then
    if [ "$TOTAL_LAG" -eq 0 ]; then
        print_status "OK" "No consumer lag (caught up)"
    elif [ "$TOTAL_LAG" -lt 100 ]; then
        print_status "OK" "Low consumer lag: $TOTAL_LAG messages"
    elif [ "$TOTAL_LAG" -lt 500 ]; then
        print_status "WARN" "Moderate consumer lag: $TOTAL_LAG messages"
    else
        print_status "WARN" "High consumer lag: $TOTAL_LAG messages"
    fi
else
    print_status "INFO" "Consumer lag not available yet"
fi

# Check recent logs for invalid events
echo ""
echo "6. Checking recent logs for invalid event detections..."
INVALID_LOGS=$(docker logs --tail 100 "$CONSUMER_CONTAINER" 2>&1 | grep -c "invalid_event_schema_skipped" || echo "0")

if [ "$INVALID_LOGS" -gt 0 ]; then
    print_status "INFO" "Found $INVALID_LOGS invalid event log entries in recent logs"
    echo ""
    echo "   Recent invalid events:"
    docker logs --tail 100 "$CONSUMER_CONTAINER" 2>&1 | grep "invalid_event_schema_skipped" | tail -3 | while read -r line; do
        ERROR_MSG=$(echo "$line" | jq -r '.error' 2>/dev/null || echo "N/A")
        CORRELATION_ID=$(echo "$line" | jq -r '.correlation_id' 2>/dev/null || echo "N/A")
        echo "     - Error: ${ERROR_MSG:0:80}..."
        echo "       Correlation ID: $CORRELATION_ID"
    done
else
    print_status "INFO" "No invalid events detected in recent logs"
fi

# Check for error alerts
echo ""
echo "7. Checking for high invalid event count alerts..."
ALERT_LOGS=$(docker logs --tail 1000 "$CONSUMER_CONTAINER" 2>&1 | grep -c "high_invalid_event_count_alert" || echo "0")

if [ "$ALERT_LOGS" -gt 0 ]; then
    print_status "WARN" "Found $ALERT_LOGS high invalid event count alerts"
    echo "   This suggests a systemic issue with event producers"
else
    print_status "OK" "No high invalid event count alerts"
fi

# Summary
echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo ""

# Overall status
if [ "$READY_STATUS" = "true" ] && [ "$TOTAL_LAG" -lt 100 ]; then
    print_status "OK" "Consumer is healthy and processing events"
    echo ""
    echo "The invalid event detection feature is working correctly."
    echo "Invalid events are being automatically detected and skipped."
    echo ""
elif [ "$READY_STATUS" = "true" ]; then
    print_status "WARN" "Consumer is healthy but has some lag"
    echo ""
    echo "Monitor the consumer lag. If it continues to grow, investigate:"
    echo "  - Are invalid events causing the lag?"
    echo "  - Are there performance issues?"
    echo "  - Are producers sending too many events?"
    echo ""
else
    print_status "WARN" "Consumer is starting up or has issues"
    echo ""
    echo "Wait a few minutes for the consumer to fully start."
    echo "If issues persist, check the logs:"
    echo "  docker logs -f $CONSUMER_CONTAINER"
    echo ""
fi

# Next steps
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Monitor metrics endpoint for invalid events:"
echo "   curl $METRICS_URL | jq .invalid_events"
echo ""
echo "2. Watch logs for invalid event detections:"
echo "   docker logs -f $CONSUMER_CONTAINER | grep invalid_event_schema_skipped"
echo ""
echo "3. Set up alerting on high invalid event count (>100/hour)"
echo ""
echo "4. Review invalid event reasons weekly to identify patterns"
echo ""
echo "5. Fix producers sending invalid events (if needed)"
echo ""

# Documentation
echo "=========================================="
echo "Documentation"
echo "=========================================="
echo ""
echo "Full details: INVALID_EVENT_DETECTION_IMPLEMENTATION.md"
echo "Quick ref:    INVALID_EVENT_FIX_SUMMARY.md"
echo "Test script:  scripts/test_invalid_event_detection.py"
echo ""
