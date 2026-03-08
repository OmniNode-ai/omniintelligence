# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Protocol handler base protocol and registry.

Defines the ProtocolHandler protocol that all protocol-specific handlers
must implement, and the ProtocolHandlerRegistry for resolving handlers
by protocol type.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from omniintelligence.nodes.node_protocol_handler_effect.models import (
    EnumHandlerStatus,
    EnumProtocolType,
    ModelProtocolHandlerInput,
    ModelProtocolHandlerOutput,
)

# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definition
# =============================================================================


@runtime_checkable
class ProtocolHandler(Protocol):
    """Protocol for transport/wire protocol handlers.

    Each handler abstracts the details of a specific protocol (HTTP, Bolt,
    PostgreSQL, Kafka) behind a uniform interface for connect, execute,
    disconnect, and health_check operations.

    Implementations MUST:
        - Support connection pooling where applicable
        - Return structured errors (not raise for domain errors)
        - Thread correlation_id through all operations
        - Be safe for concurrent use from multiple coroutines
    """

    async def connect(self, config: dict[str, Any]) -> None:
        """Establish a connection to the protocol backend.

        Args:
            config: Protocol-specific connection configuration.
                HTTP: {"base_url": str, "timeout": float, "headers": dict}
                Bolt: {"uri": str, "auth": tuple, "database": str}
                PostgreSQL: {"dsn": str, "min_size": int, "max_size": int}
                Kafka: {"bootstrap_servers": str, "client_id": str}

        Raises:
            ConnectionError: If the connection cannot be established.
        """
        ...

    async def execute(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a protocol operation.

        Args:
            operation: The operation to perform (protocol-specific).
                HTTP: "GET", "POST", "PUT", "DELETE"
                Bolt: "query", "write"
                PostgreSQL: "query", "execute"
                Kafka: "produce", "consume"
            params: Operation-specific parameters.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            dict with protocol-specific result data.

        Raises:
            RuntimeError: If handler is not connected.
            TimeoutError: If the operation times out.
        """
        ...

    async def disconnect(self) -> None:
        """Close the connection and release resources.

        Must be idempotent - calling disconnect on an already-disconnected
        handler must not raise.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the handler's connection is healthy.

        Returns:
            True if the connection is healthy and operational.
            False if disconnected or unhealthy.
        """
        ...


# =============================================================================
# Handler Registry
# =============================================================================


@dataclass
class ProtocolHandlerRegistry:
    """Registry mapping protocol types to handler implementations.

    Provides handler lookup and lifecycle management for all
    registered protocol handlers.

    Attributes:
        handlers: Mapping of protocol type to handler implementation.
    """

    handlers: dict[EnumProtocolType, ProtocolHandler] = field(
        default_factory=dict,
    )

    def get_handler(self, protocol: EnumProtocolType) -> ProtocolHandler | None:
        """Get the handler for a specific protocol type.

        Args:
            protocol: The protocol type to look up.

        Returns:
            The handler implementation, or None if not registered.
        """
        return self.handlers.get(protocol)

    async def disconnect_all(self) -> None:
        """Disconnect all registered handlers.

        Logs errors but does not raise - ensures all handlers
        get a chance to clean up even if some fail.
        """
        for protocol_type, handler in self.handlers.items():
            try:
                await handler.disconnect()
            except Exception:
                logger.exception(
                    "Failed to disconnect handler",
                    extra={"protocol": protocol_type.value},
                )


# =============================================================================
# Main Handler Function
# =============================================================================


async def handle_protocol_execute(
    input_data: ModelProtocolHandlerInput,
    *,
    handler_registry: ProtocolHandlerRegistry,
) -> ModelProtocolHandlerOutput:
    """Execute a protocol operation via the appropriate handler.

    Execution Flow:
        1. Look up handler from registry by protocol type
        2. If no handler registered, return NOT_CONNECTED status
        3. Execute the operation via the handler
        4. Return structured result with timing

    Error Handling:
        - Missing handler: returns NOT_CONNECTED (structured, no raise)
        - ConnectionError: returns CONNECTION_ERROR
        - TimeoutError: returns TIMEOUT
        - Other exceptions: returns FAILED with error message

    Args:
        input_data: The protocol operation request.
        handler_registry: Registry of protocol handlers.

    Returns:
        ModelProtocolHandlerOutput with the operation result.
    """
    start_time = time.perf_counter()
    correlation_str = (
        str(input_data.correlation_id) if input_data.correlation_id else None
    )

    # -------------------------------------------------------------------------
    # Step 1: Look up handler
    # -------------------------------------------------------------------------
    handler = handler_registry.get_handler(input_data.protocol)

    if handler is None:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "No handler registered for protocol",
            extra={
                "protocol": input_data.protocol.value,
                "operation": input_data.operation,
                "correlation_id": correlation_str,
            },
        )
        return ModelProtocolHandlerOutput(
            correlation_id=input_data.correlation_id,
            protocol=input_data.protocol,
            operation=input_data.operation,
            status=EnumHandlerStatus.NOT_CONNECTED,
            error_message=f"No handler registered for protocol: {input_data.protocol.value}",
            executed_at=datetime.now(UTC),
            duration_ms=elapsed_ms,
            retry_count=input_data.retry_count,
        )

    # -------------------------------------------------------------------------
    # Step 2: Execute operation
    # -------------------------------------------------------------------------
    try:
        result = await handler.execute(
            input_data.operation,
            input_data.params,
            correlation_id=correlation_str,
        )
    except ConnectionError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Connection error for {input_data.protocol.value}: {exc}"
        logger.exception(
            "Protocol handler connection error",
            extra={
                "protocol": input_data.protocol.value,
                "operation": input_data.operation,
                "correlation_id": correlation_str,
            },
        )
        return ModelProtocolHandlerOutput(
            correlation_id=input_data.correlation_id,
            protocol=input_data.protocol,
            operation=input_data.operation,
            status=EnumHandlerStatus.CONNECTION_ERROR,
            error_message=error_msg,
            executed_at=datetime.now(UTC),
            duration_ms=elapsed_ms,
            retry_count=input_data.retry_count,
        )

    except TimeoutError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Timeout for {input_data.protocol.value}: {exc}"
        logger.exception(
            "Protocol handler timeout",
            extra={
                "protocol": input_data.protocol.value,
                "operation": input_data.operation,
                "correlation_id": correlation_str,
            },
        )
        return ModelProtocolHandlerOutput(
            correlation_id=input_data.correlation_id,
            protocol=input_data.protocol,
            operation=input_data.operation,
            status=EnumHandlerStatus.TIMEOUT,
            error_message=error_msg,
            executed_at=datetime.now(UTC),
            duration_ms=elapsed_ms,
            retry_count=input_data.retry_count,
        )

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        error_msg = f"Operation failed for {input_data.protocol.value}: {exc}"
        logger.exception(
            "Protocol handler operation failed",
            extra={
                "protocol": input_data.protocol.value,
                "operation": input_data.operation,
                "correlation_id": correlation_str,
            },
        )
        return ModelProtocolHandlerOutput(
            correlation_id=input_data.correlation_id,
            protocol=input_data.protocol,
            operation=input_data.operation,
            status=EnumHandlerStatus.FAILED,
            error_message=error_msg,
            executed_at=datetime.now(UTC),
            duration_ms=elapsed_ms,
            retry_count=input_data.retry_count,
        )

    # -------------------------------------------------------------------------
    # Step 3: Success
    # -------------------------------------------------------------------------
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Protocol operation succeeded",
        extra={
            "protocol": input_data.protocol.value,
            "operation": input_data.operation,
            "duration_ms": elapsed_ms,
            "correlation_id": correlation_str,
        },
    )

    return ModelProtocolHandlerOutput(
        correlation_id=input_data.correlation_id,
        protocol=input_data.protocol,
        operation=input_data.operation,
        status=EnumHandlerStatus.SUCCESS,
        result=result,
        executed_at=datetime.now(UTC),
        duration_ms=elapsed_ms,
        retry_count=input_data.retry_count,
    )


__all__ = [
    "ProtocolHandler",
    "ProtocolHandlerRegistry",
    "handle_protocol_execute",
]
