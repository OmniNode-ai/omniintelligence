# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reward signal scoring and pairing system metrics computation.

Implements the reward function and pairing metrics for the Review-Fix Pairing
system (Phase 4). Provides queryable signals for the OmniDash metrics pipeline.

Reward function (outcome → reward value):

    | Outcome                                  | Reward |
    |------------------------------------------|--------|
    | Violation avoided preemptively           | +1.0   |
    | Violation fixed deterministically via    | +0.8   |
    |   codemod                                |        |
    | Violation resolved manually              | +0.5   |
    | Reintroduced within 3 PRs                | -1.0   |
    | Agent repeatedly introduces same         | -2.0   |
    |   violation                              |        |

Pairing metrics:

    - paired_finding_rate: confirmed_pairs / total_findings per repo/window
    - avg_confidence_score: mean confidence across all pairs
    - p50_resolution_seconds: median time from observed to resolved
    - reintroduction_rate: reintroduced / total promoted patterns
    - autofix_pct: tool_autofix=True pairs / total pairs
    - preemptive_avoidance_rate: avoidance events / total injection events

Architecture:
    Pure computation — no Kafka, no Postgres, no HTTP in this module.
    Callers (Effect/Reducer nodes) handle all I/O.

Reference: OMN-2589
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reward function
# ---------------------------------------------------------------------------


@unique
class RewardOutcome(str, Enum):
    """Outcome type for a reward signal.

    Maps to the reward values defined in the design doc.
    """

    PREEMPTIVE_AVOIDANCE = "preemptive_avoidance"
    """Violation avoided because the pattern was injected preemptively. +1.0"""

    CODEMOD_FIX = "codemod_fix"
    """Violation fixed deterministically via a validated codemod. +0.8"""

    MANUAL_RESOLUTION = "manual_resolution"
    """Violation resolved manually by a developer. +0.5"""

    REINTRODUCED = "reintroduced"
    """Fix was reverted and the violation reappeared within 3 PRs. -1.0"""

    REPEATED_VIOLATION = "repeated_violation"
    """Agent repeatedly introduces the same violation despite injection. -2.0"""


# Reward mapping (frozen at module load)
_REWARD_MAP: dict[RewardOutcome, float] = {
    RewardOutcome.PREEMPTIVE_AVOIDANCE: 1.0,
    RewardOutcome.CODEMOD_FIX: 0.8,
    RewardOutcome.MANUAL_RESOLUTION: 0.5,
    RewardOutcome.REINTRODUCED: -1.0,
    RewardOutcome.REPEATED_VIOLATION: -2.0,
}


@dataclass(frozen=True)
class RewardScoringResult:
    """Result of scoring a single reward event.

    Attributes:
        signal_id: Unique identifier for this reward signal.
        outcome: The outcome type that triggered this reward.
        reward_value: Numeric reward in [-2.0, +1.0].
        agent_id: Agent that generated/fixed the violation (may be empty).
        repo: Repository slug where the outcome occurred.
        rule_id: Rule that was avoided, fixed, or violated.
        scored_at: UTC datetime of scoring.
    """

    signal_id: UUID
    outcome: RewardOutcome
    reward_value: float
    agent_id: str
    repo: str
    rule_id: str
    scored_at: datetime


class RewardScorer:
    """Pure reward scorer implementing the design doc's reward function.

    Usage::

        scorer = RewardScorer()
        result = scorer.score(
            outcome=RewardOutcome.PREEMPTIVE_AVOIDANCE,
            agent_id="claude-sonnet-4",
            repo="OmniNode-ai/omniintelligence",
            rule_id="ruff:E501",
        )
        assert result.reward_value == 1.0
    """

    def score(
        self,
        *,
        outcome: RewardOutcome,
        agent_id: str = "",
        repo: str = "",
        rule_id: str = "",
        signal_id: UUID | None = None,
    ) -> RewardScoringResult:
        """Score a single reward event.

        Args:
            outcome: The outcome that occurred.
            agent_id: Optional agent identifier.
            repo: Optional repository slug.
            rule_id: The rule associated with the event.
            signal_id: Optional pre-assigned signal ID.

        Returns:
            ``RewardScoringResult`` with the reward value.
        """
        reward_value = _REWARD_MAP[outcome]

        result = RewardScoringResult(
            signal_id=signal_id or uuid4(),
            outcome=outcome,
            reward_value=reward_value,
            agent_id=agent_id,
            repo=repo,
            rule_id=rule_id,
            scored_at=datetime.now(tz=UTC),
        )

        logger.debug(
            "RewardScorer.score: outcome=%s reward=%.1f agent=%s rule=%s",
            outcome.value,
            reward_value,
            agent_id or "<none>",
            rule_id,
        )

        return result

    def score_batch(
        self,
        events: list[dict],
    ) -> list[RewardScoringResult]:
        """Score a batch of reward events.

        Each dict must have keys: ``outcome`` (RewardOutcome or str value),
        and optionally ``agent_id``, ``repo``, ``rule_id``, ``signal_id``.

        Args:
            events: List of event dicts.

        Returns:
            List of ``RewardScoringResult`` instances.
        """
        results = []
        for event in events:
            outcome = event.get("outcome")
            if isinstance(outcome, str):
                try:
                    outcome = RewardOutcome(outcome)
                except ValueError:
                    logger.warning(
                        "RewardScorer.score_batch: invalid outcome value %r", outcome
                    )
                    continue
            if not isinstance(outcome, RewardOutcome):
                logger.warning("RewardScorer.score_batch: invalid outcome %r", outcome)
                continue

            results.append(
                self.score(
                    outcome=outcome,
                    agent_id=event.get("agent_id", ""),
                    repo=event.get("repo", ""),
                    rule_id=event.get("rule_id", ""),
                    signal_id=event.get("signal_id"),
                )
            )
        return results

    @staticmethod
    def reward_for(outcome: RewardOutcome) -> float:
        """Return the reward value for a given outcome.

        Args:
            outcome: The outcome type.

        Returns:
            Reward value in [-2.0, +1.0].
        """
        return _REWARD_MAP[outcome]


# ---------------------------------------------------------------------------
# Pairing metrics
# ---------------------------------------------------------------------------


@dataclass
class FindingRecord:
    """Minimal record for pairing metrics computation.

    Attributes:
        finding_id: UUID of the finding.
        repo: Repository slug.
        rule_id: Rule that was observed.
        observed_at: When the finding was first seen.
        has_confirmed_pair: Whether a confirmed pair exists for this finding.
        tool_autofix: Whether the associated fix was an autofix.
        confidence_score: Confidence of the associated pair (0.0 if no pair).
        resolved_at: When the finding was resolved (None if unresolved).
    """

    finding_id: UUID
    repo: str
    rule_id: str
    observed_at: datetime
    has_confirmed_pair: bool = False
    tool_autofix: bool = False
    confidence_score: float = 0.0
    resolved_at: datetime | None = None


@dataclass
class InjectionRecord:
    """Minimal record for injection metrics computation.

    Attributes:
        injection_id: UUID of the injection event.
        repo: Repository slug.
        had_avoidance: Whether at least one preemptive avoidance reward was
            emitted for this injection.
    """

    injection_id: UUID
    repo: str
    had_avoidance: bool = False


@dataclass(frozen=True)
class PairingMetricsSnapshot:
    """Computed pairing system metrics for a repo and time window.

    Attributes:
        repo: Repository slug (``"__all__"`` for workspace-wide metrics).
        window_days: Time window in days.
        paired_finding_rate: Fraction of findings with confirmed pairs.
        avg_confidence_score: Mean confidence score across confirmed pairs.
        p50_resolution_seconds: Median seconds from observed to resolved.
        reintroduction_rate: Fraction of promoted patterns reintroduced.
        autofix_pct: Fraction of pairs where fix was tool-generated.
        preemptive_avoidance_rate: Fraction of injections that produced avoidance.
        total_findings: Total findings in window.
        total_pairs: Total confirmed pairs in window.
        computed_at: UTC datetime of computation.
    """

    repo: str
    window_days: int
    paired_finding_rate: float
    avg_confidence_score: float
    p50_resolution_seconds: float
    reintroduction_rate: float
    autofix_pct: float
    preemptive_avoidance_rate: float
    total_findings: int
    total_pairs: int
    computed_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class PairingMetricsCalculator:
    """Computes pairing system metrics from finding and injection records.

    Pure computation — callers fetch records from Postgres and pass them in.

    Usage::

        calc = PairingMetricsCalculator()
        snapshot = calc.compute(
            findings=findings,
            injections=injections,
            promoted_patterns=10,
            reintroduced_patterns=2,
            repo="OmniNode-ai/omniintelligence",
            window_days=7,
        )
    """

    def compute(
        self,
        findings: list[FindingRecord],
        injections: list[InjectionRecord],
        *,
        promoted_patterns: int = 0,
        reintroduced_patterns: int = 0,
        repo: str = "__all__",
        window_days: int = 7,
    ) -> PairingMetricsSnapshot:
        """Compute a full metrics snapshot.

        Args:
            findings: All findings in the time window.
            injections: All injection events in the time window.
            promoted_patterns: Total number of patterns promoted in window.
            reintroduced_patterns: Number of promoted patterns reintroduced.
            repo: Repository slug to compute for (``"__all__"`` for all).
            window_days: Length of the time window in days.

        Returns:
            ``PairingMetricsSnapshot`` with all seven metrics.
        """
        # Filter by repo if specified
        if repo != "__all__":
            findings = [f for f in findings if f.repo == repo]
            injections = [i for i in injections if i.repo == repo]

        total_findings = len(findings)
        confirmed = [f for f in findings if f.has_confirmed_pair]
        total_pairs = len(confirmed)

        # 1. Paired finding rate
        paired_rate = total_pairs / total_findings if total_findings else 0.0

        # 2. Average confidence score (only confirmed pairs)
        if confirmed:
            avg_conf = statistics.mean(f.confidence_score for f in confirmed)
        else:
            avg_conf = 0.0

        # 3. P50 resolution seconds
        resolution_times = [
            (f.resolved_at - f.observed_at).total_seconds()
            for f in confirmed
            if f.resolved_at is not None
        ]
        p50_resolution = (
            statistics.median(resolution_times) if resolution_times else 0.0
        )

        # 4. Reintroduction rate
        if promoted_patterns > 0:
            reintroduction_rate = reintroduced_patterns / promoted_patterns
        else:
            reintroduction_rate = 0.0

        # 5. Autofix percentage
        if confirmed:
            autofix_pct = sum(1 for f in confirmed if f.tool_autofix) / total_pairs
        else:
            autofix_pct = 0.0

        # 6. Preemptive avoidance rate
        total_injections = len(injections)
        if total_injections > 0:
            avoidance_count = sum(1 for i in injections if i.had_avoidance)
            avoidance_rate = avoidance_count / total_injections
        else:
            avoidance_rate = 0.0

        snapshot = PairingMetricsSnapshot(
            repo=repo,
            window_days=window_days,
            paired_finding_rate=round(paired_rate, 6),
            avg_confidence_score=round(avg_conf, 6),
            p50_resolution_seconds=round(p50_resolution, 2),
            reintroduction_rate=round(reintroduction_rate, 6),
            autofix_pct=round(autofix_pct, 6),
            preemptive_avoidance_rate=round(avoidance_rate, 6),
            total_findings=total_findings,
            total_pairs=total_pairs,
        )

        logger.info(
            "PairingMetricsCalculator.compute: repo=%s window=%dd "
            "findings=%d pairs=%d pair_rate=%.3f avg_conf=%.3f",
            repo,
            window_days,
            total_findings,
            total_pairs,
            paired_rate,
            avg_conf,
        )

        return snapshot

    def cumulative_reward(
        self,
        results: list[RewardScoringResult],
        *,
        agent_id: str | None = None,
        repo: str | None = None,
        rule_id: str | None = None,
    ) -> float:
        """Compute cumulative reward across a set of scoring results.

        Optionally filter by agent_id, repo, or rule_id.

        Args:
            results: List of ``RewardScoringResult`` from the scorer.
            agent_id: Optional filter by agent.
            repo: Optional filter by repo.
            rule_id: Optional filter by rule.

        Returns:
            Sum of reward values across matching results.
        """
        filtered = results
        if agent_id is not None:
            filtered = [r for r in filtered if r.agent_id == agent_id]
        if repo is not None:
            filtered = [r for r in filtered if r.repo == repo]
        if rule_id is not None:
            filtered = [r for r in filtered if r.rule_id == rule_id]

        return sum(r.reward_value for r in filtered)
