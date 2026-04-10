# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for the code entity → learned pattern bridge compute node.

Ticket: OMN-7863
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)


class ModelCodeEntityBridgeInput(BaseModel):
    """Input for deriving learned patterns from code_entities.

    Carries a batch of code entities (from AST extraction) plus optional
    metadata for canary A/B testing and end-to-end tracing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="End-to-end tracing identifier",
    )
    entities: list[ModelCodeEntity] = Field(
        default_factory=list,
        description="Code entities extracted from AST ingestion",
    )
    source_repo: str = Field(
        ...,
        min_length=1,
        description="Repository name the entities were extracted from",
    )
    canary_id: str | None = Field(
        default=None,
        description="Optional canary tag for A/B testing (e.g. 'canary-v1')",
    )
    project_scope: str | None = Field(
        default=None,
        max_length=255,
        description="Optional project scope (e.g. 'omniclaude'). NULL means global.",
    )
    domain_id: str = Field(
        default="code_structure",
        max_length=50,
        description="Domain identifier applied to derived patterns",
    )
    min_confidence: float = Field(
        default=0.7,
        ge=0.5,
        le=1.0,
        description="Minimum entity confidence required to derive a pattern",
    )


__all__ = ["ModelCodeEntityBridgeInput"]
