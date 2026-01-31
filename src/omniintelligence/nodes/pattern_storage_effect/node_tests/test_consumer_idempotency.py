# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration tests for consumer idempotency handling.

Tests the IdempotencyGate for Kafka event deduplication and
ModelEventEnvelope validation for required fields.

Reference: OMN-1669 (STORE-004)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.pattern_storage_effect.consumer.envelope import (
    ModelEventEnvelope,
)
from omniintelligence.nodes.pattern_storage_effect.consumer.idempotency import (
    IdempotencyGate,
    cleanup_processed_events,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_conn() -> MagicMock:
    """Create a mock asyncpg connection.

    Returns:
        Mock connection with fetchval and execute as AsyncMock.
    """
    conn = MagicMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()
    return conn


# =============================================================================
# IdempotencyGate Tests
# =============================================================================


@pytest.mark.unit
class TestIdempotencyGate:
    """Tests for IdempotencyGate.check_and_mark()."""

    @pytest.mark.asyncio
    async def test_idempotency_gate_first_event(self, mock_conn: MagicMock) -> None:
        """First event with unique ID should return True (is_new).

        When INSERT ON CONFLICT DO NOTHING RETURNING succeeds, it returns
        the event_id, indicating this is the first time we've seen this event.
        """
        gate = IdempotencyGate()
        event_id = uuid4()

        # Mock fetchval to return the event_id (simulating successful insert)
        mock_conn.fetchval.return_value = event_id

        result = await gate.check_and_mark(mock_conn, event_id)

        assert result is True
        mock_conn.fetchval.assert_called_once()
        # Verify the SQL contains the expected INSERT pattern
        call_args = mock_conn.fetchval.call_args
        sql = call_args[0][0]
        assert "INSERT INTO processed_events" in sql
        assert "ON CONFLICT DO NOTHING" in sql
        assert "RETURNING event_id" in sql
        # Verify event_id was passed as parameter
        assert call_args[0][1] == event_id

    @pytest.mark.asyncio
    async def test_idempotency_gate_duplicate_event(
        self, mock_conn: MagicMock
    ) -> None:
        """Second call with same event_id returns False (duplicate).

        When INSERT ON CONFLICT DO NOTHING doesn't insert (conflict),
        RETURNING yields nothing (None), indicating a duplicate event.
        """
        gate = IdempotencyGate()
        event_id = uuid4()

        # Mock fetchval to return None (simulating conflict - duplicate)
        mock_conn.fetchval.return_value = None

        result = await gate.check_and_mark(mock_conn, event_id)

        assert result is False
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotency_gate_multiple_unique_events(
        self, mock_conn: MagicMock
    ) -> None:
        """Multiple unique events should all return True."""
        gate = IdempotencyGate()

        event_ids = [uuid4() for _ in range(3)]
        results = []

        for event_id in event_ids:
            # Each unique event returns its ID (successful insert)
            mock_conn.fetchval.return_value = event_id
            result = await gate.check_and_mark(mock_conn, event_id)
            results.append(result)

        assert all(r is True for r in results)
        assert mock_conn.fetchval.call_count == 3


# =============================================================================
# Cleanup Tests
# =============================================================================


@pytest.mark.unit
class TestCleanup:
    """Tests for cleanup_processed_events()."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_events(self, mock_conn: MagicMock) -> None:
        """Events older than retention are deleted."""
        mock_conn.execute.return_value = "DELETE 5"

        result = await cleanup_processed_events(mock_conn, retention_days=7)

        assert result == 5
        mock_conn.execute.assert_called_once()
        # Verify the SQL contains DELETE with retention interval
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        assert "DELETE FROM processed_events" in sql
        assert "INTERVAL" in sql
        # Verify retention_days was passed
        assert call_args[0][1] == 7

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_events(self, mock_conn: MagicMock) -> None:
        """Events within retention period are kept (delete returns 0)."""
        mock_conn.execute.return_value = "DELETE 0"

        result = await cleanup_processed_events(mock_conn, retention_days=7)

        assert result == 0

    @pytest.mark.asyncio
    async def test_cleanup_default_retention(self, mock_conn: MagicMock) -> None:
        """Default retention of 7 days is used when not specified."""
        mock_conn.execute.return_value = "DELETE 10"

        result = await cleanup_processed_events(mock_conn)

        assert result == 10
        # Verify default retention_days=7 was passed
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == 7

    @pytest.mark.asyncio
    async def test_cleanup_custom_retention(self, mock_conn: MagicMock) -> None:
        """Custom retention period is respected."""
        mock_conn.execute.return_value = "DELETE 100"

        result = await cleanup_processed_events(mock_conn, retention_days=30)

        assert result == 100
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == 30


# =============================================================================
# EventEnvelope Validation Tests
# =============================================================================


@pytest.mark.unit
class TestEventEnvelope:
    """Tests for ModelEventEnvelope validation."""

    def test_envelope_validation_valid(self) -> None:
        """Valid envelope should pass validation."""
        data = {
            "event_id": str(uuid4()),
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
        }

        envelope = ModelEventEnvelope.model_validate(data)

        assert envelope.producer_id == "test-producer"
        assert envelope.schema_version == "1.0.0"
        assert envelope.correlation_id is None

    def test_envelope_with_correlation_id(self) -> None:
        """Envelope with optional correlation_id should pass."""
        corr_id = uuid4()
        data = {
            "event_id": str(uuid4()),
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
            "correlation_id": str(corr_id),
        }

        envelope = ModelEventEnvelope.model_validate(data)

        assert envelope.correlation_id == corr_id

    def test_envelope_validation_missing_event_id(self) -> None:
        """Missing event_id should raise ValidationError."""
        data = {
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
        }

        with pytest.raises(ValidationError) as exc_info:
            ModelEventEnvelope.model_validate(data)

        # Verify event_id is mentioned in the error
        errors = exc_info.value.errors()
        assert any(err["loc"] == ("event_id",) for err in errors)

    def test_envelope_validation_missing_event_time(self) -> None:
        """Missing event_time should raise ValidationError."""
        data = {
            "event_id": str(uuid4()),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
        }

        with pytest.raises(ValidationError) as exc_info:
            ModelEventEnvelope.model_validate(data)

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("event_time",) for err in errors)

    def test_envelope_validation_missing_producer_id(self) -> None:
        """Missing producer_id should raise ValidationError."""
        data = {
            "event_id": str(uuid4()),
            "event_time": datetime.now(UTC).isoformat(),
            "schema_version": "1.0.0",
        }

        with pytest.raises(ValidationError) as exc_info:
            ModelEventEnvelope.model_validate(data)

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("producer_id",) for err in errors)

    def test_envelope_validation_missing_schema_version(self) -> None:
        """Missing schema_version should raise ValidationError."""
        data = {
            "event_id": str(uuid4()),
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
        }

        with pytest.raises(ValidationError) as exc_info:
            ModelEventEnvelope.model_validate(data)

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("schema_version",) for err in errors)

    def test_envelope_invalid_event_id_format(self) -> None:
        """Invalid UUID format for event_id should raise ValidationError."""
        data = {
            "event_id": "not-a-uuid",
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
        }

        with pytest.raises(ValidationError) as exc_info:
            ModelEventEnvelope.model_validate(data)

        errors = exc_info.value.errors()
        assert any("event_id" in str(err["loc"]) for err in errors)

    def test_envelope_is_frozen(self) -> None:
        """Envelope should be immutable (frozen)."""
        data = {
            "event_id": str(uuid4()),
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
        }

        envelope = ModelEventEnvelope.model_validate(data)

        # Attempting to modify should raise an error
        with pytest.raises(ValidationError):
            envelope.producer_id = "modified"  # type: ignore[misc]

    def test_envelope_event_id_is_uuid_type(self) -> None:
        """event_id should be parsed as UUID type."""
        event_id = uuid4()
        data = {
            "event_id": str(event_id),
            "event_time": datetime.now(UTC).isoformat(),
            "producer_id": "test-producer",
            "schema_version": "1.0.0",
        }

        envelope = ModelEventEnvelope.model_validate(data)

        assert isinstance(envelope.event_id, type(event_id))
        assert envelope.event_id == event_id
