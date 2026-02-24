# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Anti-gaming guardrail checks — pure functions, no I/O.

Four structural defenses against metric gaming:

1. Goodhart's Law Detection:
   Monitor correlated metric pairs. When metric A improves AND metric B
   degrades, and their sum of deltas exceeds the threshold, emit alert.

2. Reward Hacking Detection:
   When correctness improves by > X% but human_acceptance_rate does not
   improve accordingly, emit alert.

3. Distributional Shift Detection:
   Compare current evidence source distribution against baseline using
   a simple symmetric KL-divergence approximation. Alert on excess drift.

4. Diversity Constraint:
   Enforce minimum number of distinct EvidenceItem source types.
   Fewer than N → DiversityConstraintViolation (VETO).

Constraints:
  - Guards 1–3 emit alerts only (non-blocking).
  - Guard 4 (diversity) is a veto.
  - All thresholds from ModelGuardrailConfig (zero hardcoded numbers).
  - Pure functions: identical inputs → identical outputs.

Ticket: OMN-2563
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_alert_event import (
    ModelAntiGamingAlertUnion,
    ModelDistributionalShiftAlert,
    ModelDiversityConstraintViolation,
    ModelGoodhartViolationAlert,
    ModelRewardHackingAlert,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_config import (
    ModelGuardrailConfig,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_input import (
    ModelGuardrailInput,
    ModelScoreVectorSnapshot,
)
from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_output import (
    ModelGuardrailOutput,
)

logger = logging.getLogger(__name__)

# Minimum probability for KL divergence computation (prevents log(0))
_KL_EPSILON = 1e-9


def check_goodhart_violation(
    run_id: str,
    objective_id: str,
    current_score: ModelScoreVectorSnapshot,
    previous_score: ModelScoreVectorSnapshot,
    config: ModelGuardrailConfig,
    occurred_at_utc: str,
) -> list[ModelGoodhartViolationAlert]:
    """Check for Goodhart's Law violations in correlated metric pairs.

    Fires when metric_a improves AND metric_b degrades, with total divergence
    exceeding the threshold.

    Args:
        run_id:         Current run identifier.
        objective_id:   ObjectiveSpec identifier.
        current_score:  Score from the current run.
        previous_score: Score from the previous run.
        config:         Guardrail configuration.
        occurred_at_utc: Timestamp for alerts.

    Returns:
        List of GoodhartViolationAlert (may be empty).
    """
    alerts: list[ModelGoodhartViolationAlert] = []

    for pair in config.correlation_pairs:
        delta_a = (
            current_score.get_dimension(pair.metric_a)
            - previous_score.get_dimension(pair.metric_a)
        )
        delta_b = (
            current_score.get_dimension(pair.metric_b)
            - previous_score.get_dimension(pair.metric_b)
        )

        # Goodhart violation: A improves while B degrades
        if delta_a > 0 and delta_b < 0:
            total_divergence = abs(delta_a) + abs(delta_b)
            if total_divergence > pair.divergence_threshold:
                logger.warning(
                    "Goodhart violation (run=%s): %s improved %.3f while %s degraded %.3f "
                    "(divergence=%.3f > threshold=%.3f)",
                    run_id,
                    pair.metric_a,
                    delta_a,
                    pair.metric_b,
                    delta_b,
                    total_divergence,
                    pair.divergence_threshold,
                )
                alerts.append(
                    ModelGoodhartViolationAlert(
                        run_id=run_id,
                        objective_id=objective_id,
                        improving_metric=pair.metric_a,
                        degrading_metric=pair.metric_b,
                        improvement_delta=delta_a,
                        degradation_delta=delta_b,
                        threshold=pair.divergence_threshold,
                        occurred_at_utc=occurred_at_utc,
                    )
                )

    return alerts


def check_reward_hacking(
    run_id: str,
    objective_id: str,
    current_score: ModelScoreVectorSnapshot,
    previous_score: ModelScoreVectorSnapshot,
    human_acceptance_rate: float | None,
    previous_acceptance_rate: float | None,
    config: ModelGuardrailConfig,
    occurred_at_utc: str,
) -> ModelRewardHackingAlert | None:
    """Check for reward hacking: score improves but human acceptance does not.

    Fires when:
    - correctness improves by > config.reward_hacking_score_threshold
    - AND acceptance_rate_delta < config.reward_hacking_acceptance_floor

    Args:
        run_id:                   Current run identifier.
        objective_id:             ObjectiveSpec identifier.
        current_score:            Score from the current run.
        previous_score:           Score from the previous run.
        human_acceptance_rate:    Current acceptance rate (None = skip check).
        previous_acceptance_rate: Previous acceptance rate (None = skip check).
        config:                   Guardrail configuration.
        occurred_at_utc:          Timestamp for alerts.

    Returns:
        RewardHackingAlert if detected, None otherwise.
    """
    if human_acceptance_rate is None or previous_acceptance_rate is None:
        # Cannot check without acceptance rate data
        return None

    correctness_improvement = (
        current_score.correctness - previous_score.correctness
    )

    if correctness_improvement <= config.reward_hacking_score_threshold:
        return None  # Not enough correctness improvement to trigger check

    acceptance_delta = human_acceptance_rate - previous_acceptance_rate

    if acceptance_delta <= config.reward_hacking_acceptance_floor:
        logger.warning(
            "Reward hacking detected (run=%s): correctness improved %.3f (> threshold=%.3f) "
            "but acceptance_rate_delta=%.3f (< floor=%.3f)",
            run_id,
            correctness_improvement,
            config.reward_hacking_score_threshold,
            acceptance_delta,
            config.reward_hacking_acceptance_floor,
        )
        return ModelRewardHackingAlert(
            run_id=run_id,
            objective_id=objective_id,
            score_improvement=correctness_improvement,
            acceptance_rate_delta=acceptance_delta,
            threshold=config.reward_hacking_score_threshold,
            occurred_at_utc=occurred_at_utc,
        )

    return None


def _symmetric_kl_divergence(
    p: dict[str, float], q: dict[str, float]
) -> float:
    """Compute symmetric KL-divergence between two probability distributions.

    Uses a simple approximation: 0.5 * (KL(p||q) + KL(q||p)).
    Both distributions are normalized to sum to 1.0.

    Args:
        p: Current distribution {source: value}.
        q: Baseline distribution {source: value}.

    Returns:
        Symmetric KL-divergence score (0.0 = identical).
    """
    # Get union of all keys
    all_keys = sorted(set(p.keys()) | set(q.keys()))

    # Normalize to proper distributions
    p_total = max(sum(p.values()), _KL_EPSILON)
    q_total = max(sum(q.values()), _KL_EPSILON)

    p_norm = {k: (p.get(k, 0.0) + _KL_EPSILON) / (p_total + len(all_keys) * _KL_EPSILON) for k in all_keys}
    q_norm = {k: (q.get(k, 0.0) + _KL_EPSILON) / (q_total + len(all_keys) * _KL_EPSILON) for k in all_keys}

    kl_pq = sum(p_norm[k] * math.log(p_norm[k] / q_norm[k]) for k in all_keys)
    kl_qp = sum(q_norm[k] * math.log(q_norm[k] / p_norm[k]) for k in all_keys)

    return 0.5 * (kl_pq + kl_qp)


def check_distributional_shift(
    run_id: str,
    objective_id: str,
    current_dist: dict[str, float] | None,
    baseline_dist: dict[str, float] | None,
    config: ModelGuardrailConfig,
    occurred_at_utc: str,
) -> ModelDistributionalShiftAlert | None:
    """Check for distributional shift in evidence sources.

    Computes KL-divergence between current and baseline distributions.
    Emits alert if divergence exceeds threshold.

    Args:
        run_id:          Current run identifier.
        objective_id:    ObjectiveSpec identifier.
        current_dist:    Current {source: value} distribution. None = skip.
        baseline_dist:   Baseline {source: value} distribution. None = skip.
        config:          Guardrail configuration.
        occurred_at_utc: Timestamp for alerts.

    Returns:
        DistributionalShiftAlert if drift detected, None otherwise.
    """
    if current_dist is None or baseline_dist is None or not baseline_dist:
        return None  # No baseline to compare against

    drift_score = _symmetric_kl_divergence(current_dist, baseline_dist)

    if drift_score <= config.drift_threshold:
        return None

    # Identify shifted sources (those with > 50% relative change)
    shifted: list[str] = []
    for source in current_dist:
        baseline_val = baseline_dist.get(source, 0.0)
        current_val = current_dist.get(source, 0.0)
        if baseline_val > 0:
            relative_change = abs(current_val - baseline_val) / (baseline_val + _KL_EPSILON)
            if relative_change > 0.5:
                shifted.append(source)
        elif current_val > 0:
            shifted.append(source)  # New source not in baseline

    logger.warning(
        "Distributional shift detected (run=%s): drift_score=%.4f > threshold=%.4f "
        "shifted_sources=%s",
        run_id,
        drift_score,
        config.drift_threshold,
        shifted,
    )
    return ModelDistributionalShiftAlert(
        run_id=run_id,
        objective_id=objective_id,
        drift_score=drift_score,
        threshold=config.drift_threshold,
        shifted_sources=tuple(sorted(shifted)),
        occurred_at_utc=occurred_at_utc,
    )


def check_diversity_constraint(
    run_id: str,
    objective_id: str,
    evidence_sources: tuple[str, ...],
    config: ModelGuardrailConfig,
    occurred_at_utc: str,
) -> ModelDiversityConstraintViolation | None:
    """Check that the evaluation uses at least N distinct evidence source types.

    This is a VETO check — if violated, the EvaluationResult must be rejected.

    Args:
        run_id:           Current run identifier.
        objective_id:     ObjectiveSpec identifier.
        evidence_sources: Distinct evidence source types in the current bundle.
        config:           Guardrail configuration.
        occurred_at_utc:  Timestamp for alerts.

    Returns:
        DiversityConstraintViolation if too few sources, None otherwise.
    """
    distinct_sources = set(evidence_sources)
    n = len(distinct_sources)

    if n >= config.min_evidence_sources:
        return None

    logger.warning(
        "Diversity constraint violation (run=%s): %d source types present, "
        "minimum required=%d",
        run_id,
        n,
        config.min_evidence_sources,
    )
    return ModelDiversityConstraintViolation(
        run_id=run_id,
        objective_id=objective_id,
        present_sources=tuple(sorted(distinct_sources)),
        required_min_sources=config.min_evidence_sources,
        occurred_at_utc=occurred_at_utc,
    )


def run_all_guardrails(input_data: ModelGuardrailInput) -> ModelGuardrailOutput:
    """Run all four anti-gaming guardrail checks.

    Evaluation order:
    1. Diversity constraint (veto — checked first)
    2. Goodhart's Law detection (non-blocking)
    3. Reward hacking detection (non-blocking)
    4. Distributional shift detection (non-blocking)

    Pure function: identical inputs → identical outputs.

    Args:
        input_data: Guardrail input with scores, distribution, and config.

    Returns:
        ModelGuardrailOutput with all detected alerts and veto flag.
    """
    now_utc = datetime.now(tz=timezone.utc).isoformat()
    config = input_data.config
    objective_id = config.objective_id

    # 1. Diversity constraint check (VETO)
    diversity_violation = check_diversity_constraint(
        run_id=input_data.run_id,
        objective_id=objective_id,
        evidence_sources=input_data.evidence_sources,
        config=config,
        occurred_at_utc=now_utc,
    )

    alerts: list[ModelAntiGamingAlertUnion] = []

    # 2–4 only run with previous score available
    if input_data.previous_score is not None:
        # 2. Goodhart's Law detection
        goodhart_alerts = check_goodhart_violation(
            run_id=input_data.run_id,
            objective_id=objective_id,
            current_score=input_data.current_score,
            previous_score=input_data.previous_score,
            config=config,
            occurred_at_utc=now_utc,
        )
        alerts.extend(goodhart_alerts)

        # 3. Reward hacking detection
        rh_alert = check_reward_hacking(
            run_id=input_data.run_id,
            objective_id=objective_id,
            current_score=input_data.current_score,
            previous_score=input_data.previous_score,
            human_acceptance_rate=input_data.human_acceptance_rate,
            previous_acceptance_rate=input_data.previous_acceptance_rate,
            config=config,
            occurred_at_utc=now_utc,
        )
        if rh_alert is not None:
            alerts.append(rh_alert)

    # 4. Distributional shift detection
    drift_alert = check_distributional_shift(
        run_id=input_data.run_id,
        objective_id=objective_id,
        current_dist=input_data.current_source_distribution,
        baseline_dist=input_data.baseline_source_distribution,
        config=config,
        occurred_at_utc=now_utc,
    )
    if drift_alert is not None:
        alerts.append(drift_alert)

    if alerts or diversity_violation:
        logger.info(
            "Guardrail check (run=%s): %d alert(s) raised, veto=%s",
            input_data.run_id,
            len(alerts),
            diversity_violation is not None,
        )

    return ModelGuardrailOutput(
        run_id=input_data.run_id,
        alerts=tuple(alerts),
        diversity_violation=diversity_violation,
    )


__all__ = [
    "check_distributional_shift",
    "check_diversity_constraint",
    "check_goodhart_violation",
    "check_reward_hacking",
    "run_all_guardrails",
]
