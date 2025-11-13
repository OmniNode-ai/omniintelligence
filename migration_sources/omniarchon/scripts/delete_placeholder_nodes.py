#!/usr/bin/env python3
"""
Delete all PLACEHOLDER FILE nodes from Memgraph.

PLACEHOLDER nodes have entity_id format: file:{project}:{path}
REAL nodes have entity_id format: file_{hash12}
"""

import logging

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEMGRAPH_URI = "bolt://localhost:7687"


def delete_placeholder_nodes():
    """Delete all PLACEHOLDER FILE nodes."""
    driver = GraphDatabase.driver(MEMGRAPH_URI)

    try:
        with driver.session() as session:
            # Count before deletion
            result = session.run(
                "MATCH (p:FILE) WHERE p.entity_id CONTAINS ':' RETURN count(p) as count"
            )
            placeholder_count = result.single()["count"]
            logger.info(f"Found {placeholder_count} PLACEHOLDER nodes to delete")

            if placeholder_count == 0:
                logger.info("✅ No PLACEHOLDER nodes found. Database is clean!")
                return

            # Delete PLACEHOLDER nodes (CASCADE deletes relationships)
            logger.info("🗑️  Deleting PLACEHOLDER nodes and their relationships...")
            result = session.run(
                """
                MATCH (p:FILE)
                WHERE p.entity_id CONTAINS ':'
                DETACH DELETE p
                RETURN count(p) as deleted_count
            """
            )
            deleted_count = result.single()["deleted_count"]
            logger.info(f"✅ Deleted {deleted_count} PLACEHOLDER nodes")

            # Verify deletion
            result = session.run(
                "MATCH (p:FILE) WHERE p.entity_id CONTAINS ':' RETURN count(p) as count"
            )
            remaining = result.single()["count"]

            if remaining == 0:
                logger.info("✅ All PLACEHOLDER nodes deleted successfully!")
            else:
                logger.warning(f"⚠️  {remaining} PLACEHOLDER nodes still remain")

            # Count REAL nodes
            result = session.run(
                "MATCH (f:FILE) WHERE f.entity_id =~ 'file_[a-f0-9]{12}' RETURN count(f) as count"
            )
            real_count = result.single()["count"]
            logger.info(f"📊 Remaining REAL FILE nodes: {real_count}")

    finally:
        driver.close()


if __name__ == "__main__":
    delete_placeholder_nodes()
