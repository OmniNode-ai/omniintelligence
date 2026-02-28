# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_llm_routing_decision_effect node tests.

Provides mock implementations of ProtocolPatternRepository and
ProtocolKafkaPublisher for unit testing LLM routing decision processing
without requiring real infrastructure.

Reference:
    - OMN-2939: Bifrost feedback loop — add LLM routing decision consumer in omniintelligence
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from omniintelligence.nodes.node_llm_routing_decision_effect.models import (
    ModelLlmRoutingDecisionEvent,
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


class MockLlmRoutingDecisionRepository:
    """Mock implementation of ProtocolPatternRepository for testing.

    Simulates a PostgreSQL database with in-memory storage, supporting
    the specific SQL operations used by the LLM routing decision handler.

    The upsert behaviour mirrors the real SQL:
    - First call for a given (session_id, correlation_id) inserts a row.
    - Subsequent calls update ``processed_at`` (no duplicate rows).

    Attributes:
        rows: In-memory store keyed by (session_id, correlation_id).
        queries_executed: History of (query, args) tuples for verification.
        simulate_db_error: If set, raises this exception on execute.
    """

    def __init__(self) -> None:
        # Key: (session_id, correlation_id)
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
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
        if "INSERT INTO llm_routing_decisions" in query:
            if len(args) >= 12:
                session_id = args[0]
                correlation_id = args[1]
                selected_agent = args[2]
                llm_confidence = args[3]
                llm_latency_ms = args[4]
                fallback_used = args[5]
                model_used = args[6]
                fuzzy_top_candidate = args[7]
                llm_selected_candidate = args[8]
                agreement = args[9]
                routing_prompt_version = args[10]
                processed_at = args[11]
                key = (session_id, correlation_id)
                if key in self.rows:
                    # ON CONFLICT DO UPDATE: update processed_at only.
                    self.rows[key]["processed_at"] = processed_at
                    return "UPDATE 1"
                else:
                    self.rows[key] = {
                        "session_id": session_id,
                        "correlation_id": correlation_id,
                        "selected_agent": selected_agent,
                        "llm_confidence": llm_confidence,
                        "llm_latency_ms": llm_latency_ms,
                        "fallback_used": fallback_used,
                        "model_used": model_used,
                        "fuzzy_top_candidate": fuzzy_top_candidate,
                        "llm_selected_candidate": llm_selected_candidate,
                        "agreement": agreement,
                        "routing_prompt_version": routing_prompt_version,
                        "processed_at": processed_at,
                    }
                    return "INSERT 0 1"

        return "EXECUTE 0"

    def get_row(self, session_id: str, correlation_id: str) -> dict[str, Any] | None:
        """Retrieve stored row for assertion in tests."""
        return self.rows.get((session_id, correlation_id))

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
def mock_repository() -> MockLlmRoutingDecisionRepository:
    """Provide a fresh mock repository for each test."""
    return MockLlmRoutingDecisionRepository()


@pytest.fixture
def mock_publisher() -> MockKafkaPublisher:
    """Provide a fresh mock Kafka publisher for each test."""
    return MockKafkaPublisher()


@pytest.fixture
def sample_session_id() -> str:
    """Fixed session ID string for deterministic tests."""
    return "test-session-llm-routing"


@pytest.fixture
def sample_correlation_id() -> str:
    """Fixed correlation ID string for tracing tests."""
    return "corr-12345678-abcd-efab"


@pytest.fixture
def sample_routing_decision_event(
    sample_session_id: str,
    sample_correlation_id: str,
) -> ModelLlmRoutingDecisionEvent:
    """LLM routing decision event with typical successful routing data."""
    return ModelLlmRoutingDecisionEvent(
        session_id=sample_session_id,
        correlation_id=sample_correlation_id,
        selected_agent="agent-api",
        llm_confidence=0.92,
        llm_latency_ms=45,
        fallback_used=False,
        model_used="http://192.168.86.201:8001",
        fuzzy_top_candidate="agent-api",
        llm_selected_candidate="agent-api",
        agreement=True,
        routing_prompt_version="v1.2",
        emitted_at=datetime(2026, 2, 27, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_routing_decision_event_fallback(
    sample_session_id: str,
    sample_correlation_id: str,
) -> ModelLlmRoutingDecisionEvent:
    """LLM routing decision event where fallback was used."""
    return ModelLlmRoutingDecisionEvent(
        session_id=sample_session_id,
        correlation_id=sample_correlation_id,
        selected_agent="agent-polymorphic",
        llm_confidence=0.0,
        llm_latency_ms=0,
        fallback_used=True,
        model_used="http://192.168.86.201:8001",
        fuzzy_top_candidate="agent-polymorphic",
        llm_selected_candidate=None,
        agreement=True,
        routing_prompt_version="v1.2",
        emitted_at=datetime(2026, 2, 27, 12, 0, 0, tzinfo=UTC),
    )
