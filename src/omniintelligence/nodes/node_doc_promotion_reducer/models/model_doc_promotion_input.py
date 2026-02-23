# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Input models for NodeDocPromotionReducer.

Ticket: OMN-2395
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_context_item_source_type import (
    EnumContextItemSourceType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_promotion_tier import (
    EnumPromotionTier,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_attribution_signal import (
    ModelAttributionSignal,
)


class ModelPromotionCandidate(BaseModel):
    """A single ContextItem candidate for promotion evaluation.

    Attributes:
        item_id:           UUID of the ContextItem.
        source_type:       Source type — drives threshold set selection.
        current_tier:      Current promotion tier.
        scored_runs:       Total number of runs where the item was scored.
        positive_signals:  Cumulative count of positive attribution signals.
        used_rate:         Fraction of runs where the item was used (0.0-1.0).
        hurt_rate:         Fraction of scored runs where the item hurt quality.
        recent_signals:    New attribution signals received since last evaluation.
        correlation_id:    Optional correlation ID for tracing.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    item_id: UUID
    source_type: EnumContextItemSourceType
    current_tier: EnumPromotionTier
    scored_runs: int = Field(ge=0)
    positive_signals: int = Field(ge=0)
    used_rate: float = Field(ge=0.0, le=1.0)
    hurt_rate: float = Field(ge=0.0, le=1.0)
    recent_signals: tuple[ModelAttributionSignal, ...] = Field(default=())
    correlation_id: str | None = None


class ModelDocPromotionInput(BaseModel):
    """Batch of ContextItem candidates for promotion evaluation.

    Attributes:
        candidates:    Promotion candidates to evaluate.
        dry_run:       If True, compute decisions but do not persist transitions.
        correlation_id: Optional correlation ID for tracing.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    candidates: tuple[ModelPromotionCandidate, ...]
    dry_run: bool = False
    correlation_id: str | None = None


__all__ = ["ModelDocPromotionInput", "ModelPromotionCandidate"]
