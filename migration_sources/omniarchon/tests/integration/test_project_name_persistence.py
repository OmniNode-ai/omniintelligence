"""
Integration Tests for project_name Persistence Through Tree Building

REGRESSION TEST for Critical Bug: DirectoryIndexer Overwrites project_name

Bug Description:
    In directory_indexer.py:341, the ON MATCH clause of the MERGE operation
    was overwriting correct project_name values with "unknown":

    BUGGY CODE:
        ON MATCH SET child.project_name = $project_name,  # ← OVERWRITES existing value!
                     child.path = $child_path,
                     child.updated_at = $timestamp

    FIXED CODE:
        ON MATCH SET child.updated_at = $timestamp  # ← Only updates timestamp

    The bug occurred because:
    1. File nodes are created FIRST with CORRECT project_name during ingestion
    2. Directory tree building happens SECOND via _create_contains_relationship()
    3. MERGE's ON MATCH clause would OVERWRITE the correct value with "unknown"
    4. This caused ALL files to show project_name="unknown" instead of actual project name

Critical Difference from test_project_name_propagation.py:
    - test_project_name_propagation.py tests if project_name is SET during creation
    - THIS test validates that project_name PERSISTS and is NOT OVERWRITTEN

Test Strategy:
    1. Create FILE nodes with CORRECT project_name (simulating ingestion)
    2. Run tree building (which triggers MERGE with ON MATCH)
    3. Verify project_name is PRESERVED (not overwritten with "unknown")
    4. Verify this works for multiple files, nested directories, edge cases

This test would FAIL with the old buggy code and PASS with the fixed code.

Created: 2025-11-13
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import List, Optional

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
    return os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")


@pytest_asyncio.fixture(scope="function")
async def memgraph_adapter(memgraph_uri):
    """Create Memgraph adapter for tests."""
    adapter = MemgraphKnowledgeAdapter(uri=memgraph_uri, username=None, password=None)
    await adapter.initialize()
    yield adapter
    await adapter.close()


@pytest_asyncio.fixture(scope="function")
async def directory_indexer(memgraph_adapter):
    """Create DirectoryIndexer instance for tests."""
    return DirectoryIndexer(memgraph_adapter)


@pytest.fixture
def unique_test_id():
    """Generate unique ID for test data isolation."""
    return str(uuid.uuid4())[:8]


@pytest_asyncio.fixture(autouse=True)
async def cleanup_test_data(memgraph_adapter):
    """Clean up test data before and after each test."""

    async def cleanup():
        """Remove all nodes with test project names."""
        query = """
        MATCH (n)
        WHERE n.project_name STARTS WITH 'test_persistence_'
        DETACH DELETE n
        """
        async with memgraph_adapter.driver.session() as session:
            await session.run(query)
        await asyncio.sleep(0.1)

    # Cleanup before test
    await cleanup()

    yield

    # Cleanup after test
    await cleanup()


async def create_file_node_directly(
    memgraph_adapter: MemgraphKnowledgeAdapter,
    project_name: str,
    file_path: str,
    entity_id: Optional[str] = None,
) -> str:
    """
    Create a FILE node DIRECTLY in Memgraph with correct project_name.

    This simulates the state AFTER file ingestion but BEFORE tree building.
    The file has the CORRECT project_name that should NOT be overwritten.

    Returns:
        entity_id of the created file node
    """
    if entity_id is None:
        entity_id = f"file:{project_name}:{file_path}"

    query = """
    CREATE (f:File {
        entity_id: $entity_id,
        project_name: $project_name,
        path: $path,
        name: $name,
        created_at: timestamp()
    })
    RETURN f.entity_id as entity_id
    """

    file_name = Path(file_path).name

    async with memgraph_adapter.driver.session() as session:
        result = await session.run(
            query,
            entity_id=entity_id,
            project_name=project_name,
            path=file_path,
            name=file_name,
        )
        record = await result.single()
        return record["entity_id"]


async def verify_file_project_name(
    memgraph_adapter: MemgraphKnowledgeAdapter,
    entity_id: str,
    expected_project_name: str,
) -> dict:
    """
    Verify that a FILE node has the expected project_name.

    Returns:
        Dict with file node properties including project_name
    """
    query = """
    MATCH (f:File {entity_id: $entity_id})
    RETURN f.entity_id as entity_id,
           f.project_name as project_name,
           f.path as path,
           f.name as name
    """

    async with memgraph_adapter.driver.session() as session:
        result = await session.run(query, entity_id=entity_id)
        file_node = await result.single()

    assert file_node is not None, f"File node not found: {entity_id}"
    assert file_node["project_name"] == expected_project_name, (
        f"❌ REGRESSION DETECTED: project_name was OVERWRITTEN!\n"
        f"  File: {file_node['path']}\n"
        f"  Entity ID: {entity_id}\n"
        f"  Expected: '{expected_project_name}'\n"
        f"  Actual: '{file_node['project_name']}'\n"
        f"  This indicates the ON MATCH clause is still overwriting project_name!"
    )

    return file_node


@pytest.mark.asyncio
@pytest.mark.integration
class TestProjectNamePersistenceThroughTreeBuilding:
    """
    Regression tests for project_name persistence during tree building.

    These tests specifically validate that the MERGE ON MATCH clause does NOT
    overwrite correct project_name values with "unknown" during tree building.
    """

    async def test_single_file_project_name_preserved_after_tree_building(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test that project_name on a single file is NOT overwritten during tree building.

        Steps:
        1. Create FILE node with CORRECT project_name (simulating ingestion)
        2. Run tree building (triggers MERGE with ON MATCH)
        3. Verify project_name is still CORRECT (not "unknown")

        This is the SIMPLEST regression test case.
        """
        project_name = f"test_persistence_single_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        file_path = str(project_path / "main.py")
        entity_id = f"file:{project_name}:{file_path}"

        # Step 1: Create FILE node with CORRECT project_name (simulating post-ingestion state)
        created_entity_id = await create_file_node_directly(
            memgraph_adapter, project_name, file_path, entity_id
        )
        assert created_entity_id == entity_id

        # Verify initial state (file has correct project_name)
        initial_state = await verify_file_project_name(
            memgraph_adapter, entity_id, project_name
        )
        assert initial_state["project_name"] == project_name

        # Step 2: Run tree building (this will trigger MERGE with ON MATCH)
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=[file_path],
            file_entity_mapping={file_path: entity_id},
        )

        await asyncio.sleep(0.2)

        # Step 3: Verify project_name is STILL correct (not overwritten with "unknown")
        final_state = await verify_file_project_name(
            memgraph_adapter, entity_id, project_name
        )
        assert final_state["project_name"] == project_name, (
            f"❌ BUG REPRODUCED: project_name was overwritten during tree building!\n"
            f"  Before tree building: '{initial_state['project_name']}'\n"
            f"  After tree building: '{final_state['project_name']}'\n"
            f"  The ON MATCH clause is overwriting the correct value!"
        )

    async def test_multiple_files_project_name_preserved(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test that project_name on multiple files is NOT overwritten during tree building.

        This tests that the bug doesn't affect some files while sparing others.
        """
        project_name = f"test_persistence_multiple_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create multiple files
        file_paths = [
            str(project_path / "file1.py"),
            str(project_path / "file2.py"),
            str(project_path / "file3.py"),
        ]

        entity_ids = []

        # Step 1: Create all FILE nodes with CORRECT project_name
        for file_path in file_paths:
            entity_id = f"file:{project_name}:{file_path}"
            await create_file_node_directly(
                memgraph_adapter, project_name, file_path, entity_id
            )
            entity_ids.append(entity_id)

        # Verify initial state
        for entity_id in entity_ids:
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Step 2: Run tree building
        file_entity_mapping = {
            path: entity_id for path, entity_id in zip(file_paths, entity_ids)
        }

        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
            file_entity_mapping=file_entity_mapping,
        )

        await asyncio.sleep(0.2)

        # Step 3: Verify ALL files still have correct project_name
        for entity_id in entity_ids:
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

    async def test_nested_directory_structure_project_name_preserved(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test project_name preservation in nested directory structures.

        This tests the most common scenario: files in nested directories.
        The bug would affect these files when creating CONTAINS relationships.
        """
        project_name = f"test_persistence_nested_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create nested structure
        src_dir = project_path / "src"
        src_dir.mkdir()
        utils_dir = src_dir / "utils"
        utils_dir.mkdir()

        file_paths = [
            str(project_path / "README.md"),
            str(src_dir / "main.py"),
            str(utils_dir / "helper.py"),
        ]

        entity_ids = []

        # Step 1: Create FILE nodes with CORRECT project_name
        for file_path in file_paths:
            entity_id = f"file:{project_name}:{file_path}"
            await create_file_node_directly(
                memgraph_adapter, project_name, file_path, entity_id
            )
            entity_ids.append(entity_id)

        # Verify initial state
        for entity_id in entity_ids:
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Step 2: Run tree building (creates PROJECT, DIRECTORY nodes and CONTAINS relationships)
        file_entity_mapping = {
            path: entity_id for path, entity_id in zip(file_paths, entity_ids)
        }

        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
            file_entity_mapping=file_entity_mapping,
        )

        await asyncio.sleep(0.2)

        # Step 3: Verify all files STILL have correct project_name
        for entity_id in entity_ids:
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Step 4: Verify tree structure is correct AND all nodes have correct project_name
        tree_query = """
        MATCH (p:PROJECT {project_name: $project_name})
        MATCH (d:Directory {project_name: $project_name})
        MATCH (f:File {project_name: $project_name})
        RETURN count(DISTINCT p) as project_count,
               count(DISTINCT d) as directory_count,
               count(DISTINCT f) as file_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(tree_query, project_name=project_name)
            counts = await result.single()

        assert counts["project_count"] == 1, "Should have 1 PROJECT node"
        assert (
            counts["directory_count"] == 2
        ), "Should have 2 DIRECTORY nodes (src, src/utils)"
        assert counts["file_count"] == 3, "Should have 3 FILE nodes"

    async def test_project_name_preserved_across_multiple_tree_builds(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test that project_name survives MULTIPLE tree building operations.

        This simulates re-ingestion or incremental updates where tree building
        runs multiple times on the same files.
        """
        project_name = f"test_persistence_multiple_builds_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        file_path = str(project_path / "main.py")
        entity_id = f"file:{project_name}:{file_path}"

        # Step 1: Create FILE node with CORRECT project_name
        await create_file_node_directly(
            memgraph_adapter, project_name, file_path, entity_id
        )

        # Verify initial state
        await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Step 2: Run tree building MULTIPLE times
        for iteration in range(3):
            await directory_indexer.index_directory_hierarchy(
                project_name=project_name,
                project_root=str(project_path),
                file_paths=[file_path],
                file_entity_mapping={file_path: entity_id},
            )

            await asyncio.sleep(0.1)

            # Verify project_name is STILL correct after each iteration
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

    async def test_no_files_have_unknown_project_name_after_tree_building(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test that NO files end up with "unknown" as project_name after tree building.

        This is the ultimate regression test: verify that "unknown" doesn't appear anywhere.
        """
        project_name = f"test_persistence_no_unknown_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        src_dir = project_path / "src"
        src_dir.mkdir()

        file_paths = [
            str(project_path / "file1.py"),
            str(src_dir / "file2.py"),
        ]

        entity_ids = []

        # Create FILE nodes with CORRECT project_name
        for file_path in file_paths:
            entity_id = f"file:{project_name}:{file_path}"
            await create_file_node_directly(
                memgraph_adapter, project_name, file_path, entity_id
            )
            entity_ids.append(entity_id)

        # Run tree building
        file_entity_mapping = {
            path: entity_id for path, entity_id in zip(file_paths, entity_ids)
        }

        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
            file_entity_mapping=file_entity_mapping,
        )

        await asyncio.sleep(0.2)

        # Query for ANY file with "unknown" project_name
        unknown_query = """
        MATCH (f:File)
        WHERE f.project_name = 'unknown'
           OR f.project_name IS NULL
           OR f.project_name = ''
        RETURN f.entity_id as entity_id,
               f.project_name as project_name,
               f.path as path
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(unknown_query)
            unknown_files = await result.data()

        assert len(unknown_files) == 0, (
            f"❌ CRITICAL BUG: Found {len(unknown_files)} files with 'unknown' project_name!\n"
            + "\n".join(
                [
                    f"  - {f['path']} (entity_id: {f['entity_id']}, "
                    f"project_name: {f.get('project_name', 'NULL')})"
                    for f in unknown_files
                ]
            )
            + "\n\nThis indicates the ON MATCH clause is overwriting correct values with 'unknown'!"
        )

    async def test_contains_relationships_dont_overwrite_metadata(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test that creating CONTAINS relationships doesn't overwrite file metadata.

        This directly tests the _create_contains_relationship() method which
        contained the bug.
        """
        project_name = f"test_persistence_contains_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        file_path = str(project_path / "main.py")
        entity_id = f"file:{project_name}:{file_path}"

        # Step 1: Create FILE node with CORRECT project_name and additional metadata
        query = """
        CREATE (f:File {
            entity_id: $entity_id,
            project_name: $project_name,
            path: $path,
            name: $name,
            language: 'python',
            custom_field: 'important_value',
            created_at: timestamp()
        })
        RETURN f
        """

        async with memgraph_adapter.driver.session() as session:
            await session.run(
                query,
                entity_id=entity_id,
                project_name=project_name,
                path=file_path,
                name="main.py",
            )

        # Step 2: Run tree building (creates CONTAINS relationships)
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=[file_path],
            file_entity_mapping={file_path: entity_id},
        )

        await asyncio.sleep(0.2)

        # Step 3: Verify ALL metadata is preserved (not just project_name)
        verify_query = """
        MATCH (f:File {entity_id: $entity_id})
        RETURN f.entity_id as entity_id,
               f.project_name as project_name,
               f.path as path,
               f.language as language,
               f.custom_field as custom_field
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(verify_query, entity_id=entity_id)
            file_node = await result.single()

        assert file_node["project_name"] == project_name, "project_name was overwritten"
        assert file_node["language"] == "python", "language field was overwritten"
        assert (
            file_node["custom_field"] == "important_value"
        ), "custom_field was overwritten"

    async def test_edge_case_file_with_complex_path(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Test project_name preservation for files with complex paths.

        Tests edge cases like deeply nested paths, special characters, etc.
        """
        project_name = f"test_persistence_complex_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create deeply nested structure
        deep_dir = project_path / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)

        file_path = str(deep_dir / "deep_file.py")
        entity_id = f"file:{project_name}:{file_path}"

        # Create FILE node
        await create_file_node_directly(
            memgraph_adapter, project_name, file_path, entity_id
        )

        # Verify initial state
        await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Run tree building (creates many intermediate DIRECTORY nodes)
        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=[file_path],
            file_entity_mapping={file_path: entity_id},
        )

        await asyncio.sleep(0.2)

        # Verify project_name is still correct
        await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Verify tree connectivity
        connectivity_query = """
        MATCH path = (p:PROJECT {project_name: $project_name})
                      -[:CONTAINS*]->(f:File {entity_id: $entity_id})
        RETURN size(relationships(path)) as path_length
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(
                connectivity_query, project_name=project_name, entity_id=entity_id
            )
            path_result = await result.single()

        # Should have path: PROJECT -> a -> b -> c -> d -> e -> file (6 hops)
        assert path_result["path_length"] == 6, (
            f"Tree connectivity broken: expected path length 6, "
            f"got {path_result['path_length']}"
        )


@pytest.mark.asyncio
@pytest.mark.integration
class TestProjectNamePersistenceRealWorldScenarios:
    """
    Real-world scenario tests for project_name persistence.

    These tests simulate actual ingestion workflows where files are indexed first,
    then tree building happens afterward.
    """

    async def test_simulated_bulk_ingestion_workflow(
        self, tmp_path, directory_indexer, memgraph_adapter, unique_test_id
    ):
        """
        Simulate a realistic bulk ingestion workflow.

        Workflow:
        1. Ingest files (creates FILE nodes with correct project_name)
        2. Build tree structure (creates PROJECT, DIRECTORY, CONTAINS)
        3. Verify ALL files still have correct project_name
        4. Verify tree structure is complete and correct
        """
        project_name = f"test_persistence_bulk_{unique_test_id}"
        project_path = tmp_path / project_name
        project_path.mkdir()

        # Create realistic project structure
        src_dir = project_path / "src"
        src_dir.mkdir()
        (src_dir / "utils").mkdir()
        (src_dir / "models").mkdir()

        tests_dir = project_path / "tests"
        tests_dir.mkdir()

        docs_dir = project_path / "docs"
        docs_dir.mkdir()

        file_paths = [
            str(project_path / "README.md"),
            str(project_path / "setup.py"),
            str(src_dir / "__init__.py"),
            str(src_dir / "main.py"),
            str(src_dir / "utils" / "helpers.py"),
            str(src_dir / "models" / "user.py"),
            str(tests_dir / "test_main.py"),
            str(docs_dir / "guide.md"),
        ]

        entity_ids = []

        # Phase 1: Simulate file ingestion (creates FILE nodes with correct project_name)
        for file_path in file_paths:
            entity_id = f"file:{project_name}:{file_path}"
            await create_file_node_directly(
                memgraph_adapter, project_name, file_path, entity_id
            )
            entity_ids.append(entity_id)

        # Verify all files have correct project_name after ingestion
        for entity_id in entity_ids:
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Phase 2: Build tree structure (this is where the bug would occur)
        file_entity_mapping = {
            path: entity_id for path, entity_id in zip(file_paths, entity_ids)
        }

        await directory_indexer.index_directory_hierarchy(
            project_name=project_name,
            project_root=str(project_path),
            file_paths=file_paths,
            file_entity_mapping=file_entity_mapping,
        )

        await asyncio.sleep(0.3)

        # Phase 3: Verify ALL files STILL have correct project_name (not overwritten)
        for entity_id in entity_ids:
            await verify_file_project_name(memgraph_adapter, entity_id, project_name)

        # Phase 4: Verify complete tree structure
        tree_validation_query = """
        MATCH (p:PROJECT {project_name: $project_name})
        OPTIONAL MATCH (p)-[:CONTAINS*]->(d:Directory)
        WHERE d.project_name = $project_name
        OPTIONAL MATCH (p)-[:CONTAINS*]->(f:File)
        WHERE f.project_name = $project_name
        RETURN count(DISTINCT p) as project_count,
               count(DISTINCT d) as directory_count,
               count(DISTINCT f) as file_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(tree_validation_query, project_name=project_name)
            tree_stats = await result.single()

        assert tree_stats["project_count"] == 1, "Should have 1 PROJECT node"
        assert tree_stats["directory_count"] == 5, (
            f"Should have 5 DIRECTORY nodes (src, utils, models, tests, docs), "
            f"found {tree_stats['directory_count']}"
        )
        assert (
            tree_stats["file_count"] == 8
        ), f"Should have 8 FILE nodes, found {tree_stats['file_count']}"

        # Phase 5: Verify NO orphaned files (all reachable from PROJECT)
        orphan_query = """
        MATCH (f:File {project_name: $project_name})
        OPTIONAL MATCH path = (p:PROJECT {project_name: $project_name})-[:CONTAINS*]->(f)
        WITH f, path
        WHERE path IS NULL
        RETURN count(f) as orphan_count
        """

        async with memgraph_adapter.driver.session() as session:
            result = await session.run(orphan_query, project_name=project_name)
            orphan_result = await result.single()

        assert orphan_result["orphan_count"] == 0, (
            f"Found {orphan_result['orphan_count']} orphaned files! "
            f"Files exist but are not reachable from PROJECT root."
        )


if __name__ == "__main__":
    """
    Run these regression tests with:

    pytest tests/integration/test_project_name_persistence.py -v

    Run specific test:
    pytest tests/integration/test_project_name_persistence.py::TestProjectNamePersistenceThroughTreeBuilding::test_single_file_project_name_preserved_after_tree_building -v

    Run all tests with detailed output:
    pytest tests/integration/test_project_name_persistence.py -v -s

    Run only regression tests:
    pytest tests/integration/test_project_name_persistence.py -v -m integration
    """
    print("Run with: pytest tests/integration/test_project_name_persistence.py -v")
