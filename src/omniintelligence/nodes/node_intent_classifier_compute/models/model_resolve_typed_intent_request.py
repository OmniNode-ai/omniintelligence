# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request model for typed intent resolution."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intent_classifier_compute.models.enum_intent_class import (
    EnumIntentClass,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_typed_intent_config import (
    ModelTypedIntentConfig,
)

# Shared with the typed classification handler to keep its default consistent.
DEFAULT_TYPED_CONFIDENCE_THRESHOLD: float = 0.3


class ModelResolveTypedIntentRequest(BaseModel):
    """Intent category, confidence, and optional resolution configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    intent_category: str
    confidence: float
    confidence_threshold: float = DEFAULT_TYPED_CONFIDENCE_THRESHOLD
    config_table: dict[EnumIntentClass, ModelTypedIntentConfig] | None = None


__all__ = ["ModelResolveTypedIntentRequest"]
