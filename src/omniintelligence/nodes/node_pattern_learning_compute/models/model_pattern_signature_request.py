# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for HandlerPatternSignature."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_pattern_learning_compute.handlers.protocols import (
    PatternClusterDict,
)


class ModelPatternSignatureRequest(BaseModel):
    """Typed inputs for HandlerPatternSignature."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    cluster: PatternClusterDict | None
