# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Semantic analysis config model for Intent Classifier Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intent_classifier_compute.models.model_semantic_boosts_config import (
    ModelSemanticBoostsConfig,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_semantic_limits_config import (
    ModelSemanticLimitsConfig,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_semantic_scoring_config import (
    ModelSemanticScoringConfig,
)


class ModelSemanticAnalysisConfig(BaseModel):
    """Frozen configuration for semantic analysis operations.

    Values sourced from contract.yaml -> configuration.semantic_analysis.
    Contains nested configuration for boosts, scoring, and limits.

    Attributes:
        boosts: Confidence boost configuration for different match types.
        scoring: Scoring algorithm parameters for domain detection.
        limits: Result set size limits.
        default_min_confidence: Default minimum confidence threshold for results.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    boosts: ModelSemanticBoostsConfig = Field(
        default_factory=ModelSemanticBoostsConfig,
        description="Confidence boost configuration",
    )
    scoring: ModelSemanticScoringConfig = Field(
        default_factory=ModelSemanticScoringConfig,
        description="Scoring algorithm parameters",
    )
    limits: ModelSemanticLimitsConfig = Field(
        default_factory=ModelSemanticLimitsConfig,
        description="Result set size limits",
    )
    default_min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Default minimum confidence threshold for semantic results",
    )


__all__ = ["ModelSemanticAnalysisConfig"]
