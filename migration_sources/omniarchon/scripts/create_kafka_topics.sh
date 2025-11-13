#!/bin/bash
# Create all Kafka topics required by archon-intelligence consumer
# Generated: 2025-10-27

set -e

REDPANDA_HOST="${1:-192.168.86.200}"
PARTITIONS="${2:-1}"
REPLICAS="${3:-1}"

echo "Creating Kafka topics on $REDPANDA_HOST (partitions=$PARTITIONS, replicas=$REPLICAS)"

# Function to create topic if it doesn't exist
create_topic() {
    local topic=$1
    ssh "$REDPANDA_HOST" "/usr/local/bin/docker exec omninode-bridge-redpanda rpk topic create '$topic' --partitions $PARTITIONS --replicas $REPLICAS 2>&1" || echo "  Topic $topic already exists or failed (continuing...)"
}

# Phase 1: Core Intelligence Topics
echo "Creating Phase 1 topics (Quality Assessment, Entity Extraction, Performance)..."
create_topic "dev.archon-intelligence.quality.assess-code-requested.v1"
create_topic "dev.archon-intelligence.quality.assess-document-requested.v1"
create_topic "dev.archon-intelligence.quality.compliance-check-requested.v1"
create_topic "dev.archon-intelligence.entity.extract-code-requested.v1"
create_topic "dev.archon-intelligence.entity.extract-document-requested.v1"
create_topic "dev.archon-intelligence.entity.search-requested.v1"
create_topic "dev.archon-intelligence.entity.relationships-requested.v1"
create_topic "dev.archon-intelligence.performance.baseline-requested.v1"
create_topic "dev.archon-intelligence.performance.opportunities-requested.v1"
create_topic "dev.archon-intelligence.performance.optimize-requested.v1"
create_topic "dev.archon-intelligence.performance.report-requested.v1"
create_topic "dev.archon-intelligence.performance.trends-requested.v1"

# Phase 2: Document & Pattern Topics
echo "Creating Phase 2 topics (Freshness, Pattern Learning, Traceability)..."
create_topic "dev.archon-intelligence.freshness.analyze-requested.v1"
create_topic "dev.archon-intelligence.freshness.stale-requested.v1"
create_topic "dev.archon-intelligence.freshness.refresh-requested.v1"
create_topic "dev.archon-intelligence.freshness.stats-requested.v1"
create_topic "dev.archon-intelligence.freshness.document-requested.v1"
create_topic "dev.archon-intelligence.freshness.cleanup-requested.v1"
create_topic "dev.archon-intelligence.freshness.document-update-requested.v1"
create_topic "dev.archon-intelligence.freshness.event-stats-requested.v1"
create_topic "dev.archon-intelligence.freshness.analyses-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.match-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.hybrid-score-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.semantic-analyze-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.metrics-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.cache-stats-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.cache-clear-requested.v1"
create_topic "dev.archon-intelligence.pattern-learning.health-requested.v1"
create_topic "dev.archon-intelligence.traceability.track-requested.v1"
create_topic "dev.archon-intelligence.traceability.track-batch-requested.v1"
create_topic "dev.archon-intelligence.traceability.lineage-requested.v1"
create_topic "dev.archon-intelligence.traceability.evolution-requested.v1"
create_topic "dev.archon-intelligence.traceability.execution-logs-requested.v1"
create_topic "dev.archon-intelligence.traceability.execution-summary-requested.v1"
create_topic "dev.archon-intelligence.traceability.analytics-requested.v1"
create_topic "dev.archon-intelligence.traceability.analytics-compute-requested.v1"
create_topic "dev.archon-intelligence.traceability.feedback-analyze-requested.v1"
create_topic "dev.archon-intelligence.traceability.feedback-apply-requested.v1"
create_topic "dev.archon-intelligence.traceability.health-requested.v1"

# Phase 3: Advanced Analytics Topics
echo "Creating Phase 3 topics (Autonomous Learning, Pattern Analytics, Custom Rules, Quality Trends, Perf Analytics)..."
create_topic "dev.archon-intelligence.autonomous.patterns-ingest-requested.v1"
create_topic "dev.archon-intelligence.autonomous.patterns-success-requested.v1"
create_topic "dev.archon-intelligence.autonomous.predict-agent-requested.v1"
create_topic "dev.archon-intelligence.autonomous.predict-time-requested.v1"
create_topic "dev.archon-intelligence.autonomous.safety-score-requested.v1"
create_topic "dev.archon-intelligence.autonomous.stats-requested.v1"
create_topic "dev.archon-intelligence.autonomous.health-requested.v1"
create_topic "dev.archon-intelligence.pattern-analytics.success-rates-requested.v1"
create_topic "dev.archon-intelligence.pattern-analytics.top-patterns-requested.v1"
create_topic "dev.archon-intelligence.pattern-analytics.emerging-requested.v1"
create_topic "dev.archon-intelligence.pattern-analytics.history-requested.v1"
create_topic "dev.archon-intelligence.pattern-analytics.health-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.evaluate-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.get-rules-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.load-config-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.register-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.enable-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.disable-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.clear-requested.v1"
create_topic "dev.archon-intelligence.custom-rules.health-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.snapshot-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.project-trend-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.file-trend-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.file-history-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.detect-regression-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.stats-requested.v1"
create_topic "dev.archon-intelligence.quality-trends.clear-requested.v1"
create_topic "dev.archon-intelligence.perf-analytics.baselines-requested.v1"
create_topic "dev.archon-intelligence.perf-analytics.metrics-requested.v1"
create_topic "dev.archon-intelligence.perf-analytics.opportunities-requested.v1"
create_topic "dev.archon-intelligence.perf-analytics.anomaly-check-requested.v1"
create_topic "dev.archon-intelligence.perf-analytics.trends-requested.v1"
create_topic "dev.archon-intelligence.perf-analytics.health-requested.v1"

# Phase 4: Bridge & Utility Topics
echo "Creating Phase 4 topics (Bridge Intelligence, Document Processing, System Utilities)..."
create_topic "dev.archon-intelligence.bridge.generate-intelligence-requested.v1"
create_topic "dev.archon-intelligence.bridge.bridge-health-requested.v1"
create_topic "dev.archon-intelligence.bridge.capabilities-requested.v1"
create_topic "dev.archon-intelligence.document.process-document-requested.v1"
create_topic "dev.archon-intelligence.document.batch-index-requested.v1"
create_topic "dev.archon-intelligence.system.metrics-requested.v1"
create_topic "dev.archon-intelligence.system.kafka-health-requested.v1"
create_topic "dev.archon-intelligence.system.kafka-metrics-requested.v1"

# Phase 5: Tree + Stamping Topics (already exist, but ensure they're present)
echo "Creating Phase 5 topics (Tree Discovery, Indexing, Search)..."
create_topic "dev.archon-intelligence.tree.index-project-requested.v1"
create_topic "dev.archon-intelligence.tree.search-files-requested.v1"
create_topic "dev.archon-intelligence.tree.get-status-requested.v1"

# Intelligence Adapter Topics
echo "Creating Intelligence Adapter topics..."
create_topic "dev.archon-intelligence.intelligence.document-index-requested.v1"
create_topic "dev.archon-intelligence.intelligence.repository-scan-requested.v1"
create_topic "dev.archon-intelligence.intelligence.search-requested.v1"

# Original codegen topics
echo "Creating original codegen topics..."
create_topic "omninode.codegen.request.validate.v1"
create_topic "omninode.codegen.request.analyze.v1"
create_topic "omninode.codegen.request.pattern.v1"
create_topic "omninode.codegen.request.mixin.v1"

echo ""
echo "✅ Topic creation complete!"
echo ""
echo "Verifying topics..."
ssh "$REDPANDA_HOST" "/usr/local/bin/docker exec omninode-bridge-redpanda rpk topic list 2>&1" | grep "dev.archon-intelligence\|omninode.codegen" | wc -l | xargs echo "Total topics created:"
