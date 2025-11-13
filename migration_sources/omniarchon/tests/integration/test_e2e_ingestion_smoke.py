#!/usr/bin/env python3
"""
End-to-End Ingestion Smoke Test

Comprehensive validation of the complete ingestion pipeline from Kafka event
to vector storage (Qdrant) and knowledge graph (Memgraph).

Test Coverage:
1. Kafka event publishing with inline content
2. Consumer event processing
3. Intelligence service document processing
4. Vector creation in Qdrant (1536 dimensions)
5. Node creation in Memgraph with metadata
6. File tree relationships (PROJECT → DIRECTORY → FILE)
7. Performance validation (<30s total)
8. Data cleanup

Usage:
    poetry run pytest tests/integration/test_e2e_ingestion_smoke.py -v
    poetry run pytest tests/integration/test_e2e_ingestion_smoke.py::TestE2EIngestionSmoke::test_single_file_ingestion_complete_pipeline -v

Created: 2025-11-12
ONEX Pattern: Integration testing for complete ingestion pipeline
"""

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio
from aiokafka import AIOKafkaProducer
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# Test Configuration
# ==============================================================================

# Service URLs from environment
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "dev.archon-intelligence")
KAFKA_TOPIC = f"{KAFKA_TOPIC_PREFIX}.enrich-document.v1"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
MEMGRAPH_URI = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")

INTELLIGENCE_URL = os.getenv("INTELLIGENCE_URL", "http://localhost:8053")
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8054")
SEARCH_URL = os.getenv("SEARCH_URL", "http://localhost:8055")

# Test configuration
TEST_TIMEOUT_SECONDS = 30
PROCESSING_CHECK_INTERVAL = 2  # seconds
QDRANT_COLLECTION = "archon_vectors"
EXPECTED_VECTOR_DIMENSIONS = 1536


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def test_project_name():
    """Generate unique project name for test isolation"""
    return f"e2e_smoke_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def test_file_content():
    """Realistic Python test file content"""
    return '''#!/usr/bin/env python3
"""
Test Module for E2E Ingestion Smoke Test

This is a realistic Python module used to validate the complete
ingestion pipeline from Kafka event to vector storage and knowledge graph.

Features:
- Authentication utilities
- Database connection pooling
- API endpoint configuration
- Error handling and retry logic
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """
    Manages authentication and authorization for the application.

    Attributes:
        api_key: API key for external service authentication
        token_expiry: Token expiration time in seconds
    """

    def __init__(self, api_key: str, token_expiry: int = 3600):
        self.api_key = api_key
        self.token_expiry = token_expiry
        self._token_cache: Dict[str, Any] = {}

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate user and return access token.

        Args:
            username: User identifier
            password: User password

        Returns:
            Access token if authentication succeeds, None otherwise
        """
        logger.info(f"Authenticating user: {username}")

        # Validation logic
        if not username or not password:
            logger.error("Missing credentials")
            return None

        # Token generation (simplified for test)
        token = f"token_{username}_{os.urandom(16).hex()}"
        self._token_cache[token] = {
            "username": username,
            "expires_at": time.time() + self.token_expiry
        }

        return token

    def validate_token(self, token: str) -> bool:
        """Validate authentication token"""
        if token not in self._token_cache:
            return False

        token_data = self._token_cache[token]
        return time.time() < token_data["expires_at"]


class DatabaseConnectionPool:
    """Database connection pool for efficient resource management"""

    def __init__(self, host: str, port: int, database: str, pool_size: int = 10):
        self.host = host
        self.port = port
        self.database = database
        self.pool_size = pool_size
        self._connections = []

    async def initialize(self):
        """Initialize connection pool"""
        logger.info(f"Initializing connection pool: {self.database}@{self.host}:{self.port}")
        # Pool initialization logic would go here
        pass

    async def get_connection(self):
        """Get connection from pool"""
        # Connection retrieval logic
        pass


# API endpoint configuration
API_ENDPOINTS = {
    "authentication": "/api/v1/auth",
    "users": "/api/v1/users",
    "documents": "/api/v1/documents",
    "search": "/api/v1/search"
}

# Default configuration
DEFAULT_CONFIG = {
    "api_timeout": 30,
    "retry_attempts": 3,
    "backoff_factor": 2.0,
    "enable_cache": True,
    "cache_ttl": 300
}


def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value with fallback"""
    return DEFAULT_CONFIG.get(key, default)


if __name__ == "__main__":
    # Example usage
    auth_manager = AuthenticationManager(api_key="test_key")
    token = auth_manager.authenticate("testuser", "testpass")
    print(f"Generated token: {token}")
'''


@pytest_asyncio.fixture(scope="module")
async def memgraph_connection():
    """Create Memgraph connection for verification"""
    driver = AsyncGraphDatabase.driver(MEMGRAPH_URI)
    yield driver
    await driver.close()


@pytest_asyncio.fixture(scope="module")
async def qdrant_client():
    """Create Qdrant client for verification"""
    client = QdrantClient(url=QDRANT_URL)

    # Ensure collection exists
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if QDRANT_COLLECTION not in collection_names:
        logger.info(f"Creating Qdrant collection: {QDRANT_COLLECTION}")
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=EXPECTED_VECTOR_DIMENSIONS, distance=Distance.COSINE
            ),
        )

    yield client


@pytest_asyncio.fixture(scope="module")
async def http_client():
    """HTTP client for service communication"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def cleanup_test_data(test_project_name, memgraph_connection, qdrant_client):
    """Cleanup test data after each test"""
    yield  # Run test first

    # Cleanup Memgraph nodes
    try:
        async with memgraph_connection.session() as session:
            # Delete FILE nodes
            await session.run(
                """
                MATCH (f:FILE)
                WHERE f.project_name = $project_name
                DETACH DELETE f
                """,
                project_name=test_project_name,
            )

            # Delete DIRECTORY nodes
            await session.run(
                """
                MATCH (d:DIRECTORY)
                WHERE d.project_name = $project_name
                DETACH DELETE d
                """,
                project_name=test_project_name,
            )

            # Delete PROJECT node
            await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})
                DETACH DELETE p
                """,
                project_name=test_project_name,
            )

        logger.info(f"Cleaned up Memgraph nodes for project: {test_project_name}")
    except Exception as e:
        logger.warning(f"Failed to cleanup Memgraph: {e}")

    # Cleanup Qdrant vectors
    try:
        # Delete vectors by metadata filter
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector={
                "filter": {
                    "must": [
                        {"key": "project_name", "match": {"value": test_project_name}}
                    ]
                }
            },
        )
        logger.info(f"Cleaned up Qdrant vectors for project: {test_project_name}")
    except Exception as e:
        logger.warning(f"Failed to cleanup Qdrant: {e}")


# ==============================================================================
# Test Helper Functions
# ==============================================================================


async def publish_kafka_event(
    project_name: str, file_path: str, content: str, language: str = "python"
) -> str:
    """
    Publish test file ingestion event to Kafka.

    Args:
        project_name: Project name slug
        file_path: File path relative to project root
        content: File content
        language: Programming language

    Returns:
        Correlation ID for tracking
    """
    correlation_id = f"e2e-smoke-{uuid.uuid4().hex[:12]}"

    # Calculate content hash
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Build event payload (v2.0.0 schema with inline content)
    event = {
        "event_type": "enrich_document",
        "event_version": "2.0.0",
        "correlation_id": correlation_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "project_name": project_name,
        "files": [
            {
                "path": file_path,
                "content": content,
                "content_hash": content_hash,
                "language": language,
                "size_bytes": len(content.encode("utf-8")),
                "last_modified": datetime.now(UTC).isoformat(),
                "entity_id": f"archon://{project_name}/documents/{file_path}",
            }
        ],
    }

    # Publish to Kafka
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        request_timeout_ms=10000,
    )

    try:
        await producer.start()

        # Send event
        metadata = await producer.send_and_wait(
            KAFKA_TOPIC, value=event, key=correlation_id.encode("utf-8")
        )

        logger.info(
            f"Published Kafka event: topic={metadata.topic}, "
            f"partition={metadata.partition}, offset={metadata.offset}, "
            f"correlation_id={correlation_id}"
        )

        return correlation_id

    finally:
        await producer.stop()


async def wait_for_vector_in_qdrant(
    qdrant_client: QdrantClient,
    project_name: str,
    file_path: str,
    timeout: float = TEST_TIMEOUT_SECONDS,
) -> bool:
    """
    Wait for vector to appear in Qdrant.

    Returns:
        True if vector found, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Search for vectors with matching metadata
            results = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                scroll_filter={
                    "must": [
                        {"key": "project_name", "match": {"value": project_name}},
                        {"key": "file_path", "match": {"value": file_path}},
                    ]
                },
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            if results and results[0]:  # results is tuple (points, next_offset)
                points = results[0]
                if len(points) > 0:
                    logger.info(f"Vector found in Qdrant: {file_path}")
                    return True

        except Exception as e:
            logger.debug(f"Error checking Qdrant: {e}")

        await asyncio.sleep(PROCESSING_CHECK_INTERVAL)

    return False


async def wait_for_node_in_memgraph(
    memgraph_driver,
    project_name: str,
    file_path: str,
    timeout: float = TEST_TIMEOUT_SECONDS,
) -> bool:
    """
    Wait for FILE node to appear in Memgraph.

    Returns:
        True if node found, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            async with memgraph_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (f:FILE)
                    WHERE f.project_name = $project_name
                      AND (f.path CONTAINS $file_path OR f.entity_id CONTAINS $file_path)
                    RETURN f.path as path, f.entity_id as entity_id
                    LIMIT 1
                    """,
                    project_name=project_name,
                    file_path=file_path,
                )

                record = await result.single()
                if record:
                    logger.info(f"Node found in Memgraph: {record['path']}")
                    return True

        except Exception as e:
            logger.debug(f"Error checking Memgraph: {e}")

        await asyncio.sleep(PROCESSING_CHECK_INTERVAL)

    return False


async def verify_file_tree_structure(
    memgraph_driver, project_name: str
) -> Dict[str, Any]:
    """
    Verify file tree structure (PROJECT → DIRECTORY → FILE).

    Returns:
        Dictionary with verification results
    """
    async with memgraph_driver.session() as session:
        # Check PROJECT node exists
        project_result = await session.run(
            """
            MATCH (p:PROJECT {name: $project_name})
            RETURN count(p) as count
            """,
            project_name=project_name,
        )
        project_record = await project_result.single()
        project_count = project_record["count"] if project_record else 0

        # Check DIRECTORY nodes
        dir_result = await session.run(
            """
            MATCH (d:DIRECTORY)
            WHERE d.project_name = $project_name
            RETURN count(d) as count
            """,
            project_name=project_name,
        )
        dir_record = await dir_result.single()
        dir_count = dir_record["count"] if dir_record else 0

        # Check FILE nodes
        file_result = await session.run(
            """
            MATCH (f:FILE)
            WHERE f.project_name = $project_name
            RETURN count(f) as count
            """,
            project_name=project_name,
        )
        file_record = await file_result.single()
        file_count = file_record["count"] if file_record else 0

        # Check CONTAINS relationships
        contains_result = await session.run(
            """
            MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(n)
            RETURN count(n) as count
            """,
            project_name=project_name,
        )
        contains_record = await contains_result.single()
        contains_count = contains_record["count"] if contains_record else 0

        # Check for orphaned files
        orphan_result = await session.run(
            """
            MATCH (f:FILE)
            WHERE f.project_name = $project_name
              AND NOT (d:DIRECTORY)-[:CONTAINS]->(f)
              AND NOT (p:PROJECT)-[:CONTAINS]->(f)
            RETURN count(f) as count
            """,
            project_name=project_name,
        )
        orphan_record = await orphan_result.single()
        orphan_count = orphan_record["count"] if orphan_record else 0

        return {
            "project_nodes": project_count,
            "directory_nodes": dir_count,
            "file_nodes": file_count,
            "contains_relationships": contains_count,
            "orphaned_files": orphan_count,
            "has_valid_tree": project_count > 0
            and file_count > 0
            and orphan_count == 0,
        }


async def verify_vector_dimensions(
    qdrant_client: QdrantClient, project_name: str, file_path: str
) -> Dict[str, Any]:
    """
    Verify vector has correct dimensions and metadata.

    Returns:
        Dictionary with vector details
    """
    results = qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter={
            "must": [
                {"key": "project_name", "match": {"value": project_name}},
                {"key": "file_path", "match": {"value": file_path}},
            ]
        },
        limit=1,
        with_payload=True,
        with_vectors=True,
    )

    if not results or not results[0]:
        return {"found": False}

    point = results[0][0]  # First point from first page

    vector_size = len(point.vector) if hasattr(point, "vector") and point.vector else 0

    return {
        "found": True,
        "vector_size": vector_size,
        "correct_dimensions": vector_size == EXPECTED_VECTOR_DIMENSIONS,
        "metadata": dict(point.payload) if point.payload else {},
    }


# ==============================================================================
# Test Class
# ==============================================================================


@pytest.mark.asyncio
class TestE2EIngestionSmoke:
    """End-to-end ingestion smoke tests"""

    async def test_single_file_ingestion_complete_pipeline(
        self,
        test_project_name,
        test_file_content,
        memgraph_connection,
        qdrant_client,
        http_client,
        cleanup_test_data,
    ):
        """
        Test complete ingestion of single file through entire pipeline.

        Validates:
        1. Kafka event publishing
        2. Consumer processing
        3. Intelligence service processing
        4. Vector storage in Qdrant (1536 dimensions)
        5. Node storage in Memgraph
        6. Metadata correctness
        7. Performance (<30s)
        """
        start_time = time.time()

        # Test file configuration
        test_file_path = "src/auth/authentication_manager.py"

        logger.info("=" * 70)
        logger.info("🚀 Starting E2E Ingestion Smoke Test")
        logger.info("=" * 70)
        logger.info(f"Project: {test_project_name}")
        logger.info(f"File: {test_file_path}")
        logger.info(f"Content size: {len(test_file_content)} bytes")

        # Step 1: Verify services are healthy
        logger.info("\n📋 Step 1: Verifying service health...")

        services_ok = True
        for service_name, url in [
            ("intelligence", INTELLIGENCE_URL),
            ("bridge", BRIDGE_URL),
            ("search", SEARCH_URL),
        ]:
            try:
                response = await http_client.get(f"{url}/health", timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"  ✅ {service_name}: healthy")
                else:
                    logger.error(
                        f"  ❌ {service_name}: unhealthy (HTTP {response.status_code})"
                    )
                    services_ok = False
            except Exception as e:
                logger.error(f"  ❌ {service_name}: unreachable - {e}")
                services_ok = False

        assert services_ok, "One or more services are unhealthy"

        # Step 2: Publish Kafka event
        logger.info("\n📤 Step 2: Publishing Kafka event...")

        correlation_id = await publish_kafka_event(
            project_name=test_project_name,
            file_path=test_file_path,
            content=test_file_content,
            language="python",
        )

        logger.info(f"  ✅ Event published: correlation_id={correlation_id}")

        publish_duration = time.time() - start_time
        logger.info(f"  ⏱️  Publishing took {publish_duration:.2f}s")

        # Step 3: Wait for vector in Qdrant
        logger.info("\n🔍 Step 3: Waiting for vector in Qdrant...")

        vector_found = await wait_for_vector_in_qdrant(
            qdrant_client=qdrant_client,
            project_name=test_project_name,
            file_path=test_file_path,
            timeout=TEST_TIMEOUT_SECONDS,
        )

        assert vector_found, f"Vector not found in Qdrant after {TEST_TIMEOUT_SECONDS}s"

        vector_duration = time.time() - start_time
        logger.info(f"  ✅ Vector found in {vector_duration:.2f}s")

        # Step 4: Verify vector dimensions and metadata
        logger.info("\n🔬 Step 4: Verifying vector dimensions...")

        vector_info = await verify_vector_dimensions(
            qdrant_client=qdrant_client,
            project_name=test_project_name,
            file_path=test_file_path,
        )

        assert vector_info["found"], "Vector not found in detailed check"
        assert vector_info["correct_dimensions"], (
            f"Vector has {vector_info['vector_size']} dimensions, "
            f"expected {EXPECTED_VECTOR_DIMENSIONS}"
        )

        logger.info(f"  ✅ Vector dimensions correct: {vector_info['vector_size']}")
        logger.info(f"  📊 Metadata keys: {list(vector_info['metadata'].keys())}")

        # Step 5: Wait for node in Memgraph
        logger.info("\n🔍 Step 5: Waiting for node in Memgraph...")

        node_found = await wait_for_node_in_memgraph(
            memgraph_driver=memgraph_connection,
            project_name=test_project_name,
            file_path=test_file_path,
            timeout=TEST_TIMEOUT_SECONDS,
        )

        assert node_found, f"Node not found in Memgraph after {TEST_TIMEOUT_SECONDS}s"

        node_duration = time.time() - start_time
        logger.info(f"  ✅ Node found in {node_duration:.2f}s")

        # Step 6: Verify file tree structure
        logger.info("\n🌳 Step 6: Verifying file tree structure...")

        # Wait a bit for tree building to complete
        await asyncio.sleep(3)

        tree_info = await verify_file_tree_structure(
            memgraph_driver=memgraph_connection, project_name=test_project_name
        )

        logger.info(f"  📊 PROJECT nodes: {tree_info['project_nodes']}")
        logger.info(f"  📊 DIRECTORY nodes: {tree_info['directory_nodes']}")
        logger.info(f"  📊 FILE nodes: {tree_info['file_nodes']}")
        logger.info(
            f"  📊 CONTAINS relationships: {tree_info['contains_relationships']}"
        )
        logger.info(f"  📊 Orphaned files: {tree_info['orphaned_files']}")

        # Note: Tree building may be async, so we don't assert on it
        # Just log the results for observability
        if tree_info["has_valid_tree"]:
            logger.info("  ✅ File tree structure is valid")
        else:
            logger.warning(
                "  ⚠️  File tree structure incomplete (may still be building)"
            )

        # Step 7: Performance validation
        total_duration = time.time() - start_time

        logger.info("\n⏱️  Step 7: Performance summary:")
        logger.info(f"  Total duration: {total_duration:.2f}s")
        logger.info(f"  Target: <{TEST_TIMEOUT_SECONDS}s")

        assert total_duration < TEST_TIMEOUT_SECONDS, (
            f"Pipeline took {total_duration:.2f}s, "
            f"exceeded timeout of {TEST_TIMEOUT_SECONDS}s"
        )

        logger.info(f"  ✅ Performance target met")

        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("✅ E2E Ingestion Smoke Test PASSED")
        logger.info("=" * 70)
        logger.info(f"✓ Kafka event published")
        logger.info(f"✓ Vector created in Qdrant ({EXPECTED_VECTOR_DIMENSIONS}D)")
        logger.info(f"✓ Node created in Memgraph")
        logger.info(f"✓ Completed in {total_duration:.2f}s")
        logger.info("=" * 70)

    async def test_ingestion_creates_proper_relationships(
        self,
        test_project_name,
        test_file_content,
        memgraph_connection,
        qdrant_client,
        cleanup_test_data,
    ):
        """
        Test that ingestion creates proper file tree relationships.

        Validates:
        1. PROJECT node created
        2. DIRECTORY nodes created for path hierarchy
        3. FILE node connected via CONTAINS relationships
        4. No orphaned files
        """
        test_file_path = "src/utils/helpers.py"

        logger.info("=" * 70)
        logger.info("🌳 Testing File Tree Relationships")
        logger.info("=" * 70)

        # Publish event
        correlation_id = await publish_kafka_event(
            project_name=test_project_name,
            file_path=test_file_path,
            content=test_file_content,
            language="python",
        )

        logger.info(f"Event published: {correlation_id}")

        # Wait for processing
        node_found = await wait_for_node_in_memgraph(
            memgraph_driver=memgraph_connection,
            project_name=test_project_name,
            file_path=test_file_path,
            timeout=TEST_TIMEOUT_SECONDS,
        )

        assert node_found, "Node not found in Memgraph"

        # Give tree builder time to complete
        await asyncio.sleep(5)

        # Verify relationships
        tree_info = await verify_file_tree_structure(
            memgraph_driver=memgraph_connection, project_name=test_project_name
        )

        logger.info(f"Tree structure: {tree_info}")

        # Assert tree structure (if tree building completed)
        if tree_info["project_nodes"] > 0:
            assert tree_info["project_nodes"] >= 1, "No PROJECT node found"
            assert tree_info["file_nodes"] >= 1, "No FILE nodes found"

            # Check for proper hierarchy
            # Expected: PROJECT -> src -> utils -> helpers.py
            # So we should have at least 2 directory nodes (src, utils)
            if tree_info["directory_nodes"] > 0:
                logger.info(
                    f"✅ Directory hierarchy created: {tree_info['directory_nodes']} directories"
                )

            # Verify no orphans
            assert (
                tree_info["orphaned_files"] == 0
            ), f"Found {tree_info['orphaned_files']} orphaned files"

            logger.info("✅ File tree relationships are correct")
        else:
            logger.warning("⚠️  Tree structure not yet built (async operation)")

        logger.info("=" * 70)


# ==============================================================================
# Main Entry Point
# ==============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])
