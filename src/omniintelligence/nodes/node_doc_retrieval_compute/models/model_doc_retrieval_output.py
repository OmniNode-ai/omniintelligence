# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Output models for NodeDocRetrievalCompute.

Ticket: OMN-2396
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ModelRankedDocItem(BaseModel):
    """A single re-ranked document item for session context assembly.

    Attributes:
        item_id:             UUID of the ContextItem.
        source_ref:          Document path.
        similarity:          Raw Qdrant cosine similarity.
        scope_boost:         Multiplier applied for scope proximity (0.80-1.20).
        tier_multiplier:     Multiplier applied for promotion tier (0.85-1.15).
        intent_weight:       Multiplier for intent-type affinity (from DOCUMENT_INTENT_TYPE_WEIGHTS).
        final_score:         similarity * scope_boost * tier_multiplier * intent_weight.
        token_estimate:      Estimated token cost.
        content_fingerprint: SHA-256 fingerprint (used for deduplication).
        section_heading:     Optional section heading.
        crawl_scope:         Repository scope that produced this item.
        correlation_id:      Propagated from input.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    item_id: UUID
    source_ref: str
    similarity: float = Field(ge=0.0, le=1.0)
    scope_boost: float = Field(ge=0.0)
    tier_multiplier: float = Field(ge=0.0)
    intent_weight: float = Field(ge=0.0)
    final_score: float = Field(ge=0.0)
    token_estimate: int = Field(ge=0)
    content_fingerprint: str
    section_heading: str | None = None
    crawl_scope: str = ""
    correlation_id: str | None = None


class ModelDocRetrievalOutput(BaseModel):
    """Output of document retrieval re-ranking and budget enforcement.

    Attributes:
        ranked_items:         Ordered list of items selected for context (highest score first).
                              Already budget-capped and deduplicated.
        doc_token_budget:     Token budget allocated for document items (may be less than
                              all ranked items if budget is tight).
        tokens_used:          Total tokens consumed by ranked_items.
        items_considered:     Count of search results evaluated before re-ranking.
        items_filtered:       Count of items removed (below similarity threshold, wrong tier, etc.).
        budget_fraction_used: doc_token_budget / total_token_budget.
        intent_category:      Echoed from input.
        correlation_id:       Echoed from input.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    ranked_items: tuple[ModelRankedDocItem, ...]
    doc_token_budget: int = Field(ge=0)
    tokens_used: int = Field(ge=0)
    items_considered: int = Field(ge=0)
    items_filtered: int = Field(ge=0)
    budget_fraction_used: float = Field(ge=0.0, le=1.0)
    intent_category: str = "default"
    correlation_id: str | None = None


__all__ = ["ModelDocRetrievalOutput", "ModelRankedDocItem"]
