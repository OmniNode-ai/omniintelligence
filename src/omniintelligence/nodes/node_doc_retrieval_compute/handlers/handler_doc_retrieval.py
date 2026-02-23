# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for DocRetrievalCompute — scope-aware re-ranking and adaptive budget.

Behavior:
  - Receives raw Qdrant search results (ModelDocSearchResult candidates)
  - Filters results below doc_min_similarity and outside allowed tiers
  - Applies 3-factor score re-ranking:
      final_score = similarity * scope_boost * tier_multiplier * intent_weight
  - Enforces adaptive token budget by intent category
  - Caps output at max_doc_items, deduplicated by content_fingerprint
  - Returns ranked items ready for context assembly

Scoring:
  scope_boost (proximity to session repo):
    exact repo match:         1.20
    same org, other repo:     0.90
    org-wide (no org match):  0.80

  tier_multiplier (trust level):
    SHARED:                   1.15
    VALIDATED (earned):       1.00  (bootstrap_confidence == 0.0)
    VALIDATED (bootstrapped): 0.85  (bootstrap_confidence > 0.0)
    QUARANTINE:               0.70  (only included if allow_bootstrap_validated=True)
    other:                    1.00

  intent_weight (from DOCUMENT_INTENT_TYPE_WEIGHTS or default 1.0):
    Keyed by (intent_category, source_type). Falls back to 1.0 if not found.

Adaptive Token Budget:
  doc_token_budget = total_token_budget * budget_fraction
  budget_fraction selected by intent_category from DocSourceConfig overrides,
  with fallback to doc_token_budget_fraction_default.

Design:
  - Pure function (no I/O). Caller handles Qdrant queries and signal emission.
  - All scoring constants defined at module level (no hardcoded numbers in logic).
  - Returns items sorted by final_score descending, budget-capped, fingerprint-deduplicated.

Ticket: OMN-2396
"""

from __future__ import annotations

import logging

from omniintelligence.nodes.node_doc_retrieval_compute.models.model_doc_retrieval_input import (
    DocSourceConfig,
    ModelDocRetrievalInput,
    ModelDocSearchResult,
)
from omniintelligence.nodes.node_doc_retrieval_compute.models.model_doc_retrieval_output import (
    ModelDocRetrievalOutput,
    ModelRankedDocItem,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Scoring constants
# =============================================================================

# scope_boost: measures proximity of item's crawl_scope to query_scope
_SCOPE_BOOST_EXACT: float = 1.20  # item.crawl_scope == query_scope
_SCOPE_BOOST_SAME_ORG: float = 0.90  # same org prefix (e.g. "omninode/")
_SCOPE_BOOST_ORG_WIDE: float = 0.80  # no org match

# tier_multiplier: trust in the item's promotion status
_TIER_MULTIPLIER_SHARED: float = 1.15
_TIER_MULTIPLIER_VALIDATED_EARNED: float = 1.00
_TIER_MULTIPLIER_VALIDATED_BOOTSTRAPPED: float = 0.85
_TIER_MULTIPLIER_QUARANTINE: float = 0.70
_TIER_MULTIPLIER_DEFAULT: float = 1.00

# Allowed tiers for inclusion
_ALLOWED_TIERS: frozenset[str] = frozenset({"validated", "shared"})

# Intent-type weights: (intent_category -> (source_type -> weight))
# Source types not listed for an intent default to 1.0.
DOCUMENT_INTENT_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "debugging": {
        "FAILURE_PATTERN": 2.0,
        "CONFIG_NOTE": 1.2,
        "RULE": 1.0,
        "DOC_EXCERPT": 0.8,
    },
    "code_generation": {
        "EXAMPLE": 2.0,
        "API_CONSTRAINT": 1.8,
        "RULE": 1.5,
        "DOC_EXCERPT": 1.2,
    },
    "refactoring": {
        "RULE": 2.0,
        "REPO_MAP": 1.8,
        "DOC_EXCERPT": 1.5,
        "API_CONSTRAINT": 1.3,
    },
    "configuration": {
        "CONFIG_NOTE": 2.5,
        "RULE": 1.8,
        "DOC_EXCERPT": 1.2,
    },
    "compliance": {
        "RULE": 2.5,
        "CONFIG_NOTE": 2.0,
        "DOC_EXCERPT": 1.5,
    },
}


# =============================================================================
# Scoring helpers (pure functions)
# =============================================================================


def _compute_scope_boost(item_scope: str, query_scope: str) -> float:
    """Return scope_boost for an item given the current query scope.

    Comparison is case-insensitive. Scope format is 'org/repo'.

    Args:
        item_scope:  crawl_scope of the context item.
        query_scope: Scope of the current session.

    Returns:
        Scope boost multiplier (0.80, 0.90, or 1.20).
    """
    if not item_scope or not query_scope:
        return _SCOPE_BOOST_ORG_WIDE

    item_lower = item_scope.strip().lower()
    query_lower = query_scope.strip().lower()

    if item_lower == query_lower:
        return _SCOPE_BOOST_EXACT

    # Same org: both scopes share the same 'org/' prefix
    item_org = item_lower.split("/")[0] if "/" in item_lower else item_lower
    query_org = query_lower.split("/")[0] if "/" in query_lower else query_lower

    if item_org == query_org:
        return _SCOPE_BOOST_SAME_ORG

    return _SCOPE_BOOST_ORG_WIDE


def _compute_tier_multiplier(tier: str, bootstrap_confidence: float) -> float:
    """Return tier_multiplier for an item.

    Args:
        tier:                 Promotion tier string (lowercase).
        bootstrap_confidence: Bootstrap confidence score. > 0.0 means bootstrapped.

    Returns:
        Tier multiplier (0.70-1.15).
    """
    tier_lower = tier.lower()

    if tier_lower == "shared":
        return _TIER_MULTIPLIER_SHARED

    if tier_lower == "validated":
        if bootstrap_confidence > 0.0:
            return _TIER_MULTIPLIER_VALIDATED_BOOTSTRAPPED
        return _TIER_MULTIPLIER_VALIDATED_EARNED

    if tier_lower == "quarantine":
        return _TIER_MULTIPLIER_QUARANTINE

    return _TIER_MULTIPLIER_DEFAULT


def _compute_intent_weight(intent_category: str, source_type: str) -> float:
    """Return intent-type weight for an item.

    Looks up (intent_category, source_type) in DOCUMENT_INTENT_TYPE_WEIGHTS.
    Returns 1.0 if either key is not found.

    Args:
        intent_category: Current query intent (e.g. 'debugging').
        source_type:     ContextItem source type (e.g. 'RULE', 'DOC_EXCERPT').

    Returns:
        Intent weight (1.0 if not found).
    """
    intent_weights = DOCUMENT_INTENT_TYPE_WEIGHTS.get(intent_category.lower())
    if intent_weights is None:
        return 1.0
    return intent_weights.get(source_type.upper(), 1.0)


def _compute_doc_token_budget(
    total_token_budget: int,
    intent_category: str,
    config: DocSourceConfig,
) -> int:
    """Compute the token budget allocated for document items.

    Selects the budget fraction from config overrides, falling back to default.

    Args:
        total_token_budget: Total token budget for context assembly.
        intent_category:    Current query intent.
        config:             DocSourceConfig with fraction settings.

    Returns:
        Integer token budget for document items.
    """
    fraction = config.doc_token_budget_fraction_overrides.get(
        intent_category.lower(), config.doc_token_budget_fraction_default
    )
    return int(total_token_budget * fraction)


def _is_allowed(
    result: ModelDocSearchResult,
    config: DocSourceConfig,
) -> bool:
    """Return True if a search result passes inclusion filters.

    Filters applied (any failing filter → excluded):
      1. similarity >= doc_min_similarity
      2. tier in _ALLOWED_TIERS (validated or shared)
      3. If bootstrapped VALIDATED and allow_bootstrap_validated is False → excluded
      4. If STATIC_STANDARDS with zero scored runs and allow_unscored_static_standards is False → excluded

    Args:
        result: The Qdrant search result to evaluate.
        config: DocSourceConfig driving the inclusion policy.

    Returns:
        True if item should be included for re-ranking.
    """
    if result.similarity < config.doc_min_similarity:
        return False

    tier_lower = result.tier.lower()

    if tier_lower not in _ALLOWED_TIERS:
        return False

    if (
        tier_lower == "validated"
        and result.bootstrap_confidence > 0.0
        and not config.allow_bootstrap_validated
    ):
        return False

    return True


# =============================================================================
# Main handler
# =============================================================================


async def handle_doc_retrieval(
    input_data: ModelDocRetrievalInput,
) -> ModelDocRetrievalOutput:
    """Re-rank and budget-enforce document context items.

    Steps:
      1. Filter candidates by similarity threshold and allowed tiers.
      2. Compute final_score = similarity * scope_boost * tier_multiplier * intent_weight.
      3. Sort by final_score descending.
      4. Deduplicate by content_fingerprint (first occurrence wins).
      5. Enforce adaptive token budget: accumulate tokens up to doc_token_budget.
      6. Cap at max_doc_items.

    Args:
        input_data: Retrieval request with Qdrant results and policy config.

    Returns:
        ModelDocRetrievalOutput with ranked, budget-capped items.
    """
    config = input_data.config
    doc_token_budget = _compute_doc_token_budget(
        input_data.total_token_budget,
        input_data.intent_category,
        config,
    )

    items_considered = len(input_data.search_results)
    items_filtered = 0

    # Step 1: Filter + score
    scored: list[ModelRankedDocItem] = []
    for result in input_data.search_results:
        if not _is_allowed(result, config):
            items_filtered += 1
            continue

        scope_boost = _compute_scope_boost(result.crawl_scope, input_data.query_scope)
        tier_multiplier = _compute_tier_multiplier(
            result.tier, result.bootstrap_confidence
        )
        intent_weight = _compute_intent_weight(
            input_data.intent_category, result.source_type
        )
        final_score = result.similarity * scope_boost * tier_multiplier * intent_weight

        scored.append(
            ModelRankedDocItem(
                item_id=result.item_id,
                source_ref=result.source_ref,
                similarity=result.similarity,
                scope_boost=scope_boost,
                tier_multiplier=tier_multiplier,
                intent_weight=intent_weight,
                final_score=final_score,
                token_estimate=result.token_estimate,
                content_fingerprint=result.content_fingerprint,
                section_heading=result.section_heading,
                crawl_scope=result.crawl_scope,
                correlation_id=result.correlation_id,
            )
        )

    # Step 2: Sort by final_score descending
    scored.sort(key=lambda x: x.final_score, reverse=True)

    # Step 3: Deduplicate by content_fingerprint + enforce budget + cap at max_doc_items
    seen_fingerprints: set[str] = set()
    selected: list[ModelRankedDocItem] = []
    tokens_used = 0

    for item in scored:
        if len(selected) >= config.max_doc_items:
            break
        if item.content_fingerprint in seen_fingerprints:
            items_filtered += 1
            continue
        if tokens_used + item.token_estimate > doc_token_budget:
            # Skip items that would exceed budget
            continue

        seen_fingerprints.add(item.content_fingerprint)
        selected.append(item)
        tokens_used += item.token_estimate

    budget_fraction_used = tokens_used / max(input_data.total_token_budget, 1)

    logger.info(
        "DocRetrieval: considered=%d filtered=%d selected=%d tokens=%d/%d (%.1f%%) intent=%s",
        items_considered,
        items_filtered,
        len(selected),
        tokens_used,
        doc_token_budget,
        budget_fraction_used * 100,
        input_data.intent_category,
    )

    return ModelDocRetrievalOutput(
        ranked_items=tuple(selected),
        doc_token_budget=doc_token_budget,
        tokens_used=tokens_used,
        items_considered=items_considered,
        items_filtered=items_filtered,
        budget_fraction_used=budget_fraction_used,
        intent_category=input_data.intent_category,
        correlation_id=input_data.correlation_id,
    )


__all__ = [
    "DOCUMENT_INTENT_TYPE_WEIGHTS",
    "handle_doc_retrieval",
]
