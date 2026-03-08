# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Models for Protocol Handler Effect node.

This module exports all models used by the NodeProtocolHandlerEffect,
including input, output, and supporting enums for protocol operations.

Key Models:
    - ModelProtocolHandlerInput: Input specifying protocol, operation, params
    - ModelProtocolHandlerOutput: Output with status, result, timing
    - EnumProtocolType: Supported protocol types (http_rest, bolt, postgresql, kafka)
    - EnumHandlerStatus: Operation status codes

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from omniintelligence.nodes.node_protocol_handler_effect.models.enum_handler_status import (
    EnumHandlerStatus,
)
from omniintelligence.nodes.node_protocol_handler_effect.models.enum_protocol_type import (
    EnumProtocolType,
)
from omniintelligence.nodes.node_protocol_handler_effect.models.model_protocol_handler_input import (
    ModelProtocolHandlerInput,
)
from omniintelligence.nodes.node_protocol_handler_effect.models.model_protocol_handler_output import (
    ModelProtocolHandlerOutput,
)

__all__ = [
    "EnumHandlerStatus",
    "EnumProtocolType",
    "ModelProtocolHandlerInput",
    "ModelProtocolHandlerOutput",
]
