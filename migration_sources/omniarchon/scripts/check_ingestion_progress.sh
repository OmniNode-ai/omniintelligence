#!/bin/bash
# Quick progress check for Kafka ingestion
# Usage: ./scripts/check_ingestion_progress.sh

TARGET=22130

# Get vector count
VECTORS=$(curl -s http://localhost:6333/collections/archon_vectors | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "0")

# Get node count
NODES=$(docker exec -i archon-memgraph mgconsole << 'EOF' 2>/dev/null | grep -E "^\| [0-9]" | awk '{print $2}'
MATCH (n) RETURN count(n) as total_nodes;
EOF
)

# Calculate percentage
PERCENT=$(python3 -c "print(f'{($VECTORS / $TARGET * 100):.1f}')" 2>/dev/null || echo "0")

# Get recent activity
RECENT=$(docker logs archon-intelligence-consumer-1 --since 5m --tail 50 2>/dev/null | \
    grep -c "batch_file_processing_succeeded" || echo "0")

# Display status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Ingestion Progress - $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Vectors:   ${VECTORS} / ${TARGET} (${PERCENT}%)"
echo "Nodes:     ${NODES}"
echo "Activity:  ${RECENT} completions (last 5 min)"

# Progress bar
BARS=$(python3 -c "print('█' * int($VECTORS / $TARGET * 50))" 2>/dev/null || echo "")
SPACES=$(python3 -c "print('░' * (50 - int($VECTORS / $TARGET * 50)))" 2>/dev/null || echo "")
echo "Progress:  [${BARS}${SPACES}] ${PERCENT}%"

# Check if complete
if [ "$VECTORS" -ge "$TARGET" ]; then
    echo ""
    echo "✅ PROCESSING COMPLETE!"
    echo "Run: python3 scripts/verify_environment.py --verbose"
else
    # Calculate ETA (assuming ~2 vectors/second average rate)
    if [ "$VECTORS" -gt 0 ]; then
        REMAINING=$(($TARGET - $VECTORS))
        ETA_SECONDS=$(($REMAINING / 2))
        ETA_MINUTES=$(($ETA_SECONDS / 60))
        ETA_HOURS=$(python3 -c "print(f'{($ETA_MINUTES / 60):.1f}')" 2>/dev/null || echo "?")
        echo ""
        if [ "$ETA_MINUTES" -gt 60 ]; then
            echo "⏱️  Estimated time remaining: ~${ETA_HOURS} hours"
        else
            echo "⏱️  Estimated time remaining: ~${ETA_MINUTES} minutes"
        fi
    fi
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
