#!/usr/bin/env python3
"""
Build Directory Tree for Indexed Project

Creates PROJECT and DIRECTORY nodes with CONTAINS relationships in Memgraph
for projects that have been indexed via bulk_ingest_repository.py.

This script queries existing FILE nodes in Memgraph and builds the complete
directory hierarchy structure, enabling file tree visualization and queries.

Usage:
    # Build tree for a specific project
    python build_directory_tree.py omniarchon /Volumes/PRO-G40/Code/omniarchon

    # Build tree for all indexed projects
    python build_directory_tree.py --all

Requirements:
    - Project must be indexed first (run bulk_ingest_repository.py)
    - Memgraph must be running (archon-memgraph:7687)
    - FILE nodes must exist in Memgraph

What it does:
    1. Queries Memgraph for all FILE nodes in the project
    2. Extracts unique directory paths from file paths
    3. Creates PROJECT node
    4. Creates DIRECTORY nodes for all directories
    5. Creates CONTAINS relationships: PROJECT → DIR → FILE
    6. Creates PARENT relationships for bidirectional navigation

Created: 2025-11-07
ONEX Pattern: Orchestrator (workflow coordination)
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root and intelligence service to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INTELLIGENCE_SERVICE_DIR = PROJECT_ROOT / "services" / "intelligence"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(INTELLIGENCE_SERVICE_DIR))

# Load .env
env_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=env_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def build_directory_tree(project_name: str, project_root: str) -> dict:
    """
    Build directory tree structure for an indexed project.

    Args:
        project_name: Project identifier (e.g., "omniarchon")
        project_root: Absolute path to project root

    Returns:
        Dictionary with statistics
    """
    from src.services.directory_indexer import DirectoryIndexer
    from storage.memgraph_adapter import MemgraphKnowledgeAdapter

    logger.info("=" * 70)
    logger.info("DIRECTORY TREE BUILDER")
    logger.info("=" * 70)
    logger.info(f"Project: {project_name}")
    logger.info(f"Project root: {project_root}")
    logger.info("=" * 70)
    logger.info("")

    # Initialize Memgraph adapter
    memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
    logger.info(f"🔌 Connecting to Memgraph: {memgraph_uri}")

    memgraph_adapter = MemgraphKnowledgeAdapter(
        uri=memgraph_uri, username=None, password=None
    )
    await memgraph_adapter.initialize()

    # Initialize DirectoryIndexer
    directory_indexer = DirectoryIndexer(memgraph_adapter)

    # Query Memgraph for existing FILE nodes to extract file paths
    logger.info(f"🔍 Querying Memgraph for FILE nodes in project: {project_name}")

    query = """
    MATCH (f:File)
    WHERE f.project_name = $project_name OR f.path CONTAINS $project_name
    RETURN f.path as file_path, f.entity_id as entity_id
    ORDER BY f.path
    """

    try:
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            records = await result.data()

            if not records:
                logger.warning(
                    f"⚠️  No FILE nodes found for project: {project_name}. "
                    f"Run bulk_ingest_repository.py first to index files."
                )
                return {"success": False, "error": "No FILE nodes found"}

            # Extract actual file paths from archon:// URIs and create mapping
            file_paths = []
            file_entity_mapping = {}  # Maps file_path → entity_id

            for record in records:
                uri = record["file_path"]
                entity_id = record["entity_id"]

                # Parse archon://projects/{project}/documents/{actual_path}
                # Example: archon://projects/omniarchon/documents//Volumes/PRO-G40/Code/omniarchon/file.py
                if "documents/" in uri:
                    # Extract everything after "documents/"
                    actual_path = uri.split("documents/", 1)[1]
                    # Remove leading slash if double slash was present
                    if actual_path.startswith("/"):
                        actual_path = actual_path
                    else:
                        # If no leading slash, assume relative path
                        actual_path = "/" + actual_path
                    file_paths.append(actual_path)
                    file_entity_mapping[actual_path] = entity_id
                else:
                    logger.warning(f"⚠️  Unexpected URI format: {uri}")
                    file_paths.append(uri)
                    file_entity_mapping[uri] = entity_id

            logger.info(
                f"✅ Found {len(file_paths)} FILE nodes in Memgraph for {project_name}"
            )
            logger.debug(f"Sample file paths: {file_paths[:3]}")

            # Build directory tree
            logger.info("")
            logger.info("🌳 Building directory hierarchy...")
            logger.info("")

            stats = await directory_indexer.index_directory_hierarchy(
                project_name=project_name,
                project_root=project_root,
                file_paths=file_paths,
                file_entity_mapping=file_entity_mapping,
            )

            logger.info("")
            logger.info("=" * 70)
            logger.info("DIRECTORY TREE BUILD COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Projects created: {stats.get('projects', 0)}")
            logger.info(f"Directories created: {stats.get('directories', 0)}")
            logger.info(f"Files linked: {stats.get('files', 0)}")
            logger.info(f"Relationships created: {stats.get('relationships', 0)}")
            logger.info("=" * 70)

            # Verify tree structure
            logger.info("")
            logger.info("🔍 Verifying tree structure...")

            verify_query = """
            MATCH (p:PROJECT {name: $project_name})
            OPTIONAL MATCH (p)-[:CONTAINS*]->(d:DIRECTORY)
            OPTIONAL MATCH (p)-[:CONTAINS*]->(f:File)
            RETURN
                count(DISTINCT d) as directory_count,
                count(DISTINCT f) as file_count,
                count(DISTINCT p) as project_count
            """

            verify_result = await session.run(verify_query, project_name=project_name)
            verify_record = await verify_result.single()

            if verify_record:
                logger.info(f"✅ PROJECT nodes: {verify_record['project_count']}")
                logger.info(f"✅ DIRECTORY nodes: {verify_record['directory_count']}")
                logger.info(f"✅ FILE nodes (connected): {verify_record['file_count']}")

                # Check for orphaned files
                orphan_query = """
                MATCH (f:File)
                WHERE f.project_name = $project_name OR f.path CONTAINS $project_name
                OPTIONAL MATCH (f)<-[r:CONTAINS]-()
                WITH f, r
                WHERE r IS NULL
                RETURN count(f) as orphan_count
                """

                orphan_result = await session.run(
                    orphan_query, project_name=project_name
                )
                orphan_record = await orphan_result.single()

                if orphan_record and orphan_record["orphan_count"] > 0:
                    logger.warning(
                        f"⚠️  Found {orphan_record['orphan_count']} orphaned FILE nodes (not connected to directories)"
                    )
                else:
                    logger.info("✅ No orphaned files - all files connected to tree")

            # Close adapter
            await memgraph_adapter.close()

            return {"success": True, **stats}

    except Exception as e:
        logger.error(f"❌ Failed to build directory tree: {e}", exc_info=True)
        await memgraph_adapter.close()
        return {"success": False, "error": str(e)}


async def build_all_projects():
    """
    Build directory trees for all indexed projects found in Memgraph.
    """
    from storage.memgraph_adapter import MemgraphKnowledgeAdapter

    logger.info("=" * 70)
    logger.info("BUILDING DIRECTORY TREES FOR ALL PROJECTS")
    logger.info("=" * 70)

    # Initialize Memgraph adapter
    memgraph_uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
    memgraph_adapter = MemgraphKnowledgeAdapter(
        uri=memgraph_uri, username=None, password=None
    )
    await memgraph_adapter.initialize()

    # Query for all unique project names
    query = """
    MATCH (f:File)
    WHERE f.project_name IS NOT NULL
    RETURN DISTINCT f.project_name as project_name, f.project_root as project_root
    ORDER BY project_name
    """

    try:
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query)
            records = await result.data()

            if not records:
                logger.warning("⚠️  No projects found in Memgraph")
                await memgraph_adapter.close()
                return

            logger.info(f"Found {len(records)} projects:")
            for record in records:
                logger.info(
                    f"  - {record['project_name']} ({record.get('project_root', 'no root')})"
                )

            logger.info("")

            # Build tree for each project
            results = []
            for record in records:
                project_name = record["project_name"]
                project_root = record.get("project_root") or f"/path/to/{project_name}"

                logger.info(f"Building tree for: {project_name}")
                result = await build_directory_tree(project_name, project_root)
                results.append({"project": project_name, **result})
                logger.info("")

            # Summary
            logger.info("=" * 70)
            logger.info("ALL PROJECTS SUMMARY")
            logger.info("=" * 70)
            successful = sum(1 for r in results if r.get("success"))
            failed = len(results) - successful
            logger.info(f"Total projects processed: {len(results)}")
            logger.info(f"Successful: {successful}")
            logger.info(f"Failed: {failed}")
            logger.info("=" * 70)

            await memgraph_adapter.close()

    except Exception as e:
        logger.error(f"❌ Failed to build trees for all projects: {e}", exc_info=True)
        await memgraph_adapter.close()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build directory tree structure for indexed projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build tree for specific project
  %(prog)s omniarchon /Volumes/PRO-G40/Code/omniarchon

  # Build tree for all indexed projects
  %(prog)s --all

  # Verbose logging
  %(prog)s omniarchon /path/to/project --verbose
        """,
    )

    parser.add_argument(
        "project_name", nargs="?", help="Project name (e.g., 'omniarchon')"
    )

    parser.add_argument(
        "project_root", nargs="?", help="Absolute path to project root directory"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Build trees for all indexed projects in Memgraph",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Validate arguments
    if args.all:
        # Build all projects
        asyncio.run(build_all_projects())
    elif args.project_name and args.project_root:
        # Build specific project
        asyncio.run(build_directory_tree(args.project_name, args.project_root))
    else:
        print("Error: Must provide either --all or both project_name and project_root")
        print("Run with -h for usage information")
        sys.exit(1)


if __name__ == "__main__":
    main()
