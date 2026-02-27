# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ScoringReducer evaluation handler — deterministic gate + shaped reward.

This module implements the core algorithmic unit of the objective architecture.

Two-stage evaluation pipeline:
    Stage 1 — Hard gates:
        Iterate ``spec.gates`` in order. For each gate, look up the evidence
        item with ``item.source == gate.evidence_source`` and call
        ``gate.passes(item.value)``. If any gate fails, immediately return a
        failed EvaluationResult with all-zero ScoreVector and the failing gate
        IDs in ``failures``. Shaped terms are NOT evaluated.

    Stage 2 — Shaped reward (gates all passed):
        For each shaped term in ``spec.shaped_terms``:
        - Find the evidence item matching ``term.evidence_source``.
        - Apply direction: ``minimize`` inverts the value (1.0 - value).
        - Clamp to [0.0, 1.0].
        - Accumulate weighted contribution into the appropriate ScoreVector dim.
        - Record the contributing evidence item_id in attribution_refs.

Replay invariant:
    Identical (evidence, spec) inputs always produce bit-identical outputs.
    The handler has zero external I/O — no DB, no Kafka, no filesystem.

Ticket: OMN-2545
"""

from __future__ import annotations

import logging
from collections import defaultdict

from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evaluation_result import (
    ModelEvaluationResult,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evidence_bundle import (
    ModelEvidenceBundle,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
    ModelObjectiveSpec,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_score_vector import (
    ModelScoreVector,
)

logger = logging.getLogger(__name__)

# Valid ScoreVector dimension names
_SCORE_DIMENSIONS = frozenset(
    {"correctness", "safety", "cost", "latency", "maintainability", "human_time"}
)


def _build_evidence_index(
    evidence: ModelEvidenceBundle,
) -> dict[str, float]:
    """Build a source → value lookup from an EvidenceBundle.

    When multiple items share the same source key, the last one wins
    (deterministic for sorted inputs).

    Args:
        evidence: The evidence bundle to index.

    Returns:
        Mapping from evidence source key to normalized float value.
    """
    return {item.source: item.value for item in evidence.items}


def _build_evidence_item_index(
    evidence: ModelEvidenceBundle,
) -> dict[str, str]:
    """Build a source → item_id lookup from an EvidenceBundle.

    Used to populate attribution_refs with specific item IDs.

    Args:
        evidence: The evidence bundle to index.

    Returns:
        Mapping from evidence source key to item_id.
    """
    return {item.source: item.item_id for item in evidence.items}


def _clamp(value: float) -> float:
    """Clamp a float to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def evaluate_run(
    evidence: ModelEvidenceBundle,
    spec: ModelObjectiveSpec,
) -> ModelEvaluationResult:
    """Evaluate an EvidenceBundle against an ObjectiveSpec.

    Pure function — no side effects, no I/O. Identical inputs always produce
    bit-identical outputs (replay invariant).

    Stage 1 — Hard gates:
        All gates in ``spec.gates`` must pass. If any fail, returns a
        failed result immediately. Shaped terms are not evaluated.

    Stage 2 — Shaped reward:
        Only reached when all gates pass. Computes weighted sum contributions
        per ScoreVector dimension. Clamps all intermediate floats to [0.0, 1.0].

    Args:
        evidence: The evidence bundle from the agent run.
        spec:     The objective specification with gates and shaped terms.

    Returns:
        ModelEvaluationResult with passed flag, ScoreVector, failures, and
        attribution_refs.
    """
    evidence_values = _build_evidence_index(evidence)
    evidence_item_ids = _build_evidence_item_index(evidence)

    # =========================================================================
    # Stage 1 — Hard gates
    # =========================================================================
    failed_gates: list[str] = []

    for gate in spec.gates:
        evidence_value = evidence_values.get(gate.evidence_source)
        if evidence_value is None:
            # Missing evidence counts as gate failure
            logger.warning(
                "Gate '%s' references evidence source '%s' not present in bundle '%s'.",
                gate.id,
                gate.evidence_source,
                evidence.run_id,
            )
            failed_gates.append(gate.id)
            continue

        if not gate.passes(evidence_value):
            logger.debug(
                "Gate '%s' FAILED for run '%s': source='%s' value=%.4f threshold=%.4f",
                gate.id,
                evidence.run_id,
                gate.evidence_source,
                evidence_value,
                gate.threshold,
            )
            failed_gates.append(gate.id)

    if failed_gates:
        logger.info(
            "Run '%s' FAILED gates: %s (objective=%s)",
            evidence.run_id,
            failed_gates,
            spec.objective_id,
        )
        return ModelEvaluationResult(
            passed=False,
            score_vector=ModelScoreVector.zero(),
            failures=tuple(failed_gates),
            attribution_refs=(),
        )

    # =========================================================================
    # Stage 2 — Shaped reward (all gates passed)
    # =========================================================================
    # Accumulate weighted contributions per ScoreVector dimension
    dimension_scores: dict[str, float] = defaultdict(float)
    attribution_refs: list[str] = []

    for term in spec.shaped_terms:
        raw_value = evidence_values.get(term.evidence_source)
        if raw_value is None:
            # Missing evidence contributes 0 to this term
            logger.debug(
                "Shaped term '%s' references missing evidence source '%s' in bundle '%s'. "
                "Contributing 0.",
                term.id,
                term.evidence_source,
                evidence.run_id,
            )
            continue

        # Apply direction: minimize → invert value
        if term.direction == "minimize":
            adjusted = 1.0 - _clamp(raw_value)
        else:
            adjusted = _clamp(raw_value)

        contribution = _clamp(term.weight * adjusted)
        dimension_scores[term.score_dimension] += contribution

        # Record attribution only for non-zero contributions
        if contribution > 0.0:
            item_id = evidence_item_ids.get(term.evidence_source)
            if item_id is not None and item_id not in attribution_refs:
                attribution_refs.append(item_id)

        logger.debug(
            "Shaped term '%s' (dim=%s, dir=%s, weight=%.3f): "
            "raw=%.4f adjusted=%.4f contribution=%.4f",
            term.id,
            term.score_dimension,
            term.direction,
            term.weight,
            raw_value,
            adjusted,
            contribution,
        )

    # Clamp all dimension scores to [0.0, 1.0]
    clamped: dict[str, float] = {
        dim: _clamp(score) for dim, score in dimension_scores.items()
    }

    score_vector = ModelScoreVector(
        correctness=clamped.get("correctness", 0.0),
        safety=clamped.get("safety", 0.0),
        cost=clamped.get("cost", 0.0),
        latency=clamped.get("latency", 0.0),
        maintainability=clamped.get("maintainability", 0.0),
        human_time=clamped.get("human_time", 0.0),
    )

    logger.info(
        "Run '%s' PASSED all gates (objective=%s). "
        "ScoreVector: correctness=%.3f safety=%.3f cost=%.3f "
        "latency=%.3f maintainability=%.3f human_time=%.3f",
        evidence.run_id,
        spec.objective_id,
        score_vector.correctness,
        score_vector.safety,
        score_vector.cost,
        score_vector.latency,
        score_vector.maintainability,
        score_vector.human_time,
    )

    return ModelEvaluationResult(
        passed=True,
        score_vector=score_vector,
        failures=(),
        attribution_refs=tuple(attribution_refs),
    )


__all__ = ["evaluate_run"]
