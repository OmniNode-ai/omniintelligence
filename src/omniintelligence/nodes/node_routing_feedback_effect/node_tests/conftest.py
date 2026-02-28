# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_routing_feedback_effect node tests.

Provides mock implementations of ProtocolPatternRepository and
ProtocolKafkaPublisher for unit testing routing feedback processing
without requiring real infrastructure.

Reference:
    - OMN-2366: Add routing.feedback consumer in omniintelligence
    - OMN-2935: Fix routing feedback loop — subscribe to routing-outcome-raw.v1
    - OMN-2622: Fold routing-feedback-skipped.v1 into routing-feedback.v1
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from omniintelligence.nodes.node_routing_feedback_effect.models import (
    ModelRoutingFeedbackPayload,
)

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

    The upsert behaviour mirrors the real SQL (OMN-2622 schema):
    - First call for a given session_id inserts a row.
    - Subsequent calls update outcome + processed_at (no duplicate rows).
    - Skipped events (feedback_status == "skipped") do not call execute().

    Attributes:
        rows: In-memory store keyed by session_id.
        queries_executed: History of (query, args) tuples for verification.
        simulate_db_error: If set, raises this exception on execute.
    """

    def __init__(self) -> None:
        # Key: session_id
        self.rows: dict[str, dict[str, Any]] = {}
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

        # Handle upsert: INSERT ... ON CONFLICT (session_id) DO UPDATE
        if "INSERT INTO routing_feedback_scores" in query:
            if len(args) >= 3:
                session_id = args[0]
                outcome = args[1]
                processed_at = args[2]
                if session_id in self.rows:
                    # ON CONFLICT DO UPDATE: update outcome + processed_at
                    self.rows[session_id].update(
                        {
                            "outcome": outcome,
                            "processed_at": processed_at,
                        }
                    )
                    return "UPDATE 1"
                else:
                    self.rows[session_id] = {
                        "session_id": session_id,
                        "outcome": outcome,
                        "processed_at": processed_at,
                        "created_at": processed_at,
                    }
                    return "INSERT 0 1"

        return "EXECUTE 0"

    def get_row(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve stored row for assertion in tests."""
        return self.rows.get(session_id)

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

    Supports two failure modes:
    - ``simulate_publish_error``: Raises on every ``publish()`` call.
    - ``publish_side_effects``: List of ``Exception | None`` consumed in order.
      ``None`` means succeed (append to ``published``); an ``Exception`` means
      raise for that specific call.  Once the list is exhausted, subsequent
      calls succeed normally.  Use this for "fail first call, succeed second"
      scenarios (e.g. main topic fails -> DLQ succeeds).

    Attributes:
        published: List of (topic, key, value) tuples for published events.
        simulate_publish_error: If set, raises this exception on every publish.
        publish_side_effects: Per-call side effects (consumed left-to-right).
    """

    def __init__(self) -> None:
        self.published: list[tuple[str, str, dict[str, Any]]] = []
        self.simulate_publish_error: Exception | None = None
        self.publish_side_effects: list[Exception | None] = []

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        # Per-call side effects take priority over the blanket error flag.
        if self.publish_side_effects:
            effect = self.publish_side_effects.pop(0)
            if effect is not None:
                raise effect
            self.published.append((topic, key, value))
            return

        if self.simulate_publish_error is not None:
            raise self.simulate_publish_error
        self.published.append((topic, key, value))


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
def sample_routing_feedback_event_produced(
    sample_session_id: str,
) -> ModelRoutingFeedbackPayload:
    """Routing-feedback event with feedback_status='produced'."""
    return ModelRoutingFeedbackPayload(
        session_id=sample_session_id,
        outcome="success",
        feedback_status="produced",
        skip_reason=None,
        emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_routing_feedback_event_skipped(
    sample_session_id: str,
) -> ModelRoutingFeedbackPayload:
    """Routing-feedback event with feedback_status='skipped'."""
    return ModelRoutingFeedbackPayload(
        session_id=sample_session_id,
        outcome="unknown",
        feedback_status="skipped",
        skip_reason="NO_INJECTION",
        emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
    )


# Legacy fixture aliases for test backward compatibility.
@pytest.fixture
def sample_routing_feedback_event_success(
    sample_routing_feedback_event_produced: ModelRoutingFeedbackPayload,
) -> ModelRoutingFeedbackPayload:
    """Alias for sample_routing_feedback_event_produced."""
    return sample_routing_feedback_event_produced


@pytest.fixture
def sample_routing_feedback_event_failed(
    sample_session_id: str,
) -> ModelRoutingFeedbackPayload:
    """Routing-feedback event with outcome='failed' and feedback_status='produced'."""
    return ModelRoutingFeedbackPayload(
        session_id=sample_session_id,
        outcome="failed",
        feedback_status="produced",
        skip_reason=None,
        emitted_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC),
    )
