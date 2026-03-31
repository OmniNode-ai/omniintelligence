# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Golden chain test for node_pattern_storage_effect.

Verifies the full event flow:
  publish pattern-learned event -> handle_store_pattern -> pattern-stored output event

Uses EventBusInmemory + mock ProtocolPatternStore to test the chain
without real PostgreSQL.

Reference: OMN-7142
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.models import ModelNodeIdentity

from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
    StorePatternResult,
    handle_store_pattern,
)
from omniintelligence.nodes.node_pattern_storage_effect.models import (
    EnumPatternState,
    ModelPatternStorageInput,
    ModelPatternStoredEvent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_pattern_store(*, existing_id: None = None) -> Any:
    """Create a mock ProtocolPatternStore that behaves like an empty store."""
    store = AsyncMock()
    store.check_exists_by_id = AsyncMock(return_value=existing_id)
    store.check_exists = AsyncMock(return_value=False)
    store.get_latest_version = AsyncMock(return_value=None)
    store.get_stored_at = AsyncMock(return_value=None)
    store.set_previous_not_current = AsyncMock(return_value=0)
    # store_pattern returns the pattern_id it receives
    store.store_pattern = AsyncMock(side_effect=lambda **kw: kw["pattern_id"])
    store.store_with_version_transition = AsyncMock(
        side_effect=lambda **kw: kw["pattern_id"]
    )
    return store


def _make_storage_input(**overrides: Any) -> ModelPatternStorageInput:
    """Build a valid ModelPatternStorageInput with sensible defaults."""
    defaults: dict[str, Any] = {
        "pattern_id": uuid4(),
        "signature": "def foo() -> None: ...",
        "signature_hash": "abc123hash",
        "domain": "code_patterns",
        "confidence": 0.85,
        "correlation_id": uuid4(),
    }
    defaults.update(overrides)
    return ModelPatternStorageInput(**defaults)


class _EventBusKafkaPublisherAdapter:
    """Thin adapter from ProtocolKafkaPublisher to EventBusInmemory."""

    def __init__(self, bus: EventBusInmemory) -> None:
        self._bus = bus

    async def publish(self, topic: str, key: str, value: dict[str, Any]) -> None:
        value_bytes = json.dumps(value, default=str).encode()
        key_bytes = key.encode() if key else None
        await self._bus.publish(topic=topic, key=key_bytes, value=value_bytes)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

PUBLISH_TOPIC = "test.onex.evt.omniintelligence.pattern-stored.v1"


@pytest.mark.asyncio
@pytest.mark.integration
class TestPatternStorageGoldenChain:
    """Golden chain: command -> handler -> output event on bus."""

    async def test_store_pattern_publishes_event(self) -> None:
        """Publish a pattern-learned command, run handler, verify stored event."""
        bus = EventBusInmemory(environment="test", group="test-group")
        await bus.start()

        received: list[Any] = []
        identity = ModelNodeIdentity(
            env="test",
            service="omniintelligence",
            node_name="pattern_storage_effect",
            version="1.0.0",
        )

        try:
            unsub = await bus.subscribe(
                PUBLISH_TOPIC, identity, lambda msg: received.append(msg)
            )

            adapter = _EventBusKafkaPublisherAdapter(bus)
            mock_store = _make_mock_pattern_store()
            mock_conn = AsyncMock()
            input_data = _make_storage_input()

            # Execute handler
            result: StorePatternResult = await handle_store_pattern(
                input_data, pattern_store=mock_store, conn=mock_conn
            )

            assert result.success is True
            assert result.event is not None
            event: ModelPatternStoredEvent = result.event

            # Simulate runtime publishing the output event
            await adapter.publish(
                topic=PUBLISH_TOPIC,
                key=str(event.pattern_id),
                value=event.model_dump(mode="json"),
            )

            # Verify subscriber received the event
            assert len(received) == 1
            payload = json.loads(received[0].value)
            assert payload["pattern_id"] == str(input_data.pattern_id)
            assert payload["domain"] == "code_patterns"
            assert payload["state"] == EnumPatternState.CANDIDATE.value
            assert payload["confidence"] == 0.85
            assert payload["version"] == 1

            await unsub()
        finally:
            await bus.close()

    async def test_handler_output_has_meaningful_payload(self) -> None:
        """Verify handler output carries all required fields."""
        mock_store = _make_mock_pattern_store()
        mock_conn = AsyncMock()
        cid = uuid4()
        input_data = _make_storage_input(correlation_id=cid)

        result = await handle_store_pattern(
            input_data, pattern_store=mock_store, conn=mock_conn
        )

        assert result.success is True
        assert result.event is not None
        evt = result.event
        assert evt.pattern_id == input_data.pattern_id
        assert evt.signature == input_data.signature
        assert evt.signature_hash == input_data.signature_hash
        assert evt.domain == input_data.domain
        assert evt.confidence == input_data.confidence
        assert evt.correlation_id == cid
        assert evt.state == EnumPatternState.CANDIDATE
        assert isinstance(evt.stored_at, datetime)


__all__ = ["TestPatternStorageGoldenChain"]
