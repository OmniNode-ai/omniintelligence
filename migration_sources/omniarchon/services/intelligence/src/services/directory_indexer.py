"""
Directory Hierarchy Indexer

Builds and maintains directory hierarchy in Memgraph knowledge graph.
Creates PROJECT, DIRECTORY nodes and CONTAINS relationships.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def validate_project_name(project_name: Optional[str]) -> None:
    """
    Validate project_name is non-empty.

    Args:
        project_name: Project name to validate

    Raises:
        ValueError: If project_name is None, empty, or whitespace-only
    """
    if not project_name or not project_name.strip():
        raise ValueError(
            "project_name is required and cannot be empty. "
            "All ingested files must belong to a project."
        )


class DirectoryIndexer:
    """
    Indexes directory hierarchy for project structure visualization.

    Creates hierarchical structure in Memgraph:
    - PROJECT nodes: Top-level project containers
    - DIRECTORY nodes: Directory structure
    - FILE nodes: Individual files (linked to existing Entity nodes)
    - CONTAINS relationships: Hierarchical links

    This enables directory-level queries and file tree visualization.
    """

    def __init__(self, memgraph_adapter):
        """
        Initialize directory indexer.

        Args:
            memgraph_adapter: Memgraph adapter instance for graph operations
        """
        self.memgraph = memgraph_adapter
        logger.info("DirectoryIndexer initialized")

    async def index_directory_hierarchy(
        self,
        project_name: str,
        project_root: str,
        file_paths: List[str],
        file_entity_mapping: Dict[str, str] = None,
    ) -> Dict[str, int]:
        """
        Index complete directory hierarchy for a project.

        Creates hierarchical structure:
        1. PROJECT node at root
        2. DIRECTORY nodes for all directories
        3. CONTAINS relationships:
           - PROJECT → Top-level directories
           - DIRECTORY → Subdirectories
           - DIRECTORY → Files

        Args:
            project_name: Project identifier (e.g., "omniarchon")
            project_root: Absolute path to project root
            file_paths: List of file paths to index (relative or absolute)

        Returns:
            Dictionary with counts: {projects, directories, files, relationships}

        Raises:
            ValueError: If project_name is None, empty, or whitespace-only
            Exception: If indexing fails
        """
        # Validate project_name BEFORE processing
        validate_project_name(project_name)

        # Entry logging
        logger.info(
            f"ENTER index_directory_hierarchy: project_name={project_name}, "
            f"project_root={project_root}, file_count={len(file_paths)}"
        )

        stats = {"projects": 0, "directories": 0, "files": 0, "relationships": 0}

        start_time = datetime.now(timezone.utc)

        try:
            # Step 1: Create project node
            logger.debug(
                f"🌳 [DIR INDEX] Creating PROJECT node | project={project_name}"
            )
            await self._create_project_node(project_name, project_root)
            stats["projects"] = 1

            # Step 2: Extract unique directories from file paths
            logger.debug(
                f"🌳 [DIR INDEX] Extracting directories | files={len(file_paths)}"
            )
            directories = self._extract_directories(file_paths, project_root)
            logger.debug(f"🌳 [DIR INDEX] Found {len(directories)} unique directories")

            # Step 3: Create directory nodes
            for idx, dir_path in enumerate(sorted(directories), 1):
                logger.debug(
                    f"🌳 [DIR INDEX] Creating DIRECTORY node {idx}/{len(directories)} | "
                    f"path={dir_path}"
                )
                await self._create_directory_node(project_name, dir_path, project_root)
                stats["directories"] += 1

            # Step 4: Create hierarchy relationships
            # 4a. Project → Top-level directories
            top_level_dirs = [
                d for d in directories if str(Path(d).parent) == project_root
            ]

            logger.debug(
                f"🌳 [DIR INDEX] Creating PROJECT → DIRECTORY relationships | "
                f"count={len(top_level_dirs)}"
            )

            for dir_path in top_level_dirs:
                await self._create_contains_relationship(
                    parent_id=f"project:{project_name}",
                    child_id=f"dir:{project_name}:{dir_path}",
                    parent_type="PROJECT",
                    child_type="Directory",
                )
                stats["relationships"] += 1

            # 4b. Directory → Subdirectories
            logger.debug(f"🌳 [DIR INDEX] Creating DIRECTORY → DIRECTORY relationships")
            subdirectory_rels = 0

            for dir_path in directories:
                parent_path = str(Path(dir_path).parent)
                if parent_path in directories:
                    await self._create_contains_relationship(
                        parent_id=f"dir:{project_name}:{parent_path}",
                        child_id=f"dir:{project_name}:{dir_path}",
                        parent_type="Directory",
                        child_type="Directory",
                    )
                    stats["relationships"] += 1
                    subdirectory_rels += 1

            logger.debug(
                f"🌳 [DIR INDEX] Created {subdirectory_rels} subdirectory relationships"
            )

            # 4c. Directory → Files (and PROJECT → root-level files)
            logger.debug(
                f"🌳 [DIR INDEX] Creating DIRECTORY → FILE relationships | "
                f"files={len(file_paths)}"
            )

            for file_path in file_paths:
                dir_path = str(Path(file_path).parent)

                # Use actual entity_id from mapping if provided, otherwise construct one
                if file_entity_mapping and file_path in file_entity_mapping:
                    file_entity_id = file_entity_mapping[file_path]
                else:
                    file_entity_id = f"file:{project_name}:{file_path}"

                # Check if file is at project root
                if dir_path == project_root:
                    # Link directly to PROJECT node for root-level files
                    await self._create_contains_relationship(
                        parent_id=f"project:{project_name}",
                        child_id=file_entity_id,
                        parent_type="PROJECT",
                        child_type="File",
                    )
                else:
                    # Link to DIRECTORY node for files in subdirectories
                    await self._create_contains_relationship(
                        parent_id=f"dir:{project_name}:{dir_path}",
                        child_id=file_entity_id,
                        parent_type="Directory",
                        child_type="File",
                    )
                stats["relationships"] += 1

            stats["files"] = len(file_paths)

            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            # Success exit logging
            logger.info(
                f"EXIT index_directory_hierarchy: SUCCESS - projects={stats['projects']}, "
                f"directories={stats['directories']}, files={stats['files']}, "
                f"relationships={stats['relationships']}, duration_ms={duration_ms:.2f}"
            )

            return stats

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            logger.error(
                f"EXIT index_directory_hierarchy: ERROR - {type(e).__name__}: {str(e)}, "
                f"duration_ms={duration_ms:.2f}",
                exc_info=True,
            )
            raise

    async def _create_project_node(self, project_name: str, project_root: str):
        """
        Create or update PROJECT node in Memgraph.

        Uses MERGE to avoid duplicates.

        Args:
            project_name: Project identifier
            project_root: Absolute path to project root
        """
        query = """
        MERGE (project:PROJECT {entity_id: $entity_id})
        SET project.project_name = $name,
            project.root_path = $path,
            project.indexed_at = $timestamp
        RETURN project.entity_id AS entity_id
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=f"project:{project_name}",
                    name=project_name,
                    path=project_root,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()

                if record:
                    logger.debug(
                        f"✅ [DIR INDEX] PROJECT node created | "
                        f"entity_id={record['entity_id']}"
                    )

        except Exception as e:
            logger.error(
                f"❌ [DIR INDEX] Failed to create PROJECT node | "
                f"project={project_name} | "
                f"error={str(e)}",
                exc_info=True,
            )
            raise

    async def _create_directory_node(
        self, project_name: str, dir_path: str, project_root: str
    ):
        """
        Create or update DIRECTORY node in Memgraph.

        Uses MERGE to avoid duplicates.

        Args:
            project_name: Project identifier
            dir_path: Directory path (relative or absolute)
            project_root: Absolute path to project root
        """
        query = """
        MERGE (dir:Directory {entity_id: $entity_id})
        SET dir.name = $name,
            dir.path = $path,
            dir.project_name = $project_name,
            dir.depth = $depth,
            dir.indexed_at = $timestamp
        RETURN dir.entity_id AS entity_id
        """

        dir_name = Path(dir_path).name
        depth = self._calculate_depth(dir_path, project_root)

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=f"dir:{project_name}:{dir_path}",
                    name=dir_name,
                    path=dir_path,
                    project_name=project_name,
                    depth=depth,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()

                if record:
                    logger.debug(
                        f"✅ [DIR INDEX] DIRECTORY node created | "
                        f"entity_id={record['entity_id']} | depth={depth}"
                    )

        except Exception as e:
            logger.error(
                f"❌ [DIR INDEX] Failed to create DIRECTORY node | "
                f"path={dir_path} | "
                f"error={str(e)}",
                exc_info=True,
            )
            raise

    async def _create_contains_relationship(
        self, parent_id: str, child_id: str, parent_type: str, child_type: str
    ):
        """
        Create CONTAINS relationship between parent and child nodes.

        Uses MERGE to avoid duplicates. Creates stub nodes if they don't exist.

        Args:
            parent_id: Parent node entity_id
            child_id: Child node entity_id
            parent_type: Parent node label (PROJECT, DIRECTORY)
            child_type: Child node label (DIRECTORY, FILE)
        """
        query = f"""
        MATCH (parent:{parent_type} {{entity_id: $parent_id}})
        MERGE (child:{child_type} {{entity_id: $child_id}})
        ON CREATE SET child.project_name = $project_name,
                      child.path = $child_path,
                      child.created_at = $timestamp
        ON MATCH SET child.updated_at = $timestamp
        MERGE (parent)-[r:CONTAINS]->(child)
        SET r.created_at = $timestamp
        RETURN r
        """

        try:
            # Extract project_name and path from entity_id
            # Format: "file:project_name:path" or "dir:project_name:path"
            parts = child_id.split(":", 2)
            project_name = parts[1] if len(parts) > 1 else "unknown"
            child_path = parts[2] if len(parts) > 2 else child_id

            async with self.memgraph.driver.session() as session:
                result = await session.run(
                    query,
                    parent_id=parent_id,
                    child_id=child_id,
                    project_name=project_name,
                    child_path=child_path,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()

                if record:
                    logger.debug(
                        f"✅ [DIR INDEX] CONTAINS relationship created | "
                        f"parent={parent_id} | "
                        f"child={child_id}"
                    )
                else:
                    # Relationship might already exist or nodes not found
                    logger.debug(
                        f"⚠️ [DIR INDEX] CONTAINS relationship returned no record | "
                        f"parent={parent_id} | "
                        f"child={child_id}"
                    )

        except Exception as e:
            logger.error(
                f"❌ [DIR INDEX] Failed to create CONTAINS relationship | "
                f"parent={parent_id} | "
                f"child={child_id} | "
                f"error={str(e)}",
                exc_info=True,
            )
            raise

    def _extract_directories(
        self, file_paths: List[str], project_root: str
    ) -> List[str]:
        """
        Extract unique directory paths from file paths.

        For each file, adds all parent directories up to (but not including)
        the project root.

        Args:
            file_paths: List of file paths
            project_root: Project root path (excluded from results)

        Returns:
            List of unique directory paths
        """
        directories = set()
        project_root_path = Path(project_root)

        for file_path in file_paths:
            path = Path(file_path)

            # Add all parent directories up to project root
            for parent in path.parents:
                # Stop at project root (don't include it)
                if parent == project_root_path:
                    break

                # Only include directories under project root
                parent_str = str(parent)
                if parent_str.startswith(project_root):
                    directories.add(parent_str)

        return sorted(list(directories))

    def _calculate_depth(self, dir_path: str, project_root: str) -> int:
        """
        Calculate directory depth relative to project root.

        Depth is the number of path components from project root to directory.
        Root-level directories (immediate children of project root) have depth 0.

        Args:
            dir_path: Full directory path
            project_root: Project root path

        Returns:
            Depth as integer (0 for root-level directories, >0 for subdirectories)

        Examples:
            project_root = "/project"
            dir_path = "/project/src" → depth = 0 (root-level)
            dir_path = "/project/src/utils" → depth = 1 (1 level below root-level)
            dir_path = "/project/src/utils/helpers" → depth = 2
        """
        try:
            dir_path_obj = Path(dir_path)
            project_root_obj = Path(project_root)

            # Get relative path from project root to directory
            relative_path = dir_path_obj.relative_to(project_root_obj)

            # Count the number of parts in the relative path minus 1
            # (root-level directories have 1 part, so depth = 0)
            depth = len(relative_path.parts) - 1

            return depth

        except ValueError as e:
            # dir_path is not relative to project_root
            logger.warning(
                f"⚠️ [DIR INDEX] Cannot calculate depth - dir_path not under project_root | "
                f"dir_path={dir_path} | project_root={project_root} | error={str(e)}"
            )
            return 0  # Default to 0 if calculation fails

    async def get_project_statistics(self, project_name: str) -> Dict[str, int]:
        """
        Get statistics for a project's directory hierarchy.

        Args:
            project_name: Project identifier

        Returns:
            Dictionary with counts: {directories, files, total_nodes}
        """
        query = """
        MATCH (project:PROJECT {name: $project_name})
        OPTIONAL MATCH (project)-[:CONTAINS*]->(dir:Directory)
        OPTIONAL MATCH (project)-[:CONTAINS*]->(file:File)
        RETURN
            count(DISTINCT dir) as directory_count,
            count(DISTINCT file) as file_count,
            count(DISTINCT dir) + count(DISTINCT file) + 1 as total_nodes
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(query, project_name=project_name)
                record = await result.single()

                if record:
                    return {
                        "directories": record["directory_count"],
                        "files": record["file_count"],
                        "total_nodes": record["total_nodes"],
                    }

                return {"directories": 0, "files": 0, "total_nodes": 0}

        except Exception as e:
            logger.error(
                f"❌ [DIR INDEX] Failed to get project statistics | "
                f"project={project_name} | "
                f"error={str(e)}",
                exc_info=True,
            )
            return {"directories": 0, "files": 0, "total_nodes": 0}
