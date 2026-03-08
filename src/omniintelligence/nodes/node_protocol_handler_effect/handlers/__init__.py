# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handlers for Protocol Handler Effect node.

Note: Concrete handler implementations (HttpRestHandler, BoltHandler,
PostgresHandler, KafkaHandler) live in omniintelligence.adapters to
comply with ONEX I/O audit and cross-repo validation policies.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from omniintelligence.nodes.node_protocol_handler_effect.handlers.handler_protocol import (
    ProtocolHandler,
    ProtocolHandlerRegistry,
    handle_protocol_execute,
)

__all__ = [
    "ProtocolHandler",
    "ProtocolHandlerRegistry",
    "handle_protocol_execute",
]
