# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for TF-IDF intent classification."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_classifier_compute.models.model_classification_config import (
    ModelClassificationConfig,
)


class ModelClassifyIntentRequest(BaseModel):
    """Text and optional configuration for TF-IDF classification."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    content: str
    config: ModelClassificationConfig | None = None
    confidence_threshold: float | None = None
    multi_label: bool | None = None
    max_intents: int | None = None
    score_boosts: dict[str, float] | None = None


__all__ = ["ModelClassifyIntentRequest"]
