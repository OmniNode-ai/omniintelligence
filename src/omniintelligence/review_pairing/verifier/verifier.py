# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Finding Disappearance Verifier: Post-Fix CI Confirmation.

Determines whether a finding has disappeared after a fix commit by
comparing pre-fix and post-fix CI/linter results.

Architecture:
    - Pure computation: no Kafka or GitHub API calls (those belong in Effect nodes)
    - Stateless: all context is passed in via function arguments
    - Idempotent: verifying the same pair twice yields the same result

Verification outcomes:
    - ``confirmed``: finding not present in post-fix CI results
    - ``still_present``: finding still appears in post-fix CI results
    - ``config_only``: finding disappeared but a tool config was changed
      (classified as config fix, not a code transform)
    - ``disappears_without_mod``: finding disappeared but the fix commit
      did not touch the finding's file_path

Per the design doc: "No promotion without disappearance proof."
A ``confirmed`` outcome is required before a pair is eligible for
pattern promotion.

Reference: OMN-2560
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique
from uuid import UUID, uuid4

from omniintelligence.review_pairing.engine.scorer import has_config_change
from omniintelligence.review_pairing.models import (
    FindingFixPair,
    ReviewFindingObserved,
    ReviewFindingResolved,
)

logger = logging.getLogger(__name__)


@unique
class VerificationOutcome(str, Enum):
    """Outcome of a post-fix finding disappearance verification.

    Values:
        CONFIRMED: Finding is absent from post-fix CI results.
        STILL_PRESENT: Finding still appears in post-fix CI results.
        CONFIG_ONLY: Finding disappeared but only a tool config file changed
            (not a code transform; do not promote).
        DISAPPEARS_WITHOUT_MOD: Finding disappeared without modification to
            the file it was reported in (suspicious; apply penalty).
        VERIFICATION_PENDING: CI results not yet available.
    """

    CONFIRMED = "confirmed"
    STILL_PRESENT = "still_present"
    CONFIG_ONLY = "config_only"
    DISAPPEARS_WITHOUT_MOD = "disappears_without_mod"
    VERIFICATION_PENDING = "verification_pending"


@dataclass(frozen=True)
class PostFixFinding:
    """A single finding from a post-fix CI run.

    Attributes:
        rule_id: Canonical rule identifier (e.g. ``ruff:E501``).
        file_path: Relative path to the file containing the finding.
        line_start: First line number (1-indexed).
        tool_name: Name of the tool that generated this finding.
    """

    rule_id: str
    file_path: str
    line_start: int
    tool_name: str


@dataclass
class PostFixCIFindings:
    """Container for post-fix CI results used by the verifier.

    Attributes:
        commit_sha: Git SHA of the post-fix commit that was checked.
        findings: List of findings from post-fix CI runs.
        ci_run_id: Identifier of the CI run (e.g. GitHub Actions run ID).
        files_modified_by_fix: Set of files modified by the fix commit.
            Used for ``disappears_without_mod`` detection.
        files_in_pr: Set of all files modified across the entire PR.
            Used for config change detection.
        verification_source: How the verification was done.
            One of: ``ci_rerun``, ``lint_rerun``, ``merge_commit``, ``manual``.
    """

    commit_sha: str
    findings: list[PostFixFinding] = field(default_factory=list)
    ci_run_id: str = "unknown"
    files_modified_by_fix: set[str] = field(default_factory=set)
    files_in_pr: set[str] = field(default_factory=set)
    verification_source: str = "ci_rerun"


@dataclass
class VerificationResult:
    """Result of a finding disappearance verification attempt.

    Attributes:
        pair_id: UUID of the ``FindingFixPair`` that was verified.
        finding_id: UUID of the ``ReviewFindingObserved`` that was verified.
        outcome: The verification outcome.
        disappearance_confirmed: Whether the finding is confirmed absent.
        confidence_delta: Confidence score adjustment based on the outcome.
            Applied to the existing pair confidence.
        resolved_event: If outcome is CONFIRMED, the ``ReviewFindingResolved``
            event to emit to Kafka. ``None`` for other outcomes.
        verification_source: How the verification was done.
        verified_at: UTC datetime of verification.
        notes: Optional human-readable notes for debugging.
    """

    pair_id: UUID
    finding_id: UUID
    outcome: VerificationOutcome
    disappearance_confirmed: bool
    confidence_delta: float = 0.0
    resolved_event: ReviewFindingResolved | None = None
    verification_source: str = "ci_rerun"
    verified_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    notes: str = ""


class FindingDisappearanceVerifier:
    """Post-fix CI confirmation verifier for finding disappearance.

    The verifier is stateless. All I/O (Kafka, Postgres, GitHub API) is
    handled by the caller (Effect nodes). The verifier only performs
    pure computation.

    Usage::

        verifier = FindingDisappearanceVerifier()
        result = verifier.verify(
            finding=finding_observed_event,
            pair=finding_fix_pair,
            post_fix_ci=post_fix_ci_findings,
        )
        if result.outcome == VerificationOutcome.CONFIRMED:
            # emit result.resolved_event to Kafka
            # update pair.disappearance_confirmed = True in Postgres
            ...
    """

    def verify(
        self,
        finding: ReviewFindingObserved,
        pair: FindingFixPair,
        post_fix_ci: PostFixCIFindings,
    ) -> VerificationResult:
        """Verify whether a finding has disappeared after a fix.

        Args:
            finding: The original ``ReviewFindingObserved`` event.
            pair: The ``FindingFixPair`` to verify (must reference the same finding).
            post_fix_ci: Post-fix CI results to compare against.

        Returns:
            ``VerificationResult`` describing the outcome.
        """
        # Check if the finding still appears in post-fix CI results
        still_present = self._finding_still_present(finding, post_fix_ci)

        if still_present:
            logger.info(
                "FindingDisappearanceVerifier: finding=%s still present after fix=%s",
                finding.finding_id,
                pair.fix_commit_sha,
            )
            return VerificationResult(
                pair_id=pair.pair_id,
                finding_id=finding.finding_id,
                outcome=VerificationOutcome.STILL_PRESENT,
                disappearance_confirmed=False,
                confidence_delta=-0.20,
                verification_source=post_fix_ci.verification_source,
                notes=f"finding rule_id={finding.rule_id} file={finding.file_path} still present in post-fix CI",
            )

        # Finding is absent. Determine why.
        config_change = has_config_change(post_fix_ci.files_in_pr)
        if config_change:
            logger.info(
                "FindingDisappearanceVerifier: finding=%s disappeared via config change",
                finding.finding_id,
            )
            return VerificationResult(
                pair_id=pair.pair_id,
                finding_id=finding.finding_id,
                outcome=VerificationOutcome.CONFIG_ONLY,
                disappearance_confirmed=False,
                confidence_delta=-0.10,
                verification_source=post_fix_ci.verification_source,
                notes="finding disappeared but a tool config file was modified in the PR",
            )

        disappears_without_mod = (
            len(post_fix_ci.files_modified_by_fix) > 0
            and finding.file_path not in post_fix_ci.files_modified_by_fix
        )
        if disappears_without_mod:
            logger.info(
                "FindingDisappearanceVerifier: finding=%s disappeared without modifying its file",
                finding.finding_id,
            )
            return VerificationResult(
                pair_id=pair.pair_id,
                finding_id=finding.finding_id,
                outcome=VerificationOutcome.DISAPPEARS_WITHOUT_MOD,
                disappearance_confirmed=False,
                confidence_delta=-0.15,
                verification_source=post_fix_ci.verification_source,
                notes=(
                    f"finding disappeared but fix did not touch {finding.file_path}; "
                    "flagged for manual review"
                ),
            )

        # Confirmed: finding is absent and the fix touched the right file
        resolved_event = ReviewFindingResolved(
            resolution_id=uuid4(),
            finding_id=finding.finding_id,
            fix_commit_sha=pair.fix_commit_sha,
            verified_at_commit_sha=post_fix_ci.commit_sha,
            ci_run_id=post_fix_ci.ci_run_id,
            resolved_at=datetime.now(tz=UTC),
        )

        logger.info(
            "FindingDisappearanceVerifier: finding=%s CONFIRMED absent after fix=%s",
            finding.finding_id,
            pair.fix_commit_sha,
        )

        return VerificationResult(
            pair_id=pair.pair_id,
            finding_id=finding.finding_id,
            outcome=VerificationOutcome.CONFIRMED,
            disappearance_confirmed=True,
            confidence_delta=0.0,
            resolved_event=resolved_event,
            verification_source=post_fix_ci.verification_source,
            notes=f"finding rule_id={finding.rule_id} confirmed absent in post-fix CI run {post_fix_ci.ci_run_id}",
        )

    @staticmethod
    def _finding_still_present(
        finding: ReviewFindingObserved,
        post_fix_ci: PostFixCIFindings,
    ) -> bool:
        """Check if the finding is still present in the post-fix CI results.

        A finding is considered still present if any post-fix finding matches
        on both ``rule_id`` and ``file_path``. Line number is NOT required to
        match because the fix may have shifted line numbers.

        Args:
            finding: The original finding to look up.
            post_fix_ci: Post-fix CI results.

        Returns:
            ``True`` if the finding is still present.
        """
        # Extract bare rule code for comparison (e.g., "E501" from "ruff:E501")
        bare_rule = (
            finding.rule_id.split(":")[-1]
            if ":" in finding.rule_id
            else finding.rule_id
        )

        for post_finding in post_fix_ci.findings:
            post_bare = (
                post_finding.rule_id.split(":")[-1]
                if ":" in post_finding.rule_id
                else post_finding.rule_id
            )
            rule_matches = (
                post_finding.rule_id == finding.rule_id
                or post_bare == bare_rule
                or post_finding.rule_id == bare_rule
            )
            if rule_matches and post_finding.file_path == finding.file_path:
                return True
        return False
