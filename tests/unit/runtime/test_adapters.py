# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for Intelligence protocol adapters.

Validates:
    - Protocol conformance (isinstance checks)
    - Correct delegation to underlying infrastructure
    - Serialization boundaries (bytes, JSON)

Related:
    - OMN-2091: Wire real dependencies into dispatch handlers (Phase 2)
    - OMN-2326: Migrate intelligence DB writes to omnibase_infra effect boundary
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from omniintelligence.runtime.adapters import (
    AdapterIdempotencyStoreInfra,
    AdapterIntentClassifier,
    AdapterKafkaPublisher,
    AdapterPatternRepositoryRuntime,
)

pytestmark = pytest.mark.unit


# Protocol imports for isinstance checks
from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    ProtocolIntentClassifier,
)
from omniintelligence.nodes.node_claude_hook_event_effect.handlers.handler_claude_event import (
    ProtocolKafkaPublisher as HookProtocolKafkaPublisher,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    ProtocolIdempotencyStore,
    ProtocolPatternRepository,
)
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    ProtocolKafkaPublisher as LifecycleProtocolKafkaPublisher,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def mock_runtime() -> MagicMock:
    """Create a mock PostgresRepositoryRuntime with async pool methods."""
    runtime = MagicMock()
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value="OK")
    runtime._pool = pool
    return runtime


@pytest.fixture()
def mock_event_bus() -> MagicMock:
    """Create a mock event bus with async publish."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture()
def mock_infra_idempotency_store() -> MagicMock:
    """Create a mock omnibase_infra idempotency store."""
    store = MagicMock()
    store.check_and_record = AsyncMock(return_value=True)  # True = new
    store.is_processed = AsyncMock(return_value=False)
    store.mark_processed = AsyncMock()
    return store


# =============================================================================
# AdapterPatternRepositoryRuntime
# =============================================================================


class TestAdapterPatternRepositoryRuntime:
    """Tests for AdapterPatternRepositoryRuntime."""

    def test_protocol_conformance(self, mock_runtime: MagicMock) -> None:
        """Adapter satisfies ProtocolPatternRepository."""
        adapter = AdapterPatternRepositoryRuntime(mock_runtime)
        assert isinstance(adapter, ProtocolPatternRepository)

    @pytest.mark.asyncio()
    async def test_fetch_delegates_to_runtime_pool(
        self, mock_runtime: MagicMock
    ) -> None:
        """fetch() delegates with exact args to runtime pool."""
        # asyncpg Records -> dicts
        mock_runtime._pool.fetch.return_value = [{"id": 1, "name": "test"}]

        adapter = AdapterPatternRepositoryRuntime(mock_runtime)
        query = "SELECT * FROM patterns WHERE id = $1"
        result = await adapter.fetch(query, 42)

        mock_runtime._pool.fetch.assert_awaited_once_with(query, 42)
        assert result == [{"id": 1, "name": "test"}]

    @pytest.mark.asyncio()
    async def test_fetch_passes_multiple_args(self, mock_runtime: MagicMock) -> None:
        """fetch() passes multiple positional args through."""
        adapter = AdapterPatternRepositoryRuntime(mock_runtime)
        query = "SELECT * FROM patterns WHERE id = $1 AND status = $2"
        await adapter.fetch(query, 1, "active")

        mock_runtime._pool.fetch.assert_awaited_once_with(query, 1, "active")

    @pytest.mark.asyncio()
    async def test_fetchrow_delegates_to_runtime_pool(
        self, mock_runtime: MagicMock
    ) -> None:
        """fetchrow() delegates with exact args to runtime pool."""
        mock_runtime._pool.fetchrow.return_value = {"id": 1, "status": "validated"}

        adapter = AdapterPatternRepositoryRuntime(mock_runtime)
        query = "SELECT * FROM patterns WHERE id = $1"
        result = await adapter.fetchrow(query, 99)

        mock_runtime._pool.fetchrow.assert_awaited_once_with(query, 99)
        assert result == {"id": 1, "status": "validated"}

    @pytest.mark.asyncio()
    async def test_fetchrow_returns_none_when_no_row(
        self, mock_runtime: MagicMock
    ) -> None:
        """fetchrow() returns None when pool returns None."""
        mock_runtime._pool.fetchrow.return_value = None

        adapter = AdapterPatternRepositoryRuntime(mock_runtime)
        result = await adapter.fetchrow("SELECT 1 WHERE FALSE")

        assert result is None

    @pytest.mark.asyncio()
    async def test_execute_delegates_to_runtime_pool(
        self, mock_runtime: MagicMock
    ) -> None:
        """execute() delegates with exact args to runtime pool."""
        mock_runtime._pool.execute.return_value = "UPDATE 1"

        adapter = AdapterPatternRepositoryRuntime(mock_runtime)
        query = "UPDATE patterns SET status = $1 WHERE id = $2"
        result = await adapter.execute(query, "deprecated", 5)

        mock_runtime._pool.execute.assert_awaited_once_with(query, "deprecated", 5)
        assert result == "UPDATE 1"


# =============================================================================
# AdapterIdempotencyStoreInfra
# =============================================================================


class TestAdapterIdempotencyStoreInfra:
    """Tests for AdapterIdempotencyStoreInfra."""

    def test_protocol_conformance(
        self, mock_infra_idempotency_store: MagicMock
    ) -> None:
        """Adapter satisfies ProtocolIdempotencyStore."""
        adapter = AdapterIdempotencyStoreInfra(mock_infra_idempotency_store)
        assert isinstance(adapter, ProtocolIdempotencyStore)

    @pytest.mark.asyncio()
    async def test_check_and_record_inverts_semantics_for_new(
        self, mock_infra_idempotency_store: MagicMock
    ) -> None:
        """check_and_record() returns False (new) when infra returns True (new)."""
        mock_infra_idempotency_store.check_and_record.return_value = True  # new
        request_id = uuid4()

        adapter = AdapterIdempotencyStoreInfra(mock_infra_idempotency_store)
        result = await adapter.check_and_record(request_id)

        mock_infra_idempotency_store.check_and_record.assert_awaited_once_with(
            message_id=request_id, domain="pattern_lifecycle"
        )
        assert result is False  # intelligence: False = new

    @pytest.mark.asyncio()
    async def test_check_and_record_inverts_semantics_for_duplicate(
        self, mock_infra_idempotency_store: MagicMock
    ) -> None:
        """check_and_record() returns True (duplicate) when infra returns False (duplicate)."""
        mock_infra_idempotency_store.check_and_record.return_value = False  # duplicate
        request_id = uuid4()

        adapter = AdapterIdempotencyStoreInfra(mock_infra_idempotency_store)
        result = await adapter.check_and_record(request_id)

        assert result is True  # intelligence: True = duplicate

    @pytest.mark.asyncio()
    async def test_exists_delegates_to_is_processed(
        self, mock_infra_idempotency_store: MagicMock
    ) -> None:
        """exists() delegates to infra is_processed()."""
        mock_infra_idempotency_store.is_processed.return_value = True
        request_id = uuid4()

        adapter = AdapterIdempotencyStoreInfra(mock_infra_idempotency_store)
        result = await adapter.exists(request_id)

        mock_infra_idempotency_store.is_processed.assert_awaited_once_with(
            message_id=request_id, domain="pattern_lifecycle"
        )
        assert result is True

    @pytest.mark.asyncio()
    async def test_record_delegates_to_mark_processed(
        self, mock_infra_idempotency_store: MagicMock
    ) -> None:
        """record() delegates to infra mark_processed()."""
        request_id = uuid4()

        adapter = AdapterIdempotencyStoreInfra(mock_infra_idempotency_store)
        await adapter.record(request_id)

        mock_infra_idempotency_store.mark_processed.assert_awaited_once_with(
            message_id=request_id, domain="pattern_lifecycle"
        )


# =============================================================================
# AdapterKafkaPublisher
# =============================================================================


class TestAdapterKafkaPublisher:
    """Tests for AdapterKafkaPublisher."""

    def test_protocol_conformance_lifecycle(self, mock_event_bus: MagicMock) -> None:
        """Adapter satisfies ProtocolKafkaPublisher from handler_transition."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        assert isinstance(adapter, LifecycleProtocolKafkaPublisher)

    def test_protocol_conformance_hook(self, mock_event_bus: MagicMock) -> None:
        """Adapter satisfies ProtocolKafkaPublisher from handler_claude_event."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        assert isinstance(adapter, HookProtocolKafkaPublisher)

    @pytest.mark.asyncio()
    async def test_publish_encodes_key_as_utf8_bytes(
        self, mock_event_bus: MagicMock
    ) -> None:
        """publish() encodes key as UTF-8 bytes."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        await adapter.publish(topic="test.topic", key="my-key", value={"a": 1})

        call_kwargs = mock_event_bus.publish.call_args
        assert call_kwargs.kwargs["key"] == b"my-key"

    @pytest.mark.asyncio()
    async def test_publish_encodes_value_as_compact_json_bytes(
        self, mock_event_bus: MagicMock
    ) -> None:
        """publish() encodes value as compact JSON (no whitespace), UTF-8."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        payload = {"event_type": "test", "count": 42}
        await adapter.publish(topic="test.topic", key="k", value=payload)

        call_kwargs = mock_event_bus.publish.call_args
        value_bytes = call_kwargs.kwargs["value"]

        # Must be bytes
        assert isinstance(value_bytes, bytes)

        # Must decode to the original payload
        decoded = json.loads(value_bytes.decode("utf-8"))
        assert decoded == payload

        # Must be compact (no spaces after separators)
        assert b" " not in value_bytes

    @pytest.mark.asyncio()
    async def test_publish_passes_topic_through(
        self, mock_event_bus: MagicMock
    ) -> None:
        """publish() passes topic to event_bus.publish unchanged."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        topic = "onex.evt.omniintelligence.pattern-stored.v1"
        await adapter.publish(topic=topic, key="k", value={})

        call_kwargs = mock_event_bus.publish.call_args
        assert call_kwargs.kwargs["topic"] == topic

    @pytest.mark.asyncio()
    async def test_publish_none_key_passes_none(
        self, mock_event_bus: MagicMock
    ) -> None:
        """publish() passes None to event_bus when key is falsy."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        # The adapter checks `if key` -- empty string is falsy, same as None
        await adapter.publish(topic="t", key="", value={"x": 1})

        call_kwargs = mock_event_bus.publish.call_args
        assert call_kwargs.kwargs["key"] is None

    @pytest.mark.asyncio()
    async def test_publish_uses_default_str_for_non_serializable(
        self, mock_event_bus: MagicMock
    ) -> None:
        """publish() uses default=str for non-JSON-serializable values (e.g. UUID)."""
        adapter = AdapterKafkaPublisher(mock_event_bus)
        test_uuid = uuid4()
        await adapter.publish(topic="t", key="k", value={"id": test_uuid})

        call_kwargs = mock_event_bus.publish.call_args
        value_bytes = call_kwargs.kwargs["value"]
        decoded = json.loads(value_bytes.decode("utf-8"))
        assert decoded["id"] == str(test_uuid)


# =============================================================================
# AdapterIntentClassifier
# =============================================================================


class TestAdapterIntentClassifier:
    """Tests for AdapterIntentClassifier."""

    def test_protocol_conformance(self) -> None:
        """Adapter satisfies ProtocolIntentClassifier."""
        adapter = AdapterIntentClassifier()
        assert isinstance(adapter, ProtocolIntentClassifier)

    def test_uses_default_config_when_none(self) -> None:
        """Constructor uses DEFAULT_CLASSIFICATION_CONFIG when no config given."""
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            DEFAULT_CLASSIFICATION_CONFIG,
        )

        adapter = AdapterIntentClassifier()
        assert adapter._config is DEFAULT_CLASSIFICATION_CONFIG

    def test_uses_provided_config(self) -> None:
        """Constructor uses explicitly provided config."""
        custom_config = MagicMock(name="custom_config")
        adapter = AdapterIntentClassifier(config=custom_config)
        assert adapter._config is custom_config

    @pytest.mark.asyncio()
    async def test_compute_calls_handle_intent_classification(self) -> None:
        """compute() delegates to handle_intent_classification with input and config."""
        mock_result = MagicMock(name="classification_output")
        mock_input = MagicMock(name="classification_input")

        # The import is lazy (inside compute()), so patch at the handlers package
        # which is where the lazy import resolves from
        with patch(
            "omniintelligence.nodes.node_intent_classifier_compute.handlers.handle_intent_classification",
            return_value=mock_result,
        ) as mock_handler:
            adapter = AdapterIntentClassifier()
            result = await adapter.compute(mock_input)

            mock_handler.assert_called_once_with(
                input_data=mock_input,
                config=adapter._config,
            )
            assert result is mock_result
