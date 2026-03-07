# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Storage Router Effect node.

This module exports the storage router effect node and its supporting
models, handlers, and protocols. The node routes completed compute events
to the appropriate storage backend (Qdrant, Memgraph, PostgreSQL) based
on event type.

Key Components:
    - NodeStorageRouterEffect: Pure declarative effect node (thin shell)
    - ModelStorageRouteInput: Input from compute-completed events
    - ModelStorageRouteOutput: Output for storage.completed/storage.failed events
    - EnumStorageBackend: Target storage backends (qdrant, memgraph, postgresql)
    - EnumStorageRouteStatus: Routing operation status
    - StorageClientRegistry: Registry of storage backend clients
    - ProtocolStorageClient: Interface for storage backend implementations
    - ProtocolDlqPublisher: Interface for DLQ publishing

Routing Rules:
    - vectorization.completed -> Qdrant vector storage
    - entity.extraction-completed -> Memgraph graph storage
    - pattern.matched -> PostgreSQL pattern storage

Usage (Declarative Pattern):
    from omniintelligence.nodes.node_storage_router_effect import (
        NodeStorageRouterEffect,
        handle_route_storage,
        StorageClientRegistry,
        ModelStorageRouteInput,
    )

    # Create node via container (pure declarative shell)
    from omnibase_core.models.container import ModelONEXContainer
    container = ModelONEXContainer()
    node = NodeStorageRouterEffect(container)

    # Handlers are called directly with their dependencies
    result = await handle_route_storage(
        input_data=ModelStorageRouteInput(...),
        client_registry=client_registry,
        dlq_publisher=dlq_publisher,
    )

    # For event-driven execution, use RuntimeHostProcess
    # which reads handler_routing from contract.yaml

Reference:
    - OMN-371: Storage router effect node implementation
"""

from omniintelligence.nodes.node_storage_router_effect.handlers import (
    MAX_RETRIES,
    ROUTING_TABLE,
    ProtocolDlqPublisher,
    ProtocolStorageClient,
    RouteStorageResult,
    StorageClientRegistry,
    handle_route_storage,
    resolve_backend,
)
from omniintelligence.nodes.node_storage_router_effect.models import (
    EnumStorageBackend,
    EnumStorageRouteStatus,
    ModelStorageRouteInput,
    ModelStorageRouteOutput,
)
from omniintelligence.nodes.node_storage_router_effect.node import (
    NodeStorageRouterEffect,
)

__all__ = [
    "MAX_RETRIES",
    "ROUTING_TABLE",
    "EnumStorageBackend",
    "EnumStorageRouteStatus",
    "ModelStorageRouteInput",
    "ModelStorageRouteOutput",
    "NodeStorageRouterEffect",
    "ProtocolDlqPublisher",
    "ProtocolStorageClient",
    "RouteStorageResult",
    "StorageClientRegistry",
    "handle_route_storage",
    "resolve_backend",
]
