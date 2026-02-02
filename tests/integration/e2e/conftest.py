# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Fixtures for E2E integration tests of the pattern learning pipeline.

This module provides pytest fixtures for end-to-end testing of the pattern
learning pipeline using:
- Real PostgreSQL (192.168.86.200:5436, database: omninode_bridge) for data integrity
- MockKafkaPublisher for event assertions (no real Kafka needed)

Test Coverage:
    - Pattern learning compute (TC1-TC3)
    - Pattern storage to learned_patterns table
    - Feedback loop updates (TC4)

Infrastructure Configuration (from .env):
    - PostgreSQL: 192.168.86.200:5436 (database: omninode_bridge)

Reference:
    - OMN-1800: E2E integration tests for pattern learning pipeline
    - learned_patterns.repository.yaml: Repository contract for pattern storage
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

# Import shared fixtures and utilities from root integration conftest
from tests.integration.conftest import (
    POSTGRES_AVAILABLE,
    POSTGRES_COMMAND_TIMEOUT,
    POSTGRES_DATABASE,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
    MockKafkaPublisher,
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

E2E_DOMAIN: str = "code_generation"
"""Domain used for E2E test patterns. Uses existing domain from domain_taxonomy to satisfy FK."""


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

    This function detects whether migration 008_add_signature_hash has been applied.

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
    not POSTGRES_AVAILABLE or not POSTGRES_PASSWORD,
    reason=f"PostgreSQL not available at {POSTGRES_HOST}:{POSTGRES_PORT} or password not set",
)
"""Skip marker for E2E tests requiring real PostgreSQL connectivity."""


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
    if not POSTGRES_PASSWORD:
        return False

    try:
        import asyncpg
    except ImportError:
        return False

    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
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
    - Real PostgreSQL connection to 192.168.86.200:5436
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
    if not POSTGRES_PASSWORD:
        pytest.skip(
            "POSTGRES_PASSWORD not set - add to .env file or environment. "
            "Expected .env at project root"
        )

    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed - add to dev dependencies")

    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            timeout=30,
            command_timeout=POSTGRES_COMMAND_TIMEOUT,
        )
    except (OSError, Exception) as e:
        pytest.skip(
            f"Database connection failed: {e}. "
            f"Target: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
        )

    try:
        yield conn
    finally:
        # Cleanup: Remove all E2E test patterns
        try:
            await _cleanup_e2e_test_data(conn, signature_hash_available)
        except Exception as cleanup_error:
            # Log but don't fail the test on cleanup error
            print(f"Warning: E2E cleanup failed: {cleanup_error}")
        finally:
            await conn.close()


@pytest_asyncio.fixture
async def e2e_db_conn_with_signature_hash(
    e2e_db_conn: Any,
    signature_hash_available: bool,
) -> AsyncGenerator[Any, None]:
    """Database connection fixture that requires signature_hash column.

    This fixture wraps e2e_db_conn and skips the test if the signature_hash
    column doesn't exist (migration 008 not applied).

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
            "Run migration 008_add_signature_hash.sql first."
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
       - pattern_signature LIKE 'test_e2e_%' (fallback)

    Note: Uses signature prefix ONLY for cleanup - does NOT delete by domain_id
    since E2E tests use existing production domains (e.g., code_generation).

    The function is backward compatible with databases that don't have the
    signature_hash column (migration 008 not applied).

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
    # Note: Only uses signature prefix for cleanup to avoid deleting production data
    if use_signature_hash:
        # Use signature_hash (preferred - migration 008 applied)
        select_query = """
            SELECT id FROM learned_patterns
            WHERE signature_hash LIKE $1
        """
        delete_query = """
            DELETE FROM learned_patterns
            WHERE signature_hash LIKE $1
        """
    else:
        # Fallback: use pattern_signature (migration 008 not applied)
        select_query = """
            SELECT id FROM learned_patterns
            WHERE pattern_signature LIKE $1
        """
        delete_query = """
            DELETE FROM learned_patterns
            WHERE pattern_signature LIKE $1
        """

    # First, get the IDs of patterns we're going to delete
    pattern_ids = await conn.fetch(
        select_query,
        f"{E2E_SIGNATURE_PREFIX}%",
    )

    # Delete pattern_injections that reference these patterns
    # Uses array overlap operator (&&) to find injections containing any of these patterns
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
    result = await conn.execute(
        delete_query,
        f"{E2E_SIGNATURE_PREFIX}%",
    )
    # Parse "DELETE N" to get count
    if result and result.startswith("DELETE "):
        return int(result.split()[1])
    return 0


# =============================================================================
# Mock Kafka Fixture
# =============================================================================


@pytest.fixture
def mock_kafka() -> MockKafkaPublisher:
    """Create a MockKafkaPublisher for testing event emission without real Kafka.

    The mock records all published events for assertion in tests.
    Events are stored as (topic, key, value) tuples.

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
    """Create a pattern storage handler with real PostgreSQL for E2E testing.

    This fixture provides access to the handle_store_pattern function wired
    to the real PostgreSQL database for storing patterns.

    Args:
        e2e_db_conn: The E2E database connection fixture.

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

    # Create adapter that uses real DB operations
    # For E2E we use the actual AdapterPatternStore if available,
    # otherwise fall back to MockPatternStore for the protocol
    try:
        from omniintelligence.adapters.adapter_pattern_store import AdapterPatternStore

        # AdapterPatternStore manages its own connection pool
        pattern_store = AdapterPatternStore()
    except ImportError:
        # Fallback to mock if adapter not available
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
        signature: str = "def e2e_test_function(): return True",
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
# Exports
# =============================================================================

__all__ = [
    "E2E_DOMAIN",
    "E2E_SIGNATURE_PREFIX",
    "E2E_TEST_PREFIX",
    "_check_signature_hash_column_exists",
    "cleanup_e2e_patterns",
    "create_e2e_pattern_input",
    "create_e2e_signature_hash",
    "create_e2e_training_data",
    "e2e_correlation_id",
    "e2e_db_conn",
    "e2e_db_conn_with_signature_hash",
    "e2e_session_id",
    "e2e_timestamp",
    "feedback_handler",
    "mock_kafka",
    "pattern_learning_handler",
    "pattern_learning_node",
    "pattern_storage_handler",
    "requires_e2e_postgres",
    "signature_hash_available",
]
