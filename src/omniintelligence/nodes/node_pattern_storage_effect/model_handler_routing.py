# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""HandlerRouting - handler routing configuration from contract."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_storage_effect.model_handler_config import (
    HandlerConfig,
)
from omniintelligence.nodes.node_pattern_storage_effect.model_operation_handler import (
    OperationHandler,
)


class HandlerRouting(BaseModel):
    """Handler routing configuration from contract.

    Attributes:
        routing_strategy: Strategy for routing operations (e.g., operation_match).
        entry_point: Main entry point handler configuration.
        handlers: List of operation-to-handler mappings.
        default_handler: Fallback handler for unrecognized operations.
    """

    routing_strategy: str = "operation_match"
    entry_point: HandlerConfig | None = None
    handlers: list[OperationHandler] = Field(default_factory=list)
    default_handler: HandlerConfig | None = None
