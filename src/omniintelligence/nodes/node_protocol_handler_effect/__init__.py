# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Protocol Handler Effect node.

This module exports the protocol handler effect node and its supporting
models, handlers, and protocols. The node provides protocol-specific
handler implementations for declarative effect nodes.

Key Components:
    - NodeProtocolHandlerEffect: Pure declarative effect node (thin shell)
    - ModelProtocolHandlerInput: Input specifying protocol, operation, params
    - ModelProtocolHandlerOutput: Output with status, result, timing
    - EnumProtocolType: Supported protocols (http_rest, bolt, postgresql, kafka)
    - EnumHandlerStatus: Operation status codes
    - ProtocolHandler: Base protocol interface for all handlers
    - ProtocolHandlerRegistry: Registry for handler lookup

Concrete handler implementations (HttpRestHandler, BoltHandler,
PostgresHandler, KafkaHandler) live in omniintelligence.adapters to
comply with ONEX I/O audit and cross-repo validation policies.

Usage (Declarative Pattern):
    from omniintelligence.nodes.node_protocol_handler_effect import (
        NodeProtocolHandlerEffect,
        handle_protocol_execute,
        ProtocolHandlerRegistry,
        EnumProtocolType,
        ModelProtocolHandlerInput,
    )
    from omniintelligence.adapters import HttpRestHandler

    # Wire handlers
    http_handler = HttpRestHandler()
    await http_handler.connect({"base_url": "https://api.example.com"})

    registry = ProtocolHandlerRegistry(
        handlers={EnumProtocolType.HTTP_REST: http_handler}
    )

    # Execute via handler function
    result = await handle_protocol_execute(
        input_data=ModelProtocolHandlerInput(
            protocol=EnumProtocolType.HTTP_REST,
            operation="GET",
            params={"path": "/health"},
        ),
        handler_registry=registry,
    )

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from omniintelligence.nodes.node_protocol_handler_effect.handlers import (
    ProtocolHandler,
    ProtocolHandlerRegistry,
    handle_protocol_execute,
)
from omniintelligence.nodes.node_protocol_handler_effect.models import (
    EnumHandlerStatus,
    EnumProtocolType,
    ModelProtocolHandlerInput,
    ModelProtocolHandlerOutput,
)
from omniintelligence.nodes.node_protocol_handler_effect.node import (
    NodeProtocolHandlerEffect,
)

__all__ = [
    "EnumHandlerStatus",
    "EnumProtocolType",
    "ModelProtocolHandlerInput",
    "ModelProtocolHandlerOutput",
    "NodeProtocolHandlerEffect",
    "ProtocolHandler",
    "ProtocolHandlerRegistry",
    "handle_protocol_execute",
]
