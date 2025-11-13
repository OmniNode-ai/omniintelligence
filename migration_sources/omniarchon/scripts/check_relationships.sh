#!/bin/bash
# Quick Relationship Storage Verification Script
#
# Checks Memgraph for relationships stored by the intelligence pipeline
#
# Usage: ./scripts/check_relationships.sh

set -euo pipefail

echo "======================================================================"
echo "Relationship Storage Verification"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"
echo ""

# Check if Memgraph container is running
echo "🔌 Checking Memgraph connectivity..."
if docker ps | grep -q memgraph; then
    echo "✅ Memgraph container is running"
else
    echo "❌ Memgraph container not found"
    echo "   Start services: docker compose up -d"
    exit 1
fi

echo ""
echo "📊 Querying relationship statistics..."
echo ""

# Query total relationships
echo "Total Relationships:"
docker exec archon-memgraph mgconsole -e "
MATCH ()-[r:RELATES]->()
RETURN count(r) as total_relationships;
" 2>/dev/null || {
    echo "❌ Failed to query Memgraph"
    echo "   Container name might be different. Check: docker ps | grep memgraph"
    exit 1
}

echo ""
echo "Relationships by Type:"
docker exec archon-memgraph mgconsole -e "
MATCH ()-[r:RELATES]->()
RETURN r.relationship_type as type, count(*) as count
ORDER BY count DESC;
" 2>/dev/null

echo ""
echo "Sample Relationships (first 10):"
docker exec archon-memgraph mgconsole -e "
MATCH (source:Entity)-[r:RELATES]->(target:Entity)
RETURN
    source.name as source,
    r.relationship_type as type,
    target.name as target,
    r.confidence_score as confidence
LIMIT 10;
" 2>/dev/null

echo ""
echo "Total Entities (for context):"
docker exec archon-memgraph mgconsole -e "
MATCH (e:Entity)
RETURN count(e) as total_entities;
" 2>/dev/null

echo ""
echo "======================================================================"
echo "Verification Complete"
echo "======================================================================"
echo ""
echo "Expected Results:"
echo "  - Total relationships > 0 (if documents have been indexed)"
echo "  - Relationship types include: USES, CALLS, INHERITS, etc."
echo "  - Entities should also exist (relationships require entities)"
echo ""
echo "If no relationships found:"
echo "  1. Check if documents have been indexed"
echo "  2. Check LangExtract logs: docker logs archon-langextract"
echo "  3. Check intelligence logs: docker logs archon-intelligence | grep MEMGRAPH"
echo ""
