# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node Protocol Handler Effect - Declarative effect node for protocol operations.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive protocol operation request (input_model in contract)
    2. Route to appropriate protocol handler based on protocol field
    3. Execute operation via handler (HTTP, Bolt, PostgreSQL, Kafka)
    4. Return structured response (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - Container DI: Handler dependencies resolved via container

Node Responsibilities:
    - Define I/O model contract (ModelProtocolHandlerInput -> ModelProtocolHandlerOutput)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_protocol.py: Protocol dispatch handler
    - handlers/handler_http_rest.py: HTTP/REST protocol handler
    - handlers/handler_bolt.py: Neo4j/Memgraph Bolt protocol handler
    - handlers/handler_postgres.py: PostgreSQL protocol handler
    - handlers/handler_kafka.py: Kafka protocol handler

Related Tickets:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeProtocolHandlerEffect(NodeEffect):
    """Declarative effect node for executing protocol-specific operations.

    This effect node is a lightweight shell that defines the I/O contract
    for protocol handler operations. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - execute_protocol: Execute an operation via the appropriate handler

    Protocol Handlers (resolved from input.protocol field):
        - http_rest -> HttpRestHandler (httpx)
        - bolt -> BoltHandler (neo4j driver)
        - postgresql -> PostgresHandler (asyncpg)
        - kafka -> KafkaHandler (confluent-kafka)

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (handler_registry). This node contains NO instance variables
        for handlers or registries.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_protocol_handler_effect import (
            NodeProtocolHandlerEffect,
            handle_protocol_execute,
            ProtocolHandlerRegistry,
        )

        # Create effect node via container (pure declarative shell)
        container = ModelONEXContainer()
        effect = NodeProtocolHandlerEffect(container)

        # Handlers are invoked directly with their dependencies
        result = await handle_protocol_execute(
            input_data,
            handler_registry=registry,
        )

        # Or use RuntimeHostProcess for event-driven execution
        # which reads handler_routing from contract.yaml
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeProtocolHandlerEffect"]
