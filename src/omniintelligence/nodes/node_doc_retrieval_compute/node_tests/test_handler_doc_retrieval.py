# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Tests for handler_doc_retrieval — scope boost, tier multiplier, budget enforcement.

Ticket: OMN-2396
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from omniintelligence.nodes.node_doc_retrieval_compute.handlers.handler_doc_retrieval import (
    _compute_doc_token_budget,
    _compute_intent_weight,
    _compute_scope_boost,
    _compute_tier_multiplier,
    _is_allowed,
    handle_doc_retrieval,
)
from omniintelligence.nodes.node_doc_retrieval_compute.models.model_doc_retrieval_input import (
    DocSourceConfig,
    ModelDocRetrievalInput,
    ModelDocSearchResult,
)

# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------


def _make_result(
    *,
    similarity: float = 0.80,
    tier: str = "validated",
    source_type: str = "RULE",
    crawl_scope: str = "omninode/omniintelligence",
    token_estimate: int = 100,
    bootstrap_confidence: float = 0.0,
    content_fingerprint: str | None = None,
) -> ModelDocSearchResult:
    return ModelDocSearchResult(
        item_id=uuid4(),
        similarity=similarity,
        source_ref="docs/CLAUDE.md",
        tier=tier,
        source_type=source_type,
        crawl_scope=crawl_scope,
        content_fingerprint=content_fingerprint or f"fp-{uuid4().hex[:8]}",
        token_estimate=token_estimate,
        bootstrap_confidence=bootstrap_confidence,
    )


def _make_input(
    results: list[ModelDocSearchResult],
    *,
    query_scope: str = "omninode/omniintelligence",
    intent_category: str = "default",
    total_token_budget: int = 4096,
    config: DocSourceConfig | None = None,
) -> ModelDocRetrievalInput:
    return ModelDocRetrievalInput(
        search_results=tuple(results),
        query_scope=query_scope,
        intent_category=intent_category,
        total_token_budget=total_token_budget,
        config=config or DocSourceConfig(),
    )


# ---------------------------------------------------------------------------
# _compute_scope_boost
# ---------------------------------------------------------------------------


class TestScopeBoost:
    def test_exact_match(self) -> None:
        assert (
            _compute_scope_boost(
                "omninode/omniintelligence", "omninode/omniintelligence"
            )
            == 1.20
        )

    def test_exact_match_case_insensitive(self) -> None:
        assert (
            _compute_scope_boost(
                "Omninode/OmniIntelligence", "omninode/omniintelligence"
            )
            == 1.20
        )

    def test_same_org(self) -> None:
        boost = _compute_scope_boost("omninode/omniclaude", "omninode/omniintelligence")
        assert boost == 0.90

    def test_different_org(self) -> None:
        boost = _compute_scope_boost("otherorg/somerepo", "omninode/omniintelligence")
        assert boost == 0.80

    def test_empty_item_scope(self) -> None:
        assert _compute_scope_boost("", "omninode/omniintelligence") == 0.80

    def test_empty_query_scope(self) -> None:
        assert _compute_scope_boost("omninode/omniintelligence", "") == 0.80

    def test_no_slash_in_scopes(self) -> None:
        # No slash: treat entire string as org
        boost = _compute_scope_boost("omninode", "omninode")
        assert boost == 1.20


# ---------------------------------------------------------------------------
# _compute_tier_multiplier
# ---------------------------------------------------------------------------


class TestTierMultiplier:
    def test_shared(self) -> None:
        assert _compute_tier_multiplier("shared", 0.0) == 1.15

    def test_shared_uppercase(self) -> None:
        assert _compute_tier_multiplier("SHARED", 0.0) == 1.15

    def test_validated_earned(self) -> None:
        assert _compute_tier_multiplier("validated", 0.0) == 1.00

    def test_validated_bootstrapped(self) -> None:
        assert _compute_tier_multiplier("validated", 0.75) == 0.85

    def test_quarantine(self) -> None:
        assert _compute_tier_multiplier("quarantine", 0.0) == 0.70

    def test_unknown_tier(self) -> None:
        assert _compute_tier_multiplier("unknown_tier", 0.0) == 1.00


# ---------------------------------------------------------------------------
# _compute_intent_weight
# ---------------------------------------------------------------------------


class TestIntentWeight:
    def test_compliance_rule(self) -> None:
        weight = _compute_intent_weight("compliance", "RULE")
        assert weight == 2.5

    def test_debugging_failure_pattern(self) -> None:
        assert _compute_intent_weight("debugging", "FAILURE_PATTERN") == 2.0

    def test_unknown_intent(self) -> None:
        assert _compute_intent_weight("unknown_intent", "RULE") == 1.0

    def test_unknown_source_type(self) -> None:
        # Known intent, unknown source_type
        assert _compute_intent_weight("compliance", "UNKNOWN_TYPE") == 1.0

    def test_case_insensitive_intent(self) -> None:
        assert _compute_intent_weight("COMPLIANCE", "RULE") == 2.5


# ---------------------------------------------------------------------------
# _compute_doc_token_budget
# ---------------------------------------------------------------------------


class TestDocTokenBudget:
    def test_default_fraction(self) -> None:
        config = DocSourceConfig()
        budget = _compute_doc_token_budget(4096, "default", config)
        assert budget == int(4096 * 0.30)

    def test_compliance_override(self) -> None:
        config = DocSourceConfig()
        budget = _compute_doc_token_budget(4096, "compliance", config)
        assert budget == int(4096 * 0.40)

    def test_debugging_override(self) -> None:
        config = DocSourceConfig()
        budget = _compute_doc_token_budget(4096, "debugging", config)
        assert budget == int(4096 * 0.20)

    def test_unknown_intent_uses_default(self) -> None:
        config = DocSourceConfig()
        budget = _compute_doc_token_budget(4096, "unknown_intent", config)
        assert budget == int(4096 * 0.30)

    def test_custom_override(self) -> None:
        config = DocSourceConfig(
            doc_token_budget_fraction_default=0.50,
            doc_token_budget_fraction_overrides={"custom": 0.60},
        )
        assert _compute_doc_token_budget(1000, "custom", config) == 600
        assert _compute_doc_token_budget(1000, "other", config) == 500


# ---------------------------------------------------------------------------
# _is_allowed
# ---------------------------------------------------------------------------


class TestIsAllowed:
    def test_below_similarity_excluded(self) -> None:
        result = _make_result(similarity=0.60, tier="validated")
        config = DocSourceConfig(doc_min_similarity=0.65)
        assert _is_allowed(result, config) is False

    def test_at_similarity_threshold_included(self) -> None:
        result = _make_result(similarity=0.65, tier="validated")
        config = DocSourceConfig(doc_min_similarity=0.65)
        assert _is_allowed(result, config) is True

    def test_quarantine_excluded(self) -> None:
        result = _make_result(tier="quarantine", similarity=0.80)
        config = DocSourceConfig()
        assert _is_allowed(result, config) is False

    def test_shared_included(self) -> None:
        result = _make_result(tier="shared", similarity=0.80)
        assert _is_allowed(result, DocSourceConfig()) is True

    def test_bootstrapped_validated_excluded_when_not_allowed(self) -> None:
        result = _make_result(
            tier="validated", bootstrap_confidence=0.75, similarity=0.80
        )
        config = DocSourceConfig(allow_bootstrap_validated=False)
        assert _is_allowed(result, config) is False

    def test_bootstrapped_validated_included_when_allowed(self) -> None:
        result = _make_result(
            tier="validated", bootstrap_confidence=0.75, similarity=0.80
        )
        config = DocSourceConfig(allow_bootstrap_validated=True)
        assert _is_allowed(result, config) is True


# ---------------------------------------------------------------------------
# handle_doc_retrieval (integration)
# ---------------------------------------------------------------------------


class TestHandleDocRetrieval:
    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        result = await handle_doc_retrieval(_make_input([]))
        assert len(result.ranked_items) == 0
        assert result.tokens_used == 0
        assert result.items_considered == 0

    @pytest.mark.asyncio
    async def test_scope_ordering(self) -> None:
        """Exact-repo item ranks above same-org item."""
        exact = _make_result(
            similarity=0.80,
            crawl_scope="omninode/omniintelligence",
            token_estimate=50,
        )
        same_org = _make_result(
            similarity=0.80,
            crawl_scope="omninode/omniclaude",
            token_estimate=50,
        )
        result = await handle_doc_retrieval(
            _make_input([same_org, exact], query_scope="omninode/omniintelligence")
        )
        assert len(result.ranked_items) == 2
        # Exact scope should rank first
        assert result.ranked_items[0].scope_boost == 1.20

    @pytest.mark.asyncio
    async def test_tier_ordering(self) -> None:
        """SHARED item ranks above earned VALIDATED at same similarity."""
        shared = _make_result(tier="shared", similarity=0.80, token_estimate=50)
        validated = _make_result(tier="validated", similarity=0.80, token_estimate=50)
        result = await handle_doc_retrieval(_make_input([validated, shared]))
        assert result.ranked_items[0].tier_multiplier == 1.15  # SHARED first

    @pytest.mark.asyncio
    async def test_budget_enforcement(self) -> None:
        """Items exceeding the token budget are excluded."""
        big = _make_result(token_estimate=1000, similarity=0.90)
        small1 = _make_result(token_estimate=100, similarity=0.85)
        small2 = _make_result(token_estimate=100, similarity=0.80)
        config = DocSourceConfig(doc_token_budget_fraction_default=0.10)
        # total_token_budget=4096, 10% = 409 tokens
        result = await handle_doc_retrieval(
            _make_input(
                [big, small1, small2],
                total_token_budget=4096,
                config=config,
            )
        )
        # big (1000 tokens) exceeds budget of 409 → excluded
        for item in result.ranked_items:
            assert item.token_estimate <= 409

    @pytest.mark.asyncio
    async def test_max_doc_items_cap(self) -> None:
        """No more than max_doc_items are returned."""
        results = [_make_result(token_estimate=10, similarity=0.80) for _ in range(20)]
        config = DocSourceConfig(max_doc_items=5)
        result = await handle_doc_retrieval(_make_input(results, config=config))
        assert len(result.ranked_items) <= 5

    @pytest.mark.asyncio
    async def test_deduplication_by_fingerprint(self) -> None:
        """Items with duplicate content_fingerprint are deduplicated."""
        fingerprint = "same-fingerprint"
        r1 = _make_result(
            similarity=0.90, content_fingerprint=fingerprint, token_estimate=50
        )
        r2 = _make_result(
            similarity=0.80, content_fingerprint=fingerprint, token_estimate=50
        )
        result = await handle_doc_retrieval(_make_input([r1, r2]))
        # Only one item with this fingerprint
        fps = [item.content_fingerprint for item in result.ranked_items]
        assert fps.count(fingerprint) == 1

    @pytest.mark.asyncio
    async def test_below_similarity_filtered(self) -> None:
        """Items below doc_min_similarity are excluded."""
        low = _make_result(similarity=0.50)
        high = _make_result(similarity=0.80)
        config = DocSourceConfig(doc_min_similarity=0.65)
        result = await handle_doc_retrieval(_make_input([low, high], config=config))
        assert all(item.similarity >= 0.65 for item in result.ranked_items)
        assert result.items_filtered >= 1

    @pytest.mark.asyncio
    async def test_compliance_intent_budget(self) -> None:
        """Compliance intent gets 40% budget fraction."""
        result = await handle_doc_retrieval(
            _make_input(
                [_make_result(token_estimate=10)],
                intent_category="compliance",
                total_token_budget=1000,
            )
        )
        assert result.doc_token_budget == 400  # 40% of 1000

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self) -> None:
        result = await handle_doc_retrieval(
            ModelDocRetrievalInput(
                search_results=(),
                query_scope="omninode/omniintelligence",
                correlation_id="test-corr",
            )
        )
        assert result.correlation_id == "test-corr"

    @pytest.mark.asyncio
    async def test_final_score_formula(self) -> None:
        """Verify final_score = similarity * scope_boost * tier_multiplier * intent_weight."""
        result_item = _make_result(
            similarity=0.80,
            tier="shared",
            source_type="RULE",
            crawl_scope="omninode/omniintelligence",
            token_estimate=50,
        )
        output = await handle_doc_retrieval(
            _make_input(
                [result_item],
                query_scope="omninode/omniintelligence",
                intent_category="compliance",
            )
        )
        assert len(output.ranked_items) == 1
        item = output.ranked_items[0]
        expected = 0.80 * 1.20 * 1.15 * 2.5  # compliance RULE weight = 2.5
        assert abs(item.final_score - expected) < 1e-9

    @pytest.mark.asyncio
    async def test_items_considered_and_filtered(self) -> None:
        below = _make_result(similarity=0.40)  # below threshold
        quarantine_item = _make_result(tier="quarantine", similarity=0.80)  # wrong tier
        valid = _make_result(similarity=0.80, token_estimate=10)
        result = await handle_doc_retrieval(
            _make_input([below, quarantine_item, valid])
        )
        assert result.items_considered == 3
        assert result.items_filtered >= 2
        assert len(result.ranked_items) == 1

    @pytest.mark.asyncio
    async def test_budget_fraction_used(self) -> None:
        result_item = _make_result(token_estimate=100, similarity=0.80)
        output = await handle_doc_retrieval(
            _make_input([result_item], total_token_budget=1000)
        )
        assert output.budget_fraction_used == pytest.approx(100 / 1000)
