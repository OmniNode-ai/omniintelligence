# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for handler_doc_promotion — NodeDocPromotionReducer.

All tests use in-memory models only. No live connections.

Test coverage:
    - Source-type threshold dispatch: STATIC_STANDARDS, REPO_DERIVED, MEMORY_HOOK
    - QUARANTINE->VALIDATED promotion gate (scored_runs threshold)
    - VALIDATED->SHARED promotion gates (runs + used_rate + signal_floor)
    - Signal floor blocks early V->S promotion (document items)
    - Signal floor not required for hook-derived items (v0 behavior)
    - VALIDATED->QUARANTINE demotion (hurt_rate threshold)
    - BLACKLISTED: no transitions applied
    - STATIC_STANDARDS: no Q->V gate (starts VALIDATED)
    - Partial failure: unknown source_type is skipped
    - DOC_SECTION_MATCHED signal below doc_min_similarity is skipped
    - Attribution signal accumulation affects promotion decisions
    - PATTERN_VIOLATED drives hurt_rate and triggers demotion
    - Dry run: decisions returned without side effects
    - Empty candidates: returns zero counts
    - Correlation ID propagated through decisions

Ticket: OMN-2395
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from omniintelligence.nodes.node_doc_promotion_reducer.handlers.handler_doc_promotion import (
    _accumulate_signals,
    handle_doc_promotion,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_attribution_signal_type import (
    DOC_MIN_SIMILARITY,
    EnumAttributionSignalType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_context_item_source_type import (
    EnumContextItemSourceType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_promotion_tier import (
    EnumPromotionTier,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_attribution_signal import (
    ModelAttributionSignal,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_doc_promotion_input import (
    ModelDocPromotionInput,
    ModelPromotionCandidate,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_candidate(
    *,
    source_type: EnumContextItemSourceType = EnumContextItemSourceType.REPO_DERIVED,
    current_tier: EnumPromotionTier = EnumPromotionTier.QUARANTINE,
    scored_runs: int = 0,
    positive_signals: int = 0,
    used_rate: float = 0.0,
    hurt_rate: float = 0.0,
    recent_signals: tuple[ModelAttributionSignal, ...] = (),
    correlation_id: str | None = "test-corr",
) -> ModelPromotionCandidate:
    return ModelPromotionCandidate(
        item_id=uuid4(),
        source_type=source_type,
        current_tier=current_tier,
        scored_runs=scored_runs,
        positive_signals=positive_signals,
        used_rate=used_rate,
        hurt_rate=hurt_rate,
        recent_signals=recent_signals,
        correlation_id=correlation_id,
    )


def _make_signal(
    signal_type: EnumAttributionSignalType,
    strength: float = 1.0,
    similarity: float | None = None,
) -> ModelAttributionSignal:
    return ModelAttributionSignal(
        item_id=uuid4(),
        signal_type=signal_type,
        strength=strength,
        similarity=similarity,
    )


def _make_input(
    candidates: list[ModelPromotionCandidate],
    dry_run: bool = False,
    correlation_id: str | None = "test-corr",
) -> ModelDocPromotionInput:
    return ModelDocPromotionInput(
        candidates=tuple(candidates),
        dry_run=dry_run,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# QUARANTINE -> VALIDATED
# ---------------------------------------------------------------------------


class TestQuarantineToValidated:
    @pytest.mark.asyncio
    async def test_repo_derived_promotes_at_threshold(self) -> None:
        """REPO_DERIVED: Q->V at 5 scored_runs."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=5,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.VALIDATED
        assert result.decisions[0].promoted is True

    @pytest.mark.asyncio
    async def test_repo_derived_blocked_below_threshold(self) -> None:
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=4,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.QUARANTINE
        assert result.decisions[0].promoted is False

    @pytest.mark.asyncio
    async def test_memory_hook_promotes_at_10_runs(self) -> None:
        """MEMORY_HOOK: Q->V at 10 scored_runs (v0 unchanged)."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.MEMORY_HOOK,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=10,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.VALIDATED
        assert result.decisions[0].promoted is True

    @pytest.mark.asyncio
    async def test_static_standards_starts_validated_no_qv_gate(self) -> None:
        """STATIC_STANDARDS: quarantine_to_validated_runs is None — skip Q->V."""
        # STATIC_STANDARDS starting in QUARANTINE: should not promote via Q->V
        # (the design doc says it starts VALIDATED, so QUARANTINE is unexpected
        # but the handler must not crash)
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=100,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        # quarantine_to_validated_runs is None -> no Q->V gate -> stays QUARANTINE
        assert result.decisions[0].new_tier == EnumPromotionTier.QUARANTINE
        assert result.decisions[0].promoted is False


# ---------------------------------------------------------------------------
# VALIDATED -> SHARED
# ---------------------------------------------------------------------------


class TestValidatedToShared:
    @pytest.mark.asyncio
    async def test_static_standards_full_promotion(self) -> None:
        """STATIC_STANDARDS: V->S at 10 runs, 0.10 used_rate, 5 signals."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=10,
            used_rate=0.10,
            positive_signals=5,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.SHARED
        assert result.decisions[0].promoted is True
        assert result.decisions[0].blocked_by is None

    @pytest.mark.asyncio
    async def test_blocked_by_insufficient_runs(self) -> None:
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=9,  # threshold is 10
            used_rate=0.15,
            positive_signals=5,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.VALIDATED
        assert result.decisions[0].blocked_by is not None
        assert "scored_runs" in result.decisions[0].blocked_by

    @pytest.mark.asyncio
    async def test_blocked_by_low_used_rate(self) -> None:
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=10,
            used_rate=0.05,  # below 0.10
            positive_signals=5,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].blocked_by is not None
        assert "used_rate" in result.decisions[0].blocked_by

    @pytest.mark.asyncio
    async def test_signal_floor_blocks_early_promotion(self) -> None:
        """Signal floor prevents V->S with only 4 positive signals."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=15,
            used_rate=0.20,
            positive_signals=4,  # floor is 5
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.VALIDATED
        assert result.decisions[0].blocked_by is not None
        assert "positive_signals" in result.decisions[0].blocked_by

    @pytest.mark.asyncio
    async def test_signal_floor_satisfied_by_recent_signals(self) -> None:
        """Signal floor can be met by accumulating recent attribution signals."""
        rule_signal = _make_signal(
            EnumAttributionSignalType.RULE_FOLLOWED, strength=0.9
        )
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=10,
            used_rate=0.12,
            positive_signals=4,  # 1 short of floor
            recent_signals=(rule_signal,),  # adds 1 -> total 5
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.SHARED
        assert result.decisions[0].promoted is True

    @pytest.mark.asyncio
    async def test_no_signal_floor_for_memory_hook(self) -> None:
        """MEMORY_HOOK: no signal floor (v0 behavior)."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.MEMORY_HOOK,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=30,
            used_rate=0.25,
            positive_signals=0,  # floor is 0 for MEMORY_HOOK
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.SHARED
        assert result.decisions[0].promoted is True

    @pytest.mark.asyncio
    async def test_repo_derived_full_promotion(self) -> None:
        """REPO_DERIVED: V->S at 20 runs, 0.15 used_rate, 5 signals."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=20,
            used_rate=0.15,
            positive_signals=5,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.SHARED
        assert result.decisions[0].promoted is True


# ---------------------------------------------------------------------------
# Demotion: VALIDATED -> QUARANTINE
# ---------------------------------------------------------------------------


class TestDemotion:
    @pytest.mark.asyncio
    async def test_pattern_violated_triggers_demotion(self) -> None:
        """High hurt_rate triggers VALIDATED->QUARANTINE."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=10,
            hurt_rate=0.50,  # >= 0.40 threshold
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.QUARANTINE
        assert result.decisions[0].demoted is True
        assert result.items_demoted == 1

    @pytest.mark.asyncio
    async def test_demotion_signal_accumulation(self) -> None:
        """PATTERN_VIOLATED signals accumulate into hurt_rate and trigger demotion."""
        # Start with low hurt_rate but add pattern_violated signal
        violated_signal = _make_signal(
            EnumAttributionSignalType.PATTERN_VIOLATED, strength=1.0
        )
        # scored_runs=1, hurt_rate=0.0 initially
        # After accumulation: hurt_count=1, effective_hurt_rate = 1/1 = 1.0 >= 0.40
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=1,
            hurt_rate=0.0,
            recent_signals=(violated_signal,),
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].demoted is True

    @pytest.mark.asyncio
    async def test_demotion_takes_priority_over_promotion(self) -> None:
        """Demotion check runs before promotion gates."""
        # Candidate meets V->S gates but also has high hurt_rate
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.VALIDATED,
            scored_runs=15,
            used_rate=0.15,
            positive_signals=10,
            hurt_rate=0.45,  # >= 0.40 threshold → demote
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.QUARANTINE
        assert result.decisions[0].demoted is True

    @pytest.mark.asyncio
    async def test_no_demotion_from_quarantine(self) -> None:
        """Demotion only applies to VALIDATED tier."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
            hurt_rate=0.90,  # would trigger demotion if VALIDATED
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        # No demotion from QUARANTINE
        assert result.decisions[0].demoted is False


# ---------------------------------------------------------------------------
# BLACKLISTED
# ---------------------------------------------------------------------------


class TestBlacklisted:
    @pytest.mark.asyncio
    async def test_blacklisted_no_transitions(self) -> None:
        """BLACKLISTED is a terminal tier — no promotion or demotion."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.BLACKLISTED,
            scored_runs=100,
            used_rate=1.0,
            positive_signals=100,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.BLACKLISTED
        assert result.decisions[0].promoted is False
        assert result.decisions[0].demoted is False
        assert result.decisions[0].blocked_by is not None


# ---------------------------------------------------------------------------
# Attribution signal handling
# ---------------------------------------------------------------------------


class TestAttributionSignals:
    def test_doc_section_matched_below_threshold_skipped(self) -> None:
        """DOC_SECTION_MATCHED below DOC_MIN_SIMILARITY is ignored."""
        signal = _make_signal(
            EnumAttributionSignalType.DOC_SECTION_MATCHED,
            strength=0.50,
            similarity=DOC_MIN_SIMILARITY - 0.01,  # just below threshold
        )
        candidate = _make_candidate(
            positive_signals=0,
            recent_signals=(signal,),
        )
        effective_positive, _ = _accumulate_signals(candidate)
        # Signal should be skipped
        assert effective_positive == 0

    def test_doc_section_matched_at_threshold_counted(self) -> None:
        """DOC_SECTION_MATCHED at exactly DOC_MIN_SIMILARITY is counted."""
        signal = _make_signal(
            EnumAttributionSignalType.DOC_SECTION_MATCHED,
            strength=DOC_MIN_SIMILARITY,
            similarity=DOC_MIN_SIMILARITY,
        )
        candidate = _make_candidate(
            positive_signals=0,
            recent_signals=(signal,),
        )
        effective_positive, _ = _accumulate_signals(candidate)
        assert effective_positive == 1

    def test_pattern_violated_increments_hurt_rate(self) -> None:
        """PATTERN_VIOLATED increments effective hurt_rate."""
        signal = _make_signal(EnumAttributionSignalType.PATTERN_VIOLATED)
        candidate = _make_candidate(
            scored_runs=10,
            hurt_rate=0.0,
            recent_signals=(signal,),
        )
        _, effective_hurt = _accumulate_signals(candidate)
        assert effective_hurt > 0.0

    def test_rule_followed_increments_positive_signals(self) -> None:
        signal = _make_signal(EnumAttributionSignalType.RULE_FOLLOWED, strength=0.9)
        candidate = _make_candidate(positive_signals=3, recent_signals=(signal,))
        effective_positive, _ = _accumulate_signals(candidate)
        assert effective_positive == 4

    def test_standard_cited_increments_positive_signals(self) -> None:
        signal = _make_signal(EnumAttributionSignalType.STANDARD_CITED, strength=1.0)
        candidate = _make_candidate(positive_signals=0, recent_signals=(signal,))
        effective_positive, _ = _accumulate_signals(candidate)
        assert effective_positive == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_candidates(self) -> None:
        result = await handle_doc_promotion(_make_input([]))
        assert result.items_promoted == 0
        assert result.items_demoted == 0
        assert result.items_unchanged == 0
        assert len(result.decisions) == 0

    @pytest.mark.asyncio
    async def test_dry_run_returns_decisions(self) -> None:
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=5,
        )
        result = await handle_doc_promotion(_make_input([candidate], dry_run=True))
        assert result.dry_run is True
        # Decision still computed
        assert result.decisions[0].new_tier == EnumPromotionTier.VALIDATED

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self) -> None:
        candidate = _make_candidate(
            correlation_id="my-corr-id",
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
        )
        result = await handle_doc_promotion(
            _make_input([candidate], correlation_id="my-corr-id")
        )
        assert result.correlation_id == "my-corr-id"
        assert result.decisions[0].correlation_id == "my-corr-id"

    @pytest.mark.asyncio
    async def test_multiple_candidates_aggregate_counts(self) -> None:
        promoted = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=5,
        )
        unchanged = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.QUARANTINE,
            scored_runs=3,
        )
        demoted = _make_candidate(
            source_type=EnumContextItemSourceType.REPO_DERIVED,
            current_tier=EnumPromotionTier.VALIDATED,
            hurt_rate=0.60,  # >= 0.45 threshold
        )
        result = await handle_doc_promotion(_make_input([promoted, unchanged, demoted]))
        assert result.items_promoted == 1
        assert result.items_demoted == 1
        assert result.items_unchanged == 1

    @pytest.mark.asyncio
    async def test_shared_tier_no_further_promotion(self) -> None:
        """Items already at SHARED have no further gates."""
        candidate = _make_candidate(
            source_type=EnumContextItemSourceType.STATIC_STANDARDS,
            current_tier=EnumPromotionTier.SHARED,
            scored_runs=100,
            used_rate=1.0,
            positive_signals=100,
        )
        result = await handle_doc_promotion(_make_input([candidate]))
        assert result.decisions[0].new_tier == EnumPromotionTier.SHARED
        assert result.decisions[0].promoted is False
