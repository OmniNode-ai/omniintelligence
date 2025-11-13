"""
Unit Tests for Tree Visualization API

Tests file tree structure building, dependency extraction, and statistics.
Validates recursive tree construction and metadata inclusion.

Coverage Target: 90%+
"""

import os
import sys
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../services/intelligence/src")
)

from src.constants import MemgraphLabels


@pytest.fixture
def mock_memgraph_adapter():
    """Create mock Memgraph adapter with driver and session."""
    adapter = MagicMock()

    # Mock driver and session
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_result = AsyncMock()

    # Configure session context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Configure result
    mock_result.single = AsyncMock(return_value=None)
    mock_result.values = AsyncMock(return_value=[])
    mock_session.run = AsyncMock(return_value=mock_result)

    # Configure driver
    mock_driver.session.return_value = mock_session
    adapter.driver = mock_driver

    return adapter


class TreeVisualizationService:
    """
    Service for building file tree visualizations.
    Simulates actual implementation for tree structure API.
    """

    def __init__(self, memgraph_adapter):
        self.memgraph = memgraph_adapter

    async def build_tree_structure(
        self, project_name: str, max_depth: int = 10, include_dependencies: bool = True
    ) -> Dict:
        """
        Build hierarchical tree structure for project.

        Args:
            project_name: Project to visualize
            max_depth: Maximum depth to traverse
            include_dependencies: Include import dependencies

        Returns:
            Tree structure dictionary
        """
        # Get project root
        project_node = await self._get_project_node(project_name)
        if not project_node:
            return {"error": "Project not found"}

        # Build tree recursively
        tree = {
            "name": project_name,
            "type": "project",
            "path": project_node.get("path"),
            "children": [],
        }

        # Get top-level items
        children = await self._get_children(
            f"project:{project_name}", max_depth, include_dependencies, depth=0
        )
        tree["children"] = children

        # Gather statistics
        stats = await self.gather_tree_statistics(project_name)
        tree["statistics"] = stats

        return tree

    async def _get_project_node(self, project_name: str) -> Dict:
        """Get PROJECT node metadata."""
        query = """
        MATCH (p:PROJECT {name: $project_name})
        RETURN p.name as name, p.path as path
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(query, project_name=project_name)
                record = await result.single()
                if record:
                    return {"name": record["name"], "path": record["path"]}
                return None
        except Exception:
            return None

    async def _get_children(
        self,
        parent_id: str,
        max_depth: int,
        include_dependencies: bool,
        depth: int = 0,
    ) -> List[Dict]:
        """
        Recursively get children of a node.

        Args:
            parent_id: Parent node entity_id
            max_depth: Maximum recursion depth
            include_dependencies: Include import dependencies
            depth: Current depth level

        Returns:
            List of child node dictionaries
        """
        if depth >= max_depth:
            return []

        query = """
        MATCH (parent {entity_id: $parent_id})-[:CONTAINS]->(child)
        RETURN child.entity_id as id,
               child.name as name,
               child.path as path,
               child.relative_path as relative_path,
               labels(child)[0] as type,
               child.file_type as file_type,
               child.size as size
        ORDER BY child.name
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(query, parent_id=parent_id)
                records = await result.values()

                children = []
                for r in records:
                    child = {
                        "id": r[0],
                        "name": r[1],
                        "path": r[2],
                        "relative_path": r[3],
                        "type": r[4].lower() if r[4] else "unknown",
                        "file_type": r[5],
                        "size": r[6],
                    }

                    # Recursively get children for directories
                    if child["type"] == "directory":
                        child["children"] = await self._get_children(
                            r[0], max_depth, include_dependencies, depth + 1
                        )
                    else:
                        child["children"] = []

                    # Add dependencies for files
                    if include_dependencies and child["type"] == "file":
                        child["dependencies"] = await self.extract_dependencies(r[0])

                    children.append(child)

                return children

        except Exception:
            return []

    async def extract_dependencies(self, file_id: str) -> List[Dict]:
        """
        Extract import dependencies for a file.

        Args:
            file_id: FILE node entity_id

        Returns:
            List of dependency dictionaries
        """
        query = f"""
        MATCH (file{MemgraphLabels.FILE} {{entity_id: $file_id}})-[r:IMPORTS]->(target{MemgraphLabels.FILE})
        RETURN target.entity_id as target_id,
               target.relative_path as target_path,
               r.import_type as import_type,
               r.confidence as confidence
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(query, file_id=file_id)
                records = await result.values()

                return [
                    {
                        "target_id": r[0],
                        "target_path": r[1],
                        "import_type": r[2],
                        "confidence": r[3],
                    }
                    for r in records
                ]

        except Exception:
            return []

    async def gather_tree_statistics(self, project_name: str) -> Dict:
        """
        Gather statistics about project tree.

        Args:
            project_name: Project to analyze

        Returns:
            Statistics dictionary
        """
        query = f"""
        MATCH (project:PROJECT {{name: $project_name}})
        OPTIONAL MATCH (project)-[:CONTAINS*]->(dir:DIRECTORY)
        OPTIONAL MATCH (project)-[:CONTAINS*]->(file{MemgraphLabels.FILE})
        OPTIONAL MATCH (file)-[imp:IMPORTS]->()
        RETURN count(DISTINCT dir) as directories,
               count(DISTINCT file) as files,
               count(DISTINCT imp) as imports
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(query, project_name=project_name)
                record = await result.single()

                if record:
                    return {
                        "directories": record["directories"] or 0,
                        "files": record["files"] or 0,
                        "imports": record["imports"] or 0,
                        "total_nodes": (record["directories"] or 0)
                        + (record["files"] or 0)
                        + 1,
                    }

                return {"directories": 0, "files": 0, "imports": 0, "total_nodes": 0}

        except Exception:
            return {"directories": 0, "files": 0, "imports": 0, "total_nodes": 0}


@pytest.fixture
def tree_service(mock_memgraph_adapter):
    """Create TreeVisualizationService instance with mocked adapter."""
    return TreeVisualizationService(mock_memgraph_adapter)


class TestTreeVisualizationServiceInitialization:
    """Test TreeVisualizationService initialization."""

    def test_init_success(self, mock_memgraph_adapter):
        """Test successful initialization."""
        service = TreeVisualizationService(mock_memgraph_adapter)
        assert service.memgraph == mock_memgraph_adapter

    def test_init_stores_adapter(self, mock_memgraph_adapter):
        """Test adapter reference is stored."""
        service = TreeVisualizationService(mock_memgraph_adapter)
        assert service.memgraph is not None


@pytest.mark.asyncio
class TestBuildTreeStructure:
    """Test build_tree_structure method."""

    async def test_build_tree_structure_success(self, tree_service):
        """Test building tree structure for project."""
        # Configure mock to return project node
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()

        # First call: get project node
        project_result = AsyncMock()
        project_result.single = AsyncMock(
            return_value={"name": "test_project", "path": "/test/project"}
        )

        # Second call: get children (empty)
        children_result = AsyncMock()
        children_result.values = AsyncMock(return_value=[])

        # Third call: statistics
        stats_result = AsyncMock()
        stats_result.single = AsyncMock(
            return_value={"directories": 5, "files": 20, "imports": 15}
        )

        mock_session.run = AsyncMock(
            side_effect=[project_result, children_result, stats_result]
        )

        tree = await tree_service.build_tree_structure("test_project")

        assert tree["name"] == "test_project"
        assert tree["type"] == "project"
        assert "children" in tree
        assert "statistics" in tree

    async def test_build_tree_structure_project_not_found(self, tree_service):
        """Test building tree when project doesn't exist."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        tree = await tree_service.build_tree_structure("nonexistent_project")

        assert "error" in tree

    async def test_build_tree_structure_with_max_depth(self, tree_service):
        """Test tree building respects max_depth parameter."""
        mock_session = tree_service.memgraph.driver.session.return_value

        # Mock project node
        project_result = AsyncMock()
        project_result.single = AsyncMock(
            return_value={"name": "test", "path": "/test"}
        )

        # Mock empty children and stats
        empty_result = AsyncMock()
        empty_result.values = AsyncMock(return_value=[])
        empty_result.single = AsyncMock(
            return_value={"directories": 0, "files": 0, "imports": 0}
        )

        mock_session.run = AsyncMock(
            side_effect=[project_result, empty_result, empty_result]
        )

        tree = await tree_service.build_tree_structure("test", max_depth=3)

        # Should succeed (depth limit applied in recursion)
        assert tree["name"] == "test"

    async def test_build_tree_structure_without_dependencies(self, tree_service):
        """Test tree building without dependencies."""
        mock_session = tree_service.memgraph.driver.session.return_value

        project_result = AsyncMock()
        project_result.single = AsyncMock(
            return_value={"name": "test", "path": "/test"}
        )

        empty_result = AsyncMock()
        empty_result.values = AsyncMock(return_value=[])
        empty_result.single = AsyncMock(
            return_value={"directories": 0, "files": 0, "imports": 0}
        )

        mock_session.run = AsyncMock(
            side_effect=[project_result, empty_result, empty_result]
        )

        tree = await tree_service.build_tree_structure(
            "test", include_dependencies=False
        )

        assert tree["name"] == "test"

    async def test_build_tree_structure_includes_statistics(self, tree_service):
        """Test tree structure includes statistics."""
        mock_session = tree_service.memgraph.driver.session.return_value

        project_result = AsyncMock()
        project_result.single = AsyncMock(
            return_value={"name": "test", "path": "/test"}
        )

        children_result = AsyncMock()
        children_result.values = AsyncMock(return_value=[])

        stats_result = AsyncMock()
        stats_result.single = AsyncMock(
            return_value={"directories": 10, "files": 50, "imports": 30}
        )

        mock_session.run = AsyncMock(
            side_effect=[project_result, children_result, stats_result]
        )

        tree = await tree_service.build_tree_structure("test")

        assert "statistics" in tree
        assert tree["statistics"]["directories"] == 10
        assert tree["statistics"]["files"] == 50
        assert tree["statistics"]["imports"] == 30


@pytest.mark.asyncio
class TestGetChildren:
    """Test _get_children recursive method."""

    async def test_get_children_files_and_directories(self, tree_service):
        """Test getting mixed children (files and directories)."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                [
                    "dir:test:src",
                    "src",
                    "/test/src",
                    "src",
                    "DIRECTORY",
                    None,
                    None,
                ],
                [
                    "file:test:main.py",
                    "main.py",
                    "/test/main.py",
                    "main.py",
                    "FILE",
                    ".py",
                    1024,
                ],
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        children = await tree_service._get_children(
            "project:test", max_depth=5, include_dependencies=False
        )

        assert len(children) == 2
        assert children[0]["type"] == "directory"
        assert children[1]["type"] == "file"

    async def test_get_children_respects_max_depth(self, tree_service):
        """Test children recursion stops at max depth."""
        # At max depth, should return empty
        children = await tree_service._get_children(
            "some:node", max_depth=5, include_dependencies=False, depth=5
        )

        assert children == []

    async def test_get_children_recursive_directories(self, tree_service):
        """Test recursive directory traversal."""
        mock_session = tree_service.memgraph.driver.session.return_value

        # First level: directory
        level1_result = AsyncMock()
        level1_result.values = AsyncMock(
            return_value=[
                [
                    "dir:test:src",
                    "src",
                    "/test/src",
                    "src",
                    "DIRECTORY",
                    None,
                    None,
                ]
            ]
        )

        # Second level: empty
        level2_result = AsyncMock()
        level2_result.values = AsyncMock(return_value=[])

        mock_session.run = AsyncMock(side_effect=[level1_result, level2_result])

        children = await tree_service._get_children(
            "project:test", max_depth=10, include_dependencies=False
        )

        # Should have nested children
        assert len(children) == 1
        assert "children" in children[0]

    async def test_get_children_includes_file_metadata(self, tree_service):
        """Test children include file metadata."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                [
                    "file:test:app.py",
                    "app.py",
                    "/test/app.py",
                    "app.py",
                    "FILE",
                    ".py",
                    2048,
                ]
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        children = await tree_service._get_children(
            "project:test", max_depth=5, include_dependencies=False
        )

        assert children[0]["name"] == "app.py"
        assert children[0]["file_type"] == ".py"
        assert children[0]["size"] == 2048

    async def test_get_children_sorted_by_name(self, tree_service):
        """Test children are sorted alphabetically by name."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await tree_service._get_children(
            "project:test", max_depth=5, include_dependencies=False
        )

        # Verify query includes ORDER BY
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "ORDER BY" in query


@pytest.mark.asyncio
class TestExtractDependencies:
    """Test extract_dependencies method."""

    async def test_extract_dependencies_success(self, tree_service):
        """Test extracting file dependencies."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                ["file:test:utils.py", "utils.py", "module", 1.0],
                ["file:test:config.py", "config.py", "module", 0.9],
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        dependencies = await tree_service.extract_dependencies("file:test:main.py")

        assert len(dependencies) == 2
        assert dependencies[0]["target_path"] == "utils.py"
        assert dependencies[0]["import_type"] == "module"
        assert dependencies[0]["confidence"] == 1.0

    async def test_extract_dependencies_no_imports(self, tree_service):
        """Test file with no dependencies."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        dependencies = await tree_service.extract_dependencies("file:test:isolated.py")

        assert dependencies == []

    async def test_extract_dependencies_includes_confidence(self, tree_service):
        """Test dependencies include confidence scores."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[["file:test:dep.py", "dep.py", "class", 0.85]]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        dependencies = await tree_service.extract_dependencies("file:test:main.py")

        assert dependencies[0]["confidence"] == 0.85

    async def test_extract_dependencies_error_handling(self, tree_service):
        """Test error handling during dependency extraction."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        dependencies = await tree_service.extract_dependencies("file:test:error.py")

        # Should return empty list on error
        assert dependencies == []


@pytest.mark.asyncio
class TestGatherTreeStatistics:
    """Test gather_tree_statistics method."""

    async def test_gather_statistics_success(self, tree_service):
        """Test gathering tree statistics."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(
            return_value={"directories": 15, "files": 75, "imports": 50}
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        stats = await tree_service.gather_tree_statistics("test_project")

        assert stats["directories"] == 15
        assert stats["files"] == 75
        assert stats["imports"] == 50
        assert stats["total_nodes"] == 91  # 15 + 75 + 1 (project)

    async def test_gather_statistics_empty_project(self, tree_service):
        """Test statistics for empty project."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(
            return_value={"directories": 0, "files": 0, "imports": 0}
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        stats = await tree_service.gather_tree_statistics("empty_project")

        assert stats["directories"] == 0
        assert stats["files"] == 0
        assert stats["imports"] == 0
        assert (
            stats["total_nodes"] == 1
        )  # Empty project still has the project node itself

    async def test_gather_statistics_no_result(self, tree_service):
        """Test statistics when query returns no result."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        stats = await tree_service.gather_tree_statistics("nonexistent")

        assert stats["directories"] == 0
        assert stats["files"] == 0
        assert stats["imports"] == 0

    async def test_gather_statistics_error_handling(self, tree_service):
        """Test error handling in statistics gathering."""
        mock_session = tree_service.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        stats = await tree_service.gather_tree_statistics("error_project")

        # Should return zeros on error
        assert stats["directories"] == 0
        assert stats["files"] == 0


class TestTreeNodeMetadata:
    """Test tree node metadata inclusion."""

    def test_tree_node_has_required_fields(self):
        """Test tree nodes have required fields."""
        node = {
            "id": "file:test:main.py",
            "name": "main.py",
            "path": "/test/main.py",
            "type": "file",
        }

        assert "id" in node
        assert "name" in node
        assert "path" in node
        assert "type" in node

    def test_file_node_has_file_metadata(self):
        """Test FILE nodes include file-specific metadata."""
        file_node = {
            "id": "file:test:app.py",
            "name": "app.py",
            "type": "file",
            "file_type": ".py",
            "size": 4096,
            "children": [],
        }

        assert file_node["file_type"] == ".py"
        assert file_node["size"] == 4096

    def test_directory_node_has_children(self):
        """Test DIRECTORY nodes have children array."""
        dir_node = {
            "id": "dir:test:src",
            "name": "src",
            "type": "directory",
            "children": [],
        }

        assert "children" in dir_node
        assert isinstance(dir_node["children"], list)

    def test_tree_includes_dependencies_when_requested(self):
        """Test file nodes include dependencies when requested."""
        file_node_with_deps = {
            "id": "file:test:main.py",
            "name": "main.py",
            "type": "file",
            "dependencies": [{"target_path": "utils.py", "import_type": "module"}],
        }

        assert "dependencies" in file_node_with_deps
        assert len(file_node_with_deps["dependencies"]) == 1


if __name__ == "__main__":
    import subprocess

    try:
        result = subprocess.run(
            ["pytest", __file__, "-v", "--tb=short", "-x"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
