# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Routing-feedback events dispatched through the engine the runtime builds.

``create_intelligence_dispatch_engine`` is the entry point ``PluginIntelligence``
uses, so these tests send the event through ``engine.dispatch`` on the topic
alias rather than calling ``HandlerRoutingFeedback`` directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.constants import TOPIC_ROUTING_FEEDBACK_PROCESSED
from omniintelligence.runtime.dispatch_handler_routing_feedback import (
    DISPATCH_ALIAS_ROUTING_FEEDBACK,
)
from omniintelligence.runtime.dispatch_handlers import (
    create_intelligence_dispatch_engine,
)
from omniintelligence.topics import IntentTopic

_INTENT_OUTCOME_LABELED = IntentTopic.INTENT_OUTCOME_LABELED.value


def _make_engine(*, repository: MagicMock, producer: MagicMock) -> Any:
    idempotency_store = MagicMock()
    idempotency_store.exists = AsyncMock(return_value=False)
    idempotency_store.record = AsyncMock(return_value=None)
    idempotency_store.check_and_record = AsyncMock(return_value=False)
    return create_intelligence_dispatch_engine(
        repository=repository,
        idempotency_store=idempotency_store,
        intent_classifier=MagicMock(compute=AsyncMock()),
        kafka_producer=producer,
    )


def _make_envelope(*, feedback_status: str, skip_reason: str | None) -> Any:
    from omnibase_core.models.core.model_envelope_metadata import (
        ModelEnvelopeMetadata,
    )
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

    correlation_id = uuid4()
    return ModelEventEnvelope(
        payload={
            "event_name": "routing.feedback",
            "session_id": f"fictional-routefb-{uuid4()}",
            "outcome": "success",
            "feedback_status": feedback_status,
            "skip_reason": skip_reason,
            "correlation_id": str(correlation_id),
            "emitted_at": datetime.now(UTC).isoformat(),
        },
        envelope_id=uuid4(),
        envelope_timestamp=datetime.now(UTC),
        correlation_id=correlation_id,
        event_type="omniclaude.routing-feedback",
        metadata=ModelEnvelopeMetadata(),
    )


def _published_topics(producer: MagicMock) -> list[str]:
    return [call.kwargs["topic"] for call in producer.publish.await_args_list]


@pytest.fixture
def repository() -> MagicMock:
    repo = MagicMock()
    repo.fetch = AsyncMock(return_value=[])
    repo.fetchrow = AsyncMock(return_value=None)
    repo.execute = AsyncMock(return_value="INSERT 0 1")
    return repo


@pytest.fixture
def producer() -> MagicMock:
    return MagicMock(publish=AsyncMock(return_value=None))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_produced_event_writes_one_row_and_publishes_processed_event(
    repository: MagicMock, producer: MagicMock
) -> None:
    engine = _make_engine(repository=repository, producer=producer)
    envelope = _make_envelope(feedback_status="produced", skip_reason=None)

    result = await engine.dispatch(
        topic=DISPATCH_ALIAS_ROUTING_FEEDBACK, envelope=envelope
    )

    assert result.is_successful(), result.error_message
    session_id = envelope.payload["session_id"]
    repository.execute.assert_awaited_once()
    assert repository.execute.await_args.args[1] == session_id
    producer.publish.assert_awaited_once()
    published = producer.publish.await_args.kwargs
    assert published["topic"] == TOPIC_ROUTING_FEEDBACK_PROCESSED
    assert published["key"] == session_id
    assert published["value"]["session_id"] == session_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skipped_event_writes_no_row_and_publishes_nothing(
    repository: MagicMock, producer: MagicMock
) -> None:
    engine = _make_engine(repository=repository, producer=producer)
    envelope = _make_envelope(
        feedback_status="skipped", skip_reason="guardrail:min_session_length"
    )

    result = await engine.dispatch(
        topic=DISPATCH_ALIAS_ROUTING_FEEDBACK, envelope=envelope
    )

    assert result.is_successful(), result.error_message
    repository.execute.assert_not_awaited()
    repository.fetch.assert_not_awaited()
    repository.fetchrow.assert_not_awaited()
    topics = _published_topics(producer)
    assert _INTENT_OUTCOME_LABELED not in topics
    assert TOPIC_ROUTING_FEEDBACK_PROCESSED not in topics
    producer.publish.assert_not_awaited()
