# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for matching code entities to a pattern role."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternRole,
)


class ModelMatchPatternRequest(BaseModel):
    """Request for matching code entities to a pattern role."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    role: ModelPatternRole = Field(description="Pattern role to match")
    entities: tuple[ModelCodeEntity, ...] = Field(
        description="Code entities to inspect for the role"
    )


__all__ = ["ModelMatchPatternRequest"]
