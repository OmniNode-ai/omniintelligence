# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Test fixtures for Protocol Handler Effect node tests.

Provides mock handler implementations, factory functions, and
fixed test data for unit testing protocol handlers.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_protocol import (
    ProtocolHandlerRegistry,
)
from omniintelligence.nodes.node_protocol_handler_effect.models import (
    EnumProtocolType,
    ModelProtocolHandlerInput,
)

# =============================================================================
# Fixed Test Data
# =============================================================================

FIXED_CORRELATION_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


# =============================================================================
# Mock Handler
# =============================================================================


class MockProtocolHandler:
    """Mock protocol handler for unit testing.

    Records calls and allows configuring responses and errors.

    Attributes:
        connected: Whether connect() has been called.
        connect_calls: List of config dicts passed to connect().
        execute_calls: List of (operation, params, correlation_id) tuples.
        disconnect_calls: Count of disconnect() calls.
        health_check_result: Value returned by health_check().
        execute_result: Value returned by execute().
        execute_error: Exception to raise from execute() (if set).
    """

    def __init__(self) -> None:
        self.connected: bool = False
        self.connect_calls: list[dict[str, Any]] = []
        self.execute_calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.disconnect_calls: int = 0
        self.health_check_result: bool = True
        self.execute_result: dict[str, Any] = {"status": "ok"}
        self.execute_error: Exception | None = None

    async def connect(self, config: dict[str, Any]) -> None:
        self.connect_calls.append(config)
        self.connected = True

    async def execute(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        self.execute_calls.append((operation, params, correlation_id))
        if self.execute_error is not None:
            raise self.execute_error
        return self.execute_result

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False

    async def health_check(self) -> bool:
        return self.health_check_result


# =============================================================================
# Factory Functions
# =============================================================================


def make_input(
    *,
    protocol: EnumProtocolType = EnumProtocolType.HTTP_REST,
    operation: str = "GET",
    config: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    correlation_id: UUID | None = FIXED_CORRELATION_ID,
    retry_count: int = 0,
) -> ModelProtocolHandlerInput:
    """Create a ModelProtocolHandlerInput with sensible defaults.

    Args:
        protocol: Protocol type.
        operation: Operation to execute.
        config: Protocol-specific config.
        params: Operation-specific params.
        correlation_id: Correlation ID.
        retry_count: Retry count.

    Returns:
        ModelProtocolHandlerInput instance.
    """
    return ModelProtocolHandlerInput(
        protocol=protocol,
        operation=operation,
        config=config or {},
        params=params or {},
        correlation_id=correlation_id,
        retry_count=retry_count,
    )


def make_registry(
    *,
    handlers: dict[EnumProtocolType, MockProtocolHandler] | None = None,
) -> ProtocolHandlerRegistry:
    """Create a ProtocolHandlerRegistry with mock handlers.

    Args:
        handlers: Mapping of protocol type to mock handler.
            If None, creates a default registry with an HTTP handler.

    Returns:
        ProtocolHandlerRegistry instance.
    """
    if handlers is None:
        handlers = {EnumProtocolType.HTTP_REST: MockProtocolHandler()}
    return ProtocolHandlerRegistry(handlers=handlers)  # type: ignore[arg-type]


__all__ = [
    "FIXED_CORRELATION_ID",
    "MockProtocolHandler",
    "make_input",
    "make_registry",
]
