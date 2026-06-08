# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Code relationship model extracted from Python AST parsing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelCodeRelationship(BaseModel):
    """A relationship between two code entities.

    Describes structural relationships such as inheritance, imports,
    definitions, implementations, and calls detected from AST analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        aliases = {
            "relationship_id": "id",
            "source_entity_id": "source_entity",
            "target_entity_id": "target_entity",
        }
        for legacy_key, canonical_key in aliases.items():
            if legacy_key in normalized and canonical_key not in normalized:
                normalized[canonical_key] = normalized.pop(legacy_key)
            else:
                normalized.pop(legacy_key, None)
        normalized.pop("metadata", None)
        return normalized

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

    @property
    def relationship_id(self) -> str:
        return self.id

    @property
    def source_entity_id(self) -> str:
        return self.source_entity

    @property
    def target_entity_id(self) -> str:
        return self.target_entity
