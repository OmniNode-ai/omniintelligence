# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node Storage Router Effect - Declarative effect node for storage coordination.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive compute-completed event (input_model in contract)
    2. Route to appropriate storage backend based on event_type
    3. Execute storage via handler (Qdrant, Memgraph, PostgreSQL)
    4. Return structured response (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - Container DI: Handler dependencies resolved via container

Node Responsibilities:
    - Define I/O model contract (ModelStorageRouteInput -> ModelStorageRouteOutput)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_route_storage.py: Storage routing handler

Related Tickets:
    - OMN-371: Storage router effect node implementation
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeStorageRouterEffect(NodeEffect):
    """Declarative effect node for routing compute events to storage backends.

    This effect node is a lightweight shell that defines the I/O contract
    for storage routing operations. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - route_storage: Route compute events to appropriate storage backend

    Routing Rules (defined in handler):
        - vectorization.completed -> Qdrant vector storage
        - entity.extraction-completed -> Memgraph graph storage
        - pattern.matched -> PostgreSQL pattern storage

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (client_registry, dlq_publisher). This node contains NO
        instance variables for handlers or registries.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_storage_router_effect import (
            NodeStorageRouterEffect,
            handle_route_storage,
            StorageClientRegistry,
        )

        # Create effect node via container (pure declarative shell)
        container = ModelONEXContainer()
        effect = NodeStorageRouterEffect(container)

        # Handlers are invoked directly with their dependencies
        result = await handle_route_storage(
            input_data,
            client_registry=registry,
            dlq_publisher=dlq,
        )

        # Or use RuntimeHostProcess for event-driven execution
        # which reads handler_routing from contract.yaml
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeStorageRouterEffect"]
