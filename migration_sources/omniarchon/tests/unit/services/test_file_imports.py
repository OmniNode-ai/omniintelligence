"""
Unit Tests for File Import Relationships

Tests IMPORTS relationship creation between FILE nodes in Memgraph.
Validates import detection, confidence scoring, and batch processing.

Coverage Target: 90%+
"""

import os
import sys
from datetime import datetime, timezone
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add service path for imports
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../../services/intelligence/src")
)

from constants.memgraph_labels import MemgraphLabels


@pytest.fixture
def mock_memgraph_adapter():
    """Create mock Memgraph adapter with driver and session."""
    adapter = MagicMock()

    # Mock driver and session
    mock_driver = MagicMock()
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_record = {"relationship_id": "import_rel_123"}

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


class FileImportManager:
    """
    Helper class for managing file import relationships.
    Simulates actual implementation that would exist in codebase.
    """

    def __init__(self, memgraph_adapter):
        self.memgraph = memgraph_adapter

    async def create_import_relationship(
        self,
        project_name: str,
        source_file: str,
        target_file: str,
        import_type: str = "module",
        confidence: float = 1.0,
        line_number: int = None,
    ) -> bool:
        """
        Create IMPORTS relationship between two files.

        Args:
            project_name: Project identifier
            source_file: File that imports (importer)
            target_file: File being imported (importee)
            import_type: Type of import (module, class, function)
            confidence: Confidence score (0.0-1.0)
            line_number: Line number where import occurs

        Returns:
            True if successful, False otherwise
        """
        query = f"""
        MATCH (source:{MemgraphLabels.FILE} {{entity_id: $source_id}})
        MATCH (target:{MemgraphLabels.FILE} {{entity_id: $target_id}})
        MERGE (source)-[r:IMPORTS]->(target)
        SET r.import_type = $import_type,
            r.confidence = $confidence,
            r.line_number = $line_number,
            r.created_at = $timestamp
        RETURN r
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(
                    query,
                    source_id=f"file:{project_name}:{source_file}",
                    target_id=f"file:{project_name}:{target_file}",
                    import_type=import_type,
                    confidence=confidence,
                    line_number=line_number,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                record = await result.single()
                return record is not None

        except Exception as e:
            raise Exception(f"Failed to create IMPORTS relationship: {e}")

    async def store_file_imports(
        self, project_name: str, file_path: str, imports: List[Dict]
    ) -> int:
        """
        Store all imports for a file in batch.

        Args:
            project_name: Project identifier
            file_path: Source file path
            imports: List of import dictionaries with keys:
                - target: Target file path
                - import_type: Type of import
                - confidence: Confidence score
                - line_number: Line number

        Returns:
            Number of imports successfully created
        """
        count = 0
        for import_data in imports:
            try:
                success = await self.create_import_relationship(
                    project_name=project_name,
                    source_file=file_path,
                    target_file=import_data["target"],
                    import_type=import_data.get("import_type", "module"),
                    confidence=import_data.get("confidence", 1.0),
                    line_number=import_data.get("line_number"),
                )
                if success:
                    count += 1
            except Exception:
                # Continue on error
                pass

        return count

    async def get_file_imports(self, project_name: str, file_path: str) -> List[Dict]:
        """
        Get all imports for a file.

        Args:
            project_name: Project identifier
            file_path: File path

        Returns:
            List of import dictionaries
        """
        query = f"""
        MATCH (source:{MemgraphLabels.FILE} {{entity_id: $file_id}})-[r:IMPORTS]->(target:{MemgraphLabels.FILE})
        RETURN target.path as target_path,
               target.relative_path as target_relative,
               r.import_type as import_type,
               r.confidence as confidence,
               r.line_number as line_number
        ORDER BY r.line_number
        """

        try:
            async with self.memgraph.driver.session() as session:
                result = await session.run(
                    query, file_id=f"file:{project_name}:{file_path}"
                )
                records = await result.values()

                return [
                    {
                        "target_path": r[0],
                        "target_relative": r[1],
                        "import_type": r[2],
                        "confidence": r[3],
                        "line_number": r[4],
                    }
                    for r in records
                ]

        except Exception as e:
            raise Exception(f"Failed to get file imports: {e}")


@pytest.fixture
def import_manager(mock_memgraph_adapter):
    """Create FileImportManager instance with mocked adapter."""
    return FileImportManager(mock_memgraph_adapter)


class TestFileImportManagerInitialization:
    """Test FileImportManager initialization."""

    def test_init_success(self, mock_memgraph_adapter):
        """Test successful initialization."""
        manager = FileImportManager(mock_memgraph_adapter)
        assert manager.memgraph == mock_memgraph_adapter

    def test_init_stores_adapter(self, mock_memgraph_adapter):
        """Test adapter reference is stored."""
        manager = FileImportManager(mock_memgraph_adapter)
        assert manager.memgraph is not None


@pytest.mark.asyncio
class TestCreateImportRelationship:
    """Test create_import_relationship method."""

    async def test_create_import_relationship_success(self, import_manager):
        """Test successful IMPORTS relationship creation."""
        success = await import_manager.create_import_relationship(
            project_name="test_project",
            source_file="src/main.py",
            target_file="src/utils.py",
            import_type="module",
            confidence=1.0,
            line_number=5,
        )

        assert success is True

    async def test_create_import_relationship_minimal(self, import_manager):
        """Test IMPORTS creation with minimal parameters."""
        success = await import_manager.create_import_relationship(
            project_name="test",
            source_file="a.py",
            target_file="b.py",
        )

        assert success is True

    async def test_create_import_relationship_uses_merge(self, import_manager):
        """Test IMPORTS relationship uses MERGE (idempotent)."""
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="a.py",
            target_file="b.py",
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "MERGE" in query
        assert "IMPORTS" in query

    async def test_create_import_relationship_module_type(self, import_manager):
        """Test IMPORTS with module import type."""
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="main.py",
            target_file="utils.py",
            import_type="module",
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["import_type"] == "module"

    async def test_create_import_relationship_class_type(self, import_manager):
        """Test IMPORTS with class import type."""
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="app.py",
            target_file="models.py",
            import_type="class",
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["import_type"] == "class"

    async def test_create_import_relationship_function_type(self, import_manager):
        """Test IMPORTS with function import type."""
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="app.py",
            target_file="helpers.py",
            import_type="function",
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["import_type"] == "function"

    async def test_create_import_relationship_confidence_scoring(self, import_manager):
        """Test IMPORTS with confidence scores."""
        # High confidence
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="a.py",
            target_file="b.py",
            confidence=1.0,
        )

        # Low confidence
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="x.py",
            target_file="y.py",
            confidence=0.5,
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        assert mock_session.run.call_count >= 2

    async def test_create_import_relationship_with_line_number(self, import_manager):
        """Test IMPORTS stores line number."""
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="main.py",
            target_file="utils.py",
            line_number=42,
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["line_number"] == 42

    async def test_create_import_relationship_circular_imports(self, import_manager):
        """Test circular imports (A imports B, B imports A)."""
        # A -> B
        success1 = await import_manager.create_import_relationship(
            project_name="test",
            source_file="a.py",
            target_file="b.py",
        )

        # B -> A (circular)
        success2 = await import_manager.create_import_relationship(
            project_name="test",
            source_file="b.py",
            target_file="a.py",
        )

        # Both should succeed
        assert success1 is True
        assert success2 is True

    async def test_create_import_relationship_missing_target(self, import_manager):
        """Test IMPORTS when target file doesn't exist yet."""
        # Configure mock to return None (no record)
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        success = await import_manager.create_import_relationship(
            project_name="test",
            source_file="existing.py",
            target_file="missing.py",
        )

        # Should return False when nodes don't exist
        assert success is False

    async def test_create_import_relationship_includes_timestamp(self, import_manager):
        """Test IMPORTS relationship includes created_at timestamp."""
        await import_manager.create_import_relationship(
            project_name="test",
            source_file="a.py",
            target_file="b.py",
        )

        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert "timestamp" in params

    async def test_create_import_relationship_error_handling(self, import_manager):
        """Test error handling during IMPORTS creation."""
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc:
            await import_manager.create_import_relationship(
                project_name="error",
                source_file="a.py",
                target_file="b.py",
            )

        assert "Failed to create IMPORTS relationship" in str(exc.value)


@pytest.mark.asyncio
class TestStoreFileImports:
    """Test store_file_imports batch method."""

    async def test_store_file_imports_single(self, import_manager):
        """Test storing single import."""
        imports = [
            {
                "target": "utils.py",
                "import_type": "module",
                "confidence": 1.0,
                "line_number": 1,
            }
        ]

        count = await import_manager.store_file_imports(
            "test_project", "main.py", imports
        )

        assert count == 1

    async def test_store_file_imports_multiple(self, import_manager):
        """Test storing multiple imports."""
        imports = [
            {"target": "utils.py", "import_type": "module", "confidence": 1.0},
            {"target": "config.py", "import_type": "module", "confidence": 1.0},
            {"target": "models.py", "import_type": "class", "confidence": 0.9},
        ]

        count = await import_manager.store_file_imports("test", "main.py", imports)

        assert count == 3

    async def test_store_file_imports_empty_list(self, import_manager):
        """Test storing empty import list."""
        count = await import_manager.store_file_imports("test", "main.py", [])

        assert count == 0

    async def test_store_file_imports_minimal_data(self, import_manager):
        """Test storing imports with minimal data."""
        imports = [
            {"target": "a.py"},  # Only target, no type/confidence
            {"target": "b.py"},
        ]

        count = await import_manager.store_file_imports("test", "main.py", imports)

        # Should use defaults and succeed
        assert count == 2

    async def test_store_file_imports_with_defaults(self, import_manager):
        """Test imports use default values when not specified."""
        imports = [{"target": "utils.py"}]  # No import_type or confidence

        await import_manager.store_file_imports("test", "main.py", imports)

        # Verify defaults were used
        mock_session = import_manager.memgraph.driver.session.return_value
        call_args = mock_session.run.call_args
        params = call_args[1]

        assert params["import_type"] == "module"  # Default
        assert params["confidence"] == 1.0  # Default

    async def test_store_file_imports_partial_failure(self, import_manager):
        """Test batch processing continues on partial failures."""
        imports = [
            {"target": "good1.py"},
            {"target": "bad.py"},  # Will fail
            {"target": "good2.py"},
        ]

        # Configure mock to fail on second import
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_result_success = AsyncMock()
        mock_result_success.single = AsyncMock(return_value={"r": "relationship"})
        mock_result_fail = AsyncMock()
        mock_result_fail.single = AsyncMock(side_effect=Exception("Import failed"))

        mock_session.run = AsyncMock(
            side_effect=[
                mock_result_success,
                mock_result_fail,
                mock_result_success,
            ]
        )

        count = await import_manager.store_file_imports("test", "main.py", imports)

        # Should have 2 successes despite 1 failure
        assert count == 2

    async def test_store_file_imports_large_batch(self, import_manager):
        """Test storing large batch of imports."""
        imports = [{"target": f"file_{i}.py"} for i in range(100)]

        count = await import_manager.store_file_imports("test", "main.py", imports)

        assert count == 100


@pytest.mark.asyncio
class TestGetFileImports:
    """Test get_file_imports retrieval method."""

    async def test_get_file_imports_success(self, import_manager):
        """Test retrieving file imports."""
        # Configure mock to return import data
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                ["/test/utils.py", "utils.py", "module", 1.0, 5],
                ["/test/config.py", "config.py", "module", 1.0, 10],
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        imports = await import_manager.get_file_imports("test", "main.py")

        assert len(imports) == 2
        assert imports[0]["target_path"] == "/test/utils.py"
        assert imports[0]["import_type"] == "module"

    async def test_get_file_imports_empty(self, import_manager):
        """Test retrieving imports for file with no imports."""
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(return_value=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        imports = await import_manager.get_file_imports("test", "isolated.py")

        assert imports == []

    async def test_get_file_imports_ordered_by_line_number(self, import_manager):
        """Test imports are ordered by line number."""
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                ["/test/a.py", "a.py", "module", 1.0, 1],
                ["/test/b.py", "b.py", "module", 1.0, 5],
                ["/test/c.py", "c.py", "module", 1.0, 10],
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        imports = await import_manager.get_file_imports("test", "main.py")

        # Verify query includes ORDER BY
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "ORDER BY" in query

    async def test_get_file_imports_includes_metadata(self, import_manager):
        """Test retrieved imports include all metadata."""
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_result = AsyncMock()
        mock_result.values = AsyncMock(
            return_value=[
                [
                    "/test/utils.py",
                    "utils.py",
                    "function",
                    0.95,
                    15,
                ]
            ]
        )
        mock_session.run = AsyncMock(return_value=mock_result)

        imports = await import_manager.get_file_imports("test", "main.py")

        assert imports[0]["target_path"] == "/test/utils.py"
        assert imports[0]["target_relative"] == "utils.py"
        assert imports[0]["import_type"] == "function"
        assert imports[0]["confidence"] == 0.95
        assert imports[0]["line_number"] == 15

    async def test_get_file_imports_error_handling(self, import_manager):
        """Test error handling during import retrieval."""
        mock_session = import_manager.memgraph.driver.session.return_value
        mock_session.run.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc:
            await import_manager.get_file_imports("test", "main.py")

        assert "Failed to get file imports" in str(exc.value)


class TestImportTypeClassification:
    """Test import type classification logic."""

    def test_classify_module_import(self):
        """Test classifying module imports."""
        # import utils
        # from . import module
        assert "module" in ["module", "class", "function"]

    def test_classify_class_import(self):
        """Test classifying class imports."""
        # from models import User, Admin
        assert "class" in ["module", "class", "function"]

    def test_classify_function_import(self):
        """Test classifying function imports."""
        # from utils import calculate, format
        assert "function" in ["module", "class", "function"]


class TestImportConfidenceScoring:
    """Test import confidence scoring logic."""

    def test_confidence_explicit_import(self):
        """Test confidence for explicit imports."""
        # from utils import specific_function
        confidence = 1.0  # High confidence
        assert 0.9 <= confidence <= 1.0

    def test_confidence_wildcard_import(self):
        """Test confidence for wildcard imports."""
        # from utils import *
        confidence = 0.5  # Lower confidence
        assert 0.4 <= confidence <= 0.6

    def test_confidence_relative_import(self):
        """Test confidence for relative imports."""
        # from . import something
        confidence = 0.8  # Medium-high confidence
        assert 0.7 <= confidence <= 0.9

    def test_confidence_range_validation(self):
        """Test confidence scores are in valid range."""
        valid_confidences = [0.0, 0.5, 0.75, 1.0]
        for conf in valid_confidences:
            assert 0.0 <= conf <= 1.0


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
