#!/usr/bin/env python3
"""
Delete ALL FILE nodes from Memgraph to start fresh with hash-based entity IDs.
"""
import logging

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEMGRAPH_URI = "bolt://localhost:7687"


def delete_all_nodes():
    """Delete all FILE nodes and relationships"""
    driver = GraphDatabase.driver(MEMGRAPH_URI)

    with driver.session() as session:
        # Count before deletion
        result = session.run("MATCH (n:FILE) RETURN count(n) as count")
        before_count = result.single()["count"]
        logger.info(f"Found {before_count} FILE nodes to delete")

        # Delete all FILE nodes and their relationships
        result = session.run(
            """
            MATCH (n:FILE)
            DETACH DELETE n
            RETURN count(n) as deleted
        """
        )
        deleted = result.single()["deleted"]

        logger.info(f"✅ Deleted {deleted} FILE nodes and all their relationships")

        # Verify
        result = session.run("MATCH (n:FILE) RETURN count(n) as count")
        after_count = result.single()["count"]
        logger.info(f"📊 Remaining FILE nodes: {after_count}")

    driver.close()


if __name__ == "__main__":
    delete_all_nodes()
