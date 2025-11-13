#!/usr/bin/env python3
"""
Verify Relationship Storage in Memgraph

Tests the complete relationship storage pipeline:
1. Check Memgraph connectivity
2. Query existing relationships
3. Verify storage statistics
4. Sample relationship data

Usage:
    poetry run python3 scripts/verify_relationship_storage.py
    poetry run python3 scripts/verify_relationship_storage.py --verbose
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.intelligence.storage.memgraph_adapter import MemgraphKnowledgeAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def check_connectivity(adapter: MemgraphKnowledgeAdapter) -> bool:
    """Check if Memgraph is accessible."""
    logger.info("🔌 Checking Memgraph connectivity...")

    try:
        await adapter.initialize()
        is_healthy = await adapter.health_check()

        if is_healthy:
            logger.info("✅ Memgraph connection healthy")
            return True
        else:
            logger.error("❌ Memgraph health check failed")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to connect to Memgraph: {e}")
        return False


async def get_relationship_statistics(
    adapter: MemgraphKnowledgeAdapter,
) -> Dict[str, Any]:
    """Get relationship statistics from Memgraph."""
    logger.info("📊 Querying relationship statistics...")

    try:
        stats = await adapter.get_entity_statistics()

        total_relationships = stats.get("total_relationships", 0)
        relationship_counts = stats.get("relationship_counts_by_type", {})

        logger.info(f"✅ Total relationships: {total_relationships}")

        if relationship_counts:
            logger.info("   Relationships by type:")
            for rel_type, count in relationship_counts.items():
                logger.info(f"     - {rel_type}: {count}")
        else:
            logger.warning("   No relationship type breakdown available")

        return stats
    except Exception as e:
        logger.error(f"❌ Failed to query statistics: {e}")
        return {}


async def sample_relationships(
    adapter: MemgraphKnowledgeAdapter, limit: int = 10
) -> None:
    """Query and display sample relationships."""
    logger.info(f"🔍 Sampling {limit} relationships...")

    try:
        # Query sample relationships using Cypher
        async with adapter.driver.session() as session:
            query = """
            MATCH (source:Entity)-[r:RELATES]->(target:Entity)
            RETURN
                source.entity_id as source_id,
                source.name as source_name,
                r.relationship_type as rel_type,
                r.confidence_score as confidence,
                target.entity_id as target_id,
                target.name as target_name,
                source.source_path as source_path
            LIMIT $limit
            """

            result = await session.run(query, limit=limit)
            records = await result.data()

            if not records:
                logger.warning("⚠️ No relationships found in database")
                logger.info("   This may indicate:")
                logger.info("   1. No documents have been indexed yet")
                logger.info("   2. LangExtract is not extracting relationships")
                logger.info("   3. Entities exist but relationships failed to store")
                return

            logger.info(f"✅ Found {len(records)} relationships:")

            for idx, record in enumerate(records, 1):
                source_name = record.get("source_name", "Unknown")
                target_name = record.get("target_name", "Unknown")
                rel_type = record.get("rel_type", "UNKNOWN")
                confidence = record.get("confidence", 0.0)
                source_path = record.get("source_path", "Unknown")

                logger.info(
                    f"   {idx}. {source_name} --[{rel_type}]--> {target_name} "
                    f"(confidence: {confidence:.2f}, path: {source_path})"
                )

    except Exception as e:
        logger.error(f"❌ Failed to sample relationships: {e}", exc_info=True)


async def check_relationship_storage_health(adapter: MemgraphKnowledgeAdapter) -> bool:
    """
    Perform comprehensive health check for relationship storage.

    Returns:
        True if relationship storage is healthy, False otherwise
    """
    logger.info("🏥 Performing relationship storage health check...")

    checks_passed = 0
    checks_total = 4

    # Check 1: Connectivity
    logger.info("Check 1/4: Connectivity")
    if await check_connectivity(adapter):
        checks_passed += 1

    # Check 2: Statistics
    logger.info("\nCheck 2/4: Statistics")
    stats = await get_relationship_statistics(adapter)
    if stats.get("total_relationships", 0) > 0:
        checks_passed += 1
        logger.info("✅ Relationships exist in database")
    else:
        logger.warning(
            "⚠️ No relationships found (may be expected if no indexing has occurred)"
        )

    # Check 3: Sample data
    logger.info("\nCheck 3/4: Sample Data")
    try:
        await sample_relationships(adapter, limit=5)
        checks_passed += 1
    except Exception as e:
        logger.error(f"❌ Failed to sample relationships: {e}")

    # Check 4: Entity existence (relationships need entities)
    logger.info("\nCheck 4/4: Entity Existence")
    total_entities = stats.get("total_entities", 0)
    if total_entities > 0:
        checks_passed += 1
        logger.info(f"✅ Found {total_entities} entities (required for relationships)")
    else:
        logger.warning(
            "⚠️ No entities found - relationships cannot be created without entities"
        )

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Health Check Results: {checks_passed}/{checks_total} checks passed")

    if checks_passed == checks_total:
        logger.info("✅ Relationship storage is HEALTHY")
        return True
    elif checks_passed >= checks_total - 1:
        logger.warning(
            "⚠️ Relationship storage is DEGRADED (likely no data indexed yet)"
        )
        return True
    else:
        logger.error("❌ Relationship storage is UNHEALTHY")
        return False


async def verify_relationship_types() -> None:
    """Verify relationship type distribution."""
    logger.info("\n📈 Analyzing relationship type distribution...")

    memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://memgraph:7687")
    adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri)

    try:
        await adapter.initialize()

        async with adapter.driver.session() as session:
            query = """
            MATCH ()-[r:RELATES]->()
            RETURN r.relationship_type as type, count(*) as count
            ORDER BY count DESC
            """

            result = await session.run(query)
            records = await result.data()

            if not records:
                logger.warning("⚠️ No relationship types found")
                return

            logger.info("Relationship type distribution:")
            total = sum(r["count"] for r in records)

            for record in records:
                rel_type = record["type"]
                count = record["count"]
                percentage = (count / total) * 100
                logger.info(f"  {rel_type:20s}: {count:5d} ({percentage:5.1f}%)")

    except Exception as e:
        logger.error(f"❌ Failed to analyze relationship types: {e}")
    finally:
        await adapter.close()


async def main():
    """Main verification function."""
    logger.info("=" * 60)
    logger.info("Relationship Storage Verification")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Get Memgraph URI from environment
    memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://memgraph:7687")
    logger.info(f"Memgraph URI: {memgraph_uri}")

    # Create adapter
    adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri)

    try:
        # Run health check
        is_healthy = await check_relationship_storage_health(adapter)

        # Additional analysis
        await verify_relationship_types()

        # Exit with appropriate code
        if is_healthy:
            logger.info("\n✅ Verification completed successfully")
            return 0
        else:
            logger.error("\n❌ Verification found issues")
            return 1

    except Exception as e:
        logger.error(f"\n❌ Verification failed with error: {e}", exc_info=True)
        return 2

    finally:
        await adapter.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
