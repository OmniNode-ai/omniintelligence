# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Replay verification for DecisionRecord provenance.

Given a stored ``reproducibility_snapshot``, the replay verifier re-derives the
decision outcome and confirms it matches the recorded ``selected_candidate``.

Design Decisions:
    - Replay does NOT require live model registry — uses snapshot state only.
    - Non-matching replay is logged as a provenance integrity event.
    - The replay algorithm uses the scoring breakdown from the snapshot to
      re-select the winner deterministically.

Replay Algorithm:
    1. Load scoring_breakdown from snapshot (serialized JSON).
    2. Find the candidate with the highest score.
    3. If tie: apply tie_breaker from snapshot.
    4. Compare replayed winner to recorded selected_candidate.

Ticket: OMN-2467
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from omniintelligence.decision_store.models import DecisionRecordRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ReplayResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayResult:
    """Result of replaying a DecisionRecord.

    Attributes:
        decision_id: ID of the replayed decision.
        original_candidate: Candidate recorded in the DecisionRecord.
        replayed_candidate: Candidate re-derived by the replay verifier.
        match: True if replayed == original.
        reason: Explanation of any mismatch (empty string if match=True).
        correlation_id: Trace correlation ID for end-to-end tracing.
    """

    decision_id: str
    original_candidate: str
    replayed_candidate: str | None
    match: bool
    reason: str = ""
    correlation_id: str | None = None

    def __str__(self) -> str:
        status = "MATCH" if self.match else "MISMATCH"
        return (
            f"ReplayResult({status}: decision_id={self.decision_id!r}, "
            f"original={self.original_candidate!r}, "
            f"replayed={self.replayed_candidate!r})"
        )


# ---------------------------------------------------------------------------
# Replay keys in reproducibility_snapshot
# ---------------------------------------------------------------------------

_SNAP_KEY_SCORING = "scoring_breakdown"
_SNAP_KEY_TIE_BREAKER = "tie_breaker"
_SNAP_KEY_CONSTRAINTS = "constraints_applied"
_SNAP_KEY_SELECTED = "selected_candidate"


# ---------------------------------------------------------------------------
# replay_decision
# ---------------------------------------------------------------------------


def replay_decision(
    record: DecisionRecordRow,
    *,
    correlation_id: str | None = None,
) -> ReplayResult:
    """Re-derive the decision outcome from the stored reproducibility_snapshot.

    The snapshot must contain sufficient state to re-derive the decision
    without live system state. Specifically:

    - ``scoring_breakdown``: JSON-serialized list of
      ``{"candidate": str, "score": float}`` objects.
    - ``tie_breaker`` (optional): Name of the tie-breaking rule.
    - ``selected_candidate`` (optional): Original candidate for cross-check.

    Args:
        record: The DecisionRecordRow to replay.
        correlation_id: Trace correlation ID for end-to-end tracing.

    Returns:
        ReplayResult indicating whether the replay matches the original decision.
    """
    snapshot = record.reproducibility_snapshot
    decision_id = record.decision_id
    original = record.selected_candidate

    # ------------------------------------------------------------------
    # Step 1: Extract scoring_breakdown from snapshot
    # ------------------------------------------------------------------
    scoring_raw = snapshot.get(_SNAP_KEY_SCORING)
    if not scoring_raw:
        # Fallback: use the stored scoring_breakdown from the record itself
        if record.scoring_breakdown:
            scoring_entries = [
                {"candidate": s.candidate, "score": s.score}
                for s in record.scoring_breakdown
            ]
        else:
            reason = (
                "Cannot replay: reproducibility_snapshot missing 'scoring_breakdown' "
                "and record has no scoring_breakdown entries."
            )
            logger.warning(
                "Replay failed for decision_id=%s: %s",
                decision_id,
                reason,
                extra={"correlation_id": correlation_id},
            )
            return ReplayResult(
                decision_id=decision_id,
                original_candidate=original,
                replayed_candidate=None,
                match=False,
                reason=reason,
                correlation_id=correlation_id,
            )
    else:
        # Parse scoring from snapshot — reproducibility_snapshot is dict[str, str],
        # so scoring_raw is always a string here.
        try:
            scoring_entries = json.loads(scoring_raw)
        except json.JSONDecodeError as exc:
            reason = f"Cannot replay: failed to parse scoring_breakdown JSON: {exc}"
            logger.warning(
                "Replay failed for decision_id=%s: %s",
                decision_id,
                reason,
                extra={"correlation_id": correlation_id},
            )
            return ReplayResult(
                decision_id=decision_id,
                original_candidate=original,
                replayed_candidate=None,
                match=False,
                reason=reason,
                correlation_id=correlation_id,
            )

    if not scoring_entries:
        reason = "Cannot replay: scoring_breakdown is empty."
        logger.warning(
            "Replay failed for decision_id=%s: %s",
            decision_id,
            reason,
            extra={"correlation_id": correlation_id},
        )
        return ReplayResult(
            decision_id=decision_id,
            original_candidate=original,
            replayed_candidate=None,
            match=False,
            reason=reason,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Step 2: Find the highest-scoring candidate
    # ------------------------------------------------------------------
    # scoring_entries is a list of dicts from JSON; annotate elements explicitly
    scoring_list: list[dict[str, object]] = scoring_entries  # any-ok: JSON-deserialized
    try:
        max_score = max(float(e["score"]) for e in scoring_list)  # type: ignore[arg-type]  # NOTE: JSON-deserialized data lacks static float typing; runtime checks/except guard ensure valid numeric 'score' values
    except (KeyError, TypeError, ValueError) as exc:
        reason = f"Cannot replay: malformed scoring entry: {exc}"
        logger.warning(
            "Replay failed for decision_id=%s: %s",
            decision_id,
            reason,
            extra={"correlation_id": correlation_id},
        )
        return ReplayResult(
            decision_id=decision_id,
            original_candidate=original,
            replayed_candidate=None,
            match=False,
            reason=reason,
            correlation_id=correlation_id,
        )

    top_candidates = [
        str(e["candidate"])
        for e in scoring_list
        if abs(float(e["score"]) - max_score) < 1e-9  # type: ignore[arg-type]  # NOTE: JSON-deserialized scores are untyped; try/except on max_score above guards against invalid values
    ]

    # ------------------------------------------------------------------
    # Step 3: Apply tie-breaker if multiple candidates at top score
    # ------------------------------------------------------------------
    if len(top_candidates) == 1:
        replayed = top_candidates[0]
    else:
        tie_breaker = snapshot.get(_SNAP_KEY_TIE_BREAKER) or record.tie_breaker
        replayed = _apply_tie_breaker(top_candidates, tie_breaker)
        logger.debug(
            "Replay applied tie-breaker=%r for decision_id=%s. candidates=%s replayed=%s",
            tie_breaker,
            decision_id,
            top_candidates,
            replayed,
            extra={"correlation_id": correlation_id},
        )

    # ------------------------------------------------------------------
    # Step 4: Compare replayed vs original
    # ------------------------------------------------------------------
    match = replayed == original

    if not match:
        logger.warning(
            "Provenance integrity: replay mismatch for decision_id=%s. "
            "original=%r replayed=%r",
            decision_id,
            original,
            replayed,
            extra={"correlation_id": correlation_id},
        )
        return ReplayResult(
            decision_id=decision_id,
            original_candidate=original,
            replayed_candidate=replayed,
            match=False,
            reason=(
                f"Replay selected {replayed!r} but original decision was {original!r}. "
                "Provenance integrity check FAILED."
            ),
            correlation_id=correlation_id,
        )

    logger.debug(
        "Replay verified successfully. decision_id=%s candidate=%r",
        decision_id,
        replayed,
        extra={"correlation_id": correlation_id},
    )
    return ReplayResult(
        decision_id=decision_id,
        original_candidate=original,
        replayed_candidate=replayed,
        match=True,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Tie-breaker logic
# ---------------------------------------------------------------------------


def _apply_tie_breaker(candidates: list[str], tie_breaker: str | None) -> str:
    """Apply tie-breaking rule to select from equally-scored candidates.

    Supported tie-breaker rules:
    - ``"alphabetical"`` (default): Pick lexicographically first candidate.
    - ``"first"`` or None: Pick the first candidate in list order.
    - Any other value: Fall back to alphabetical with a warning.

    Args:
        candidates: List of candidate names with equal top score.
        tie_breaker: Name of the tie-breaking rule.

    Returns:
        The selected candidate name.
    """
    if not candidates:
        msg = "No candidates to break tie between"
        raise ValueError(msg)

    if tie_breaker is None or tie_breaker in ("first", ""):
        return candidates[0]

    if tie_breaker == "alphabetical":
        return sorted(candidates)[0]

    # fallback-ok: unknown tie-breaker, use alphabetical for determinism
    logger.warning(
        "Unknown tie_breaker=%r, falling back to alphabetical sort.",
        tie_breaker,
    )
    return sorted(candidates)[0]


__all__ = [
    "ReplayResult",
    "replay_decision",
]
