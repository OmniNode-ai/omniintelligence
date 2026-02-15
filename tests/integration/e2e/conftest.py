# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Fixtures for E2E integration tests of the pattern learning pipeline.

This module provides pytest fixtures for end-to-end testing of the pattern
learning pipeline using:
- Real PostgreSQL (configured via OMNIINTELLIGENCE_DB_URL) for data integrity
- Real Kafka/Redpanda (configured via KAFKA_BOOTSTRAP_SERVERS) for event emission and verification

Test Coverage:
    - Pattern learning compute (TC1-TC3)
    - Pattern storage to learned_patterns table
    - Feedback loop updates (TC4)
    - Kafka event emission and verification

Infrastructure Configuration (from .env):
    - PostgreSQL: configured via OMNIINTELLIGENCE_DB_URL
    - Kafka/Redpanda: ${KAFKA_BOOTSTRAP_SERVERS} (external port for host access)

Kafka Integration:
    The module provides real Kafka integration via the `e2e_kafka_publisher` fixture.
    This publisher implements the `ProtocolKafkaPublisher` interface and wraps
    `AIOKafkaProducer` for actual event emission.

    For tests requiring event verification, use the `e2e_kafka_consumer` fixture
    which can subscribe to topics and verify published events.

    Tests are isolated via unique topic prefixes (e2e_test_{uuid}_) to prevent
    pollution between test runs.

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
    - learned_patterns.repository.yaml: Repository contract for pattern storage
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

# Logger for cleanup operations
_cleanup_logger = logging.getLogger(__name__)

# Import shared fixtures and utilities from root integration conftest
from omniintelligence.utils.db_url import safe_db_url_display as _safe_db_url_display
from tests.integration.conftest import (
    KAFKA_AVAILABLE,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_REQUEST_TIMEOUT_MS,
    OMNIINTELLIGENCE_DB_URL,
    POSTGRES_AVAILABLE,
    POSTGRES_COMMAND_TIMEOUT,
    MockKafkaPublisher,
    RealKafkaPublisher,
)

if TYPE_CHECKING:
    import asyncpg

# =============================================================================
# Constants
# =============================================================================

E2E_TEST_PREFIX: str = "e2e_test_"
"""Prefix for E2E test data to enable cleanup without affecting production data."""

E2E_SIGNATURE_PREFIX: str = "test_e2e_"
"""Prefix for signature_hash values created during E2E tests."""

E2E_SIGNATURE_CONTAINS: str = "e2e_test"
"""Substring to match in pattern_signature for fallback cleanup.

Used when signature_hash column doesn't exist. The fallback cleanup uses
LIKE '%e2e_test%' to match patterns created by create_test_pattern(),
which generates signatures like 'def e2e_test_pattern_<uuid>(): pass'.
"""

E2E_DOMAIN: str = "code_generation"
"""Domain used for E2E test patterns.

Uses existing domain from domain_taxonomy to satisfy FK.
"""


# =============================================================================
# Kafka Consumer Utilities
# =============================================================================


async def wait_for_message(
    consumer: Any,
    topic: str,
    timeout_seconds: float = 10.0,
    poll_interval_ms: int = 500,
) -> dict[str, Any]:
    """Wait for a message on topic, raising AssertionError if not received.

    This helper polls the Kafka consumer with explicit timeouts and retry logic
    to reliably receive messages in E2E tests. Unlike relying on async iteration
    timeout behavior, this provides deterministic failure when messages aren't
    received.

    Args:
        consumer: AIOKafkaConsumer instance (already started and subscribed).
        topic: The topic to wait for a message on.
        timeout_seconds: Maximum time to wait for a message (default: 10s).
        poll_interval_ms: Time between poll attempts in milliseconds (default: 500ms).

    Returns:
        Dictionary with 'key', 'value', and 'topic' from the received message.

    Raises:
        AssertionError: If no message is received within the timeout period.
    """
    import json
    import time

    start_time = time.monotonic()
    max_attempts = int((timeout_seconds * 1000) / poll_interval_ms)

    for attempt in range(max_attempts):
        # Use getmany for explicit polling with timeout
        # This returns a dict of {TopicPartition: [messages]}
        records = await consumer.getmany(timeout_ms=poll_interval_ms, max_records=10)

        for tp, messages in records.items():
            for msg in messages:
                if msg.topic == topic:
                    return {
                        "key": msg.key.decode("utf-8") if msg.key else None,
                        "value": json.loads(msg.value.decode("utf-8")),
                        "topic": msg.topic,
                    }

        # Check if we've exceeded our timeout
        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_seconds:
            break

    # Calculate actual elapsed time for the error message
    elapsed = time.monotonic() - start_time
    raise AssertionError(
        f"Kafka consumer did not receive message on topic '{topic}' "
        f"within {timeout_seconds}s timeout (elapsed: {elapsed:.2f}s, "
        f"attempts: {max_attempts}). This indicates a real infrastructure "
        f"issue - the message was not delivered to the broker or the consumer "
        f"failed to read it."
    )


# =============================================================================
# Kafka Topic Cleanup Utilities
# =============================================================================


async def delete_kafka_topics(
    topics: set[str] | list[str],
    *,
    bootstrap_servers: str | None = None,
    timeout_ms: int = 30000,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Delete Kafka topics using the admin client.

    This function provides graceful cleanup of test topics. It handles errors
    gracefully and logs the results for debugging.

    Args:
        topics: Set or list of topic names to delete.
        bootstrap_servers: Kafka bootstrap servers. Defaults to KAFKA_BOOTSTRAP_SERVERS.
        timeout_ms: Timeout for admin operations in milliseconds.

    Returns:
        A tuple of (deleted_topics, failed_topics) where:
        - deleted_topics: List of topic names that were successfully deleted.
        - failed_topics: List of (topic_name, error_message) tuples for failures.

    Note:
        This function is designed to be safe - it will not raise exceptions
        for missing topics or other expected errors. All errors are logged
        and returned in the failed_topics list.
    """
    if not topics:
        return [], []

    if bootstrap_servers is None:
        bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS

    deleted: list[str] = []
    failed: list[tuple[str, str]] = []
    topics_list = list(topics)

    try:
        from aiokafka.admin import AIOKafkaAdminClient
    except ImportError:
        _cleanup_logger.warning(
            "aiokafka.admin not available - cannot delete topics. Topics to delete: %s",
            topics_list,
        )
        return [], [(t, "aiokafka.admin not available") for t in topics_list]

    admin: AIOKafkaAdminClient | None = None
    try:
        admin = AIOKafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            request_timeout_ms=timeout_ms,
        )
        await admin.start()

        # Note: AIOKafkaAdminClient doesn't have list_topics, so we try to
        # delete topics and handle "not found" errors gracefully.

        # Delete topics one by one for better error handling
        for topic in topics_list:
            try:
                await admin.delete_topics([topic])
                deleted.append(topic)
                _cleanup_logger.debug("Deleted Kafka topic: %s", topic)
            except Exception as e:
                error_msg = str(e)
                # Check for common "topic not found" patterns
                is_not_found = (
                    "UnknownTopicOrPartition" in error_msg
                    or "does not exist" in error_msg.lower()
                )
                if is_not_found:
                    _cleanup_logger.debug(
                        "Topic %s does not exist (already deleted or never created)",
                        topic,
                    )
                    # Consider this a success - the topic is gone
                    deleted.append(topic)
                else:
                    _cleanup_logger.warning(
                        "Failed to delete topic %s: %s", topic, error_msg
                    )
                    failed.append((topic, error_msg))

    except Exception as e:
        _cleanup_logger.warning(
            "Kafka admin client error during topic cleanup: %s. Topics: %s",
            e,
            topics_list,
        )
        # Mark all remaining topics as failed
        already_processed = set(deleted) | {t for t, _ in failed}
        for topic in topics_list:
            if topic not in already_processed:
                failed.append((topic, f"Admin client error: {e}"))

    finally:
        if admin is not None:
            try:
                await admin.close()
            except Exception as e:
                _cleanup_logger.debug("Error closing admin client: %s", e)

    if deleted:
        _cleanup_logger.info(
            "E2E Kafka cleanup: deleted %d topics: %s",
            len(deleted),
            deleted,
        )
    if failed:
        _cleanup_logger.warning(
            "E2E Kafka cleanup: failed to delete %d topics: %s",
            len(failed),
            failed,
        )

    return deleted, failed


async def list_e2e_test_topics(
    prefix: str = "e2e_test_",
    *,
    bootstrap_servers: str | None = None,
    timeout_ms: int = 30000,
) -> list[str]:
    """List all Kafka topics matching the E2E test prefix.

    Args:
        prefix: Topic prefix to match. Defaults to "e2e_test_".
        bootstrap_servers: Kafka bootstrap servers. Defaults to KAFKA_BOOTSTRAP_SERVERS.
        timeout_ms: Timeout for admin operations in milliseconds.

    Returns:
        List of topic names matching the prefix.
    """
    if bootstrap_servers is None:
        bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS

    try:
        from aiokafka import AIOKafkaConsumer
    except ImportError:
        _cleanup_logger.warning("aiokafka not available - cannot list topics")
        return []

    consumer: AIOKafkaConsumer | None = None
    try:
        # Use a consumer to get topic list (more reliable than admin client)
        consumer = AIOKafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            request_timeout_ms=timeout_ms,
        )
        await consumer.start()
        all_topics = await consumer.topics()
        return [t for t in all_topics if t.startswith(prefix)]

    except Exception as e:
        _cleanup_logger.warning("Failed to list topics: %s", e)
        return []

    finally:
        if consumer is not None:
            try:
                await consumer.stop()
            except Exception as e:
                _cleanup_logger.debug("Error stopping consumer: %s", e)


# =============================================================================
# Path Resolution (ensure tests/ is in Python path)
# =============================================================================

_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


# =============================================================================
# Schema Version Detection
# =============================================================================


async def _check_signature_hash_column_exists(conn: Any) -> bool:
    """Check if the signature_hash column exists in learned_patterns table.

    This function detects whether migration 009_add_signature_hash has been applied.

    Args:
        conn: asyncpg.Connection to the database.

    Returns:
        True if signature_hash column exists, False otherwise.
    """
    result = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'learned_patterns'
              AND column_name = 'signature_hash'
        )
        """
    )
    return bool(result)


# =============================================================================
# Skip Markers
# =============================================================================

requires_e2e_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE or not OMNIINTELLIGENCE_DB_URL,
    reason=("PostgreSQL not available or OMNIINTELLIGENCE_DB_URL not set"),
)
"""Skip marker for E2E tests requiring real PostgreSQL connectivity."""

requires_e2e_kafka = pytest.mark.skipif(
    not KAFKA_AVAILABLE,
    reason=f"Kafka not available at {KAFKA_BOOTSTRAP_SERVERS}",
)
"""Skip marker for E2E tests requiring real Kafka connectivity."""


# =============================================================================
# Session-Scoped Schema Detection
# =============================================================================


@pytest_asyncio.fixture(scope="session")
async def signature_hash_available() -> bool:
    """Session-scoped fixture that checks if signature_hash column exists.

    This fixture establishes a temporary connection to check the database schema
    once per test session. The result is cached for the duration of the session,
    avoiding repeated schema checks and eliminating global state mutation.

    Returns:
        True if signature_hash column exists in learned_patterns table,
        False otherwise.

    Note:
        If PostgreSQL is not available, returns False (tests will skip via
        other mechanisms like requires_e2e_postgres marker).
    """
    if not OMNIINTELLIGENCE_DB_URL:
        return False

    try:
        import asyncpg
    except ImportError:
        return False

    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            OMNIINTELLIGENCE_DB_URL,
            timeout=30,
            command_timeout=POSTGRES_COMMAND_TIMEOUT,
        )
    except (OSError, Exception):
        return False

    try:
        result = await _check_signature_hash_column_exists(conn)
        return result
    finally:
        await conn.close()


# =============================================================================
# Database Connection Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def e2e_db_conn(
    signature_hash_available: bool,
) -> AsyncGenerator[Any, None]:
    """Create a dedicated asyncpg connection for E2E tests with automatic cleanup.

    This fixture provides:
    - Real PostgreSQL connection (configured via OMNIINTELLIGENCE_DB_URL)
    - Test isolation via E2E-prefixed signature_hash values
    - Automatic cleanup of test data after each test
    - Schema version detection via session-scoped signature_hash_available fixture

    The cleanup ensures no test pollution by removing patterns where
    signature_hash LIKE 'test_e2e_%' after each test.

    Args:
        signature_hash_available: Session-scoped fixture indicating if signature_hash
            column exists in the database schema.

    Yields:
        asyncpg.Connection connected to the test database.

    Note:
        Tests MUST use signature_hash values starting with 'test_e2e_' to ensure
        proper cleanup. Use the create_e2e_signature_hash() helper for this.
    """
    if not OMNIINTELLIGENCE_DB_URL:
        pytest.skip(
            "OMNIINTELLIGENCE_DB_URL not set - add to .env file or environment. "
            "Expected .env at project root"
        )

    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed - add to dev dependencies")

    try:
        conn: asyncpg.Connection = await asyncpg.connect(
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
        # Cleanup: Remove all E2E test patterns
        try:
            await _cleanup_e2e_test_data(conn, signature_hash_available)
        except Exception as cleanup_error:
            # Log but don't fail the test on cleanup error
            _cleanup_logger.warning("E2E cleanup failed: %s", cleanup_error)
        finally:
            await conn.close()


@pytest_asyncio.fixture
async def e2e_db_conn_with_signature_hash(
    e2e_db_conn: Any,
    signature_hash_available: bool,
) -> AsyncGenerator[Any, None]:
    """Database connection fixture that requires signature_hash column.

    This fixture wraps e2e_db_conn and skips the test if the signature_hash
    column doesn't exist (migration 009 not applied).

    Use this fixture for tests that depend on the signature_hash column.

    Args:
        e2e_db_conn: The E2E database connection fixture.
        signature_hash_available: Session-scoped fixture indicating if signature_hash
            column exists in the database schema.

    Yields:
        asyncpg.Connection connected to the test database.

    Raises:
        pytest.skip: If signature_hash column doesn't exist.
    """
    if not signature_hash_available:
        pytest.skip(
            "signature_hash column not found in learned_patterns table. "
            "Run migration 009_add_signature_hash.sql first."
        )

    yield e2e_db_conn


async def _cleanup_e2e_test_data(
    conn: Any,
    signature_hash_available: bool | None = None,
) -> int:
    """Remove all E2E test data from learned_patterns and pattern_injections tables.

    This function removes:
    1. pattern_injections where pattern_ids reference E2E test patterns
    2. Patterns created during E2E testing by matching:
       - signature_hash LIKE 'test_e2e_%' (if column exists)
       - pattern_signature LIKE '%e2e_test%' (fallback - contains match)

    Note: Uses signature patterns ONLY for cleanup - does NOT delete by domain_id
    since E2E tests use existing production domains (e.g., code_generation).

    The function is backward compatible with databases that don't have the
    signature_hash column (migration 009 not applied).

    **Fallback Pattern Matching**:
    When signature_hash column doesn't exist, the fallback uses a "contains" match
    (LIKE '%e2e_test%') rather than "starts with" because create_test_pattern()
    generates signatures like 'def e2e_test_pattern_<uuid>(): pass' where the
    E2E marker is in the middle of the string, not at the start.

    Args:
        conn: asyncpg.Connection to the database.
        signature_hash_available: Whether the signature_hash column exists.
            If None, will check the schema dynamically (for backward compatibility).

    Returns:
        Number of learned_patterns rows deleted.
    """
    # Check schema version if not provided (backward compatibility)
    use_signature_hash = signature_hash_available
    if use_signature_hash is None:
        use_signature_hash = await _check_signature_hash_column_exists(conn)

    # Build the appropriate query based on schema version
    # Note: Only uses signature patterns for cleanup to avoid deleting production data
    if use_signature_hash:
        # Use signature_hash (preferred - migration 009 applied)
        # signature_hash values start with E2E_SIGNATURE_PREFIX
        # (e.g., 'test_e2e_<hash>')
        #
        # IMPORTANT: Also handle NULL signature_hash case by falling back to
        # pattern_signature matching. This catches patterns that were created
        # without a signature_hash (e.g., by direct SQL or older code paths).
        # NULL LIKE 'pattern%' evaluates to NULL (not TRUE), so we need the OR.
        select_query = """
            SELECT id FROM learned_patterns
            WHERE signature_hash LIKE $1
               OR (signature_hash IS NULL AND pattern_signature LIKE $2)
        """
        delete_query = """
            DELETE FROM learned_patterns
            WHERE signature_hash LIKE $1
               OR (signature_hash IS NULL AND pattern_signature LIKE $2)
        """
        like_pattern = f"{E2E_SIGNATURE_PREFIX}%"
        fallback_pattern = f"%{E2E_SIGNATURE_CONTAINS}%"
    else:
        # Fallback: use pattern_signature (migration 009 not applied)
        # pattern_signature values contain E2E_SIGNATURE_CONTAINS
        # (e.g., 'def e2e_test_pattern_...')
        # Uses "contains" match since the E2E marker is in the middle
        select_query = """
            SELECT id FROM learned_patterns
            WHERE pattern_signature LIKE $1
        """
        delete_query = """
            DELETE FROM learned_patterns
            WHERE pattern_signature LIKE $1
        """
        like_pattern = f"%{E2E_SIGNATURE_CONTAINS}%"
        fallback_pattern = None  # Not used in this branch

    # First, get the IDs of patterns we're going to delete
    if fallback_pattern is not None:
        # Two parameters: signature_hash and pattern_signature fallback
        pattern_ids = await conn.fetch(
            select_query,
            like_pattern,
            fallback_pattern,
        )
    else:
        # Single parameter: pattern_signature only
        pattern_ids = await conn.fetch(
            select_query,
            like_pattern,
        )

    # Delete pattern_injections that reference these patterns
    # Uses array overlap (&&) to find injections containing these patterns
    if pattern_ids:
        ids_list = [row["id"] for row in pattern_ids]
        await conn.execute(
            """
            DELETE FROM pattern_injections
            WHERE pattern_ids && $1::uuid[]
            """,
            ids_list,
        )

    # Delete the E2E test patterns
    if fallback_pattern is not None:
        # Two parameters: signature_hash and pattern_signature fallback
        result = await conn.execute(
            delete_query,
            like_pattern,
            fallback_pattern,
        )
    else:
        # Single parameter: pattern_signature only
        result = await conn.execute(
            delete_query,
            like_pattern,
        )
    # Parse "DELETE N" to get count
    if result and result.startswith("DELETE "):
        return int(result.split()[1])
    return 0


# =============================================================================
# Mock Kafka Fixture (for backward compatibility)
# =============================================================================


@pytest.fixture
def mock_kafka() -> MockKafkaPublisher:
    """Create a MockKafkaPublisher for testing event emission without real Kafka.

    The mock records all published events for assertion in tests.
    Events are stored as (topic, key, value) tuples.

    Note: For E2E tests that need real Kafka, use e2e_kafka_publisher instead.

    Returns:
        MockKafkaPublisher instance with empty event list.

    Example:
        >>> async def test_event_emission(mock_kafka):
        ...     # Run code that emits events
        ...     events = mock_kafka.get_events_for_topic("pattern-stored")
        ...     assert len(events) == 1
    """
    return MockKafkaPublisher()


# =============================================================================
# Real Kafka Fixtures
# =============================================================================

# Design Note: Why RealKafkaPublisher instead of EventBusKafka?
#
# PR #58 reviewer suggested considering EventBusInmemory/EventBusKafka here.
# After evaluation, RealKafkaPublisher is the correct choice for E2E tests because:
#
# 1. Interface Match: ONEX effect node handlers accept ProtocolKafkaPublisher
#    (publish(topic, key, value: dict)), not ProtocolEventBus (publish with bytes).
#    Using EventBus would require an adapter layer (as in node_claude_hook_event_effect).
#
# 2. Publish-Only Scope: E2E tests only need publish + verify. RealKafkaPublisher
#    provides get_events_for_topic() for verification. Full pub/sub semantics
#    (subscribe callbacks, event routing) are not needed here.
#
# 3. Pattern Already Available: For tests that need full pub/sub (like node
#    integration tests), EventBusInmemory + EventBusKafkaPublisherAdapter is
#    already used in tests/integration/nodes/node_claude_hook_event_effect/.
#
# 4. Direct Dependency Injection: Handlers receive ProtocolKafkaPublisher directly.
#    No adapter indirection means simpler test setup and clearer error messages.
#
# When to use EventBus instead: Tests requiring subscribe callbacks, event routing
# between nodes, or consumer group behavior testing.


@pytest.fixture(scope="session")
def e2e_topic_prefix() -> str:
    """Generate a unique topic prefix for E2E test isolation.

    Each test session gets a unique prefix to prevent topic pollution
    between concurrent test runs or leftover messages from previous runs.

    Returns:
        A unique prefix string like "e2e_test_abc123_".

    Note:
        Topics with this prefix can be safely deleted after tests.
        The prefix format is: e2e_test_{short_uuid}_
    """
    short_uuid = uuid4().hex[:8]
    return f"e2e_test_{short_uuid}_"


@pytest_asyncio.fixture
async def e2e_kafka_producer() -> AsyncGenerator[Any, None]:
    """Create an AIOKafka producer for E2E tests.

    Auto-configures from .env file. Skips test gracefully if Kafka
    is not available.

    Yields:
        AIOKafkaProducer connected to the configured bootstrap servers.
    """
    try:
        from aiokafka import AIOKafkaProducer
    except ImportError:
        pytest.skip("aiokafka not installed - add to core dependencies")

    if not KAFKA_AVAILABLE:
        pytest.skip(f"Kafka not reachable at {KAFKA_BOOTSTRAP_SERVERS}")

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
async def e2e_kafka_publisher(
    e2e_kafka_producer: Any,
    e2e_topic_prefix: str,
) -> AsyncGenerator[RealKafkaPublisher, None]:
    """Create a real Kafka publisher for E2E tests.

    This fixture provides a publisher that implements ProtocolKafkaPublisher
    and wraps the actual AIOKafkaProducer. Events are published to real Kafka
    with a test-specific topic prefix for isolation.

    The publisher also tracks published events for assertion, matching the
    MockKafkaPublisher interface.

    **Topic Cleanup**: Topics created during the test are automatically deleted
    in the teardown phase to prevent broker pollution. Cleanup is graceful -
    failures are logged but do not cause test failures.

    Args:
        e2e_kafka_producer: The underlying AIOKafkaProducer fixture.
        e2e_topic_prefix: Unique topic prefix for test isolation.

    Yields:
        RealKafkaPublisher instance connected to real Kafka.

    Example:
        >>> @pytest.mark.asyncio
        >>> @requires_e2e_kafka
        >>> async def test_pattern_promotion_emits_event(
        ...     e2e_kafka_publisher,
        ...     e2e_db_conn,
        ... ):
        ...     # Run promotion handler with real Kafka
        ...     result = await check_and_promote_patterns(
        ...         repository=e2e_db_conn,
        ...         producer=e2e_kafka_publisher,
        ...     )
        ...     # Verify events were published
        ...     events = e2e_kafka_publisher.get_events_for_topic("pattern-promoted")
        ...     assert len(events) == result.patterns_promoted
    """
    publisher = RealKafkaPublisher(
        e2e_kafka_producer,
        topic_prefix=e2e_topic_prefix,
    )

    try:
        yield publisher
    finally:
        # Cleanup: Delete topics created during the test
        created_topics = publisher.get_created_topics()
        if created_topics:
            _cleanup_logger.debug(
                "E2E test cleanup: attempting to delete %d topics with prefix %s",
                len(created_topics),
                e2e_topic_prefix,
            )
            try:
                deleted, failed = await delete_kafka_topics(created_topics)
                if deleted:
                    _cleanup_logger.debug(
                        "E2E test cleanup: successfully deleted topics: %s", deleted
                    )
                if failed:
                    _cleanup_logger.warning(
                        "E2E test cleanup: some topics could not be deleted: %s", failed
                    )
            except Exception as e:
                # Graceful degradation - log but don't fail the test
                _cleanup_logger.warning(
                    "E2E test cleanup: topic deletion failed: %s. Topics: %s",
                    e,
                    created_topics,
                )


@pytest_asyncio.fixture
async def e2e_kafka_consumer(
    e2e_topic_prefix: str,
) -> AsyncGenerator[Any, None]:
    """Create an AIOKafka consumer for E2E event verification.

    This fixture provides a consumer that can subscribe to topics and verify
    that events were actually published to Kafka. Useful for end-to-end
    verification beyond just checking the publisher's recorded events.

    The consumer uses the test-specific topic prefix for isolation.

    Args:
        e2e_topic_prefix: Unique topic prefix for test isolation.

    Yields:
        AIOKafkaConsumer connected to the configured bootstrap servers.

    Example:
        >>> @pytest.mark.asyncio
        >>> @requires_e2e_kafka
        >>> async def test_verify_events_via_consumer(
        ...     e2e_kafka_publisher,
        ...     e2e_kafka_consumer,
        ...     e2e_topic_prefix,
        ... ):
        ...     topic = f"{e2e_topic_prefix}test-topic"
        ...     await e2e_kafka_publisher.publish("test-topic", "key", {"data": 1})
        ...
        ...     e2e_kafka_consumer.subscribe([topic])
        ...     async for msg in e2e_kafka_consumer:
        ...         assert msg.value == b'{"data": 1}'
        ...         break
    """
    try:
        from aiokafka import AIOKafkaConsumer
    except ImportError:
        pytest.skip("aiokafka not installed - add to core dependencies")

    if not KAFKA_AVAILABLE:
        pytest.skip(f"Kafka not reachable at {KAFKA_BOOTSTRAP_SERVERS}")

    import os

    # Use unique consumer group per test run to avoid offset issues
    group_id = f"e2e_consumer_{e2e_topic_prefix}_{os.getpid()}"

    consumer = AIOKafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=5000,  # 5 second timeout for polling
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
# Kafka-Enabled Handler Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def promotion_handler_with_kafka(
    e2e_db_conn: Any,
    e2e_kafka_publisher: RealKafkaPublisher,
) -> AsyncGenerator[Any, None]:
    """Create a pattern promotion handler wired to real Kafka for E2E testing.

    This fixture provides the check_and_promote_patterns function with real
    PostgreSQL for database operations and real Kafka for event emission.

    Args:
        e2e_db_conn: The E2E database connection fixture.
        e2e_kafka_publisher: Real Kafka publisher fixture.

    Yields:
        A callable that wraps check_and_promote_patterns with dependencies.

    Example:
        >>> @pytest.mark.asyncio
        >>> @requires_e2e_postgres
        >>> @requires_e2e_kafka
        >>> async def test_promotion_with_real_kafka(
        ...     promotion_handler_with_kafka,
        ...     e2e_kafka_publisher,
        ... ):
        ...     # Set up provisional patterns first...
        ...     result = await promotion_handler_with_kafka()
        ...     # Verify events were published
        ...     events = e2e_kafka_publisher.published_events
        ...     assert len(events) > 0
    """
    from omniintelligence.nodes.node_pattern_promotion_effect.handlers import (
        check_and_promote_patterns,
    )

    async def _handle(
        *,
        dry_run: bool = False,
        correlation_id: UUID | None = None,
        topic_env_prefix: str = "",
    ) -> Any:
        """Wrapper that provides dependencies to check_and_promote_patterns."""
        return await check_and_promote_patterns(
            repository=e2e_db_conn,
            producer=e2e_kafka_publisher,
            dry_run=dry_run,
            correlation_id=correlation_id,
            topic_env_prefix=topic_env_prefix,
        )

    yield _handle


@pytest_asyncio.fixture
async def demotion_handler_with_kafka(
    e2e_db_conn: Any,
    e2e_kafka_publisher: RealKafkaPublisher,
) -> AsyncGenerator[Any, None]:
    """Create a pattern demotion handler wired to real Kafka for E2E testing.

    This fixture provides the check_and_demote_patterns function with real
    PostgreSQL for database operations and real Kafka for event emission.

    Args:
        e2e_db_conn: The E2E database connection fixture.
        e2e_kafka_publisher: Real Kafka publisher fixture.

    Yields:
        A callable that wraps check_and_demote_patterns with dependencies.
    """
    from omniintelligence.nodes.node_pattern_demotion_effect.handlers import (
        check_and_demote_patterns,
    )

    async def _handle(
        *,
        dry_run: bool = False,
        correlation_id: UUID | None = None,
        topic_env_prefix: str = "",
    ) -> Any:
        """Wrapper that provides dependencies to check_and_demote_patterns."""
        return await check_and_demote_patterns(
            repository=e2e_db_conn,
            producer=e2e_kafka_publisher,
            dry_run=dry_run,
            correlation_id=correlation_id,
            topic_env_prefix=topic_env_prefix,
        )

    yield _handle


# =============================================================================
# Pattern Learning Node Fixtures
# =============================================================================


@pytest.fixture
def pattern_learning_handler() -> Any:
    """Create a HandlerPatternLearning instance for E2E testing.

    This fixture instantiates the pattern learning handler which can process
    training data and produce learned/candidate patterns.

    Returns:
        HandlerPatternLearning instance ready for use.

    Example:
        >>> def test_pattern_learning(pattern_learning_handler):
        ...     result = pattern_learning_handler.handle(training_data)
        ...     assert result.success
    """
    from omniintelligence.nodes.node_pattern_learning_compute.handlers import (
        HandlerPatternLearning,
    )

    handler = HandlerPatternLearning()
    handler.initialize()
    return handler


@pytest.fixture
def pattern_learning_node() -> Any:
    """Create a NodePatternLearningCompute instance for E2E testing.

    This fixture provides the full ONEX node (thin shell) for pattern learning.
    Note: The node delegates to handlers, so for most tests, use
    pattern_learning_handler directly.

    Returns:
        NodePatternLearningCompute instance.
    """
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer

    from omniintelligence.nodes.node_pattern_learning_compute import (
        NodePatternLearningCompute,
    )

    container = ModelONEXContainer()
    return NodePatternLearningCompute(container)


# =============================================================================
# Pattern Storage Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def pattern_storage_handler(
    e2e_db_conn: Any,
) -> AsyncGenerator[Any, None]:
    """Create a pattern storage handler for E2E testing.

    This fixture provides access to the handle_store_pattern function with a
    MockPatternStore for protocol compliance. The MockPatternStore provides
    in-memory storage that implements ProtocolPatternStore.

    Note:
        This fixture uses MockPatternStore (in-memory) rather than
        AdapterPatternStore (from omniintelligence.repositories) because
        AdapterPatternStore requires a PostgresRepositoryRuntime which is
        complex to wire. For tests that need real database storage, use the
        e2e_db_conn fixture directly with SQL queries (see create_test_pattern
        in TC4 tests).

    Args:
        e2e_db_conn: The E2E database connection fixture. Passed to
            handle_store_pattern for transaction control, though
            MockPatternStore ignores it.

    Yields:
        A callable that wraps handle_store_pattern with the connection.

    Example:
        >>> async def test_storage(pattern_storage_handler, create_e2e_pattern_input):
        ...     input_data = create_e2e_pattern_input()
        ...     event = await pattern_storage_handler(input_data)
        ...     assert event.pattern_id is not None
    """
    from omniintelligence.nodes.node_pattern_storage_effect.handlers import (
        handle_store_pattern,
    )
    from omniintelligence.testing import MockPatternStore

    # MockPatternStore provides in-memory storage implementing ProtocolPatternStore.
    # For real database storage in E2E tests, use direct SQL with e2e_db_conn
    # (see create_test_pattern in test_tc4_feedback_loop.py).
    pattern_store = MockPatternStore()

    async def _handle(input_data: Any) -> Any:
        """Wrapper that provides the connection to handle_store_pattern."""
        return await handle_store_pattern(
            input_data,
            pattern_store=pattern_store,
            conn=e2e_db_conn,
        )

    yield _handle


# =============================================================================
# Feedback Loop Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def feedback_handler(e2e_db_conn: Any) -> AsyncGenerator[Any, None]:
    """Create a session outcome handler for E2E feedback loop testing.

    This fixture provides access to the record_session_outcome function
    wired to real PostgreSQL for updating pattern metrics.

    Args:
        e2e_db_conn: The E2E database connection fixture.

    Yields:
        A callable that wraps record_session_outcome with the connection.

    Example:
        >>> async def test_feedback(feedback_handler):
        ...     result = await feedback_handler(
        ...         session_id=uuid4(),
        ...         success=True,
        ...     )
        ...     assert result.status == EnumOutcomeRecordingStatus.SUCCESS
    """
    from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
        record_session_outcome,
    )

    async def _handle(
        session_id: UUID,
        success: bool,
        failure_reason: str | None = None,
        correlation_id: UUID | None = None,
    ) -> Any:
        """Wrapper that provides the repository connection."""
        return await record_session_outcome(
            session_id=session_id,
            success=success,
            failure_reason=failure_reason,
            repository=e2e_db_conn,  # asyncpg.Connection implements the protocol
            correlation_id=correlation_id,
        )

    yield _handle


# =============================================================================
# Test Data Factory Functions
# =============================================================================


def create_e2e_signature_hash(base: str | None = None) -> str:
    """Create a signature_hash with the E2E test prefix for proper cleanup.

    All E2E tests MUST use signature_hash values created by this function
    to ensure automatic cleanup after tests.

    Args:
        base: Optional base string to include in the hash. If None, uses uuid4.

    Returns:
        A signature_hash string starting with 'test_e2e_'.

    Example:
        >>> hash_value = create_e2e_signature_hash("my_pattern")
        >>> assert hash_value.startswith("test_e2e_")
    """
    if base is None:
        base = str(uuid4())
    # Create a deterministic hash from the base
    hash_suffix = hashlib.sha256(base.encode()).hexdigest()[:32]
    return f"{E2E_SIGNATURE_PREFIX}{hash_suffix}"


@pytest.fixture
def create_e2e_pattern_input() -> Any:
    """Factory fixture for creating valid pattern storage inputs for E2E tests.

    Returns a factory function that creates ModelPatternStorageInput instances
    with E2E-appropriate defaults (test prefix, test domain, etc.).

    Returns:
        Factory function for creating pattern inputs.

    Example:
        >>> def test_storage(create_e2e_pattern_input):
        ...     input1 = create_e2e_pattern_input()
        ...     input2 = create_e2e_pattern_input(confidence=0.9)
    """
    from omniintelligence.testing import create_valid_pattern_input

    def _factory(
        pattern_id: UUID | None = None,
        signature: str = "test_e2e_def_pattern_function(): return True",
        signature_hash: str | None = None,
        domain: str = E2E_DOMAIN,
        confidence: float = 0.75,
        version: int = 1,
        correlation_id: UUID | None = None,
        actor: str = "e2e_test",
        source_run_id: str = "e2e_run_001",
        tags: list[str] | None = None,
        learning_context: str = "e2e_integration_test",
    ) -> Any:
        """Create a pattern storage input with E2E test defaults."""
        if pattern_id is None:
            pattern_id = uuid4()
        if signature_hash is None:
            signature_hash = create_e2e_signature_hash(str(pattern_id))
        if correlation_id is None:
            correlation_id = uuid4()
        if tags is None:
            tags = ["e2e", "integration", "test"]

        return create_valid_pattern_input(
            pattern_id=pattern_id,
            signature=signature,
            signature_hash=signature_hash,
            domain=domain,
            confidence=confidence,
            version=version,
            correlation_id=correlation_id,
            actor=actor,
            source_run_id=source_run_id,
            tags=tags,
            learning_context=learning_context,
        )

    return _factory


@pytest.fixture
def create_e2e_training_data() -> Any:
    """Factory fixture for creating training data for pattern learning tests.

    Returns a factory function that creates TrainingDataItemDict sequences
    suitable for the pattern learning pipeline.

    Returns:
        Factory function for creating training data.

    Example:
        >>> def test_learning(create_e2e_training_data, pattern_learning_handler):
        ...     data = create_e2e_training_data(count=5)
        ...     result = pattern_learning_handler.handle(data)
    """

    def _factory(
        count: int = 3,
        pattern_type: str = "code",
        base_code: str = "def example_function(): pass",
        labels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Create training data items for pattern learning.

        Args:
            count: Number of training items to create.
            pattern_type: Type of pattern (code, error, workflow, etc.).
            base_code: Base code snippet to use (with variations).
            labels: Labels to apply to items.

        Returns:
            List of TrainingDataItemDict instances.
        """
        if labels is None:
            labels = ["e2e_test", "integration"]

        items: list[dict[str, Any]] = []
        for i in range(count):
            item: dict[str, Any] = {
                "item_id": f"e2e_item_{i}_{uuid4().hex[:8]}",
                "code_snippet": f"{base_code}  # variant {i}",
                "pattern_type": pattern_type,
                "labels": labels,
                "metadata": {
                    "source": "e2e_test",
                    "variant": i,
                },
            }
            items.append(item)
        return items

    return _factory


# =============================================================================
# Cleanup Fixture (explicit)
# =============================================================================


@pytest_asyncio.fixture
async def cleanup_e2e_patterns(
    e2e_db_conn: Any,
    signature_hash_available: bool,
) -> AsyncGenerator[None, None]:
    """Explicit cleanup fixture that removes E2E test patterns before and after test.

    Use this fixture when you need guaranteed cleanup even if the main fixture
    fails. It runs cleanup both before (to handle leftover data from failed tests)
    and after the test.

    Args:
        e2e_db_conn: The E2E database connection fixture.
        signature_hash_available: Session-scoped fixture indicating if signature_hash
            column exists in the database schema.

    Yields:
        None - cleanup happens as side effect.
    """
    # Pre-test cleanup (in case previous test failed)
    await _cleanup_e2e_test_data(e2e_db_conn, signature_hash_available)

    yield

    # Post-test cleanup
    await _cleanup_e2e_test_data(e2e_db_conn, signature_hash_available)


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def e2e_correlation_id() -> UUID:
    """Provide a unique correlation ID for E2E test tracing.

    Returns:
        A new UUID for correlation tracking.
    """
    return uuid4()


@pytest.fixture
def e2e_session_id() -> UUID:
    """Provide a unique session ID for E2E feedback loop tests.

    Returns:
        A new UUID for session identification.
    """
    return uuid4()


@pytest.fixture
def e2e_timestamp() -> datetime:
    """Provide a consistent timestamp for E2E test assertions.

    Returns:
        Current UTC datetime.
    """
    return datetime.now(UTC)


# =============================================================================
# Session-Scoped Kafka Topic Cleanup
# =============================================================================


@pytest_asyncio.fixture(scope="session", autouse=True)
async def e2e_kafka_session_cleanup() -> AsyncGenerator[None, None]:
    """Session-scoped fixture that cleans up orphaned E2E Kafka topics.

    This fixture runs AUTOMATICALLY at the END of the test session (autouse=True)
    and deletes ALL topics matching the E2E test prefix pattern (e2e_test_*).
    This catches:
    - Topics from tests that crashed before cleanup
    - Topics from previous test runs that were never cleaned up
    - Topics created by tests that didn't use e2e_kafka_publisher

    The cleanup is graceful - failures are logged but do not cause test failures.

    Note:
        This fixture yields immediately and only performs cleanup on teardown.
        It's safe to run even if no Kafka operations occur in the test session.
    """
    # Yield immediately - cleanup happens on teardown
    yield

    # Session teardown: clean up ALL orphaned E2E test topics
    if not KAFKA_AVAILABLE:
        _cleanup_logger.debug(
            "E2E session cleanup: Kafka not available, skipping topic cleanup"
        )
        return

    _cleanup_logger.info("E2E session cleanup: scanning for orphaned test topics...")

    try:
        orphaned_topics = await list_e2e_test_topics(prefix="e2e_test_")
        if orphaned_topics:
            _cleanup_logger.info(
                "E2E session cleanup: found %d orphaned topics: %s",
                len(orphaned_topics),
                orphaned_topics,
            )
            deleted, failed = await delete_kafka_topics(orphaned_topics)
            _cleanup_logger.info(
                "E2E session cleanup complete: deleted=%d, failed=%d",
                len(deleted),
                len(failed),
            )
        else:
            _cleanup_logger.info("E2E session cleanup: no orphaned topics found")
    except Exception as e:
        # Graceful degradation - log but don't fail
        _cleanup_logger.warning(
            "E2E session cleanup: error during orphan topic cleanup: %s", e
        )


# Note: The synchronous e2e_cleanup_on_session_end fixture was removed because
# it created a new event loop which conflicts with pytest-asyncio's loop management.
# The async e2e_kafka_session_cleanup fixture (above) handles session cleanup properly.


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "E2E_DOMAIN",
    "E2E_SIGNATURE_CONTAINS",
    "E2E_SIGNATURE_PREFIX",
    "E2E_TEST_PREFIX",
    # Utility functions
    "_check_signature_hash_column_exists",
    "cleanup_e2e_patterns",
    # Factory fixtures
    "create_e2e_pattern_input",
    "create_e2e_signature_hash",
    "create_e2e_training_data",
    "delete_kafka_topics",
    # Handler fixtures
    "demotion_handler_with_kafka",
    # Utility fixtures
    "e2e_correlation_id",
    # Database fixtures
    "e2e_db_conn",
    "e2e_db_conn_with_signature_hash",
    # Kafka fixtures
    "e2e_kafka_consumer",
    "e2e_kafka_producer",
    "e2e_kafka_publisher",
    "e2e_kafka_session_cleanup",
    "e2e_session_id",
    "e2e_timestamp",
    "e2e_topic_prefix",
    "feedback_handler",
    "list_e2e_test_topics",
    "mock_kafka",
    "pattern_learning_handler",
    "pattern_learning_node",
    "pattern_storage_handler",
    "promotion_handler_with_kafka",
    # Skip markers
    "requires_e2e_kafka",
    "requires_e2e_postgres",
    "signature_hash_available",
    # Kafka consumer utilities
    "wait_for_message",
]
