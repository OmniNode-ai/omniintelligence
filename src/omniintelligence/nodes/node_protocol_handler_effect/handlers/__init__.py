# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handlers for Protocol Handler Effect node.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_bolt import (
    BoltHandler,
)
from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_http_rest import (
    HttpRestHandler,
)
from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_kafka import (
    KafkaHandler,
)
from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_postgres import (
    PostgresHandler,
)
from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_protocol import (
    ProtocolHandler,
    ProtocolHandlerRegistry,
    handle_protocol_execute,
)

__all__ = [
    "BoltHandler",
    "HttpRestHandler",
    "KafkaHandler",
    "PostgresHandler",
    "ProtocolHandler",
    "ProtocolHandlerRegistry",
    "handle_protocol_execute",
]
