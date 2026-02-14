# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for pattern_lifecycle_effect node tests.

Provides mock implementations of ProtocolPatternRepository,
ProtocolIdempotencyStore, and ProtocolKafkaPublisher for unit testing
lifecycle transitions without requiring real infrastructure.

Reference:
    - OMN-1805: Pattern lifecycle effect node with atomic projections
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any  # any-ok: test mocks implement asyncpg Protocol with *args: Any
from uuid import UUID

import pytest

from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    ProtocolIdempotencyStore,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

# =============================================================================
# Mock asyncpg.Record Implementation
# =============================================================================


class MockRecord(dict[str, Any]):
    """Dict-like object that mimics asyncpg.Record behavior.

    asyncpg.Record supports both dict-style access (record["column"]) and
    attribute access (record.column). This mock provides the same interface
    for testing.
    """

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to columns."""
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Record has no column '{name}'")


# =============================================================================
# Mock Protocol Implementations
# =============================================================================


class MockPatternRepository:
    """Mock implementation of ProtocolPatternRepository for testing.

    Simulates a pattern database with in-memory storage. Supports
    asyncpg-style operations for testing transition handlers without
    a real database connection.

    The repository tracks:
    - patterns: In-memory pattern storage
    - queries_executed: History of SQL queries for verification
    - inserted_audits: Audit records inserted during transitions

    Attributes:
        patterns: Map of pattern_id to pattern data.
        queries_executed: List of (query, args) tuples.
        inserted_audits: List of audit record data.
        simulate_db_error: If set, raises this exception on execute.
    """

    def __init__(
        self,
        patterns: dict[UUID, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the mock repository.

        Args:
            patterns: Initial pattern data, keyed by pattern_id.
        """
        self.patterns: dict[UUID, dict[str, Any]] = patterns or {}
        self.queries_executed: list[tuple[str, tuple[Any, ...]]] = []
        self.inserted_audits: list[dict[str, Any]] = []
        self.simulate_db_error: Exception | None = None
        self._status_updates: dict[UUID, str] = {}

    def add_pattern(
        self,
        pattern_id: UUID,
        status: str = "provisional",
        **extra: Any,
    ) -> None:
        """Add a pattern to the mock database.

        Args:
            pattern_id: Unique identifier for the pattern.
            status: Current status (e.g., "provisional", "validated").
            **extra: Additional pattern fields.
        """
        self.patterns[pattern_id] = {
            "id": pattern_id,
            "status": status,
            **extra,
        }

    async def fetch(
        self,
        query: str,
        *args: Any,
    ) -> list[Mapping[str, Any]]:
        """Execute a query and return all results as Record objects.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            List of record objects with dict-like access to columns.
        """
        self.queries_executed.append((query, args))
        return []

    async def fetchrow(
        self,
        query: str,
        *args: Any,
    ) -> Mapping[str, Any] | None:
        """Execute a query and return first row, or None.

        Simulates the GET_PATTERN_STATUS query for testing.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            Single record or None if no rows.
        """
        self.queries_executed.append((query, args))

        # Handle: Get pattern by ID (SQL_GET_PATTERN_STATUS)
        if "SELECT" in query.upper() and "learned_patterns" in query.lower():
            if args:
                pattern_id = args[0]
                pattern = self.patterns.get(pattern_id)
                if pattern is not None:
                    return MockRecord(pattern)
        return None

    async def execute(
        self,
        query: str,
        *args: Any,
    ) -> str:
        """Execute a query and return the status string.

        Simulates UPDATE and INSERT operations for testing.

        Args:
            query: SQL query with $1, $2, etc. positional placeholders.
            *args: Positional arguments corresponding to placeholders.

        Returns:
            Status string from PostgreSQL (e.g., "UPDATE 1", "INSERT 0 1").

        Raises:
            Exception: If simulate_db_error is set.
        """
        self.queries_executed.append((query, args))

        # Simulate database error if configured
        if self.simulate_db_error is not None:
            raise self.simulate_db_error

        # Handle: UPDATE pattern status with guard
        if "UPDATE learned_patterns" in query:
            if len(args) >= 4:
                pattern_id = args[0]
                to_status = args[1]
                # transition_at = args[2]
                from_status = args[3]

                pattern = self.patterns.get(pattern_id)
                if pattern is not None and pattern.get("status") == from_status:
                    # Status guard passes - update the pattern
                    pattern["status"] = to_status
                    self._status_updates[pattern_id] = to_status
                    return "UPDATE 1"
            return "UPDATE 0"  # Status guard failed

        # Handle: INSERT audit record
        if "INSERT INTO pattern_lifecycle_transitions" in query:
            self.inserted_audits.append({"query": query, "args": args})
            return "INSERT 0 1"

        return "EXECUTE 0"

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.patterns.clear()
        self.queries_executed.clear()
        self.inserted_audits.clear()
        self._status_updates.clear()
        self.simulate_db_error = None


class MockIdempotencyStore:
    """Mock implementation of ProtocolIdempotencyStore for testing.

    Simulates idempotency key tracking with in-memory storage.
    Tracks which request_ids have been processed to prevent duplicates.

    Attributes:
        processed_ids: Set of request_ids that have been processed.
        recorded_ids: List of request_ids in the order they were recorded.
    """

    def __init__(
        self,
        processed_ids: set[UUID] | None = None,
    ) -> None:
        """Initialize the mock idempotency store.

        Args:
            processed_ids: Initial set of already-processed request_ids.
        """
        self.processed_ids: set[UUID] = processed_ids or set()
        self.recorded_ids: list[UUID] = []

    async def check_and_record(self, request_id: UUID) -> bool:
        """Check if request_id exists, and if not, record it atomically.

        Args:
            request_id: The idempotency key to check and record.

        Returns:
            True if this is a DUPLICATE (request_id already existed).
            False if this is NEW (request_id was just recorded).
        """
        if request_id in self.processed_ids:
            return True  # Duplicate
        self.processed_ids.add(request_id)
        self.recorded_ids.append(request_id)
        return False  # New

    async def exists(self, request_id: UUID) -> bool:
        """Check if request_id exists without recording.

        Args:
            request_id: The idempotency key to check.

        Returns:
            True if request_id exists, False otherwise.
        """
        return request_id in self.processed_ids

    async def record(self, request_id: UUID) -> None:
        """Record a request_id as processed (without checking).

        This should be called AFTER successful operation completion to
        prevent replay of the same request_id.

        Args:
            request_id: The idempotency key to record.

        Note:
            If the request_id already exists, this is a no-op (idempotent).
        """
        if request_id not in self.processed_ids:
            self.processed_ids.add(request_id)
            self.recorded_ids.append(request_id)

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.processed_ids.clear()
        self.recorded_ids.clear()


class MockKafkaPublisher:
    """Mock implementation of ProtocolKafkaPublisher for testing.

    Tracks all published events for verification in tests.

    Attributes:
        published_events: List of (topic, key, value) tuples.
        simulate_error: If set, raises this exception on publish.
    """

    def __init__(self) -> None:
        """Initialize with empty published events list."""
        self.published_events: list[tuple[str, str, dict[str, Any]]] = []
        self.simulate_error: Exception | None = None

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Record the published event.

        Args:
            topic: Target Kafka topic name.
            key: Message key for partitioning.
            value: Event payload as a dictionary.

        Raises:
            Exception: If simulate_error is set.
        """
        if self.simulate_error is not None:
            raise self.simulate_error
        self.published_events.append((topic, key, value))

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.published_events.clear()
        self.simulate_error = None


# =============================================================================
# Protocol Compliance Verification
# =============================================================================

# Verify mock implementations conform to protocols at import time
assert isinstance(MockPatternRepository(), ProtocolPatternRepository)
assert isinstance(MockIdempotencyStore(), ProtocolIdempotencyStore)
assert isinstance(MockKafkaPublisher(), ProtocolKafkaPublisher)


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_repository() -> MockPatternRepository:
    """Provide a fresh mock pattern repository for each test."""
    return MockPatternRepository()


@pytest.fixture
def mock_idempotency_store() -> MockIdempotencyStore:
    """Provide a fresh mock idempotency store for each test."""
    return MockIdempotencyStore()


@pytest.fixture
def mock_producer() -> MockKafkaPublisher:
    """Provide a fresh mock Kafka publisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Fixed pattern ID for deterministic tests."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_request_id() -> UUID:
    """Fixed request ID for idempotency tests."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_transition_at() -> datetime:
    """Fixed timestamp for transition tests."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
