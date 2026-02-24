# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern Candidate Reducer: cluster, promote, and lifecycle state machine.

Aggregates confirmed ``FindingFixPair`` records into pattern candidates,
evaluates promotion gates, and drives the full pattern lifecycle state machine:

    CANDIDATE → VALIDATED → PROMOTED → STABLE → DECAYING → DEPRECATED

Core invariants:
    - No promotion without ``disappearance_confirmed=True`` on all pairs.
    - State transitions are deterministic given the same input sequence.
    - Deprecated patterns are retained for anti-pattern validator generation.

Promotion Gates (CANDIDATE → VALIDATED):
    1. Occurred ≥ N times (default N=3, configurable via ``MIN_OCCURRENCES``).
    2. Fix transform convergence: edit distance similarity ≥ 0.85 across pairs.
    3. All contributing pairs have ``disappearance_confirmed=True``.
    4. Reintroduction rate < 0.2.
    5. Tool version stability: same ``tool_version`` across ≥ 80% of pairs.

State Transitions:
    CANDIDATE → VALIDATED   Promotion gates pass.
    VALIDATED → PROMOTED    Acceptance suite passes + replay regression clean.
    PROMOTED  → STABLE      No reintroduction over configurable time window.
    STABLE    → DECAYING    score *= decay_factor per window without recurrence.
    DECAYING  → DEPRECATED  Score drops below minimum threshold.
    Any state → DEPRECATED  Oscillation threshold exceeded or AI-only demotion.

Architecture:
    Pure computation — no Kafka, no Postgres, no Qdrant.
    Callers (Effect/Reducer nodes) handle all I/O and event emission.

Reference: OMN-2568
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, unique
from uuid import UUID, uuid4

from omniintelligence.review_pairing.models import FindingFixPair

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (environment-variable overridable)
# ---------------------------------------------------------------------------

MIN_OCCURRENCES: int = int(os.getenv("PATTERN_MIN_OCCURRENCES", "3"))
"""Minimum number of confirmed pairs before promotion evaluation."""

TRANSFORM_SIMILARITY_THRESHOLD: float = float(
    os.getenv("PATTERN_TRANSFORM_SIMILARITY", "0.85")
)
"""Minimum edit-distance similarity (0-1) for transform convergence."""

MAX_REINTRODUCTION_RATE: float = float(
    os.getenv("PATTERN_MAX_REINTRODUCTION_RATE", "0.20")
)
"""Maximum fraction of fixes that are reverted before VALIDATED gate fails."""

TOOL_VERSION_STABILITY: float = float(
    os.getenv("PATTERN_TOOL_VERSION_STABILITY", "0.80")
)
"""Fraction of pairs that must share the majority tool_version."""

STABLE_WINDOW_DAYS: int = int(os.getenv("PATTERN_STABLE_WINDOW_DAYS", "30"))
"""Days without reintroduction to transition PROMOTED → STABLE."""

DECAY_FACTOR: float = float(os.getenv("PATTERN_DECAY_FACTOR", "0.90"))
"""Multiplicative score decay per window without recurrence (STABLE → DECAYING)."""

MIN_SCORE_THRESHOLD: float = float(os.getenv("PATTERN_MIN_SCORE", "0.10"))
"""Score below which DECAYING → DEPRECATED transition fires."""

MAX_OSCILLATIONS: int = int(os.getenv("PATTERN_MAX_OSCILLATIONS", "3"))
"""Oscillation count (reintroduced then fixed again) above which → DEPRECATED."""


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@unique
class PatternLifecycleState(str, Enum):
    """State machine states for a pattern candidate.

    Transitions (happy path):
        CANDIDATE → VALIDATED → PROMOTED → STABLE → DECAYING → DEPRECATED

    Fast-path demotion (any state → DEPRECATED):
        - Oscillation threshold exceeded.
        - AI-only pattern without acceptance suite passage.
    """

    CANDIDATE = "candidate"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    STABLE = "stable"
    DECAYING = "decaying"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class PatternClusterKey:
    """Immutable AST cluster key that groups related findings.

    Findings with the same ``(rule_id, node_type, parent_node_type)`` are
    assumed to share a common structural cause and are clustered together.

    Attributes:
        rule_id: Canonical rule identifier (e.g. ``ruff:E501``).
        node_type: AST node type of the flagged construct (e.g. ``FunctionDef``).
            Use ``"unknown"`` when AST context is not available.
        parent_node_type: Parent AST node type (e.g. ``ClassDef``).
            Use ``"unknown"`` when AST context is not available.
    """

    rule_id: str
    node_type: str = "unknown"
    parent_node_type: str = "unknown"

    def __str__(self) -> str:
        return f"{self.rule_id}|{self.node_type}|{self.parent_node_type}"


@dataclass
class PromotionGateResult:
    """Result of evaluating promotion gates for a pattern cluster.

    Attributes:
        passed: Whether all gates passed (cluster is ready for VALIDATED).
        gate_name: Name of the gate that blocked promotion (empty if passed).
        gate_detail: Human-readable detail on why the gate failed.
        occurrence_count: Number of confirmed pairs in the cluster.
        similarity_score: Edit-distance similarity across diff transforms.
        reintroduction_rate: Fraction of reverted fixes.
        tool_version_stability: Fraction sharing majority tool_version.
    """

    passed: bool
    gate_name: str = ""
    gate_detail: str = ""
    occurrence_count: int = 0
    similarity_score: float = 0.0
    reintroduction_rate: float = 0.0
    tool_version_stability: float = 0.0


@dataclass
class PatternCandidate:
    """Mutable in-memory representation of a pattern candidate cluster.

    One ``PatternCandidate`` exists per ``PatternClusterKey``. It accumulates
    confirmed pairs, tracks lifecycle state, and carries scoring metadata.

    Attributes:
        candidate_id: Globally unique identifier for this candidate.
        cluster_key: The AST cluster key that defines this pattern.
        state: Current lifecycle state.
        confirmed_pairs: List of confirmed ``FindingFixPair`` records.
        reintroduced_pair_ids: Set of pair_ids that were reintroduced (reverted).
        pattern_score: Running quality score in [0.0, 1.0].
        transform_signature: Convergent diff transform string (set on VALIDATED).
        oscillation_count: How many times this pattern was reintroduced and fixed.
        created_at: UTC datetime when the first pair was added.
        last_recurrence_at: UTC datetime of the most recent confirmed pair.
        promoted_at: UTC datetime of PROMOTED transition (``None`` if not promoted).
        validated_at: UTC datetime of VALIDATED transition.
        deprecated_at: UTC datetime of DEPRECATED transition.
        state_history: Ordered list of ``(state, datetime, reason)`` tuples.
    """

    candidate_id: UUID = field(default_factory=uuid4)
    cluster_key: PatternClusterKey = field(
        default_factory=lambda: PatternClusterKey(rule_id="unknown")
    )
    state: PatternLifecycleState = PatternLifecycleState.CANDIDATE
    confirmed_pairs: list[FindingFixPair] = field(default_factory=list)
    reintroduced_pair_ids: set[UUID] = field(default_factory=set)
    pattern_score: float = 1.0
    transform_signature: str = ""
    oscillation_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    last_recurrence_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    promoted_at: datetime | None = None
    validated_at: datetime | None = None
    deprecated_at: datetime | None = None
    state_history: list[tuple[PatternLifecycleState, datetime, str]] = field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Similarity helpers (pure)
# ---------------------------------------------------------------------------


def _normalize_diff(diff: str) -> str:
    """Normalise a diff hunk string for similarity comparison.

    Strips leading +/- markers and whitespace for token-level comparison.
    """
    lines = []
    for line in diff.splitlines():
        stripped = line.lstrip("+-").strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def _edit_similarity(a: str, b: str) -> float:
    """Compute normalised edit-distance similarity between two strings.

    Returns a value in [0.0, 1.0] where 1.0 = identical.

    Uses the standard Wagner-Fischer dynamic-programming algorithm.
    """
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0

    # Work on characters; truncate very long strings to cap runtime
    MAX = 2000
    a = a[:MAX]
    b = b[:MAX]

    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            if ca == cb:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr

    distance = prev[lb]
    return 1.0 - distance / max(la, lb)


def _transform_similarity(pairs: list[FindingFixPair]) -> float:
    """Compute average pairwise edit-distance similarity of diff transforms.

    Uses the concatenated diff hunks from each pair as the transform
    representation. Returns 1.0 for a single pair (trivially convergent).

    Args:
        pairs: Confirmed ``FindingFixPair`` records in the cluster.

    Returns:
        Average similarity in [0.0, 1.0].
    """
    if len(pairs) <= 1:
        return 1.0

    normalized = [_normalize_diff("\n".join(p.diff_hunks)) for p in pairs]

    total, count = 0.0, 0
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            total += _edit_similarity(normalized[i], normalized[j])
            count += 1

    return total / count if count else 1.0


def _tool_version_stability(pairs: list[FindingFixPair]) -> float:
    """Compute fraction of pairs sharing the majority tool_version.

    Args:
        pairs: Confirmed ``FindingFixPair`` records.

    Returns:
        Fraction in [0.0, 1.0].
    """
    if not pairs:
        return 1.0

    # tool_version lives on the finding; pairs store finding_id only.
    # The reducer receives tool_version separately via pair metadata.
    # Here we use the pair's diff_hunks as a proxy — in production the
    # caller enriches pairs with a tool_version attribute via the pairing DB.
    # For the stateless computation, we accept tool_versions as an external list.
    # This function is therefore a placeholder that always returns 1.0 when
    # called without version context. The full integration passes version_map.
    return 1.0  # Overridden by evaluate_promotion_gates when version_map provided


# ---------------------------------------------------------------------------
# Main reducer class
# ---------------------------------------------------------------------------


class PatternCandidateReducer:
    """Stateless pattern candidate reducer for the Review-Fix Pairing system.

    Manages the full lifecycle state machine for pattern candidates.
    All state is stored in ``PatternCandidate`` dataclass instances; the
    reducer itself has no mutable state.

    Usage::

        reducer = PatternCandidateReducer()

        # Add a confirmed pair to a cluster
        candidate = reducer.ingest_pair(
            candidate=candidate,
            pair=confirmed_pair,
            cluster_key=PatternClusterKey(rule_id="ruff:E501"),
        )

        # Drive the state machine
        candidate = reducer.tick(candidate)
        if candidate.state == PatternLifecycleState.PROMOTED:
            # Emit pattern-promoted.v1 event
            ...
    """

    # -----------------------------------------------------------------------
    # Ingestion
    # -----------------------------------------------------------------------

    def ingest_pair(
        self,
        candidate: PatternCandidate,
        pair: FindingFixPair,
        *,
        cluster_key: PatternClusterKey | None = None,
    ) -> PatternCandidate:
        """Add a confirmed ``FindingFixPair`` to a pattern cluster.

        Args:
            candidate: The ``PatternCandidate`` to update.
            pair: A confirmed ``FindingFixPair`` (``disappearance_confirmed=True``).
            cluster_key: Optional override for the cluster key.

        Returns:
            Updated ``PatternCandidate`` (mutated in place and returned).

        Raises:
            ValueError: If ``pair.disappearance_confirmed`` is ``False``.
        """
        if not pair.disappearance_confirmed:
            raise ValueError(
                f"pair {pair.pair_id} must have disappearance_confirmed=True "
                "before ingestion into the pattern reducer"
            )

        candidate.confirmed_pairs.append(pair)
        candidate.last_recurrence_at = datetime.now(tz=UTC)

        if cluster_key is not None:
            object.__setattr__(candidate, "cluster_key", cluster_key)

        logger.debug(
            "PatternCandidateReducer.ingest_pair: candidate=%s pair=%s total=%d",
            candidate.candidate_id,
            pair.pair_id,
            len(candidate.confirmed_pairs),
        )
        return candidate

    def mark_reintroduced(
        self,
        candidate: PatternCandidate,
        pair_id: UUID,
    ) -> PatternCandidate:
        """Mark a pair as reintroduced (fix was reverted).

        Increments oscillation_count and adds pair_id to reintroduced set.

        Args:
            candidate: The ``PatternCandidate`` to update.
            pair_id: UUID of the pair whose fix was reverted.

        Returns:
            Updated ``PatternCandidate``.
        """
        candidate.reintroduced_pair_ids.add(pair_id)
        candidate.oscillation_count += 1

        logger.info(
            "PatternCandidateReducer.mark_reintroduced: candidate=%s oscillations=%d",
            candidate.candidate_id,
            candidate.oscillation_count,
        )
        return candidate

    # -----------------------------------------------------------------------
    # Promotion gate evaluation
    # -----------------------------------------------------------------------

    def evaluate_promotion_gates(
        self,
        candidate: PatternCandidate,
        *,
        tool_version_map: dict[UUID, str] | None = None,
    ) -> PromotionGateResult:
        """Evaluate all promotion gates for a CANDIDATE cluster.

        Args:
            candidate: The cluster to evaluate.
            tool_version_map: Optional mapping of pair_id → tool_version string.
                When provided, used for tool version stability computation.

        Returns:
            ``PromotionGateResult`` describing which gate passed/failed.
        """
        pairs = candidate.confirmed_pairs
        occurrence_count = len(pairs)

        # Gate 1: minimum occurrences
        if occurrence_count < MIN_OCCURRENCES:
            return PromotionGateResult(
                passed=False,
                gate_name="min_occurrences",
                gate_detail=(
                    f"only {occurrence_count} confirmed pairs; need ≥ {MIN_OCCURRENCES}"
                ),
                occurrence_count=occurrence_count,
            )

        # Gate 2: all pairs must have disappearance_confirmed=True
        # (enforced at ingest but verified here for safety)
        unconfirmed = [p for p in pairs if not p.disappearance_confirmed]
        if unconfirmed:
            return PromotionGateResult(
                passed=False,
                gate_name="disappearance_confirmed",
                gate_detail=(
                    f"{len(unconfirmed)} pairs missing disappearance_confirmed"
                ),
                occurrence_count=occurrence_count,
            )

        # Gate 3: transform convergence
        similarity = _transform_similarity(pairs)
        if similarity < TRANSFORM_SIMILARITY_THRESHOLD:
            return PromotionGateResult(
                passed=False,
                gate_name="transform_convergence",
                gate_detail=(
                    f"similarity={similarity:.3f} below threshold "
                    f"{TRANSFORM_SIMILARITY_THRESHOLD}"
                ),
                occurrence_count=occurrence_count,
                similarity_score=similarity,
            )

        # Gate 4: reintroduction rate
        reintroduction_rate = (
            len(candidate.reintroduced_pair_ids) / occurrence_count
            if occurrence_count
            else 0.0
        )
        if reintroduction_rate >= MAX_REINTRODUCTION_RATE:
            return PromotionGateResult(
                passed=False,
                gate_name="reintroduction_rate",
                gate_detail=(
                    f"reintroduction_rate={reintroduction_rate:.3f} ≥ "
                    f"{MAX_REINTRODUCTION_RATE}"
                ),
                occurrence_count=occurrence_count,
                similarity_score=similarity,
                reintroduction_rate=reintroduction_rate,
            )

        # Gate 5: tool version stability
        if tool_version_map:
            versions = [tool_version_map.get(p.pair_id, "unknown") for p in pairs]
            if versions:
                from collections import Counter

                counts = Counter(versions)
                majority_count = counts.most_common(1)[0][1]
                version_stability = majority_count / len(versions)
            else:
                version_stability = 1.0
        else:
            version_stability = 1.0

        if version_stability < TOOL_VERSION_STABILITY:
            return PromotionGateResult(
                passed=False,
                gate_name="tool_version_stability",
                gate_detail=(
                    f"version_stability={version_stability:.3f} below "
                    f"{TOOL_VERSION_STABILITY}"
                ),
                occurrence_count=occurrence_count,
                similarity_score=similarity,
                reintroduction_rate=reintroduction_rate,
                tool_version_stability=version_stability,
            )

        return PromotionGateResult(
            passed=True,
            occurrence_count=occurrence_count,
            similarity_score=similarity,
            reintroduction_rate=reintroduction_rate,
            tool_version_stability=version_stability,
        )

    # -----------------------------------------------------------------------
    # State transitions
    # -----------------------------------------------------------------------

    def _transition(
        self,
        candidate: PatternCandidate,
        new_state: PatternLifecycleState,
        reason: str,
    ) -> PatternCandidate:
        """Apply a state transition and record it in state_history."""
        now = datetime.now(tz=UTC)
        old_state = candidate.state
        candidate.state = new_state
        candidate.state_history.append((new_state, now, reason))

        logger.info(
            "PatternCandidateReducer: candidate=%s %s → %s [%s]",
            candidate.candidate_id,
            old_state.value,
            new_state.value,
            reason,
        )
        return candidate

    def try_validate(
        self,
        candidate: PatternCandidate,
        *,
        tool_version_map: dict[UUID, str] | None = None,
    ) -> tuple[PatternCandidate, PromotionGateResult]:
        """Attempt CANDIDATE → VALIDATED transition.

        Args:
            candidate: Must be in CANDIDATE state.
            tool_version_map: Optional pair_id → tool_version mapping.

        Returns:
            ``(updated_candidate, gate_result)`` tuple.
        """
        if candidate.state != PatternLifecycleState.CANDIDATE:
            return candidate, PromotionGateResult(
                passed=False,
                gate_name="wrong_state",
                gate_detail=f"expected CANDIDATE, got {candidate.state.value}",
            )

        gate_result = self.evaluate_promotion_gates(
            candidate, tool_version_map=tool_version_map
        )
        if not gate_result.passed:
            return candidate, gate_result

        # Compute and store transform signature
        pairs = candidate.confirmed_pairs
        candidate.transform_signature = _normalize_diff(
            "\n".join(pairs[0].diff_hunks) if pairs else ""
        )
        candidate.validated_at = datetime.now(tz=UTC)

        candidate = self._transition(
            candidate,
            PatternLifecycleState.VALIDATED,
            "all promotion gates passed",
        )
        return candidate, gate_result

    def promote(
        self,
        candidate: PatternCandidate,
        *,
        acceptance_passed: bool,
        replay_clean: bool,
    ) -> PatternCandidate:
        """Attempt VALIDATED → PROMOTED transition.

        Args:
            candidate: Must be in VALIDATED state.
            acceptance_passed: Whether the acceptance suite passed.
            replay_clean: Whether the replay regression check passed.

        Returns:
            Updated ``PatternCandidate``.
        """
        if candidate.state != PatternLifecycleState.VALIDATED:
            logger.warning(
                "promote called on candidate=%s in state=%s (expected VALIDATED)",
                candidate.candidate_id,
                candidate.state.value,
            )
            return candidate

        if not acceptance_passed:
            return self._transition(
                candidate,
                PatternLifecycleState.DEPRECATED,
                "acceptance suite failed — AI-only demotion path",
            )

        if not replay_clean:
            return self._transition(
                candidate,
                PatternLifecycleState.DEPRECATED,
                "replay regression failed",
            )

        candidate.promoted_at = datetime.now(tz=UTC)
        return self._transition(
            candidate,
            PatternLifecycleState.PROMOTED,
            "acceptance suite + replay regression passed",
        )

    def stabilize(
        self,
        candidate: PatternCandidate,
    ) -> PatternCandidate:
        """Attempt PROMOTED → STABLE transition.

        Transitions if no reintroduction has occurred within STABLE_WINDOW_DAYS.

        Args:
            candidate: Must be in PROMOTED state.

        Returns:
            Updated ``PatternCandidate``.
        """
        if candidate.state != PatternLifecycleState.PROMOTED:
            return candidate

        if candidate.promoted_at is None:
            return candidate

        window = timedelta(days=STABLE_WINDOW_DAYS)
        elapsed = datetime.now(tz=UTC) - candidate.promoted_at

        if elapsed < window:
            return candidate  # Not enough time has passed

        # Check for reintroductions since promotion
        recent_reintroductions = len(candidate.reintroduced_pair_ids)
        if recent_reintroductions > 0:
            return candidate  # Still seeing reintroductions

        return self._transition(
            candidate,
            PatternLifecycleState.STABLE,
            f"no reintroductions over {STABLE_WINDOW_DAYS}-day window",
        )

    def apply_decay(
        self,
        candidate: PatternCandidate,
        *,
        recurrence_observed: bool = False,
    ) -> PatternCandidate:
        """Apply decay to a STABLE pattern.

        If no recurrence was observed in the current window, apply decay factor.
        If score drops below minimum threshold, transition to DEPRECATED.

        Args:
            candidate: Must be in STABLE or DECAYING state.
            recurrence_observed: Whether a new confirmed pair was observed
                in the current window.

        Returns:
            Updated ``PatternCandidate``.
        """
        if candidate.state not in (
            PatternLifecycleState.STABLE,
            PatternLifecycleState.DECAYING,
        ):
            return candidate

        if recurrence_observed:
            # Recurrence resets decay — no score change
            candidate.last_recurrence_at = datetime.now(tz=UTC)
            return candidate

        # Apply decay
        old_score = candidate.pattern_score
        candidate.pattern_score = round(old_score * DECAY_FACTOR, 6)

        logger.debug(
            "PatternCandidateReducer.apply_decay: candidate=%s score %.4f → %.4f",
            candidate.candidate_id,
            old_score,
            candidate.pattern_score,
        )

        if candidate.state == PatternLifecycleState.STABLE:
            candidate = self._transition(
                candidate,
                PatternLifecycleState.DECAYING,
                f"score decayed from {old_score:.4f} to {candidate.pattern_score:.4f}",
            )

        if candidate.pattern_score < MIN_SCORE_THRESHOLD:
            candidate.deprecated_at = datetime.now(tz=UTC)
            return self._transition(
                candidate,
                PatternLifecycleState.DEPRECATED,
                f"score {candidate.pattern_score:.4f} below minimum {MIN_SCORE_THRESHOLD}",
            )

        return candidate

    def deprecate(
        self,
        candidate: PatternCandidate,
        reason: str,
    ) -> PatternCandidate:
        """Fast-path deprecation from any state.

        Used for oscillation threshold exceeded or manual deprecation.

        Args:
            candidate: Any state.
            reason: Human-readable deprecation reason.

        Returns:
            Updated ``PatternCandidate`` in DEPRECATED state.
        """
        candidate.deprecated_at = datetime.now(tz=UTC)
        return self._transition(candidate, PatternLifecycleState.DEPRECATED, reason)

    # -----------------------------------------------------------------------
    # Unified tick (convenience driver)
    # -----------------------------------------------------------------------

    def tick(
        self,
        candidate: PatternCandidate,
        *,
        acceptance_passed: bool = True,
        replay_clean: bool = True,
        recurrence_observed: bool = False,
        tool_version_map: dict[UUID, str] | None = None,
    ) -> PatternCandidate:
        """Drive the state machine forward by one tick.

        Applies the appropriate transition based on current state:
            CANDIDATE   → try_validate
            VALIDATED   → promote
            PROMOTED    → stabilize
            STABLE      → apply_decay
            DECAYING    → apply_decay
            DEPRECATED  → no-op

        Also applies fast-path deprecation if oscillation threshold exceeded.

        Args:
            candidate: The candidate to advance.
            acceptance_passed: Required for VALIDATED → PROMOTED.
            replay_clean: Required for VALIDATED → PROMOTED.
            recurrence_observed: Whether a new pair was observed (for decay).
            tool_version_map: Optional pair_id → tool_version for gate 5.

        Returns:
            Updated ``PatternCandidate``.
        """
        # Fast-path: oscillation check (any state)
        if candidate.oscillation_count >= MAX_OSCILLATIONS:
            if candidate.state != PatternLifecycleState.DEPRECATED:
                return self.deprecate(
                    candidate,
                    f"oscillation_count={candidate.oscillation_count} ≥ {MAX_OSCILLATIONS}",
                )

        state = candidate.state

        if state == PatternLifecycleState.CANDIDATE:
            candidate, _ = self.try_validate(
                candidate, tool_version_map=tool_version_map
            )

        elif state == PatternLifecycleState.VALIDATED:
            candidate = self.promote(
                candidate,
                acceptance_passed=acceptance_passed,
                replay_clean=replay_clean,
            )

        elif state == PatternLifecycleState.PROMOTED:
            candidate = self.stabilize(candidate)

        elif state in (
            PatternLifecycleState.STABLE,
            PatternLifecycleState.DECAYING,
        ):
            candidate = self.apply_decay(
                candidate, recurrence_observed=recurrence_observed
            )

        # DEPRECATED is terminal — no-op

        return candidate

    # -----------------------------------------------------------------------
    # Factory
    # -----------------------------------------------------------------------

    @staticmethod
    def new_candidate(
        cluster_key: PatternClusterKey,
        initial_pair: FindingFixPair | None = None,
    ) -> PatternCandidate:
        """Create a new ``PatternCandidate`` for a cluster.

        Args:
            cluster_key: The AST cluster key for this candidate.
            initial_pair: Optional first confirmed pair to add immediately.

        Returns:
            A new ``PatternCandidate`` in CANDIDATE state.
        """
        candidate = PatternCandidate(
            candidate_id=uuid4(),
            cluster_key=cluster_key,
        )
        candidate.state_history.append(
            (PatternLifecycleState.CANDIDATE, candidate.created_at, "created")
        )

        if initial_pair is not None:
            if not initial_pair.disappearance_confirmed:
                raise ValueError(
                    f"initial_pair {initial_pair.pair_id} must have "
                    "disappearance_confirmed=True"
                )
            candidate.confirmed_pairs.append(initial_pair)

        return candidate
