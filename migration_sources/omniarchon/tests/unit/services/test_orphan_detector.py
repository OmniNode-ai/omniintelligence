"""
Unit Tests for OrphanDetector Service

Tests orphan file detection using graph analysis.
Validates detection of no-import files, unreachable files, and dead code.

Coverage Target: 90%+
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../services/intelligence/src")
)

from services.orphan_detector import (
    OrphanDetectionResult,
    OrphanDetector,
    OrphanFile,
)


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

    # Configure result with default empty values
    mock_result.single = AsyncMock(return_value={"total": 0})
    mock_result.values = AsyncMock(return_value=[])
    mock_session.run = AsyncMock(return_value=mock_result)

    # Configure driver
    mock_driver.session.return_value = mock_session
    adapter.driver = mock_driver

    return adapter


@pytest.fixture
def orphan_detector(mock_memgraph_adapter):
    """Create OrphanDetector instance with mocked adapter."""
    return OrphanDetector(mock_memgraph_adapter)


class TestOrphanFileModel:
    """Test OrphanFile Pydantic model."""

    def test_orphan_file_creation(self):
        """Test creating OrphanFile instance."""
        orphan = OrphanFile(
            file_path="/test/path/orphan.py",
            relative_path="src/orphan.py",
            orphan_type="no_imports",
            reason="No other files import this file",
            import_count=0,
            entity_count=5,
        )

        assert orphan.file_path == "/test/path/orphan.py"
        assert orphan.relative_path == "src/orphan.py"
        assert orphan.orphan_type == "no_imports"
        assert orphan.import_count == 0
        assert orphan.entity_count == 5

    def test_orphan_file_with_defaults(self):
        """Test OrphanFile with default values."""
        orphan = OrphanFile(
            file_path="/test/orphan.py",
            relative_path="orphan.py",
            orphan_type="unreachable",
            reason="Not reachable from entry points",
        )

        assert orphan.import_count == 0  # Default
        assert orphan.entity_count == 0  # Default
        assert orphan.entry_point_distance is None  # Default

    def test_orphan_file_all_fields(self):
        """Test OrphanFile with all fields populated."""
        orphan = OrphanFile(
            file_path="/test/dead.py",
            relative_path="dead.py",
            orphan_type="dead_code",
            reason="Dead code",
            entry_point_distance=None,
            import_count=0,
            entity_count=0,
            last_modified="2025-01-01T00:00:00Z",
        )

        assert orphan.last_modified == "2025-01-01T00:00:00Z"


class TestOrphanDetectionResultModel:
    """Test OrphanDetectionResult Pydantic model."""

    def test_result_creation(self):
        """Test creating OrphanDetectionResult."""
        result = OrphanDetectionResult(
            project="test_project",
            orphaned_files=[],
            unreachable_files=[],
            dead_code_files=[],
            total_files=100,
            total_orphans=5,
            entry_points=["main.py", "app.py"],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        assert result.project == "test_project"
        assert result.total_files == 100
        assert result.total_orphans == 5
        assert len(result.entry_points) == 2

    def test_result_with_orphans(self):
        """Test result with orphan files."""
        orphan = OrphanFile(
            file_path="/test/orphan.py",
            relative_path="orphan.py",
            orphan_type="no_imports",
            reason="No imports",
        )

        result = OrphanDetectionResult(
            project="test",
            orphaned_files=[orphan],
            total_files=10,
            total_orphans=1,
            scan_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        assert len(result.orphaned_files) == 1
        assert result.orphaned_files[0].orphan_type == "no_imports"


class TestOrphanDetectorInitialization:
    """Test OrphanDetector initialization."""

    def test_init_success(self, mock_memgraph_adapter):
        """Test successful initialization."""
        detector = OrphanDetector(mock_memgraph_adapter)
        assert detector.memgraph == mock_memgraph_adapter

    def test_init_default_entry_point_patterns(self, orphan_detector):
        """Test default entry point patterns are set."""
        assert "main.py" in orphan_detector.entry_point_patterns
        assert "app.py" in orphan_detector.entry_point_patterns
        assert "__main__.py" in orphan_detector.entry_point_patterns

    def test_init_entry_point_patterns_complete(self, orphan_detector):
        """Test all expected entry point patterns."""
        expected_patterns = [
            "main.py",
            "app.py",
            "__main__.py",
            "manage.py",
            "server.py",
            "index.py",
            "cli.py",
        ]

        for pattern in expected_patterns:
            assert pattern in orphan_detector.entry_point_patterns


@pytest.mark.asyncio
class TestDetectOrphans:
    """Test detect_orphans method."""

    async def test_detect_orphans_success(self, orphan_detector):
        """Test successful orphan detection."""
        # Configure mocks
        mock_session = orphan_detector.memgraph.driver.session.return_value

        # Mock entry points
        entry_point_result = AsyncMock()
        entry_point_result.values = AsyncMock(
            return_value=[["file:test:main.py", "/test/main.py", "main.py"]]
        )

        # Mock file counts
        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 10})

        # Mock empty orphan results
        empty_result = AsyncMock()
        empty_result.values = AsyncMock(return_value=[])

        # Configure different returns for different queries
        mock_session.run = AsyncMock(
            side_effect=[
                entry_point_result,  # Entry points
                empty_result,  # No incoming imports
                empty_result,  # Unreachable files
                empty_result,  # Dead code
                count_result,  # File count
            ]
        )

        result = await orphan_detector.detect_orphans("test_project")

        assert result.project == "test_project"
        assert result.total_files == 10
        assert isinstance(result.scan_timestamp, str)

    async def test_detect_orphans_with_custom_entry_points(self, orphan_detector):
        """Test orphan detection with custom entry points."""
        custom_entry_points = ["custom_main.py", "custom_app.py"]

        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_result.single = AsyncMock(return_value={"total": 0})
        mock_session.run = AsyncMock(return_value=mock_result)

        result = await orphan_detector.detect_orphans(
            "test_project", custom_entry_points=custom_entry_points
        )

        # Verify custom patterns were used
        call_args = mock_session.run.call_args_list[0]
        params = call_args[1]
        assert params["patterns"] == custom_entry_points

    async def test_detect_orphans_finds_all_types(self, orphan_detector):
        """Test detection finds all orphan types."""
        mock_session = orphan_detector.memgraph.driver.session.return_value

        # Mock orphan files - no_imports and unreachable expect 5 values:
        # [path, relative_path, import_count, entity_count, last_modified]
        orphan_data_5 = [
            ["/test/orphan1.py", "orphan1.py", 0, 5, "2025-01-01T00:00:00Z"]
        ]

        # Mock dead code files - dead_code expects 4 values:
        # [path, relative_path, entity_count, last_modified]
        dead_code_data_4 = [["/test/dead.py", "dead.py", 3, "2025-01-01T00:00:00Z"]]

        orphan_result = AsyncMock()
        orphan_result.values = AsyncMock(return_value=orphan_data_5)

        dead_code_result = AsyncMock()
        dead_code_result.values = AsyncMock(return_value=dead_code_data_4)

        entry_point_result = AsyncMock()
        entry_point_result.values = AsyncMock(
            return_value=[["file:test:main.py", "/test/main.py", "main.py"]]
        )

        count_result = AsyncMock()
        count_result.single = AsyncMock(return_value={"total": 10})

        mock_session.run = AsyncMock(
            side_effect=[
                entry_point_result,
                orphan_result,  # No imports (5 values)
                orphan_result,  # Unreachable (5 values)
                dead_code_result,  # Dead code (4 values)
                count_result,
            ]
        )

        result = await orphan_detector.detect_orphans("test_project")

        assert len(result.orphaned_files) > 0
        assert len(result.unreachable_files) > 0
        assert len(result.dead_code_files) > 0

    async def test_detect_orphans_error_handling(self, orphan_detector):
        """Test error handling during detection."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc:
            await orphan_detector.detect_orphans("error_project")

        assert "Database error" in str(exc.value)


@pytest.mark.asyncio
class TestFindEntryPoints:
    """Test _find_entry_points method."""

    async def test_find_entry_points_default_patterns(self, orphan_detector):
        """Test finding entry points with default patterns."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                ["file:test:main.py", "/test/main.py", "main.py"],
                ["file:test:app.py", "/test/app.py", "app.py"],
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        entry_points = await orphan_detector._find_entry_points("test_project")

        assert len(entry_points) == 2
        assert entry_points[0]["path"] == "/test/main.py"
        assert entry_points[1]["path"] == "/test/app.py"

    async def test_find_entry_points_custom_patterns(self, orphan_detector):
        """Test finding entry points with custom patterns."""
        custom_patterns = ["custom.py", "start.py"]

        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_entry_points("test_project", custom_patterns)

        call_args = mock_session.run.call_args
        params = call_args[1]
        assert params["patterns"] == custom_patterns

    async def test_find_entry_points_none_found(self, orphan_detector):
        """Test when no entry points are found."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        entry_points = await orphan_detector._find_entry_points("test_project")

        assert entry_points == []

    async def test_find_entry_points_query_structure(self, orphan_detector):
        """Test entry points query structure."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_entry_points("test_project")

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "MATCH" in query
        assert "PROJECT" in query
        assert "FILE" in query
        assert "WHERE" in query


@pytest.mark.asyncio
class TestFindNoIncomingImports:
    """Test _find_no_incoming_imports method."""

    async def test_find_no_incoming_imports_success(self, orphan_detector):
        """Test finding files with no incoming imports."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                ["/test/orphan.py", "orphan.py", 0, 3, None],
                ["/test/unused.py", "unused.py", 2, 5, "2025-01-01T00:00:00Z"],
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        orphans = await orphan_detector._find_no_incoming_imports("test_project")

        assert len(orphans) == 2
        assert orphans[0].orphan_type == "no_imports"
        assert orphans[0].reason == "No other files import this file"

    async def test_find_no_incoming_imports_excludes_init(self, orphan_detector):
        """Test that __init__.py files are excluded."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_no_incoming_imports("test_project")

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        # Query should exclude __init__.py
        assert "__init__.py" in query
        assert "NOT" in query

    async def test_find_no_incoming_imports_empty_result(self, orphan_detector):
        """Test when no orphans are found."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        orphans = await orphan_detector._find_no_incoming_imports("test_project")

        assert orphans == []

    async def test_find_no_incoming_imports_query_checks_imports(self, orphan_detector):
        """Test query checks for IMPORTS relationships."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_no_incoming_imports("test_project")

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        # Should check for absence of incoming IMPORTS
        assert "IMPORTS" in query
        assert "NOT" in query


@pytest.mark.asyncio
class TestFindUnreachableFiles:
    """Test _find_unreachable_files method."""

    async def test_find_unreachable_files_success(self, orphan_detector):
        """Test finding unreachable files."""
        entry_points = [
            {
                "id": "file:test:main.py",
                "path": "/test/main.py",
                "relative_path": "main.py",
            }
        ]

        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[["/test/unreachable.py", "unreachable.py", 0, 2, None]]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        unreachable = await orphan_detector._find_unreachable_files(
            "test_project", entry_points
        )

        assert len(unreachable) == 1
        assert unreachable[0].orphan_type == "unreachable"

    async def test_find_unreachable_files_no_entry_points(self, orphan_detector):
        """Test with no entry points returns empty list."""
        unreachable = await orphan_detector._find_unreachable_files("test_project", [])

        assert unreachable == []

    async def test_find_unreachable_files_uses_graph_traversal(self, orphan_detector):
        """Test query uses graph traversal from entry points."""
        entry_points = [
            {
                "id": "file:test:main.py",
                "path": "/test/main.py",
                "relative_path": "main.py",
            }
        ]

        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_unreachable_files("test_project", entry_points)

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        # Should use variable-length path traversal
        assert "IMPORTS*" in query or "-[:IMPORTS]->" in query

    async def test_find_unreachable_files_includes_reason(self, orphan_detector):
        """Test unreachable files include descriptive reason."""
        entry_points = [
            {
                "id": "file:test:main.py",
                "path": "/test/main.py",
                "relative_path": "main.py",
            }
        ]

        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[["/test/unreachable.py", "unreachable.py", 0, 0, None]]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        unreachable = await orphan_detector._find_unreachable_files(
            "test_project", entry_points
        )

        assert "entry points" in unreachable[0].reason.lower()


@pytest.mark.asyncio
class TestFindDeadCode:
    """Test _find_dead_code method."""

    async def test_find_dead_code_success(self, orphan_detector):
        """Test finding dead code files."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[["/test/dead.py", "dead.py", 0, None]]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        dead_code = await orphan_detector._find_dead_code("test_project")

        assert len(dead_code) == 1
        assert dead_code[0].orphan_type == "dead_code"

    async def test_find_dead_code_checks_both_imports_and_usage(self, orphan_detector):
        """Test query checks both imports and entity usage."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_dead_code("test_project")

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        # Should check for no imports AND no used entities
        assert "IMPORTS" in query
        assert "DEFINES" in query or "CALLS" in query or "EXTENDS" in query

    async def test_find_dead_code_excludes_init_files(self, orphan_detector):
        """Test dead code detection excludes __init__.py."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._find_dead_code("test_project")

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "__init__.py" in query

    async def test_find_dead_code_empty_result(self, orphan_detector):
        """Test when no dead code is found."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        dead_code = await orphan_detector._find_dead_code("test_project")

        assert dead_code == []


@pytest.mark.asyncio
class TestCountProjectFiles:
    """Test _count_project_files method."""

    async def test_count_project_files_success(self, orphan_detector):
        """Test counting project files."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"total": 42})
        mock_session.run = AsyncMock(return_value=mock_result)

        count = await orphan_detector._count_project_files("test_project")

        assert count == 42

    async def test_count_project_files_zero(self, orphan_detector):
        """Test counting when no files exist."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"total": 0})
        mock_session.run = AsyncMock(return_value=mock_result)

        count = await orphan_detector._count_project_files("empty_project")

        assert count == 0

    async def test_count_project_files_no_result(self, orphan_detector):
        """Test counting when query returns no result."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        count = await orphan_detector._count_project_files("nonexistent")

        assert count == 0

    async def test_count_project_files_query_structure(self, orphan_detector):
        """Test file count query structure."""
        mock_session = orphan_detector.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"total": 0})
        mock_session.run = AsyncMock(return_value=mock_result)

        await orphan_detector._count_project_files("test_project")

        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "MATCH" in query
        assert "PROJECT" in query
        assert "FILE" in query
        assert "count" in query.lower()


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
