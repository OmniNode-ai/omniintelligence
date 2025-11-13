"""
Unit Tests for DirectoryIndexer Service

Tests directory hierarchy creation, navigation, and statistics.
Validates PROJECT → DIRECTORY → FILE hierarchy in Memgraph.

Coverage Target: 90%+
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../services/intelligence/src")
)

from services.directory_indexer import DirectoryIndexer


@pytest.fixture
def mock_memgraph_adapter():
    """Create mock Memgraph adapter with driver and session."""
    adapter = MagicMock()

    # Mock driver and session
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"entity_id": "test_entity_id"}

    # Configure session context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Configure result
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_result.values = AsyncMock(return_value=[])
    mock_session.run = AsyncMock(return_value=mock_result)

    # Configure driver
    mock_driver.session.return_value = mock_session
    adapter.driver = mock_driver

    return adapter


@pytest.fixture
def directory_indexer(mock_memgraph_adapter):
    """Create DirectoryIndexer instance with mocked adapter."""
    return DirectoryIndexer(mock_memgraph_adapter)


class TestDirectoryIndexerInitialization:
    """Test DirectoryIndexer initialization."""

    def test_init_success(self, mock_memgraph_adapter):
        """Test successful initialization with memgraph adapter."""
        indexer = DirectoryIndexer(mock_memgraph_adapter)
        assert indexer.memgraph == mock_memgraph_adapter

    def test_init_stores_adapter_reference(self, mock_memgraph_adapter):
        """Test that adapter reference is stored correctly."""
        indexer = DirectoryIndexer(mock_memgraph_adapter)
        assert indexer.memgraph is not None
        assert indexer.memgraph == mock_memgraph_adapter


@pytest.mark.asyncio
class TestIndexDirectoryHierarchy:
    """Test index_directory_hierarchy method."""

    async def test_index_simple_hierarchy(self, directory_indexer):
        """Test indexing simple project hierarchy."""
        project_name = "test_project"
        project_root = "/test/path/project"
        file_paths = [
            "/test/path/project/src/main.py",
            "/test/path/project/src/utils.py",
            "/test/path/project/tests/test_main.py",
        ]

        result = await directory_indexer.index_directory_hierarchy(
            project_name, project_root, file_paths
        )

        assert result["projects"] == 1
        assert result["directories"] >= 2  # At least src/ and tests/
        assert result["files"] == len(file_paths)
        assert result["relationships"] > 0

    async def test_index_nested_hierarchy(self, directory_indexer):
        """Test indexing deeply nested directory structure."""
        project_name = "nested_project"
        project_root = "/test/nested"
        file_paths = [
            "/test/nested/src/api/v1/routes/users.py",
            "/test/nested/src/api/v1/models/user.py",
            "/test/nested/src/services/auth/jwt.py",
        ]

        result = await directory_indexer.index_directory_hierarchy(
            project_name, project_root, file_paths
        )

        # Should have multiple directory levels
        assert (
            result["directories"] >= 5
        )  # src, api, v1, routes, models, services, auth
        assert result["files"] == len(file_paths)

    async def test_index_single_file(self, directory_indexer):
        """Test indexing project with single file."""
        project_name = "minimal_project"
        project_root = "/test/minimal"
        file_paths = ["/test/minimal/main.py"]

        result = await directory_indexer.index_directory_hierarchy(
            project_name, project_root, file_paths
        )

        assert result["projects"] == 1
        assert result["files"] == 1
        assert result["directories"] == 0  # No subdirectories

    async def test_index_empty_file_list(self, directory_indexer):
        """Test indexing with empty file list."""
        project_name = "empty_project"
        project_root = "/test/empty"
        file_paths = []

        result = await directory_indexer.index_directory_hierarchy(
            project_name, project_root, file_paths
        )

        assert result["projects"] == 1
        assert result["files"] == 0
        assert result["directories"] == 0

    async def test_index_duplicate_files(self, directory_indexer):
        """Test indexing with duplicate file paths (should be idempotent)."""
        project_name = "dup_project"
        project_root = "/test/dup"
        file_paths = [
            "/test/dup/src/main.py",
            "/test/dup/src/main.py",  # Duplicate
        ]

        result = await directory_indexer.index_directory_hierarchy(
            project_name, project_root, file_paths
        )

        # Should process all files (MERGE handles duplicates)
        assert result["files"] == len(file_paths)

    async def test_index_handles_memgraph_error(self, directory_indexer):
        """Test error handling when Memgraph operations fail."""
        # Configure mock to raise exception
        directory_indexer.memgraph.driver.session.side_effect = Exception(
            "Memgraph connection failed"
        )

        with pytest.raises(Exception) as exc:
            await directory_indexer.index_directory_hierarchy(
                "error_project", "/test/error", ["/test/error/file.py"]
            )

        assert "Memgraph connection failed" in str(exc.value)


@pytest.mark.asyncio
class TestCreateProjectNode:
    """Test _create_project_node method."""

    async def test_create_project_node_success(self, directory_indexer):
        """Test successful PROJECT node creation."""
        project_name = "test_project"
        project_root = "/test/path"

        await directory_indexer._create_project_node(project_name, project_root)

        # Verify session.run was called with correct query
        mock_session = directory_indexer.memgraph.driver.session.return_value
        assert mock_session.run.called

        # Check query contains MERGE for PROJECT
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "MERGE" in query
        assert "PROJECT" in query

    async def test_create_project_node_with_timestamp(self, directory_indexer):
        """Test PROJECT node includes indexed_at timestamp."""
        project_name = "timestamped_project"
        project_root = "/test/timestamped"

        with patch("services.directory_indexer.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.isoformat.return_value = "2025-01-01T12:00:00"
            mock_datetime.now.return_value = mock_now

            await directory_indexer._create_project_node(project_name, project_root)

        # Verify timestamp was included
        mock_session = directory_indexer.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        assert "timestamp" in call_args[1]

    async def test_create_project_node_idempotent(self, directory_indexer):
        """Test creating same project node twice (MERGE should handle)."""
        project_name = "same_project"
        project_root = "/test/same"

        # Create twice
        await directory_indexer._create_project_node(project_name, project_root)
        await directory_indexer._create_project_node(project_name, project_root)

        # Should succeed (MERGE makes it idempotent)
        mock_session = directory_indexer.memgraph.driver.session.return_value
        assert mock_session.run.call_count >= 2

    async def test_create_project_node_error_handling(self, directory_indexer):
        """Test error handling in project node creation."""
        mock_session = directory_indexer.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc:
            await directory_indexer._create_project_node("error_project", "/test/error")

        assert "Database error" in str(exc.value)


@pytest.mark.asyncio
class TestCreateDirectoryNode:
    """Test _create_directory_node method."""

    async def test_create_directory_node_success(self, directory_indexer):
        """Test successful DIRECTORY node creation."""
        project_name = "test_project"
        project_root = "/test/path"
        dir_path = "/test/path/src"

        await directory_indexer._create_directory_node(
            project_name, dir_path, project_root
        )

        mock_session = directory_indexer.memgraph.driver.session.return_value
        assert mock_session.run.called

        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "MERGE" in query
        assert "Directory" in query

    async def test_create_directory_node_extracts_name(self, directory_indexer):
        """Test DIRECTORY node extracts directory name from path."""
        project_name = "test_project"
        project_root = "/test/path"
        dir_path = "/test/path/to/directory"

        await directory_indexer._create_directory_node(
            project_name, dir_path, project_root
        )

        # Verify name parameter is just "directory"
        mock_session = directory_indexer.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]
        assert params["name"] == "directory"

    async def test_create_directory_node_with_metadata(self, directory_indexer):
        """Test DIRECTORY node includes all metadata."""
        project_name = "metadata_project"
        project_root = "/test/metadata"
        dir_path = "/test/metadata/src/api"

        await directory_indexer._create_directory_node(
            project_name, dir_path, project_root
        )

        mock_session = directory_indexer.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert "entity_id" in params
        assert "path" in params
        assert "project_name" in params
        assert "timestamp" in params

        # Verify project_name has correct value and is not None
        assert (
            params["project_name"] == project_name
        ), f"Expected project_name='{project_name}', got '{params['project_name']}'"
        assert params["project_name"] is not None, "project_name cannot be None"


@pytest.mark.asyncio
class TestCreateContainsRelationship:
    """Test _create_contains_relationship method."""

    async def test_create_contains_relationship_success(self, directory_indexer):
        """Test successful CONTAINS relationship creation."""
        parent_id = "project:test"
        child_id = "dir:test:src"
        parent_type = "PROJECT"
        child_type = "DIRECTORY"

        await directory_indexer._create_contains_relationship(
            parent_id, child_id, parent_type, child_type
        )

        mock_session = directory_indexer.memgraph.driver.session.return_value
        assert mock_session.run.called

        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "CONTAINS" in query
        assert "MERGE" in query

    async def test_create_contains_project_to_directory(self, directory_indexer):
        """Test PROJECT → DIRECTORY relationship."""
        parent_id = "project:myproject"
        child_id = "dir:myproject:src"

        await directory_indexer._create_contains_relationship(
            parent_id, child_id, "PROJECT", "DIRECTORY"
        )

        mock_session = directory_indexer.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "PROJECT" in query
        assert "DIRECTORY" in query

    async def test_create_contains_directory_to_file(self, directory_indexer):
        """Test DIRECTORY → FILE relationship."""
        parent_id = "dir:myproject:src"
        child_id = "file:myproject:src/main.py"

        await directory_indexer._create_contains_relationship(
            parent_id, child_id, "DIRECTORY", "FILE"
        )

        mock_session = directory_indexer.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "DIRECTORY" in query
        assert "FILE" in query

    async def test_create_contains_with_timestamp(self, directory_indexer):
        """Test CONTAINS relationship includes created_at timestamp."""
        await directory_indexer._create_contains_relationship(
            "parent:id", "child:id", "PROJECT", "DIRECTORY"
        )

        mock_session = directory_indexer.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert "timestamp" in params

    async def test_create_contains_missing_nodes(self, directory_indexer):
        """Test CONTAINS relationship when nodes don't exist."""
        # Configure mock to return None (no record found)
        mock_session = directory_indexer.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        # Should log warning but not raise exception
        await directory_indexer._create_contains_relationship(
            "missing:parent", "missing:child", "PROJECT", "DIRECTORY"
        )


class TestExtractDirectories:
    """Test _extract_directories method."""

    def test_extract_directories_simple(self, directory_indexer):
        """Test extracting directories from simple file paths."""
        file_paths = [
            "/project/src/main.py",
            "/project/src/utils.py",
            "/project/tests/test_main.py",
        ]
        project_root = "/project"

        directories = directory_indexer._extract_directories(file_paths, project_root)

        assert "/project/src" in directories
        assert "/project/tests" in directories
        assert project_root not in directories  # Root excluded

    def test_extract_directories_nested(self, directory_indexer):
        """Test extracting nested directory structure."""
        file_paths = [
            "/project/src/api/v1/routes/users.py",
            "/project/src/api/v1/models/user.py",
        ]
        project_root = "/project"

        directories = directory_indexer._extract_directories(file_paths, project_root)

        # Should include all parent directories
        assert "/project/src" in directories
        assert "/project/src/api" in directories
        assert "/project/src/api/v1" in directories
        assert "/project/src/api/v1/routes" in directories
        assert "/project/src/api/v1/models" in directories

    def test_extract_directories_removes_duplicates(self, directory_indexer):
        """Test duplicate directories are removed."""
        file_paths = [
            "/project/src/file1.py",
            "/project/src/file2.py",
            "/project/src/file3.py",
        ]
        project_root = "/project"

        directories = directory_indexer._extract_directories(file_paths, project_root)

        # Should only have one instance of /project/src
        assert directories.count("/project/src") == 1

    def test_extract_directories_sorted(self, directory_indexer):
        """Test directories are returned sorted."""
        file_paths = [
            "/project/zzz/file.py",
            "/project/aaa/file.py",
            "/project/mmm/file.py",
        ]
        project_root = "/project"

        directories = directory_indexer._extract_directories(file_paths, project_root)

        # Should be sorted alphabetically
        assert directories == sorted(directories)

    def test_extract_directories_empty_list(self, directory_indexer):
        """Test extracting from empty file list."""
        directories = directory_indexer._extract_directories([], "/project")
        assert directories == []

    def test_extract_directories_single_level(self, directory_indexer):
        """Test files directly in project root."""
        file_paths = ["/project/main.py"]
        project_root = "/project"

        directories = directory_indexer._extract_directories(file_paths, project_root)

        # No subdirectories
        assert directories == []


@pytest.mark.asyncio
class TestGetProjectStatistics:
    """Test get_project_statistics method."""

    async def test_get_statistics_success(self, directory_indexer):
        """Test getting project statistics."""
        # Configure mock to return statistics
        mock_session = directory_indexer.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_record = {
            "directory_count": 10,
            "file_count": 50,
            "total_nodes": 61,  # 10 + 50 + 1 (project node)
        }
        mock_result.single = AsyncMock(return_value=mock_record)
        mock_session.run = AsyncMock(return_value=mock_result)

        stats = await directory_indexer.get_project_statistics("test_project")

        assert stats["directories"] == 10
        assert stats["files"] == 50
        assert stats["total_nodes"] == 61

    async def test_get_statistics_empty_project(self, directory_indexer):
        """Test statistics for project with no files."""
        mock_session = directory_indexer.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_record = {
            "directory_count": 0,
            "file_count": 0,
            "total_nodes": 1,  # Just project node
        }
        mock_result.single = AsyncMock(return_value=mock_record)
        mock_session.run = AsyncMock(return_value=mock_result)

        stats = await directory_indexer.get_project_statistics("empty_project")

        assert stats["directories"] == 0
        assert stats["files"] == 0

    async def test_get_statistics_nonexistent_project(self, directory_indexer):
        """Test statistics for nonexistent project."""
        mock_session = directory_indexer.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        stats = await directory_indexer.get_project_statistics("nonexistent")

        assert stats["directories"] == 0
        assert stats["files"] == 0
        assert stats["total_nodes"] == 0

    async def test_get_statistics_error_handling(self, directory_indexer):
        """Test error handling in statistics retrieval."""
        mock_session = directory_indexer.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        stats = await directory_indexer.get_project_statistics("error_project")

        # Should return zeros on error
        assert stats["directories"] == 0
        assert stats["files"] == 0
        assert stats["total_nodes"] == 0


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
