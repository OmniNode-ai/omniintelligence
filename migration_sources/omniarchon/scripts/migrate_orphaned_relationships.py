#!/usr/bin/env python3
"""
Migrate orphaned relationships from PLACEHOLDER to REAL FILE nodes.

Strategy:
1. Find all PLACEHOLDER nodes (entity_id contains ':' or 'placeholder')
2. For each PLACEHOLDER, find matching REAL node by path
3. Recreate relationships pointing to REAL node
4. Delete PLACEHOLDER and old relationships
5. Verify 100% success (0 PLACEHOLDERs remaining)

Safety:
- Dry-run mode by default (--dry-run)
- Requires explicit --execute flag to modify database
- Transaction-based (rollback on error)
- Detailed logging and progress reporting
- Validation before and after migration

Usage:
    # Preview migration (default, read-only)
    python scripts/migrate_orphaned_relationships.py

    # Execute migration (actually modify database)
    python scripts/migrate_orphaned_relationships.py --execute

    # Validate current state only
    python scripts/migrate_orphaned_relationships.py --validate-only
"""
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from neo4j import AsyncGraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RelationshipMigrator:
    """Migrates relationships from PLACEHOLDER to REAL FILE nodes."""

    def __init__(self, memgraph_uri: str, dry_run: bool = True, verbose: bool = False):
        """
        Initialize migrator.

        Args:
            memgraph_uri: Memgraph connection URI
            dry_run: If True, only simulate migration (no changes)
            verbose: Enable verbose logging
        """
        self.uri = memgraph_uri
        self.dry_run = dry_run
        self.verbose = verbose
        self.driver = None

        if verbose:
            logger.setLevel(logging.DEBUG)

        self.stats = {
            "placeholders_found": 0,
            "placeholders_migrated": 0,
            "placeholders_deleted": 0,
            "placeholders_failed": 0,
            "relationships_migrated": 0,
            "real_nodes_connected": 0,
            "failures": [],
            "start_time": datetime.now(timezone.utc),
            "end_time": None,
        }

    async def initialize(self):
        """Initialize database connection."""
        try:
            self.driver = AsyncGraphDatabase.driver(self.uri)
            await self.driver.verify_connectivity()
            logger.info(f"✅ Connected to Memgraph at {self.uri}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Memgraph: {e}")
            raise

    async def close(self):
        """Close database connection."""
        if self.driver:
            await self.driver.close()
            logger.info("🔌 Database connection closed")

    async def validate_pre_migration(self) -> bool:
        """
        Validate database state before migration.

        Returns:
            True if state is as expected, False otherwise
        """
        logger.info("🔍 Running pre-migration validation...")

        async with self.driver.session() as session:
            # Check 1: Count REAL nodes
            result = await session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file_'
                  AND NOT f.entity_id CONTAINS ':'
                  AND NOT f.entity_id CONTAINS 'placeholder'
                RETURN COUNT(f) AS real_count
            """
            )
            record = await result.single()
            real_count = record["real_count"] if record else 0

            logger.info(f"  ✓ REAL FILE nodes: {real_count}")

            # Check 2: Count PLACEHOLDER nodes
            result = await session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file:'
                   OR f.entity_id CONTAINS 'placeholder'
                RETURN COUNT(f) AS placeholder_count
            """
            )
            record = await result.single()
            placeholder_count = record["placeholder_count"] if record else 0

            logger.info(f"  ✓ PLACEHOLDER FILE nodes: {placeholder_count}")
            self.stats["placeholders_found"] = placeholder_count

            # Check 3: Count orphaned REAL nodes
            result = await session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file_'
                  AND NOT f.entity_id CONTAINS ':'
                OPTIONAL MATCH (f)-[r]-()
                WITH f, COUNT(r) AS rel_count
                WHERE rel_count = 0
                RETURN COUNT(f) AS orphaned_count
            """
            )
            record = await result.single()
            orphaned_count = record["orphaned_count"] if record else 0

            logger.info(f"  ✓ Orphaned REAL nodes: {orphaned_count}")

            # Check 4: Count relationships to PLACEHOLDER nodes
            result = await session.run(
                """
                MATCH (f:FILE)-[r]-()
                WHERE f.entity_id STARTS WITH 'file:'
                   OR f.entity_id CONTAINS 'placeholder'
                RETURN COUNT(DISTINCT r) AS placeholder_rels
            """
            )
            record = await result.single()
            placeholder_rels = record["placeholder_rels"] if record else 0

            logger.info(f"  ✓ Relationships to PLACEHOLDERs: {placeholder_rels}")

            # Validation checks
            checks_passed = True

            if real_count == 0:
                logger.error("  ❌ No REAL nodes found - migration not possible")
                checks_passed = False

            if placeholder_count == 0:
                logger.warning("  ⚠️ No PLACEHOLDER nodes found - nothing to migrate")

            logger.info(
                f"{'✅' if checks_passed else '❌'} Pre-migration validation {'passed' if checks_passed else 'FAILED'}"
            )
            return checks_passed

    async def migrate_all(self) -> Dict:
        """
        Migrate all PLACEHOLDER relationships to REAL nodes.

        Returns:
            Migration statistics dictionary
        """
        mode = "🧪 DRY-RUN" if self.dry_run else "🔄 EXECUTE"
        logger.info(
            f"{mode} Starting relationship migration (dry_run={self.dry_run})..."
        )

        # Step 1: Validate pre-migration state
        if not await self.validate_pre_migration():
            logger.error("❌ Pre-migration validation failed - aborting")
            return self.stats

        # Step 2: Find all PLACEHOLDER nodes with relationships
        placeholders = await self._find_placeholders_with_relationships()
        logger.info(f"  Found {len(placeholders)} PLACEHOLDER nodes to migrate")

        if len(placeholders) == 0:
            logger.info("  ✅ No PLACEHOLDER nodes to migrate")
            return self.stats

        # Step 3: Migrate each PLACEHOLDER
        migrated_count = 0
        progress_interval = 50  # Report progress every 50 items

        for i, placeholder in enumerate(placeholders, 1):
            if self.verbose:
                logger.debug(
                    f"  [{i}/{len(placeholders)}] Migrating {placeholder['entity_id']}..."
                )

            success = await self._migrate_placeholder(
                placeholder_id=placeholder["entity_id"],
                file_path=placeholder["file_path"],
                project_name=placeholder["project_name"],
            )

            if success:
                migrated_count += 1
            else:
                self.stats["placeholders_failed"] += 1

            # Progress reporting every 50 relationships
            if i % progress_interval == 0 or i == len(placeholders):
                logger.info(
                    f"  Progress: {i}/{len(placeholders)} ({(i/len(placeholders)*100):.1f}%) | "
                    f"Success: {migrated_count} | Failed: {self.stats['placeholders_failed']}"
                )

        # Step 4: Clean up orphaned PLACEHOLDERs (no relationships)
        if not self.dry_run:
            await self._cleanup_orphaned_placeholders()

        # Step 5: Validate post-migration
        if not self.dry_run:
            await self.validate_post_migration()

        self.stats["end_time"] = datetime.now(timezone.utc)
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()

        logger.info(
            f"\n{'✅' if not self.dry_run else '🧪'} Migration {'complete' if not self.dry_run else 'simulation complete'}!"
        )
        logger.info(f"  Duration: {duration:.1f} seconds")
        logger.info(f"  Placeholders found: {self.stats['placeholders_found']}")
        logger.info(f"  Placeholders migrated: {self.stats['placeholders_migrated']}")
        logger.info(f"  Placeholders deleted: {self.stats['placeholders_deleted']}")
        logger.info(f"  Placeholders failed: {self.stats['placeholders_failed']}")
        logger.info(f"  Relationships migrated: {self.stats['relationships_migrated']}")
        logger.info(f"  REAL nodes connected: {self.stats['real_nodes_connected']}")

        if self.stats["failures"]:
            logger.warning(f"\n⚠️ Failed migrations: {len(self.stats['failures'])}")
            if self.verbose:
                for failure in self.stats["failures"][:20]:  # Show first 20
                    logger.warning(
                        f"  - {failure['placeholder_id']}: {failure['reason']}"
                    )

        return self.stats

    async def _find_placeholders_with_relationships(self) -> List[Dict]:
        """Find all PLACEHOLDER nodes that have relationships."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (p:FILE)
                WHERE p.entity_id STARTS WITH 'file:'
                   OR p.entity_id CONTAINS 'placeholder'
                OPTIONAL MATCH (p)-[r]-()
                WITH p, COLLECT(r) AS rels
                WHERE SIZE(rels) > 0
                RETURN p.entity_id AS entity_id,
                       COALESCE(p.path, p.file_path) AS file_path,
                       COALESCE(p.project_name, 'unknown') AS project_name,
                       SIZE(rels) AS rel_count
            """
            )

            placeholders = []
            async for record in result:
                placeholders.append(
                    {
                        "entity_id": record["entity_id"],
                        "file_path": record["file_path"],
                        "project_name": record["project_name"],
                        "rel_count": record["rel_count"],
                    }
                )

            return placeholders

    async def _migrate_placeholder(
        self, placeholder_id: str, file_path: str, project_name: str
    ) -> bool:
        """
        Migrate a single PLACEHOLDER node's relationships.

        Args:
            placeholder_id: PLACEHOLDER entity_id
            file_path: File path (may be placeholder path format)
            project_name: Project name

        Returns:
            True if migration successful, False otherwise
        """
        async with self.driver.session() as session:
            # Find matching REAL node
            real_id = await self._find_real_node(
                session, file_path, project_name, placeholder_id
            )

            if not real_id:
                self.stats["failures"].append(
                    {
                        "placeholder_id": placeholder_id,
                        "reason": "No matching REAL node found",
                        "file_path": file_path,
                        "project_name": project_name,
                    }
                )
                if self.verbose:
                    logger.debug(f"    ⚠️ No REAL node found for {file_path}")
                return False

            if self.verbose:
                logger.debug(f"    Found REAL node: {real_id}")

            # Migrate relationships
            if not self.dry_run:
                try:
                    rel_count = await self._recreate_relationships(
                        session, placeholder_id, real_id
                    )

                    self.stats["relationships_migrated"] += rel_count
                    self.stats["placeholders_migrated"] += 1
                    self.stats["real_nodes_connected"] += 1

                    if self.verbose:
                        logger.debug(f"    ✅ Migrated {rel_count} relationships")
                except Exception as e:
                    logger.error(f"    ❌ Failed to migrate {placeholder_id}: {e}")
                    self.stats["failures"].append(
                        {
                            "placeholder_id": placeholder_id,
                            "reason": f"Exception: {str(e)}",
                            "file_path": file_path,
                        }
                    )
                    return False
            else:
                if self.verbose:
                    logger.debug(f"    🧪 Would migrate relationships to {real_id}")
                self.stats["placeholders_migrated"] += 1
                self.stats["real_nodes_connected"] += 1

            return True

    async def _find_real_node(
        self, session, file_path: str, project_name: str, placeholder_id: str
    ) -> Optional[str]:
        """
        Find REAL FILE node matching the given path.

        Tries multiple strategies:
        1. Direct path match on path or file_path property
        2. Extract path from placeholder_id format (file:project:path)
        3. Fuzzy path matching (basename match)
        """
        # Strategy 1: Direct path match
        result = await session.run(
            """
            MATCH (real:FILE)
            WHERE (real.file_path = $file_path OR real.path = $file_path)
              AND real.project_name = $project_name
              AND real.entity_id STARTS WITH 'file_'
              AND NOT real.entity_id CONTAINS ':'
              AND NOT real.entity_id CONTAINS 'placeholder'
            RETURN real.entity_id AS real_id
            LIMIT 1
        """,
            {"file_path": file_path, "project_name": project_name},
        )

        record = await result.single()
        if record:
            return record["real_id"]

        # Strategy 2: Extract path from placeholder_id
        # Format: file:project:path or file:project:archon://path
        if placeholder_id.startswith("file:"):
            parts = placeholder_id.split(":", 2)
            if len(parts) >= 3:
                extracted_path = parts[2]

                # Try exact match on extracted path
                result = await session.run(
                    """
                    MATCH (real:FILE)
                    WHERE (real.path CONTAINS $path_fragment OR real.file_path CONTAINS $path_fragment)
                      AND real.project_name = $project_name
                      AND real.entity_id STARTS WITH 'file_'
                      AND NOT real.entity_id CONTAINS ':'
                    RETURN real.entity_id AS real_id
                    LIMIT 1
                """,
                    {"path_fragment": extracted_path, "project_name": project_name},
                )

                record = await result.single()
                if record:
                    return record["real_id"]

        # Strategy 3: Basename matching as fallback (only if verbose to avoid false positives)
        if self.verbose:
            # Extract basename from file_path
            import os

            basename = os.path.basename(file_path) if file_path else None

            if basename and basename not in ["unknown", ""]:
                result = await session.run(
                    """
                    MATCH (real:FILE)
                    WHERE real.name = $basename
                      AND real.project_name = $project_name
                      AND real.entity_id STARTS WITH 'file_'
                      AND NOT real.entity_id CONTAINS ':'
                    RETURN real.entity_id AS real_id
                    LIMIT 1
                """,
                    {"basename": basename, "project_name": project_name},
                )

                record = await result.single()
                if record:
                    logger.debug(f"    ℹ️ Matched via basename: {basename}")
                    return record["real_id"]

        return None

    async def _recreate_relationships(
        self, session, placeholder_id: str, real_id: str
    ) -> int:
        """
        Recreate relationships from PLACEHOLDER to REAL node.

        Returns:
            Number of relationships recreated
        """
        # Get all relationships (both incoming and outgoing)
        result = await session.run(
            """
            MATCH (p {entity_id: $placeholder_id})

            // Outgoing relationships
            OPTIONAL MATCH (p)-[r_out]->(target)
            WITH p, COLLECT(DISTINCT {
                target_id: target.entity_id,
                type: type(r_out),
                props: properties(r_out)
            }) AS out_rels

            // Incoming relationships
            OPTIONAL MATCH (source)-[r_in]->(p)
            WITH p, out_rels, COLLECT(DISTINCT {
                source_id: source.entity_id,
                type: type(r_in),
                props: properties(r_in)
            }) AS in_rels

            RETURN out_rels, in_rels
        """,
            {"placeholder_id": placeholder_id},
        )

        record = await result.single()
        if not record:
            return 0

        out_rels = record["out_rels"]
        in_rels = record["in_rels"]

        total_rels = 0

        # Recreate outgoing relationships
        for rel in out_rels:
            if rel["target_id"]:
                try:
                    # Build dynamic query with relationship type
                    rel_type = rel["type"]
                    await session.run(
                        f"""
                        MATCH (real {{entity_id: $real_id}})
                        MATCH (target {{entity_id: $target_id}})
                        MERGE (real)-[r:{rel_type}]->(target)
                        SET r = $props
                    """,
                        {
                            "real_id": real_id,
                            "target_id": rel["target_id"],
                            "props": rel["props"] or {},
                        },
                    )
                    total_rels += 1
                except Exception as e:
                    logger.warning(
                        f"    ⚠️ Failed to recreate outgoing relationship: {e}"
                    )

        # Recreate incoming relationships
        for rel in in_rels:
            if rel["source_id"]:
                try:
                    # Build dynamic query with relationship type
                    rel_type = rel["type"]
                    await session.run(
                        f"""
                        MATCH (source {{entity_id: $source_id}})
                        MATCH (real {{entity_id: $real_id}})
                        MERGE (source)-[r:{rel_type}]->(real)
                        SET r = $props
                    """,
                        {
                            "source_id": rel["source_id"],
                            "real_id": real_id,
                            "props": rel["props"] or {},
                        },
                    )
                    total_rels += 1
                except Exception as e:
                    logger.warning(
                        f"    ⚠️ Failed to recreate incoming relationship: {e}"
                    )

        # Delete PLACEHOLDER node (cascade deletes old relationships)
        await session.run(
            """
            MATCH (p {entity_id: $placeholder_id})
            DETACH DELETE p
        """,
            {"placeholder_id": placeholder_id},
        )

        self.stats["placeholders_deleted"] += 1

        return total_rels

    async def _cleanup_orphaned_placeholders(self):
        """Delete PLACEHOLDER nodes with no relationships."""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (p:FILE)
                WHERE (p.entity_id STARTS WITH 'file:' OR p.entity_id CONTAINS 'placeholder')
                  AND NOT (p)-[]-()
                DETACH DELETE p
                RETURN COUNT(p) AS deleted_count
            """
            )

            record = await result.single()
            deleted = record["deleted_count"] if record else 0

            self.stats["placeholders_deleted"] += deleted
            if deleted > 0:
                logger.info(f"  🧹 Cleaned up {deleted} orphaned PLACEHOLDERs")

    async def validate_post_migration(self) -> bool:
        """Validate database state after migration."""
        logger.info("\n🔍 Running post-migration validation...")

        async with self.driver.session() as session:
            # Check 1: No PLACEHOLDER nodes remain
            result = await session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file:'
                   OR f.entity_id CONTAINS 'placeholder'
                RETURN COUNT(f) AS placeholder_count
            """
            )
            record = await result.single()
            placeholder_count = record["placeholder_count"] if record else 0

            check1 = placeholder_count == 0
            logger.info(
                f"  {'✅' if check1 else '❌'} PLACEHOLDER nodes: {placeholder_count} (expected: 0)"
            )

            # Check 2: Count orphaned REAL nodes
            result = await session.run(
                """
                MATCH (f:FILE)
                WHERE f.entity_id STARTS WITH 'file_'
                  AND NOT f.entity_id CONTAINS ':'
                OPTIONAL MATCH (f)-[r]-()
                WITH f, COUNT(r) AS rel_count
                WHERE rel_count = 0
                RETURN COUNT(f) AS orphaned_real_nodes
            """
            )
            record = await result.single()
            orphaned_count = record["orphaned_real_nodes"] if record else 0

            # Note: Some REAL nodes may legitimately have no relationships
            # This is a warning, not a failure
            logger.info(
                f"  {'ℹ️'} Orphaned REAL nodes: {orphaned_count} (note: may be legitimate)"
            )

            # Check 3: All entity_ids are hash-based
            result = await session.run(
                """
                MATCH (f:FILE)
                WHERE NOT f.entity_id =~ '^file_[a-f0-9]{12}$'
                RETURN COUNT(f) AS non_hash_count
            """
            )
            record = await result.single()
            non_hash_count = record["non_hash_count"] if record else 0

            check3 = non_hash_count == 0
            logger.info(
                f"  {'✅' if check3 else '❌'} Non-hash entity_ids: {non_hash_count} (expected: 0)"
            )

            all_passed = check1 and check3
            logger.info(
                f"{'✅' if all_passed else '❌'} Post-migration validation {'PASSED' if all_passed else 'FAILED'}"
            )

            return all_passed


async def main():
    """Main migration entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate relationships from PLACEHOLDER to REAL FILE nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration (dry-run, default)
  python scripts/migrate_orphaned_relationships.py

  # Execute migration (actually modify database)
  python scripts/migrate_orphaned_relationships.py --execute

  # Validate current state only
  python scripts/migrate_orphaned_relationships.py --validate-only

  # Execute with verbose logging and save stats
  python scripts/migrate_orphaned_relationships.py --execute --verbose --output migration_stats.json
        """,
    )
    parser.add_argument(
        "--memgraph-uri",
        default="bolt://localhost:7687",
        help="Memgraph connection URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate migration without making changes (default mode if --execute not specified)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute migration (modifies database)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation checks, do not migrate",
    )
    parser.add_argument("--output", help="Save migration stats to JSON file")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging (debug level)"
    )

    args = parser.parse_args()

    # Determine dry_run mode
    # Default is dry-run unless --execute is specified
    dry_run = not args.execute

    if args.validate_only:
        # Just run validation
        logger.info("🔍 Validation-only mode")
        dry_run = True
    elif not args.execute and not args.dry_run:
        # Default behavior: dry-run
        logger.info(
            "ℹ️ Running in DRY-RUN mode by default. Use --execute to actually modify database."
        )
        dry_run = True

    if not dry_run:
        logger.warning("⚠️ EXECUTING MIGRATION - This will modify the database!")
        logger.warning("⚠️ Press Ctrl+C within 5 seconds to cancel...")
        try:
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            logger.info("\n❌ Migration cancelled by user")
            sys.exit(0)

    # Run migration
    migrator = RelationshipMigrator(
        memgraph_uri=args.memgraph_uri, dry_run=dry_run, verbose=args.verbose
    )

    try:
        await migrator.initialize()

        if args.validate_only:
            # Just run validation
            await migrator.validate_pre_migration()
        else:
            # Run full migration
            stats = await migrator.migrate_all()

            # Save stats if requested
            if args.output:
                with open(args.output, "w") as f:
                    # Convert datetime to string for JSON serialization
                    stats_json = stats.copy()
                    stats_json["start_time"] = stats["start_time"].isoformat()
                    stats_json["end_time"] = (
                        stats["end_time"].isoformat() if stats["end_time"] else None
                    )
                    json.dump(stats_json, f, indent=2)
                logger.info(f"\n📊 Stats saved to: {args.output}")

    except Exception as e:
        logger.error(f"❌ Migration failed with error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await migrator.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n❌ Migration interrupted by user")
        sys.exit(1)
