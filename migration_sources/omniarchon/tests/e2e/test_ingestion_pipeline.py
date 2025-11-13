"""
End-to-End Tests for Ingestion Pipeline with Tree Building

Tests the complete ingestion workflow from file discovery through
tree building and orphan prevention.

Validates:
- Full workflow: discovery → indexing → tree building
- Real repository ingestion
- Tree structure completeness
- Zero orphans after complete pipeline
- Performance characteristics

Coverage Target: 90%+
Created: 2025-11-10
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List

import pytest

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SERVICES_DIR = PROJECT_ROOT / "services" / "intelligence" / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SERVICES_DIR))

from src.constants import MemgraphLabels
from storage.memgraph_adapter import MemgraphKnowledgeAdapter

from scripts.bulk_ingest_repository import BulkIngestApp


@pytest.fixture(scope="module")
def memgraph_uri():
    """Get Memgraph URI from environment."""
    return os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")


@pytest.fixture(scope="module")
async def memgraph_adapter(memgraph_uri):
    """Create Memgraph adapter for E2E tests."""
    adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri, username=None, password=None)
    await adapter.initialize()
    yield adapter
    await adapter.close()


@pytest.fixture
async def e2e_project_cleanup(memgraph_adapter):
    """Clean up E2E test project data."""
    project_name = "test_e2e_pipeline"

    async def cleanup():
        """Remove all nodes and relationships for test project."""
        query = """
        MATCH (n)
        WHERE n.project_name = $project_name
           OR (n:PROJECT AND n.project_name = $project_name)
        DETACH DELETE n
        """
        async with memgraph_adapter.driver.session() as session:
            await session.run(query, project_name=project_name)

    await cleanup()
    yield project_name
    await cleanup()


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
class TestFullIngestionPipeline:
    """Test complete ingestion pipeline end-to-end."""

    async def test_simple_project_ingestion_complete(
        self, tmp_path, memgraph_adapter, e2e_project_cleanup
    ):
        """Test complete ingestion of a simple project."""
        project_name = e2e_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create realistic project structure
        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")
        (src_dir / "main.py").write_text(
            "def main():\n    print('Hello, world!')\n\nif __name__ == '__main__':\n    main()"
        )
        (src_dir / "utils.py").write_text("def helper():\n    return 42")

        tests_dir = project_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")
        (tests_dir / "test_main.py").write_text("def test_main():\n    assert True")

        (project_path / "README.md").write_text("# Test Project")
        (project_path / "setup.py").write_text(
            "from setuptools import setup\nsetup(name='test')"
        )

        # Build tree manually (since we're testing tree building, not Kafka)
        from services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [
            str(src_dir / "__init__.py"),
            str(src_dir / "main.py"),
            str(src_dir / "utils.py"),
            str(tests_dir / "__init__.py"),
            str(tests_dir / "test_main.py"),
            str(project_path / "README.md"),
            str(project_path / "setup.py"),
        ]

        stats = await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Verify statistics
        assert stats["projects"] == 1
        assert stats["directories"] == 2  # src/, tests/
        assert stats["files"] == 7
        assert stats["relationships"] > 0

        # Verify no orphans
        orphan_query = f"""
        MATCH (f{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
          AND NOT ((:PROJECT|DIRECTORY)-[:CONTAINS]->(f))
        RETURN count(f) as orphan_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_query, project_name=project_name)
            record = await result.single()
            orphan_count = record["orphan_count"]

        assert orphan_count == 0, f"Found {orphan_count} orphaned FILE nodes"

        # Verify tree navigability
        tree_query = """
        MATCH (p:PROJECT {project_name: $project_name})-[:CONTAINS*]->(node)
        RETURN count(node) as reachable_nodes
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(tree_query, project_name=project_name)
            record = await result.single()
            reachable_count = record["reachable_nodes"]

        # Should reach all 2 directories + 7 files = 9 nodes
        assert (
            reachable_count == 9
        ), f"Only {reachable_count} nodes reachable from PROJECT"

    async def test_complex_nested_project_ingestion(
        self, tmp_path, memgraph_adapter, e2e_project_cleanup
    ):
        """Test complete ingestion of a complex nested project."""
        project_name = e2e_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create complex nested structure
        api_routes = project_path / "src" / "api" / "v1" / "routes"
        api_routes.mkdir(parents=True)
        (api_routes / "users.py").write_text("# users route")
        (api_routes / "auth.py").write_text("# auth route")

        api_models = project_path / "src" / "api" / "v1" / "models"
        api_models.mkdir(parents=True)
        (api_models / "user.py").write_text("# user model")
        (api_models / "token.py").write_text("# token model")

        services = project_path / "src" / "services"
        services.mkdir(parents=True)
        (services / "auth_service.py").write_text("# auth service")
        (services / "user_service.py").write_text("# user service")

        utils = project_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "validators.py").write_text("# validators")
        (utils / "helpers.py").write_text("# helpers")

        # Build tree
        from services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [
            str(api_routes / "users.py"),
            str(api_routes / "auth.py"),
            str(api_models / "user.py"),
            str(api_models / "token.py"),
            str(services / "auth_service.py"),
            str(services / "user_service.py"),
            str(utils / "validators.py"),
            str(utils / "helpers.py"),
        ]

        stats = await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Verify no orphans in complex structure
        orphan_query = f"""
        MATCH (f{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
          AND NOT ((:PROJECT|DIRECTORY)-[:CONTAINS]->(f))
        RETURN f.path as orphan_path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_query, project_name=project_name)
            orphans = await result.data()

        assert len(orphans) == 0, f"Found {len(orphans)} orphaned files: {orphans}"

        # Verify all directories are connected
        disconnected_dirs_query = """
        MATCH (d:DIRECTORY)
        WHERE d.project_name = $project_name
          AND NOT ((:PROJECT|DIRECTORY)-[:CONTAINS]->(d))
        RETURN d.path as disconnected_path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(
                disconnected_dirs_query, project_name=project_name
            )
            disconnected = await result.data()

        assert (
            len(disconnected) == 0
        ), f"Found {len(disconnected)} disconnected directories"

    async def test_empty_directories_excluded(
        self, tmp_path, memgraph_adapter, e2e_project_cleanup
    ):
        """Test that empty directories are not indexed."""
        project_name = e2e_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create directory with file
        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        # Create empty directory (should not be indexed)
        empty_dir = project_path / "empty"
        empty_dir.mkdir()

        # Build tree
        from services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [str(src_dir / "main.py")]  # Only src/ has files

        stats = await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Verify only src/ directory was indexed
        assert stats["directories"] == 1

        # Verify empty/ directory is not in graph
        empty_dir_query = """
        MATCH (d:DIRECTORY)
        WHERE d.project_name = $project_name
          AND d.path CONTAINS 'empty'
        RETURN count(d) as empty_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(empty_dir_query, project_name=project_name)
            record = await result.single()
            empty_count = record["empty_count"]

        assert empty_count == 0, "Empty directory should not be indexed"

    async def test_idempotent_ingestion(
        self, tmp_path, memgraph_adapter, e2e_project_cleanup
    ):
        """Test that running ingestion twice doesn't create duplicates."""
        project_name = e2e_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        from services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [str(src_dir / "main.py")]

        # Run indexing twice
        stats1 = await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        stats2 = await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Stats should be the same
        assert stats1["projects"] == stats2["projects"]
        assert stats1["directories"] == stats2["directories"]

        # Verify no duplicate nodes
        duplicate_query = """
        MATCH (n)
        WHERE n.project_name = $project_name
        WITH n.entity_id as entity_id, count(*) as count
        WHERE count > 1
        RETURN entity_id, count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(duplicate_query, project_name=project_name)
            duplicates = await result.data()

        assert len(duplicates) == 0, f"Found duplicate nodes: {duplicates}"


@pytest.mark.asyncio
@pytest.mark.e2e
class TestTreeRebuildingOnExistingData:
    """Test tree rebuilding on projects with existing FILE nodes."""

    async def test_rebuild_tree_for_existing_files(
        self, tmp_path, memgraph_adapter, e2e_project_cleanup
    ):
        """Test rebuilding tree for files that already exist in Memgraph."""
        project_name = e2e_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        # Step 1: Create FILE nodes without tree structure (simulate legacy data)
        file_entity_id = f"file:{project_name}:src/main.py"

        create_file_query = f"""
        CREATE (f{MemgraphLabels.FILE} {{
            entity_id: $entity_id,
            path: $path,
            project_name: $project_name
        }})
        """

        async with memgraph_adapter.driver.session() as session:
            await session.run(
                create_file_query,
                entity_id=file_entity_id,
                path=str(src_dir / "main.py"),
                project_name=project_name,
            )

        # Verify file exists but is orphaned
        orphan_check_query = f"""
        MATCH (f{MemgraphLabels.FILE} {{entity_id: $entity_id}})
        OPTIONAL MATCH contains_path = ()-[:CONTAINS]->(f)
        WITH f, contains_path
        WHERE contains_path IS NULL
        RETURN count(f) as orphan_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_check_query, entity_id=file_entity_id)
            record = await result.single()
            orphan_count_before = record["orphan_count"]

        assert orphan_count_before == 1, "File should be orphaned before tree building"

        # Step 2: Build tree structure
        from services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        file_paths = [str(src_dir / "main.py")]
        file_entity_mapping = {str(src_dir / "main.py"): file_entity_id}

        await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
            file_entity_mapping=file_entity_mapping,
        )

        # Step 3: Verify file is no longer orphaned
        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_check_query, entity_id=file_entity_id)
            record = await result.single()
            orphan_count_after = record["orphan_count"]

        assert (
            orphan_count_after == 0
        ), "File should not be orphaned after tree building"


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceCharacteristics:
    """Test performance characteristics of tree building."""

    async def test_large_project_performance(
        self, tmp_path, memgraph_adapter, e2e_project_cleanup
    ):
        """Test tree building performance with large project (100+ files)."""
        import time

        project_name = e2e_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create 100 files across 10 directories
        file_paths = []
        for i in range(10):
            dir_path = project_path / f"module_{i}"
            dir_path.mkdir()
            for j in range(10):
                file_path = dir_path / f"file_{j}.py"
                file_path.write_text(f"# File {i}-{j}")
                file_paths.append(str(file_path))

        # Build tree and measure time
        from services.directory_indexer import DirectoryIndexer

        indexer = DirectoryIndexer(memgraph_adapter)

        start_time = time.perf_counter()

        stats = await indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Verify completion
        assert stats["files"] == 100
        assert stats["directories"] == 10

        # Performance target: < 5 seconds for 100 files
        assert (
            duration_ms < 5000
        ), f"Tree building took {duration_ms:.0f}ms (target: <5000ms)"

        # Verify no orphans
        orphan_query = f"""
        MATCH (f{MemgraphLabels.FILE})
        WHERE f.project_name = $project_name
          AND NOT ((:PROJECT|DIRECTORY)-[:CONTAINS]->(f))
        RETURN count(f) as orphan_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_query, project_name=project_name)
            record = await result.single()
            orphan_count = record["orphan_count"]

        assert (
            orphan_count == 0
        ), f"Found {orphan_count} orphaned files in large project"


if __name__ == "__main__":
    import subprocess

    try:
        result = subprocess.run(
            ["pytest", __file__, "-v", "--tb=short", "-x", "-m", "e2e"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
