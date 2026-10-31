# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for semantic analysis."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_classifier_compute.models.model_semantic_analysis_config import (
    ModelSemanticAnalysisConfig,
)


class ModelAnalyzeSemanticsRequest(BaseModel):
    """Text, context, and optional semantic analysis configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    content: str
    context: str | None = None
    min_confidence: float | None = None
    config: ModelSemanticAnalysisConfig | None = None


__all__ = ["ModelAnalyzeSemanticsRequest"]
