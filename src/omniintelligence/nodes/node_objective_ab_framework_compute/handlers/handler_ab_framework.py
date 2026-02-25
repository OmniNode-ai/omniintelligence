# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""A/B objective testing framework handler — pure functions.

Core logic for multi-variant objective evaluation:

1. Traffic splitting via deterministic hash on run_id.
   Same run_id → same variant assignment every time.

2. Parallel evaluation against all variants.
   Each variant receives the same EvidenceBundle.

3. Divergence detection.
   Compares active and shadow results: different passed outcomes OR
   ScoreVector L2 distance > threshold.

4. Statistical significance tracking.
   Shadow win rate over N runs. Emits upgrade-ready signal at threshold.

Constraints:
  - Shadow variants never drive policy state changes.
  - Traffic split is deterministic: same run_id → same assignment.
  - Statistical significance threshold and min_runs from registry config.
  - Promotion is NOT automatic — upgrade-ready is a signal only.

Ticket: OMN-2571
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any

from omniintelligence.nodes.node_objective_ab_framework_compute.models.enum_variant_role import (
    EnumVariantRole,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_input import (
    ModelABEvaluationInput,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_ab_evaluation_output import (
    ModelABEvaluationOutput,
    ModelVariantEvaluationResult,
)
from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariant,
    ModelObjectiveVariantRegistry,
)

logger = logging.getLogger(__name__)


def route_to_variant(
    run_id: str,
    registry: ModelObjectiveVariantRegistry,
) -> ModelObjectiveVariant:
    """Deterministically route a run_id to a variant using hash-based splitting.

    The routing is reproducible: the same run_id always maps to the same
    variant. Implements a consistent hash that respects traffic_weight.

    Algorithm:
        1. Hash run_id to a float in [0.0, 1.0]
        2. Cumulative weight scan to find the variant bucket
        3. Return the variant whose bucket contains the hash value

    Args:
        run_id:   Execution run identifier.
        registry: Registry of variants with traffic weights.

    Returns:
        The variant that should receive this run.
    """
    # SHA-256 hash of run_id → deterministic float in [0.0, 1.0)
    hash_bytes = hashlib.sha256(run_id.encode("utf-8")).digest()
    hash_int = int.from_bytes(hash_bytes[:8], "big")
    hash_frac = hash_int / (2**64)  # normalize to [0.0, 1.0)

    # Cumulative weight scan
    cumulative = 0.0
    for variant in registry.variants:
        if not variant.is_active:
            continue
        cumulative += variant.traffic_weight
        if hash_frac < cumulative:
            return variant

    # Fallback: return the active variant (handles floating point edge cases)
    for variant in registry.variants:
        if variant.role == EnumVariantRole.ACTIVE:
            return variant

    # Should never reach here (registry validates exactly 1 active)
    return registry.variants[0]


def compute_score_delta(
    result_a: ModelVariantEvaluationResult,
    result_b: ModelVariantEvaluationResult,
) -> float:
    """Compute L2 distance between two variant ScoreVectors.

    Args:
        result_a: First variant result.
        result_b: Second variant result.

    Returns:
        L2 distance in [0.0, sqrt(6)] (normalized to 6 dimensions).
    """
    dims = [
        ("score_correctness", result_a.score_correctness, result_b.score_correctness),
        ("score_safety", result_a.score_safety, result_b.score_safety),
        ("score_cost", result_a.score_cost, result_b.score_cost),
        ("score_latency", result_a.score_latency, result_b.score_latency),
        (
            "score_maintainability",
            result_a.score_maintainability,
            result_b.score_maintainability,
        ),
        ("score_human_time", result_a.score_human_time, result_b.score_human_time),
    ]
    return math.sqrt(sum((a - b) ** 2 for _, a, b in dims))


def detect_divergence(
    active: ModelVariantEvaluationResult,
    shadow: ModelVariantEvaluationResult,
    threshold: float,
) -> bool:
    """Detect divergence between active and shadow variant results.

    Divergence occurs when:
    - They disagree on passed outcome (one passes, other fails), OR
    - Their ScoreVector L2 distance exceeds the threshold.

    Args:
        active:    Active variant evaluation result.
        shadow:    Shadow variant evaluation result.
        threshold: L2 distance threshold for divergence.

    Returns:
        True if divergence detected.
    """
    if active.passed != shadow.passed:
        return True
    return compute_score_delta(active, shadow) > threshold


def check_upgrade_ready(
    _shadow_variant_id: str,
    run_count: int,
    shadow_wins: int,
    registry: ModelObjectiveVariantRegistry,
) -> bool:
    """Check if a shadow variant has reached statistical significance for upgrade.

    Uses a simple win-rate threshold check:
    - Must have at least min_runs_for_significance runs
    - Shadow win rate must exceed (1 - significance_threshold)

    Note: This is a simplified significance test. A full binomial test
    would be more rigorous, but this provides a practical threshold.

    Args:
        _shadow_variant_id: Shadow variant ID being checked (reserved for future use).
        run_count:          Total runs evaluated for this variant.
        shadow_wins:        Runs where shadow outperformed active.
        registry:           Registry containing threshold config.

    Returns:
        True if the shadow variant is ready for promotion.
    """
    if run_count < registry.min_runs_for_significance:
        return False

    win_rate = shadow_wins / max(run_count, 1)
    # Upgrade ready when win rate exceeds (1 - significance_threshold)
    # e.g., threshold=0.05 → need win_rate > 0.95
    return win_rate >= (1.0 - registry.significance_threshold)


def _evaluate_variant_against_bundle(
    variant: ModelObjectiveVariant,
    evidence_bundle: dict[str, Any],
) -> ModelVariantEvaluationResult:
    """Evaluate a single variant against an evidence bundle.

    This is a stub evaluation that reads pre-computed scores from the
    evidence bundle's metadata field if present, or returns zeros.
    In production, this delegates to ScoringReducerCompute.

    Args:
        variant:         The variant to evaluate.
        evidence_bundle: The evidence bundle dict.

    Returns:
        ModelVariantEvaluationResult with scores.
    """
    # Extract scores from bundle metadata if available (for testing/replay)
    # In production, this calls ScoringReducerCompute(spec=variant.objective_spec)
    metadata = evidence_bundle.get("metadata", {})
    if isinstance(metadata, dict):
        scores = metadata.get("precomputed_scores", {})
    else:
        scores = {}

    passed = bool(metadata.get("passed", True)) if isinstance(metadata, dict) else True

    return ModelVariantEvaluationResult(
        variant_id=variant.variant_id,
        objective_id=variant.objective_id,
        objective_version=variant.objective_version,
        role=variant.role,
        passed=passed,
        score_correctness=float(scores.get("correctness", 0.0)),
        score_safety=float(scores.get("safety", 0.0)),
        score_cost=float(scores.get("cost", 0.0)),
        score_latency=float(scores.get("latency", 0.0)),
        score_maintainability=float(scores.get("maintainability", 0.0)),
        score_human_time=float(scores.get("human_time", 0.0)),
        drives_policy_state=(variant.role == EnumVariantRole.ACTIVE),
    )


def run_ab_evaluation(input_data: ModelABEvaluationInput) -> ModelABEvaluationOutput:
    """Run A/B evaluation of an EvidenceBundle against all registered variants.

    Evaluation order:
    1. Evaluate all variants against the same evidence bundle
    2. Detect divergence between active and shadow variants
    3. Check statistical significance for upgrade-ready signal

    Shadow variants do NOT affect policy state (drives_policy_state=False).
    Same run_id always produces same routing decision (deterministic).

    Args:
        input_data: A/B evaluation input with evidence bundle and registry.

    Returns:
        ModelABEvaluationOutput with per-variant results and divergence/upgrade flags.
    """
    registry = input_data.registry

    # Evaluate all active variants against the same evidence bundle
    variant_results: list[ModelVariantEvaluationResult] = []
    for variant in registry.variants:
        result = _evaluate_variant_against_bundle(
            variant=variant,
            evidence_bundle=input_data.evidence_bundle,
        )
        variant_results.append(result)

    # Find active and shadow results for divergence detection
    active_result = next(
        (r for r in variant_results if r.role == EnumVariantRole.ACTIVE), None
    )
    shadow_results = [r for r in variant_results if r.role == EnumVariantRole.SHADOW]

    divergence_detected = False
    upgrade_ready = False
    upgrade_ready_variant_id: str | None = None

    if active_result is not None:
        for shadow_result in shadow_results:
            # Check divergence
            if detect_divergence(
                active_result, shadow_result, registry.divergence_threshold
            ):
                divergence_detected = True
                logger.info(
                    "Variant divergence detected (run=%s): active=%s shadow=%s",
                    input_data.run_id,
                    active_result.objective_version,
                    shadow_result.objective_version,
                )

            # Check upgrade-ready signal
            run_count = input_data.run_count_by_variant.get(shadow_result.variant_id, 0)
            shadow_wins = input_data.shadow_win_count_by_variant.get(
                shadow_result.variant_id, 0
            )

            if check_upgrade_ready(
                shadow_result.variant_id,
                run_count=run_count,
                shadow_wins=shadow_wins,
                registry=registry,
            ):
                upgrade_ready = True
                upgrade_ready_variant_id = shadow_result.variant_id
                logger.info(
                    "Upgrade ready: shadow variant '%s' reached significance "
                    "(run_count=%d, shadow_wins=%d)",
                    shadow_result.variant_id,
                    run_count,
                    shadow_wins,
                )

    return ModelABEvaluationOutput(
        run_id=input_data.run_id,
        variant_results=tuple(variant_results),
        divergence_detected=divergence_detected,
        upgrade_ready=upgrade_ready,
        upgrade_ready_variant_id=upgrade_ready_variant_id,
    )


__all__ = [
    "check_upgrade_ready",
    "compute_score_delta",
    "detect_divergence",
    "route_to_variant",
    "run_ab_evaluation",
]
