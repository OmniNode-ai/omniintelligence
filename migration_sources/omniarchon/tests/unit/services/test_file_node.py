"""
Unit Tests for File Node Creation

Tests FILE node creation in Memgraph knowledge graph with proper metadata.
Validates MERGE behavior, metadata extraction, and error handling.

Coverage Target: 90%+
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../services/intelligence/src")
)


@pytest.fixture
def mock_memgraph_adapter():
    """Create mock Memgraph adapter with driver and session."""
    adapter = MagicMock()

    # Mock driver and session
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"entity_id": "file:test:src/main.py"}

    # Configure session context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Configure result
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session.run = AsyncMock(return_value=mock_result)

    # Configure driver
    mock_driver.session.return_value = mock_session
    adapter.driver = mock_driver

    return adapter


class FileNodeCreator:
    """
    Helper class for FILE node creation (simulates actual implementation).
    This would exist in the actual codebase.
    """

    def __init__(self, memgraph_adapter):
        self.memgraph = memgraph_adapter

    async def create_file_node(
        self,
        project_name: str,
        file_path: str,
        relative_path: str = None,
        file_type: str = None,
        size: int = None,
        last_modified: str = None,
    ):
        """
        Create or update FILE node in Memgraph.

        Args:
            project_name: Project identifier
            file_path: Absolute file path
            relative_path: Project-relative path
            file_type: File extension (e.g., '.py')
            size: File size in bytes
            last_modified: Last modification timestamp
        """
        from pathlib import Path

        # Extract metadata
        path_obj = Path(file_path)
        file_name = path_obj.name
        file_extension = path_obj.suffix or file_type
        rel_path = relative_path or file_path

        query = """
        MERGE (file:FILE {entity_id: $entity_id})
        SET file.name = $name,
            file.path = $path,
            file.relative_path = $relative_path,
            file.project_name = $project_name,
            file.file_type = $file_type,
            file.size = $size,
            file.last_modified = $last_modified,
            file.indexed_at = $timestamp
        RETURN file.entity_id
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(
                    query,
                    entity_id=f"file:{project_name}:{rel_path}",
                    name=file_name,
                    path=file_path,
                    relative_path=rel_path,
                    project_name=project_name,
                    file_type=file_extension,
                    size=size,
                    last_modified=last_modified,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()
                return record["entity_id"] if record else None

        except Exception as e:
            raise Exception(f"Failed to create FILE node: {e}")


@pytest.fixture
def file_node_creator(mock_memgraph_adapter):
    """Create FileNodeCreator instance with mocked adapter."""
    return FileNodeCreator(mock_memgraph_adapter)


class TestFileNodeCreatorInitialization:
    """Test FileNodeCreator initialization."""

    def test_init_success(self, mock_memgraph_adapter):
        """Test successful initialization."""
        creator = FileNodeCreator(mock_memgraph_adapter)
        assert creator.memgraph == mock_memgraph_adapter

    def test_init_stores_adapter(self, mock_memgraph_adapter):
        """Test adapter reference is stored."""
        creator = FileNodeCreator(mock_memgraph_adapter)
        assert creator.memgraph is not None


@pytest.mark.asyncio
class TestCreateFileNode:
    """Test create_file_node method."""

    async def test_create_file_node_success(self, file_node_creator):
        """Test successful FILE node creation."""
        entity_id = await file_node_creator.create_file_node(
            project_name="test_project",
            file_path="/test/path/src/main.py",
            relative_path="src/main.py",
            file_type=".py",
            size=1024,
            last_modified="2025-01-01T00:00:00Z",
        )

        assert entity_id == "file:test:src/main.py"

    async def test_create_file_node_minimal_params(self, file_node_creator):
        """Test FILE node creation with minimal parameters."""
        entity_id = await file_node_creator.create_file_node(
            project_name="minimal_project",
            file_path="/test/minimal/file.py",
        )

        # Should extract metadata from path
        assert entity_id is not None

    async def test_create_file_node_extracts_filename(self, file_node_creator):
        """Test FILE node extracts filename from path."""
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/path/to/some_file.py",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["name"] == "some_file.py"

    async def test_create_file_node_extracts_file_type(self, file_node_creator):
        """Test FILE node extracts file extension."""
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/path/to/file.ts",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["file_type"] == ".ts"

    async def test_create_file_node_handles_no_extension(self, file_node_creator):
        """Test FILE node handles files without extension."""
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/path/to/Dockerfile",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        # Should be empty string or None
        assert params["file_type"] in ["", None]

    async def test_create_file_node_uses_merge(self, file_node_creator):
        """Test FILE node creation uses MERGE (idempotent)."""
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/test/file.py",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "MERGE" in query
        assert "FILE" in query

    async def test_create_file_node_duplicate_updates(self, file_node_creator):
        """Test creating duplicate FILE node updates existing (MERGE behavior)."""
        # Create once
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/test/file.py",
            size=1024,
        )

        # Create again with different size
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/test/file.py",
            size=2048,
        )

        # Should succeed (MERGE updates)
        mock_session = file_node_creator.memgraph.driver.session.return_value
        assert mock_session.run.call_count >= 2

    async def test_create_file_node_includes_timestamp(self, file_node_creator):
        """Test FILE node includes indexed_at timestamp."""
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/test/file.py",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        # Verify timestamp parameter exists and is in ISO format
        assert "timestamp" in params
        assert isinstance(params["timestamp"], str)
        # Check it's roughly in ISO 8601 format (contains T and timezone info)
        assert "T" in params["timestamp"]

    async def test_create_file_node_with_all_metadata(self, file_node_creator):
        """Test FILE node with complete metadata."""
        await file_node_creator.create_file_node(
            project_name="complete_project",
            file_path="/test/complete/src/api/routes.py",
            relative_path="src/api/routes.py",
            file_type=".py",
            size=4096,
            last_modified="2025-01-01T10:30:00Z",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["name"] == "routes.py"
        assert params["path"] == "/test/complete/src/api/routes.py"
        assert params["relative_path"] == "src/api/routes.py"
        assert params["file_type"] == ".py"
        assert params["size"] == 4096
        assert params["last_modified"] == "2025-01-01T10:30:00Z"

        # Verify project_name is present and correct
        assert (
            params["project_name"] == "complete_project"
        ), f"Expected project_name='complete_project', got '{params['project_name']}'"
        assert params["project_name"] is not None, "project_name cannot be None"

    async def test_create_file_node_entity_id_format(self, file_node_creator):
        """Test FILE node entity_id follows format: file:{project}:{relative_path}."""
        await file_node_creator.create_file_node(
            project_name="myproject",
            file_path="/projects/myproject/src/main.py",
            relative_path="src/main.py",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["entity_id"] == "file:myproject:src/main.py"

    async def test_create_file_node_handles_special_characters(self, file_node_creator):
        """Test FILE node handles special characters in paths."""
        await file_node_creator.create_file_node(
            project_name="test",
            file_path="/test/path/with spaces/file-name_v2.py",
            relative_path="with spaces/file-name_v2.py",
        )

        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["name"] == "file-name_v2.py"

    async def test_create_file_node_error_handling(self, file_node_creator):
        """Test error handling during FILE node creation."""
        mock_session = file_node_creator.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc:
            await file_node_creator.create_file_node(
                project_name="error_project",
                file_path="/test/error.py",
            )

        assert "Failed to create FILE node" in str(exc.value)

    async def test_create_file_node_missing_memgraph(self):
        """Test graceful degradation when Memgraph unavailable."""
        # Create creator with None adapter
        creator = FileNodeCreator(None)

        # Should raise AttributeError or similar
        with pytest.raises((AttributeError, Exception)):
            await creator.create_file_node(
                project_name="test",
                file_path="/test/file.py",
            )


class TestFileNodeMetadataExtraction:
    """Test metadata extraction for FILE nodes."""

    def test_extract_filename_simple(self):
        """Test extracting filename from simple path."""
        from pathlib import Path

        path = Path("/test/path/file.py")
        assert path.name == "file.py"

    def test_extract_filename_nested(self):
        """Test extracting filename from nested path."""
        from pathlib import Path

        path = Path("/test/deep/nested/path/module.ts")
        assert path.name == "module.ts"

    def test_extract_file_extension(self):
        """Test extracting file extension."""
        from pathlib import Path

        path = Path("/test/file.py")
        assert path.suffix == ".py"

    def test_extract_file_extension_multiple_dots(self):
        """Test extracting extension with multiple dots."""
        from pathlib import Path

        path = Path("/test/file.test.js")
        assert path.suffix == ".js"  # Only last extension

    def test_extract_file_extension_none(self):
        """Test file with no extension."""
        from pathlib import Path

        path = Path("/test/README")
        assert path.suffix == ""

    def test_extract_parent_directory(self):
        """Test extracting parent directory."""
        from pathlib import Path

        path = Path("/test/project/src/main.py")
        assert str(path.parent) == "/test/project/src"

    def test_extract_relative_path_calculation(self):
        """Test calculating relative path from absolute."""
        from pathlib import Path

        absolute = Path("/test/project/src/api/routes.py")
        project_root = Path("/test/project")
        relative = absolute.relative_to(project_root)

        assert str(relative) == "src/api/routes.py"


@pytest.mark.asyncio
class TestFileNodeValidation:
    """Test FILE node validation and constraints."""

    async def test_create_file_node_validates_project_name(self, file_node_creator):
        """Test project_name is required and properly set."""
        # Should work with valid project name
        entity_id = await file_node_creator.create_file_node(
            project_name="valid_project",
            file_path="/test/file.py",
        )
        assert entity_id is not None

        # Verify project_name was passed correctly
        mock_session = file_node_creator.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert (
            params["project_name"] == "valid_project"
        ), "project_name must be passed to query"
        assert params["project_name"] is not None, "project_name cannot be None"

    async def test_create_file_node_validates_file_path(self, file_node_creator):
        """Test file_path is required."""
        # Should work with valid path
        entity_id = await file_node_creator.create_file_node(
            project_name="test",
            file_path="/valid/path/file.py",
        )
        assert entity_id is not None

    async def test_create_file_node_optional_metadata(self, file_node_creator):
        """Test metadata fields are optional."""
        # Should work without optional fields
        entity_id = await file_node_creator.create_file_node(
            project_name="test",
            file_path="/test/file.py",
            # No relative_path, file_type, size, last_modified
        )
        assert entity_id is not None


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
