#!/bin/bash
# Validate Memgraph relationship migration state
# Can be run before or after migration to check database health

set -e

echo "🔍 Memgraph Relationship Migration Validation"
echo "=============================================="
echo ""
echo "Timestamp: $(date)"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Memgraph is accessible
if ! docker exec memgraph mgconsole --execute "RETURN 1;" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot connect to Memgraph${NC}"
    echo "   Make sure Memgraph container is running: docker ps | grep memgraph"
    exit 1
fi

echo -e "${GREEN}✅ Memgraph connection OK${NC}"
echo ""

# Query 1: Count REAL vs PLACEHOLDER nodes
echo "📊 1. Node Distribution"
echo "   ━━━━━━━━━━━━━━━━━━━━━"

REAL_COUNT=$(docker exec memgraph mgconsole --execute "
MATCH (f:FILE)
WHERE f.entity_id STARTS WITH 'file_'
  AND NOT f.entity_id CONTAINS ':'
  AND NOT f.entity_id CONTAINS 'placeholder'
RETURN COUNT(f) AS count;
" 2>/dev/null | tail -1 | tr -d ' ')

PLACEHOLDER_COUNT=$(docker exec memgraph mgconsole --execute "
MATCH (f:FILE)
WHERE f.entity_id STARTS WITH 'file:'
   OR f.entity_id CONTAINS 'placeholder'
RETURN COUNT(f) AS count;
" 2>/dev/null | tail -1 | tr -d ' ')

echo "   REAL FILE nodes: $REAL_COUNT"
echo "   PLACEHOLDER nodes: $PLACEHOLDER_COUNT"
echo ""

if [ "$PLACEHOLDER_COUNT" -eq 0 ]; then
    echo -e "   ${GREEN}✅ No PLACEHOLDER nodes (migration complete)${NC}"
elif [ "$PLACEHOLDER_COUNT" -gt 0 ]; then
    echo -e "   ${YELLOW}⚠️ $PLACEHOLDER_COUNT PLACEHOLDER nodes exist (migration needed)${NC}"
fi
echo ""

# Query 2: Count orphaned REAL nodes
echo "📊 2. Orphaned REAL Nodes"
echo "   ━━━━━━━━━━━━━━━━━━━━━"

ORPHANED_COUNT=$(docker exec memgraph mgconsole --execute "
MATCH (f:FILE)
WHERE f.entity_id STARTS WITH 'file_'
  AND NOT f.entity_id CONTAINS ':'
OPTIONAL MATCH (f)-[r]-()
WITH f, COUNT(r) AS rel_count
WHERE rel_count = 0
RETURN COUNT(f) AS count;
" 2>/dev/null | tail -1 | tr -d ' ')

echo "   Orphaned REAL nodes: $ORPHANED_COUNT"
echo ""

if [ "$ORPHANED_COUNT" -eq 0 ]; then
    echo -e "   ${GREEN}✅ All REAL nodes have relationships${NC}"
elif [ "$ORPHANED_COUNT" -gt 0 ] && [ "$PLACEHOLDER_COUNT" -gt 0 ]; then
    echo -e "   ${RED}❌ $ORPHANED_COUNT orphaned REAL nodes (migration needed)${NC}"
else
    echo -e "   ${YELLOW}ℹ️ Some REAL nodes have no relationships (may be legitimate)${NC}"
fi
echo ""

# Query 3: Relationship counts
echo "📊 3. Relationship Distribution"
echo "   ━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker exec memgraph mgconsole --execute "
MATCH (f:FILE)-[r]-()
WITH f.entity_id STARTS WITH 'file_' AS is_real,
     COUNT(DISTINCT f) AS nodes_with_rels,
     COUNT(r) AS total_rels
RETURN is_real,
       nodes_with_rels,
       total_rels
ORDER BY is_real DESC;
" 2>/dev/null | tail -n +2

echo ""

# Query 4: Property completeness
echo "📊 4. Property Completeness"
echo "   ━━━━━━━━━━━━━━━━━━━━━━━━"

docker exec memgraph mgconsole --execute "
MATCH (f:FILE)
WITH f.entity_id STARTS WITH 'file_' AS is_real,
     SIZE(keys(f)) AS prop_count
RETURN is_real,
       MIN(prop_count) AS min_props,
       AVG(prop_count) AS avg_props,
       MAX(prop_count) AS max_props;
" 2>/dev/null | tail -n +2

echo ""
echo "   Expected: REAL nodes have 15+ properties, PLACEHOLDERs have 4"
echo ""

# Query 5: Entity ID format validation
echo "📊 5. Entity ID Format Compliance"
echo "   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

NON_HASH_COUNT=$(docker exec memgraph mgconsole --execute "
MATCH (f:FILE)
WHERE NOT f.entity_id =~ '^file_[a-f0-9]{12}$'
RETURN COUNT(f) AS count;
" 2>/dev/null | tail -1 | tr -d ' ')

echo "   Non-hash format entity_ids: $NON_HASH_COUNT"
echo ""

if [ "$NON_HASH_COUNT" -eq 0 ]; then
    echo -e "   ${GREEN}✅ All entity_ids use hash-based format${NC}"
else
    echo -e "   ${YELLOW}⚠️ $NON_HASH_COUNT nodes use deprecated format${NC}"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Determine migration status
if [ "$PLACEHOLDER_COUNT" -eq 0 ] && [ "$NON_HASH_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ MIGRATION COMPLETE${NC}"
    echo ""
    echo "   - All PLACEHOLDER nodes removed"
    echo "   - All entity_ids use hash-based format"
    echo "   - REAL nodes: $REAL_COUNT"
    echo "   - Orphaned nodes: $ORPHANED_COUNT (may be legitimate)"
elif [ "$PLACEHOLDER_COUNT" -gt 0 ] || [ "$ORPHANED_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠️ MIGRATION NEEDED${NC}"
    echo ""
    echo "   Run migration script:"
    echo "   python scripts/migrate_orphaned_relationships.py --execute"
    echo ""
    echo "   Or preview first:"
    echo "   python scripts/migrate_orphaned_relationships.py"
else
    echo -e "${GREEN}✅ DATABASE HEALTHY${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
