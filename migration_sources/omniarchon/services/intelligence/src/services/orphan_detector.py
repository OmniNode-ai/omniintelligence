"""
Orphan File Detection Service

Identifies orphaned and unreachable files in a project using graph analysis.

Orphan Types:
1. **No Incoming Imports**: Files that no other file imports
2. **Unreachable from Entry Points**: Files not in dependency chain from main files
3. **Dead Code**: Orphaned files that also define no used entities
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from src.constants import MemgraphLabels

logger = logging.getLogger(__name__)


class OrphanFile(BaseModel):
    """Represents an orphaned file"""

    file_path: str = Field(..., description="Full file path")
    relative_path: str = Field(..., description="Project-relative path")
    orphan_type: str = Field(
        ..., description="Orphan type: no_imports, unreachable, or dead_code"
    )
    reason: str = Field(..., description="Explanation of why file is orphaned")
    entry_point_distance: Optional[int] = Field(
        None, description="Hops from nearest entry point"
    )
    import_count: int = Field(0, description="Number of outgoing imports")
    entity_count: int = Field(0, description="Number of defined entities")
    last_modified: Optional[str] = Field(
        None, description="Last modification timestamp"
    )


class OrphanDetectionResult(BaseModel):
    """Result of orphan detection analysis"""

    project: str = Field(..., description="Project name")
    orphaned_files: List[OrphanFile] = Field(
        default_factory=list, description="Files with no incoming imports"
    )
    unreachable_files: List[OrphanFile] = Field(
        default_factory=list, description="Files unreachable from entry points"
    )
    dead_code_files: List[OrphanFile] = Field(
        default_factory=list, description="Orphaned files with no used entities"
    )
    total_files: int = Field(0, description="Total number of files in project")
    total_orphans: int = Field(0, description="Total number of orphaned files")
    entry_points: List[str] = Field(
        default_factory=list, description="Entry point files used for analysis"
    )
    scan_timestamp: str = Field(..., description="ISO timestamp of scan")


class OrphanDetector:
    """
    Detects orphaned and unreachable files using Memgraph graph queries.

    Uses graph analysis to identify files that are:
    - Not imported by any other files
    - Unreachable from project entry points
    - Dead code (orphaned with no used entities)
    """

    def __init__(self, memgraph_adapter):
        """
        Initialize orphan detector.

        Args:
            memgraph_adapter: MemgraphKnowledgeAdapter instance
        """
        self.memgraph = memgraph_adapter

        # Entry point patterns (common entry files)
        self.entry_point_patterns = [
            "main.py",
            "app.py",
            "__main__.py",
            "manage.py",
            "server.py",
            "index.py",
            "cli.py",
        ]

    async def detect_orphans(
        self, project_name: str, custom_entry_points: Optional[List[str]] = None
    ) -> OrphanDetectionResult:
        """
        Detect all types of orphaned files in a project.

        Args:
            project_name: Project to analyze
            custom_entry_points: Optional custom entry point file names

        Returns:
            OrphanDetectionResult with all orphaned files

        Example:
            result = await detector.detect_orphans("omniarchon")
            print(f"Found {result.total_orphans} orphaned files")
        """
        # Entry logging
        logger.info(
            f"ENTER detect_orphans: project_name={project_name}, "
            f"custom_entry_points={custom_entry_points}"
        )

        try:
            # Step 1: Identify entry points
            entry_points = await self._find_entry_points(
                project_name, custom_entry_points
            )

            # Step 2: Find files with no incoming imports
            no_import_files = await self._find_no_incoming_imports(project_name)

            # Step 3: Find unreachable files from entry points
            unreachable_files = await self._find_unreachable_files(
                project_name, entry_points
            )

            # Step 4: Find dead code (orphaned + no used entities)
            dead_code_files = await self._find_dead_code(project_name)

            # Step 5: Get total file count
            total_files = await self._count_project_files(project_name)

            result = OrphanDetectionResult(
                project=project_name,
                orphaned_files=no_import_files,
                unreachable_files=unreachable_files,
                dead_code_files=dead_code_files,
                total_files=total_files,
                total_orphans=len(no_import_files),
                entry_points=[ep["path"] for ep in entry_points],
                scan_timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Success exit logging
            logger.info(
                f"EXIT detect_orphans: SUCCESS - total_files={result.total_files}, "
                f"orphans={result.total_orphans}, unreachable={len(unreachable_files)}, "
                f"dead_code={len(dead_code_files)}"
            )

            return result

        except Exception as e:
            logger.error(
                f"EXIT detect_orphans: ERROR - {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            raise

    async def _find_entry_points(
        self, project_name: str, custom_patterns: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Find entry point files in project.

        Entry points are files that typically serve as the starting point
        of execution (main.py, app.py, etc.).

        Args:
            project_name: Project to search
            custom_patterns: Optional custom entry point file names

        Returns:
            List of entry point file metadata
        """
        patterns = custom_patterns or self.entry_point_patterns

        query = f"""
        MATCH (project:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:CONTAINS*]->(file:{MemgraphLabels.FILE})
        WHERE file.name IN $patterns
        RETURN file.entity_id as id,
               file.path as path,
               file.relative_path as relative_path
        ORDER BY file.name
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(
                query, project_name=project_name, patterns=patterns
            )

            records = await result.values()
            entry_points = [
                {"id": r[0], "path": r[1], "relative_path": r[2]} for r in records
            ]

            logger.info(
                f"🔍 [ORPHAN] Found entry points | "
                f"count={len(entry_points)} | "
                f"patterns={patterns}"
            )

            return entry_points

    async def _find_no_incoming_imports(self, project_name: str) -> List[OrphanFile]:
        """
        Find files with no incoming IMPORTS relationships.

        These are files that are not imported by any other file in the project,
        indicating they may be unused or orphaned.

        Args:
            project_name: Project to analyze

        Returns:
            List of OrphanFile instances for files with no imports
        """
        query = f"""
        MATCH (project:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:CONTAINS*]->(file:{MemgraphLabels.FILE})
        WHERE NOT file.name IN ['__init__.py', '__pycache__']
        OPTIONAL MATCH import_path = (file)<-[:IMPORTS]-()
        WITH file, import_path
        WHERE import_path IS NULL
        RETURN file.path as path,
               file.relative_path as relative_path,
               file.import_count as imports,
               file.entity_count as entities,
               file.last_modified as modified
        ORDER BY file.relative_path
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            records = await result.values()

            orphan_files = [
                OrphanFile(
                    file_path=r[0],
                    relative_path=r[1],
                    orphan_type="no_imports",
                    reason="No other files import this file",
                    import_count=r[2] or 0,
                    entity_count=r[3] or 0,
                    last_modified=r[4],
                )
                for r in records
            ]

            logger.info(
                f"🔍 [ORPHAN] No incoming imports | "
                f"project={project_name} | "
                f"count={len(orphan_files)}"
            )

            return orphan_files

    async def _find_unreachable_files(
        self, project_name: str, entry_points: List[Dict]
    ) -> List[OrphanFile]:
        """
        Find files unreachable from entry points via import chains.

        Uses graph traversal to find all files reachable from entry points,
        then identifies files NOT in that set. These files exist but cannot
        be reached through the import dependency chain.

        Args:
            project_name: Project to analyze
            entry_points: List of entry point file metadata

        Returns:
            List of OrphanFile instances for unreachable files
        """
        if not entry_points:
            logger.warning(
                "🔍 [ORPHAN] No entry points found | " "skipping reachability analysis"
            )
            return []

        # Get all reachable files from entry points
        entry_point_ids = [ep["id"] for ep in entry_points]

        query = f"""
        MATCH path = (entry:{MemgraphLabels.FILE})-[:IMPORTS*0..10]->(reachable:{MemgraphLabels.FILE})
        WHERE entry.entity_id IN $entry_point_ids
        WITH COLLECT(DISTINCT reachable.entity_id) AS reachable_ids

        MATCH (project:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:CONTAINS*]->(file:{MemgraphLabels.FILE})
        WHERE NOT file.entity_id IN reachable_ids
          AND NOT file.name IN ['__init__.py']
        RETURN file.path as path,
               file.relative_path as relative_path,
               file.import_count as imports,
               file.entity_count as entities,
               file.last_modified as modified
        ORDER BY file.relative_path
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(
                query, entry_point_ids=entry_point_ids, project_name=project_name
            )
            records = await result.values()

            # Create entry point summary for reason
            entry_point_summary = ", ".join(
                [ep["relative_path"] for ep in entry_points[:3]]
            )

            unreachable_files = [
                OrphanFile(
                    file_path=r[0],
                    relative_path=r[1],
                    orphan_type="unreachable",
                    reason=f"Not reachable from entry points: {entry_point_summary}",
                    import_count=r[2] or 0,
                    entity_count=r[3] or 0,
                    last_modified=r[4],
                )
                for r in records
            ]

            logger.info(
                f"🔍 [ORPHAN] Unreachable files | "
                f"project={project_name} | "
                f"entry_points={len(entry_points)} | "
                f"count={len(unreachable_files)}"
            )

            return unreachable_files

    async def _find_dead_code(self, project_name: str) -> List[OrphanFile]:
        """
        Find dead code files (no imports AND entities not used).

        Dead code files are the most severe type of orphan:
        - No other files import them (orphaned)
        - They define no entities that are used elsewhere
        - High confidence candidates for removal

        Args:
            project_name: Project to analyze

        Returns:
            List of OrphanFile instances for dead code files
        """
        query = f"""
        MATCH (project:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:CONTAINS*]->(file:{MemgraphLabels.FILE})
        WHERE NOT file.name IN ['__init__.py']
        OPTIONAL MATCH import_path = (file)<-[:IMPORTS]-()
        OPTIONAL MATCH usage_path = (file)-[:DEFINES]->()<-[:CALLS|EXTENDS]-()
        WITH file, import_path, usage_path
        WHERE import_path IS NULL AND usage_path IS NULL
        RETURN file.path as path,
               file.relative_path as relative_path,
               file.entity_count as entities,
               file.last_modified as modified
        ORDER BY file.relative_path
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            records = await result.values()

            dead_code_files = [
                OrphanFile(
                    file_path=r[0],
                    relative_path=r[1],
                    orphan_type="dead_code",
                    reason="File has no imports and defines no used entities",
                    import_count=0,
                    entity_count=r[2] or 0,
                    last_modified=r[3],
                )
                for r in records
            ]

            logger.info(
                f"🔍 [ORPHAN] Dead code files | "
                f"project={project_name} | "
                f"count={len(dead_code_files)}"
            )

            return dead_code_files

    async def _count_project_files(self, project_name: str) -> int:
        """
        Count total files in project.

        Args:
            project_name: Project to count

        Returns:
            Total number of FILE nodes in project
        """
        query = f"""
        MATCH (project:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:CONTAINS*]->(file:{MemgraphLabels.FILE})
        RETURN count(file) as total
        """

        async with self.memgraph.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            record = await result.single()
            total = record["total"] if record else 0

            logger.info(
                f"🔍 [ORPHAN] Project file count | "
                f"project={project_name} | "
                f"total={total}"
            )

            return total
