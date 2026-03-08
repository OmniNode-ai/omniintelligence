# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Tests for handle_protocol_execute and ProtocolHandlerRegistry.

Tests cover:
    - Successful protocol execution for each protocol type
    - Missing handler (no handler registered)
    - ConnectionError handling
    - TimeoutError handling
    - Generic exception handling
    - Correlation ID threading
    - Duration timing
    - Registry disconnect_all
    - Input model validation

Ticket: OMN-373
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omniintelligence.nodes.node_protocol_handler_effect.handlers import (
    ProtocolHandlerRegistry,
    handle_protocol_execute,
)
from omniintelligence.nodes.node_protocol_handler_effect.models import (
    EnumHandlerStatus,
    EnumProtocolType,
)
from omniintelligence.nodes.node_protocol_handler_effect.node_tests.conftest import (
    FIXED_CORRELATION_ID,
    MockProtocolHandler,
    make_input,
    make_registry,
)

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# handle_protocol_execute tests - Success paths
# =============================================================================


class TestHandleProtocolExecuteSuccess:
    """Tests for successful protocol execution."""

    @pytest.mark.asyncio
    async def test_http_rest_success(self) -> None:
        """HTTP REST handler returns SUCCESS with result data."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_result = {"status_code": 200, "body": {"ok": True}}
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
            params={"path": "/health"},
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.SUCCESS
        assert result.protocol == EnumProtocolType.HTTP_REST
        assert result.operation == "GET"
        assert result.result == {"status_code": 200, "body": {"ok": True}}
        assert result.error_message is None
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_bolt_success(self) -> None:
        """Bolt handler returns SUCCESS with query records."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_result = {"records": [{"name": "Alice"}], "summary": {}}
        registry = make_registry(
            handlers={EnumProtocolType.BOLT: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.BOLT,
            operation="query",
            params={"cypher": "MATCH (n) RETURN n LIMIT 1"},
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.SUCCESS
        assert result.protocol == EnumProtocolType.BOLT
        assert result.result is not None
        assert result.result["records"] == [{"name": "Alice"}]

    @pytest.mark.asyncio
    async def test_postgresql_success(self) -> None:
        """PostgreSQL handler returns SUCCESS with query rows."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_result = {"rows": [{"id": 1}], "row_count": 1}
        registry = make_registry(
            handlers={EnumProtocolType.POSTGRESQL: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.POSTGRESQL,
            operation="query",
            params={"sql": "SELECT 1 AS id"},
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.SUCCESS
        assert result.protocol == EnumProtocolType.POSTGRESQL
        assert result.result is not None
        assert result.result["row_count"] == 1

    @pytest.mark.asyncio
    async def test_kafka_success(self) -> None:
        """Kafka handler returns SUCCESS with delivery confirmation."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_result = {"topic": "test-topic", "delivered": True}
        registry = make_registry(
            handlers={EnumProtocolType.KAFKA: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.KAFKA,
            operation="produce",
            params={"topic": "test-topic", "value": {"key": "value"}},
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.SUCCESS
        assert result.protocol == EnumProtocolType.KAFKA
        assert result.result is not None
        assert result.result["delivered"] is True


# =============================================================================
# handle_protocol_execute tests - Error paths
# =============================================================================


class TestHandleProtocolExecuteErrors:
    """Tests for protocol execution error handling."""

    @pytest.mark.asyncio
    async def test_missing_handler_returns_not_connected(self) -> None:
        """Missing handler returns NOT_CONNECTED status."""
        registry = ProtocolHandlerRegistry(handlers={})

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.NOT_CONNECTED
        assert "No handler registered" in (result.error_message or "")
        assert result.result is None

    @pytest.mark.asyncio
    async def test_connection_error_returns_connection_error(self) -> None:
        """ConnectionError from handler returns CONNECTION_ERROR status."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_error = ConnectionError("Connection refused")
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.CONNECTION_ERROR
        assert "Connection error" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_timeout_error_returns_timeout(self) -> None:
        """TimeoutError from handler returns TIMEOUT status."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_error = TimeoutError("Request timed out")
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.TIMEOUT
        assert "Timeout" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_generic_exception_returns_failed(self) -> None:
        """Generic exception from handler returns FAILED status."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_error = RuntimeError("Something went wrong")
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.status == EnumHandlerStatus.FAILED
        assert "Operation failed" in (result.error_message or "")


# =============================================================================
# Correlation ID threading
# =============================================================================


class TestCorrelationIdThreading:
    """Tests for correlation ID propagation."""

    @pytest.mark.asyncio
    async def test_correlation_id_passed_to_handler(self) -> None:
        """Correlation ID is passed through to the handler execute call."""
        mock_handler = MockProtocolHandler()
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
            correlation_id=FIXED_CORRELATION_ID,
        )

        await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert len(mock_handler.execute_calls) == 1
        _, _, call_correlation_id = mock_handler.execute_calls[0]
        assert call_correlation_id == str(FIXED_CORRELATION_ID)

    @pytest.mark.asyncio
    async def test_correlation_id_preserved_in_output(self) -> None:
        """Correlation ID from input is preserved in output."""
        mock_handler = MockProtocolHandler()
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
            correlation_id=FIXED_CORRELATION_ID,
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.correlation_id == FIXED_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_none_correlation_id_handled(self) -> None:
        """None correlation ID is handled gracefully."""
        mock_handler = MockProtocolHandler()
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
            correlation_id=None,
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.correlation_id is None
        assert result.status == EnumHandlerStatus.SUCCESS

        _, _, call_correlation_id = mock_handler.execute_calls[0]
        assert call_correlation_id is None


# =============================================================================
# Registry tests
# =============================================================================


class TestProtocolHandlerRegistry:
    """Tests for ProtocolHandlerRegistry."""

    def test_get_handler_returns_registered(self) -> None:
        """get_handler returns the registered handler."""
        mock_handler = MockProtocolHandler()
        registry = ProtocolHandlerRegistry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},  # type: ignore[dict-item]
        )

        result = registry.get_handler(EnumProtocolType.HTTP_REST)
        assert result is mock_handler

    def test_get_handler_returns_none_for_missing(self) -> None:
        """get_handler returns None for unregistered protocol."""
        registry = ProtocolHandlerRegistry(handlers={})

        result = registry.get_handler(EnumProtocolType.BOLT)
        assert result is None

    @pytest.mark.asyncio
    async def test_disconnect_all_disconnects_handlers(self) -> None:
        """disconnect_all calls disconnect on all registered handlers."""
        http_handler = MockProtocolHandler()
        bolt_handler = MockProtocolHandler()
        http_handler.connected = True
        bolt_handler.connected = True

        registry = ProtocolHandlerRegistry(
            handlers={
                EnumProtocolType.HTTP_REST: http_handler,  # type: ignore[dict-item]
                EnumProtocolType.BOLT: bolt_handler,  # type: ignore[dict-item]
            },
        )

        await registry.disconnect_all()

        assert http_handler.disconnect_calls == 1
        assert bolt_handler.disconnect_calls == 1

    @pytest.mark.asyncio
    async def test_disconnect_all_continues_on_error(self) -> None:
        """disconnect_all continues if a handler raises during disconnect."""
        http_handler = MockProtocolHandler()
        bolt_handler = MockProtocolHandler()

        # Make HTTP handler's disconnect raise
        original_disconnect = http_handler.disconnect

        async def failing_disconnect() -> None:
            raise RuntimeError("Disconnect failed")

        http_handler.disconnect = failing_disconnect  # type: ignore[assignment]

        registry = ProtocolHandlerRegistry(
            handlers={
                EnumProtocolType.HTTP_REST: http_handler,  # type: ignore[dict-item]
                EnumProtocolType.BOLT: bolt_handler,  # type: ignore[dict-item]
            },
        )

        # Should not raise
        await registry.disconnect_all()

        # Bolt handler should still be disconnected
        assert bolt_handler.disconnect_calls == 1


# =============================================================================
# Duration and timing tests
# =============================================================================


class TestDurationTiming:
    """Tests for duration_ms field in output."""

    @pytest.mark.asyncio
    async def test_duration_is_non_negative(self) -> None:
        """Duration is always non-negative."""
        mock_handler = MockProtocolHandler()
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_duration_measured_on_error(self) -> None:
        """Duration is measured even when operation fails."""
        mock_handler = MockProtocolHandler()
        mock_handler.execute_error = RuntimeError("fail")
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.duration_ms >= 0
        assert result.status == EnumHandlerStatus.FAILED


# =============================================================================
# Retry count propagation
# =============================================================================


class TestRetryCount:
    """Tests for retry_count propagation."""

    @pytest.mark.asyncio
    async def test_retry_count_propagated(self) -> None:
        """retry_count from input is propagated to output."""
        mock_handler = MockProtocolHandler()
        registry = make_registry(
            handlers={EnumProtocolType.HTTP_REST: mock_handler},
        )

        input_data = make_input(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
            retry_count=2,
        )

        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        assert result.retry_count == 2


# =============================================================================
# Input model validation
# =============================================================================


class TestInputModelValidation:
    """Tests for ModelProtocolHandlerInput validation."""

    def test_empty_operation_rejected(self) -> None:
        """Empty operation string is rejected by model validation."""
        with pytest.raises(ValueError):
            make_input(operation="")

    def test_negative_retry_count_rejected(self) -> None:
        """Negative retry_count is rejected by model validation."""
        with pytest.raises(ValueError):
            make_input(retry_count=-1)

    def test_frozen_input_model(self) -> None:
        """Input model is frozen (immutable)."""
        input_data = make_input()
        with pytest.raises(ValidationError):
            input_data.operation = "POST"  # type: ignore[misc]
