"""
End-to-End File Tree/Graph Indexing Integration Tests

Tests the complete workflow from file ingestion through graph building
to query execution using real Memgraph and Qdrant instances.

Test Coverage:
- Full file indexing pipeline (discovery → metadata → graph → embeddings)
- FILE node creation and IMPORT relationship storage
- Directory hierarchy building (PROJECT → DIR → FILE)
- Entity linking (FILE -[:DEFINES]-> ENTITY)
- Import resolution accuracy
- Orphan detection
- Tree visualization API
- Path information in embeddings

Created: 2025-11-07
ONEX Pattern: Integration testing for file tree/graph implementation
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def service_urls():
    """Service URL configuration"""
    return {
        "intelligence": os.getenv("INTELLIGENCE_URL", "http://localhost:8053"),
        "bridge": os.getenv("BRIDGE_URL", "http://localhost:8054"),
        "search": os.getenv("SEARCH_URL", "http://localhost:8055"),
        "memgraph_uri": os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
    }


@pytest.fixture(scope="module")
def test_fixtures_dir():
    """Path to test fixtures directory"""
    return Path(__file__).parent.parent / "fixtures"


@pytest_asyncio.fixture(scope="module")
async def memgraph_connection(service_urls):
    """Create Memgraph connection for querying"""
    driver = AsyncGraphDatabase.driver(service_urls["memgraph_uri"])
    yield driver
    await driver.close()


@pytest_asyncio.fixture(scope="module")
async def http_client():
    """HTTP client for service communication"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        yield client


class FileTreeTestHelper:
    """Helper class for file tree/graph testing"""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        memgraph_driver,
        service_urls: Dict[str, str],
    ):
        self.http_client = http_client
        self.memgraph_driver = memgraph_driver
        self.service_urls = service_urls

    async def wait_for_indexing(
        self, project_name: str, expected_file_count: int, timeout: float = 30.0
    ) -> bool:
        """Wait for files to be indexed in Memgraph"""
        start_time = time.time()
        check_interval = 2.0

        while time.time() - start_time < timeout:
            async with self.memgraph_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                    RETURN count(f) as file_count
                    """,
                    project_name=project_name,
                )
                record = await result.single()
                if record and record["file_count"] >= expected_file_count:
                    return True

            await asyncio.sleep(check_interval)

        return False

    async def get_file_nodes(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all FILE nodes for a project"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                RETURN f.path as path,
                       f.entity_count as entity_count,
                       f.import_count as import_count,
                       f.last_modified as last_modified
                ORDER BY f.path
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def get_import_relationships(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all IMPORTS relationships for a project"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f1:FILE)
                -[r:IMPORTS]->(f2:FILE)
                RETURN f1.path as source,
                       f2.path as target,
                       r.import_type as import_type,
                       r.line_number as line_number
                ORDER BY f1.path, f2.path
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def get_directory_hierarchy(self, project_name: str) -> List[Dict[str, Any]]:
        """Get complete directory hierarchy for a project"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH path = (p:PROJECT {name: $project_name})-[:CONTAINS*]->(n)
                WHERE n:DIR OR n:FILE
                RETURN [node in nodes(path) |
                        {type: labels(node)[0],
                         name: COALESCE(node.name, node.path)}] as hierarchy,
                       length(path) as depth
                ORDER BY depth, hierarchy
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def get_entity_links(self, project_name: str) -> List[Dict[str, Any]]:
        """Get FILE -[:DEFINES]-> ENTITY relationships"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                -[:DEFINES]->(e:ENTITY)
                RETURN f.path as file_path,
                       e.name as entity_name,
                       e.type as entity_type
                ORDER BY f.path, e.name
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def detect_orphans(self, project_name: str) -> List[Dict[str, Any]]:
        """Detect orphaned files (no imports in or out)"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                OPTIONAL MATCH outgoing = (f)-[:IMPORTS]->()
                OPTIONAL MATCH incoming = ()-[:IMPORTS]->(f)
                WITH f, outgoing, incoming
                WHERE outgoing IS NULL AND incoming IS NULL
                RETURN f.path as path,
                       f.entity_count as entity_count
                ORDER BY f.path
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def get_tree_visualization(self, project_name: str) -> Dict[str, Any]:
        """Get tree visualization from API"""
        response = await self.http_client.get(
            f"{self.service_urls['intelligence']}/api/tree/visualize",
            params={"project_name": project_name},
        )
        response.raise_for_status()
        return response.json()

    async def search_by_file_path(self, file_path: str) -> Dict[str, Any]:
        """Search for files by path using search service"""
        response = await self.http_client.post(
            f"{self.service_urls['search']}/search",
            json={
                "query": f"file:{file_path}",
                "mode": "hybrid",
                "limit": 10,
                "filters": {"file_path": file_path},
            },
        )
        response.raise_for_status()
        return response.json()

    async def verify_embeddings_include_path(
        self, project_name: str, file_path: str
    ) -> bool:
        """Verify embeddings include path information"""
        # Search for the file
        results = await self.search_by_file_path(file_path)

        # Check if path appears in metadata or content
        for result in results.get("results", []):
            metadata = result.get("metadata", {})
            if metadata.get("file_path") == file_path:
                return True
            if file_path in result.get("content", ""):
                return True

        return False

    async def cleanup_project(self, project_name: str):
        """Clean up test project data from Memgraph"""
        async with self.memgraph_driver.session() as session:
            await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})
                OPTIONAL MATCH (p)-[:CONTAINS*]->(n)
                DETACH DELETE p, n
                """,
                project_name=project_name,
            )


@pytest_asyncio.fixture
async def file_tree_helper(http_client, memgraph_connection, service_urls):
    """Create file tree test helper"""
    helper = FileTreeTestHelper(http_client, memgraph_connection, service_urls)
    yield helper


@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_file_indexing_pipeline(
    file_tree_helper: FileTreeTestHelper, test_fixtures_dir: Path
):
    """
    Test complete file indexing workflow:
    1. Ingest test repository via bulk_ingest
    2. Verify file nodes created in Memgraph
    3. Verify import relationships stored
    4. Verify directory hierarchy built (PROJECT → DIR → FILE)
    5. Run orphan detection
    6. Verify results accurate
    7. Query tree visualization API
    8. Verify embeddings include path information
    """
    project_name = f"test_e2e_small_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        # Step 1: Ingest test repository
        logger.info(f"Ingesting test repository: {repo_path}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        # Run bulk ingest (this publishes Kafka events)
        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Step 2: Wait for indexing to complete (expect 3 files: main.py, utils.py, orphan.py)
        indexed = await file_tree_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed within timeout"

        # Step 3: Verify file nodes
        file_nodes = await file_tree_helper.get_file_nodes(project_name)
        assert len(file_nodes) == 3, f"Expected 3 files, found {len(file_nodes)}"

        file_paths = [node["path"] for node in file_nodes]
        assert any("main.py" in path for path in file_paths)
        assert any("utils.py" in path for path in file_paths)
        assert any("orphan.py" in path for path in file_paths)

        # Step 4: Verify import relationships
        imports = await file_tree_helper.get_import_relationships(project_name)
        assert len(imports) >= 1, "Expected at least 1 import relationship"

        # main.py should import utils.py
        main_imports_utils = any(
            "main.py" in imp["source"] and "utils.py" in imp["target"]
            for imp in imports
        )
        assert main_imports_utils, "main.py should import utils.py"

        # Step 5: Verify directory hierarchy
        hierarchy = await file_tree_helper.get_directory_hierarchy(project_name)
        assert len(hierarchy) > 0, "Directory hierarchy should not be empty"

        # Should have PROJECT node at root
        root_nodes = [h for h in hierarchy if h["depth"] == 1]
        assert len(root_nodes) > 0, "Should have root PROJECT node"

        # Step 6: Detect orphans
        orphans = await file_tree_helper.detect_orphans(project_name)
        assert len(orphans) >= 1, "Should detect at least 1 orphan file"

        # orphan.py should be detected as orphan
        orphan_detected = any("orphan.py" in o["path"] for o in orphans)
        assert orphan_detected, "orphan.py should be detected as orphaned"

        # Step 7: Query tree visualization API
        tree_viz = await file_tree_helper.get_tree_visualization(project_name)
        assert tree_viz is not None, "Tree visualization should return data"
        assert "nodes" in tree_viz or "files" in tree_viz, "Should contain nodes/files"

        # Step 8: Verify embeddings include path information
        main_py_path = next(path for path in file_paths if "main.py" in path)
        has_path = await file_tree_helper.verify_embeddings_include_path(
            project_name, main_py_path
        )
        assert has_path, "Embeddings should include file path information"

        logger.info("✅ Full file indexing pipeline test passed")

    finally:
        # Cleanup
        await file_tree_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_file_node_entity_linking(
    file_tree_helper: FileTreeTestHelper, test_fixtures_dir: Path
):
    """
    Test FILE -[:DEFINES]-> ENTITY relationships.

    Verifies that:
    - Functions and classes are extracted as entities
    - FILE nodes link to their defined entities
    - entity_count matches actual entity count
    """
    project_name = f"test_entities_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        # Ingest repository
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await file_tree_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get entity links
        entity_links = await file_tree_helper.get_entity_links(project_name)
        assert len(entity_links) > 0, "Should have entity links"

        # Verify utils.py defines entities
        utils_entities = [e for e in entity_links if "utils.py" in e["file_path"]]
        assert len(utils_entities) >= 2, "utils.py should define at least 2 entities"

        # Check for specific entities
        entity_names = [e["entity_name"] for e in utils_entities]
        assert (
            "helper_function" in entity_names or "HelperClass" in entity_names
        ), "Should find function or class entities"

        # Verify entity_count accuracy
        file_nodes = await file_tree_helper.get_file_nodes(project_name)
        for node in file_nodes:
            if "utils.py" in node["path"]:
                actual_entity_count = len(
                    [e for e in entity_links if e["file_path"] == node["path"]]
                )
                assert (
                    node["entity_count"] == actual_entity_count
                ), f"entity_count mismatch: stored={node['entity_count']}, actual={actual_entity_count}"

        logger.info("✅ Entity linking test passed")

    finally:
        await file_tree_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_import_resolution_accuracy(
    file_tree_helper: FileTreeTestHelper, test_fixtures_dir: Path
):
    """
    Test import resolution accuracy.

    Verifies that:
    - Import statements are correctly parsed
    - Import targets are resolved to actual files
    - Import relationships are stored with correct metadata
    """
    project_name = f"test_imports_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_complex"

    try:
        # Ingest complex repository with multiple imports
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing (expect 6+ files)
        indexed = await file_tree_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=6, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get import relationships
        imports = await file_tree_helper.get_import_relationships(project_name)
        assert len(imports) > 0, "Should have import relationships"

        # Verify main.py imports from models and utils
        main_imports = [imp for imp in imports if "main.py" in imp["source"]]
        assert len(main_imports) >= 2, "main.py should have multiple imports"

        # Check for specific imports
        import_targets = [imp["target"] for imp in main_imports]
        assert any(
            "user.py" in target for target in import_targets
        ), "Should import user.py"
        assert any(
            "helpers.py" in target for target in import_targets
        ), "Should import helpers.py"

        # Verify import_count accuracy
        file_nodes = await file_tree_helper.get_file_nodes(project_name)
        for node in file_nodes:
            if "main.py" in node["path"]:
                actual_import_count = len(
                    [imp for imp in imports if imp["source"] == node["path"]]
                )
                assert (
                    node["import_count"] == actual_import_count
                ), f"import_count mismatch for main.py"

        logger.info("✅ Import resolution test passed")

    finally:
        await file_tree_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_directory_hierarchy_correctness(
    file_tree_helper: FileTreeTestHelper, test_fixtures_dir: Path
):
    """
    Test directory hierarchy correctness.

    Verifies that:
    - PROJECT → DIR → FILE hierarchy matches filesystem
    - All directories are represented
    - Nested directories maintain correct structure
    """
    project_name = f"test_hierarchy_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_complex"

    try:
        # Ingest complex repository with nested directories
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await file_tree_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=6, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get directory hierarchy
        hierarchy = await file_tree_helper.get_directory_hierarchy(project_name)
        assert len(hierarchy) > 0, "Should have hierarchy"

        # Verify structure depth
        max_depth = max(h["depth"] for h in hierarchy)
        assert max_depth >= 3, "Should have at least 3 levels (PROJECT → DIR → FILE)"

        # Verify directory nodes exist
        dir_nodes = [
            h for h in hierarchy if any(n["type"] == "DIR" for n in h["hierarchy"])
        ]
        assert len(dir_nodes) > 0, "Should have DIR nodes"

        # Verify nested structure (src/models, src/utils)
        nested_paths = []
        for h in hierarchy:
            path_parts = [n["name"] for n in h["hierarchy"]]
            nested_paths.append(" → ".join(path_parts))

        # Check for expected directory structure
        has_src_dir = any("src" in path for path in nested_paths)
        has_models_dir = any("models" in path for path in nested_paths)
        has_utils_dir = any("utils" in path for path in nested_paths)

        assert has_src_dir, "Should have src directory"
        assert has_models_dir, "Should have models directory"
        assert has_utils_dir, "Should have utils directory"

        logger.info("✅ Directory hierarchy test passed")

    finally:
        await file_tree_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_detection_accuracy(
    file_tree_helper: FileTreeTestHelper, test_fixtures_dir: Path
):
    """
    Test orphan detection accuracy.

    Verifies that:
    - Known orphan files are detected correctly
    - Non-orphan files are not marked as orphans
    - Orphan detection handles edge cases
    """
    project_name = f"test_orphans_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        # Ingest repository with known orphan
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await file_tree_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Detect orphans
        orphans = await file_tree_helper.detect_orphans(project_name)

        # Verify orphan.py is detected
        orphan_py_detected = any("orphan.py" in o["path"] for o in orphans)
        assert orphan_py_detected, "orphan.py should be detected as orphaned"

        # Verify main.py and utils.py are NOT orphans
        main_py_orphan = any("main.py" in o["path"] for o in orphans)
        utils_py_orphan = any("utils.py" in o["path"] for o in orphans)

        assert not main_py_orphan, "main.py should not be orphaned"
        assert not utils_py_orphan, "utils.py should not be orphaned"

        # Verify orphan count
        assert (
            len(orphans) == 1
        ), f"Expected 1 orphan, found {len(orphans)}: {[o['path'] for o in orphans]}"

        logger.info("✅ Orphan detection test passed")

    finally:
        await file_tree_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_tree_visualization_completeness(
    file_tree_helper: FileTreeTestHelper, test_fixtures_dir: Path
):
    """
    Test tree visualization completeness.

    Verifies that:
    - All nodes are present in visualization
    - All edges/relationships are included
    - Visualization data is properly formatted
    """
    project_name = f"test_visualization_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        # Ingest repository
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await file_tree_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get tree visualization
        tree_viz = await file_tree_helper.get_tree_visualization(project_name)

        assert tree_viz is not None, "Tree visualization should return data"

        # Verify structure
        assert "nodes" in tree_viz or "files" in tree_viz, "Should have nodes/files"
        assert (
            "relationships" in tree_viz or "edges" in tree_viz or "imports" in tree_viz
        ), "Should have relationships/edges"

        # Verify completeness
        nodes_key = "nodes" if "nodes" in tree_viz else "files"
        nodes = tree_viz[nodes_key]

        assert len(nodes) >= 3, f"Should have at least 3 file nodes, found {len(nodes)}"

        # Verify node data includes necessary information
        for node in nodes:
            assert "path" in node or "name" in node, "Node should have path/name"
            assert (
                "entity_count" in node or "entities" in node
            ), "Node should have entity information"

        logger.info("✅ Tree visualization test passed")

    finally:
        await file_tree_helper.cleanup_project(project_name)
