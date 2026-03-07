# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handler for storage routing operations.

Routes completed compute events to the appropriate storage backend
based on event type. Handles storage failures with retry logic and
DLQ routing.

Routing Rules:
    - vectorization.completed -> Qdrant vector storage
    - entity.extraction-completed -> Memgraph graph storage
    - pattern.matched -> PostgreSQL pattern storage

Reference:
    - OMN-371: Storage router effect node
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from omniintelligence.nodes.node_storage_router_effect.models import (
    EnumStorageBackend,
    EnumStorageRouteStatus,
    ModelStorageRouteInput,
    ModelStorageRouteOutput,
)

# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Maximum number of retries before routing to DLQ
MAX_RETRIES = 3

# Event type to storage backend mapping
ROUTING_TABLE: dict[str, EnumStorageBackend] = {
    "vectorization.completed": EnumStorageBackend.QDRANT,
    "entity.extraction-completed": EnumStorageBackend.MEMGRAPH,
    "pattern.matched": EnumStorageBackend.POSTGRESQL,
}


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class ProtocolStorageClient(Protocol):
    """Protocol for storage backend clients.

    Implementations must handle storing payloads in their respective
    storage backends. Each implementation is responsible for backend-specific
    serialization, connection management, and error handling.
    """

    async def store(
        self,
        *,
        event_id: UUID,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
    ) -> None:
        """Store a payload in the backend.

        Args:
            event_id: Unique identifier for this event.
            payload: The data to store.
            correlation_id: Correlation ID for distributed tracing.

        Raises:
            StorageError: If the storage operation fails.
        """
        ...


@runtime_checkable
class ProtocolDlqPublisher(Protocol):
    """Protocol for publishing failed events to a dead letter queue.

    DLQ messages include the original event, error details, and
    retry metadata for later reprocessing.
    """

    async def publish_to_dlq(
        self,
        *,
        event_id: UUID,
        original_event: dict[str, Any],
        error_message: str,
        retry_count: int,
        correlation_id: UUID | None = None,
    ) -> None:
        """Publish a failed event to the dead letter queue.

        Args:
            event_id: Unique identifier for the failed event.
            original_event: The original event payload.
            error_message: Description of the failure.
            retry_count: Number of attempts made.
            correlation_id: Correlation ID for tracing.
        """
        ...


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class RouteStorageResult:
    """Internal result from a storage routing operation.

    Attributes:
        success: Whether the routing operation succeeded.
        output: The output event if produced.
        error_message: Error message if failed.
        routed_to_dlq: Whether the event was sent to the DLQ.
    """

    success: bool
    output: ModelStorageRouteOutput | None = None
    error_message: str | None = None
    routed_to_dlq: bool = False


@dataclass
class StorageClientRegistry:
    """Registry of storage backend clients.

    Maps storage backends to their client implementations.
    This is a frozen configuration provided at initialization.

    Attributes:
        clients: Mapping of backend type to client implementation.
    """

    clients: dict[EnumStorageBackend, ProtocolStorageClient] = field(
        default_factory=dict,
    )

    def get_client(self, backend: EnumStorageBackend) -> ProtocolStorageClient | None:
        """Get the client for a specific backend.

        Args:
            backend: The storage backend to look up.

        Returns:
            The client implementation, or None if not registered.
        """
        return self.clients.get(backend)


# =============================================================================
# Routing Logic
# =============================================================================


def resolve_backend(event_type: str) -> EnumStorageBackend | None:
    """Resolve the target storage backend for an event type.

    Uses the ROUTING_TABLE to determine which storage backend
    should receive events of the given type.

    Args:
        event_type: The compute event type to route.

    Returns:
        The target storage backend, or None if no routing rule exists.
    """
    return ROUTING_TABLE.get(event_type)


# =============================================================================
# Main Handler
# =============================================================================


async def handle_route_storage(
    input_data: ModelStorageRouteInput,
    *,
    client_registry: StorageClientRegistry,
    dlq_publisher: ProtocolDlqPublisher | None = None,
) -> RouteStorageResult:
    """Route a compute event to the appropriate storage backend.

    Routing Flow:
        1. Resolve target backend from event_type using ROUTING_TABLE
        2. If no routing rule exists, return UNROUTABLE status
        3. Look up storage client for the target backend
        4. Attempt storage (client.store)
        5. On failure with retries remaining, return FAILED status
        6. On failure with retries exhausted, route to DLQ
        7. On success, return STORED status

    Error Handling:
        Domain errors (unroutable event type, missing client) are returned
        as structured results following the ONEX handler pattern.
        Infrastructure errors (storage failures) trigger DLQ routing
        when retries are exhausted.

    Args:
        input_data: The compute event to route.
        client_registry: Registry of storage backend clients.
        dlq_publisher: Optional DLQ publisher for failed events.

    Returns:
        RouteStorageResult with the routing outcome.
    """
    routed_at = datetime.now(UTC)

    # -------------------------------------------------------------------------
    # Step 1: Resolve target backend
    # -------------------------------------------------------------------------
    target_backend = resolve_backend(input_data.event_type)

    if target_backend is None:
        logger.warning(
            "No routing rule for event type",
            extra={
                "event_id": str(input_data.event_id),
                "event_type": input_data.event_type,
                "source_node": input_data.source_node,
                "correlation_id": (
                    str(input_data.correlation_id)
                    if input_data.correlation_id
                    else None
                ),
            },
        )
        return RouteStorageResult(
            success=False,
            output=ModelStorageRouteOutput(
                event_id=input_data.event_id,
                correlation_id=input_data.correlation_id,
                target_backend=None,
                status=EnumStorageRouteStatus.UNROUTABLE,
                routed_at=routed_at,
                error_message=f"No routing rule for event type: {input_data.event_type}",
                retry_count=input_data.retry_count,
            ),
            error_message=f"No routing rule for event type: {input_data.event_type}",
        )

    # -------------------------------------------------------------------------
    # Step 2: Look up storage client
    # -------------------------------------------------------------------------
    client = client_registry.get_client(target_backend)

    if client is None:
        msg = f"No storage client registered for backend: {target_backend.value}"
        logger.error(
            msg,
            extra={
                "event_id": str(input_data.event_id),
                "target_backend": target_backend.value,
                "correlation_id": (
                    str(input_data.correlation_id)
                    if input_data.correlation_id
                    else None
                ),
            },
        )
        return RouteStorageResult(
            success=False,
            output=ModelStorageRouteOutput(
                event_id=input_data.event_id,
                correlation_id=input_data.correlation_id,
                target_backend=target_backend,
                status=EnumStorageRouteStatus.FAILED,
                routed_at=routed_at,
                error_message=msg,
                retry_count=input_data.retry_count,
            ),
            error_message=msg,
        )

    # -------------------------------------------------------------------------
    # Step 3: Attempt storage
    # -------------------------------------------------------------------------
    try:
        await client.store(
            event_id=input_data.event_id,
            payload=input_data.payload,
            correlation_id=input_data.correlation_id,
        )
    except Exception as exc:
        error_msg = f"Storage failed for {target_backend.value}: {exc}"
        logger.exception(
            "Storage operation failed",
            extra={
                "event_id": str(input_data.event_id),
                "target_backend": target_backend.value,
                "retry_count": input_data.retry_count,
                "max_retries": MAX_RETRIES,
                "correlation_id": (
                    str(input_data.correlation_id)
                    if input_data.correlation_id
                    else None
                ),
            },
        )

        # Check if retries exhausted
        if input_data.retry_count >= MAX_RETRIES:
            return await _route_to_dlq(
                input_data=input_data,
                target_backend=target_backend,
                error_message=error_msg,
                dlq_publisher=dlq_publisher,
                routed_at=routed_at,
            )

        return RouteStorageResult(
            success=False,
            output=ModelStorageRouteOutput(
                event_id=input_data.event_id,
                correlation_id=input_data.correlation_id,
                target_backend=target_backend,
                status=EnumStorageRouteStatus.FAILED,
                routed_at=routed_at,
                error_message=error_msg,
                retry_count=input_data.retry_count,
            ),
            error_message=error_msg,
        )

    # -------------------------------------------------------------------------
    # Step 4: Success
    # -------------------------------------------------------------------------
    logger.info(
        "Event stored successfully",
        extra={
            "event_id": str(input_data.event_id),
            "event_type": input_data.event_type,
            "target_backend": target_backend.value,
            "source_node": input_data.source_node,
            "correlation_id": (
                str(input_data.correlation_id) if input_data.correlation_id else None
            ),
        },
    )

    return RouteStorageResult(
        success=True,
        output=ModelStorageRouteOutput(
            event_id=input_data.event_id,
            correlation_id=input_data.correlation_id,
            target_backend=target_backend,
            status=EnumStorageRouteStatus.STORED,
            routed_at=routed_at,
            retry_count=input_data.retry_count,
        ),
    )


# =============================================================================
# DLQ Routing
# =============================================================================


async def _route_to_dlq(
    *,
    input_data: ModelStorageRouteInput,
    target_backend: EnumStorageBackend,
    error_message: str,
    dlq_publisher: ProtocolDlqPublisher | None,
    routed_at: datetime,
) -> RouteStorageResult:
    """Route a failed event to the dead letter queue.

    Args:
        input_data: The original event input.
        target_backend: The target backend that failed.
        error_message: The error that caused the DLQ routing.
        dlq_publisher: The DLQ publisher (optional).
        routed_at: Timestamp for the routing result.

    Returns:
        RouteStorageResult with DLQ status.
    """
    logger.warning(
        "Retries exhausted, routing to DLQ",
        extra={
            "event_id": str(input_data.event_id),
            "target_backend": target_backend.value,
            "retry_count": input_data.retry_count,
            "error_message": error_message,
            "correlation_id": (
                str(input_data.correlation_id) if input_data.correlation_id else None
            ),
        },
    )

    if dlq_publisher is not None:
        try:
            await dlq_publisher.publish_to_dlq(
                event_id=input_data.event_id,
                original_event=input_data.payload,
                error_message=error_message,
                retry_count=input_data.retry_count,
                correlation_id=input_data.correlation_id,
            )
        except Exception as dlq_exc:
            logger.exception(
                "Failed to publish to DLQ",
                extra={
                    "event_id": str(input_data.event_id),
                    "dlq_error": str(dlq_exc),
                },
            )

    return RouteStorageResult(
        success=False,
        output=ModelStorageRouteOutput(
            event_id=input_data.event_id,
            correlation_id=input_data.correlation_id,
            target_backend=target_backend,
            status=EnumStorageRouteStatus.DLQ,
            routed_at=routed_at,
            error_message=error_message,
            retry_count=input_data.retry_count,
        ),
        error_message=error_message,
        routed_to_dlq=True,
    )


__all__ = [
    "MAX_RETRIES",
    "ROUTING_TABLE",
    "ProtocolDlqPublisher",
    "ProtocolStorageClient",
    "RouteStorageResult",
    "StorageClientRegistry",
    "handle_route_storage",
    "resolve_backend",
]
