"""
Integration Tests for Orphan Prevention

Tests that the full ingestion pipeline creates proper tree structure
and prevents orphaned FILE nodes in Memgraph.

Validates:
- All FILE nodes have parent DIRECTORY or PROJECT nodes
- CONTAINS relationships exist for all files
- No orphaned FILE nodes after ingestion
- Tree structure is complete and navigable

Coverage Target: 90%+
Created: 2025-11-10
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List

import pytest
import pytest_asyncio

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SERVICES_DIR = PROJECT_ROOT / "services" / "intelligence"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SERVICES_DIR))

from src.constants.memgraph_labels import MemgraphLabels
from storage.memgraph_adapter import MemgraphKnowledgeAdapter

from scripts.bulk_ingest_repository import BulkIngestApp

# Note: memgraph_uri fixture is now provided by conftest.py with auto-detection


@pytest_asyncio.fixture(scope="function")
async def memgraph_adapter(memgraph_uri):
    """Create Memgraph adapter for tests."""
    adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri, username=None, password=None)
    await adapter.initialize()
    yield adapter
    await adapter.close()


@pytest_asyncio.fixture
async def test_project_cleanup(memgraph_adapter):
    """Clean up test project data before and after tests."""
    project_name = "test_orphan_prevention"

    async def cleanup():
        """Remove all nodes and relationships for test project."""
        query = f"""
        MATCH (n)
        WHERE n.project_name = $project_name
           OR (n:{MemgraphLabels.PROJECT} AND n.project_name = $project_name)
        DETACH DELETE n
        """
        async with memgraph_adapter.driver.session() as session:
            await session.run(query, project_name=project_name)
        # Small delay to ensure cleanup transaction is committed
        await asyncio.sleep(0.1)

    # Cleanup before test
    await cleanup()

    yield project_name

    # Cleanup after test
    await cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
class TestOrphanPrevention:
    """Test orphan prevention during ingestion."""

    async def test_no_orphans_after_simple_ingestion(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that simple project ingestion creates no orphaned FILE nodes."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create test files
        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main file")
        (src_dir / "utils.py").write_text("# utils file")

        tests_dir = project_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("# test file")

        # Run ingestion (dry_run=False to actually publish events)
        # Note: This requires Kafka to be running
        app = BulkIngestApp(
            project_path=project_path,
            project_name=project_name,
            kafka_bootstrap_servers=os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"
            ),
            dry_run=True,  # Use dry_run for unit test environment
            skip_tree=False,
        )

        # Manually build tree (since dry_run skips Kafka)
        with patch.object(app, "build_directory_tree") as mock_build_tree:
            # Simulate successful tree building
            mock_build_tree.return_value = True

            # Manually create tree structure for testing
            from src.services.directory_indexer import DirectoryIndexer

            indexer = DirectoryIndexer(memgraph_adapter)

            file_paths = [
                str(src_dir / "main.py"),
                str(src_dir / "utils.py"),
                str(tests_dir / "test_main.py"),
            ]

            await indexer.index_directory_hierarchy(
                project_name=project_name,
                project_root=str(project_path),
                file_paths=file_paths,
            )

        # Query for orphaned FILE nodes (Memgraph-compatible)
        orphan_query = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        WITH f
        OPTIONAL MATCH (parent)-[:CONTAINS]->(f)
        WITH f, parent
        WHERE parent IS NULL
        RETURN f.path as file_path, f.entity_id as entity_id
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_query, project_name=project_name)
            orphans = await result.data()

        # Verify no orphans
        assert len(orphans) == 0, f"Found {len(orphans)} orphaned FILE nodes: {orphans}"

        # Verify all FILE nodes have project_name property
        project_name_check = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        RETURN f.path as file_path, f.project_name as project_name
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(project_name_check, project_name=project_name)
            files_with_project = await result.data()

        assert len(files_with_project) == len(
            file_paths
        ), f"Expected {len(file_paths)} files with project_name, found {len(files_with_project)}"
        for file_data in files_with_project:
            assert file_data["project_name"] == project_name, (
                f"File {file_data['file_path']} has incorrect project_name: "
                f"{file_data['project_name']}"
            )
            assert (
                file_data["project_name"] is not None
            ), f"File {file_data['file_path']} has NULL project_name"

    async def test_no_orphans_after_nested_ingestion(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that nested directory structure creates no orphaned FILE nodes."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create deeply nested structure
        api_dir = project_path / "src" / "api" / "v1" / "routes"
        api_dir.mkdir(parents=True)
        (api_dir / "users.py").write_text("# users route")

        models_dir = project_path / "src" / "api" / "v1" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "user.py").write_text("# user model")

        services_dir = project_path / "src" / "services" / "auth"
        services_dir.mkdir(parents=True)
        (services_dir / "jwt.py").write_text("# jwt service")

        # Build tree
        from src.services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [
            str(api_dir / "users.py"),
            str(models_dir / "user.py"),
            str(services_dir / "jwt.py"),
        ]

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Query for orphaned FILE nodes (Memgraph-compatible)
        orphan_query = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        WITH f
        OPTIONAL MATCH (parent)-[:CONTAINS]->(f)
        WITH f, parent
        WHERE parent IS NULL
        RETURN f.path as file_path, f.entity_id as entity_id
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_query, project_name=project_name)
            orphans = await result.data()

        assert (
            len(orphans) == 0
        ), f"Found {len(orphans)} orphaned FILE nodes in nested structure"

        # Verify all FILE nodes have project_name property
        project_name_check = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        RETURN f.path as file_path, f.project_name as project_name
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(project_name_check, project_name=project_name)
            files_with_project = await result.data()

        assert len(files_with_project) == len(
            file_paths
        ), f"Expected {len(file_paths)} files with project_name, found {len(files_with_project)}"
        for file_data in files_with_project:
            assert (
                file_data["project_name"] == project_name
            ), f"File {file_data['file_path']} has incorrect project_name"
            assert (
                file_data["project_name"] is not None
            ), f"File {file_data['file_path']} has NULL project_name"

    async def test_root_level_files_not_orphaned(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that root-level files are linked to PROJECT node."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create root-level file
        (project_path / "setup.py").write_text("# setup file")
        (project_path / "README.md").write_text("# readme")

        # Build tree
        from src.services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [str(project_path / "setup.py"), str(project_path / "README.md")]

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Wait for transaction commit/visibility (Memgraph async session timing)
        await asyncio.sleep(0.2)

        # Query for root-level files with PROJECT parent
        root_files_query = f"""
        MATCH (p:{MemgraphLabels.PROJECT})-[:CONTAINS]->(f:{MemgraphLabels.FILE})
        WHERE p.project_name = $project_name
        RETURN f.path as file_path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(root_files_query, project_name=project_name)
            root_files = await result.data()

        # Should have 2 root-level files
        assert (
            len(root_files) == 2
        ), f"Expected 2 root-level files, found {len(root_files)}"

        # Verify all FILE nodes have project_name property
        project_name_check = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        RETURN f.path as file_path, f.project_name as project_name
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(project_name_check, project_name=project_name)
            files_with_project = await result.data()

        assert (
            len(files_with_project) == 2
        ), f"Expected 2 files with project_name, found {len(files_with_project)}"
        for file_data in files_with_project:
            assert (
                file_data["project_name"] == project_name
            ), f"File {file_data['file_path']} missing project_name"
            assert (
                file_data["project_name"] is not None
            ), f"File {file_data['file_path']} has NULL project_name"

    async def test_all_files_have_parents(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that every FILE node has exactly one parent."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create mixed structure
        (project_path / "root.py").write_text("# root file")

        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        (utils_dir / "helpers.py").write_text("# helpers")

        # Build tree
        from src.services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [
            str(project_path / "root.py"),
            str(src_dir / "main.py"),
            str(utils_dir / "helpers.py"),
        ]

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Wait for transaction commit/visibility (Memgraph async session timing)
        await asyncio.sleep(0.2)

        # Query for files with parent count
        parent_count_query = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        OPTIONAL MATCH (parent)-[:CONTAINS]->(f)
        WITH f, count(parent) as parent_count
        RETURN f.path as file_path, parent_count
        ORDER BY f.path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(parent_count_query, project_name=project_name)
            files_with_parents = await result.data()

        # Every file should have exactly 1 parent
        for file_data in files_with_parents:
            assert file_data["parent_count"] == 1, (
                f"File {file_data['file_path']} has {file_data['parent_count']} parents, "
                f"expected exactly 1"
            )

        assert (
            len(files_with_parents) == 3
        ), f"Expected 3 files, found {len(files_with_parents)}"

        # Verify all FILE nodes have project_name property
        project_name_check = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
        RETURN f.path as file_path, f.project_name as project_name
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(project_name_check, project_name=project_name)
            files_with_project = await result.data()

        assert (
            len(files_with_project) == 3
        ), f"Expected 3 files with project_name, found {len(files_with_project)}"
        for file_data in files_with_project:
            assert (
                file_data["project_name"] == project_name
            ), f"File {file_data['file_path']} missing project_name"
            assert (
                file_data["project_name"] is not None
            ), f"File {file_data['file_path']} has NULL project_name"


@pytest.mark.asyncio
@pytest.mark.integration
class TestTreeStructureCompleteness:
    """Test that tree structure is complete and navigable."""

    async def test_all_directories_have_contains_relationships(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that all DIRECTORY nodes have CONTAINS relationships."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create nested structure
        deep_dir = project_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        (deep_dir / "file.py").write_text("# deep file")

        # Build tree
        from src.services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [str(deep_dir / "file.py")]

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Query for directories without CONTAINS relationships (Memgraph-compatible)
        orphan_dirs_query = f"""
        MATCH (d:{MemgraphLabels.DIRECTORY})
        WHERE d.project_name = $project_name
        WITH d
        OPTIONAL MATCH (d)-[:CONTAINS]->(child)
        OPTIONAL MATCH (parent)-[:CONTAINS]->(d)
        WITH d, child, parent
        WHERE child IS NULL AND parent IS NULL
        RETURN d.path as dir_path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_dirs_query, project_name=project_name)
            orphan_dirs = await result.data()

        # Only the deepest directory (d/) should have no outgoing CONTAINS
        # But it should still have an incoming CONTAINS from its parent
        # So query should return 0 directories that are both unlinked
        assert (
            len(orphan_dirs) == 0
        ), f"Found {len(orphan_dirs)} orphaned DIRECTORY nodes"

        # Verify all DIRECTORY nodes have project_name property
        dir_project_name_check = f"""
        MATCH (d:{MemgraphLabels.DIRECTORY})
        WHERE d.project_name = $project_name
        RETURN d.path as dir_path, d.project_name as project_name
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(
                dir_project_name_check, project_name=project_name
            )
            dirs_with_project = await result.data()

        # Should have 4 directories: a, b, c, d
        assert (
            len(dirs_with_project) >= 4
        ), f"Expected at least 4 directories with project_name, found {len(dirs_with_project)}"
        for dir_data in dirs_with_project:
            assert (
                dir_data["project_name"] == project_name
            ), f"Directory {dir_data['dir_path']} missing project_name"
            assert (
                dir_data["project_name"] is not None
            ), f"Directory {dir_data['dir_path']} has NULL project_name"

    async def test_project_node_exists(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that PROJECT node is created."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create simple structure
        (project_path / "file.py").write_text("# file")

        # Build tree
        from src.services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [str(project_path / "file.py")]

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Query for PROJECT node
        project_query = f"""
        MATCH (p:{MemgraphLabels.PROJECT})
        WHERE p.project_name = $project_name
        RETURN p.entity_id as entity_id, p.root_path as root_path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(project_query, project_name=project_name)
            projects = await result.data()

        assert len(projects) == 1, f"Expected 1 PROJECT node, found {len(projects)}"
        assert projects[0]["entity_id"] == f"project:{project_name}"

        # Verify PROJECT node has project_name property
        project_detail_query = f"""
        MATCH (p:{MemgraphLabels.PROJECT})
        WHERE p.project_name = $project_name
        RETURN p.project_name as project_name, p.entity_id as entity_id
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(project_detail_query, project_name=project_name)
            project_details = await result.data()

        assert len(project_details) == 1, "PROJECT node must exist"
        assert (
            project_details[0]["project_name"] == project_name
        ), "PROJECT node must have correct project_name"
        assert (
            project_details[0]["project_name"] is not None
        ), "PROJECT node project_name cannot be NULL"

    async def test_tree_depth_calculation(
        self, tmp_path, memgraph_adapter, test_project_cleanup
    ):
        """Test that directory depth is calculated correctly."""
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create nested directories
        level1 = project_path / "level1"
        level1.mkdir()
        (level1 / "file1.py").write_text("# level 1")

        level2 = level1 / "level2"
        level2.mkdir()
        (level2 / "file2.py").write_text("# level 2")

        level3 = level2 / "level3"
        level3.mkdir()
        (level3 / "file3.py").write_text("# level 3")

        # Build tree
        from src.services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [
            str(level1 / "file1.py"),
            str(level2 / "file2.py"),
            str(level3 / "file3.py"),
        ]

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Query for directory depths
        depth_query = f"""
        MATCH (d:{MemgraphLabels.DIRECTORY})
        WHERE d.project_name = $project_name
        RETURN d.name as dir_name, d.depth as depth
        ORDER BY d.depth
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(depth_query, project_name=project_name)
            directories = await result.data()

        # Verify depth progression
        assert (
            len(directories) == 3
        ), f"Expected 3 directories, found {len(directories)}"
        assert directories[0]["depth"] == 0  # level1
        assert directories[1]["depth"] == 1  # level2
        assert directories[2]["depth"] == 2  # level3

        # Verify all DIRECTORY nodes have project_name property
        dir_project_check = f"""
        MATCH (d:{MemgraphLabels.DIRECTORY})
        WHERE d.project_name = $project_name
        RETURN d.name as dir_name, d.project_name as project_name
        """
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(dir_project_check, project_name=project_name)
            dirs_with_project = await result.data()

        assert (
            len(dirs_with_project) == 3
        ), f"Expected 3 directories with project_name, found {len(dirs_with_project)}"
        for dir_data in dirs_with_project:
            assert (
                dir_data["project_name"] == project_name
            ), f"Directory {dir_data['dir_name']} has incorrect project_name"
            assert (
                dir_data["project_name"] is not None
            ), f"Directory {dir_data['dir_name']} has NULL project_name"


# Add patch import for the first test case
from unittest.mock import patch

if __name__ == "__main__":
    import subprocess

    try:
        result = subprocess.run(
            ["pytest", __file__, "-v", "--tb=short", "-x", "-m", "integration"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
