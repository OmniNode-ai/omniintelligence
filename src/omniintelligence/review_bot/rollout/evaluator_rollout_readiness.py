"""Rollout readiness evaluator for the Code Intelligence Review Bot.

Computes advisory readiness signals to inform human graduation decisions
from OBSERVE -> WARN -> BLOCK. Signals are advisory only; no auto-promotion.

OMN-2500: Implement OBSERVE -> WARN -> BLOCK rollout progression.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omniintelligence.review_bot.rollout.model_enforcement_mode import EnforcementMode

# Advisory thresholds for readiness signals
FALSE_POSITIVE_RATE_THRESHOLD: float = 0.20  # < 20% false positive rate
MIN_PRS_REVIEWED_IN_WARN: int = 10  # At least 10 PRs in WARN mode
MIN_CLEAN_MERGED_PRS: int = 5  # No BLOCKERs in last 5 merged PRs


@dataclass
class ReadinessSignal:
    """A single advisory readiness signal.

    Attributes:
        name: Short identifier for the signal.
        is_ready: True if the signal condition is satisfied.
        description: Human-readable description of the signal.
        detail: Additional detail about the current state.
    """

    name: str
    is_ready: bool
    description: str
    detail: str = ""


@dataclass
class RolloutReadinessReport:
    """Advisory report for graduation readiness to the next mode.

    Attributes:
        current_mode: The current enforcement mode.
        target_mode: The mode being evaluated for graduation.
        signals: Advisory readiness signals.
        overall_ready: True if all signals are satisfied.
    """

    current_mode: EnforcementMode
    target_mode: EnforcementMode
    signals: list[ReadinessSignal] = field(default_factory=list)

    @property
    def overall_ready(self) -> bool:
        """True if all advisory signals are satisfied."""
        return bool(self.signals) and all(s.is_ready for s in self.signals)

    @property
    def ready_count(self) -> int:
        """Number of signals that are satisfied."""
        return sum(1 for s in self.signals if s.is_ready)

    @property
    def total_count(self) -> int:
        """Total number of signals."""
        return len(self.signals)


class EvaluatorRolloutReadiness:
    """Evaluates readiness signals for rolling out to the next enforcement mode.

    This evaluator is advisory only. No auto-promotion occurs. The readiness
    report is surfaced in PR summaries to inform human decisions.

    Signals for OBSERVE -> WARN:
    - At least 10 PRs reviewed in OBSERVE mode (have baseline coverage)
    - False-positive rate < 20% (based on OmniMemory rejection signals)

    Signals for WARN -> BLOCK:
    - At least 10 PRs reviewed in WARN mode without complaints
    - False-positive rate < 20%
    - No BLOCKER findings in last 5 merged PRs

    Usage::

        evaluator = EvaluatorRolloutReadiness(
            prs_reviewed_in_current_mode=15,
            false_positive_rate=0.12,
            blockers_in_last_merged_prs=0,
        )
        report = evaluator.evaluate(
            current_mode=EnforcementMode.WARN,
            target_mode=EnforcementMode.BLOCK,
        )
        if report.overall_ready:
            print("Ready to graduate to BLOCK mode!")
    """

    def __init__(
        self,
        prs_reviewed_in_current_mode: int = 0,
        false_positive_rate: float = 1.0,
        blockers_in_last_merged_prs: int = 0,
        fp_threshold: float = FALSE_POSITIVE_RATE_THRESHOLD,
        min_prs_warn: int = MIN_PRS_REVIEWED_IN_WARN,
        min_clean_prs: int = MIN_CLEAN_MERGED_PRS,
    ) -> None:
        """Initialise the evaluator with current metrics.

        Args:
            prs_reviewed_in_current_mode: PRs reviewed in current mode.
            false_positive_rate: Fraction of findings rejected (0.0-1.0).
            blockers_in_last_merged_prs: BLOCKER findings in last N merged PRs.
            fp_threshold: False-positive rate threshold for readiness.
            min_prs_warn: Minimum PRs in WARN/OBSERVE mode.
            min_clean_prs: Minimum clean merged PRs for BLOCK graduation.
        """
        self._prs_reviewed = prs_reviewed_in_current_mode
        self._fp_rate = false_positive_rate
        self._blockers_in_last = blockers_in_last_merged_prs
        self._fp_threshold = fp_threshold
        self._min_prs_warn = min_prs_warn
        self._min_clean_prs = min_clean_prs

    def evaluate(
        self,
        current_mode: EnforcementMode,
        target_mode: EnforcementMode,
    ) -> RolloutReadinessReport:
        """Evaluate readiness to graduate from current_mode to target_mode.

        Args:
            current_mode: The current enforcement mode.
            target_mode: The mode being evaluated for graduation.

        Returns:
            RolloutReadinessReport with advisory signals.
        """
        report = RolloutReadinessReport(
            current_mode=current_mode,
            target_mode=target_mode,
        )

        if (
            current_mode == EnforcementMode.OBSERVE
            and target_mode == EnforcementMode.WARN
        ):
            report.signals = self._signals_for_observe_to_warn()
        elif (
            current_mode == EnforcementMode.WARN
            and target_mode == EnforcementMode.BLOCK
        ):
            report.signals = self._signals_for_warn_to_block()
        else:
            # Non-standard transition: no specific signals
            report.signals = []

        return report

    def _signals_for_observe_to_warn(self) -> list[ReadinessSignal]:
        prs_ready = self._prs_reviewed >= self._min_prs_warn
        fp_ready = self._fp_rate < self._fp_threshold

        return [
            ReadinessSignal(
                name="min_prs_reviewed",
                is_ready=prs_ready,
                description=f"At least {self._min_prs_warn} PRs reviewed in OBSERVE mode",
                detail=(f"{self._prs_reviewed}/{self._min_prs_warn} PRs reviewed"),
            ),
            ReadinessSignal(
                name="false_positive_rate",
                is_ready=fp_ready,
                description=f"False-positive rate < {self._fp_threshold:.0%}",
                detail=(
                    f"Current rate: {self._fp_rate:.1%} "
                    f"(threshold: {self._fp_threshold:.0%})"
                ),
            ),
        ]

    def _signals_for_warn_to_block(self) -> list[ReadinessSignal]:
        prs_ready = self._prs_reviewed >= self._min_prs_warn
        fp_ready = self._fp_rate < self._fp_threshold
        clean_prs_ready = self._blockers_in_last == 0

        return [
            ReadinessSignal(
                name="min_prs_reviewed",
                is_ready=prs_ready,
                description=f"At least {self._min_prs_warn} PRs reviewed in WARN mode",
                detail=(f"{self._prs_reviewed}/{self._min_prs_warn} PRs reviewed"),
            ),
            ReadinessSignal(
                name="false_positive_rate",
                is_ready=fp_ready,
                description=f"False-positive rate < {self._fp_threshold:.0%}",
                detail=(
                    f"Current rate: {self._fp_rate:.1%} "
                    f"(threshold: {self._fp_threshold:.0%})"
                ),
            ),
            ReadinessSignal(
                name="no_blockers_in_recent_merges",
                is_ready=clean_prs_ready,
                description=(
                    f"No BLOCKER findings in last {self._min_clean_prs} merged PRs"
                ),
                detail=(
                    f"{self._blockers_in_last} BLOCKER finding(s) found "
                    f"in last {self._min_clean_prs} merged PRs"
                ),
            ),
        ]


__all__ = [
    "FALSE_POSITIVE_RATE_THRESHOLD",
    "MIN_CLEAN_MERGED_PRS",
    "MIN_PRS_REVIEWED_IN_WARN",
    "EvaluatorRolloutReadiness",
    "ReadinessSignal",
    "RolloutReadinessReport",
]
