"""Semantic Relation model for AST-based analysis."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from omniintelligence.nodes.semantic_analysis_compute.models.enums import (
    EnumSemanticRelationType,
)


class ModelSemanticRelation(BaseModel):
    """Represents a semantic relation between two entities.

    A relation captures the relationship between code entities,
    such as imports, function calls, inheritance, or references.
    """

    source: str = Field(
        ...,
        min_length=1,
        description="Name of the source entity in the relation",
    )
    target: str = Field(
        ...,
        min_length=1,
        description="Name of the target entity in the relation",
    )
    relation_type: EnumSemanticRelationType = Field(
        ...,
        description="Type of the semantic relation",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the relation (0.0 to 1.0)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the relation (e.g., line number, context)",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate that confidence is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSemanticRelation"]
