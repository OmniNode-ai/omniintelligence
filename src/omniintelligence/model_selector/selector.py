# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelSelector — selects the best model and emits a DecisionRecord.

Every model selection call:
1. Evaluates all candidate models against constraints and scoring weights.
2. Constructs a DecisionRecord with full scoring breakdown.
3. Emits the DecisionRecord before returning (non-blocking).
4. Returns the selected candidate.

Design Decisions:
    - Emit synchronously before returning: the decision is a fact; emit
      must happen before caller receives result.
    - ``reproducibility_snapshot`` captures model registry state so the
      selection can be re-derived without live system state.
    - Non-blocking Kafka emission: follows ONEX hook pattern — emit via
      background channel, never block selection.
    - ``timestamp`` is injected by the caller — no ``datetime.now()`` defaults.

Ticket: OMN-2466
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from omniintelligence.model_selector.decision_emitter import (
    DecisionEmitter,
    DecisionEmitterBase,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateScore:
    """Per-candidate scoring result.

    Attributes:
        candidate: Model name/identifier.
        score: Aggregate score (0.0-1.0).
        breakdown: Per-metric scores contributing to the aggregate.
    """

    candidate: str
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for DecisionRecord storage."""
        return {
            "candidate": self.candidate,
            "score": self.score,
            "breakdown": self.breakdown,
        }


@dataclass(frozen=True)
class SelectionResult:
    """Result of a model selection operation.

    Attributes:
        selected_candidate: The winning model name.
        decision_id: UUID4 identifying this decision event.
        scores: Scores for all evaluated candidates.
        tie_breaker: Name of the tie-breaking rule applied (or None).
    """

    selected_candidate: str
    decision_id: str
    scores: list[CandidateScore]
    tie_breaker: str | None = None


# ---------------------------------------------------------------------------
# ModelSelector
# ---------------------------------------------------------------------------


class ModelSelector:
    """Selects the best model candidate and emits a DecisionRecord.

    This is the primary producer of DecisionRecord events. Every call to
    ``select()`` results in exactly one DecisionRecord emission.

    Scoring:
        Candidates are scored using weighted metrics. The selector applies
        constraints and scoring weights provided at construction time.

    Non-blocking Emission:
        DecisionRecord emission uses the injected ``DecisionEmitter``. The
        real emitter sends events via Kafka in a fire-and-forget manner.
        Emission failures are caught and logged — they never block the
        selection result.

    Reproducibility:
        The ``reproducibility_snapshot`` captures:
        - ``model_registry_version``: current registry version string
        - ``scoring_weights``: JSON-serialized weights used for scoring
        - ``active_constraints``: JSON-serialized constraint map
        - ``scoring_breakdown``: JSON-serialized per-candidate scores
        - ``selected_candidate``: recorded winner (for cross-check)

    Args:
        scoring_weights: Dict mapping metric name to float weight (0.0-1.0).
            Weights must sum to approximately 1.0.
        constraints: Dict mapping constraint name → reason string.
        model_registry_version: Opaque version identifier of the current
            model registry state. Defaults to ``"unknown"``.
        emitter: DecisionEmitter for event emission. Defaults to a new
            ``DecisionEmitter()`` (degraded mode with no Kafka publisher).
    """

    def __init__(
        self,
        *,
        scoring_weights: dict[str, float] | None = None,
        constraints: dict[str, str] | None = None,
        model_registry_version: str = "unknown",
        emitter: DecisionEmitterBase | None = None,
    ) -> None:
        """Initialize ModelSelector.

        Args:
            scoring_weights: Per-metric weights for scoring (default: equal weighting).
            constraints: Active constraints applied to all selections.
            model_registry_version: Registry version string for reproducibility.
            emitter: DecisionEmitter implementation (injected for testing).
        """
        self._scoring_weights: dict[str, float] = scoring_weights or {"default": 1.0}
        self._constraints: dict[str, str] = constraints or {}
        self._model_registry_version = model_registry_version
        self._emitter: DecisionEmitterBase = emitter or DecisionEmitter()

    def select(
        self,
        candidates: list[str],
        *,
        scores: dict[str, dict[str, float]],
        timestamp: datetime,
        decision_type: str = "model_select",
        agent_rationale: str | None = None,
        session_id: str | None = None,
    ) -> SelectionResult:
        """Select the best model candidate and emit a DecisionRecord.

        Emits the DecisionRecord before returning the result. Emission is
        non-blocking; failures are caught and logged.

        Args:
            candidates: List of candidate model names to evaluate.
            scores: Dict mapping candidate → metric_scores dict.
                Example: ``{"claude-3-opus": {"quality": 0.9, "cost": 0.8}}``.
            timestamp: Decision timestamp (injected by caller, no defaults).
            decision_type: Classification of this decision
                (e.g., ``"model_select"``).
            agent_rationale: Optional Layer 2 LLM rationale for this decision.
            session_id: Optional session context for correlation.

        Returns:
            SelectionResult with the selected candidate and decision metadata.

        Raises:
            ValueError: If ``candidates`` is empty.
        """
        if not candidates:
            msg = "ModelSelector.select() requires at least one candidate"
            raise ValueError(msg)

        # ------------------------------------------------------------------
        # Step 1: Score all candidates
        # ------------------------------------------------------------------
        scored = self._score_candidates(candidates, scores)

        # ------------------------------------------------------------------
        # Step 2: Select winner (highest aggregate score, tie-break if needed)
        # ------------------------------------------------------------------
        winner, tie_breaker = self._pick_winner(scored)

        # ------------------------------------------------------------------
        # Step 3: Build DecisionRecord
        # ------------------------------------------------------------------
        decision_id = str(uuid.uuid4())

        reproducibility_snapshot = self._build_snapshot(
            winner=winner,
            scored=scored,
        )

        record: dict[str, Any] = {
            "decision_id": decision_id,
            "decision_type": decision_type,
            "timestamp": timestamp.isoformat(),
            "candidates_considered": candidates,
            "constraints_applied": self._constraints,
            "scoring_breakdown": [s.to_dict() for s in scored],
            "tie_breaker": tie_breaker,
            "selected_candidate": winner,
            "agent_rationale": agent_rationale,
            "reproducibility_snapshot": reproducibility_snapshot,
            "session_id": session_id,
        }

        # ------------------------------------------------------------------
        # Step 4: Emit (non-blocking; failure must not prevent return)
        # ------------------------------------------------------------------
        emitted_at = datetime.now(UTC)
        try:
            self._emitter.emit(record, emitted_at)
        except Exception as exc:
            # fallback-ok: emission failure does not block selection
            logger.warning(
                "ModelSelector: emission failed (degraded mode). "
                "decision_id=%s error=%s",
                decision_id,
                exc,
            )

        # ------------------------------------------------------------------
        # Step 5: Return result
        # ------------------------------------------------------------------
        return SelectionResult(
            selected_candidate=winner,
            decision_id=decision_id,
            scores=scored,
            tie_breaker=tie_breaker,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _score_candidates(
        self,
        candidates: list[str],
        scores: dict[str, dict[str, float]],
    ) -> list[CandidateScore]:
        """Compute aggregate scores for all candidates.

        Args:
            candidates: All candidates to score.
            scores: Per-candidate per-metric scores.

        Returns:
            List of CandidateScore sorted descending by aggregate score.
        """
        result = []
        for candidate in candidates:
            metrics = scores.get(candidate, {})
            aggregate = self._compute_aggregate(metrics)
            result.append(
                CandidateScore(
                    candidate=candidate,
                    score=aggregate,
                    breakdown=dict(metrics),
                )
            )
        # Sort descending by score, then alphabetical for stability
        result.sort(key=lambda s: (-s.score, s.candidate))
        return result

    def _compute_aggregate(self, metrics: dict[str, float]) -> float:
        """Compute weighted aggregate score from per-metric values.

        Args:
            metrics: Metric name → score dict.

        Returns:
            Weighted aggregate score (0.0-1.0).
        """
        if not metrics:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        for metric, weight in self._scoring_weights.items():
            if metric in metrics:
                weighted_sum += metrics[metric] * weight
                total_weight += weight

        if total_weight == 0.0:
            # fallback-ok: no matching metrics → average all provided metrics
            return sum(metrics.values()) / len(metrics)

        return weighted_sum / total_weight

    def _pick_winner(
        self,
        scored: list[CandidateScore],
    ) -> tuple[str, str | None]:
        """Select the highest-scoring candidate.

        Args:
            scored: Candidates sorted descending by score.

        Returns:
            Tuple of (winner_name, tie_breaker_applied_or_None).
        """
        if not scored:
            msg = "No scored candidates to select from"
            raise ValueError(msg)

        best_score = scored[0].score
        top = [s for s in scored if abs(s.score - best_score) < 1e-9]

        if len(top) == 1:
            return top[0].candidate, None

        # Tie-break: alphabetical (deterministic, reproducible)
        winner = sorted(top, key=lambda s: s.candidate)[0]
        return winner.candidate, "alphabetical"

    def _build_snapshot(
        self,
        winner: str,
        scored: list[CandidateScore],
    ) -> dict[str, str]:
        """Build reproducibility_snapshot from current runtime state.

        The snapshot must contain sufficient state to re-derive the decision
        without live system state.

        Args:
            winner: The selected candidate name.
            scored: Full scoring breakdown.

        Returns:
            Dict[str, str] suitable for DecisionRecord.reproducibility_snapshot.
        """
        snapshot_scoring = [
            {"candidate": s.candidate, "score": s.score} for s in scored
        ]
        return {
            "model_registry_version": self._model_registry_version,
            "scoring_weights": json.dumps(self._scoring_weights),
            "active_constraints": json.dumps(list(self._constraints.keys())),
            "scoring_breakdown": json.dumps(snapshot_scoring),
            "selected_candidate": winner,
        }


__all__ = [
    "CandidateScore",
    "ModelSelector",
    "SelectionResult",
]
