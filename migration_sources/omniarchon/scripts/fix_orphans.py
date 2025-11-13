#!/usr/bin/env python3
"""
Orphan Node Remediation Script

Detects and fixes orphaned FILE nodes in Memgraph that lack CONTAINS relationships
from DIRECTORY or PROJECT nodes. Orphan nodes break the file tree hierarchy and
prevent proper visualization and queries.

Features:
- Automatic orphan detection
- Dry-run mode for previewing fixes
- Path parsing to create missing DIRECTORY nodes
- Automatic CONTAINS relationship creation
- Comprehensive logging with correlation IDs

Usage:
    # Detect orphans (dry-run)
    python fix_orphans.py <project-name>

    # Fix orphans (apply changes)
    python fix_orphans.py <project-name> --apply

    # Fix orphans with verbose logging
    python fix_orphans.py <project-name> --apply --verbose

Created: 2025-11-11
ONEX Pattern: Effect (database mutations with validation)
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import uuid4

from dotenv import load_dotenv

# Add project root and intelligence service to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INTELLIGENCE_SERVICE_DIR = PROJECT_ROOT / "services" / "intelligence"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(INTELLIGENCE_SERVICE_DIR))

# Load .env from project root
env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

# Logging configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


class OrphanNodeFixer:
    """
    Detects and fixes orphaned FILE nodes in Memgraph.

    Orphan FILE nodes lack incoming CONTAINS relationships from DIRECTORY or PROJECT
    nodes, breaking the file tree hierarchy.
    """

    def __init__(
        self,
        project_name: str,
        memgraph_uri: str = "bolt://localhost:7687",
        dry_run: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize orphan node fixer.

        Args:
            project_name: Project name to fix
            memgraph_uri: Memgraph connection URI
            dry_run: If True, only detect orphans (don't apply fixes)
            verbose: Enable verbose logging
        """
        self.project_name = project_name
        self.memgraph_uri = memgraph_uri
        self.dry_run = dry_run
        self.correlation_id = str(uuid4())

        # Configure logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=log_level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        self.logger = logging.getLogger(__name__)

        self.memgraph_adapter = None

    async def initialize(self):
        """Initialize Memgraph connection."""
        try:
            from storage.memgraph_adapter import MemgraphKnowledgeAdapter

            self.memgraph_adapter = MemgraphKnowledgeAdapter(
                uri=self.memgraph_uri, username=None, password=None
            )
            await self.memgraph_adapter.initialize()
            self.logger.info(f"✅ Connected to Memgraph at {self.memgraph_uri}")

        except ImportError as e:
            self.logger.error(f"❌ Cannot import Memgraph adapter: {e}")
            raise

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Memgraph: {e}")
            raise

    async def close(self):
        """Close Memgraph connection."""
        if self.memgraph_adapter:
            await self.memgraph_adapter.close()
            self.logger.info("🔌 Memgraph connection closed")

    async def detect_orphans(self) -> List[Dict[str, str]]:
        """
        Detect orphaned FILE nodes without CONTAINS relationships.

        Returns:
            List of orphan node dictionaries with entity_id, path, and filename
        """
        query = """
        MATCH (f:FILE)
        WHERE f.project_name = $project_name
          AND NOT (f)<-[:CONTAINS]-()
        RETURN f.entity_id as entity_id, f.path as path, f.filename as filename
        ORDER BY f.path
        """

        try:
            async with self.memgraph_adapter.driver.session() as session:
                result = await session.run(query, project_name=self.project_name)
                records = await result.data()

                self.logger.info(
                    f"🔍 Found {len(records)} orphaned FILE nodes",
                    extra={
                        "correlation_id": self.correlation_id,
                        "project_name": self.project_name,
                        "orphan_count": len(records),
                    },
                )

                return records

        except Exception as e:
            self.logger.error(
                f"❌ Failed to detect orphans: {e}",
                extra={"correlation_id": self.correlation_id, "error": str(e)},
            )
            raise

    def parse_file_path(self, file_path: str) -> Tuple[str, str, List[str]]:
        """
        Parse file path to extract project root, filename, and directory components.

        Args:
            file_path: File path (e.g., "archon://documents/project/src/file.py")

        Returns:
            Tuple of (project_root, filename, directory_components)
            - project_root: Project root path (e.g., "/project")
            - filename: File name (e.g., "file.py")
            - directory_components: List of directory names (e.g., ["src"])
        """
        # Handle archon:// URIs
        if "documents/" in file_path:
            actual_path = file_path.split("documents/", 1)[1]
        else:
            actual_path = file_path

        path_obj = Path(actual_path)

        # Extract components
        filename = path_obj.name
        parent_dir = path_obj.parent

        # Find project root (first component after splitting)
        parts = parent_dir.parts

        if not parts:
            return ("", filename, [])

        # Project root is the first component
        project_root = parts[0] if parts else ""

        # Directory components are everything between project root and file
        directory_components = list(parts[1:]) if len(parts) > 1 else []

        return (project_root, filename, directory_components)

    async def ensure_directory_chain(
        self, project_root: str, directory_components: List[str]
    ) -> str:
        """
        Ensure complete directory chain exists, creating missing DIRECTORY nodes.

        Args:
            project_root: Project root path
            directory_components: List of directory names (e.g., ["src", "utils"])

        Returns:
            Entity ID of the deepest directory (parent of the file)
        """
        if not directory_components:
            # File is at project root, return PROJECT entity_id
            return f"project:{self.project_name}"

        # Ensure PROJECT node exists
        await self.ensure_project_node(project_root)

        # Build directory chain
        current_path = project_root
        parent_id = f"project:{self.project_name}"

        for dir_name in directory_components:
            current_path = str(Path(current_path) / dir_name)
            dir_entity_id = f"dir:{self.project_name}:{current_path}"

            # Create DIRECTORY node if doesn't exist
            await self.ensure_directory_node(dir_entity_id, dir_name, current_path)

            # Create CONTAINS relationship from parent to this directory
            await self.create_contains_relationship(
                parent_id=parent_id,
                child_id=dir_entity_id,
                parent_type=(
                    "PROJECT" if parent_id.startswith("project:") else "DIRECTORY"
                ),
                child_type="DIRECTORY",
            )

            # Update parent for next iteration
            parent_id = dir_entity_id

        return parent_id

    async def ensure_project_node(self, project_root: str):
        """
        Ensure PROJECT node exists, creating if necessary.

        Args:
            project_root: Project root path
        """
        query = """
        MERGE (p:PROJECT {entity_id: $entity_id})
        ON CREATE SET
            p.project_name = $project_name,
            p.root_path = $project_root,
            p.indexed_at = $timestamp
        RETURN p.entity_id as entity_id
        """

        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would ensure PROJECT node: project:{self.project_name}",
                extra={
                    "correlation_id": self.correlation_id,
                    "entity_id": f"project:{self.project_name}",
                },
            )
            return

        try:
            async with self.memgraph_adapter.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=f"project:{self.project_name}",
                    project_name=self.project_name,
                    project_root=project_root,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()

                if record:
                    self.logger.debug(
                        f"✅ PROJECT node exists: {record['entity_id']}",
                        extra={
                            "correlation_id": self.correlation_id,
                            "entity_id": record["entity_id"],
                        },
                    )

        except Exception as e:
            self.logger.error(
                f"❌ Failed to ensure PROJECT node: {e}",
                extra={"correlation_id": self.correlation_id, "error": str(e)},
            )
            raise

    async def ensure_directory_node(self, entity_id: str, dir_name: str, dir_path: str):
        """
        Ensure DIRECTORY node exists, creating if necessary.

        Args:
            entity_id: Directory entity ID
            dir_name: Directory name
            dir_path: Full directory path
        """
        query = """
        MERGE (d:DIRECTORY {entity_id: $entity_id})
        ON CREATE SET
            d.name = $name,
            d.path = $path,
            d.project_name = $project_name,
            d.indexed_at = $timestamp
        RETURN d.entity_id as entity_id
        """

        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would ensure DIRECTORY node: {entity_id}",
                extra={
                    "correlation_id": self.correlation_id,
                    "entity_id": entity_id,
                    "dir_name": dir_name,
                },
            )
            return

        try:
            async with self.memgraph_adapter.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=entity_id,
                    name=dir_name,
                    path=dir_path,
                    project_name=self.project_name,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()

                if record:
                    self.logger.debug(
                        f"✅ DIRECTORY node exists: {record['entity_id']}",
                        extra={
                            "correlation_id": self.correlation_id,
                            "entity_id": record["entity_id"],
                        },
                    )

        except Exception as e:
            self.logger.error(
                f"❌ Failed to ensure DIRECTORY node: {e}",
                extra={
                    "correlation_id": self.correlation_id,
                    "error": str(e),
                    "entity_id": entity_id,
                },
            )
            raise

    async def create_contains_relationship(
        self, parent_id: str, child_id: str, parent_type: str, child_type: str
    ):
        """
        Create CONTAINS relationship from parent to child.

        Args:
            parent_id: Parent entity ID
            child_id: Child entity ID
            parent_type: Parent node label (PROJECT or DIRECTORY)
            child_type: Child node label (DIRECTORY or FILE)
        """
        query = f"""
        MATCH (parent:{parent_type} {{entity_id: $parent_id}})
        MATCH (child:{child_type} {{entity_id: $child_id}})
        MERGE (parent)-[r:CONTAINS]->(child)
        ON CREATE SET r.created_at = $timestamp
        RETURN r
        """

        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would create CONTAINS: {parent_id} -> {child_id}",
                extra={
                    "correlation_id": self.correlation_id,
                    "parent_id": parent_id,
                    "child_id": child_id,
                    "relationship": "CONTAINS",
                },
            )
            return

        try:
            async with self.memgraph_adapter.driver.session() as session:
                result = await session.run(
                    query,
                    parent_id=parent_id,
                    child_id=child_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()

                if record:
                    self.logger.debug(
                        f"✅ CONTAINS relationship created: {parent_id} -> {child_id}",
                        extra={
                            "correlation_id": self.correlation_id,
                            "parent_id": parent_id,
                            "child_id": child_id,
                        },
                    )

        except Exception as e:
            self.logger.error(
                f"❌ Failed to create CONTAINS relationship: {e}",
                extra={
                    "correlation_id": self.correlation_id,
                    "error": str(e),
                    "parent_id": parent_id,
                    "child_id": child_id,
                },
            )
            raise

    async def fix_orphan(self, orphan: Dict[str, str]) -> bool:
        """
        Fix a single orphan FILE node by creating missing directory chain and relationship.

        Args:
            orphan: Orphan node dictionary with entity_id, path, filename

        Returns:
            True if fixed successfully, False otherwise
        """
        entity_id = orphan["entity_id"]
        file_path = orphan["path"]
        filename = orphan.get("filename", "unknown")

        try:
            self.logger.info(
                f"🔧 Fixing orphan: {filename}",
                extra={
                    "correlation_id": self.correlation_id,
                    "entity_id": entity_id,
                    "file_path": file_path,
                },
            )

            # Parse file path
            project_root, filename, directory_components = self.parse_file_path(
                file_path
            )

            self.logger.debug(
                f"   Parsed: root={project_root}, dirs={directory_components}, file={filename}",
                extra={
                    "correlation_id": self.correlation_id,
                    "project_root": project_root,
                    "directory_components": directory_components,
                    "file_name": filename,
                },
            )

            # Ensure directory chain exists
            parent_id = await self.ensure_directory_chain(
                project_root, directory_components
            )

            # Create CONTAINS relationship from parent directory to file
            await self.create_contains_relationship(
                parent_id=parent_id,
                child_id=entity_id,
                parent_type=(
                    "PROJECT" if parent_id.startswith("project:") else "DIRECTORY"
                ),
                child_type="FILE",
            )

            self.logger.info(
                f"✅ Fixed orphan: {filename}",
                extra={
                    "correlation_id": self.correlation_id,
                    "entity_id": entity_id,
                    "parent_id": parent_id,
                },
            )

            return True

        except Exception as e:
            self.logger.error(
                f"❌ Failed to fix orphan {filename}: {e}",
                extra={
                    "correlation_id": self.correlation_id,
                    "entity_id": entity_id,
                    "error": str(e),
                },
            )
            return False

    async def run(self) -> int:
        """
        Run orphan detection and remediation.

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        start_time = datetime.now(timezone.utc)

        try:
            await self.initialize()

            self.logger.info("=" * 70)
            self.logger.info("🔍 ORPHAN NODE DETECTION & REMEDIATION")
            self.logger.info("=" * 70)
            self.logger.info(f"Project: {self.project_name}")
            self.logger.info(
                f"Mode: {'DRY RUN (preview only)' if self.dry_run else 'APPLY FIXES'}"
            )
            self.logger.info(f"Correlation ID: {self.correlation_id}")
            self.logger.info("=" * 70)
            self.logger.info("")

            # Detect orphans
            orphans = await self.detect_orphans()

            if not orphans:
                self.logger.info("✅ No orphan FILE nodes detected - tree is healthy!")
                return 0

            self.logger.info("")
            self.logger.info(f"Found {len(orphans)} orphan nodes:")
            for idx, orphan in enumerate(orphans[:10], 1):
                self.logger.info(
                    f"  {idx}. {orphan.get('filename', 'unknown')} ({orphan['entity_id']})"
                )

            if len(orphans) > 10:
                self.logger.info(f"  ... and {len(orphans) - 10} more")

            self.logger.info("")

            if self.dry_run:
                self.logger.info(
                    "🔍 DRY RUN MODE - No changes will be applied. "
                    "Run with --apply to fix orphans."
                )
                return 0

            # Fix orphans
            self.logger.info("=" * 70)
            self.logger.info("🔧 FIXING ORPHAN NODES")
            self.logger.info("=" * 70)
            self.logger.info("")

            fixed_count = 0
            failed_count = 0

            for idx, orphan in enumerate(orphans, 1):
                self.logger.info(f"Processing orphan {idx}/{len(orphans)}...")
                success = await self.fix_orphan(orphan)

                if success:
                    fixed_count += 1
                else:
                    failed_count += 1

            # Summary
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info("📊 REMEDIATION SUMMARY")
            self.logger.info("=" * 70)
            self.logger.info(f"Total orphans found: {len(orphans)}")
            self.logger.info(f"Successfully fixed: {fixed_count}")
            self.logger.info(f"Failed to fix: {failed_count}")
            self.logger.info(f"Duration: {duration_ms:.0f}ms")
            self.logger.info("=" * 70)

            if failed_count > 0:
                self.logger.warning(f"⚠️  {failed_count} orphans could not be fixed")
                return 1

            self.logger.info("✅ All orphan nodes successfully remediated!")
            return 0

        except Exception as e:
            self.logger.error(f"❌ Fatal error: {e}", exc_info=True)
            return 1

        finally:
            await self.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Detect and fix orphaned FILE nodes in Memgraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Detect orphans (dry-run)
  %(prog)s omniarchon

  # Fix orphans (apply changes)
  %(prog)s omniarchon --apply

  # Fix with verbose logging
  %(prog)s omniarchon --apply --verbose
        """,
    )

    parser.add_argument(
        "project_name",
        type=str,
        help="Project name to fix orphans for",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes (default: dry-run mode)",
    )

    parser.add_argument(
        "--memgraph-uri",
        type=str,
        default=os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        help="Memgraph connection URI (default: bolt://localhost:7687)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


async def main_async() -> int:
    """Async main entry point."""
    args = parse_args()

    fixer = OrphanNodeFixer(
        project_name=args.project_name,
        memgraph_uri=args.memgraph_uri,
        dry_run=not args.apply,
        verbose=args.verbose,
    )

    return await fixer.run()


def main() -> int:
    """Main entry point (sync wrapper)."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
