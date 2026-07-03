# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit coverage for the dispatch envelope-rehydration adapter (OMN-13887).

omnibase_core removed its in-tree ``MessageDispatchEngine`` in 0.46.x; the
Intelligence runtime migrated to ``omnibase_infra.runtime.message_dispatch_engine``.
That engine materializes every envelope to a JSON-safe dict at the dispatch
boundary (OMN-1518) and interprets a non-None ``str`` dispatcher return as an
output topic. The adapter seam (``_rehydrate_dispatch_envelope`` /
``_adapt_context_dispatcher``) restores a ``ModelEventEnvelope`` view for the
unchanged domain handlers and normalizes their status-sentinel returns.

These tests lock in that boundary behavior directly, independent of any single
handler, since the domain handlers themselves are exercised by their own
direct-call suites.

Related:
    - OMN-13887: migrate off removed core MessageDispatchEngine
    - OMN-1518: dispatch engine serialization boundary (materialized dict)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

from omniintelligence.runtime.dispatch_handlers import (
    _adapt_context_dispatcher,
    _rehydrate_dispatch_envelope,
)


class TestRehydrateDispatchEnvelope:
    """`_rehydrate_dispatch_envelope` reconstructs a ModelEventEnvelope from the
    engine's materialized dict and passes typed envelopes through unchanged."""

    def test_materialized_dict_rehydrates_payload_and_trace_fields(self) -> None:
        correlation_id = uuid4()
        ts = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
        materialized = {
            "payload": {"session_id": "s-1", "value": 7},
            "__bindings": {},
            "__debug_trace": {
                "event_type": "intelligence.pattern-stored",
                "correlation_id": str(correlation_id),
                "timestamp": ts.isoformat(),
                "topic": "onex.events.intelligence.pattern-stored.v1",
            },
        }

        envelope = _rehydrate_dispatch_envelope(materialized)

        assert isinstance(envelope, ModelEventEnvelope)
        # Payload survives as the dict the handlers expect.
        assert envelope.payload == {"session_id": "s-1", "value": 7}
        assert envelope.correlation_id == correlation_id
        assert envelope.event_type == "intelligence.pattern-stored"
        assert envelope.envelope_timestamp == ts

    def test_passthrough_when_already_envelope(self) -> None:
        original: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={"a": 1}, correlation_id=uuid4()
        )
        assert _rehydrate_dispatch_envelope(original) is original

    def test_missing_trace_defaults_are_safe(self) -> None:
        # No __debug_trace and a bare payload must not raise.
        envelope = _rehydrate_dispatch_envelope({"payload": {"k": "v"}})
        assert envelope.payload == {"k": "v"}
        assert envelope.correlation_id is None
        assert envelope.event_type is None

    def test_malformed_correlation_id_is_dropped_not_raised(self) -> None:
        envelope = _rehydrate_dispatch_envelope(
            {"payload": {}, "__debug_trace": {"correlation_id": "not-a-uuid"}}
        )
        assert envelope.correlation_id is None

    def test_non_dict_input_wrapped_as_payload(self) -> None:
        envelope = _rehydrate_dispatch_envelope("opaque")
        assert envelope.payload == "opaque"


class TestAdaptContextDispatcher:
    """`_adapt_context_dispatcher` rehydrates the envelope for the wrapped handler
    and normalizes sentinel-string returns to None (engine output-topic contract)."""

    @pytest.mark.asyncio
    async def test_handler_receives_rehydrated_envelope(self) -> None:
        seen: dict[str, object] = {}

        async def handler(envelope: ModelEventEnvelope[object], context: object) -> str:
            seen["payload"] = envelope.payload
            seen["event_type"] = envelope.event_type
            return "ok"

        adapted = _adapt_context_dispatcher(handler)
        materialized = {
            "payload": {"x": 1},
            "__debug_trace": {"event_type": "e.t", "correlation_id": str(uuid4())},
        }

        result = await adapted(materialized, object())

        assert seen["payload"] == {"x": 1}
        assert seen["event_type"] == "e.t"
        # "ok" is a sentinel (no dot) -> normalized to None so the infra engine
        # does not treat it as an output topic.
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("sentinel", ["ok", "skip", "error:boom", ""])
    async def test_sentinel_returns_normalized_to_none(self, sentinel: str) -> None:
        async def handler(envelope: ModelEventEnvelope[object], context: object) -> str:
            return sentinel

        adapted = _adapt_context_dispatcher(handler)
        assert await adapted({"payload": {}}, object()) is None

    @pytest.mark.asyncio
    async def test_real_topic_string_passes_through(self) -> None:
        async def handler(envelope: ModelEventEnvelope[object], context: object) -> str:
            return "onex.events.intelligence.thing.v1"

        adapted = _adapt_context_dispatcher(handler)
        assert (
            await adapted({"payload": {}}, object())
            == "onex.events.intelligence.thing.v1"
        )

    @pytest.mark.asyncio
    async def test_list_and_none_returns_pass_through(self) -> None:
        async def handler_list(
            envelope: ModelEventEnvelope[object], context: object
        ) -> list[str]:
            return ["a.b", "c.d"]

        async def handler_none(
            envelope: ModelEventEnvelope[object], context: object
        ) -> None:
            return None

        assert await _adapt_context_dispatcher(handler_list)(
            {"payload": {}}, object()
        ) == ["a.b", "c.d"]
        assert (
            await _adapt_context_dispatcher(handler_none)({"payload": {}}, object())
            is None
        )
