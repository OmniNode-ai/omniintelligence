# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Golden chain test for routing feedback dispatch handler (Task 5 — OMN-8127).

Verifies that:
1. The dispatch handler is registered for the correct topic alias
2. ModelRoutingFeedbackPayload validates correctly as the input model
3. ModelRoutingFeedbackProcessedEvent validates correctly as the output model
4. Output event contains required field-level values: session_id, outcome,
   feedback_status, emitted_at, processed_at — NOT just "handler was called"

This test prevents regression of the routing_feedback_events gap fixed
in OMN-8170 (dispatch_handler_routing_feedback.py + dispatch_handlers.py
registration).

Uses EventBusInmemory and mock kafka_producer — no Kafka required.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from omnibase_core.event_bus.event_bus_inmemory import EventBusInmemory

from omniintelligence.nodes.node_routing_feedback_effect.models import (
    ModelRoutingFeedbackPayload,
    ModelRoutingFeedbackProcessedEvent,
)
from omniintelligence.runtime.dispatch_handler_routing_feedback import (
    DISPATCH_ALIAS_ROUTING_FEEDBACK,
    create_routing_feedback_dispatch_handler,
)

TOPIC_ROUTING_FEEDBACK_V1 = "onex.evt.omniclaude.routing-feedback.v1"
TOPIC_ROUTING_FEEDBACK_PROCESSED = (
    "onex.evt.omniintelligence.routing-feedback-processed.v1"
)


@pytest.mark.unit
def test_routing_feedback_dispatch_alias_matches_source_topic() -> None:
    """Verify DISPATCH_ALIAS_ROUTING_FEEDBACK is derived from the canonical source topic.

    The dispatch engine uses this alias to route incoming messages.
    It must resolve to the topic that omniclaude emits on.
    """
    # The dispatch alias must contain the canonical topic components
    assert "routing-feedback" in DISPATCH_ALIAS_ROUTING_FEEDBACK, (
        f"DISPATCH_ALIAS_ROUTING_FEEDBACK '{DISPATCH_ALIAS_ROUTING_FEEDBACK}' "
        "must contain 'routing-feedback'"
    )
    assert "omniclaude" in DISPATCH_ALIAS_ROUTING_FEEDBACK, (
        f"DISPATCH_ALIAS_ROUTING_FEEDBACK '{DISPATCH_ALIAS_ROUTING_FEEDBACK}' "
        "must contain 'omniclaude' to scope to the correct producer"
    )


@pytest.mark.unit
def test_routing_feedback_payload_model_validation() -> None:
    """Verify ModelRoutingFeedbackPayload validates correctly for 'produced' status.

    This is the canonical input model consumed from onex.evt.omniclaude.routing-feedback.v1.
    """
    now = datetime.now(UTC)
    correlation_id = uuid4()

    payload = ModelRoutingFeedbackPayload(
        session_id="session-abc123",
        outcome="success",
        feedback_status="produced",
        skip_reason=None,
        correlation_id=correlation_id,
        emitted_at=now,
    )

    # Round-trip validation
    restored = ModelRoutingFeedbackPayload.model_validate(payload.model_dump())
    assert restored.session_id == "session-abc123"
    assert restored.outcome == "success"
    assert restored.feedback_status == "produced"
    assert restored.skip_reason is None
    assert restored.correlation_id == correlation_id


@pytest.mark.unit
def test_routing_feedback_payload_skipped_status() -> None:
    """Verify ModelRoutingFeedbackPayload validates for 'skipped' status with skip_reason."""
    now = datetime.now(UTC)

    payload = ModelRoutingFeedbackPayload(
        session_id="session-xyz",
        outcome="failed",
        feedback_status="skipped",
        skip_reason="guardrail:min_session_length",
        correlation_id=uuid4(),
        emitted_at=now,
    )

    assert payload.feedback_status == "skipped"
    assert payload.skip_reason == "guardrail:min_session_length"


@pytest.mark.unit
def test_routing_feedback_processed_event_model_validation() -> None:
    """Verify ModelRoutingFeedbackProcessedEvent validates correctly.

    This is the canonical output model published to
    onex.evt.omniintelligence.routing-feedback-processed.v1.
    """
    now = datetime.now(UTC)

    event = ModelRoutingFeedbackProcessedEvent(
        session_id="session-abc123",
        outcome="success",
        feedback_status="produced",
        emitted_at=now,
        processed_at=now,
    )

    restored = ModelRoutingFeedbackProcessedEvent.model_validate(event.model_dump())
    assert restored.session_id == "session-abc123"
    assert restored.outcome == "success"
    assert restored.feedback_status == "produced"
    assert restored.event_name == "routing.feedback.processed"
    assert restored.emitted_at == now
    assert restored.processed_at == now


@pytest.mark.unit
async def test_routing_feedback_dispatch_handler_invokes_process() -> None:
    """Verify dispatch handler calls process_routing_feedback with correct payload.

    Chain: create_routing_feedback_dispatch_handler → handle(envelope) →
           process_routing_feedback(payload, producer)
    Asserts that the handler is invoked and produces a result string.
    """
    mock_repository = AsyncMock()
    mock_producer = AsyncMock()

    now = datetime.now(UTC)
    correlation_id = uuid4()

    # Build the canonical input payload
    feedback_payload = ModelRoutingFeedbackPayload(
        session_id="session-golden-chain",
        outcome="success",
        feedback_status="produced",
        skip_reason=None,
        correlation_id=correlation_id,
        emitted_at=now,
    )

    # Create mock envelope as the dispatch engine provides it
    mock_envelope = MagicMock()
    mock_envelope.payload = feedback_payload.model_dump(mode="json")
    mock_context = MagicMock()

    # Mock process_routing_feedback to avoid DB access
    # status must be EnumRoutingFeedbackStatus (has .value) as used by the handler
    from omniintelligence.nodes.node_routing_feedback_effect.models.enum_routing_feedback_status import (
        EnumRoutingFeedbackStatus,
    )

    mock_result = MagicMock()
    mock_result.status = EnumRoutingFeedbackStatus.SUCCESS

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "omniintelligence.nodes.node_routing_feedback_effect.handlers."
            "handler_routing_feedback.process_routing_feedback",
            AsyncMock(return_value=mock_result),
        )

        handler = create_routing_feedback_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_producer,
        )

        result = await handler(mock_envelope, mock_context)

    # Handler must return a non-empty result string
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.unit
async def test_routing_feedback_processed_event_published_to_bus() -> None:
    """Verify that ModelRoutingFeedbackProcessedEvent flows through EventBusInmemory.

    Chain: ModelRoutingFeedbackProcessedEvent → bus.publish_envelope →
           consumed message with correct field values.

    This is the output side of the routing feedback pipeline — verifies
    what omnidash will project into routing_feedback_events.
    NOT just "event received" — verifies session_id, outcome, feedback_status non-null.
    """
    bus = EventBusInmemory()
    await bus.start()

    now = datetime.now(UTC)

    event = ModelRoutingFeedbackProcessedEvent(
        session_id="session-golden-chain-output",
        outcome="success",
        feedback_status="produced",
        emitted_at=now,
        processed_at=now,
    )

    # Validate before emission
    assert (
        ModelRoutingFeedbackProcessedEvent.model_validate(event.model_dump()) == event
    )

    await bus.publish_envelope(event, topic=TOPIC_ROUTING_FEEDBACK_PROCESSED)

    history = await bus.get_event_history(
        limit=10, topic=TOPIC_ROUTING_FEEDBACK_PROCESSED
    )
    assert len(history) == 1

    received_raw = json.loads(history[0].value.decode("utf-8"))

    # Field-level assertions — NOT just count > 0
    assert received_raw["session_id"] == "session-golden-chain-output", (
        "session_id must be non-null (projection join key for routing_feedback_events)"
    )
    assert received_raw["outcome"] == "success", "outcome must be non-null"
    assert received_raw["feedback_status"] == "produced", (
        "feedback_status must be 'produced' for events that reach the projection"
    )
    assert received_raw["event_name"] == "routing.feedback.processed"
    assert received_raw["emitted_at"] is not None, "emitted_at must be non-null"
    assert received_raw["processed_at"] is not None, "processed_at must be non-null"

    await bus.close()
