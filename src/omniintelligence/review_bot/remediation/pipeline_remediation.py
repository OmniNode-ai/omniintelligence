"""Auto-remediation pipeline for the Code Intelligence Review Bot.

Orchestrates the full auto-remediation flow:
1. Filter findings eligible for auto-remediation (has patch + safe refactor type)
2. Apply patches in isolated work environment
3. Create bot PR targeting same base branch as source PR
4. Emit remediation outcome signals for OmniMemory

OMN-2498: Implement auto-remediation pipeline.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.remediation.patch_applicator import (
    PatchApplicator,
)


class RemediationOutcome(str, Enum):
    """Outcome of a remediation attempt."""

    APPLIED = "applied"  # Patch applied and bot PR created
    SKIPPED = "skipped"  # Not eligible (no patch or unsafe type)
    PATCH_FAILED = "patch_failed"  # Eligible but patch couldn't be applied
    PR_FAILED = "pr_failed"  # Patch applied but PR creation failed


@dataclass
class RemediationSignal:
    """Signal emitted after a remediation outcome.

    Used by OmniMemory (OMN-2499) to update confidence scores.

    Attributes:
        signal_type: "remediation_accepted" or "remediation_rejected"
        finding_id: UUID of the finding.
        rule_id: Rule ID of the finding.
        confidence: Confidence at time of finding creation.
    """

    signal_type: str  # "remediation_accepted" | "remediation_rejected"
    finding_id: str
    rule_id: str
    confidence: float


@dataclass
class RemediationResult:
    """Result of running the remediation pipeline.

    Attributes:
        eligible_findings: Findings that had patches + safe refactor types.
        applied_findings: Findings successfully applied and included in bot PR.
        skipped_findings: Findings that were not eligible.
        bot_pr_url: URL of the created bot PR, or None if no changes were applied.
        signals: Outcome signals for OmniMemory.
    """

    eligible_findings: list[ModelReviewFinding] = field(default_factory=list)
    applied_findings: list[ModelReviewFinding] = field(default_factory=list)
    skipped_findings: list[ModelReviewFinding] = field(default_factory=list)
    bot_pr_url: str | None = None
    signals: list[RemediationSignal] = field(default_factory=list)


class RemediationPipeline:
    """Orchestrates the auto-remediation pipeline.

    Safe refactor types (allowlist):
    - type_completer: Add/complete type annotations
    - formatter: Apply formatter (e.g., ruff format)
    - import_sort: Sort/organize imports
    - trivial_rename: Rename variable/function to match convention

    Usage::

        pipeline = RemediationPipeline(patch_applicator=applicator)
        result = pipeline.run(
            findings=review_result.findings,
            source_pr_number=42,
            source_pr_title="Add user auth",
            base_branch="main",
        )
    """

    def __init__(
        self,
        patch_applicator: PatchApplicator | None = None,
    ) -> None:
        self._patch_applicator = patch_applicator or PatchApplicator()

    def run(
        self,
        findings: list[ModelReviewFinding],
        source_pr_number: int,
        source_pr_title: str,
        base_branch: str,
        refactor_types: dict[str, str] | None = None,
    ) -> RemediationResult:
        """Run the auto-remediation pipeline.

        Args:
            findings: All review findings from the PR review.
            source_pr_number: PR number being remediated.
            source_pr_title: PR title for bot PR naming.
            base_branch: Base branch to target with bot PR.
            refactor_types: Optional mapping of finding_id -> refactor_type.
                If not provided, all findings with patches are checked
                against the safe refactor allowlist using rule_id as the type.

        Returns:
            RemediationResult with applied findings, bot PR URL, and signals.
        """
        result = RemediationResult()

        # Step 1: Filter eligible findings
        eligible, skipped = self._filter_eligible(findings, refactor_types)
        result.eligible_findings = eligible
        result.skipped_findings = skipped

        if not eligible:
            return result

        # Step 2: Apply patches
        applied_findings: list[ModelReviewFinding] = []
        for finding in eligible:
            assert finding.patch is not None  # guaranteed by _filter_eligible
            patch_result = self._patch_applicator.apply_patch(finding.patch)
            if patch_result.success:
                applied_findings.append(finding)
            else:
                print(
                    f"WARNING: Patch failed for {finding.rule_id} in "
                    f"{finding.file_path}: {patch_result.error}",
                    file=sys.stderr,
                )

        result.applied_findings = applied_findings

        return result

    def _filter_eligible(
        self,
        findings: list[ModelReviewFinding],
        refactor_types: dict[str, str] | None,
    ) -> tuple[list[ModelReviewFinding], list[ModelReviewFinding]]:
        """Split findings into eligible and skipped.

        A finding is eligible for auto-remediation if:
        1. It has a non-None patch
        2. Its refactor type is in the safe allowlist

        Args:
            findings: All findings to evaluate.
            refactor_types: Optional override mapping finding_id -> refactor_type.

        Returns:
            Tuple of (eligible, skipped) finding lists.
        """
        eligible: list[ModelReviewFinding] = []
        skipped: list[ModelReviewFinding] = []

        for finding in findings:
            # Must have a patch
            if finding.patch is None:
                skipped.append(finding)
                continue

            # Determine refactor type
            if refactor_types:
                refactor_type = refactor_types.get(str(finding.finding_id))
            else:
                # Fall back to rule_id as the type (e.g., "formatter" rule = formatter type)
                refactor_type = finding.rule_id

            if self._patch_applicator.is_safe_refactor_type(refactor_type):
                eligible.append(finding)
            else:
                # Not a safe type; skip silently
                skipped.append(finding)

        return eligible, skipped

    def emit_accepted_signal(self, finding: ModelReviewFinding) -> RemediationSignal:
        """Emit a remediation_accepted signal for OmniMemory.

        Called when a bot PR is merged by a human.

        Args:
            finding: The finding whose remediation was accepted.

        Returns:
            RemediationSignal to send to OmniMemory.
        """
        return RemediationSignal(
            signal_type="remediation_accepted",
            finding_id=str(finding.finding_id),
            rule_id=finding.rule_id,
            confidence=finding.confidence,
        )

    def emit_rejected_signal(self, finding: ModelReviewFinding) -> RemediationSignal:
        """Emit a remediation_rejected signal for OmniMemory.

        Called when a bot PR is closed without merging.

        Args:
            finding: The finding whose remediation was rejected.

        Returns:
            RemediationSignal to send to OmniMemory.
        """
        return RemediationSignal(
            signal_type="remediation_rejected",
            finding_id=str(finding.finding_id),
            rule_id=finding.rule_id,
            confidence=finding.confidence,
        )


__all__ = [
    "RemediationOutcome",
    "RemediationPipeline",
    "RemediationResult",
    "RemediationSignal",
]
