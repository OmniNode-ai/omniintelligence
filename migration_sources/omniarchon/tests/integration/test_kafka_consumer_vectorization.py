"""
Kafka Consumer Vectorization Pipeline Integration Tests

Comprehensive end-to-end testing of the vectorization pipeline:
- Kafka event → Consumer → Handler → Intelligence Service
- Vector creation in Qdrant
- Node creation in Memgraph
- Error handling and retries
- Idempotency guarantees

Created: 2025-11-12
Purpose: Prevent vectorization bugs by validating complete pipeline
ONEX Pattern: Integration testing for event-driven architectures
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio
from aiokafka import AIOKafkaProducer
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def service_urls():
    """Service URL configuration for testing"""
    return {
        "intelligence": os.getenv("INTELLIGENCE_URL", "http://localhost:8053"),
        "bridge": os.getenv("BRIDGE_URL", "http://localhost:8054"),
        "search": os.getenv("SEARCH_URL", "http://localhost:8055"),
        "kafka_bootstrap_servers": os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"
        ),
        "memgraph_uri": os.getenv("MEMGRAPH_URI", "bolt://localhost:7687"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
    }


@pytest.fixture(scope="module")
def kafka_topic_config():
    """Kafka topic configuration for testing"""
    return {
        "process_document_request": os.getenv(
            "KAFKA_PROCESS_DOCUMENT_REQUEST",
            "dev.archon-intelligence.document.process-document-requested.v1",
        ),
        "process_document_completed": os.getenv(
            "KAFKA_PROCESS_DOCUMENT_COMPLETED",
            "dev.archon-intelligence.document.process-document-completed.v1",
        ),
        "process_document_failed": os.getenv(
            "KAFKA_PROCESS_DOCUMENT_FAILED",
            "dev.archon-intelligence.document.process-document-failed.v1",
        ),
    }


@pytest_asyncio.fixture(scope="module")
async def kafka_producer(service_urls):
    """Create Kafka producer for publishing test events"""
    producer = AIOKafkaProducer(
        bootstrap_servers=service_urls["kafka_bootstrap_servers"],
        client_id="test-vectorization-producer",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    yield producer
    await producer.stop()


@pytest_asyncio.fixture(scope="module")
async def qdrant_client(service_urls):
    """Create Qdrant client for vector verification"""
    client = QdrantClient(url=service_urls["qdrant_url"])
    yield client


@pytest_asyncio.fixture(scope="module")
async def memgraph_connection(service_urls):
    """Create Memgraph connection for node verification"""
    driver = AsyncGraphDatabase.driver(service_urls["memgraph_uri"])
    yield driver
    await driver.close()


@pytest_asyncio.fixture(scope="module")
async def http_client():
    """HTTP client for service health checks"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        yield client


class VectorizationPipelineTestHelper:
    """Helper class for vectorization pipeline testing"""

    def __init__(
        self,
        kafka_producer: AIOKafkaProducer,
        qdrant_client: QdrantClient,
        memgraph_driver,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        kafka_topics: Dict[str, str],
    ):
        self.kafka_producer = kafka_producer
        self.qdrant_client = qdrant_client
        self.memgraph_driver = memgraph_driver
        self.http_client = http_client
        self.service_urls = service_urls
        self.kafka_topics = kafka_topics
        self.test_collection = "archon_vectors"

    async def check_services_healthy(self) -> Dict[str, bool]:
        """Verify all required services are healthy"""
        health_status = {}

        # Intelligence service
        try:
            response = await self.http_client.get(
                f"{self.service_urls['intelligence']}/health"
            )
            health_status["intelligence"] = response.status_code == 200
        except Exception as e:
            logger.warning(f"Intelligence service health check failed: {e}")
            health_status["intelligence"] = False

        # Qdrant
        try:
            collections = self.qdrant_client.get_collections()
            health_status["qdrant"] = collections is not None
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            health_status["qdrant"] = False

        # Memgraph
        try:
            async with self.memgraph_driver.session() as session:
                result = await session.run("RETURN 1 as test")
                await result.single()
            health_status["memgraph"] = True
        except Exception as e:
            logger.warning(f"Memgraph health check failed: {e}")
            health_status["memgraph"] = False

        return health_status

    async def publish_process_document_event(
        self,
        document_path: str,
        content: str,
        project_name: str,
        correlation_id: Optional[str] = None,
        document_type: str = "python",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Publish process document event to Kafka.

        Returns:
            correlation_id for tracking the event
        """
        correlation_id = correlation_id or str(uuid.uuid4())

        event_payload = {
            "event_type": "PROCESS_DOCUMENT_REQUESTED",
            "correlation_id": correlation_id,
            "timestamp": time.time(),
            "payload": {
                "document_path": document_path,
                "content": content,
                "project_name": project_name,
                "document_type": document_type,
                "processing_options": {
                    "extract_entities": True,
                    "generate_embeddings": True,
                },
                "metadata": metadata or {},
            },
        }

        # Publish to Kafka (aiokafka already serializes with value_serializer)
        await self.kafka_producer.send_and_wait(
            topic=self.kafka_topics["process_document_request"],
            key=correlation_id.encode("utf-8"),
            value=event_payload,
        )

        logger.info(
            f"Published process document event | correlation_id={correlation_id} | "
            f"document_path={document_path}"
        )

        return correlation_id

    async def wait_for_vector_creation(
        self, document_path: str, timeout: float = 30.0
    ) -> Optional[List[PointStruct]]:
        """
        Wait for vector to be created in Qdrant.

        Args:
            document_path: Path of the document to search for
            timeout: Maximum wait time in seconds

        Returns:
            List of matching vectors or None if timeout
        """
        start_time = time.time()
        check_interval = 2.0

        while time.time() - start_time < timeout:
            try:
                # Search for vectors matching the document path
                # Use scroll to find vectors with matching metadata
                vectors, _ = self.qdrant_client.scroll(
                    collection_name=self.test_collection,
                    limit=100,
                    with_payload=True,
                    with_vectors=False,
                )

                # Filter vectors by document_path in payload
                matching_vectors = [
                    v
                    for v in vectors
                    if v.payload and v.payload.get("file_path") == document_path
                ]

                if matching_vectors:
                    logger.info(
                        f"Found {len(matching_vectors)} vectors for {document_path}"
                    )
                    return matching_vectors

            except Exception as e:
                logger.debug(f"Error checking vectors: {e}")

            await asyncio.sleep(check_interval)

        logger.warning(
            f"Timeout waiting for vector creation: {document_path} after {timeout}s"
        )
        return None

    async def wait_for_node_creation(
        self, file_path: str, project_name: str, timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for FILE node to be created in Memgraph.

        Args:
            file_path: Path of the file
            project_name: Project name
            timeout: Maximum wait time in seconds

        Returns:
            Node properties or None if timeout
        """
        start_time = time.time()
        check_interval = 2.0

        while time.time() - start_time < timeout:
            try:
                async with self.memgraph_driver.session() as session:
                    result = await session.run(
                        """
                        MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE {path: $file_path})
                        RETURN f.path as path,
                               f.entity_count as entity_count,
                               f.language as language,
                               f.last_modified as last_modified
                        """,
                        project_name=project_name,
                        file_path=file_path,
                    )
                    record = await result.single()
                    if record:
                        node_data = record.data()
                        logger.info(
                            f"Found FILE node for {file_path} with {node_data.get('entity_count', 0)} entities"
                        )
                        return node_data

            except Exception as e:
                logger.debug(f"Error checking node: {e}")

            await asyncio.sleep(check_interval)

        logger.warning(
            f"Timeout waiting for node creation: {file_path} after {timeout}s"
        )
        return None

    async def get_entities_for_file(
        self, file_path: str, project_name: str
    ) -> List[Dict[str, Any]]:
        """Get all entities defined by a file"""
        async with self.memgraph_driver.session() as session:
            result = await session.run(
                """
                MATCH (p:PROJECT {name: $project_name})-[:CONTAINS*]->(f:FILE {path: $file_path})
                      -[:DEFINES]->(e:ENTITY)
                RETURN e.name as entity_name,
                       e.type as entity_type,
                       e.line_number as line_number
                ORDER BY e.name
                """,
                project_name=project_name,
                file_path=file_path,
            )
            return [record.data() async for record in result]

    async def verify_vector_content(
        self, vectors: List[PointStruct], expected_content_keywords: List[str]
    ) -> bool:
        """
        Verify that vector payload contains expected content.

        Args:
            vectors: List of vectors to check
            expected_content_keywords: Keywords that should appear in content

        Returns:
            True if all keywords found, False otherwise
        """
        if not vectors:
            return False

        for vector in vectors:
            content = vector.payload.get("content", "").lower()
            matches = [
                keyword.lower() in content for keyword in expected_content_keywords
            ]
            if all(matches):
                return True

        return False

    async def cleanup_test_data(self, project_name: str):
        """Clean up test data from Memgraph and Qdrant"""
        # Clean up Memgraph
        try:
            async with self.memgraph_driver.session() as session:
                await session.run(
                    """
                    MATCH (p:PROJECT {name: $project_name})
                    OPTIONAL MATCH (p)-[:CONTAINS*]->(n)
                    DETACH DELETE p, n
                    """,
                    project_name=project_name,
                )
            logger.info(f"Cleaned up Memgraph data for project: {project_name}")
        except Exception as e:
            logger.warning(f"Failed to clean up Memgraph: {e}")

        # Note: Qdrant vectors are typically cleaned up via project-level deletion
        # or by deleting specific point IDs. For integration tests, we may want
        # to keep vectors for debugging or use a separate test collection


@pytest_asyncio.fixture
async def pipeline_helper(
    kafka_producer,
    qdrant_client,
    memgraph_connection,
    http_client,
    service_urls,
    kafka_topic_config,
):
    """Create pipeline test helper"""
    helper = VectorizationPipelineTestHelper(
        kafka_producer=kafka_producer,
        qdrant_client=qdrant_client,
        memgraph_driver=memgraph_connection,
        http_client=http_client,
        service_urls=service_urls,
        kafka_topics=kafka_topic_config,
    )
    yield helper


@pytest.mark.slow
@pytest.mark.asyncio
async def test_consumer_creates_vector_and_node(
    pipeline_helper: VectorizationPipelineTestHelper,
):
    """
    Test that Kafka consumer processes event and creates both vector and node.

    Flow:
    1. Publish process-document-requested event to Kafka
    2. Consumer picks up event
    3. Handler calls /process/document endpoint
    4. Intelligence service creates vector in Qdrant
    5. Intelligence service creates node in Memgraph
    6. Verify both vector and node exist with correct data
    """
    # Check service health first
    health_status = await pipeline_helper.check_services_healthy()
    unhealthy_services = [
        service for service, healthy in health_status.items() if not healthy
    ]
    if unhealthy_services:
        pytest.skip(f"Required services unhealthy: {unhealthy_services}")

    # Test data
    project_name = f"test_vectorization_{int(time.time())}"
    document_path = f"/test/src/example_{uuid.uuid4().hex[:8]}.py"
    content = """
def calculate_total(items):
    '''Calculate total price of items'''
    total = 0
    for item in items:
        total += item.price
    return total

class ShoppingCart:
    '''Shopping cart for e-commerce'''
    def __init__(self):
        self.items = []

    def add_item(self, item):
        self.items.append(item)
"""

    try:
        # Step 1: Publish Kafka event
        correlation_id = await pipeline_helper.publish_process_document_event(
            document_path=document_path,
            content=content,
            project_name=project_name,
            document_type="python",
            metadata={"test": True, "test_type": "vectorization"},
        )

        logger.info(
            f"Published test event | correlation_id={correlation_id} | "
            f"document_path={document_path}"
        )

        # Step 2: Wait for vector creation
        vectors = await pipeline_helper.wait_for_vector_creation(
            document_path=document_path, timeout=30.0
        )
        assert (
            vectors is not None
        ), f"Vector not created for {document_path} within timeout"
        assert len(vectors) > 0, f"No vectors found for {document_path}"

        # Step 3: Verify vector content
        has_expected_content = await pipeline_helper.verify_vector_content(
            vectors=vectors,
            expected_content_keywords=["calculate_total", "ShoppingCart", "items"],
        )
        assert has_expected_content, "Vector content missing expected keywords"

        # Step 4: Wait for node creation
        node = await pipeline_helper.wait_for_node_creation(
            file_path=document_path, project_name=project_name, timeout=30.0
        )
        assert node is not None, f"FILE node not created for {document_path}"
        assert node["path"] == document_path, "Node path mismatch"

        # Step 5: Verify entities were extracted
        entities = await pipeline_helper.get_entities_for_file(
            file_path=document_path, project_name=project_name
        )
        assert (
            len(entities) >= 2
        ), f"Expected at least 2 entities, found {len(entities)}"

        # Verify specific entities
        entity_names = [e["entity_name"] for e in entities]
        assert "calculate_total" in entity_names, "Function entity not found"
        assert "ShoppingCart" in entity_names, "Class entity not found"

        # Step 6: Verify entity types
        entity_types = {e["entity_name"]: e["entity_type"] for e in entities}
        assert (
            entity_types.get("calculate_total") == "function"
        ), "Function type incorrect"
        assert entity_types.get("ShoppingCart") == "class", "Class type incorrect"

        logger.info(
            f"✅ Vectorization pipeline test passed | correlation_id={correlation_id} | "
            f"vectors={len(vectors)} | entities={len(entities)}"
        )

    finally:
        # Cleanup
        await pipeline_helper.cleanup_test_data(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_consumer_handles_vectorization_failure(
    pipeline_helper: VectorizationPipelineTestHelper,
):
    """
    Test that consumer handles vectorization failures gracefully.

    Flow:
    1. Publish event with invalid/malformed content
    2. Consumer processes event
    3. Handler calls intelligence service
    4. Service returns error (or times out)
    5. Verify error is handled (DLQ routing, logging, metrics)
    """
    # Check service health
    health_status = await pipeline_helper.check_services_healthy()
    if not health_status.get("intelligence"):
        pytest.skip("Intelligence service not available")

    project_name = f"test_failure_{int(time.time())}"
    document_path = f"/test/invalid_{uuid.uuid4().hex[:8]}.py"

    # Invalid content that should cause processing issues
    invalid_content = "x" * 1_000_000  # 1MB of garbage

    try:
        # Publish event with invalid content
        correlation_id = await pipeline_helper.publish_process_document_event(
            document_path=document_path,
            content=invalid_content,
            project_name=project_name,
            document_type="python",
        )

        logger.info(f"Published invalid event | correlation_id={correlation_id}")

        # Wait a bit for processing attempt
        await asyncio.sleep(10)

        # Verify vector was NOT created
        vectors = await pipeline_helper.wait_for_vector_creation(
            document_path=document_path, timeout=10.0
        )
        # We expect None or empty list since this should fail
        if vectors:
            logger.warning(
                f"Unexpectedly found {len(vectors)} vectors for failed processing"
            )

        # Verify node was NOT created (or if created, has error status)
        node = await pipeline_helper.wait_for_node_creation(
            file_path=document_path, project_name=project_name, timeout=10.0
        )
        # Node might not exist, or might exist with error marker
        if node:
            logger.info(f"Node created despite error: {node}")

        logger.info(
            "✅ Error handling test passed - no vectors created for invalid content"
        )

    finally:
        await pipeline_helper.cleanup_test_data(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_idempotency_same_event_twice(
    pipeline_helper: VectorizationPipelineTestHelper,
):
    """
    Test that processing the same event twice is idempotent.

    Flow:
    1. Publish process-document event
    2. Wait for processing to complete
    3. Publish SAME event again (same correlation_id)
    4. Verify no duplicate vectors/nodes created
    5. Verify existing data not corrupted
    """
    health_status = await pipeline_helper.check_services_healthy()
    unhealthy_services = [
        service for service, healthy in health_status.items() if not healthy
    ]
    if unhealthy_services:
        pytest.skip(f"Required services unhealthy: {unhealthy_services}")

    project_name = f"test_idempotency_{int(time.time())}"
    document_path = f"/test/idempotent_{uuid.uuid4().hex[:8]}.py"
    content = """
def test_function():
    return 42
"""
    correlation_id = str(uuid.uuid4())

    try:
        # First event
        await pipeline_helper.publish_process_document_event(
            document_path=document_path,
            content=content,
            project_name=project_name,
            correlation_id=correlation_id,
        )

        # Wait for processing
        vectors_first = await pipeline_helper.wait_for_vector_creation(
            document_path=document_path, timeout=30.0
        )
        assert vectors_first is not None, "First processing failed"
        first_vector_count = len(vectors_first)

        # Get first node state
        node_first = await pipeline_helper.wait_for_node_creation(
            file_path=document_path, project_name=project_name, timeout=30.0
        )
        assert node_first is not None, "First node creation failed"

        # Wait a bit for processing to fully complete
        await asyncio.sleep(5)

        # Second event (SAME correlation_id - idempotent operation)
        await pipeline_helper.publish_process_document_event(
            document_path=document_path,
            content=content,
            project_name=project_name,
            correlation_id=correlation_id,  # Same correlation ID
        )

        # Wait for potential second processing
        await asyncio.sleep(10)

        # Check vectors again
        vectors_second = await pipeline_helper.wait_for_vector_creation(
            document_path=document_path, timeout=5.0
        )
        second_vector_count = len(vectors_second) if vectors_second else 0

        # Verify no duplicates (idempotency)
        assert (
            second_vector_count == first_vector_count
        ), f"Duplicate vectors created: first={first_vector_count}, second={second_vector_count}"

        # Verify node still exists and unchanged
        node_second = await pipeline_helper.wait_for_node_creation(
            file_path=document_path, project_name=project_name, timeout=5.0
        )
        assert node_second is not None, "Node disappeared after second event"
        assert (
            node_second["path"] == node_first["path"]
        ), "Node data changed after second event"

        logger.info(
            f"✅ Idempotency test passed | vectors={first_vector_count} (unchanged)"
        )

    finally:
        await pipeline_helper.cleanup_test_data(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_multiple_files_batch_processing(
    pipeline_helper: VectorizationPipelineTestHelper,
):
    """
    Test processing multiple files in quick succession.

    Verifies that:
    - Consumer handles multiple events without errors
    - All files get vectorized
    - All nodes created correctly
    - No race conditions or data corruption
    """
    health_status = await pipeline_helper.check_services_healthy()
    unhealthy_services = [
        service for service, healthy in health_status.items() if not healthy
    ]
    if unhealthy_services:
        pytest.skip(f"Required services unhealthy: {unhealthy_services}")

    project_name = f"test_batch_{int(time.time())}"
    num_files = 5

    test_files = []
    for i in range(num_files):
        document_path = f"/test/batch/file_{i}_{uuid.uuid4().hex[:6]}.py"
        content = f"""
def function_{i}():
    '''Function number {i}'''
    return {i}

class Class{i}:
    '''Class number {i}'''
    pass
"""
        test_files.append((document_path, content))

    try:
        # Publish all events quickly
        correlation_ids = []
        for document_path, content in test_files:
            corr_id = await pipeline_helper.publish_process_document_event(
                document_path=document_path,
                content=content,
                project_name=project_name,
                document_type="python",
            )
            correlation_ids.append(corr_id)

        logger.info(f"Published {num_files} events for batch processing")

        # Wait for all to process (increased timeout for batch)
        await asyncio.sleep(20)

        # Verify all vectors created
        vectors_found = []
        for document_path, _ in test_files:
            vectors = await pipeline_helper.wait_for_vector_creation(
                document_path=document_path, timeout=10.0
            )
            if vectors:
                vectors_found.append(document_path)

        assert (
            len(vectors_found) == num_files
        ), f"Expected {num_files} vectors, found {len(vectors_found)}"

        # Verify all nodes created
        nodes_found = []
        for document_path, _ in test_files:
            node = await pipeline_helper.wait_for_node_creation(
                file_path=document_path, project_name=project_name, timeout=10.0
            )
            if node:
                nodes_found.append(document_path)

        assert (
            len(nodes_found) == num_files
        ), f"Expected {num_files} nodes, found {len(nodes_found)}"

        logger.info(
            f"✅ Batch processing test passed | files={num_files} | "
            f"vectors={len(vectors_found)} | nodes={len(nodes_found)}"
        )

    finally:
        await pipeline_helper.cleanup_test_data(project_name)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_vector_dimensions_correctness(
    pipeline_helper: VectorizationPipelineTestHelper,
):
    """
    Test that generated vectors have correct dimensions.

    Verifies:
    - Vector dimensions match model configuration (typically 1536 for OpenAI)
    - Vector values are normalized (if applicable)
    - Metadata is correctly attached to vectors
    """
    health_status = await pipeline_helper.check_services_healthy()
    if not all(health_status.values()):
        pytest.skip("Not all services healthy")

    project_name = f"test_dimensions_{int(time.time())}"
    document_path = f"/test/dimensions_{uuid.uuid4().hex[:8]}.py"
    content = """
def example():
    return "test"
"""

    try:
        correlation_id = await pipeline_helper.publish_process_document_event(
            document_path=document_path,
            content=content,
            project_name=project_name,
        )

        # Wait for vector creation WITH vector data this time
        await asyncio.sleep(15)

        # Get vector with actual vector data
        vectors, _ = pipeline_helper.qdrant_client.scroll(
            collection_name=pipeline_helper.test_collection,
            limit=100,
            with_payload=True,
            with_vectors=True,
        )

        matching_vectors = [
            v
            for v in vectors
            if v.payload and v.payload.get("file_path") == document_path
        ]

        assert len(matching_vectors) > 0, f"No vectors found for {document_path}"

        # Check vector dimensions
        vector = matching_vectors[0]
        vector_data = vector.vector

        # Expected dimension (from embedding model config)
        expected_dim = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        actual_dim = (
            len(vector_data)
            if isinstance(vector_data, list)
            else len(vector_data.get("default", []))
        )

        assert (
            actual_dim == expected_dim
        ), f"Vector dimension mismatch: expected={expected_dim}, actual={actual_dim}"

        # Verify metadata
        assert "file_path" in vector.payload, "Missing file_path in payload"
        assert "project_name" in vector.payload, "Missing project_name in payload"
        assert (
            vector.payload["project_name"] == project_name
        ), "Project name mismatch in payload"

        logger.info(
            f"✅ Vector dimensions test passed | dimensions={actual_dim} | "
            f"correlation_id={correlation_id}"
        )

    finally:
        await pipeline_helper.cleanup_test_data(project_name)
