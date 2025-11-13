#!/bin/bash

# Monitor Handler Processing Script
#
# Monitors Kafka event handlers in the intelligence service
# Displays handler activity in real-time
#
# Usage:
#   ./scripts/monitor_handler_processing.sh
#   ./scripts/monitor_handler_processing.sh --follow
#   ./scripts/monitor_handler_processing.sh --tail 100

set -e

# Default values
FOLLOW=false
TAIL_LINES=50
SERVICE_NAME="archon-intelligence"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -t|--tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Monitor Kafka event handler processing in Archon Intelligence service"
            echo ""
            echo "Options:"
            echo "  -f, --follow         Follow log output (like tail -f)"
            echo "  -t, --tail N         Show last N lines (default: 50)"
            echo "  -s, --service NAME   Service name (default: archon-intelligence)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --follow"
            echo "  $0 --tail 100"
            echo "  $0 --service archon-kafka-consumer --follow"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "======================================================================"
echo "🔍 MONITORING HANDLER PROCESSING"
echo "======================================================================"
echo "Service: $SERVICE_NAME"
echo "Follow Mode: $FOLLOW"
echo "Tail Lines: $TAIL_LINES"
echo "======================================================================"
echo ""

# Check if service is running
if ! docker ps --format '{{.Names}}' | grep -q "^${SERVICE_NAME}$"; then
    echo "❌ Error: Service '$SERVICE_NAME' is not running"
    echo ""
    echo "Available services:"
    docker ps --format 'table {{.Names}}\t{{.Status}}'
    exit 1
fi

echo "✅ Service '$SERVICE_NAME' is running"
echo ""

# Function to highlight important log patterns
highlight_logs() {
    grep --line-buffered -E "(validation|analysis|pattern|mixin|correlation_id|handler|event|ERROR|WARNING|INFO)" --color=always
}

# Function to filter handler-related logs
filter_handler_logs() {
    grep --line-buffered -iE "(handler|event.*process|correlation|kafka|consume|publish|response)" --color=always
}

echo "📋 Recent Handler Activity (last $TAIL_LINES lines):"
echo "----------------------------------------------------------------------"

if [ "$FOLLOW" = true ]; then
    echo "Following logs (Ctrl+C to stop)..."
    echo ""

    # Follow logs with filtering and highlighting
    docker compose logs -f --tail "$TAIL_LINES" "$SERVICE_NAME" 2>&1 | filter_handler_logs | highlight_logs
else
    # Show recent logs with filtering and highlighting
    docker compose logs --tail "$TAIL_LINES" "$SERVICE_NAME" 2>&1 | filter_handler_logs | highlight_logs

    echo ""
    echo "----------------------------------------------------------------------"
    echo "💡 Tip: Use --follow to watch logs in real-time"
    echo "💡 Tip: Use --tail N to show more/fewer lines"
fi

echo ""
echo "======================================================================"
echo "Monitor Complete"
echo "======================================================================"
