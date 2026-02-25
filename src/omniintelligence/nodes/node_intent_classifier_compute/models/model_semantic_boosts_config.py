# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Semantic boosts config model for Intent Classifier Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelSemanticBoostsConfig(BaseModel):
    """Frozen configuration for semantic analysis confidence boosts.

    Values sourced from contract.yaml -> configuration.semantic_analysis.boosts.

    Attributes:
        domain_match_boost: Boost applied when a domain indicator matches an intent.
        concept_match_boost: Boost applied when a concept matches an intent.
        topic_weight_multiplier: Multiplier for topic weights when calculating boosts.
        max_boost_cap: Maximum total boost that can be applied to any single intent.
        context_boost: Boost applied when context matches a domain.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

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


__all__ = ["ModelSemanticBoostsConfig"]
