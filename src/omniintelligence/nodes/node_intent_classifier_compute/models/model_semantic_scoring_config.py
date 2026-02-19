"""Semantic scoring config model for Intent Classifier Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelSemanticScoringConfig(BaseModel):
    """Frozen configuration for semantic analysis scoring algorithm.

    Values sourced from contract.yaml -> configuration.semantic_analysis.scoring.

    Attributes:
        match_base_initial: Initial base score for domain matches.
        match_base_max: Maximum base score from keyword matches.
        density_bonus_max: Maximum bonus from high match density.
        density_multiplier: Multiplier for match ratio in density calculation.
        diversity_bonus_max: Maximum bonus from keyword diversity.
        diversity_multiplier: Multiplier for unique keyword count.
        concept_confidence_multiplier: Multiplier for concept confidence extraction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    match_base_initial: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Initial base score for domain matches",
    )
    match_base_max: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Maximum base score from keyword matches",
    )
    density_bonus_max: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Maximum bonus from high match density",
    )
    density_multiplier: float = Field(
        default=0.3,
        ge=0.0,
        description="Multiplier for match ratio in density calculation",
    )
    diversity_bonus_max: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Maximum bonus from keyword diversity",
    )
    diversity_multiplier: float = Field(
        default=0.05,
        ge=0.0,
        description="Multiplier for unique keyword count",
    )
    concept_confidence_multiplier: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Multiplier for concept confidence extraction",
    )


__all__ = ["ModelSemanticScoringConfig"]
