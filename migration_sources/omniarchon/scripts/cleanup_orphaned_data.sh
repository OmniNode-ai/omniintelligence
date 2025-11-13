#!/bin/bash
# Cleanup Orphaned Data from Memgraph
#
# This script removes FILE nodes without project_name (orphaned from old ingestions)
# Safe to run - only deletes nodes that lack proper metadata

set -e

echo "================================================================"
echo "Orphaned Data Cleanup"
echo "================================================================"
echo ""

# Check current state
echo "📊 Current State:"
python3 << 'PYTHON'
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687")
with driver.session() as session:
    result = session.run("""
        MATCH (f:FILE)
        RETURN
            count(f) as total,
            count(f.project_name) as with_project,
            count(CASE WHEN f.project_name IS NULL THEN 1 END) as orphaned
    """)

    stats = result.single()
    print(f"  Total FILE nodes: {stats['total']:,}")
    print(f"  With project_name: {stats['with_project']:,}")
    print(f"  Orphaned (NULL): {stats['orphaned']:,}")

driver.close()
PYTHON

echo ""
read -p "❓ Delete orphaned FILE nodes? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

echo ""
echo "🗑️  Deleting orphaned FILE nodes..."

python3 << 'PYTHON'
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687")
with driver.session() as session:
    # First, count
    count_result = session.run("""
        MATCH (f:FILE)
        WHERE f.project_name IS NULL
        RETURN count(f) as count
    """)
    orphaned_count = count_result.single()['count']

    # Then delete (with relationships)
    if orphaned_count > 0:
        session.run("""
            MATCH (f:FILE)
            WHERE f.project_name IS NULL
            DETACH DELETE f
        """)
        print(f"✅ Deleted {orphaned_count:,} orphaned FILE nodes")
    else:
        print("ℹ️  No orphaned nodes found")

driver.close()
PYTHON

echo ""
echo "📊 Final State:"
python3 << 'PYTHON'
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687")
with driver.session() as session:
    result = session.run("""
        MATCH (f:FILE)
        RETURN
            count(f) as total,
            count(f.project_name) as with_project,
            count(CASE WHEN f.project_name IS NULL THEN 1 END) as orphaned
    """)

    stats = result.single()
    print(f"  Total FILE nodes: {stats['total']:,}")
    print(f"  With project_name: {stats['with_project']:,}")
    print(f"  Orphaned (NULL): {stats['orphaned']:,}")

driver.close()
PYTHON

echo ""
echo "================================================================"
echo "✅ Cleanup Complete!"
echo "================================================================"
echo ""
echo "Next steps:"
echo "  1. Re-index repository: python3 scripts/bulk_ingest_repository.py /path/to/project"
echo "  2. Verify fixes: python3 scripts/verify_recent_fixes.py --verbose"
