# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Semantic limits config model for Intent Classifier Compute Node."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelSemanticLimitsConfig(BaseModel):
    """Frozen configuration for semantic analysis result limits.

    Values sourced from contract.yaml -> configuration.semantic_analysis.limits.

    Attributes:
        max_concepts: Maximum number of concepts to return.
        max_domain_indicators: Maximum number of domain indicators to return.
        min_token_length: Minimum length for tokens to be included in analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

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
    min_token_length: int = Field(
        default=2,
        ge=1,
        description="Minimum length for tokens to be included in analysis",
    )


__all__ = ["ModelSemanticLimitsConfig"]
