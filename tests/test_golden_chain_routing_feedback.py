# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Golden chain test for routing feedback dispatch handler (OMN-8175 Task 5).

Verifies the full event bus round-trip:

    onex.evt.omniclaude.routing-feedback.v1 (input)
        -> dispatch handler -> process_routing_feedback
        -> upsert to DB (mocked) + publish processed event
    onex.evt.omniintelligence.routing-feedback-processed.v1 (output)

Assertions are field-level on the output event (session_id, outcome,
feedback_status, emitted_at, processed_at, event_name) -- NOT just
"handler was called."

Uses EventBusInmemory + adapter as ProtocolKafkaPublisher -- no Kafka required.

Imports process_routing_feedback directly to avoid the runtime.__init__ chain
which pulls in omnibase_infra (requires omnibase_spi.protocols.runtime).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from omnibase_core.event_bus.event_bus_inmemory import EventBusInmemory

from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
    process_routing_feedback,
)
from omniintelligence.nodes.node_routing_feedback_effect.models import (
    EnumRoutingFeedbackStatus,
    ModelRoutingFeedbackPayload,
    ModelRoutingFeedbackProcessedEvent,
)

TOPIC_ROUTING_FEEDBACK_PROCESSED = (
    "onex.evt.omniintelligence.routing-feedback-processed.v1"
)


class _EventBusPublisherAdapter:
    """Bridge ProtocolKafkaPublisher -> EventBusInmemory for golden chain tests."""

    def __init__(self, bus: EventBusInmemory) -> None:
        self._bus = bus

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, Any],
    ) -> None:
        value_bytes = json.dumps(
            value, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        key_bytes = key.encode("utf-8") if key else None
        await self._bus.publish(topic=topic, key=key_bytes, value=value_bytes)


class _MockRepository:
    """Minimal ProtocolPatternRepository mock returning asyncpg-style status."""

    async def fetch(self, query: str, *args: object) -> list[dict[str, Any]]:
        return []

    async def fetchrow(self, query: str, *args: object) -> dict[str, Any] | None:
        return None

    async def execute(self, query: str, *args: object) -> str:
        return "INSERT 0 1"


@pytest.mark.unit
async def test_routing_feedback_dispatch_handler() -> None:
    """Golden chain: routing-feedback in -> handler -> processed event on bus.

    Full chain: ModelRoutingFeedbackPayload -> process_routing_feedback
    -> DB upsert (mocked) + Kafka publish (EventBusInmemory)
    -> verify processed event on bus with specific field values.
    """
    bus = EventBusInmemory()
    await bus.start()

    try:
        mock_repository = _MockRepository()
        publisher = _EventBusPublisherAdapter(bus)

        now = datetime.now(UTC)
        correlation_id = uuid4()
        session_id = f"golden-chain-session-{uuid4()}"

        event = ModelRoutingFeedbackPayload(
            session_id=session_id,
            outcome="success",
            feedback_status="produced",
            skip_reason=None,
            correlation_id=correlation_id,
            emitted_at=now,
        )

        result = await process_routing_feedback(
            event=event,
            repository=mock_repository,
            kafka_publisher=publisher,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.session_id == session_id
        assert result.was_upserted is True
        assert result.feedback_status == "produced"

        history = await bus.get_event_history(
            limit=10, topic=TOPIC_ROUTING_FEEDBACK_PROCESSED
        )
        assert len(history) == 1, (
            f"Expected exactly 1 processed event, got {len(history)}"
        )

        received = json.loads(history[0].value.decode("utf-8"))

        assert received["session_id"] == session_id, (
            "session_id must match input (projection join key)"
        )
        assert received["outcome"] == "success", "outcome must be non-null"
        assert received["feedback_status"] == "produced", (
            "feedback_status must be 'produced' for events that reach the projection"
        )
        assert received["event_name"] == "routing.feedback.processed"
        assert received["emitted_at"] is not None, "emitted_at must be non-null"
        assert received["processed_at"] is not None, "processed_at must be non-null"

        ModelRoutingFeedbackProcessedEvent.model_validate(received)

    finally:
        await bus.close()


@pytest.mark.unit
async def test_routing_feedback_dispatch_handler_skipped_no_event() -> None:
    """Skipped feedback produces no DB write and no output event."""
    bus = EventBusInmemory()
    await bus.start()

    try:
        mock_repository = _MockRepository()
        publisher = _EventBusPublisherAdapter(bus)

        now = datetime.now(UTC)
        correlation_id = uuid4()
        session_id = f"golden-chain-skip-{uuid4()}"

        event = ModelRoutingFeedbackPayload(
            session_id=session_id,
            outcome="failed",
            feedback_status="skipped",
            skip_reason="guardrail:min_session_length",
            correlation_id=correlation_id,
            emitted_at=now,
        )

        result = await process_routing_feedback(
            event=event,
            repository=mock_repository,
            kafka_publisher=publisher,
        )

        assert result.status == EnumRoutingFeedbackStatus.SUCCESS
        assert result.was_upserted is False
        assert result.feedback_status == "skipped"

        history = await bus.get_event_history(
            limit=10, topic=TOPIC_ROUTING_FEEDBACK_PROCESSED
        )
        assert len(history) == 0, (
            "Skipped events must not produce a routing-feedback-processed event"
        )

    finally:
        await bus.close()


@pytest.mark.unit
async def test_routing_feedback_dispatch_handler_no_producer_graceful() -> None:
    """Handler succeeds with no kafka_producer (graceful degradation)."""
    mock_repository = _MockRepository()

    now = datetime.now(UTC)
    correlation_id = uuid4()
    session_id = f"golden-chain-no-kafka-{uuid4()}"

    event = ModelRoutingFeedbackPayload(
        session_id=session_id,
        outcome="success",
        feedback_status="produced",
        skip_reason=None,
        correlation_id=correlation_id,
        emitted_at=now,
    )

    result = await process_routing_feedback(
        event=event,
        repository=mock_repository,
        kafka_publisher=None,
    )

    assert result.status == EnumRoutingFeedbackStatus.SUCCESS
    assert result.session_id == session_id
    assert result.was_upserted is True
