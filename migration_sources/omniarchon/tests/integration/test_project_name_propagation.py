"""
Integration Tests for project_name Propagation in File Tree Graph

Tests that project_name property is correctly set and propagated across all
nodes (PROJECT, DIRECTORY, FILE) in the Memgraph tree structure.

Critical Bug Being Tested:
- DirectoryIndexer creates stub nodes without project_name during MERGE operations
- Causes 1,292+ orphaned file nodes due to missing project_name property
- Files cannot be linked to PROJECT root without this property

Validates:
- PROJECT nodes have project_name property set correctly
- DIRECTORY nodes (including stubs) have project_name property
- FILE nodes have project_name property matching their PROJECT parent
- MERGE operations update project_name on existing nodes
- No orphaned FILE nodes due to missing project_name
- All nodes are reachable from PROJECT root via project_name filtering

Test-Driven Development Approach:
- Tests are expected to FAIL initially (bug not fixed yet)
- Tests will PASS after DirectoryIndexer fixes are applied
- Clear assertion messages to guide debugging

Coverage Target: 95%+
Created: 2025-11-11
"""

import asyncio
import os
import sys
import uuid
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

from src.services.directory_indexer import DirectoryIndexer
from storage.memgraph_adapter import MemgraphKnowledgeAdapter


@pytest.fixture(scope="module")
def memgraph_uri():
    """Get Memgraph URI from environment."""
    # Use localhost for tests running outside Docker
    # Inside Docker, use memgraph:7687 (set via MEMGRAPH_URI env var)
    return os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")


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
    project_name = "test_project_name_propagation"

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
        # Small delay to ensure cleanup transaction is committed
        await asyncio.sleep(0.1)

    # Cleanup before test
    await cleanup()

    yield project_name

    # Cleanup after test
    await cleanup()


@pytest_asyncio.fixture
async def directory_indexer(memgraph_adapter):
    """Create DirectoryIndexer instance for tests."""
    return DirectoryIndexer(memgraph_adapter)


@pytest.fixture
def unique_test_id():
    """Generate unique ID for test data isolation."""
    return str(uuid.uuid4())[:8]


@pytest_asyncio.fixture(autouse=True)
async def cleanup_all_test_data(memgraph_adapter):
    """Clean up all test data before and after each test."""

    async def cleanup():
        """Remove all nodes with test project names."""
        query = """
        MATCH (n)
        WHERE n.project_name STARTS WITH 'test_'
        DETACH DELETE n
        """
        async with memgraph_adapter.driver.session() as session:
            await session.run(query)
        # Small delay to ensure cleanup transaction is committed
        await asyncio.sleep(0.1)

    # Cleanup before test
    await cleanup()

    yield

    # Cleanup after test
    await cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
class TestProjectNamePropagation:
    """Test project_name property propagation across all node types."""

    async def test_project_node_has_project_name(
        self, tmp_path, directory_indexer, memgraph_adapter, test_project_cleanup
    ):
        """
        Test that PROJECT node is created with project_name property.

        This is the base case - PROJECT nodes should always have project_name.
        """
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create simple file
        (project_path / "file.py").write_text("# test file")

        file_paths = [str(project_path / "file.py")]

        # Index directory hierarchy
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Wait for transaction commit
        await asyncio.sleep(0.2)

        # Query for PROJECT node with project_name
        query = """
        MATCH (p:PROJECT)
        WHERE p.project_name = $project_name
        RETURN p.entity_id as entity_id,
               p.project_name as project_name,
               p.root_path as root_path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            projects = await result.data()

        assert len(projects) == 1, (
            f"Expected 1 PROJECT node with project_name={project_name}, "
            f"found {len(projects)}"
        )

        project = projects[0]
        assert project["project_name"] == project_name, (
            f"PROJECT node project_name mismatch: "
            f"expected '{project_name}', got '{project['project_name']}'"
        )
        assert (
            project["entity_id"] == f"project:{project_name}"
        ), f"PROJECT node entity_id incorrect: {project['entity_id']}"

    async def test_directory_nodes_have_project_name(
        self, tmp_path, directory_indexer, memgraph_adapter, test_project_cleanup
    ):
        """
        Test that DIRECTORY nodes are created with project_name property.

        Critical Test: This validates that directory_indexer._create_directory_node()
        correctly sets project_name on all DIRECTORY nodes.
        """
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create nested directory structure
        src_dir = project_path / "src"
        src_dir.mkdir()
        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        (utils_dir / "helper.py").write_text("# helper")

        file_paths = [str(utils_dir / "helper.py")]

        # Index directory hierarchy
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Wait for transaction commit
        await asyncio.sleep(0.2)

        # Query for all DIRECTORY nodes
        query = """
        MATCH (d:Directory)
        WHERE d.project_name = $project_name
        RETURN d.entity_id as entity_id,
               d.project_name as project_name,
               d.path as path,
               d.name as name
        ORDER BY d.path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            directories = await result.data()

        # Should have 2 directories: src/ and src/utils/
        assert (
            len(directories) == 2
        ), f"Expected 2 DIRECTORY nodes, found {len(directories)}"

        # Verify each directory has project_name
        for directory in directories:
            assert directory["project_name"] == project_name, (
                f"DIRECTORY node '{directory['path']}' missing project_name: "
                f"expected '{project_name}', got '{directory.get('project_name', 'MISSING')}'"
            )

    async def test_stub_nodes_have_project_name(
        self, tmp_path, directory_indexer, memgraph_adapter, test_project_cleanup
    ):
        """
        Test that stub FILE nodes created during MERGE have project_name.

        CRITICAL BUG TEST: This is the root cause of 1,292 orphaned files.

        When DirectoryIndexer creates CONTAINS relationships, it uses MERGE
        which can create stub FILE nodes if they don't exist yet. These stubs
        MUST have project_name set, or they become orphaned.

        Bug Location: directory_indexer.py:316-322 (_create_contains_relationship)

        Current Behavior (BUG):
        - MERGE creates FILE node without project_name
        - Later queries filtering by project_name can't find these nodes
        - Nodes appear orphaned even though they exist

        Expected Behavior (AFTER FIX):
        - MERGE creates FILE node WITH project_name extracted from entity_id
        - All queries filtering by project_name work correctly
        - No orphaned nodes
        """
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create directory
        src_dir = project_path / "src"
        src_dir.mkdir()

        # Index with file that will create stub node
        file_path = str(src_dir / "main.py")
        file_entity_id = f"file:{project_name}:{file_path}"

        # Create tree structure (this will MERGE stub FILE node)
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=[file_path],
            file_entity_mapping={file_path: file_entity_id},
        )

        # Wait for transaction commit
        await asyncio.sleep(0.2)

        # Query for FILE nodes WITHOUT filtering by project_name
        # This finds all FILE nodes regardless of project_name property
        unfiltered_query = """
        MATCH (f:File)
        WHERE f.entity_id = $entity_id
        RETURN f.entity_id as entity_id,
               f.project_name as project_name,
               f.path as path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(unfiltered_query, entity_id=file_entity_id)
            all_files = await result.data()

        assert (
            len(all_files) > 0
        ), "FILE node should exist in database (unfiltered query found nothing)"

        file_node = all_files[0]

        # THE CRITICAL ASSERTION: Does the stub FILE node have project_name?
        assert file_node.get("project_name") is not None, (
            f"BUG DETECTED: Stub FILE node created without project_name property!\n"
            f"entity_id: {file_node['entity_id']}\n"
            f"path: {file_node.get('path', 'MISSING')}\n"
            f"project_name: {file_node.get('project_name', 'MISSING')}\n"
            f"This is the root cause of orphaned files - nodes exist but are unreachable "
            f"via project_name queries."
        )

        assert file_node["project_name"] == project_name, (
            f"FILE node has wrong project_name: "
            f"expected '{project_name}', got '{file_node['project_name']}'"
        )

    async def test_file_nodes_have_project_name(
        self, tmp_path, directory_indexer, memgraph_adapter, test_project_cleanup
    ):
        """
        Test that all FILE nodes have project_name property matching PROJECT parent.

        This ensures files are queryable and reachable via project_name filtering.
        """
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create files at different levels
        (project_path / "root.py").write_text("# root")

        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("# main")

        tests_dir = project_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("# test")

        file_paths = [
            str(project_path / "root.py"),
            str(src_dir / "main.py"),
            str(tests_dir / "test_main.py"),
        ]

        # Index directory hierarchy
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Wait for transaction commit
        await asyncio.sleep(0.2)

        # Query for all FILE nodes filtered by project_name
        query = """
        MATCH (f:File)
        WHERE f.project_name = $project_name
        RETURN f.entity_id as entity_id,
               f.project_name as project_name,
               f.path as path
        ORDER BY f.path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query, project_name=project_name)
            files = await result.data()

        # Should find all 3 files via project_name filtering
        assert len(files) == 3, (
            f"Expected 3 FILE nodes with project_name={project_name}, "
            f"found {len(files)}. This indicates stub nodes were created without project_name."
        )

        # Verify each file has correct project_name
        for file_node in files:
            assert file_node["project_name"] == project_name, (
                f"FILE node '{file_node['path']}' has wrong project_name: "
                f"expected '{project_name}', got '{file_node['project_name']}'"
            )

    async def test_merge_updates_project_name(
        self,
        tmp_path,
        directory_indexer,
        memgraph_adapter,
        test_project_cleanup,
        unique_test_id,
    ):
        """
        Test that MERGE operations update project_name on existing nodes.

        When a FILE node already exists (from previous ingestion), MERGE should
        ensure project_name is set correctly. This prevents nodes from becoming
        orphaned after re-ingestion.
        """
        # Use unique project name for isolation
        project_name = f"test_merge_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        src_dir = project_path / "src"
        src_dir.mkdir()
        file_path = str(src_dir / "main.py")

        # Create specific entity_id for this test
        file_entity_id = f"file:{project_name}:{file_path}"

        # First ingestion - creates nodes
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=[file_path],
            file_entity_mapping={file_path: file_entity_id},
        )

        await asyncio.sleep(0.2)

        # Second ingestion - should update existing nodes via MERGE
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=[file_path],
            file_entity_mapping={file_path: file_entity_id},
        )

        await asyncio.sleep(0.2)

        # Query by specific entity_id instead of path fragment
        query = """
        MATCH (f:File)
        WHERE f.entity_id = $entity_id
        RETURN f.entity_id as entity_id,
               f.project_name as project_name,
               f.path as path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(query, entity_id=file_entity_id)
            files = await result.data()

        assert len(files) == 1, (
            f"Expected 1 FILE node after re-ingestion, found {len(files)} "
            f"(MERGE may have created duplicates). Entity ID: {file_entity_id}"
        )

        file_node = files[0]
        assert file_node.get("project_name") == project_name, (
            f"FILE node missing project_name after MERGE: "
            f"expected '{project_name}', got '{file_node.get('project_name', 'MISSING')}'"
        )

    async def test_no_orphans_after_ingestion(
        self, tmp_path, directory_indexer, memgraph_adapter, test_project_cleanup
    ):
        """
        Test that 0 FILE nodes are orphaned after complete repository ingestion.

        This is the ultimate validation: after ingestion, ALL files must be
        reachable from the PROJECT root via CONTAINS relationships AND
        project_name filtering.

        Orphan Detection Strategy:
        1. Find all FILE nodes with matching project_name
        2. Check if they have incoming CONTAINS relationship
        3. Check if they're reachable from PROJECT root via path traversal

        A file is orphaned if:
        - It has no incoming CONTAINS relationship, OR
        - It's not reachable from PROJECT root via (p:PROJECT)-[:CONTAINS*]->(f:FILE)
        """
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create realistic project structure
        (project_path / "README.md").write_text("# readme")
        (project_path / "setup.py").write_text("# setup")

        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")
        (src_dir / "main.py").write_text("# main")

        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        (utils_dir / "__init__.py").write_text("")
        (utils_dir / "helpers.py").write_text("# helpers")

        tests_dir = project_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("# test")

        file_paths = [
            str(project_path / "README.md"),
            str(project_path / "setup.py"),
            str(src_dir / "__init__.py"),
            str(src_dir / "main.py"),
            str(utils_dir / "__init__.py"),
            str(utils_dir / "helpers.py"),
            str(tests_dir / "test_main.py"),
        ]

        # Index complete directory hierarchy
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        # Wait for transaction commit
        await asyncio.sleep(0.2)

        # Query 1: Find FILE nodes with no incoming CONTAINS relationship
        orphan_query_no_parent = """
        MATCH (f:File)
        WHERE f.project_name = $project_name
        WITH f
        OPTIONAL MATCH (parent)-[:CONTAINS]->(f)
        WITH f, parent
        WHERE parent IS NULL
        RETURN f.entity_id as entity_id,
               f.path as path,
               f.project_name as project_name
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(
                orphan_query_no_parent, project_name=project_name
            )
            orphans_no_parent = await result.data()

        assert len(orphans_no_parent) == 0, (
            f"Found {len(orphans_no_parent)} orphaned FILE nodes (no parent):\n"
            + "\n".join(
                [
                    f"  - {o['path']} (entity_id: {o['entity_id']})"
                    for o in orphans_no_parent
                ]
            )
            + "\nThese files have no incoming CONTAINS relationship."
        )

        # Query 2: Find FILE nodes not reachable from PROJECT root
        orphan_query_unreachable = """
        MATCH (p:PROJECT {project_name: $project_name})
        MATCH (f:File {project_name: $project_name})
        OPTIONAL MATCH contains_path = (p)-[:CONTAINS*]->(f)
        WITH p, f, contains_path
        WHERE contains_path IS NULL
        RETURN f.entity_id as entity_id,
               f.path as path,
               f.project_name as project_name
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(
                orphan_query_unreachable, project_name=project_name
            )
            orphans_unreachable = await result.data()

        assert len(orphans_unreachable) == 0, (
            f"Found {len(orphans_unreachable)} orphaned FILE nodes "
            f"(unreachable from PROJECT root):\n"
            + "\n".join(
                [
                    f"  - {o['path']} (entity_id: {o['entity_id']})"
                    for o in orphans_unreachable
                ]
            )
            + f"\nThese files exist with project_name={project_name} but are not "
            f"reachable via (PROJECT)-[:CONTAINS*]->(FILE) path."
        )

        # Query 3: Verify total file count matches expected
        count_query = """
        MATCH (p:PROJECT {project_name: $project_name})-[:CONTAINS*]->(f:File)
        RETURN count(f) as file_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(count_query, project_name=project_name)
            count_result = await result.single()
            reachable_files = count_result["file_count"]

        assert reachable_files == len(file_paths), (
            f"File count mismatch: indexed {len(file_paths)} files, "
            f"but only {reachable_files} are reachable from PROJECT root. "
            f"Missing {len(file_paths) - reachable_files} files."
        )

    async def test_all_nodes_reachable_via_project_name_filter(
        self, tmp_path, directory_indexer, memgraph_adapter, test_project_cleanup
    ):
        """
        Test that all nodes (PROJECT, DIRECTORY, FILE) are findable via project_name.

        This validates that project_name filtering works correctly across the
        entire tree structure, ensuring no nodes are "invisible" due to missing
        project_name properties.
        """
        project_name = test_project_cleanup
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create structure
        src_dir = project_path / "src"
        src_dir.mkdir()
        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        (utils_dir / "helper.py").write_text("# helper")

        file_paths = [str(utils_dir / "helper.py")]

        # Index directory hierarchy
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
        )

        await asyncio.sleep(0.2)

        # Count all nodes by type with project_name filter
        count_query = """
        MATCH (p:PROJECT {project_name: $project_name})
        WITH count(p) as project_count
        MATCH (d:Directory {project_name: $project_name})
        WITH project_count, count(d) as directory_count
        MATCH (f:File {project_name: $project_name})
        RETURN project_count,
               directory_count,
               count(f) as file_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(count_query, project_name=project_name)
            counts = await result.single()

        assert (
            counts["project_count"] == 1
        ), f"Expected 1 PROJECT node, found {counts['project_count']}"
        assert (
            counts["directory_count"] == 2
        ), f"Expected 2 DIRECTORY nodes (src, src/utils), found {counts['directory_count']}"
        assert (
            counts["file_count"] == 1
        ), f"Expected 1 FILE node, found {counts['file_count']}"

        # Verify tree connectivity with project_name filter
        connectivity_query = """
        MATCH path = (p:PROJECT {project_name: $project_name})
                      -[:CONTAINS*]->(leaf)
        WHERE (leaf:Directory OR leaf:File)
        RETURN count(path) as path_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(connectivity_query, project_name=project_name)
            connectivity = await result.single()

        # Should have paths to: src, src/utils, helper.py = 3 paths
        expected_paths = 3
        assert connectivity["path_count"] == expected_paths, (
            f"Expected {expected_paths} paths from PROJECT to leaves, "
            f"found {connectivity['path_count']}. "
            f"This indicates broken tree connectivity or missing project_name properties."
        )


@pytest.mark.asyncio
@pytest.mark.integration
class TestProjectNameEdgeCases:
    """Test edge cases and error conditions for project_name propagation."""

    async def test_multiple_projects_isolated(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test that multiple projects with same directory names don't interfere.

        Validates that project_name correctly isolates different projects.
        """
        # Create two separate projects with unique names
        project1_name = f"test_project_1_{unique_test_id}"
        project1_path = tmp_path / project1_name
        project1_path.mkdir()
        src1 = project1_path / "src"
        src1.mkdir()
        (src1 / "main.py").write_text("# project 1")

        project2_name = f"test_project_2_{unique_test_id}"
        project2_path = tmp_path / project2_name
        project2_path.mkdir()
        src2 = project2_path / "src"
        src2.mkdir()
        (src2 / "main.py").write_text("# project 2")

        # Index both projects
        await directory_indexer.index_directory_hierarchy(
            project_name=project1_name,
            project_root=str(project1_path),
            file_paths=[str(src1 / "main.py")],
        )

        await directory_indexer.index_directory_hierarchy(
            project_name=project2_name,
            project_root=str(project2_path),
            file_paths=[str(src2 / "main.py")],
        )

        await asyncio.sleep(0.2)

        # Query files for each project separately with scoped queries
        query = """
        MATCH (f:File)
        WHERE f.project_name = $project_name
        RETURN count(f) as file_count
        """

        async with memgraph_adapter.driver.session() as session:
            result1 = await session.run(query, project_name=project1_name)
            count1 = (await result1.single())["file_count"]

            result2 = await session.run(query, project_name=project2_name)
            count2 = (await result2.single())["file_count"]

        assert (
            count1 == 1
        ), f"Project 1 ({project1_name}) should have 1 file, found {count1}"
        assert (
            count2 == 1
        ), f"Project 2 ({project2_name}) should have 1 file, found {count2}"

        # Note: Cleanup is handled by cleanup_all_test_data fixture

    async def test_empty_project_name_handling(
        self, tmp_path, directory_indexer, memgraph_adapter
    ):
        """
        Test handling of empty or invalid project_name.

        Should raise ValueError with clear error message.
        """
        project_path = tmp_path / "test_empty"
        project_path.mkdir()
        (project_path / "file.py").write_text("# file")

        # Test with empty project_name - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await directory_indexer.index_directory_hierarchy(
                project_name="",  # Empty project name
                project_root=str(project_path),
                file_paths=[str(project_path / "file.py")],
            )

        # Verify error message is clear
        assert "project_name is required" in str(exc_info.value)
        assert "cannot be empty" in str(exc_info.value)

        # Test with None project_name - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await directory_indexer.index_directory_hierarchy(
                project_name=None,  # None project name
                project_root=str(project_path),
                file_paths=[str(project_path / "file.py")],
            )

        assert "project_name is required" in str(exc_info.value)

        # Test with whitespace-only project_name - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await directory_indexer.index_directory_hierarchy(
                project_name="   ",  # Whitespace-only project name
                project_root=str(project_path),
                file_paths=[str(project_path / "file.py")],
            )

        assert "project_name is required" in str(exc_info.value)

        # Cleanup any nodes that might have been created
        cleanup_query = """
        MATCH (n)
        WHERE n.project_name = "" OR n.project_name IS NULL
        DETACH DELETE n
        """
        async with memgraph_adapter.driver.session() as session:
            await session.run(cleanup_query)


if __name__ == "__main__":
    """
    Run these tests with:

    pytest tests/integration/test_project_name_propagation.py -v

    Run specific test:
    pytest tests/integration/test_project_name_propagation.py::TestProjectNamePropagation::test_stub_nodes_have_project_name -v

    Run with detailed output:
    pytest tests/integration/test_project_name_propagation.py -v -s
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                "pytest",
                __file__,
                "-v",
                "--tb=short",
                "-x",  # Stop on first failure
                "-m",
                "integration",
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-asyncio")
