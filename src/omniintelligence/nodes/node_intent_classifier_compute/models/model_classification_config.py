# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Classification config model for Intent Classifier Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelClassificationConfig(BaseModel):
    """Frozen configuration for TF-IDF intent classification.

    Values sourced from contract.yaml -> configuration.classification.
    All fields have sensible defaults matching the contract specification.

    Attributes:
        classifier_version: Version identifier for the classifier algorithm.
        exact_match_weight: Weight applied to exact keyword matches in TF-IDF scoring.
        partial_match_weight: Weight applied to partial/fuzzy keyword matches.
        min_pattern_length_for_partial: Minimum pattern length required for partial matching.
        default_confidence_threshold: Default confidence threshold for classification results.
        default_max_intents: Maximum number of secondary intents to return.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    classifier_version: str = Field(
        default="1.0.0",
        description="Version identifier for the classifier algorithm",
    )
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
    default_multi_label: bool = Field(
        default=False,
        description="Default multi-label mode for returning secondary intents",
    )


__all__ = ["ModelClassificationConfig"]
