# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for DocPromotionReducer — source-type-aware promotion and demotion.

Behavior:
  - Evaluates ContextItem candidates against source-type-specific gates
  - Applies QUARANTINE→VALIDATED, VALIDATED→SHARED, and VALIDATED→QUARANTINE
    transitions based on scored_runs, used_rate, hurt_rate, and signal floor
  - Does NOT persist transitions (pure reducer — caller handles persistence)

Promotion Logic:
  Each source type has a ModelPromotionThresholdSet from THRESHOLD_SETS.
  Gates are applied in priority order:

  1. Demotion check (VALIDATED→QUARANTINE):
     - hurt_rate >= threshold.validated_to_quarantine_hurt_rate → demote
     - Takes priority over any promotion

  2. QUARANTINE→VALIDATED:
     - current_tier == QUARANTINE
     - threshold.quarantine_to_validated_runs is not None
     - scored_runs >= threshold.quarantine_to_validated_runs

  3. VALIDATED→SHARED:
     - current_tier == VALIDATED (after Q→V advancement)
     - scored_runs >= threshold.validated_to_shared_runs
     - used_rate >= threshold.validated_to_shared_used_rate
     - positive_signals >= threshold.validated_to_shared_signal_floor

  4. BLACKLISTED:
     - Terminal tier. No further transitions evaluated.

Attribution Signal Processing:
  Each candidate may carry recent_signals. Before promotion gates are evaluated:
  - POSITIVE_SIGNAL_TYPES contribute to positive_signals counter
  - NEGATIVE_SIGNAL_TYPES (PATTERN_VIOLATED) contribute to hurt_rate increase

  Note: The handler accumulates signal counts from recent_signals into the
  candidate's running totals for gate evaluation. This does NOT modify the
  candidate model — running counts are computed locally.

  DOC_SECTION_MATCHED signals are only valid when similarity >= DOC_MIN_SIMILARITY.
  The handler validates this invariant and skips invalid signals.

Design:
  - Pure function (no I/O). Caller persists transitions.
  - All threshold logic in THRESHOLD_SETS (no hardcoded numbers here).
  - BLACKLISTED items are returned unchanged with no gates applied.

Ticket: OMN-2395
"""

from __future__ import annotations

import logging

from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_attribution_signal_type import (
    DOC_MIN_SIMILARITY,
    NEGATIVE_SIGNAL_TYPES,
    POSITIVE_SIGNAL_TYPES,
    EnumAttributionSignalType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_context_item_source_type import (
    EnumContextItemSourceType,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_promotion_tier import (
    EnumPromotionTier,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_doc_promotion_input import (
    ModelDocPromotionInput,
    ModelPromotionCandidate,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_doc_promotion_output import (
    ModelDocPromotionOutput,
    ModelPromotionDecision,
)
from omniintelligence.nodes.node_doc_promotion_reducer.models.model_promotion_threshold_set import (
    THRESHOLD_SETS,
    ModelPromotionThresholdSet,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Signal accumulation
# =============================================================================


def _accumulate_signals(
    candidate: ModelPromotionCandidate,
) -> tuple[int, float]:
    """Compute effective positive_signals and hurt_rate after accumulating recent signals.

    Processes candidate.recent_signals:
      - Each positive signal increments the running positive_signals count.
      - Each PATTERN_VIOLATED signal increments an effective hurt counter.
      - DOC_SECTION_MATCHED signals below DOC_MIN_SIMILARITY are skipped.

    The effective hurt_rate is recomputed as:
        new_hurt_rate = (existing_hurt_count + new_hurts) / (scored_runs + 1)
    where scored_runs + 1 approximates the denominator after this batch.
    If scored_runs == 0, the denominator is 1.

    Returns:
        (effective_positive_signals, effective_hurt_rate)
    """
    positive_count = candidate.positive_signals
    # Compute existing absolute hurt count from hurt_rate
    denominator = max(candidate.scored_runs, 1)
    hurt_count = round(candidate.hurt_rate * denominator)

    for signal in candidate.recent_signals:
        # Validate DOC_SECTION_MATCHED similarity gate
        if signal.signal_type == EnumAttributionSignalType.DOC_SECTION_MATCHED:
            if signal.similarity is None or signal.similarity < DOC_MIN_SIMILARITY:
                logger.debug(
                    "Skipping DOC_SECTION_MATCHED signal for item %s: "
                    "similarity=%s below minimum=%s",
                    candidate.item_id,
                    signal.similarity,
                    DOC_MIN_SIMILARITY,
                )
                continue

        if signal.signal_type in POSITIVE_SIGNAL_TYPES:
            positive_count += 1
        elif signal.signal_type in NEGATIVE_SIGNAL_TYPES:
            hurt_count += 1

    effective_hurt_rate = hurt_count / denominator
    return positive_count, min(effective_hurt_rate, 1.0)


# =============================================================================
# Gate evaluation (pure, per-candidate)
# =============================================================================


def _evaluate_candidate(
    candidate: ModelPromotionCandidate,
    thresholds: ModelPromotionThresholdSet,
) -> ModelPromotionDecision:
    """Evaluate a single candidate against the threshold set.

    Returns a ModelPromotionDecision with the computed tier transition.
    """
    old_tier = candidate.current_tier

    # BLACKLISTED: terminal — no transitions
    if old_tier == EnumPromotionTier.BLACKLISTED:
        return ModelPromotionDecision(
            item_id=candidate.item_id,
            old_tier=old_tier,
            new_tier=old_tier,
            promoted=False,
            demoted=False,
            blocked_by="item is BLACKLISTED (terminal tier)",
            correlation_id=candidate.correlation_id,
        )

    # Accumulate signal effects
    effective_positive_signals, effective_hurt_rate = _accumulate_signals(candidate)

    current_tier = old_tier

    # Priority 1: Demotion check (VALIDATED → QUARANTINE)
    if (
        current_tier == EnumPromotionTier.VALIDATED
        and effective_hurt_rate >= thresholds.validated_to_quarantine_hurt_rate
    ):
        logger.info(
            "Demoting item %s: VALIDATED→QUARANTINE (hurt_rate=%.3f >= threshold=%.3f)",
            candidate.item_id,
            effective_hurt_rate,
            thresholds.validated_to_quarantine_hurt_rate,
        )
        return ModelPromotionDecision(
            item_id=candidate.item_id,
            old_tier=old_tier,
            new_tier=EnumPromotionTier.QUARANTINE,
            promoted=False,
            demoted=True,
            blocked_by=None,
            correlation_id=candidate.correlation_id,
        )

    # Priority 2: QUARANTINE → VALIDATED
    if (
        current_tier == EnumPromotionTier.QUARANTINE
        and thresholds.quarantine_to_validated_runs is not None
        and candidate.scored_runs >= thresholds.quarantine_to_validated_runs
    ):
        logger.info(
            "Promoting item %s: QUARANTINE→VALIDATED (scored_runs=%d >= threshold=%d)",
            candidate.item_id,
            candidate.scored_runs,
            thresholds.quarantine_to_validated_runs,
        )
        current_tier = EnumPromotionTier.VALIDATED

    # Priority 3: VALIDATED → SHARED
    if current_tier == EnumPromotionTier.VALIDATED:
        # Check all V→S gates
        if candidate.scored_runs < thresholds.validated_to_shared_runs:
            blocked = (
                f"scored_runs={candidate.scored_runs} < "
                f"required={thresholds.validated_to_shared_runs}"
            )
            return ModelPromotionDecision(
                item_id=candidate.item_id,
                old_tier=old_tier,
                new_tier=current_tier,
                promoted=(current_tier != old_tier),
                demoted=False,
                blocked_by=blocked,
                correlation_id=candidate.correlation_id,
            )

        if candidate.used_rate < thresholds.validated_to_shared_used_rate:
            blocked = (
                f"used_rate={candidate.used_rate:.3f} < "
                f"required={thresholds.validated_to_shared_used_rate:.3f}"
            )
            return ModelPromotionDecision(
                item_id=candidate.item_id,
                old_tier=old_tier,
                new_tier=current_tier,
                promoted=(current_tier != old_tier),
                demoted=False,
                blocked_by=blocked,
                correlation_id=candidate.correlation_id,
            )

        if (
            thresholds.validated_to_shared_signal_floor > 0
            and effective_positive_signals < thresholds.validated_to_shared_signal_floor
        ):
            blocked = (
                f"positive_signals={effective_positive_signals} < "
                f"signal_floor={thresholds.validated_to_shared_signal_floor}"
            )
            return ModelPromotionDecision(
                item_id=candidate.item_id,
                old_tier=old_tier,
                new_tier=current_tier,
                promoted=(current_tier != old_tier),
                demoted=False,
                blocked_by=blocked,
                correlation_id=candidate.correlation_id,
            )

        # All V→S gates passed
        logger.info(
            "Promoting item %s: VALIDATED→SHARED "
            "(runs=%d, used_rate=%.3f, positive_signals=%d)",
            candidate.item_id,
            candidate.scored_runs,
            candidate.used_rate,
            effective_positive_signals,
        )
        return ModelPromotionDecision(
            item_id=candidate.item_id,
            old_tier=old_tier,
            new_tier=EnumPromotionTier.SHARED,
            promoted=True,
            demoted=False,
            blocked_by=None,
            correlation_id=candidate.correlation_id,
        )

    # QUARANTINE with no Q→V gate (STATIC_STANDARDS starts VALIDATED — shouldn't be here)
    # or SHARED (no further promotions)
    return ModelPromotionDecision(
        item_id=candidate.item_id,
        old_tier=old_tier,
        new_tier=current_tier,
        promoted=(current_tier != old_tier),
        demoted=False,
        blocked_by=None if current_tier != old_tier else "no applicable promotion gate",
        correlation_id=candidate.correlation_id,
    )


# =============================================================================
# Main handler
# =============================================================================


async def handle_doc_promotion(
    input_data: ModelDocPromotionInput,
    *,
    threshold_sets: dict[EnumContextItemSourceType, ModelPromotionThresholdSet]
    | None = None,
) -> ModelDocPromotionOutput:
    """Evaluate promotion gates for a batch of ContextItem candidates.

    Selects the threshold set for each candidate based on source_type.
    Evaluates demotion, Q→V, and V→S gates in priority order.
    Returns decisions without persisting — caller handles persistence.

    Args:
        input_data:     Batch of candidates with recent attribution signals.
        threshold_sets: Optional override for canonical THRESHOLD_SETS.
                        Defaults to the canonical sets from model_promotion_threshold_set.

    Returns:
        ModelDocPromotionOutput with per-candidate decisions and aggregate counts.
    """
    effective_thresholds = (
        threshold_sets if threshold_sets is not None else THRESHOLD_SETS
    )

    decisions: list[ModelPromotionDecision] = []
    items_promoted = 0
    items_demoted = 0
    items_unchanged = 0

    for candidate in input_data.candidates:
        thresholds = effective_thresholds.get(candidate.source_type)
        if thresholds is None:
            # Unknown source type — skip without a decision
            logger.warning(
                "No threshold set for source_type=%s (item_id=%s). Skipping.",
                candidate.source_type,
                candidate.item_id,
            )
            continue

        if input_data.dry_run:
            # Compute decision without side effects
            decision = _evaluate_candidate(candidate, thresholds)
            decisions.append(decision)
            if decision.promoted:
                items_promoted += 1
            elif decision.demoted:
                items_demoted += 1
            else:
                items_unchanged += 1
        else:
            decision = _evaluate_candidate(candidate, thresholds)
            decisions.append(decision)
            if decision.promoted:
                items_promoted += 1
            elif decision.demoted:
                items_demoted += 1
            else:
                items_unchanged += 1

    logger.info(
        "DocPromotion: promoted=%d demoted=%d unchanged=%d dry_run=%s",
        items_promoted,
        items_demoted,
        items_unchanged,
        input_data.dry_run,
    )

    return ModelDocPromotionOutput(
        decisions=tuple(decisions),
        items_promoted=items_promoted,
        items_demoted=items_demoted,
        items_unchanged=items_unchanged,
        dry_run=input_data.dry_run,
        correlation_id=input_data.correlation_id,
    )


__all__ = ["handle_doc_promotion"]
