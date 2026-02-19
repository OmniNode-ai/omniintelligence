# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""OperationHandler - operation-to-handler mapping from contract."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_storage_effect.model_handler_config import (
    HandlerConfig,
)


class OperationHandler(BaseModel):
    """Operation-to-handler mapping from contract.

    Attributes:
        operation: Operation name that triggers this handler.
        handler: Handler configuration for this operation.
        description: Human-readable description of the operation.
        actions: List of actions performed by this handler.
    """

    operation: str
    handler: HandlerConfig
    description: str | None = None
    actions: list[str] = Field(default_factory=list)
