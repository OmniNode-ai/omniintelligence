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
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from omniintelligence.nodes.node_routing_feedback_effect.models import (
    ModelSessionRawOutcomePayload,
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

    The upsert behaviour mirrors the real SQL (OMN-2935 schema):
    - First call for a given session_id inserts a row.
    - Subsequent calls update all raw signal fields + processed_at (no duplicate rows).

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
            if len(args) >= 8:
                session_id = args[0]
                injection_occurred = args[1]
                patterns_injected_count = args[2]
                tool_calls_count = args[3]
                duration_ms = args[4]
                agent_selected = args[5]
                routing_confidence = args[6]
                processed_at = args[7]
                if session_id in self.rows:
                    # ON CONFLICT DO UPDATE: update raw signal fields + processed_at
                    self.rows[session_id].update(
                        {
                            "injection_occurred": injection_occurred,
                            "patterns_injected_count": patterns_injected_count,
                            "tool_calls_count": tool_calls_count,
                            "duration_ms": duration_ms,
                            "agent_selected": agent_selected,
                            "routing_confidence": routing_confidence,
                            "processed_at": processed_at,
                        }
                    )
                    return "UPDATE 1"
                else:
                    self.rows[session_id] = {
                        "session_id": session_id,
                        "injection_occurred": injection_occurred,
                        "patterns_injected_count": patterns_injected_count,
                        "tool_calls_count": tool_calls_count,
                        "duration_ms": duration_ms,
                        "agent_selected": agent_selected,
                        "routing_confidence": routing_confidence,
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
def sample_agent_selected() -> str:
    """Fixed agent name for deterministic tests."""
    return "omniarchon"


@pytest.fixture
def sample_routing_confidence() -> float:
    """Fixed routing confidence for deterministic tests."""
    return 0.91


@pytest.fixture
def sample_raw_outcome_event_with_injection(
    sample_session_id: str,
    sample_agent_selected: str,
    sample_routing_confidence: float,
) -> ModelSessionRawOutcomePayload:
    """Routing-outcome-raw event with injection_occurred=True."""
    return ModelSessionRawOutcomePayload(
        session_id=sample_session_id,
        injection_occurred=True,
        patterns_injected_count=3,
        tool_calls_count=12,
        duration_ms=45200,
        agent_selected=sample_agent_selected,
        routing_confidence=sample_routing_confidence,
        emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_raw_outcome_event_no_injection(
    sample_session_id: str,
) -> ModelSessionRawOutcomePayload:
    """Routing-outcome-raw event with injection_occurred=False."""
    return ModelSessionRawOutcomePayload(
        session_id=sample_session_id,
        injection_occurred=False,
        patterns_injected_count=0,
        tool_calls_count=5,
        duration_ms=12000,
        agent_selected="",
        routing_confidence=0.0,
        emitted_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
    )


# Keep legacy fixture names as aliases for backward compatibility within test file.
@pytest.fixture
def sample_routing_feedback_event_success(
    sample_raw_outcome_event_with_injection: ModelSessionRawOutcomePayload,
) -> ModelSessionRawOutcomePayload:
    """Alias for sample_raw_outcome_event_with_injection."""
    return sample_raw_outcome_event_with_injection


@pytest.fixture
def sample_routing_feedback_event_failed(
    sample_raw_outcome_event_no_injection: ModelSessionRawOutcomePayload,
) -> ModelSessionRawOutcomePayload:
    """Alias for sample_raw_outcome_event_no_injection."""
    return sample_raw_outcome_event_no_injection
