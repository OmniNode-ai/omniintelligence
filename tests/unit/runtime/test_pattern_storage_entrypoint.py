# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Pattern-learned -> pattern-stored through the entry point the runtime uses.

``PluginIntelligence`` subscribes each contract topic with the callback from
``create_dispatch_callback`` and routes the message through the frozen
``MessageDispatchEngine``. These tests drive that same path with the real
engine, a recording upsert store and a recording producer, so a drop or a
refusal anywhere between the raw Kafka message and the published
pattern-stored event shows up here.

Related:
    - OMN-21047: prove one pattern-learned event yields one pattern-stored
      event and one candidate row
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStoredEvent,
)
from omniintelligence.protocols import (
    ProtocolIdempotencyStore,
    ProtocolIntentClassifier,
    ProtocolPatternRepository,
)
from omniintelligence.runtime.dispatch_handlers import (
    DISPATCH_ALIAS_PATTERN_LEARNED,
    create_dispatch_callback,
    create_intelligence_dispatch_engine,
)
from omniintelligence.topics import IntentTopic

PATTERN_STORED_TOPIC = IntentTopic.PATTERN_STORED.value

pytestmark = pytest.mark.unit


class RecordingUpsertStore:
    """Records upsert calls; returns the pattern id like a fresh insert."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def upsert_pattern(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain_id: str,
        domain_version: str,
        confidence: float,
        version: int,
        source_session_ids: list[UUID],
    ) -> UUID | None:
        self.calls.append(
            {
                "pattern_id": pattern_id,
                "signature": signature,
                "signature_hash": signature_hash,
                "domain_id": domain_id,
                "confidence": confidence,
                "version": version,
            }
        )
        return pattern_id


class RecordingProducer:
    """Records every publish; the lifecycle events share it with the stored event."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        self.published.append((topic, value))

    def stored_events(self) -> list[dict[str, Any]]:
        return [v for t, v in self.published if t == PATTERN_STORED_TOPIC]


class FakeMessage:
    """A consumed Kafka message: raw bytes plus ack/nack."""

    def __init__(self, value: bytes) -> None:
        self.value = value
        self.ack = AsyncMock()
        self.nack = AsyncMock()


def _engine(
    store: RecordingUpsertStore,
    producer: RecordingProducer,
    *,
    publish_topics: dict[str, str] | None,
) -> Any:
    repository = MagicMock()
    repository.fetch = AsyncMock(return_value=[])
    repository.fetchrow = AsyncMock(return_value=None)
    repository.execute = AsyncMock(return_value="UPDATE 0")
    assert isinstance(repository, ProtocolPatternRepository)
    idempotency = MagicMock()
    idempotency.exists = AsyncMock(return_value=False)
    idempotency.record = AsyncMock(return_value=None)
    idempotency.check_and_record = AsyncMock(return_value=False)
    assert isinstance(idempotency, ProtocolIdempotencyStore)
    classifier = MagicMock()
    classifier.compute = AsyncMock(return_value=MagicMock())
    assert isinstance(classifier, ProtocolIntentClassifier)
    return create_intelligence_dispatch_engine(
        repository=repository,
        idempotency_store=idempotency,
        intent_classifier=classifier,
        kafka_producer=producer,
        publish_topics=publish_topics,
        pattern_upsert_store=store,
    )


def _learned_event(**overrides: Any) -> dict[str, Any]:
    signature = "synthetic::fictional signature for the storage proof"
    event: dict[str, Any] = {
        "event_type": "PatternLearned",
        "pattern_id": str(uuid4()),
        "signature": signature,
        "signature_hash": hashlib.sha256(signature.encode()).hexdigest(),
        "domain_id": "general",
        "domain_version": "1.0.0",
        "confidence": 0.82,
        "version": 1,
        "source_session_ids": [str(uuid4())],
        "correlation_id": str(uuid4()),
    }
    event.update(overrides)
    return event


async def _consume(
    event_bytes: bytes,
    *,
    publish_topics: dict[str, str] | None = None,
) -> tuple[RecordingUpsertStore, RecordingProducer, FakeMessage]:
    store = RecordingUpsertStore()
    producer = RecordingProducer()
    engine = _engine(
        store,
        producer,
        publish_topics=(
            {"pattern_storage": PATTERN_STORED_TOPIC}
            if publish_topics is None
            else publish_topics
        ),
    )
    callback = create_dispatch_callback(
        engine, DISPATCH_ALIAS_PATTERN_LEARNED, kafka_producer=producer
    )
    msg = FakeMessage(event_bytes)
    await callback(msg)
    return store, producer, msg


class TestPatternLearnedYieldsOnePatternStored:
    @pytest.mark.asyncio
    async def test_one_event_one_row_one_stored_event(self) -> None:
        event = _learned_event()
        store, producer, msg = await _consume(json.dumps(event).encode())

        assert len(store.calls) == 1
        assert store.calls[0]["pattern_id"] == UUID(event["pattern_id"])
        stored = producer.stored_events()
        assert len(stored) == 1
        msg.ack.assert_awaited_once()
        msg.nack.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stored_event_is_the_declared_contract_model(self) -> None:
        event = _learned_event()
        _, producer, _ = await _consume(json.dumps(event).encode())

        stored = ModelPatternStoredEvent.model_validate(producer.stored_events()[0])
        assert str(stored.pattern_id) == event["pattern_id"]
        assert stored.signature == event["signature"]
        assert stored.signature_hash == event["signature_hash"]
        assert stored.domain == event["domain_id"]
        assert stored.version == event["version"]
        assert stored.confidence == pytest.approx(event["confidence"])
        assert stored.state == EnumPatternState.CANDIDATE
        assert str(stored.correlation_id) == event["correlation_id"]

    @pytest.mark.asyncio
    async def test_stored_event_goes_to_the_canonical_topic_without_a_contract_map(
        self,
    ) -> None:
        store = RecordingUpsertStore()
        producer = RecordingProducer()
        engine = _engine(store, producer, publish_topics=None)
        callback = create_dispatch_callback(
            engine, DISPATCH_ALIAS_PATTERN_LEARNED, kafka_producer=producer
        )
        await callback(FakeMessage(json.dumps(_learned_event()).encode()))

        assert len(producer.stored_events()) == 1


MALFORMED: list[tuple[str, bytes]] = [
    (
        "missing signature",
        json.dumps(
            {k: v for k, v in _learned_event().items() if k != "signature"}
        ).encode(),
    ),
    ("empty signature", json.dumps(_learned_event(signature="")).encode()),
    (
        "missing signature_hash",
        json.dumps(
            {k: v for k, v in _learned_event().items() if k != "signature_hash"}
        ).encode(),
    ),
    (
        "pattern_id present but not a uuid",
        json.dumps(_learned_event(pattern_id="not-a-uuid")).encode(),
    ),
    ("payload is a json array", json.dumps([1, 2, 3]).encode()),
]


class TestMalformedPatternLearnedWritesNothing:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("label", "raw"), MALFORMED, ids=[label for label, _ in MALFORMED]
    )
    async def test_no_row_no_stored_event_and_no_redelivery(
        self, label: str, raw: bytes
    ) -> None:
        store, producer, msg = await _consume(raw)

        assert store.calls == [], label
        assert producer.stored_events() == [], label
        # A structurally malformed event can never succeed on retry, so it is
        # acknowledged (and logged), not left to redeliver forever.
        msg.ack.assert_awaited_once()
        msg.nack.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_json_bytes_write_nothing(self) -> None:
        store, producer, msg = await _consume(b"\xff\xfe not json")

        assert store.calls == []
        assert producer.stored_events() == []
        msg.ack.assert_awaited_once()
