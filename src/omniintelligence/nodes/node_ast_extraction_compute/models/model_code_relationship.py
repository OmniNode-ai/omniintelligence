# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code relationship model extracted from Python AST parsing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelCodeRelationship(BaseModel):
    """A relationship between two code entities.

    Describes structural relationships such as inheritance, imports,
    definitions, implementations, and calls detected from AST analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    id: str = Field(description="UUID identifying this relationship")
    source_entity: str = Field(description="Qualified name of the source entity")
    target_entity: str = Field(description="Qualified name of the target entity")
    relationship_type: str = Field(
        description=(
            "Kind of relationship: 'inherits', 'imports', 'defines', "
            "'implements', 'calls'"
        )
    )
    trust_tier: str = Field(description="Trust level: 'strong', 'conservative', 'weak'")
    confidence: float = Field(default=1.0, description="Confidence score 0.0-1.0")
    evidence: list[str] = Field(
        default_factory=list, description="Evidence strings supporting the relationship"
    )
    inject_into_context: bool = Field(
        default=True, description="Whether to inject into LLM context"
    )
