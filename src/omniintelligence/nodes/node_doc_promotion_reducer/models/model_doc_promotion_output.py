# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for NodeDocPromotionReducer.

Ticket: OMN-2395
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_promotion_tier import (
    EnumPromotionTier,
)


class ModelPromotionDecision(BaseModel):
    """Promotion decision for a single ContextItem.

    Attributes:
        item_id:       UUID of the ContextItem.
        old_tier:      Tier before this decision.
        new_tier:      Tier after applying all gates (may equal old_tier if no change).
        promoted:      True if the item moved up (QUARANTINE→VALIDATED or VALIDATED→SHARED).
        demoted:       True if the item moved down (VALIDATED→QUARANTINE).
        blocked_by:    Human-readable reason why promotion was blocked (or None).
        correlation_id: Propagated from input candidate.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    item_id: UUID
    old_tier: EnumPromotionTier
    new_tier: EnumPromotionTier
    promoted: bool = False
    demoted: bool = False
    blocked_by: str | None = None
    correlation_id: str | None = None


class ModelDocPromotionOutput(BaseModel):
    """Batch promotion evaluation results.

    Attributes:
        decisions:       Per-candidate promotion decisions.
        items_promoted:  Count of items that moved up.
        items_demoted:   Count of items that moved down.
        items_unchanged: Count of items with no tier change.
        dry_run:         Echoed from input.
        correlation_id:  Echoed from input.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    decisions: tuple[ModelPromotionDecision, ...]
    items_promoted: int = 0
    items_demoted: int = 0
    items_unchanged: int = 0
    dry_run: bool = False
    correlation_id: str | None = None

    @property
    def total_candidates(self) -> int:
        """Total candidates evaluated."""
        return len(self.decisions)


__all__ = ["ModelDocPromotionOutput", "ModelPromotionDecision"]
