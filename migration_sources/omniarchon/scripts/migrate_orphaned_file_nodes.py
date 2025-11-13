#!/usr/bin/env python3
"""
Orphaned File Node Migration Script

Fixes orphaned file nodes in Memgraph by:
1. Detecting File nodes without CONTAINS relationships from PROJECT/DIRECTORY
2. Determining project_name from entity_id pattern (e.g., file:omniarchon:... → omniarchon)
3. Adding project_name property to orphaned nodes
4. Creating CONTAINS relationships from appropriate parent (PROJECT or DIRECTORY)

This script handles the data inconsistency where File nodes were created without
proper tree relationships, breaking the PROJECT → DIRECTORY → FILE hierarchy.

Features:
- Transaction batching (100 nodes per batch)
- Retry logic for TransientErrors (exponential backoff: 1s, 2s, 4s)
- Dry-run mode for safe previewing
- Progress reporting (every 100 nodes)
- Comprehensive logging to logs/migration_orphaned_file_nodes.log
- Safety checks and confirmation prompts

Usage:
    # Dry run (preview changes)
    python3 scripts/migrate_orphaned_file_nodes.py --dry-run

    # Apply fixes
    python3 scripts/migrate_orphaned_file_nodes.py --apply

    # Apply to specific project
    python3 scripts/migrate_orphaned_file_nodes.py --apply --project omniarchon

    # Apply with force (skip confirmation)
    python3 scripts/migrate_orphaned_file_nodes.py --apply --force

Created: 2025-11-11
ONEX Pattern: Effect (database mutations with validation and retry logic)
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
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
LOG_FILE = LOG_DIR / "migration_orphaned_file_nodes.log"

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


class OrphanedFileNodeMigration:
    """
    Migrates orphaned File nodes by adding project_name and CONTAINS relationships.
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://localhost:7687",
        dry_run: bool = True,
        project_filter: Optional[str] = None,
        batch_size: int = 100,
    ):
        """
        Initialize orphaned file node migration.

        Args:
            memgraph_uri: Memgraph connection URI
            dry_run: If True, only preview changes (don't apply)
            project_filter: Optional project name filter
            batch_size: Number of nodes to process per batch
        """
        self.memgraph_uri = memgraph_uri
        self.dry_run = dry_run
        self.project_filter = project_filter
        self.batch_size = batch_size
        self.correlation_id = str(uuid4())[:8]

        self.memgraph_adapter = None
        self.driver = None

        # Statistics
        self.stats = {
            "orphans_found": 0,
            "nodes_fixed": 0,
            "nodes_failed": 0,
            "relationships_created": 0,
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

    async def find_orphaned_files(self) -> List[Dict]:
        """
        Find File nodes without CONTAINS relationships from PROJECT/DIRECTORY.

        Returns:
            List of orphan node dictionaries with entity_id, path, project_name
        """
        # Query to find orphaned File nodes
        # Check both :File and :FILE labels for compatibility
        query = """
        MATCH (f)
        WHERE (f:File OR f:FILE)
          AND NOT (f)<-[:CONTAINS]-(:PROJECT)
          AND NOT (f)<-[:CONTAINS]-(:DIRECTORY)
        """

        if self.project_filter:
            query += " AND f.entity_id STARTS WITH $project_prefix"

        query += """
        RETURN
            f.entity_id as entity_id,
            COALESCE(f.path, f.file_path) as path,
            f.project_name as project_name,
            labels(f) as labels
        ORDER BY f.entity_id
        """

        try:
            async with self.driver.session() as session:
                params = {}
                if self.project_filter:
                    params["project_prefix"] = f"file:{self.project_filter}:"

                result = await session.run(query, **params)
                records = await result.data()

                self.stats["orphans_found"] = len(records)

                logger.info(
                    f"🔍 Found {len(records)} orphaned File nodes",
                    extra={
                        "correlation_id": self.correlation_id,
                        "orphan_count": len(records),
                        "project_filter": self.project_filter,
                    },
                )

                return records

        except Exception as e:
            logger.error(
                f"❌ Failed to find orphaned files: {e}",
                extra={"correlation_id": self.correlation_id, "error": str(e)},
            )
            raise

    def extract_project_name(self, entity_id: str) -> Optional[str]:
        """
        Extract project name from entity_id pattern.

        Examples:
            file:omniarchon:... → omniarchon
            file:omniclaude:... → omniclaude

        Args:
            entity_id: File entity ID

        Returns:
            Project name or None if pattern doesn't match
        """
        if not entity_id.startswith("file:"):
            return None

        parts = entity_id.split(":", 3)
        if len(parts) >= 2:
            return parts[1]

        return None

    async def fix_orphaned_node_with_retry(
        self, orphan: Dict, max_attempts: int = 3
    ) -> bool:
        """
        Fix a single orphaned node with retry logic for TransientErrors.

        Args:
            orphan: Orphan node dictionary
            max_attempts: Maximum retry attempts

        Returns:
            True if fixed successfully, False otherwise
        """
        entity_id = orphan["entity_id"]
        current_project_name = orphan.get("project_name")

        # Extract project name from entity_id
        extracted_project_name = self.extract_project_name(entity_id)

        if not extracted_project_name:
            logger.warning(
                f"⚠️  Cannot extract project name from entity_id: {entity_id}"
            )
            return False

        # Determine if we need to update project_name
        needs_project_name_update = current_project_name != extracted_project_name

        for attempt in range(1, max_attempts + 1):
            try:
                if self.dry_run:
                    logger.info(
                        f"[DRY RUN] Would fix orphan: {entity_id} "
                        f"(project_name: {extracted_project_name})"
                    )
                    return True

                # Fix the orphan node
                success = await self._fix_orphaned_node_transaction(
                    entity_id=entity_id,
                    project_name=extracted_project_name,
                    needs_project_name_update=needs_project_name_update,
                )

                if success:
                    self.stats["nodes_fixed"] += 1
                    return True
                else:
                    return False

            except TransientError as e:
                self.stats["retries"] += 1
                if attempt < max_attempts:
                    backoff_delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    logger.warning(
                        f"⚠️  TransientError on attempt {attempt}/{max_attempts} "
                        f"for {entity_id}: {e}. Retrying in {backoff_delay}s..."
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.error(
                        f"❌ TransientError persisted after {max_attempts} attempts "
                        f"for {entity_id}: {e}"
                    )
                    return False

            except Exception as e:
                logger.error(
                    f"❌ Failed to fix orphan {entity_id}: {e}",
                    extra={
                        "correlation_id": self.correlation_id,
                        "entity_id": entity_id,
                        "error": str(e),
                    },
                )
                return False

        return False

    async def _fix_orphaned_node_transaction(
        self, entity_id: str, project_name: str, needs_project_name_update: bool
    ) -> bool:
        """
        Fix orphaned node within a single transaction.

        Args:
            entity_id: File entity ID
            project_name: Project name to assign
            needs_project_name_update: Whether to update project_name property

        Returns:
            True if successful, False otherwise
        """
        # Query to fix orphaned node:
        # 1. Update project_name if needed
        # 2. Find or create PROJECT node
        # 3. Create CONTAINS relationship
        query = """
        // Find the orphaned file node
        MATCH (f)
        WHERE f.entity_id = $entity_id
          AND (f:File OR f:FILE)

        // Update project_name if needed
        """

        if needs_project_name_update:
            query += """
        SET f.project_name = $project_name

        """

        query += """
        // Ensure PROJECT node exists
        MERGE (p:PROJECT {entity_id: $project_entity_id})
        ON CREATE SET
            p.project_name = $project_name,
            p.name = $project_name,
            p.indexed_at = $timestamp

        // Create CONTAINS relationship
        MERGE (p)-[r:CONTAINS]->(f)
        ON CREATE SET r.created_at = $timestamp

        RETURN
            f.entity_id as file_id,
            p.entity_id as project_id,
            r IS NOT NULL as relationship_created
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=entity_id,
                    project_name=project_name,
                    project_entity_id=f"project:{project_name}",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

                record = await result.single()

                if record and record["relationship_created"]:
                    self.stats["relationships_created"] += 1
                    logger.debug(
                        f"✅ Fixed orphan: {entity_id} → PROJECT:{project_name}",
                        extra={
                            "correlation_id": self.correlation_id,
                            "file_id": entity_id,
                            "project_id": record["project_id"],
                        },
                    )
                    return True
                else:
                    logger.warning(f"⚠️  Failed to create relationship for {entity_id}")
                    return False

        except Exception as e:
            logger.error(f"❌ Transaction failed for {entity_id}: {e}")
            raise

    async def run(self) -> int:
        """
        Run the migration.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        start_time = time.time()

        logger.info("=" * 70)
        logger.info("🔧 ORPHANED FILE NODE MIGRATION")
        logger.info("=" * 70)
        logger.info(
            f"Mode: {'DRY RUN (preview only)' if self.dry_run else 'APPLY FIXES'}"
        )
        logger.info(f"Project filter: {self.project_filter or 'All projects'}")
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

            # Find orphaned files
            logger.info("🔍 Scanning for orphaned File nodes...")
            orphans = await self.find_orphaned_files()

            if not orphans:
                logger.info("✅ No orphaned File nodes found - database is healthy!")
                return 0

            logger.info("")
            logger.info(f"Found {len(orphans)} orphaned nodes:")

            # Show sample
            for idx, orphan in enumerate(orphans[:10], 1):
                entity_id = orphan["entity_id"]
                project_name = self.extract_project_name(entity_id)
                logger.info(f"  {idx}. {entity_id} → project_name={project_name}")

            if len(orphans) > 10:
                logger.info(f"  ... and {len(orphans) - 10} more")

            logger.info("")

            if self.dry_run:
                logger.info(
                    "🔍 DRY RUN MODE - No changes will be applied. "
                    "Use --apply to fix orphans."
                )
                return 0

            # Confirmation prompt (unless --force flag)
            if not self._should_skip_confirmation():
                logger.info("")
                logger.info("⚠️  IMPORTANT: This will modify your database.")
                logger.info(
                    "   Recommendation: Backup your database before proceeding."
                )
                logger.info("")
                response = input("Continue with migration? [y/N]: ")

                if response.lower() != "y":
                    logger.info("❌ Migration cancelled by user")
                    return 1

            # Fix orphans in batches
            logger.info("")
            logger.info("=" * 70)
            logger.info("🔧 FIXING ORPHANED NODES")
            logger.info("=" * 70)
            logger.info("")

            for batch_start in range(0, len(orphans), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(orphans))
                batch = orphans[batch_start:batch_end]

                logger.info(
                    f"Processing batch {batch_start // self.batch_size + 1} "
                    f"({batch_start + 1}-{batch_end} of {len(orphans)})..."
                )

                for orphan in batch:
                    success = await self.fix_orphaned_node_with_retry(orphan)
                    if not success:
                        self.stats["nodes_failed"] += 1

                # Progress update every batch
                logger.info(
                    f"  Progress: Fixed {self.stats['nodes_fixed']}/{len(orphans)}, "
                    f"Failed: {self.stats['nodes_failed']}, "
                    f"Retries: {self.stats['retries']}"
                )

            # Summary
            duration = time.time() - start_time
            success_rate = (
                (self.stats["nodes_fixed"] / len(orphans) * 100)
                if len(orphans) > 0
                else 0
            )

            logger.info("")
            logger.info("=" * 70)
            logger.info("📊 MIGRATION SUMMARY")
            logger.info("=" * 70)
            logger.info(f"Orphaned nodes found: {self.stats['orphans_found']}")
            logger.info(f"Nodes fixed: {self.stats['nodes_fixed']}")
            logger.info(f"Nodes failed: {self.stats['nodes_failed']}")
            logger.info(f"Relationships created: {self.stats['relationships_created']}")
            logger.info(f"Total retries: {self.stats['retries']}")
            logger.info(f"Success rate: {success_rate:.1f}%")
            logger.info(f"Duration: {duration:.1f}s")
            logger.info(f"Log file: {LOG_FILE}")
            logger.info("=" * 70)

            if self.stats["nodes_failed"] > 0:
                logger.warning(
                    f"⚠️  {self.stats['nodes_failed']} nodes could not be fixed. "
                    f"Check {LOG_FILE} for details."
                )
                return 1

            logger.info("✅ All orphaned nodes successfully migrated!")
            return 0

        except Exception as e:
            logger.error(f"❌ Fatal error during migration: {e}", exc_info=True)
            return 1

        finally:
            await self.close()

    def _should_skip_confirmation(self) -> bool:
        """Check if confirmation prompt should be skipped (--force flag)."""
        return "--force" in sys.argv


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate orphaned File nodes in Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry-run)
  %(prog)s --dry-run

  # Apply fixes
  %(prog)s --apply

  # Apply to specific project
  %(prog)s --apply --project omniarchon

  # Apply with force (skip confirmation)
  %(prog)s --apply --force

Backup Recommendation:
  Before running with --apply, backup your Memgraph database:
    docker exec memgraph mgconsole --output-format=json > backup.json
        """,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes (default: dry-run mode)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without applying (default: True)",
    )

    parser.add_argument(
        "--project",
        type=str,
        help="Filter by project name (e.g., omniarchon)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of nodes to process per batch (default: 100)",
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

    # If --apply is specified, turn off dry-run
    dry_run = not args.apply

    migration = OrphanedFileNodeMigration(
        memgraph_uri=args.memgraph_uri,
        dry_run=dry_run,
        project_filter=args.project,
        batch_size=args.batch_size,
    )

    return await migration.run()


def main() -> int:
    """Main entry point (sync wrapper)."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
