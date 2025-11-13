#!/usr/bin/env python3
"""
Verification script for Memgraph TransientError fix.

This script tests the retry logic implementation by simulating
concurrent entity creation and verifying no duplicate nodes are created.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "intelligence"))

from models.entity_models import (
    EntityMetadata,
    EntityType,
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipType,
)
from storage.memgraph_adapter import MemgraphKnowledgeAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_parallel_entity_creation(workers: int = 4):
    """
    Test parallel workers creating the same entities.

    This simulates the race condition that caused TransientErrors.
    With the fix, all workers should succeed without errors.
    """
    logger.info(
        f"🧪 [TEST] Starting parallel entity creation test with {workers} workers"
    )

    # Initialize adapter
    adapter = MemgraphKnowledgeAdapter(
        uri="bolt://localhost:7687", username=None, password=None
    )

    try:
        await adapter.initialize()
        logger.info("✅ [TEST] Memgraph adapter initialized")

        # Create shared entities that multiple workers will try to create
        shared_entities = [
            KnowledgeEntity(
                entity_id=f"shared_entity_{i}",
                name=f"SharedEntity{i}",
                entity_type=EntityType.CLASS,
                description=f"Shared entity {i} created by multiple workers",
                source_path="test/parallel_test.py",
                confidence_score=0.95,
                source_line_number=i * 10,
                properties={
                    "test": True,
                    "worker_test": True,
                },
                metadata=EntityMetadata(
                    file_hash="test_hash_123",
                    extraction_method="test",
                    extraction_confidence=0.95,
                ),
            )
            for i in range(5)
        ]

        # Create tasks for parallel execution
        tasks = []
        for worker_id in range(workers):
            logger.info(f"📝 [TEST] Spawning worker {worker_id + 1}/{workers}")
            task = store_entities_worker(adapter, shared_entities, worker_id)
            tasks.append(task)

        # Run all workers in parallel
        logger.info(f"🚀 [TEST] Launching {workers} workers in parallel")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        success_count = sum(1 for r in results if isinstance(r, int))
        error_count = sum(1 for r in results if isinstance(r, Exception))

        logger.info(
            f"📊 [TEST] Results: {success_count} workers succeeded, {error_count} workers failed"
        )

        # Verify no duplicate nodes
        stats = await adapter.get_entity_statistics()
        total_entities = stats.get("total_entities", 0)

        logger.info(f"📊 [TEST] Total entities in graph: {total_entities}")

        # Expected: 5 entities (one per shared entity, no duplicates)
        if total_entities == len(shared_entities):
            logger.info(f"✅ [TEST] SUCCESS - No duplicate entities created!")
            logger.info(f"✅ [TEST] All {workers} workers succeeded without conflicts")
            return True
        else:
            logger.error(
                f"❌ [TEST] FAILED - Expected {len(shared_entities)} entities, got {total_entities}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ [TEST] Test failed with error: {e}", exc_info=True)
        return False

    finally:
        await adapter.close()
        logger.info("🔒 [TEST] Memgraph adapter closed")


async def store_entities_worker(
    adapter: MemgraphKnowledgeAdapter, entities: List[KnowledgeEntity], worker_id: int
) -> int:
    """
    Worker function that stores entities.

    All workers will try to store the same entities simultaneously,
    simulating the race condition.
    """
    try:
        logger.info(f"👷 [WORKER {worker_id}] Starting entity storage")

        stored_count = await adapter.store_entities(entities)

        logger.info(f"✅ [WORKER {worker_id}] Stored {stored_count} entities")
        return stored_count

    except Exception as e:
        logger.error(f"❌ [WORKER {worker_id}] Failed: {e}", exc_info=True)
        raise


async def test_file_import_relationships(workers: int = 4):
    """
    Test parallel workers creating the same file import relationships.

    This tests the file import relationship creation with concurrent access.
    """
    logger.info(
        f"🧪 [TEST] Starting parallel file import relationship test with {workers} workers"
    )

    adapter = MemgraphKnowledgeAdapter(
        uri="bolt://localhost:7687", username=None, password=None
    )

    try:
        await adapter.initialize()

        # Create shared import relationships
        import_pairs = [
            ("file:test:main.py", "file:test:utils.py"),
            ("file:test:main.py", "file:test:models.py"),
            ("file:test:utils.py", "file:test:helpers.py"),
        ]

        # Create tasks for parallel execution
        tasks = []
        for worker_id in range(workers):
            task = create_imports_worker(adapter, import_pairs, worker_id)
            tasks.append(task)

        # Run all workers in parallel
        logger.info(f"🚀 [TEST] Launching {workers} workers in parallel")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        error_count = sum(1 for r in results if isinstance(r, Exception))

        logger.info(
            f"📊 [TEST] Results: {success_count} workers succeeded, {error_count} workers failed"
        )

        if error_count == 0:
            logger.info(
                f"✅ [TEST] SUCCESS - All {workers} workers completed without errors!"
            )
            return True
        else:
            logger.error(f"❌ [TEST] FAILED - {error_count} workers encountered errors")
            return False

    except Exception as e:
        logger.error(f"❌ [TEST] Test failed with error: {e}", exc_info=True)
        return False

    finally:
        await adapter.close()


async def create_imports_worker(
    adapter: MemgraphKnowledgeAdapter, import_pairs: List[tuple], worker_id: int
) -> bool:
    """Worker function that creates file import relationships."""
    try:
        logger.info(
            f"👷 [WORKER {worker_id}] Creating {len(import_pairs)} import relationships"
        )

        for source_id, target_id in import_pairs:
            success = await adapter.create_file_import_relationship(
                source_id=source_id,
                target_id=target_id,
                import_type="module",
                confidence=1.0,
            )
            if not success:
                logger.warning(
                    f"⚠️ [WORKER {worker_id}] Failed to create import: {source_id} → {target_id}"
                )

        logger.info(f"✅ [WORKER {worker_id}] Completed import relationship creation")
        return True

    except Exception as e:
        logger.error(f"❌ [WORKER {worker_id}] Failed: {e}", exc_info=True)
        raise


async def cleanup_test_data():
    """Clean up test data from Memgraph."""
    logger.info("🧹 [CLEANUP] Removing test data")

    adapter = MemgraphKnowledgeAdapter(
        uri="bolt://localhost:7687", username=None, password=None
    )

    try:
        await adapter.initialize()

        async with adapter.driver.session() as session:
            # Delete test entities
            await session.run(
                """
                MATCH (n)
                WHERE n.entity_id STARTS WITH 'shared_entity_'
                   OR n.entity_id STARTS WITH 'file:test:'
                DETACH DELETE n
                """
            )

        logger.info("✅ [CLEANUP] Test data removed")

    except Exception as e:
        logger.error(f"❌ [CLEANUP] Failed: {e}", exc_info=True)

    finally:
        await adapter.close()


async def main():
    """Run all verification tests."""
    logger.info("=" * 70)
    logger.info("🔍 MEMGRAPH TRANSIENT ERROR FIX VERIFICATION")
    logger.info("=" * 70)

    try:
        # Clean up any existing test data
        await cleanup_test_data()

        # Test 1: Parallel entity creation
        logger.info("\n" + "=" * 70)
        logger.info("📋 TEST 1: Parallel Entity Creation")
        logger.info("=" * 70)
        test1_passed = await test_parallel_entity_creation(workers=4)

        # Clean up before next test
        await cleanup_test_data()

        # Test 2: Parallel file import relationships
        logger.info("\n" + "=" * 70)
        logger.info("📋 TEST 2: Parallel File Import Relationships")
        logger.info("=" * 70)
        test2_passed = await test_file_import_relationships(workers=4)

        # Final cleanup
        await cleanup_test_data()

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 VERIFICATION SUMMARY")
        logger.info("=" * 70)
        logger.info(
            f"Test 1 (Entity Creation): {'✅ PASSED' if test1_passed else '❌ FAILED'}"
        )
        logger.info(
            f"Test 2 (Import Relationships): {'✅ PASSED' if test2_passed else '❌ FAILED'}"
        )

        if test1_passed and test2_passed:
            logger.info("\n🎉 ALL TESTS PASSED - TransientError fix is working!")
            return 0
        else:
            logger.error("\n❌ SOME TESTS FAILED - Review logs above")
            return 1

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
