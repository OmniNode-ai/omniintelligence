# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_routing_feedback_effect node tests.

Provides mock implementations of ProtocolPatternRepository and
ProtocolKafkaPublisher for unit testing routing feedback processing
without requiring real infrastructure.

Reference:
    - OMN-2366: Add routing.feedback consumer in omniintelligence
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from omniintelligence.nodes.node_routing_feedback_effect.models import (
    ModelRoutingFeedbackEvent,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository

# =============================================================================
# Mock asyncpg.Record Implementation
# =============================================================================


class MockRecord(dict[str, Any]):
    """Dict-like object that mimics asyncpg.Record behavior."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Record has no column '{name}'")


# =============================================================================
# Mock Protocol Implementations
# =============================================================================


class MockRoutingFeedbackRepository:
    """Mock implementation of ProtocolPatternRepository for testing.

    Simulates a PostgreSQL database with in-memory storage, supporting
    the specific SQL operations used by the routing feedback handler.

    The upsert behaviour mirrors the real SQL:
    - First call for a given (session_id, correlation_id, stage) inserts a row.
    - Subsequent calls update ``processed_at`` (no duplicate rows).

    Attributes:
        rows: In-memory store keyed by (session_id, correlation_id, stage).
        queries_executed: History of (query, args) tuples for verification.
        simulate_db_error: If set, raises this exception on execute.
    """

    def __init__(self) -> None:
        # Key: (session_id, correlation_id, stage)
        self.rows: dict[tuple[str, UUID, str], dict[str, Any]] = {}
        self.queries_executed: list[tuple[str, tuple[Any, ...]]] = []
        self.simulate_db_error: Exception | None = None

    async def fetch(
        self,
        query: str,
        *args: Any,
    ) -> list[Mapping[str, Any]]:
        self.queries_executed.append((query, args))
        return []

    async def fetchrow(
        self,
        query: str,
        *args: Any,
    ) -> Mapping[str, Any] | None:
        self.queries_executed.append((query, args))
        return None

    async def execute(
        self,
        query: str,
        *args: Any,
    ) -> str:
        self.queries_executed.append((query, args))

        if self.simulate_db_error is not None:
            raise self.simulate_db_error

        # Handle upsert: INSERT ... ON CONFLICT
        if "INSERT INTO routing_feedback_scores" in query:
            if len(args) >= 5:
                session_id = args[0]
                correlation_id = args[1]
                stage = args[2]
                outcome = args[3]
                processed_at = args[4]
                key = (session_id, correlation_id, stage)
                if key in self.rows:
                    # ON CONFLICT DO UPDATE: update processed_at only
                    self.rows[key]["processed_at"] = processed_at
                else:
                    self.rows[key] = {
                        "session_id": session_id,
                        "correlation_id": correlation_id,
                        "stage": stage,
                        "outcome": outcome,
                        "processed_at": processed_at,
                        "created_at": processed_at,
                    }
                return "INSERT 0 1"

        return "EXECUTE 0"

    def get_row(
        self, session_id: str, correlation_id: UUID, stage: str
    ) -> dict[str, Any] | None:
        """Retrieve stored row for assertion in tests."""
        return self.rows.get((session_id, correlation_id, stage))

    def row_count(self) -> int:
        """Return number of unique rows stored."""
        return len(self.rows)

    def reset(self) -> None:
        """Reset all storage for test isolation."""
        self.rows.clear()
        self.queries_executed.clear()
        self.simulate_db_error = None


class MockKafkaPublisher:
    """Mock implementation of ProtocolKafkaPublisher for testing.

    Captures published events for assertion in tests.

    Attributes:
        published: List of (topic, key, value) tuples for published events.
        simulate_publish_error: If set, raises this exception on publish.
    """

    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict[str, Any]]] = []
        self.simulate_publish_error: Exception | None = None

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        if self.simulate_publish_error is not None:
            raise self.simulate_publish_error
        self.published.append((topic, key, value))


# Protocol compliance verification at import time
assert isinstance(MockRoutingFeedbackRepository(), ProtocolPatternRepository)
assert isinstance(MockKafkaPublisher(), ProtocolKafkaPublisher)


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_repository() -> MockRoutingFeedbackRepository:
    """Provide a fresh mock repository for each test."""
    return MockRoutingFeedbackRepository()


@pytest.fixture
def mock_publisher() -> MockKafkaPublisher:
    """Provide a fresh mock Kafka publisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def sample_session_id() -> str:
    """Fixed session ID string for deterministic tests."""
    return "test-session-abc"


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_stage() -> str:
    """Default stage value."""
    return "session_end"


@pytest.fixture
def sample_routing_feedback_event_success(
    sample_session_id: str,
    sample_correlation_id: UUID,
    sample_stage: str,
) -> ModelRoutingFeedbackEvent:
    """Routing feedback event with outcome=success."""
    return ModelRoutingFeedbackEvent(
        session_id=sample_session_id,
        correlation_id=sample_correlation_id,
        stage=sample_stage,
        outcome="success",
        emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_routing_feedback_event_failed(
    sample_session_id: str,
    sample_correlation_id: UUID,
    sample_stage: str,
) -> ModelRoutingFeedbackEvent:
    """Routing feedback event with outcome=failed."""
    return ModelRoutingFeedbackEvent(
        session_id=sample_session_id,
        correlation_id=sample_correlation_id,
        stage=sample_stage,
        outcome="failed",
        emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
    )
