#!/usr/bin/env python3
"""
Quick fix for orphaned files in tree graph.

This script creates PROJECT → DIRECTORY → FILE relationships using
efficient bulk Cypher queries instead of individual relationship creation.

Usage:
    python3 scripts/quick_fix_tree.py
"""
import asyncio
import logging
from pathlib import Path

from neo4j import AsyncGraphDatabase

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def fix_tree_for_project(driver, project_name: str, project_root: str):
    """Fix tree structure for a single project using bulk operations."""
    logger.info(f"Processing project: {project_name}")

    async with driver.session() as session:
        # Step 1: Get all file paths for this project
        result = await session.run(
            """
            MATCH (f:FILE)
            WHERE f.project_name = $project_name
            RETURN f.entity_id AS entity_id,
                   COALESCE(f.path, f.file_path) AS file_path
        """,
            project_name=project_name,
        )

        files = []
        async for record in result:
            files.append(
                {"entity_id": record["entity_id"], "file_path": record["file_path"]}
            )

        logger.info(f"  Found {len(files)} files")

        if not files:
            return 0

        # Step 2: Create PROJECT node if not exists
        await session.run(
            """
            MERGE (p:PROJECT {name: $project_name})
            SET p.path = $project_root,
                p.entity_id = 'project:' + $project_name
        """,
            project_name=project_name,
            project_root=project_root,
        )

        logger.info(f"  ✓ Created/verified PROJECT node")

        # Step 3: Extract unique directory paths
        directory_paths = set()
        file_to_dir = {}  # Map file_entity_id → directory_path

        for file in files:
            file_path = file["file_path"]
            entity_id = file["entity_id"]

            # Extract actual path from archon:// URI if needed
            if "documents/" in file_path:
                actual_path = file_path.split("documents/", 1)[1]
            else:
                actual_path = file_path

            # Get parent directory
            try:
                parent_dir = str(Path(actual_path).parent)
                if parent_dir and parent_dir != "/" and parent_dir != ".":
                    directory_paths.add(parent_dir)
                    file_to_dir[entity_id] = parent_dir
            except Exception as e:
                logger.warning(f"  ⚠ Skipping file with invalid path: {file_path}")
                continue

        logger.info(f"  Extracted {len(directory_paths)} unique directories")

        # Step 4: Create DIRECTORY nodes in batches
        batch_size = 100
        dir_list = list(directory_paths)
        created_dirs = 0

        for i in range(0, len(dir_list), batch_size):
            batch = dir_list[i : i + batch_size]

            # Create directories
            await session.run(
                """
                UNWIND $directories AS dir_path
                MERGE (d:DIRECTORY {path: dir_path, project_name: $project_name})
                SET d.entity_id = 'dir:' + $project_name + ':' + dir_path,
                    d.name = split(dir_path, '/')[-1]
                RETURN COUNT(d) AS count
            """,
                directories=batch,
                project_name=project_name,
            )

            created_dirs += len(batch)
            if (i + batch_size) % 500 == 0:
                logger.info(f"  Progress: {created_dirs}/{len(dir_list)} directories")

        logger.info(f"  ✓ Created {created_dirs} DIRECTORY nodes")

        # Step 5: Create PROJECT → DIRECTORY relationships for all directories
        # Note: We'll connect ALL directories to project for now (simplified approach)
        result = await session.run(
            """
            MATCH (p:PROJECT {name: $project_name})
            MATCH (d:DIRECTORY {project_name: $project_name})
            OPTIONAL MATCH contains_path = (p)-[:CONTAINS]->(d)
            WITH p, d, contains_path
            WHERE contains_path IS NULL
            MERGE (p)-[:CONTAINS]->(d)
            RETURN COUNT(*) AS count
        """,
            project_name=project_name,
        )

        record = await result.single()
        connected_dirs = record["count"] if record else 0

        logger.info(f"  ✓ Connected PROJECT to {connected_dirs} directories")

        # Step 6: Create DIRECTORY → FILE relationships in batches
        file_batches = []
        for entity_id, dir_path in file_to_dir.items():
            file_batches.append({"file_id": entity_id, "dir_path": dir_path})

        created_rels = 0
        for i in range(0, len(file_batches), batch_size):
            batch = file_batches[i : i + batch_size]

            result = await session.run(
                """
                UNWIND $batch AS item
                MATCH (d:DIRECTORY {path: item.dir_path, project_name: $project_name})
                MATCH (f:FILE {entity_id: item.file_id})
                MERGE (d)-[:CONTAINS]->(f)
                RETURN COUNT(*) AS count
            """,
                batch=batch,
                project_name=project_name,
            )

            record = await result.single()
            created_rels += record["count"] if record else 0

            if (i + batch_size) % 500 == 0:
                logger.info(f"  Progress: {created_rels} CONTAINS relationships")

        logger.info(f"  ✓ Created {created_rels} DIRECTORY → FILE relationships")

        return created_rels


async def main():
    """Main entry point."""
    logger.info("=" * 70)
    logger.info("QUICK TREE FIX - Bulk relationship creation")
    logger.info("=" * 70)

    driver = AsyncGraphDatabase.driver("bolt://localhost:7687")

    try:
        await driver.verify_connectivity()
        logger.info("✓ Connected to Memgraph")

        # Projects to fix (excluding omniarchon which is already done)
        projects = [
            ("omniclaude", "/Volumes/PRO-G40/Code/omniclaude"),
            ("omnibase_core", "/Volumes/PRO-G40/Code/omnibase_core"),
            ("omninode_bridge", "/Volumes/PRO-G40/Code/omninode_bridge"),
            ("omnidash", "/Volumes/PRO-G40/Code/omnidash"),
        ]

        total_relationships = 0

        for project_name, project_root in projects:
            logger.info("")
            try:
                rels = await fix_tree_for_project(driver, project_name, project_root)
                total_relationships += rels
                logger.info(f"✓ {project_name} complete")
            except Exception as e:
                logger.error(f"✗ {project_name} failed: {e}")
                continue

        logger.info("")
        logger.info("=" * 70)
        logger.info(f"COMPLETE: Created {total_relationships} relationships")
        logger.info("=" * 70)

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
