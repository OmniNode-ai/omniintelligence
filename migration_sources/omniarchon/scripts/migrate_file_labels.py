#!/usr/bin/env python3
"""
File Label Migration Script

Migrates :FILE labels to :File (PascalCase) in Memgraph for schema consistency.

The codebase has standardized on :File label (PascalCase), but some nodes
may still have the old :FILE label (UPPERCASE). This script migrates all
:FILE nodes to :File while preserving all properties and relationships.

Features:
- Batch processing (1000 nodes per batch for performance)
- Retry logic for TransientErrors (exponential backoff: 1s, 2s, 4s)
- Dry-run mode for safe previewing
- Verification mode to check for remaining :FILE nodes
- Rollback capability (emergency use only)
- Progress reporting (every 1000 nodes)
- Comprehensive logging to logs/migration_file_labels.log
- Safety checks and confirmation prompts

Migration Strategy:
    For each :FILE node:
    1. Add :File label (node now has both :FILE and :File)
    2. Remove :FILE label (node now has only :File)

    This preserves all properties and relationships during the transition.

Usage:
    # Dry run (show counts)
    python3 scripts/migrate_file_labels.py --dry-run

    # Apply migration
    python3 scripts/migrate_file_labels.py --apply

    # Verify (check for remaining :FILE nodes)
    python3 scripts/migrate_file_labels.py --verify

    # Rollback (emergency only - reverts :File to :FILE)
    python3 scripts/migrate_file_labels.py --rollback

    # Apply with force (skip confirmation)
    python3 scripts/migrate_file_labels.py --apply --force

Created: 2025-11-11
ONEX Pattern: Effect (database schema migration with safety guarantees)
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from neo4j.exceptions import TransientError

# Add project root and intelligence service to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INTELLIGENCE_SERVICE_DIR = PROJECT_ROOT / "services" / "intelligence"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(INTELLIGENCE_SERVICE_DIR))

# Load .env from project root
env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

# Configure logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "migration_file_labels.log"

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# File handler for detailed logs
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

# Console handler for user-facing output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class FileLabelMigration:
    """
    Migrates :FILE labels to :File (PascalCase) for schema consistency.
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://localhost:7687",
        dry_run: bool = True,
        batch_size: int = 1000,
    ):
        """
        Initialize file label migration.

        Args:
            memgraph_uri: Memgraph connection URI
            dry_run: If True, only preview changes (don't apply)
            batch_size: Number of nodes to process per batch
        """
        self.memgraph_uri = memgraph_uri
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.correlation_id = str(uuid4())[:8]

        self.memgraph_adapter = None
        self.driver = None

        # Statistics
        self.stats = {
            "file_nodes_found": 0,
            "nodes_migrated": 0,
            "nodes_failed": 0,
            "batches_processed": 0,
            "retries": 0,
        }

    async def initialize(self):
        """Initialize Memgraph connection."""
        try:
            from storage.memgraph_adapter import MemgraphKnowledgeAdapter

            self.memgraph_adapter = MemgraphKnowledgeAdapter(
                uri=self.memgraph_uri, username=None, password=None
            )
            await self.memgraph_adapter.initialize()
            self.driver = self.memgraph_adapter.driver

            logger.info(f"✅ Connected to Memgraph at {self.memgraph_uri}")

        except ImportError as e:
            logger.error(f"❌ Cannot import Memgraph adapter: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ Failed to connect to Memgraph: {e}")
            raise

    async def close(self):
        """Close Memgraph connection."""
        if self.memgraph_adapter:
            await self.memgraph_adapter.close()
            logger.info("🔌 Memgraph connection closed")

    async def check_memgraph_health(self) -> bool:
        """
        Check if Memgraph is accessible and healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                return record["test"] == 1

        except Exception as e:
            logger.error(f"❌ Memgraph health check failed: {e}")
            return False

    async def count_file_nodes(self) -> int:
        """
        Count nodes with :FILE label (UPPERCASE).

        Returns:
            Number of :FILE nodes
        """
        query = "MATCH (n:FILE) RETURN count(n) as count"

        try:
            async with self.driver.session() as session:
                result = await session.run(query)
                record = await result.single()
                count = record["count"] if record else 0

                logger.info(
                    f"📊 Found {count} nodes with :FILE label",
                    extra={"correlation_id": self.correlation_id, "file_count": count},
                )

                return count

        except Exception as e:
            logger.error(f"❌ Failed to count :FILE nodes: {e}")
            raise

    async def count_new_file_nodes(self) -> int:
        """
        Count nodes with :File label (PascalCase).

        Returns:
            Number of :File nodes
        """
        query = "MATCH (n:File) RETURN count(n) as count"

        try:
            async with self.driver.session() as session:
                result = await session.run(query)
                record = await result.single()
                count = record["count"] if record else 0

                logger.info(
                    f"📊 Found {count} nodes with :File label",
                    extra={"correlation_id": self.correlation_id, "file_count": count},
                )

                return count

        except Exception as e:
            logger.error(f"❌ Failed to count :File nodes: {e}")
            raise

    async def migrate_batch_with_retry(
        self, batch_offset: int, max_attempts: int = 3
    ) -> int:
        """
        Migrate a batch of :FILE nodes to :File with retry logic.

        Args:
            batch_offset: Offset for batch processing
            max_attempts: Maximum retry attempts

        Returns:
            Number of nodes successfully migrated in this batch
        """
        for attempt in range(1, max_attempts + 1):
            try:
                if self.dry_run:
                    # In dry-run, just count what would be migrated
                    async with self.driver.session() as session:
                        result = await session.run(
                            """
                            MATCH (n:FILE)
                            RETURN count(n) as count
                            SKIP $skip
                            LIMIT $limit
                            """,
                            skip=batch_offset,
                            limit=self.batch_size,
                        )
                        record = await result.single()
                        batch_count = record["count"] if record else 0

                        logger.info(
                            f"[DRY RUN] Would migrate batch at offset {batch_offset} "
                            f"({batch_count} nodes)"
                        )
                        return batch_count

                # Apply migration
                migrated_count = await self._migrate_batch_transaction(batch_offset)
                return migrated_count

            except TransientError as e:
                self.stats["retries"] += 1
                if attempt < max_attempts:
                    backoff_delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    logger.warning(
                        f"⚠️  TransientError on attempt {attempt}/{max_attempts} "
                        f"for batch at offset {batch_offset}: {e}. "
                        f"Retrying in {backoff_delay}s..."
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.error(
                        f"❌ TransientError persisted after {max_attempts} attempts "
                        f"for batch at offset {batch_offset}: {e}"
                    )
                    return 0

            except Exception as e:
                logger.error(
                    f"❌ Failed to migrate batch at offset {batch_offset}: {e}",
                    extra={
                        "correlation_id": self.correlation_id,
                        "batch_offset": batch_offset,
                        "error": str(e),
                    },
                )
                return 0

        return 0

    async def _migrate_batch_transaction(self, batch_offset: int) -> int:
        """
        Migrate a batch of :FILE nodes to :File within a single transaction.

        Args:
            batch_offset: Offset for batch processing

        Returns:
            Number of nodes migrated
        """
        # Query to migrate :FILE → :File
        # Strategy: Add :File label, then remove :FILE label
        query = """
        MATCH (n:FILE)
        WITH n
        SKIP $skip
        LIMIT $limit

        // Add :File label
        SET n:File

        // Remove :FILE label
        REMOVE n:FILE

        RETURN count(n) as migrated_count
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query, skip=batch_offset, limit=self.batch_size
                )

                record = await result.single()
                migrated_count = record["migrated_count"] if record else 0

                if migrated_count > 0:
                    logger.debug(
                        f"✅ Migrated batch at offset {batch_offset}: {migrated_count} nodes",
                        extra={
                            "correlation_id": self.correlation_id,
                            "batch_offset": batch_offset,
                            "migrated_count": migrated_count,
                        },
                    )

                return migrated_count

        except Exception as e:
            logger.error(
                f"❌ Transaction failed for batch at offset {batch_offset}: {e}"
            )
            raise

    async def rollback_batch_with_retry(
        self, batch_offset: int, max_attempts: int = 3
    ) -> int:
        """
        Rollback a batch of :File nodes to :FILE (emergency use only).

        Args:
            batch_offset: Offset for batch processing
            max_attempts: Maximum retry attempts

        Returns:
            Number of nodes successfully rolled back in this batch
        """
        for attempt in range(1, max_attempts + 1):
            try:
                rolled_back_count = await self._rollback_batch_transaction(batch_offset)
                return rolled_back_count

            except TransientError as e:
                self.stats["retries"] += 1
                if attempt < max_attempts:
                    backoff_delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"⚠️  TransientError on attempt {attempt}/{max_attempts} "
                        f"for rollback batch at offset {batch_offset}: {e}. "
                        f"Retrying in {backoff_delay}s..."
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.error(
                        f"❌ TransientError persisted after {max_attempts} attempts "
                        f"for rollback batch at offset {batch_offset}: {e}"
                    )
                    return 0

            except Exception as e:
                logger.error(
                    f"❌ Failed to rollback batch at offset {batch_offset}: {e}",
                    extra={
                        "correlation_id": self.correlation_id,
                        "batch_offset": batch_offset,
                        "error": str(e),
                    },
                )
                return 0

        return 0

    async def _rollback_batch_transaction(self, batch_offset: int) -> int:
        """
        Rollback a batch of :File nodes to :FILE within a single transaction.

        Args:
            batch_offset: Offset for batch processing

        Returns:
            Number of nodes rolled back
        """
        query = """
        MATCH (n:File)
        WHERE NOT n:FILE  // Only rollback nodes that are exclusively :File
        WITH n
        SKIP $skip
        LIMIT $limit

        // Add :FILE label
        SET n:FILE

        // Remove :File label
        REMOVE n:File

        RETURN count(n) as rolled_back_count
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query, skip=batch_offset, limit=self.batch_size
                )

                record = await result.single()
                rolled_back_count = record["rolled_back_count"] if record else 0

                if rolled_back_count > 0:
                    logger.debug(
                        f"✅ Rolled back batch at offset {batch_offset}: {rolled_back_count} nodes"
                    )

                return rolled_back_count

        except Exception as e:
            logger.error(
                f"❌ Rollback transaction failed for batch at offset {batch_offset}: {e}"
            )
            raise

    async def run_migration(self) -> int:
        """
        Run the migration.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        start_time = time.time()

        logger.info("=" * 70)
        logger.info("🔧 FILE LABEL MIGRATION (:FILE → :File)")
        logger.info("=" * 70)
        logger.info(
            f"Mode: {'DRY RUN (preview only)' if self.dry_run else 'APPLY MIGRATION'}"
        )
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Correlation ID: {self.correlation_id}")
        logger.info(f"Log file: {LOG_FILE}")
        logger.info("=" * 70)
        logger.info("")

        try:
            # Initialize connection
            await self.initialize()

            # Health check
            logger.info("🏥 Checking Memgraph health...")
            if not await self.check_memgraph_health():
                logger.error("❌ Memgraph is not healthy. Aborting migration.")
                return 1

            logger.info("✅ Memgraph is healthy")
            logger.info("")

            # Count :FILE nodes
            logger.info("🔍 Counting nodes with :FILE label...")
            file_node_count = await self.count_file_nodes()
            self.stats["file_nodes_found"] = file_node_count

            if file_node_count == 0:
                logger.info("✅ No :FILE nodes found - migration already complete!")
                return 0

            logger.info("")
            logger.info(f"Found {file_node_count} nodes to migrate")

            if self.dry_run:
                logger.info("")
                logger.info(
                    "🔍 DRY RUN MODE - No changes will be applied. "
                    "Use --apply to migrate nodes."
                )
                return 0

            # Confirmation prompt (unless --force flag)
            if not self._should_skip_confirmation():
                logger.info("")
                logger.info("⚠️  IMPORTANT: This will modify your database schema.")
                logger.info(
                    "   Recommendation: Backup your database before proceeding."
                )
                logger.info("")
                response = input("Continue with migration? [y/N]: ")

                if response.lower() != "y":
                    logger.info("❌ Migration cancelled by user")
                    return 1

            # Migrate in batches
            logger.info("")
            logger.info("=" * 70)
            logger.info("🔧 MIGRATING FILE LABELS")
            logger.info("=" * 70)
            logger.info("")

            batch_offset = 0
            total_migrated = 0

            while total_migrated < file_node_count:
                batch_num = self.stats["batches_processed"] + 1
                logger.info(
                    f"Processing batch {batch_num} "
                    f"(offset {batch_offset}, limit {self.batch_size})..."
                )

                migrated_count = await self.migrate_batch_with_retry(batch_offset)

                if migrated_count == 0:
                    # No more nodes to migrate or batch failed
                    break

                total_migrated += migrated_count
                self.stats["nodes_migrated"] = total_migrated
                self.stats["batches_processed"] += 1

                # Progress update
                progress_pct = (
                    (total_migrated / file_node_count * 100)
                    if file_node_count > 0
                    else 0
                )
                logger.info(
                    f"  Progress: {total_migrated}/{file_node_count} "
                    f"({progress_pct:.1f}%), "
                    f"Retries: {self.stats['retries']}"
                )

                # Move to next batch
                # Note: We keep offset at 0 because we're removing :FILE label
                # so nodes disappear from the :FILE query result
                batch_offset = 0

            # Verify migration
            logger.info("")
            logger.info("🔍 Verifying migration...")
            remaining_file_nodes = await self.count_file_nodes()

            if remaining_file_nodes > 0:
                logger.warning(
                    f"⚠️  {remaining_file_nodes} :FILE nodes still remain. "
                    "Migration may be incomplete."
                )
                self.stats["nodes_failed"] = remaining_file_nodes

            # Summary
            duration = time.time() - start_time
            success_rate = (
                (self.stats["nodes_migrated"] / file_node_count * 100)
                if file_node_count > 0
                else 0
            )

            logger.info("")
            logger.info("=" * 70)
            logger.info("📊 MIGRATION SUMMARY")
            logger.info("=" * 70)
            logger.info(f":FILE nodes found: {self.stats['file_nodes_found']}")
            logger.info(f"Nodes migrated: {self.stats['nodes_migrated']}")
            logger.info(f"Nodes remaining: {remaining_file_nodes}")
            logger.info(f"Batches processed: {self.stats['batches_processed']}")
            logger.info(f"Total retries: {self.stats['retries']}")
            logger.info(f"Success rate: {success_rate:.1f}%")
            logger.info(f"Duration: {duration:.1f}s")
            logger.info(f"Log file: {LOG_FILE}")
            logger.info("=" * 70)

            if remaining_file_nodes > 0:
                logger.warning(
                    f"⚠️  {remaining_file_nodes} nodes could not be migrated. "
                    f"Check {LOG_FILE} for details."
                )
                return 1

            logger.info("✅ All :FILE nodes successfully migrated to :File!")
            return 0

        except Exception as e:
            logger.error(f"❌ Fatal error during migration: {e}", exc_info=True)
            return 1

        finally:
            await self.close()

    async def run_verification(self) -> int:
        """
        Verify migration by checking for remaining :FILE nodes.

        Returns:
            Exit code (0 = no :FILE nodes remain, 1 = :FILE nodes found)
        """
        logger.info("=" * 70)
        logger.info("🔍 FILE LABEL VERIFICATION")
        logger.info("=" * 70)
        logger.info("")

        try:
            await self.initialize()

            # Health check
            if not await self.check_memgraph_health():
                logger.error("❌ Memgraph is not healthy.")
                return 1

            # Count :FILE nodes
            file_node_count = await self.count_file_nodes()

            # Count :File nodes
            new_file_node_count = await self.count_new_file_nodes()

            logger.info("")
            logger.info("=" * 70)
            logger.info("📊 VERIFICATION RESULTS")
            logger.info("=" * 70)
            logger.info(f":FILE nodes (old): {file_node_count}")
            logger.info(f":File nodes (new): {new_file_node_count}")
            logger.info("=" * 70)

            if file_node_count == 0:
                logger.info("✅ Verification passed - No :FILE nodes remain!")
                return 0
            else:
                logger.warning(
                    f"⚠️  Verification failed - {file_node_count} :FILE nodes still exist"
                )
                return 1

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}", exc_info=True)
            return 1

        finally:
            await self.close()

    async def run_rollback(self) -> int:
        """
        Rollback migration (emergency use only).

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        logger.warning("=" * 70)
        logger.warning("⚠️  ROLLBACK MODE - EMERGENCY USE ONLY")
        logger.warning("=" * 70)
        logger.warning("")
        logger.warning("This will convert :File nodes back to :FILE")
        logger.warning("Only use this if you need to revert the migration")
        logger.warning("")

        # Confirmation
        response = input("Are you sure you want to rollback? [y/N]: ")
        if response.lower() != "y":
            logger.info("❌ Rollback cancelled")
            return 1

        start_time = time.time()

        try:
            await self.initialize()

            # Health check
            if not await self.check_memgraph_health():
                logger.error("❌ Memgraph is not healthy. Aborting rollback.")
                return 1

            # Count :File nodes (to rollback)
            new_file_node_count = await self.count_new_file_nodes()

            if new_file_node_count == 0:
                logger.info("✅ No :File nodes found - nothing to rollback")
                return 0

            logger.info(f"Found {new_file_node_count} :File nodes to rollback")
            logger.info("")

            # Rollback in batches
            batch_offset = 0
            total_rolled_back = 0

            while total_rolled_back < new_file_node_count:
                batch_num = self.stats["batches_processed"] + 1
                logger.info(f"Rolling back batch {batch_num}...")

                rolled_back_count = await self.rollback_batch_with_retry(batch_offset)

                if rolled_back_count == 0:
                    break

                total_rolled_back += rolled_back_count
                self.stats["batches_processed"] += 1

                logger.info(f"  Progress: {total_rolled_back}/{new_file_node_count}")

                batch_offset = 0  # Keep at 0 since we're removing :File label

            # Summary
            duration = time.time() - start_time

            logger.info("")
            logger.info("=" * 70)
            logger.info("📊 ROLLBACK SUMMARY")
            logger.info("=" * 70)
            logger.info(f"Nodes rolled back: {total_rolled_back}")
            logger.info(f"Duration: {duration:.1f}s")
            logger.info("=" * 70)

            logger.info("✅ Rollback complete")
            return 0

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}", exc_info=True)
            return 1

        finally:
            await self.close()

    def _should_skip_confirmation(self) -> bool:
        """Check if confirmation prompt should be skipped (--force flag)."""
        return "--force" in sys.argv


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate :FILE labels to :File in Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry-run)
  %(prog)s --dry-run

  # Apply migration
  %(prog)s --apply

  # Verify (check for remaining :FILE nodes)
  %(prog)s --verify

  # Rollback (emergency only)
  %(prog)s --rollback

  # Apply with force (skip confirmation)
  %(prog)s --apply --force

Backup Recommendation:
  Before running with --apply, backup your Memgraph database:
    docker exec memgraph mgconsole --output-format=json > backup.json
        """,
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="Apply migration (default: dry-run mode)",
    )

    mode_group.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration (check for remaining :FILE nodes)",
    )

    mode_group.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (emergency use only)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without applying (default: True)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of nodes to process per batch (default: 1000)",
    )

    parser.add_argument(
        "--memgraph-uri",
        type=str,
        default=os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        help="Memgraph connection URI (default: bolt://localhost:7687)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )

    return parser.parse_args()


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    # Determine mode
    if args.verify:
        # Verification mode
        migration = FileLabelMigration(
            memgraph_uri=args.memgraph_uri,
            dry_run=False,  # Not applicable in verify mode
            batch_size=args.batch_size,
        )
        return await migration.run_verification()

    elif args.rollback:
        # Rollback mode
        migration = FileLabelMigration(
            memgraph_uri=args.memgraph_uri,
            dry_run=False,
            batch_size=args.batch_size,
        )
        return await migration.run_rollback()

    else:
        # Migration mode (apply or dry-run)
        dry_run = not args.apply

        migration = FileLabelMigration(
            memgraph_uri=args.memgraph_uri,
            dry_run=dry_run,
            batch_size=args.batch_size,
        )
        return await migration.run_migration()


def main() -> int:
    """Main entry point (sync wrapper)."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
