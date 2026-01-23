"""Frozen configuration models for Intent Classifier Compute Node.

These models provide immutable, validated configuration for intent classification
and semantic analysis operations. Values are sourced from contract.yaml.

Usage:
    # Use defaults from contract.yaml
    config = ModelClassificationConfig()

    # Override specific values
    config = ModelClassificationConfig(exact_match_weight=20.0)

    # Pass to handler functions
    result = classify_intent(input_data, config=config)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelClassificationConfig(BaseModel):
    """Frozen configuration for TF-IDF intent classification.

    Values sourced from contract.yaml -> configuration.classification.
    All fields have sensible defaults matching the contract specification.

    Attributes:
        exact_match_weight: Weight applied to exact keyword matches in TF-IDF scoring.
            Higher values prioritize exact matches over partial matches.
        partial_match_weight: Weight applied to partial/fuzzy keyword matches.
            Should be lower than exact_match_weight to prefer exact matches.
        min_pattern_length_for_partial: Minimum pattern length required for partial
            matching. Prevents false positives from very short patterns.
        default_confidence_threshold: Default confidence threshold for classification
            results. Results below this threshold return "unknown" intent.
        default_max_intents: Maximum number of secondary intents to return in
            multi-label mode.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    exact_match_weight: float = Field(
        default=15.0,
        ge=0.0,
        description="Weight for exact keyword matches in TF-IDF scoring",
    )
    partial_match_weight: float = Field(
        default=3.0,
        ge=0.0,
        description="Weight for partial/fuzzy keyword matches",
    )
    min_pattern_length_for_partial: int = Field(
        default=3,
        ge=1,
        description="Minimum pattern length required for partial matching",
    )
    default_confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default confidence threshold for classification results",
    )
    default_max_intents: int = Field(
        default=5,
        ge=1,
        description="Maximum number of secondary intents to return",
    )


class ModelSemanticBoostsConfig(BaseModel):
    """Frozen configuration for semantic analysis confidence boosts.

    Values sourced from contract.yaml -> configuration.semantic_analysis.boosts.

    Attributes:
        domain_match_boost: Boost applied when a domain indicator matches an intent.
        concept_match_boost: Boost applied when a concept matches an intent.
            Multiplied by concept confidence.
        topic_weight_multiplier: Multiplier for topic weights when calculating boosts.
        max_boost_cap: Maximum total boost that can be applied to any single intent.
            Prevents over-boosting from multiple matches.
        context_boost: Boost applied when context matches a domain.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_match_boost: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Boost for domain indicator matches",
    )
    concept_match_boost: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Boost for concept matches (multiplied by confidence)",
    )
    topic_weight_multiplier: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Multiplier for topic weights in boost calculation",
    )
    max_boost_cap: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Maximum total boost for any single intent",
    )
    context_boost: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Boost when context matches a domain",
    )


class ModelSemanticScoringConfig(BaseModel):
    """Frozen configuration for semantic analysis scoring algorithm.

    Values sourced from contract.yaml -> configuration.semantic_analysis.scoring.

    The scoring formula for domain detection:
        match_base = min(match_base_max, match_base_initial + (matches * match_base_initial))
        density_bonus = min(density_bonus_max, match_ratio * density_multiplier)
        diversity_bonus = min(diversity_bonus_max, unique_keywords * diversity_multiplier)

    Attributes:
        match_base_initial: Initial base score for domain matches.
        match_base_max: Maximum base score from keyword matches.
        density_bonus_max: Maximum bonus from high match density.
        density_multiplier: Multiplier for match ratio in density calculation.
        diversity_bonus_max: Maximum bonus from keyword diversity.
        diversity_multiplier: Multiplier for unique keyword count.
        concept_confidence_multiplier: Multiplier for concept confidence extraction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

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


class ModelSemanticLimitsConfig(BaseModel):
    """Frozen configuration for semantic analysis result limits.

    Values sourced from contract.yaml -> configuration.semantic_analysis.limits.

    Attributes:
        max_concepts: Maximum number of concepts to return.
        max_domain_indicators: Maximum number of domain indicators to return.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_concepts: int = Field(
        default=20,
        ge=1,
        description="Maximum number of concepts to return",
    )
    max_domain_indicators: int = Field(
        default=5,
        ge=1,
        description="Maximum number of domain indicators to return",
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

    model_config = ConfigDict(frozen=True, extra="forbid")

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


__all__ = [
    "ModelClassificationConfig",
    "ModelSemanticAnalysisConfig",
    "ModelSemanticBoostsConfig",
    "ModelSemanticLimitsConfig",
    "ModelSemanticScoringConfig",
]
