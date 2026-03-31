# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Golden chain test for node_pattern_feedback_effect.

Verifies the full event flow:
  session-outcome command -> record_session_outcome handler ->
  ModelSessionOutcomeResult with correct status and metrics

This node has no publish_topics (it writes to PostgreSQL, not Kafka),
so the golden chain validates handler input -> handler output with
a mock repository.

Reference: OMN-7142, OMN-1678
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.event_bus.models import ModelEventMessage
from omnibase_infra.models import ModelNodeIdentity

from omniintelligence.nodes.node_pattern_feedback_effect.handlers.handler_session_outcome import (
    record_session_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
    ModelSessionOutcomeResult,
)

# ---------------------------------------------------------------------------
# Mock repository
# ---------------------------------------------------------------------------


class MockPatternRepository:
    """In-memory mock implementing ProtocolPatternRepository for testing."""

    def __init__(
        self,
        *,
        injection_rows: list[dict[str, Any]] | None = None,
        session_injection_count: int = 0,
    ) -> None:
        self._injection_rows = injection_rows or []
        self._session_injection_count = session_injection_count
        self._execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self._fetch_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: object) -> list[Mapping[str, Any]]:
        self._fetch_calls.append((query, args))
        if "SELECT injection_id" in query:
            return self._injection_rows
        if "SELECT COUNT" in query:
            return [{"count": self._session_injection_count}]
        if "RETURNING id, quality_score" in query:
            # Return effectiveness scores for pattern_ids in args[0]
            pattern_ids = args[0] if args else []
            return [{"id": pid, "quality_score": 0.75} for pid in pattern_ids]
        return []

    async def execute(self, query: str, *args: object) -> str:
        self._execute_calls.append((query, args))
        if "UPDATE pattern_injections" in query:
            return f"UPDATE {len(self._injection_rows)}"
        if "UPDATE learned_patterns" in query:
            pattern_ids = args[0] if args else []
            return f"UPDATE {len(pattern_ids) if isinstance(pattern_ids, list) else 0}"
        return "UPDATE 0"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUBSCRIBE_TOPIC = "test.onex.cmd.omniintelligence.session-outcome.v1"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestPatternFeedbackGoldenChain:
    """Golden chain: session-outcome event -> handler -> result model."""

    async def test_session_outcome_success_flow(self) -> None:
        """Record a successful session outcome and verify result."""
        session_id = uuid4()
        pattern_id = uuid4()
        cid = uuid4()

        repo = MockPatternRepository(
            injection_rows=[
                {"injection_id": uuid4(), "pattern_ids": [pattern_id]},
            ],
            session_injection_count=1,
        )

        result: ModelSessionOutcomeResult = await record_session_outcome(
            session_id=session_id,
            success=True,
            repository=repo,
            correlation_id=cid,
        )

        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.session_id == session_id
        assert result.injections_updated == 1
        assert result.patterns_updated >= 0
        assert pattern_id in result.pattern_ids
        assert result.recorded_at is not None
        assert result.error_message is None

    async def test_session_outcome_no_injections(self) -> None:
        """Verify NO_INJECTIONS_FOUND when session has no pattern injections."""
        session_id = uuid4()
        repo = MockPatternRepository(
            injection_rows=[],
            session_injection_count=0,
        )

        result = await record_session_outcome(
            session_id=session_id,
            success=True,
            repository=repo,
        )

        assert result.status == EnumOutcomeRecordingStatus.NO_INJECTIONS_FOUND
        assert result.injections_updated == 0
        assert result.patterns_updated == 0

    async def test_event_bus_delivery_to_handler(self) -> None:
        """Verify the event bus can deliver a session-outcome command
        and the handler produces a meaningful result."""
        bus = EventBusInmemory(environment="test", group="test-group")
        await bus.start()

        received: list[ModelEventMessage] = []
        identity = ModelNodeIdentity(
            env="test",
            service="omniintelligence",
            node_name="pattern_feedback_effect",
            version="1.0.0",
        )

        try:
            unsub = await bus.subscribe(
                SUBSCRIBE_TOPIC, identity, lambda msg: received.append(msg)
            )

            session_id = uuid4()
            pattern_id = uuid4()

            # Simulate publishing a session-outcome command
            command_payload = {
                "session_id": str(session_id),
                "outcome": "success",
                "correlation_id": str(uuid4()),
            }
            await bus.publish(
                SUBSCRIBE_TOPIC,
                key=str(session_id).encode(),
                value=json.dumps(command_payload).encode(),
            )

            # Verify the event bus delivered the message
            assert len(received) == 1
            delivered = json.loads(received[0].value)
            assert delivered["session_id"] == str(session_id)

            # Now process through the handler (simulating what runtime does)
            repo = MockPatternRepository(
                injection_rows=[
                    {"injection_id": uuid4(), "pattern_ids": [pattern_id]},
                ],
                session_injection_count=1,
            )
            result = await record_session_outcome(
                session_id=session_id,
                success=True,
                repository=repo,
            )

            assert result.status == EnumOutcomeRecordingStatus.SUCCESS
            assert result.injections_updated == 1

            await unsub()
        finally:
            await bus.close()

    async def test_effectiveness_scores_populated(self) -> None:
        """Verify effectiveness scores are returned for updated patterns."""
        session_id = uuid4()
        pid1 = uuid4()
        pid2 = uuid4()

        repo = MockPatternRepository(
            injection_rows=[
                {"injection_id": uuid4(), "pattern_ids": [pid1, pid2]},
            ],
            session_injection_count=1,
        )

        result = await record_session_outcome(
            session_id=session_id,
            success=True,
            repository=repo,
        )

        assert result.status == EnumOutcomeRecordingStatus.SUCCESS
        assert result.effectiveness_scores is not None
        assert len(result.effectiveness_scores) == 2
        for pid in [pid1, pid2]:
            assert pid in result.effectiveness_scores
            assert 0.0 <= result.effectiveness_scores[pid] <= 1.0


__all__ = ["TestPatternFeedbackGoldenChain"]
