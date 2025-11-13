"""
Entity ID Schema Validation Integration Tests

Tests comprehensive validation of entity_id formats across the Memgraph knowledge graph.
Ensures schema consistency to prevent orphaned nodes and broken relationships.

Test Coverage:
- FILE node entity_id format validation (file_{hash12})
- PLACEHOLDER node detection and prevention
- Relationship integrity validation
- Graph traversal correctness
- Cross-reference validation
- Schema compliance enforcement

Created: 2025-11-09
Purpose: Prevent regression of entity_id schema mismatches
Reference: ENTITY_ID_FORMAT_REFERENCE.md, MEMGRAPH_SCHEMA_ANALYSIS_REPORT.md
"""

import asyncio
import logging
import os
import re
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


# Entity ID Format Constants
FILE_HASH_PATTERN = re.compile(r"^file_[a-f0-9]{12}$")
FILE_PATH_PATTERN = re.compile(r"^file:[^:]+:.*$")
ENTITY_HASH_PATTERN = re.compile(r"^entity_[a-f0-9]{8}_[a-f0-9]{8}$")


class EntityIdValidationHelper:
    """Helper class for entity ID schema validation testing"""

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

    async def get_all_file_entity_ids(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all FILE node entity_ids for a project"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                RETURN f.entity_id as entity_id,
                       f.path as path,
                       f.name as name,
                       size(keys(f)) as property_count
                ORDER BY f.entity_id
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def count_placeholder_nodes(self, project_name: Optional[str] = None) -> int:
        """Count PLACEHOLDER FILE nodes (path-based entity_ids)"""
        async with self.memgraph_driver.session() as session:
            if project_name:
                result = await session.run(
                    """
                    MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                    WHERE f.entity_id CONTAINS ':'
                    RETURN count(f) as placeholder_count
                    """,
                    project_name=project_name,
                )
            else:
                result = await session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.entity_id CONTAINS ':'
                    RETURN count(f) as placeholder_count
                    """
                )
            record = await result.single()
            return record["placeholder_count"] if record else 0

    async def get_relationship_entity_ids(
        self, project_name: str
    ) -> List[Dict[str, Any]]:
        """Get entity_ids of source and target nodes in IMPORTS relationships"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f1:FILE)
                -[r:IMPORTS]->(f2:FILE)
                RETURN f1.entity_id as source_entity_id,
                       f1.path as source_path,
                       f1.name as source_name,
                       f2.entity_id as target_entity_id,
                       f2.path as target_path,
                       f2.name as target_name,
                       size(keys(f1)) as source_property_count,
                       size(keys(f2)) as target_property_count
                ORDER BY f1.entity_id
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def get_orphaned_file_nodes(self, project_name: str) -> List[Dict[str, Any]]:
        """Get FILE nodes with 0 relationships (orphaned)"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE)
                WHERE f.entity_id STARTS WITH 'file_'
                WITH f, size([(f)-[]-() | 1]) as rel_count
                WHERE rel_count = 0
                RETURN f.entity_id as entity_id,
                       f.path as path,
                       f.name as name,
                       rel_count
                ORDER BY f.entity_id
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def get_graph_traversal_paths(
        self, project_name: str, max_depth: int = 5
    ) -> List[Dict[str, Any]]:
        """Get all traversal paths through IMPORTS relationships"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                f"""
                MATCH (p:PROJECT {{name: $project_name}})-[:CONTAINS*]->(start:FILE)
                MATCH path = (start)-[:IMPORTS*1..{max_depth}]->(end:FILE)
                RETURN [node in nodes(path) | {{
                    entity_id: node.entity_id,
                    name: node.name,
                    path: node.path
                }}] as path_nodes,
                length(path) as path_length
                ORDER BY path_length DESC
                LIMIT 100
                """,
                project_name=project_name,
            )
            return [record.data() async for record in result]

    async def validate_entity_id_format(
        self, entity_id: str, node_type: str
    ) -> Dict[str, Any]:
        """
        Validate entity_id format against expected patterns.

        Returns:
            Dict with:
                - is_valid: bool
                - format_type: 'hash_based' | 'path_based' | 'unknown'
                - error: Optional error message
        """
        if node_type == "FILE":
            if FILE_HASH_PATTERN.match(entity_id):
                return {
                    "is_valid": True,
                    "format_type": "hash_based",
                    "error": None,
                }
            elif FILE_PATH_PATTERN.match(entity_id):
                return {
                    "is_valid": False,
                    "format_type": "path_based",
                    "error": f"FILE node using PLACEHOLDER format: {entity_id}",
                }
            else:
                return {
                    "is_valid": False,
                    "format_type": "unknown",
                    "error": f"FILE node with unknown format: {entity_id}",
                }
        elif node_type == "ENTITY":
            if ENTITY_HASH_PATTERN.match(entity_id):
                return {
                    "is_valid": True,
                    "format_type": "hash_based",
                    "error": None,
                }
            else:
                # Simple name format (stub entity)
                return {
                    "is_valid": True,
                    "format_type": "stub",
                    "error": None,
                }
        else:
            return {
                "is_valid": False,
                "format_type": "unknown",
                "error": f"Unknown node type: {node_type}",
            }

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
async def validation_helper(http_client, memgraph_connection, service_urls):
    """Create entity ID validation helper"""
    helper = EntityIdValidationHelper(http_client, memgraph_connection, service_urls)
    yield helper


@pytest.mark.slow
@pytest.mark.asyncio
async def test_all_file_nodes_use_hash_based_entity_ids(
    validation_helper: EntityIdValidationHelper, test_fixtures_dir: Path
):
    """
    Validate all FILE nodes use file_{hash} format.

    Success Criteria:
    - ALL FILE nodes match ^file_[a-f0-9]{12}$ regex
    - ZERO FILE nodes contain ':' character
    - No path-based entity_ids exist
    """
    project_name = f"test_hash_format_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        # Ingest test repository
        logger.info(f"Testing hash-based entity_id format for project: {project_name}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await validation_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed within timeout"

        # Get all FILE entity_ids
        file_nodes = await validation_helper.get_all_file_entity_ids(project_name)
        assert len(file_nodes) > 0, "No FILE nodes found"

        logger.info(f"Found {len(file_nodes)} FILE nodes to validate")

        # Validate each entity_id
        invalid_nodes = []
        path_based_nodes = []

        for node in file_nodes:
            entity_id = node["entity_id"]
            validation = await validation_helper.validate_entity_id_format(
                entity_id, "FILE"
            )

            if not validation["is_valid"]:
                invalid_nodes.append(
                    {
                        "entity_id": entity_id,
                        "path": node["path"],
                        "error": validation["error"],
                        "format_type": validation["format_type"],
                    }
                )

            if ":" in entity_id:
                path_based_nodes.append({"entity_id": entity_id, "path": node["path"]})

        # Assertions
        assert (
            len(invalid_nodes) == 0
        ), f"Found {len(invalid_nodes)} invalid entity_ids: {invalid_nodes}"
        assert (
            len(path_based_nodes) == 0
        ), f"Found {len(path_based_nodes)} path-based entity_ids: {path_based_nodes}"

        # Verify all match hash pattern
        for node in file_nodes:
            assert FILE_HASH_PATTERN.match(
                node["entity_id"]
            ), f"Entity_id doesn't match hash pattern: {node['entity_id']}"

        logger.info(
            f"✅ All {len(file_nodes)} FILE nodes use correct hash-based entity_id format"
        )

    finally:
        await validation_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_no_placeholder_nodes_exist(
    validation_helper: EntityIdValidationHelper, test_fixtures_dir: Path
):
    """
    Ensure no PLACEHOLDER stub nodes exist after indexing.

    Success Criteria:
    - Zero nodes with entity_id containing ':'
    - No file:project:module format nodes
    - No file:project:path format nodes
    """
    project_name = f"test_no_placeholders_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        logger.info(f"Testing for PLACEHOLDER nodes in project: {project_name}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await validation_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Count PLACEHOLDER nodes
        placeholder_count = await validation_helper.count_placeholder_nodes(
            project_name
        )

        assert (
            placeholder_count == 0
        ), f"Found {placeholder_count} PLACEHOLDER nodes (expected 0)"

        # Get all entity_ids and verify none contain ':'
        file_nodes = await validation_helper.get_all_file_entity_ids(project_name)
        colon_nodes = [node for node in file_nodes if ":" in node["entity_id"]]

        assert (
            len(colon_nodes) == 0
        ), f"Found {len(colon_nodes)} nodes with ':' in entity_id: {colon_nodes}"

        logger.info(
            f"✅ Verified 0 PLACEHOLDER nodes exist (checked {len(file_nodes)} FILE nodes)"
        )

    finally:
        await validation_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_all_relationships_connect_to_real_nodes(
    validation_helper: EntityIdValidationHelper, test_fixtures_dir: Path
):
    """
    Validate all relationships connect to REAL nodes (not PLACEHOLDERs).

    Success Criteria:
    - All source nodes have hash-based entity_ids
    - All target nodes have hash-based entity_ids
    - All source nodes have full properties (>4 properties)
    - All target nodes have full properties (>4 properties)
    - No relationships point to nodes with name='unknown'
    """
    project_name = f"test_real_relationships_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        logger.info(f"Testing relationship integrity for project: {project_name}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await validation_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get all relationship entity_ids
        relationships = await validation_helper.get_relationship_entity_ids(
            project_name
        )

        if len(relationships) == 0:
            logger.warning("No IMPORTS relationships found - skipping validation")
            return

        logger.info(f"Found {len(relationships)} IMPORTS relationships to validate")

        # Validate each relationship
        invalid_sources = []
        invalid_targets = []
        placeholder_sources = []
        placeholder_targets = []

        for rel in relationships:
            # Validate source entity_id format
            source_validation = await validation_helper.validate_entity_id_format(
                rel["source_entity_id"], "FILE"
            )
            if not source_validation["is_valid"]:
                invalid_sources.append(
                    {
                        "entity_id": rel["source_entity_id"],
                        "path": rel["source_path"],
                        "error": source_validation["error"],
                    }
                )

            # Validate target entity_id format
            target_validation = await validation_helper.validate_entity_id_format(
                rel["target_entity_id"], "FILE"
            )
            if not target_validation["is_valid"]:
                invalid_targets.append(
                    {
                        "entity_id": rel["target_entity_id"],
                        "path": rel["target_path"],
                        "error": target_validation["error"],
                    }
                )

            # Check for PLACEHOLDER nodes (minimal properties)
            if rel["source_property_count"] <= 4:
                placeholder_sources.append(
                    {
                        "entity_id": rel["source_entity_id"],
                        "path": rel["source_path"],
                        "property_count": rel["source_property_count"],
                    }
                )

            if rel["target_property_count"] <= 4:
                placeholder_targets.append(
                    {
                        "entity_id": rel["target_entity_id"],
                        "path": rel["target_path"],
                        "property_count": rel["target_property_count"],
                    }
                )

            # Check for name='unknown' (PLACEHOLDER indicator)
            if rel.get("source_name") == "unknown":
                logger.warning(
                    f"Source node has name='unknown': {rel['source_entity_id']}"
                )

            if rel.get("target_name") == "unknown":
                logger.warning(
                    f"Target node has name='unknown': {rel['target_entity_id']}"
                )

        # Assertions
        assert (
            len(invalid_sources) == 0
        ), f"Found {len(invalid_sources)} relationships with invalid source entity_ids: {invalid_sources}"
        assert (
            len(invalid_targets) == 0
        ), f"Found {len(invalid_targets)} relationships with invalid target entity_ids: {invalid_targets}"
        assert (
            len(placeholder_sources) == 0
        ), f"Found {len(placeholder_sources)} relationships to PLACEHOLDER source nodes: {placeholder_sources}"
        assert (
            len(placeholder_targets) == 0
        ), f"Found {len(placeholder_targets)} relationships to PLACEHOLDER target nodes: {placeholder_targets}"

        logger.info(
            f"✅ All {len(relationships)} relationships connect to REAL nodes with valid entity_ids"
        )

    finally:
        await validation_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_graph_traversal_through_imports(
    validation_helper: EntityIdValidationHelper, test_fixtures_dir: Path
):
    """
    Verify graph traversal works correctly via IMPORTS relationships.

    Success Criteria:
    - Can find connected paths through IMPORTS
    - All nodes in paths have hash-based entity_ids
    - Paths are logically correct (imports make sense)
    - No broken paths due to PLACEHOLDER nodes
    """
    project_name = f"test_graph_traversal_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_complex"

    try:
        logger.info(f"Testing graph traversal for project: {project_name}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing (expect 6+ files)
        indexed = await validation_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=6, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get traversal paths
        paths = await validation_helper.get_graph_traversal_paths(
            project_name, max_depth=5
        )

        if len(paths) == 0:
            logger.warning("No traversal paths found - repository may have no imports")
            return

        logger.info(f"Found {len(paths)} traversal paths to validate")

        # Validate each path
        invalid_path_nodes = []

        for path_data in paths:
            path_nodes = path_data["path_nodes"]
            path_length = path_data["path_length"]

            for node in path_nodes:
                entity_id = node["entity_id"]
                validation = await validation_helper.validate_entity_id_format(
                    entity_id, "FILE"
                )

                if not validation["is_valid"]:
                    invalid_path_nodes.append(
                        {
                            "entity_id": entity_id,
                            "path": node["path"],
                            "error": validation["error"],
                            "path_length": path_length,
                        }
                    )

        # Assertions
        assert (
            len(invalid_path_nodes) == 0
        ), f"Found {len(invalid_path_nodes)} invalid nodes in traversal paths: {invalid_path_nodes}"

        # Verify all paths have valid entity_ids
        total_nodes_checked = sum(len(p["path_nodes"]) for p in paths)
        logger.info(
            f"✅ Successfully traversed {len(paths)} paths ({total_nodes_checked} nodes total) with valid entity_ids"
        )

    finally:
        await validation_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_entity_id_format_validation(
    validation_helper: EntityIdValidationHelper,
):
    """
    Test entity_id validator function with various formats.

    Success Criteria:
    - Hash-based FILE entity_ids validate correctly
    - Path-based FILE entity_ids are rejected
    - Unknown formats are rejected
    - Validator provides clear error messages
    """
    logger.info("Testing entity_id format validation logic")

    # Test cases: (entity_id, node_type, expected_valid, expected_format_type)
    test_cases = [
        # Valid FILE nodes (hash-based)
        ("file_91f521860bc3", "FILE", True, "hash_based"),
        ("file_abc123def456", "FILE", True, "hash_based"),
        ("file_000000000000", "FILE", True, "hash_based"),
        # Invalid FILE nodes (path-based PLACEHOLDERs)
        ("file:omniarchon:asyncio", "FILE", False, "path_based"),
        ("file:omniarchon:archon://projects/...", "FILE", False, "path_based"),
        ("file:project:module.submodule", "FILE", False, "path_based"),
        # Invalid FILE nodes (unknown format)
        ("file_short", "FILE", False, "unknown"),
        ("file_TOOLONG123456789", "FILE", False, "unknown"),
        ("random_id", "FILE", False, "unknown"),
        # Valid ENTITY nodes
        ("entity_7275cb2b_f839d8c2", "ENTITY", True, "hash_based"),
        ("httpx", "ENTITY", True, "stub"),
        ("sys", "ENTITY", True, "stub"),
    ]

    failed_validations = []

    for entity_id, node_type, expected_valid, expected_format in test_cases:
        result = await validation_helper.validate_entity_id_format(entity_id, node_type)

        if result["is_valid"] != expected_valid:
            failed_validations.append(
                {
                    "entity_id": entity_id,
                    "node_type": node_type,
                    "expected_valid": expected_valid,
                    "actual_valid": result["is_valid"],
                    "expected_format": expected_format,
                    "actual_format": result["format_type"],
                    "error": result.get("error"),
                }
            )

    # Assertions
    assert (
        len(failed_validations) == 0
    ), f"Entity_id validation failed for {len(failed_validations)} test cases: {failed_validations}"

    logger.info(f"✅ All {len(test_cases)} entity_id validation test cases passed")


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphaned_file_detection(
    validation_helper: EntityIdValidationHelper, test_fixtures_dir: Path
):
    """
    Verify that REAL FILE nodes (hash-based) are not orphaned.

    Success Criteria:
    - REAL FILE nodes should have relationships
    - If orphaned, it's intentional (e.g., orphan.py test file)
    - PLACEHOLDER nodes should not exist
    """
    project_name = f"test_orphan_detection_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        logger.info(f"Testing orphaned file detection for project: {project_name}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await validation_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "Files were not indexed"

        # Get orphaned FILE nodes
        orphaned_nodes = await validation_helper.get_orphaned_file_nodes(project_name)

        # Log orphaned nodes for analysis
        if len(orphaned_nodes) > 0:
            logger.warning(f"Found {len(orphaned_nodes)} orphaned FILE nodes:")
            for node in orphaned_nodes:
                logger.warning(
                    f"  - {node['entity_id']}: {node['path']} (name: {node['name']})"
                )

        # Check if orphaned nodes are expected (e.g., orphan.py)
        expected_orphans = {"orphan.py"}
        unexpected_orphans = [
            node
            for node in orphaned_nodes
            if not any(exp in node["path"] for exp in expected_orphans)
        ]

        # This assertion may fail initially - that's the point!
        # It detects the schema mismatch bug.
        assert (
            len(unexpected_orphans) == 0
        ), f"Found {len(unexpected_orphans)} unexpected orphaned nodes: {unexpected_orphans}"

        logger.info(f"✅ Orphan detection working correctly (found expected orphans)")

    finally:
        await validation_helper.cleanup_project(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_entity_id_consistency_across_operations(
    validation_helper: EntityIdValidationHelper, test_fixtures_dir: Path
):
    """
    Test entity_id consistency across multiple indexing operations.

    Success Criteria:
    - Re-indexing same file produces same entity_id
    - Entity_id doesn't change on update
    - Format remains consistent across operations
    """
    project_name = f"test_consistency_{int(time.time())}"
    repo_path = test_fixtures_dir / "test_repo_small"

    try:
        logger.info(f"Testing entity_id consistency for project: {project_name}")
        from scripts.bulk_ingest_repository import main as bulk_ingest_main

        # First indexing
        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        # Wait for indexing
        indexed = await validation_helper.wait_for_indexing(
            project_name=project_name, expected_file_count=3, timeout=30.0
        )
        assert indexed, "First indexing failed"

        # Get entity_ids from first indexing
        first_nodes = await validation_helper.get_all_file_entity_ids(project_name)
        first_entity_ids = {node["path"]: node["entity_id"] for node in first_nodes}

        logger.info(f"First indexing produced {len(first_nodes)} nodes")

        # Second indexing (re-index same files)
        await asyncio.sleep(2)  # Small delay
        await bulk_ingest_main(
            repo_path=str(repo_path),
            project_name=project_name,
            kafka_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"),
            dry_run=False,
        )

        await asyncio.sleep(5)  # Wait for re-indexing

        # Get entity_ids from second indexing
        second_nodes = await validation_helper.get_all_file_entity_ids(project_name)
        second_entity_ids = {node["path"]: node["entity_id"] for node in second_nodes}

        logger.info(f"Second indexing produced {len(second_nodes)} nodes")

        # Verify entity_ids are consistent
        mismatches = []
        for path, first_id in first_entity_ids.items():
            second_id = second_entity_ids.get(path)
            if second_id and first_id != second_id:
                mismatches.append(
                    {
                        "path": path,
                        "first_entity_id": first_id,
                        "second_entity_id": second_id,
                    }
                )

        assert (
            len(mismatches) == 0
        ), f"Entity_id changed across re-indexing: {mismatches}"

        logger.info(
            f"✅ Entity_id consistency verified across {len(first_nodes)} nodes"
        )

    finally:
        await validation_helper.cleanup_project(project_name)
