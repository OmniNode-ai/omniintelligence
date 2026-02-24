# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_pattern_projection_effect unit tests.

Provides mock implementations of ProtocolPatternQueryStore and
ProtocolKafkaPublisher for testing projection handler without real
infrastructure.

Reference:
    - OMN-2424: Pattern projection snapshot publisher
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternQueryStore

# =============================================================================
# Mock Implementations
# =============================================================================


class MockPatternQueryStore:
    """Mock implementation of ProtocolPatternQueryStore for testing.

    Returns configurable rows from query_patterns() to simulate the
    pattern store without requiring a real database connection.

    Attributes:
        rows: Rows to return from query_patterns (paginated automatically).
        query_calls: List of kwargs passed to each query_patterns() call.
        simulate_error: If set, raises this exception on query_patterns().
    """

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.rows: list[dict[str, Any]] = rows or []
        self.query_calls: list[dict[str, Any]] = []
        self.simulate_error: Exception | None = None

    async def query_patterns(
        self,
        *,
        domain: str | None,
        language: str | None,
        min_confidence: float,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Return a page of rows, or raise if simulate_error is set."""
        self.query_calls.append(
            {
                "domain": domain,
                "language": language,
                "min_confidence": min_confidence,
                "limit": limit,
                "offset": offset,
            }
        )
        if self.simulate_error is not None:
            raise self.simulate_error

        # Simulate pagination
        return self.rows[offset : offset + limit]

    def reset(self) -> None:
        """Reset all state for test isolation."""
        self.rows.clear()
        self.query_calls.clear()
        self.simulate_error = None


class MockKafkaPublisher:
    """Mock Kafka publisher that records published events.

    Attributes:
        published_events: List of (topic, key, value) tuples.
        simulate_error: If set, raises this exception on publish().
    """

    def __init__(self) -> None:
        self.published_events: list[tuple[str, str, dict[str, Any]]] = []
        self.simulate_error: Exception | None = None

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        if self.simulate_error is not None:
            raise self.simulate_error
        self.published_events.append((topic, key, value))

    def reset(self) -> None:
        self.published_events.clear()
        self.simulate_error = None


# =============================================================================
# Protocol Compliance Verification
# =============================================================================

assert isinstance(MockPatternQueryStore(), ProtocolPatternQueryStore)
assert isinstance(MockKafkaPublisher(), ProtocolKafkaPublisher)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_query_store() -> MockPatternQueryStore:
    """Provide a fresh mock pattern query store for each test."""
    return MockPatternQueryStore()


@pytest.fixture
def mock_producer() -> MockKafkaPublisher:
    """Provide a fresh mock Kafka publisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_snapshot_at() -> datetime:
    """Fixed snapshot timestamp."""
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


def make_pattern_row(
    pattern_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    signature: str = "test pattern",
    signature_hash: str = "abc123",
    domain_id: str = "python",
    status: str = "validated",
    confidence: float = 0.9,
    quality_score: float = 0.85,
    version: int = 1,
    is_current: bool = True,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a minimal pattern row dict matching ModelPatternSummary fields."""
    return {
        "id": pattern_id,
        "pattern_signature": signature,
        "signature_hash": signature_hash,
        "domain_id": domain_id,
        "status": status,
        "confidence": confidence,
        "quality_score": quality_score,
        "version": version,
        "is_current": is_current,
        "created_at": created_at or datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
    }
