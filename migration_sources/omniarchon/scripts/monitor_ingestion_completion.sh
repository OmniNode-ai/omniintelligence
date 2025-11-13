#!/bin/bash
# Monitor Kafka event processing completion
# Checks progress every 5 minutes until all 22,130 events are processed

TARGET_VECTORS=22130
CHECK_INTERVAL=300  # 5 minutes
MAX_CHECKS=12       # 60 minutes max

echo "================================================="
echo "Kafka Event Processing Monitor"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Target: ${TARGET_VECTORS} vectors"
echo "Check interval: ${CHECK_INTERVAL}s (5 minutes)"
echo "================================================="
echo ""

for ((i=1; i<=MAX_CHECKS; i++)); do
    echo "--- Check $i/$(MAX_CHECKS) at $(date '+%H:%M:%S') ---"

    # Get vector count
    VECTOR_COUNT=$(curl -s http://localhost:6333/collections/archon_vectors | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['points_count'])" 2>/dev/null || echo "0")

    # Get node count
    NODE_COUNT=$(docker exec -i archon-memgraph mgconsole << 'EOF' 2>/dev/null | grep -oP '\d+' | head -1
MATCH (n) RETURN count(n) as total_nodes;
EOF
    )

    # Get recent consumer activity
    RECENT_LOGS=$(docker logs archon-intelligence-consumer-1 --since 2m --tail 5 2>/dev/null | \
        grep -c "batch_file_processing_succeeded" || echo "0")

    PERCENT=$(python3 -c "print(f'{($VECTOR_COUNT / $TARGET_VECTORS * 100):.1f}')" 2>/dev/null || echo "0")

    echo "  Vectors: ${VECTOR_COUNT} / ${TARGET_VECTORS} (${PERCENT}%)"
    echo "  Memgraph nodes: ${NODE_COUNT}"
    echo "  Recent completions (2min): ${RECENT_LOGS}"

    # Check if complete
    if [ "$VECTOR_COUNT" -ge "$TARGET_VECTORS" ]; then
        echo ""
        echo "================================================="
        echo "✅ PROCESSING COMPLETE!"
        echo "Final vectors: ${VECTOR_COUNT}"
        echo "Final nodes: ${NODE_COUNT}"
        echo "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "================================================="
        echo ""
        echo "Run verification:"
        echo "  python3 scripts/verify_environment.py --verbose"
        exit 0
    fi

    # Check if stalled (no recent activity)
    if [ "$RECENT_LOGS" -eq "0" ] && [ "$i" -gt 2 ]; then
        echo "  ⚠️  WARNING: No recent processing activity detected"
    fi

    # Sleep unless last check
    if [ "$i" -lt "$MAX_CHECKS" ]; then
        echo "  Sleeping ${CHECK_INTERVAL}s until next check..."
        echo ""
        sleep $CHECK_INTERVAL
    fi
done

echo ""
echo "================================================="
echo "⏱️  TIMEOUT: Maximum monitoring time reached"
echo "Current vectors: ${VECTOR_COUNT} / ${TARGET_VECTORS}"
echo "Please check consumer logs for issues"
echo "================================================="
exit 1
