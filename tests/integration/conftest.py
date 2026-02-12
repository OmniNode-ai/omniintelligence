# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for all integration tests.

This module provides common infrastructure fixtures that auto-configure from
the project's .env file. All integration tests can use these fixtures without
needing to manually set up environment variables.

Infrastructure Configuration (from .env):
    - PostgreSQL: 192.168.86.200:5436 (database: omninode_bridge)
    - Kafka/Redpanda: 192.168.86.200:29092 (for host scripts)

Usage:
    @pytest.mark.integration
    async def test_with_database(db_conn: asyncpg.Connection) -> None:
        result = await db_conn.fetchval("SELECT 1")
        assert result == 1

    @pytest.mark.integration
    async def test_with_pool(db_pool: asyncpg.Pool) -> None:
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1

    @pytest.mark.integration
    async def test_with_kafka(kafka_producer: AIOKafkaProducer) -> None:
        await kafka_producer.send_and_wait("test-topic", b"test-value")

Reference:
    - CLAUDE.md: Infrastructure topology documentation
    - ~/.claude/CLAUDE.md: Shared infrastructure guide
"""

from __future__ import annotations

import json
import os
import socket
import urllib.parse
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from aiokafka import AIOKafkaProducer

# =============================================================================
# Environment Loading
# =============================================================================

# Load .env file from project root BEFORE accessing any environment variables
# This ensures all fixtures and tests have access to configured values
_project_root: Path = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv

    # Load .env file if it exists
    _env_file = _project_root / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    # python-dotenv not installed, rely on existing environment
    pass

from omniintelligence.utils.db_url import safe_db_url_display as _safe_db_url_display

# =============================================================================
# Database Configuration
# =============================================================================

OMNIINTELLIGENCE_DB_URL: str = os.getenv("OMNIINTELLIGENCE_DB_URL", "")
"""PostgreSQL connection URL. Format: postgresql://user:password@host:port/database."""

# Connection pool settings
POSTGRES_MIN_POOL_SIZE: int = int(os.getenv("POSTGRES_MIN_POOL_SIZE", "2"))
"""Minimum connections in pool. Default: 2."""

POSTGRES_MAX_POOL_SIZE: int = int(os.getenv("POSTGRES_MAX_POOL_SIZE", "10"))
"""Maximum connections in pool. Default: 10."""

POSTGRES_COMMAND_TIMEOUT: float = float(os.getenv("POSTGRES_COMMAND_TIMEOUT", "60.0"))
"""Default command timeout in seconds. Default: 60.0."""


def _parse_db_url_host_port(url: str) -> tuple[str, int]:
    """Extract host and port from a PostgreSQL connection URL.

    Args:
        url: A postgresql:// URL.

    Returns:
        Tuple of (host, port).

    Raises:
        ValueError: If the URL cannot be parsed or is missing required components.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme.startswith("postgres"):
        raise ValueError(
            f"Expected a PostgreSQL URL (scheme starting with 'postgres'), "
            f"got scheme: '{parsed.scheme}'"
        )
    if not parsed.hostname:
        raise ValueError(
            "Invalid database URL: missing hostname. "
            "Expected format: postgresql://user:pass@host:port/database"
        )
    host = parsed.hostname
    port = parsed.port or 5432
    return host, port


# =============================================================================
# Kafka Configuration
# =============================================================================

KAFKA_BOOTSTRAP_SERVERS: str = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "192.168.86.200:29092"
)
"""Kafka bootstrap servers. Default: 192.168.86.200:29092 (external port)."""

KAFKA_REQUEST_TIMEOUT_MS: int = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "30000"))
"""Kafka request timeout in milliseconds. Default: 30000."""

KAFKA_MAX_BLOCK_MS: int = int(os.getenv("KAFKA_MAX_BLOCK_MS", "10000"))
"""Kafka max block time in milliseconds. Default: 10000."""


# =============================================================================
# Test Data Constants
# =============================================================================

TEST_DOMAIN_ID: str = "code_generation"
"""Pre-seeded domain from migrations for pattern tests."""

TEST_DOMAIN_VERSION: str = "1.0"
"""Default domain version for tests."""


# =============================================================================
# Infrastructure Availability Checks
# =============================================================================


def is_postgres_available(timeout: float = 2.0) -> bool:
    """Check if PostgreSQL is reachable at the configured endpoint.

    Parses OMNIINTELLIGENCE_DB_URL to extract host/port, then performs
    a TCP socket connection test to verify network connectivity.
    Does NOT verify credentials or database existence.

    Args:
        timeout: Connection timeout in seconds. Default: 2.0.

    Returns:
        True if PostgreSQL port is reachable, False otherwise.
    """
    if not OMNIINTELLIGENCE_DB_URL:
        return False
    try:
        host, port = _parse_db_url_host_port(OMNIINTELLIGENCE_DB_URL)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (OSError, ValueError):
        return False


def is_kafka_available(timeout: float = 2.0) -> bool:
    """Check if Kafka/Redpanda is reachable at the configured endpoint.

    Performs a TCP socket connection test to verify network connectivity.

    Args:
        timeout: Connection timeout in seconds. Default: 2.0.

    Returns:
        True if Kafka port is reachable, False otherwise.
    """
    try:
        # Parse host and port from bootstrap servers (take first if multiple)
        server = KAFKA_BOOTSTRAP_SERVERS.split(",")[0]
        if ":" in server:
            host, port_str = server.rsplit(":", 1)
            port = int(port_str)
        else:
            host = server
            port = 9092

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (OSError, ValueError):
        return False


# Store availability at module load for use in skip markers
POSTGRES_AVAILABLE: bool = is_postgres_available()
"""Whether PostgreSQL is reachable (checked at module load)."""

KAFKA_AVAILABLE: bool = is_kafka_available()
"""Whether Kafka is reachable (checked at module load)."""


# =============================================================================
# Skip Markers
# =============================================================================

requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason=f"PostgreSQL not reachable (OMNIINTELLIGENCE_DB_URL={'set' if OMNIINTELLIGENCE_DB_URL else 'missing'})",
)
"""Skip marker for tests requiring PostgreSQL connectivity."""

requires_kafka = pytest.mark.skipif(
    not KAFKA_AVAILABLE,
    reason=f"Kafka not reachable at {KAFKA_BOOTSTRAP_SERVERS}",
)
"""Skip marker for tests requiring Kafka connectivity."""

requires_db_url = pytest.mark.skipif(
    not OMNIINTELLIGENCE_DB_URL,
    reason="OMNIINTELLIGENCE_DB_URL not set in environment or .env file",
)
"""Skip marker for tests requiring database URL."""


# =============================================================================
# Database Connection Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def db_conn() -> AsyncGenerator[Any, None]:
    """Create a single asyncpg connection for integration tests.

    Auto-configures from OMNIINTELLIGENCE_DB_URL in .env file. Skips test
    gracefully if the URL is not set or connection fails.

    Yields:
        asyncpg.Connection connected to the test database.

    Example:
        @pytest.mark.integration
        async def test_query(db_conn: asyncpg.Connection) -> None:
            result = await db_conn.fetchval("SELECT 1")
            assert result == 1
    """
    if not OMNIINTELLIGENCE_DB_URL:
        pytest.skip(
            "OMNIINTELLIGENCE_DB_URL not set - add to .env file or environment. "
            f"Expected .env at: {_project_root / '.env'}"
        )

    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed - add to dev dependencies")

    try:
        conn = await asyncpg.connect(
            OMNIINTELLIGENCE_DB_URL,
            timeout=30,
            command_timeout=POSTGRES_COMMAND_TIMEOUT,
        )
    except (OSError, Exception) as e:
        pytest.skip(
            f"Database connection failed: {e}. "
            f"URL: {_safe_db_url_display(OMNIINTELLIGENCE_DB_URL)}"
        )

    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def db_pool() -> AsyncGenerator[Any, None]:
    """Create an asyncpg connection pool for integration tests.

    Useful for tests that need multiple concurrent connections or
    want to test connection pool behavior.

    Auto-configures from OMNIINTELLIGENCE_DB_URL in .env file. Skips test
    gracefully if the URL is not set or pool creation fails.

    Yields:
        asyncpg.Pool connected to the test database.

    Example:
        @pytest.mark.integration
        async def test_concurrent_queries(db_pool: asyncpg.Pool) -> None:
            async with db_pool.acquire() as conn1:
                async with db_pool.acquire() as conn2:
                    result1 = await conn1.fetchval("SELECT 1")
                    result2 = await conn2.fetchval("SELECT 2")
    """
    if not OMNIINTELLIGENCE_DB_URL:
        pytest.skip(
            "OMNIINTELLIGENCE_DB_URL not set - add to .env file or environment. "
            f"Expected .env at: {_project_root / '.env'}"
        )

    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed - add to dev dependencies")

    try:
        pool = await asyncpg.create_pool(
            OMNIINTELLIGENCE_DB_URL,
            min_size=POSTGRES_MIN_POOL_SIZE,
            max_size=POSTGRES_MAX_POOL_SIZE,
            timeout=30,
            command_timeout=POSTGRES_COMMAND_TIMEOUT,
        )
    except (OSError, Exception) as e:
        pytest.skip(
            f"Database pool creation failed: {e}. "
            f"URL: {_safe_db_url_display(OMNIINTELLIGENCE_DB_URL)}"
        )

    try:
        yield pool
    finally:
        await pool.close()


# =============================================================================
# Kafka Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def kafka_producer() -> AsyncGenerator[Any, None]:
    """Create an AIOKafka producer for integration tests.

    Auto-configures from .env file. Skips test gracefully if Kafka
    is not available.

    Yields:
        AIOKafkaProducer connected to the configured bootstrap servers.

    Example:
        @pytest.mark.integration
        async def test_publish_event(kafka_producer: AIOKafkaProducer) -> None:
            await kafka_producer.send_and_wait(
                "test-topic",
                value=b'{"event": "test"}',
                key=b"test-key",
            )
    """
    try:
        from aiokafka import AIOKafkaProducer
    except ImportError:
        pytest.skip("aiokafka not installed - add to core dependencies")

    if not KAFKA_AVAILABLE:
        pytest.skip(f"Kafka not reachable at {KAFKA_BOOTSTRAP_SERVERS}")

    # Note: AIOKafkaProducer does not support max_block_ms parameter
    # (that's a Java Kafka client parameter). We use request_timeout_ms instead.
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        request_timeout_ms=KAFKA_REQUEST_TIMEOUT_MS,
    )

    try:
        await producer.start()
    except Exception as e:
        pytest.skip(f"Kafka producer start failed: {e}")

    try:
        yield producer
    finally:
        await producer.stop()


@pytest_asyncio.fixture
async def kafka_consumer() -> AsyncGenerator[Any, None]:
    """Create an AIOKafka consumer for integration tests.

    Auto-configures from .env file. Skips test gracefully if Kafka
    is not available.

    Note: This creates a consumer without subscribing to any topics.
    Tests should call consumer.subscribe() with appropriate topics.

    Yields:
        AIOKafkaConsumer connected to the configured bootstrap servers.

    Example:
        @pytest.mark.integration
        async def test_consume_events(kafka_consumer: AIOKafkaConsumer) -> None:
            kafka_consumer.subscribe(["test-topic"])
            async for msg in kafka_consumer:
                break  # Process first message
    """
    try:
        from aiokafka import AIOKafkaConsumer
    except ImportError:
        pytest.skip("aiokafka not installed - add to core dependencies")

    if not KAFKA_AVAILABLE:
        pytest.skip(f"Kafka not reachable at {KAFKA_BOOTSTRAP_SERVERS}")

    consumer = AIOKafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"test-consumer-{os.getpid()}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    try:
        await consumer.start()
    except Exception as e:
        pytest.skip(f"Kafka consumer start failed: {e}")

    try:
        yield consumer
    finally:
        await consumer.stop()


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def sample_correlation_id() -> str:
    """Provide a fixed correlation ID for tracing tests.

    Returns:
        A deterministic UUID string for test repeatability.
    """
    return "12345678-1234-5678-1234-567812345678"


@pytest.fixture
def integration_test_prefix() -> str:
    """Provide a prefix for test data created during integration tests.

    This prefix helps identify and clean up test data.

    Returns:
        A string prefix for test data identification.
    """
    return "integration_test_"


# =============================================================================
# Real Kafka Publisher Adapter
# =============================================================================


class RealKafkaPublisher:
    """Real Kafka publisher that adapts AIOKafkaProducer to ProtocolKafkaPublisher.

    This adapter bridges the gap between the AIOKafkaProducer interface
    (send_and_wait) and the ProtocolKafkaPublisher interface (publish) used
    by ONEX effect node handlers.

    The adapter also tracks published events for assertion in tests, providing
    the same interface as MockKafkaPublisher for verification.

    Attributes:
        producer: The underlying AIOKafkaProducer instance.
        published_events: List of (topic, key, value) tuples for assertion.
        topic_prefix: Optional prefix added to all topics for isolation.
        created_topics: Set of unique topics that were published to.

    Example:
        >>> async def test_real_kafka_publishing(kafka_producer):
        ...     publisher = RealKafkaPublisher(kafka_producer)
        ...     await publisher.publish("test-topic", "key", {"data": "value"})
        ...     assert len(publisher.published_events) == 1
    """

    def __init__(
        self,
        producer: AIOKafkaProducer,
        *,
        topic_prefix: str = "",
    ) -> None:
        """Initialize the real Kafka publisher adapter.

        Args:
            producer: AIOKafkaProducer instance (already started).
            topic_prefix: Optional prefix for topic isolation.
        """
        self._producer: AIOKafkaProducer = producer
        self._topic_prefix = topic_prefix
        self.published_events: list[tuple[str, str, dict[str, Any]]] = []
        self.created_topics: set[str] = set()

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Publish an event to Kafka.

        Implements the ProtocolKafkaPublisher interface by adapting to
        AIOKafkaProducer.send_and_wait().

        Args:
            topic: Target Kafka topic name (prefix will be prepended if set).
            key: Message key for partitioning.
            value: Event payload as a dictionary (will be JSON serialized).
        """
        # Apply topic prefix for test isolation
        full_topic = f"{self._topic_prefix}{topic}" if self._topic_prefix else topic

        # Serialize value to JSON bytes
        value_bytes = json.dumps(value).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None

        # Publish to Kafka
        await self._producer.send_and_wait(
            full_topic,
            value=value_bytes,
            key=key_bytes,
        )

        # Track the topic for cleanup
        self.created_topics.add(full_topic)

        # Record for assertion (store with full topic for verification)
        self.published_events.append((full_topic, key, value))

    def reset(self) -> None:
        """Clear all recorded events and topics."""
        self.published_events.clear()
        self.created_topics.clear()

    def get_created_topics(self) -> set[str]:
        """Get all unique topics that were published to.

        Returns:
            Set of full topic names (including prefix) that received messages.
        """
        return self.created_topics.copy()

    def get_events_for_topic(self, topic: str) -> list[tuple[str, str, dict[str, Any]]]:
        """Get all events published to a specific topic.

        Args:
            topic: The topic to filter by (will match full topic including prefix).

        Returns:
            List of (topic, key, value) tuples for the specified topic.
        """
        # Match with or without prefix
        full_topic = f"{self._topic_prefix}{topic}" if self._topic_prefix else topic
        return [e for e in self.published_events if e[0] == full_topic or e[0] == topic]


# =============================================================================
# Mock Kafka Publisher
# =============================================================================


class MockKafkaPublisher:
    """Mock Kafka publisher that records events without publishing.

    Useful for testing event-driven code without requiring real Kafka
    infrastructure. Records all published events for assertion.

    Attributes:
        published_events: List of (topic, key, value) tuples.

    Example:
        async def test_event_publishing(mock_kafka_publisher) -> None:
            await mock_kafka_publisher.publish("topic", "key", {"data": "value"})
            assert len(mock_kafka_publisher.published_events) == 1
    """

    def __init__(self) -> None:
        """Initialize the mock publisher with empty event list."""
        self.published_events: list[tuple[str, str, dict[str, Any]]] = []

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Record the event instead of publishing.

        Args:
            topic: Target Kafka topic name.
            key: Message key for partitioning.
            value: Event payload as a dictionary.
        """
        self.published_events.append((topic, key, value))

    def reset(self) -> None:
        """Clear all recorded events."""
        self.published_events.clear()

    def get_events_for_topic(self, topic: str) -> list[tuple[str, str, dict[str, Any]]]:
        """Get all events published to a specific topic.

        Args:
            topic: The topic to filter by.

        Returns:
            List of (topic, key, value) tuples for the specified topic.
        """
        return [e for e in self.published_events if e[0] == topic]


@pytest.fixture
def mock_kafka_publisher() -> MockKafkaPublisher:
    """Create a mock Kafka publisher for testing without real Kafka.

    Returns:
        A MockKafkaPublisher instance that records events.
    """
    return MockKafkaPublisher()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Configuration constants
    "KAFKA_AVAILABLE",
    "KAFKA_BOOTSTRAP_SERVERS",
    "KAFKA_MAX_BLOCK_MS",
    "KAFKA_REQUEST_TIMEOUT_MS",
    "OMNIINTELLIGENCE_DB_URL",
    "POSTGRES_AVAILABLE",
    "POSTGRES_COMMAND_TIMEOUT",
    "POSTGRES_MAX_POOL_SIZE",
    "POSTGRES_MIN_POOL_SIZE",
    "TEST_DOMAIN_ID",
    "TEST_DOMAIN_VERSION",
    # Publisher classes
    "MockKafkaPublisher",
    "RealKafkaPublisher",
    # Fixtures
    "db_conn",
    "db_pool",
    "integration_test_prefix",
    # Availability check functions
    "is_kafka_available",
    "is_postgres_available",
    "kafka_consumer",
    "kafka_producer",
    "mock_kafka_publisher",
    # Skip markers
    "requires_db_url",
    "requires_kafka",
    "requires_postgres",
    "sample_correlation_id",
]
