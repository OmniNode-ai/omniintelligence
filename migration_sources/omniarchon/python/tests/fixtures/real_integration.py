"""
Real Integration Test Fixtures

Provides fixtures for real service connections (Kafka, Qdrant, Memgraph) for integration testing.

These fixtures:
- Connect to real services running in Docker Compose
- Create isolated test data (separate topics, collections, graphs)
- Clean up test data after each test
- Include timeout protection
- Use test-specific ports to avoid conflicts

Usage:
    @pytest.mark.real_integration
    async def test_kafka_event_flow(kafka_producer, kafka_consumer):
        # Test with real Kafka connection
        pass

Run tests with:
    pytest --real-integration tests/real_integration/
"""

import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest
import pytest_asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Add project root to path for config imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))
from config.kafka_helper import KAFKA_HOST_SERVERS

# ============================================================================
# Configuration
# ============================================================================


@pytest.fixture(scope="session")
def real_integration_config() -> Dict[str, Any]:
    """
    Configuration for real integration tests.

    Uses test-specific ports from docker-compose.test.yml:
    - Kafka: config.kafka_helper (192.168.86.200:29092 via omninode-bridge-redpanda, external port)
    - Qdrant: localhost:6334 (test-qdrant)
    - Memgraph: localhost:7688 (test-memgraph)
    - PostgreSQL: localhost:5433 (test-postgres)
    - Valkey: localhost:6380 (test-valkey)
    """
    return {
        "kafka": {
            "bootstrap_servers": os.getenv(
                "TEST_KAFKA_BOOTSTRAP_SERVERS",
                KAFKA_HOST_SERVERS,  # Use centralized config
            ),
            "request_timeout_ms": 10000,
            "max_retries": 3,
        },
        "qdrant": {
            "url": os.getenv("TEST_QDRANT_URL", "http://localhost:6334"),
            "timeout": 10.0,
        },
        "memgraph": {
            "uri": os.getenv("TEST_MEMGRAPH_URI", "bolt://localhost:7688"),
            "username": os.getenv("TEST_MEMGRAPH_USER", ""),
            "password": os.getenv("TEST_MEMGRAPH_PASSWORD", ""),
            "timeout": 10.0,
        },
        "timeouts": {
            "kafka_produce": 5.0,
            "kafka_consume": 10.0,
            "qdrant_operation": 5.0,
            "memgraph_query": 5.0,
            "cleanup": 10.0,
        },
    }


@pytest.fixture(scope="session")
def test_id() -> str:
    """Generate unique test session ID for isolated test data."""
    return f"test_{uuid.uuid4().hex[:8]}"


# ============================================================================
# Kafka Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def kafka_producer(
    real_integration_config: Dict[str, Any],
) -> AsyncGenerator[AIOKafkaProducer, None]:
    """
    Kafka producer for real integration tests.

    Automatically starts and stops the producer.
    Includes timeout protection.
    """
    config = real_integration_config["kafka"]
    producer = AIOKafkaProducer(
        bootstrap_servers=config["bootstrap_servers"],
        request_timeout_ms=config["request_timeout_ms"],
        max_request_size=1048576,  # 1MB
    )

    try:
        # Start producer with timeout
        await asyncio.wait_for(
            producer.start(),
            timeout=real_integration_config["timeouts"]["kafka_produce"],
        )
        yield producer
    finally:
        # Cleanup with timeout
        try:
            await asyncio.wait_for(
                producer.stop(), timeout=real_integration_config["timeouts"]["cleanup"]
            )
        except asyncio.TimeoutError:
            pass  # Best effort cleanup


@pytest_asyncio.fixture
async def kafka_consumer(
    real_integration_config: Dict[str, Any], test_id: str
) -> AsyncGenerator[AIOKafkaConsumer, None]:
    """
    Kafka consumer for real integration tests.

    Creates consumer with test-specific group ID for isolation.
    Automatically subscribes to test topics and cleans up.
    """
    config = real_integration_config["kafka"]
    consumer = AIOKafkaConsumer(
        bootstrap_servers=config["bootstrap_servers"],
        group_id=f"test-group-{test_id}",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        request_timeout_ms=config["request_timeout_ms"],
    )

    try:
        # Start consumer with timeout
        await asyncio.wait_for(
            consumer.start(),
            timeout=real_integration_config["timeouts"]["kafka_consume"],
        )
        yield consumer
    finally:
        # Cleanup with timeout
        try:
            await asyncio.wait_for(
                consumer.stop(), timeout=real_integration_config["timeouts"]["cleanup"]
            )
        except asyncio.TimeoutError:
            pass  # Best effort cleanup


@pytest_asyncio.fixture
async def kafka_test_topic(test_id: str) -> str:
    """Generate unique test topic name for isolation."""
    return f"test-topic-{test_id}"


# ============================================================================
# Qdrant Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def qdrant_client(
    real_integration_config: Dict[str, Any],
) -> AsyncGenerator[AsyncQdrantClient, None]:
    """
    Qdrant client for real integration tests.

    Automatically connects and disconnects from Qdrant.
    Includes timeout protection.
    """
    config = real_integration_config["qdrant"]
    client = AsyncQdrantClient(
        url=config["url"],
        timeout=config["timeout"],
    )

    try:
        yield client
    finally:
        # Cleanup
        await client.close()


@pytest_asyncio.fixture
async def qdrant_test_collection(
    qdrant_client: AsyncQdrantClient,
    test_id: str,
    real_integration_config: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    Create isolated test collection in Qdrant.

    Automatically creates collection before test and deletes after.
    Uses test-specific collection name for isolation.
    """
    collection_name = f"test_collection_{test_id}"
    timeout = real_integration_config["timeouts"]["qdrant_operation"]

    try:
        # Create test collection with timeout
        await asyncio.wait_for(
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=1536, distance=Distance.COSINE  # OpenAI embedding size
                ),
            ),
            timeout=timeout,
        )
        yield collection_name
    finally:
        # Cleanup: delete test collection
        try:
            await asyncio.wait_for(
                qdrant_client.delete_collection(collection_name=collection_name),
                timeout=real_integration_config["timeouts"]["cleanup"],
            )
        except Exception:
            pass  # Best effort cleanup


# ============================================================================
# Memgraph Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def memgraph_driver(
    real_integration_config: Dict[str, Any],
) -> AsyncGenerator[Any, None]:
    """
    Memgraph Neo4j driver for real integration tests.

    Automatically connects and disconnects from Memgraph.
    Includes timeout protection.
    """
    config = real_integration_config["memgraph"]
    driver = AsyncGraphDatabase.driver(
        config["uri"],
        auth=(config["username"], config["password"]) if config["username"] else None,
    )

    try:
        # Verify connection
        async with driver.session() as session:
            await asyncio.wait_for(session.run("RETURN 1"), timeout=config["timeout"])
        yield driver
    finally:
        # Cleanup
        await driver.close()


@pytest_asyncio.fixture
async def memgraph_test_label(test_id: str) -> str:
    """Generate unique test node label for isolation."""
    return f"TestNode_{test_id}"


@pytest_asyncio.fixture
async def memgraph_session(
    memgraph_driver: Any,
    memgraph_test_label: str,
    real_integration_config: Dict[str, Any],
) -> AsyncGenerator[Any, None]:
    """
    Memgraph session with automatic cleanup.

    Automatically creates session and deletes test nodes after test.
    Uses test-specific labels for isolation.
    """
    async with memgraph_driver.session() as session:
        try:
            yield session
        finally:
            # Cleanup: delete all test nodes
            try:
                await asyncio.wait_for(
                    session.run(f"MATCH (n:{memgraph_test_label}) DETACH DELETE n"),
                    timeout=real_integration_config["timeouts"]["cleanup"],
                )
            except Exception:
                pass  # Best effort cleanup


# ============================================================================
# Helper Fixtures & Utilities
# ============================================================================


@pytest_asyncio.fixture
async def wait_for_kafka_message(
    kafka_consumer: AIOKafkaConsumer, real_integration_config: Dict[str, Any]
) -> callable:
    """
    Helper fixture to wait for Kafka message with timeout.

    Returns async function that waits for and returns next message.
    """

    async def _wait(topic: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Wait for message on topic with timeout."""
        if timeout is None:
            timeout = real_integration_config["timeouts"]["kafka_consume"]

        # Subscribe to topic
        kafka_consumer.subscribe([topic])

        # Wait for message
        try:
            async for message in kafka_consumer:
                return {
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                    "key": message.key.decode("utf-8") if message.key else None,
                    "value": message.value.decode("utf-8") if message.value else None,
                    "timestamp": message.timestamp,
                }
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"No message received on topic {topic} within {timeout}s"
            )

    return _wait


@pytest.fixture
def qdrant_test_points() -> List[PointStruct]:
    """
    Generate test points for Qdrant.

    Returns list of PointStruct objects for testing vector operations.
    """
    import random

    points = []
    for i in range(5):
        vector = [random.random() for _ in range(1536)]
        points.append(
            PointStruct(
                id=i,
                vector=vector,
                payload={
                    "text": f"Test document {i}",
                    "category": "test",
                    "index": i,
                },
            )
        )
    return points


# ============================================================================
# Composite Fixtures (Multiple Services)
# ============================================================================


@pytest_asyncio.fixture
async def real_integration_services(
    kafka_producer: AIOKafkaProducer,
    kafka_consumer: AIOKafkaConsumer,
    qdrant_client: AsyncQdrantClient,
    memgraph_driver: Any,
) -> Dict[str, Any]:
    """
    Composite fixture providing all real service connections.

    Use this when test needs multiple services.
    """
    return {
        "kafka_producer": kafka_producer,
        "kafka_consumer": kafka_consumer,
        "qdrant": qdrant_client,
        "memgraph": memgraph_driver,
    }


# ============================================================================
# Health Check Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="session", autouse=True)
async def check_service_health(real_integration_config: Dict[str, Any]) -> None:
    """
    Check that all required services are healthy before running tests.

    Runs once per test session.
    Skips all tests if services are not available.
    """
    if os.getenv("REAL_INTEGRATION_TESTS") != "true":
        # Skip health check if not running real integration tests
        return

    health_status = {}

    # Check Kafka
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=real_integration_config["kafka"]["bootstrap_servers"],
        )
        await asyncio.wait_for(producer.start(), timeout=5.0)
        await producer.stop()
        health_status["kafka"] = True
    except Exception as e:
        health_status["kafka"] = False
        health_status["kafka_error"] = str(e)

    # Check Qdrant
    try:
        client = AsyncQdrantClient(url=real_integration_config["qdrant"]["url"])
        await asyncio.wait_for(client.get_collections(), timeout=5.0)
        await client.close()
        health_status["qdrant"] = True
    except Exception as e:
        health_status["qdrant"] = False
        health_status["qdrant_error"] = str(e)

    # Check Memgraph
    try:
        driver = AsyncGraphDatabase.driver(
            real_integration_config["memgraph"]["uri"],
            auth=(
                (
                    real_integration_config["memgraph"]["username"],
                    real_integration_config["memgraph"]["password"],
                )
                if real_integration_config["memgraph"]["username"]
                else None
            ),
        )
        async with driver.session() as session:
            await asyncio.wait_for(session.run("RETURN 1"), timeout=5.0)
        await driver.close()
        health_status["memgraph"] = True
    except Exception as e:
        health_status["memgraph"] = False
        health_status["memgraph_error"] = str(e)

    # Report health status
    unhealthy = [
        name
        for name, healthy in health_status.items()
        if not healthy and not name.endswith("_error")
    ]

    if unhealthy:
        errors = "\n".join(
            [
                f"  - {name}: {health_status.get(f'{name}_error', 'Unknown error')}"
                for name in unhealthy
            ]
        )
        pytest.skip(
            f"Required services are not healthy:\n{errors}\n\n"
            f"Start services with: docker compose -f deployment/docker-compose.test.yml up -d"
        )
