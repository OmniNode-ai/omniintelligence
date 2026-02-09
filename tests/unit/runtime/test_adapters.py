# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for Intelligence protocol adapters.

Validates:
    - Protocol conformance (isinstance checks)
    - Correct delegation to underlying infrastructure
    - Serialization boundaries (bytes, JSON)

Related:
    - OMN-2091: Wire real dependencies into dispatch handlers (Phase 2)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from omniintelligence.runtime.adapters import (
    SQL_ENSURE_IDEMPOTENCY_TABLE,
    SQL_IDEMPOTENCY_CHECK_AND_RECORD,
    SQL_IDEMPOTENCY_EXISTS,
    SQL_IDEMPOTENCY_RECORD,
    AdapterIdempotencyStorePostgres,
    AdapterIntentClassifier,
    AdapterKafkaPublisher,
    AdapterPatternRepositoryPostgres,
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
def mock_pool() -> MagicMock:
    """Create a mock asyncpg.Pool with async methods."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value="OK")
    return pool


@pytest.fixture()
def mock_event_bus() -> MagicMock:
    """Create a mock event bus with async publish."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


# =============================================================================
# AdapterPatternRepositoryPostgres
# =============================================================================


class TestAdapterPatternRepositoryPostgres:
    """Tests for AdapterPatternRepositoryPostgres."""

    def test_protocol_conformance(self, mock_pool: MagicMock) -> None:
        """Adapter satisfies ProtocolPatternRepository."""
        adapter = AdapterPatternRepositoryPostgres(mock_pool)
        assert isinstance(adapter, ProtocolPatternRepository)

    @pytest.mark.asyncio()
    async def test_fetch_delegates_to_pool(self, mock_pool: MagicMock) -> None:
        """fetch() delegates with exact args to pool.fetch()."""
        expected = [{"id": 1, "name": "test"}]
        mock_pool.fetch.return_value = expected

        adapter = AdapterPatternRepositoryPostgres(mock_pool)
        query = "SELECT * FROM patterns WHERE id = $1"
        result = await adapter.fetch(query, 42)

        mock_pool.fetch.assert_awaited_once_with(query, 42)
        assert result == expected

    @pytest.mark.asyncio()
    async def test_fetch_passes_multiple_args(self, mock_pool: MagicMock) -> None:
        """fetch() passes multiple positional args through."""
        adapter = AdapterPatternRepositoryPostgres(mock_pool)
        query = "SELECT * FROM patterns WHERE id = $1 AND status = $2"
        await adapter.fetch(query, 1, "active")

        mock_pool.fetch.assert_awaited_once_with(query, 1, "active")

    @pytest.mark.asyncio()
    async def test_fetchrow_delegates_to_pool(self, mock_pool: MagicMock) -> None:
        """fetchrow() delegates with exact args to pool.fetchrow()."""
        expected = {"id": 1, "status": "validated"}
        mock_pool.fetchrow.return_value = expected

        adapter = AdapterPatternRepositoryPostgres(mock_pool)
        query = "SELECT * FROM patterns WHERE id = $1"
        result = await adapter.fetchrow(query, 99)

        mock_pool.fetchrow.assert_awaited_once_with(query, 99)
        assert result == expected

    @pytest.mark.asyncio()
    async def test_fetchrow_returns_none_when_no_row(
        self, mock_pool: MagicMock
    ) -> None:
        """fetchrow() returns None when pool returns None."""
        mock_pool.fetchrow.return_value = None

        adapter = AdapterPatternRepositoryPostgres(mock_pool)
        result = await adapter.fetchrow("SELECT 1 WHERE FALSE")

        assert result is None

    @pytest.mark.asyncio()
    async def test_execute_delegates_to_pool(self, mock_pool: MagicMock) -> None:
        """execute() delegates with exact args to pool.execute()."""
        mock_pool.execute.return_value = "UPDATE 1"

        adapter = AdapterPatternRepositoryPostgres(mock_pool)
        query = "UPDATE patterns SET status = $1 WHERE id = $2"
        result = await adapter.execute(query, "deprecated", 5)

        mock_pool.execute.assert_awaited_once_with(query, "deprecated", 5)
        assert result == "UPDATE 1"


# =============================================================================
# AdapterIdempotencyStorePostgres
# =============================================================================


class TestAdapterIdempotencyStorePostgres:
    """Tests for AdapterIdempotencyStorePostgres."""

    def test_protocol_conformance(self, mock_pool: MagicMock) -> None:
        """Adapter satisfies ProtocolIdempotencyStore."""
        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        assert isinstance(adapter, ProtocolIdempotencyStore)

    @pytest.mark.asyncio()
    async def test_ensure_table_calls_create_table_sql(
        self, mock_pool: MagicMock
    ) -> None:
        """ensure_table() executes the CREATE TABLE IF NOT EXISTS SQL."""
        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        await adapter.ensure_table()

        mock_pool.execute.assert_awaited_once_with(SQL_ENSURE_IDEMPOTENCY_TABLE)

    @pytest.mark.asyncio()
    async def test_ensure_table_logs_on_first_call_only(
        self, mock_pool: MagicMock
    ) -> None:
        """ensure_table() logs on first call, not on subsequent calls."""
        adapter = AdapterIdempotencyStorePostgres(mock_pool)

        with patch("omniintelligence.runtime.adapters.logger") as mock_logger:
            await adapter.ensure_table()
            assert mock_logger.info.call_count == 1

            mock_logger.info.reset_mock()
            await adapter.ensure_table()
            assert mock_logger.info.call_count == 0

    @pytest.mark.asyncio()
    async def test_exists_returns_true_when_row_found(
        self, mock_pool: MagicMock
    ) -> None:
        """exists() returns True when pool.fetchrow returns a row."""
        mock_pool.fetchrow.return_value = {"?column?": 1}
        request_id = uuid4()

        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        result = await adapter.exists(request_id)

        mock_pool.fetchrow.assert_awaited_once_with(SQL_IDEMPOTENCY_EXISTS, request_id)
        assert result is True

    @pytest.mark.asyncio()
    async def test_exists_returns_false_when_no_row(self, mock_pool: MagicMock) -> None:
        """exists() returns False when pool.fetchrow returns None."""
        mock_pool.fetchrow.return_value = None
        request_id = uuid4()

        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        result = await adapter.exists(request_id)

        mock_pool.fetchrow.assert_awaited_once_with(SQL_IDEMPOTENCY_EXISTS, request_id)
        assert result is False

    @pytest.mark.asyncio()
    async def test_record_delegates_insert_to_pool(self, mock_pool: MagicMock) -> None:
        """record() delegates INSERT to pool.execute."""
        request_id = uuid4()

        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        await adapter.record(request_id)

        mock_pool.execute.assert_awaited_once_with(SQL_IDEMPOTENCY_RECORD, request_id)

    @pytest.mark.asyncio()
    async def test_check_and_record_returns_true_for_duplicate(
        self, mock_pool: MagicMock
    ) -> None:
        """check_and_record() returns True (duplicate) when fetchrow returns None.

        When INSERT ... ON CONFLICT DO NOTHING RETURNING yields no row,
        it means the row already existed (conflict), so this is a duplicate.
        """
        mock_pool.fetchrow.return_value = None
        request_id = uuid4()

        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        result = await adapter.check_and_record(request_id)

        mock_pool.fetchrow.assert_awaited_once_with(
            SQL_IDEMPOTENCY_CHECK_AND_RECORD, request_id
        )
        assert result is True

    @pytest.mark.asyncio()
    async def test_check_and_record_returns_false_for_new(
        self, mock_pool: MagicMock
    ) -> None:
        """check_and_record() returns False (new) when fetchrow returns a row.

        When INSERT ... RETURNING yields a row, it means the insert succeeded
        (no conflict), so this is a new request.
        """
        mock_pool.fetchrow.return_value = {"request_id": uuid4()}
        request_id = uuid4()

        adapter = AdapterIdempotencyStorePostgres(mock_pool)
        result = await adapter.check_and_record(request_id)

        mock_pool.fetchrow.assert_awaited_once_with(
            SQL_IDEMPOTENCY_CHECK_AND_RECORD, request_id
        )
        assert result is False


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
